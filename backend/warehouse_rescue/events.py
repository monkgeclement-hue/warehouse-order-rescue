from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EventType = Literal[
    "order.released",
    "order.line_picked",
    "order.line_short",
    "replenishment.started",
    "order.packed",
    "order.dispatched",
]


class WarehouseEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    schema_version: Literal["1.0"]
    event_type: EventType
    occurred_at: datetime
    warehouse_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    payload: dict[str, Any]

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_event_payload(self) -> "WarehouseEvent":
        required = {
            "order.released": ("carrier_cutoff_at", "expected_line_count"),
            "order.line_picked": ("sku", "quantity"),
            "order.line_short": ("sku", "requested_qty", "picked_qty", "reserve_qty"),
            "replenishment.started": ("sku",),
            "order.packed": (),
            "order.dispatched": (),
        }[self.event_type]
        missing = [key for key in required if key not in self.payload]
        if missing:
            raise ValueError(f"payload is missing required field(s): {', '.join(missing)}")

        if self.event_type == "order.released":
            lines = self.payload["expected_line_count"]
            if not isinstance(lines, int) or isinstance(lines, bool) or lines < 1:
                raise ValueError("expected_line_count must be a positive integer")
            cutoff = self.payload["carrier_cutoff_at"]
            if not isinstance(cutoff, str):
                raise ValueError("carrier_cutoff_at must be an ISO 8601 string")
            try:
                parsed_cutoff = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("carrier_cutoff_at must be an ISO 8601 string") from exc
            if parsed_cutoff.tzinfo is None or parsed_cutoff.utcoffset() is None:
                raise ValueError("carrier_cutoff_at must include a timezone")

        if self.event_type in {"order.line_picked", "order.line_short", "replenishment.started"}:
            sku = self.payload["sku"]
            if not isinstance(sku, str) or not sku.strip():
                raise ValueError("sku must be a non-empty string")

        if self.event_type == "order.line_picked":
            quantity = self.payload["quantity"]
            if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or quantity <= 0:
                raise ValueError("quantity must be a positive number")

        if self.event_type == "order.line_short":
            requested = self.payload["requested_qty"]
            picked = self.payload["picked_qty"]
            reserve = self.payload["reserve_qty"]
            quantities = (requested, picked, reserve)
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in quantities):
                raise ValueError("short-pick quantities must be numbers")
            if requested <= 0 or picked < 0 or reserve < 0 or picked >= requested:
                raise ValueError("short-pick quantities are inconsistent")

        return self
