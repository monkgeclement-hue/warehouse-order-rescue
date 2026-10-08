# Three-person integration guide

## Shared agreement

All modules exchange the `WarehouseEvent` contract in `contracts/warehouse-event.v1.schema.json`. Do not rename fields or event types independently. Propose a contract change in a pull request and update the simulator, API validation, and examples together.

A warehouse event contains a unique `event_id`, `schema_version`, `event_type`, UTC `occurred_at`, `warehouse_id`, `order_id`, `source`, and event-specific `payload`. The API returns whether it accepted or deduplicated the event and may include the updated case.

The first payload shapes are: `order.released` has `carrier_cutoff_at` (timezone-aware ISO 8601) and positive integer `expected_line_count`; `order.line_picked` has `sku` and positive `quantity`; `order.line_short` has `sku`, `requested_qty`, `picked_qty`, and `reserve_qty` (with optional `reserve_location`); `replenishment.started` has `sku`; `order.packed` and `order.dispatched` need no payload fields yet.

## Parallel ownership

- **Person 1 — coordinator and integration:** contract, simulator, ingestion boundary, local run instructions, integration review.
- **Person 2 — investigation engine:** event-to-order state, risk rules, evidence, case status, tests.
- **Person 3 — supervisor experience:** dashboard, accessibility, case evidence display, SSE connection and connection state.

This is an initial split, not a reason to work in isolation. Agree on a small interface before each person starts; integrate through pull requests into the same repository.

## Local collaboration

1. Each teammate clones the same repository and uses a local Python virtual environment.
2. Use branches such as `codex/event-contract`, `codex/risk-rules`, and `codex/dashboard` (replace the prefix if the team agrees on another convention).
3. Keep pull requests focused and avoid editing another owner's module unless coordinating first.
4. Run `python -m unittest discover -s tests -v` and manually run the demo before merging.
5. Resolve schema changes with all three modules in mind; never rely on a private payload shape that is absent from the contract.

Before connecting a real partner, the team will need sample event payloads (with personal data removed), event delivery method, field definitions, cutoff rules, location/inventory meanings, and permission for read-only access. No partner credentials belong in this repository.
