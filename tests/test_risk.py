import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from warehouse_rescue.risk import evaluate_order


class RiskRuleTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)
        self.events = [
            {"event_id": "01", "event_type": "order.released", "occurred_at": self.now.isoformat(),
             "warehouse_id": "WH-1", "source": "simulator", "payload": {
                 "carrier_cutoff_at": (self.now + timedelta(minutes=20)).isoformat(), "expected_line_count": 2}},
            {"event_id": "02", "event_type": "order.line_picked", "occurred_at": (self.now + timedelta(seconds=1)).isoformat(),
             "warehouse_id": "WH-1", "source": "simulator", "payload": {"sku": "A", "quantity": 1}},
            {"event_id": "03", "event_type": "order.line_short", "occurred_at": (self.now + timedelta(seconds=2)).isoformat(),
             "warehouse_id": "WH-1", "source": "simulator", "payload": {
                 "sku": "B", "requested_qty": 1, "picked_qty": 0, "reserve_qty": 5, "reserve_location": "R-1"}},
        ]

    def test_opens_high_risk_case_with_actionable_evidence(self):
        case = evaluate_order("ORD-1", self.events, now=self.now)
        self.assertEqual(case["risk_level"], "HIGH")
        self.assertEqual(case["status"], "OPEN")
        self.assertIn("B", case["recommendation"])
        self.assertEqual(case["evidence"]["short_lines"][0]["reserve_qty"], 5)

    def test_does_not_open_case_far_before_cutoff(self):
        release = dict(self.events[0])
        release["payload"] = {"carrier_cutoff_at": (self.now + timedelta(hours=4)).isoformat(), "expected_line_count": 2}
        case = evaluate_order("ORD-1", [release, self.events[2]], now=self.now)
        self.assertIsNone(case)

    def test_replenishment_changes_case_to_in_progress(self):
        task = {"event_id": "04", "event_type": "replenishment.started", "occurred_at": (self.now + timedelta(seconds=3)).isoformat(),
                "warehouse_id": "WH-1", "source": "simulator", "payload": {"sku": "B"}}
        case = evaluate_order("ORD-1", self.events + [task], now=self.now)
        self.assertEqual(case["status"], "IN_PROGRESS")
        self.assertIn("Monitor", case["recommendation"])

    def test_resolves_existing_case_when_order_is_packed(self):
        packed = {"event_id": "04", "event_type": "order.packed", "occurred_at": (self.now + timedelta(seconds=3)).isoformat(),
                  "warehouse_id": "WH-1", "source": "simulator", "payload": {}}
        case = evaluate_order("ORD-1", self.events + [packed], now=self.now, existing_case=True)
        self.assertEqual(case["status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
