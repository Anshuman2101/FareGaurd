# LLD — Synthetic Data Generator (Phase 0)

Code: [tools/datagen/generate.py](../../tools/datagen/generate.py) · Tests:
[tools/datagen/test_generate.py](../../tools/datagen/test_generate.py)

## Purpose
Produce realistic, fully synthetic input for later phases: normal booking traffic plus a small
share of **labeled** anomalies (so the rules engine, Kafka fraud pipeline and AI agent can be
checked against ground truth).

## Usage
```
python3 tools/datagen/generate.py [--seed 42] [--agencies 20] [--bookings 10000] [--days 30] \
    [--start 2026-09-20] [--out data/generated]
python3 -m unittest discover -s tools/datagen -v
```
Stdlib only, Python 3.9+. Same seed gives byte-identical output. Output goes to `data/generated/`
(git-ignored).

## Core idea: replay, don't fabricate
Generating bookings independently would break the domain-model invariants. Instead, the generator
creates *booking requests* and lifecycle *transitions* on one time-ordered queue and replays them
the way the real system would:
1. Request arrives → reject if suspended, then check `sub_limit`, then agency `total_limit`.
2. Pass → create `PENDING` booking, **reserve** amount on SubAgent and CreditLine.
3. Planned transitions fire later (`CONFIRMED`; `CANCELLED`/`REFUNDED` **release** the amount).
4. Events at or after the window end are not applied, so final statuses and `utilized_amount`
   are a consistent snapshot at the end of the window.

Lifecycle odds: 90% of bookings confirm (1-60 min), 10% cancel while pending; of confirmed ones
~5% cancel late (1-72 h) and ~4% are refunded (3-20 days).

## Output files (`data/generated/`)
| File | Content |
|---|---|
| `agencies.jsonl`, `credit_lines.jsonl`, `sub_agents.jsonl` | Entities with final `utilized_amount` |
| `bookings.jsonl` | Accepted bookings in creation order (money in integer minor units, ISO-8601 UTC) |
| `rejected_requests.jsonl` | Requests refused by the checks, with `reason` |
| `labels.jsonl` | Ground truth: `{record_type, record_id, pattern}` for anomalous sub-agents, bookings, rejected requests |
| `manifest.json` | Seed, counts, status/reason/label breakdowns |

Labels live in their own file so the `Booking` schema stays clean and detectors can't "cheat".

## Scale and shape (defaults)
20 agencies, 3-7 sub-agents each (~100 total), ~9-10k accepted bookings over 30 days.
Normal sub-agents use roughly 20-70% of their sub-limit; amounts are lognormal; request times
cluster around business hours. ~5% of agencies/sub-agents get suspended mid-window and then
attempt a few bookings (rejected as `ACCOUNT_SUSPENDED`).

## Anomaly patterns (~12% of non-suspended sub-agents get exactly one)
| Pattern | What it does | Where it shows up |
|---|---|---|
| `VELOCITY_BURST` | 15-30 small bookings within a few minutes | bookings |
| `NEAR_LIMIT` | In the last 40 h, utilization is pushed to 80% → 90% → 97% of `sub_limit`, never cancelled | bookings (and rejected, if the agency pool runs out) |
| `OVER_LIMIT_PROBE` | 2-4 requests above remaining headroom in the last 10 days | rejected requests |

## Known quirk (intentional)
Over-allocated agencies naturally hit `AGENCY_LIMIT_EXCEEDED`: in the default run ~700 of ~760
rejections, concentrated in 4 agencies. These are **not** labeled anomalies: they are the
realistic background noise that the over-allocation risk signal should explain, and a good
detector must not confuse them with the labeled patterns.
