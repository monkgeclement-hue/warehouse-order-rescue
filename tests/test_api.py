import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from warehouse_rescue.main import app
from warehouse_rescue import store


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        store.DB_PATH = Path(self.temp_dir.name) / "api-test.sqlite3"
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def test_demo_creates_visible_case_from_synthetic_events(self):
        result = self.client.post("/api/v1/demo/run")
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["accepted_events"], 6)
        self.assertEqual(body["case"]["risk_level"], "HIGH")
        cases = self.client.get("/api/v1/cases").json()["cases"]
        self.assertEqual(cases[0]["case_id"], body["case"]["case_id"])

    def test_duplicate_event_is_accepted_only_once(self):
        now = datetime.now(timezone.utc)
        event = {
            "event_id": "dfe257e4-5631-4b58-a912-8a5f526189bc",
            "schema_version": "1.0",
            "event_type": "order.released",
            "occurred_at": now.isoformat(),
            "warehouse_id": "WH-1",
            "order_id": "ORD-IDEMPOTENT",
            "source": "test",
            "payload": {"carrier_cutoff_at": (now + timedelta(hours=4)).isoformat(), "expected_line_count": 1},
        }
        first = self.client.post("/api/v1/events", json=event).json()
        second = self.client.post("/api/v1/events", json=event).json()
        self.assertTrue(first["accepted"])
        self.assertTrue(second["duplicate"])

    def test_rejects_event_without_timezone(self):
        event = {
            "event_id": "8a20f4f7-b70b-4c57-ad19-44ce45e5b247",
            "schema_version": "1.0",
            "event_type": "order.released",
            "occurred_at": "2026-10-08T10:00:00",
            "warehouse_id": "WH-1",
            "order_id": "ORD-NAIVE-TIME",
            "source": "test",
            "payload": {"carrier_cutoff_at": "2026-10-08T11:00:00Z", "expected_line_count": 1},
        }
        response = self.client.post("/api/v1/events", json=event)
        self.assertEqual(response.status_code, 422)

    def test_deadline_recheck_raises_risk_without_a_new_event(self):
        now = datetime.now(timezone.utc)
        events = [
            {
                "event_id": "1ce3d577-f9df-45d0-a49d-4446435b546a",
                "schema_version": "1.0",
                "event_type": "order.released",
                "occurred_at": now.isoformat(),
                "warehouse_id": "WH-1",
                "order_id": "ORD-DEADLINE",
                "source": "test",
                "payload": {"carrier_cutoff_at": (now + timedelta(minutes=40)).isoformat(), "expected_line_count": 1},
            },
            {
                "event_id": "c19a70e9-b75d-4d30-ae54-f5da57b62523",
                "schema_version": "1.0",
                "event_type": "order.line_short",
                "occurred_at": (now + timedelta(milliseconds=100)).isoformat(),
                "warehouse_id": "WH-1",
                "order_id": "ORD-DEADLINE",
                "source": "test",
                "payload": {"sku": "SKU-1", "requested_qty": 1, "picked_qty": 0, "reserve_qty": 2},
            },
        ]
        for event in events:
            response = self.client.post("/api/v1/events", json=event)
            self.assertEqual(response.status_code, 202)
        self.assertEqual(self.client.get("/api/v1/cases").json()["cases"][0]["risk_level"], "MEDIUM")

        changed = store.refresh_cases(now=now + timedelta(minutes=11))
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["risk_level"], "HIGH")

    def test_dashboard_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Order Rescue", response.text)


if __name__ == "__main__":
    unittest.main()
