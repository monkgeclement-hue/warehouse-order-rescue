# Warehouse Order Rescue

A real-time warehouse exception investigator prototype. It watches warehouse events, identifies an outbound order at risk of missing its carrier cutoff, shows the evidence behind that alert, and suggests a supervisor-reviewed next step.

## Current prototype

- A versioned event contract shared by the simulator, API, and future WMS adapters.
- A local FastAPI service that validates and stores events in an append-only SQLite event log.
- A deterministic, explainable risk rule for a short-picked order with reserve stock and no replenishment task.
- A 30-second deadline re-check so risk can rise as a carrier cutoff approaches, even if no new warehouse event arrives.
- A small dashboard that receives case updates over Server-Sent Events (SSE).
- A repeatable demo scenario; every generated record is synthetic and marked as coming from `simulator`.

This proves the flow with simulated data. It does not prove that a specific warehouse's cutoffs, inventory semantics, or recommended actions are correct. Those need to be confirmed with a warehouse partner before operational use. The prototype does not connect to or write to any WMS.

## Run locally on Windows

From this folder, create and activate a virtual environment, then install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Start the application:

```powershell
uvicorn warehouse_rescue.main:app --app-dir backend --reload
```

Open <http://127.0.0.1:8000>, then choose **Run demo scenario**. The case should appear as the simulated order events arrive. API documentation is at <http://127.0.0.1:8000/docs>.

Run the rule tests in another terminal with the virtual environment active:

```powershell
python -m unittest discover -s tests -v
```

The SQLite database is created at `backend/warehouse_rescue.db`. Remove that file to reset the local demo history.

## Team workflow

Keep one shared repository and agree on the event contract before parallel work. The initial branch layout is:

- `main` — stable, integrated version; merge reviewed pull requests here.
- `team/lephallo1` — your branch for the event contract, simulator, and ingestion/store integration.
- `team/rexlesenyeho` — the collaborator's branch for risk/case lifecycle and the supervisor dashboard.

Invite `Rexlesenyeho` to the GitHub repository with write access. Each person should push only to their own branch and open pull requests to `main`; avoid direct pushes to `main`. Keep API and event contract changes explicit so work done on separate machines can be integrated cleanly. Coordinate contract changes together before either branch depends on them.

## Next steps

1. Agree as a team on the first scenario and event fields in `contracts/warehouse-event.v1.schema.json`.
2. Run the same simulator locally and confirm all three machines show the same case.
3. Add replay, idempotency, and case lifecycle coverage.
4. Replace SQLite with PostgreSQL and add a background re-evaluation worker when the team is ready to deploy the prototype collaboratively.
5. Build a read-only adapter for a partner's WMS only after agreeing on field mappings, access, and operational rules.

See [`docs/architecture.md`](docs/architecture.md) and [`docs/team-integration.md`](docs/team-integration.md).
