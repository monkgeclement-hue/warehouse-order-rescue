# Two-person integration guide

## Shared agreement

All modules exchange the `WarehouseEvent` contract in `contracts/warehouse-event.v1.schema.json`. Do not rename fields or event types independently. Propose a contract change in a pull request and update the simulator, API validation, and examples together.

A warehouse event contains a unique `event_id`, `schema_version`, `event_type`, UTC `occurred_at`, `warehouse_id`, `order_id`, `source`, and event-specific `payload`. The API returns whether it accepted or deduplicated the event and may include the updated case.

The first payload shapes are: `order.released` has `carrier_cutoff_at` (timezone-aware ISO 8601) and positive integer `expected_line_count`; `order.line_picked` has `sku` and positive `quantity`; `order.line_short` has `sku`, `requested_qty`, `picked_qty`, and `reserve_qty` (with optional `reserve_location`); `replenishment.started` has `sku`; `order.packed` and `order.dispatched` need no payload fields yet.

## Parallel ownership

- **Lephallo1 — event pipeline:** contract, simulator, ingestion, event store, and integration coordination.
- **Rexlesenyeho — investigation experience:** risk rules, case lifecycle/evidence, dashboard, and focused tests.

Agree on API and contract changes together before either person starts dependent work. Each person owns a separate branch and integrates through pull requests into `main`.

## Branches and collaboration

The local starter branches are `main`, `team/lephallo1`, and `team/rexlesenyeho`. `main` is the shared integration branch; each teammate pushes to their own branch and opens pull requests into `main`.

After the GitHub repository is created and the branches are pushed:

1. Each teammate clones the same repository and uses a local Python virtual environment.
2. Check out the assigned remote branch, for example `git switch --track origin/team/rexlesenyeho`.
3. Keep pull requests focused and avoid editing another owner's module unless coordinating first.
4. Run `python -m unittest discover -s tests -v` and manually run the demo before merging.
5. Resolve schema changes with all three modules in mind; never rely on a private payload shape that is absent from the contract.

Before connecting a real partner, the team will need sample event payloads (with personal data removed), event delivery method, field definitions, cutoff rules, location/inventory meanings, and permission for read-only access. No partner credentials belong in this repository.
