from datetime import datetime, timezone
from typing import Any


TERMINAL_EVENTS = {"order.packed", "order.dispatched"}


def evaluate_order(
    order_id: str,
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    existing_case: bool = False,
) -> dict[str, Any] | None:
    """Build an explainable case from one order's normalized event history."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    ordered = sorted(events, key=lambda item: (item["occurred_at"], item["event_id"]))
    release = next((event for event in ordered if event["event_type"] == "order.released"), None)
    if release is None:
        return None

    payload = release["payload"]
    cutoff_text = payload.get("carrier_cutoff_at")
    expected_lines = payload.get("expected_line_count")
    if not isinstance(cutoff_text, str) or not isinstance(expected_lines, int) or expected_lines < 1:
        return None

    try:
        cutoff = datetime.fromisoformat(cutoff_text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        return None
    cutoff = cutoff.astimezone(timezone.utc)

    shorts: dict[str, dict[str, Any]] = {}
    picked_lines: set[str] = set()
    replenishment_started: set[str] = set()
    terminal = False
    for event in ordered:
        kind = event["event_type"]
        detail = event["payload"]
        sku = detail.get("sku")
        if kind == "order.line_picked" and isinstance(sku, str):
            picked_lines.add(sku)
            shorts.pop(sku, None)
        elif kind == "order.line_short" and isinstance(sku, str):
            shorts[sku] = detail
        elif kind == "replenishment.started" and isinstance(sku, str):
            replenishment_started.add(sku)
        elif kind in TERMINAL_EVENTS:
            terminal = True

    if terminal and existing_case:
        return {
            "case_id": f"EXC-{order_id}",
            "order_id": order_id,
            "warehouse_id": release["warehouse_id"],
            "status": "RESOLVED",
            "risk_level": "LOW",
            "summary": "The order has been packed or dispatched; the exception is resolved.",
            "recommendation": "No further action. Keep the event history for the audit trail.",
            "evidence": {"expected_line_count": expected_lines, "picked_line_count": len(picked_lines), "carrier_cutoff_at": cutoff.isoformat()},
            "source": release["source"],
        }
    if terminal:
        return None
    if not shorts:
        return None

    remaining = (cutoff - now.astimezone(timezone.utc)).total_seconds()
    if remaining <= 30 * 60:
        risk_level = "HIGH"
    elif remaining <= 2 * 60 * 60:
        risk_level = "MEDIUM"
    else:
        return None

    short_details = []
    waiting_for_replenishment = []
    for sku, detail in shorts.items():
        reserve_qty = detail.get("reserve_qty", 0)
        reserve_qty = reserve_qty if isinstance(reserve_qty, (int, float)) else 0
        short_details.append({
            "sku": sku,
            "requested_qty": detail.get("requested_qty"),
            "picked_qty": detail.get("picked_qty"),
            "reserve_qty": reserve_qty,
            "reserve_location": detail.get("reserve_location"),
        })
        if reserve_qty > 0 and sku not in replenishment_started:
            waiting_for_replenishment.append(sku)

    if waiting_for_replenishment:
        recommendation = (
            "Ask a floor supervisor to release replenishment from reserve stock for "
            + ", ".join(waiting_for_replenishment)
            + ", then monitor until the missing line is picked."
        )
    elif replenishment_started:
        recommendation = "Monitor the replenishment and confirm the missing line is picked before the carrier cutoff."
    else:
        recommendation = "Ask a supervisor to check an alternate location or an approved substitute for the short-picked line."

    status = "IN_PROGRESS" if replenishment_started else "OPEN"
    return {
        "case_id": f"EXC-{order_id}",
        "order_id": order_id,
        "warehouse_id": release["warehouse_id"],
        "status": status,
        "risk_level": risk_level,
        "summary": f"{len(shorts)} line(s) are short-picked with the carrier cutoff approaching.",
        "recommendation": recommendation,
        "evidence": {
            "expected_line_count": expected_lines,
            "picked_line_count": len(picked_lines),
            "short_lines": short_details,
            "carrier_cutoff_at": cutoff.isoformat(),
            "minutes_until_cutoff": max(0, round(remaining / 60)),
            "replenishment_started_for": sorted(replenishment_started),
        },
        "source": release["source"],
    }
