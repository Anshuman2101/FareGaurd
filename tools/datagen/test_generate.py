import unittest
from collections import defaultdict

from generate import generate

ACTIVE = ("PENDING", "CONFIRMED")


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate(seed=7)

    def test_deterministic_for_same_seed(self):
        self.assertEqual(self.data, generate(seed=7))
        self.assertNotEqual(self.data["bookings"], generate(seed=8)["bookings"])

    def test_scale_is_in_expected_range(self):
        self.assertEqual(len(self.data["agencies"]), 20)
        self.assertTrue(7_000 <= len(self.data["bookings"]) <= 13_000, len(self.data["bookings"]))

    def test_money_is_integer_minor_units(self):
        for b in self.data["bookings"]:
            self.assertIsInstance(b["amount"], int)
        for c in self.data["credit_lines"]:
            self.assertIsInstance(c["total_limit"], int)
            self.assertIsInstance(c["utilized_amount"], int)

    def test_utilization_matches_active_bookings_and_respects_limits(self):
        by_sub, by_agency = defaultdict(int), defaultdict(int)
        for b in self.data["bookings"]:
            if b["status"] in ACTIVE:
                by_sub[b["sub_agent_id"]] += b["amount"]
                by_agency[b["agency_id"]] += b["amount"]
        for s in self.data["sub_agents"]:
            self.assertEqual(s["utilized_amount"], by_sub[s["id"]])
            self.assertLessEqual(s["utilized_amount"], s["sub_limit"])
        for c in self.data["credit_lines"]:
            self.assertEqual(c["utilized_amount"], by_agency[c["agency_id"]])
            self.assertLessEqual(c["utilized_amount"], c["total_limit"])

    def test_referential_integrity_and_timestamps(self):
        agencies = {a["id"] for a in self.data["agencies"]}
        subs = {s["id"]: s for s in self.data["sub_agents"]}
        for b in self.data["bookings"]:
            self.assertIn(b["agency_id"], agencies)
            self.assertEqual(subs[b["sub_agent_id"]]["agency_id"], b["agency_id"])
            self.assertIn(b["status"], {"PENDING", "CONFIRMED", "CANCELLED", "REFUNDED"})
            if b["confirmed_at"]:
                self.assertLessEqual(b["created_at"], b["confirmed_at"])
            if b["closed_at"]:
                self.assertLessEqual(b["confirmed_at"] or b["created_at"], b["closed_at"])
            self.assertEqual(b["closed_at"] is not None, b["status"] in ("CANCELLED", "REFUNDED"))

    def test_over_allocation_exists(self):
        limits = {c["agency_id"]: c["total_limit"] for c in self.data["credit_lines"]}
        allocated = defaultdict(int)
        for s in self.data["sub_agents"]:
            allocated[s["agency_id"]] += s["sub_limit"]
        self.assertTrue(any(allocated[a] > limits[a] for a in limits))

    def test_all_anomaly_patterns_are_labelled(self):
        patterns = {l["pattern"] for l in self.data["labels"]}
        self.assertEqual(patterns, {"VELOCITY_BURST", "NEAR_LIMIT", "OVER_LIMIT_PROBE"})

    def test_rejections_cover_expected_reasons(self):
        reasons = {r["reason"] for r in self.data["rejected_requests"]}
        self.assertIn("SUB_LIMIT_EXCEEDED", reasons)
        self.assertIn("ACCOUNT_SUSPENDED", reasons)


if __name__ == "__main__":
    unittest.main()
