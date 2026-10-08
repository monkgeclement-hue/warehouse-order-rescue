import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .events import WarehouseEvent
from .simulator import build_order_rescue_scenario

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() == "true"
logger = logging.getLogger(__name__)


class CaseUpdates:
    def __init__(self) -> None:
        self.queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.queues.discard(queue)

    async def publish(self, case: dict) -> None:
        message = {"type": "case.updated", "case": case}
        for queue in list(self.queues):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(message)


updates = CaseUpdates()


async def recheck_deadlines() -> None:
    while True:
        await asyncio.sleep(30)
        try:
            for case in store.refresh_cases():
                await updates.publish(case)
        except Exception:
            logger.exception("Deadline re-check failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.initialize()
    rechecker = asyncio.create_task(recheck_deadlines())
    try:
        yield
    finally:
        rechecker.cancel()
        try:
            await rechecker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Warehouse Order Rescue", version="0.1.0", lifespan=lifespan)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "demo_mode": DEMO_MODE}


@app.get("/api/v1/cases")
def cases() -> dict:
    return {"cases": store.list_cases()}


@app.post("/api/v1/events", status_code=202)
async def create_event(event: WarehouseEvent) -> dict:
    inserted, case = store.ingest(event.model_dump())
    if inserted and case is not None:
        await updates.publish(case)
    return {"accepted": inserted, "duplicate": not inserted, "case": case}


@app.get("/api/v1/stream/cases")
async def stream_cases() -> StreamingResponse:
    async def generate() -> AsyncIterator[str]:
        queue = updates.subscribe()
        try:
            snapshot = {"type": "snapshot", "cases": store.list_cases()}
            yield f"event: snapshot\ndata: {json.dumps(snapshot)}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"event: {message['type']}\ndata: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            updates.unsubscribe(queue)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/v1/demo/run")
async def run_demo() -> dict:
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Demo mode is disabled")
    accepted = 0
    latest_case = None
    for raw_event in build_order_rescue_scenario():
        event = WarehouseEvent.model_validate(raw_event)
        inserted, case = store.ingest(event.model_dump())
        accepted += int(inserted)
        if case is not None:
            latest_case = case
            if inserted:
                await updates.publish(case)
    return {"accepted_events": accepted, "case": latest_case}


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
