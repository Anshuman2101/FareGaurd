"""Synthetic data generator for FareGuard (Phase 0).

Produces Agencies, CreditLines, SubAgents and Bookings as JSON Lines files, plus the rejected
requests and ground-truth anomaly labels that later phases (rules engine, fraud pipeline, AI
agent) will consume. Everything is synthetic and deterministic for a given seed.

Design: all booking requests and lifecycle transitions are put on one time-ordered event queue and
replayed exactly the way the real system would handle them (check both limits, reserve on
creation, release on cancel/refund), so the generated data always satisfies the domain-model
invariants. See docs/lld/00-synthetic-data-generator.md.

Stdlib only; runs on Python 3.9+.
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import random
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CURRENCIES = ["USD", "EUR", "GBP", "INR"]
AIRPORTS = ["JFK", "LHR", "CDG", "FRA", "DXB", "SIN", "BLR", "DEL", "SYD", "NRT", "LAX", "AMS"]
NAME_PREFIX = ["Blue", "Global", "Sky", "Prime", "Nova", "Atlas", "Orbit", "Zenith", "Coral", "Summit"]
NAME_SUFFIX = ["Travels", "Tours", "Journeys", "Voyages", "Holidays", "Trips"]

MIN_AMOUNT = 5_000  # 50.00 in minor units
SUB_AGENT_COUNT = (3, 7)
OVER_ALLOCATED_SHARE = 0.25
SUSPENDED_SHARE = 0.05
ANOMALOUS_SUB_AGENT_SHARE = 0.12
ANOMALY_PATTERNS = ["VELOCITY_BURST", "NEAR_LIMIT", "OVER_LIMIT_PROBE"]
DAY = 86_400


def _iso(start: datetime, offset_seconds: int) -> str:
    return (start + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


class Generator:
    def __init__(self, seed: int, agencies: int, bookings: int, days: int, start: datetime):
        self.rng = random.Random(seed)
        self.n_agencies = agencies
        self.target_bookings = bookings
        self.start = start
        self.window = days * DAY  # seconds; the simulation covers [0, window)

        self.agencies: Dict[str, Dict[str, Any]] = {}
        self.credit_lines: Dict[str, Dict[str, Any]] = {}
        self.sub_agents: Dict[str, Dict[str, Any]] = {}
        self.bookings: Dict[str, Dict[str, Any]] = {}
        self.rejected: List[Dict[str, Any]] = []
        self.labels: List[Dict[str, str]] = []

        # Internal-only state, not part of the schema.
        self._suspended_from: Dict[str, int] = {}
        self._cl_updated: Dict[str, int] = {}
        self._queue: List[Any] = []
        self._seq = 0

    # ---------- helpers ----------
    def _uuid(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def _push(self, t: int, kind: str, payload: Dict[str, Any]) -> None:
        self._seq += 1
        heapq.heappush(self._queue, (t, self._seq, kind, payload))

    def _ts(self, offset: Optional[int]) -> Optional[str]:
        return None if offset is None else _iso(self.start, offset)

    # ---------- entity construction ----------
    def build_entities(self) -> None:
        rng = self.rng
        for i in range(self.n_agencies):
            agency_id = self._uuid()
            created = -rng.randint(60, 900) * DAY
            suspended = rng.random() < SUSPENDED_SHARE
            self.agencies[agency_id] = {
                "id": agency_id,
                "name": "%s %s %02d" % (rng.choice(NAME_PREFIX), rng.choice(NAME_SUFFIX), i + 1),
                "status": "SUSPENDED" if suspended else "ACTIVE",
                "created_at": created,
            }
            if suspended:
                self._suspended_from[agency_id] = int(self.window * rng.uniform(0.5, 0.8))

            pool = rng.randint(200, 2000) * 1000 * 100
            self.credit_lines[agency_id] = {
                "id": self._uuid(),
                "agency_id": agency_id,
                "currency": rng.choice(CURRENCIES),
                "total_limit": pool,
                "utilized_amount": 0,
            }
            self._cl_updated[agency_id] = created
            self._build_sub_agents(agency_id, pool, created)

    def _build_sub_agents(self, agency_id: str, pool: int, agency_created: int) -> None:
        rng = self.rng
        count = rng.randint(*SUB_AGENT_COUNT)
        if rng.random() < OVER_ALLOCATED_SHARE:
            # Over-allocated: sub-limits sum to more than the agency pool (a fraud-risk signal).
            fractions = [rng.uniform(0.35, 0.8) for _ in range(count)]
        else:
            weights = [rng.uniform(0.5, 1.5) for _ in range(count)]
            total_share = rng.uniform(0.7, 1.0)
            fractions = [w / sum(weights) * total_share for w in weights]

        agency_name = self.agencies[agency_id]["name"]
        for n, fraction in enumerate(fractions):
            sub_id = self._uuid()
            suspended = rng.random() < SUSPENDED_SHARE
            self.sub_agents[sub_id] = {
                "id": sub_id,
                "agency_id": agency_id,
                "name": "%s Desk %d" % (agency_name, n + 1),
                "status": "SUSPENDED" if suspended else "ACTIVE",
                "sub_limit": int(pool * fraction) // 100 * 100,
                "utilized_amount": 0,
                "created_at": agency_created + rng.randint(1, 30) * DAY,
            }
            if suspended:
                self._suspended_from[sub_id] = int(self.window * rng.uniform(0.5, 0.8))

    # ---------- request scheduling ----------
    def _is_suspended(self, sub: Dict[str, Any], t: int) -> bool:
        inf = float("inf")
        return (
            t >= self._suspended_from.get(sub["id"], inf)
            or t >= self._suspended_from.get(sub["agency_id"], inf)
        )

    def _ever_suspended(self, sub: Dict[str, Any]) -> bool:
        return sub["id"] in self._suspended_from or sub["agency_id"] in self._suspended_from

    def _horizon(self, sub: Dict[str, Any]) -> int:
        return min(
            self.window,
            self._suspended_from.get(sub["id"], self.window),
            self._suspended_from.get(sub["agency_id"], self.window),
        )

    def _random_time(self, horizon: int) -> int:
        day = self.rng.randrange(max(1, horizon // DAY))
        hour = min(23.99, max(0.0, self.rng.gauss(13, 3.5)))
        return min(horizon - 1, day * DAY + int(hour * 3600))

    def _request(self, sub_id: str, amount: Optional[int], kind: str = "fixed",
                 target: float = 0.0, pattern: Optional[str] = None,
                 force_confirm: bool = False) -> Dict[str, Any]:
        return {"request_id": self._uuid(), "sub_agent_id": sub_id, "amount": amount, "kind": kind,
                "target": target, "pattern": pattern, "force_confirm": force_confirm}

    def schedule_requests(self) -> None:
        rng = self.rng
        subs = list(self.sub_agents.values())
        per_sub = self.target_bookings / max(1, len(subs))
        eligible = [s for s in subs if not self._ever_suspended(s)]
        k = min(len(eligible), max(1, round(ANOMALOUS_SUB_AGENT_SHARE * len(subs)))) if eligible else 0
        anomalous = {s["id"]: rng.choice(ANOMALY_PATTERNS) for s in rng.sample(eligible, k)}

        for sub in subs:
            sub_id, limit = sub["id"], sub["sub_limit"]
            horizon = self._horizon(sub)
            share = horizon / self.window
            n = max(5, round(per_sub * rng.uniform(0.6, 1.4) * share))
            # Size normal bookings so a sub-agent uses roughly 20-70% of its sub-limit over the window.
            mean_amount = rng.uniform(0.2, 0.7) * share * limit / (n * 0.85)
            for _ in range(n):
                scale = rng.lognormvariate(0, 0.5) / math.exp(0.125)
                amount = max(MIN_AMOUNT, int(mean_amount * scale) // 100 * 100)
                self._push(self._random_time(horizon), "request", self._request(sub_id, amount))

            if self._ever_suspended(sub):
                # Attempts after suspension; these must be rejected.
                for _ in range(rng.randint(3, 8)):
                    t = rng.randint(horizon, self.window - 1)
                    amount = max(MIN_AMOUNT, int(mean_amount) // 100 * 100)
                    self._push(t, "request", self._request(sub_id, amount))

            pattern = anomalous.get(sub_id)
            if pattern:
                self.labels.append({"record_type": "sub_agent", "record_id": sub_id, "pattern": pattern})
                self._schedule_anomaly(sub, pattern)

    def _schedule_anomaly(self, sub: Dict[str, Any], pattern: str) -> None:
        rng, sub_id, limit = self.rng, sub["id"], sub["sub_limit"]
        if pattern == "VELOCITY_BURST":
            t = int(self.window * rng.uniform(0.1, 0.95))
            for _ in range(rng.randint(15, 30)):
                amount = max(MIN_AMOUNT, int(limit * rng.uniform(0.005, 0.015)) // 100 * 100)
                self._push(t, "request", self._request(sub_id, amount, pattern=pattern))
                t += rng.randint(5, 15)
        elif pattern == "NEAR_LIMIT":
            # Amounts are resolved at replay time so utilization climbs to the target fraction.
            for hours_before, target in ((40, 0.80), (20, 0.90), (4, 0.97)):
                t = self.window - hours_before * 3600
                self._push(t, "request",
                           self._request(sub_id, None, "fill", target, pattern, force_confirm=True))
        else:  # OVER_LIMIT_PROBE
            for _ in range(rng.randint(2, 4)):
                t = self.window - rng.randint(3600, 10 * DAY)
                self._push(t, "request", self._request(sub_id, None, "probe", pattern=pattern))

    # ---------- replay ----------
    def run(self) -> None:
        while self._queue:
            t, _, kind, payload = heapq.heappop(self._queue)
            if t >= self.window:
                break
            if kind == "request":
                self._handle_request(t, payload)
            else:
                self._handle_transition(t, payload)

    def _resolve_amount(self, sub: Dict[str, Any], req: Dict[str, Any]) -> Optional[int]:
        if req["kind"] == "fill":
            amount = int(req["target"] * sub["sub_limit"]) - sub["utilized_amount"]
            return amount if amount >= MIN_AMOUNT else None
        if req["kind"] == "probe":
            headroom = sub["sub_limit"] - sub["utilized_amount"]
            return max(MIN_AMOUNT, headroom) + int(sub["sub_limit"] * self.rng.uniform(0.05, 0.5))
        return req["amount"]

    def _handle_request(self, t: int, req: Dict[str, Any]) -> None:
        sub = self.sub_agents[req["sub_agent_id"]]
        agency_id = sub["agency_id"]
        credit = self.credit_lines[agency_id]
        amount = self._resolve_amount(sub, req)
        if amount is None:
            return

        reason = None
        if self._is_suspended(sub, t):
            reason = "ACCOUNT_SUSPENDED"
        elif sub["utilized_amount"] + amount > sub["sub_limit"]:
            reason = "SUB_LIMIT_EXCEEDED"
        elif credit["utilized_amount"] + amount > credit["total_limit"]:
            reason = "AGENCY_LIMIT_EXCEEDED"

        if reason:
            self.rejected.append({
                "request_id": req["request_id"], "sub_agent_id": sub["id"], "agency_id": agency_id,
                "currency": credit["currency"], "amount": amount, "reason": reason,
                "requested_at": self._ts(t),
            })
            if req["pattern"]:
                self.labels.append({"record_type": "rejected_request",
                                    "record_id": req["request_id"], "pattern": req["pattern"]})
            return

        sub["utilized_amount"] += amount
        credit["utilized_amount"] += amount
        self._cl_updated[agency_id] = t
        booking_id = self._uuid()
        origin, destination = self.rng.sample(AIRPORTS, 2)
        self.bookings[booking_id] = {
            "id": booking_id, "sub_agent_id": sub["id"], "agency_id": agency_id,
            "currency": credit["currency"], "amount": amount, "status": "PENDING",
            "created_at": t, "confirmed_at": None, "closed_at": None,
            "origin": origin, "destination": destination,
            "traveler_ref": "TRV-%08d" % self.rng.randrange(10 ** 8),
        }
        if req["pattern"]:
            self.labels.append({"record_type": "booking", "record_id": booking_id,
                                "pattern": req["pattern"]})
        self._plan_lifecycle(t, booking_id, req["force_confirm"])

    def _plan_lifecycle(self, created: int, booking_id: str, force_confirm: bool) -> None:
        rng = self.rng
        if not force_confirm and rng.random() >= 0.90:
            self._push(created + rng.randint(5, 120) * 60, "transition", {"id": booking_id, "to": "CANCELLED"})
            return
        confirmed = created + rng.randint(1, 60) * 60
        self._push(confirmed, "transition", {"id": booking_id, "to": "CONFIRMED"})
        roll = rng.random()
        if force_confirm or roll >= 0.09:
            return
        if roll < 0.05:
            self._push(confirmed + rng.randint(1, 72) * 3600, "transition", {"id": booking_id, "to": "CANCELLED"})
        else:
            self._push(confirmed + rng.randint(3, 20) * DAY, "transition", {"id": booking_id, "to": "REFUNDED"})

    def _handle_transition(self, t: int, event: Dict[str, Any]) -> None:
        booking = self.bookings[event["id"]]
        new = event["to"]
        allowed = {"PENDING": {"CONFIRMED", "CANCELLED"}, "CONFIRMED": {"CANCELLED", "REFUNDED"}}
        assert new in allowed.get(booking["status"], set()), (booking["status"], new)
        booking["status"] = new
        if new == "CONFIRMED":
            booking["confirmed_at"] = t
            return
        booking["closed_at"] = t
        sub = self.sub_agents[booking["sub_agent_id"]]
        credit = self.credit_lines[booking["agency_id"]]
        sub["utilized_amount"] -= booking["amount"]
        credit["utilized_amount"] -= booking["amount"]
        self._cl_updated[booking["agency_id"]] = t
        assert sub["utilized_amount"] >= 0 and credit["utilized_amount"] >= 0

    # ---------- output ----------
    def records(self) -> Dict[str, List[Dict[str, Any]]]:
        agencies = [dict(a, created_at=self._ts(a["created_at"])) for a in self.agencies.values()]
        credit_lines = [dict(c, updated_at=self._ts(self._cl_updated[c["agency_id"]]))
                        for c in self.credit_lines.values()]
        sub_agents = [dict(s, created_at=self._ts(s["created_at"])) for s in self.sub_agents.values()]
        bookings = [dict(b, created_at=self._ts(b["created_at"]), confirmed_at=self._ts(b["confirmed_at"]),
                         closed_at=self._ts(b["closed_at"])) for b in self.bookings.values()]
        return {"agencies": agencies, "credit_lines": credit_lines, "sub_agents": sub_agents,
                "bookings": bookings, "rejected_requests": self.rejected, "labels": self.labels}


def generate(seed: int = 42, agencies: int = 20, bookings: int = 10_000, days: int = 30,
             start: str = "2026-09-20") -> Dict[str, List[Dict[str, Any]]]:
    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    gen = Generator(seed, agencies, bookings, days, start_dt)
    gen.build_entities()
    gen.schedule_requests()
    gen.run()
    return gen.records()


def write(data: Dict[str, List[Dict[str, Any]]], out_dir: Path, seed: int) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in data.items():
        with open(out_dir / ("%s.jsonl" % name), "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
    manifest = {
        "seed": seed,
        "counts": {name: len(rows) for name, rows in data.items()},
        "booking_status": dict(Counter(b["status"] for b in data["bookings"])),
        "rejection_reasons": dict(Counter(r["reason"] for r in data["rejected_requests"])),
        "labels": dict(Counter("%s/%s" % (l["record_type"], l["pattern"]) for l in data["labels"])),
    }
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate FareGuard synthetic data.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--agencies", type=int, default=20)
    parser.add_argument("--bookings", type=int, default=10_000, help="approximate accepted bookings")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start", default="2026-09-20", help="window start date, YYYY-MM-DD (UTC)")
    parser.add_argument("--out", default="data/generated", type=Path)
    args = parser.parse_args()
    data = generate(args.seed, args.agencies, args.bookings, args.days, args.start)
    print(json.dumps(write(data, args.out, args.seed), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
