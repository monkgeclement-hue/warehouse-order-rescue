from datetime import datetime, timedelta, timezone
from uuid import uuid4


def build_order_rescue_scenario(order_id: str | None = None) -> list[dict]:
    """Create synthetic events with fresh IDs and timestamps for one order."""
    now = datetime.now(timezone.utc)
    order_id = order_id or f"ORD-DEMO-{now.strftime('%H%M%S')}-{uuid4().hex[:4]}"
    events = []

    def add(event_type: str, payload: dict) -> None:
        events.append({
            "event_id": str(uuid4()),
            "schema_version": "1.0",
            "event_type": event_type,
            "occurred_at": now + timedelta(milliseconds=100 * len(events)),
            "warehouse_id": "WH-DEMO",
            "order_id": order_id,
            "source": "simulator",
            "payload": payload,
        })

    add("order.released", {
        "carrier_cutoff_at": (now + timedelta(minutes=20)).isoformat(),
        "expected_line_count": 5,
    })
    for number in range(1, 5):
        add("order.line_picked", {"sku": f"SKU-{number:03d}", "quantity": 1})
    add("order.line_short", {
        "sku": "SKU-005",
        "requested_qty": 1,
        "picked_qty": 0,
        "reserve_qty": 12,
        "reserve_location": "RESERVE-A",
    })
    return events
