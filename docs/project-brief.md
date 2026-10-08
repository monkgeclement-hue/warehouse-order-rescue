# Warehouse Order Rescue — Project Brief

## Project summary

Warehouse Order Rescue is a real-time decision-support system for warehouse supervisors. It watches order and picking events, identifies outbound orders that may miss their carrier cutoff, explains the evidence behind each alert, and suggests a next step for a human supervisor to review.

The prototype uses synthetic warehouse events because the team does not yet have a warehouse partner or live WMS data. It demonstrates and tests the system workflow; it does not claim that the current rules have been validated against a real warehouse.

## Problem statement

An outbound order can fall behind when one or more lines are short-picked, stock needs to be replenished, or packing is delayed. The information needed to recognize that risk may arrive as separate warehouse events. If a supervisor only discovers the issue close to the carrier cutoff, there may be little time to recover the order.

The problem this project addresses is how to bring those events together quickly enough to identify at-risk orders, show why each order is at risk, and help a supervisor decide what to investigate or do next. The system is intended to reduce late discovery of preventable shipping exceptions; it does not replace the WMS or make warehouse decisions on its own.

## Main goal

Build a near-real-time warehouse exception investigator that helps supervisors rescue at-risk outbound orders before their carrier cutoff by presenting timely alerts, traceable evidence, and human-reviewed recommendations.

## Objectives

1. Define a common, versioned event format that a simulator and future WMS adapters can both use.
2. Validate incoming events, reject malformed data, deduplicate retries, and preserve an event history.
3. Reconstruct an order’s current state and evaluate its picking and carrier-cutoff risk using understandable rules.
4. Open an exception case with its risk level, supporting evidence, status, and suggested next step.
5. Deliver case updates to a supervisor dashboard in real time and make the underlying order event history available for investigation.
6. Use synthetic scenarios to develop and test the complete flow before real partner data becomes available.

## How the system works

```text
Simulator (now) or read-only WMS adapter (later)
        → versioned warehouse events
        → validate, deduplicate, and append to the event log
        → rebuild order state and evaluate cutoff risk
        → create or update an exception case with evidence
        → send live updates to the supervisor dashboard
        → supervisor investigates and chooses the response
```

For the first scenario, an order has five expected lines. Four are picked, the fifth is short-picked, reserve stock is available, and the carrier cutoff is approaching. The system opens a high-risk case and recommends that a supervisor release replenishment and monitor the order. The system does not execute that action.

When new events arrive, the case is recalculated. The service also rechecks deadlines every 30 seconds so risk can rise as a cutoff approaches, even if no new warehouse event arrives. The API exposes the case and a time-ordered event history; the dashboard receives case changes over Server-Sent Events (SSE).

The shared `WarehouseEvent` v1 contract includes `event_id`, `schema_version`, `event_type`, timezone-aware `occurred_at`, `warehouse_id`, `order_id`, `source`, and an event-specific `payload`. Current event types are order release, line picked, line short, replenishment started, order packed, and order dispatched.

## Module ownership

| Owner and branch | Modules and responsibilities |
|---|---|
| **Lephallo1 — `team/lephallo1`** | Event contract and integration coordination; synthetic event simulator; event validation and ingestion API; append-only event store and deduplication; read-only order event-history API; integration and run documentation. |
| **Rexlesenyeho — `team/rexlesenyeho`** | Risk and investigation rules; case lifecycle and evidence; supervisor dashboard and live case presentation; focused risk and interface tests. |
| **Shared** | Agree on event and API contract changes before implementation; test the integrated workflow; review pull requests into `main`. |

The current API and dashboard provide a working starting point for both branches. Ownership means maintaining and extending those areas, not rebuilding them from scratch.

## Scope

### Current prototype and first milestone

- Synthetic local data for the initial order-rescue scenario.
- FastAPI service that validates events, accepts them once, stores their history in SQLite, evaluates cases, and exposes a read-only event timeline.
- Deterministic rules with explicit evidence and risk thresholds; the current thresholds are demonstration values, not warehouse-approved policy.
- HTML, CSS, and JavaScript supervisor dashboard with live case updates over SSE.
- Human review of recommendations; no commands are sent to warehouse equipment or a WMS.

### Not in the current scope

- A live connection to a warehouse partner, WMS, carrier, or production inventory system.
- Automatic replenishment, order substitution, rerouting, or other operational actions.
- Production-grade multi-warehouse identity, access control, scaling, and monitoring.
- Machine-learning risk prediction. Explainable rules are sufficient for the first milestone.

## Technologies

| Area | Current choice | Why it is used now |
|---|---|---|
| API and service | Python, FastAPI, Pydantic | Fast to build and validate typed event APIs. |
| Prototype database | SQLite | Keeps local setup simple while preserving an event log. |
| Event interface | JSON Schema and a versioned JSON event contract | Gives both contributors and future adapters a shared boundary. |
| Supervisor dashboard | HTML, CSS, vanilla JavaScript | No frontend build service is needed for the first prototype. |
| Live updates | Server-Sent Events (SSE) | Sends case updates from the API to the dashboard. |
| Collaboration | Git and GitHub branches plus pull requests | Keeps the two work streams separate and integrates them through reviewed changes. |

## Future enhancements

1. **Partner integration:** map a partner’s read-only WMS events and field meanings to the shared contract; validate the rules against sanitized real examples.
2. **Richer simulations:** add normal, late, no-reserve, replenishment-in-progress, recovered, and resolved order scenarios.
3. **Investigation workflow:** improve case ownership, acknowledgements, resolution reasons, event timeline display, and audit history.
4. **Shared deployment:** move from local SQLite to PostgreSQL and use a durable worker or queue for event processing, retries, and replay.
5. **Operational controls:** add authentication, warehouse-level access, monitoring, configurable cutoffs, and alerting.
6. **Approved actions:** only after partner validation, offer allowlisted actions that a supervisor approves and that the system verifies through follow-up events.
7. **Optional language assistance:** use an AI model only to phrase explanations from stored evidence; rules remain responsible for risk decisions, and the model cannot execute actions.

## Team workflow

`main` is the stable integration branch. Lephallo1 works on `team/lephallo1`; Rexlesenyeho works on `team/rexlesenyeho`. Keep changes on the assigned branch, run `python -m unittest discover -s tests -v`, push the branch, and open a pull request into `main`. Coordinate before changing the shared event contract or API response shape.

The first integration milestone is complete when the simulator creates an explainable at-risk order case, duplicate events do not create duplicate records, deadline rechecks can update a case, the dashboard receives case updates, and the event history can be inspected through the API.
