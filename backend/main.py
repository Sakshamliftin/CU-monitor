"""
main.py — FastAPI application entry point.
"""

# 
from __future__ import annotations

import asyncio
import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

# create server,enable react frontend

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

mimetypes.add_type("application/javascript", ".jsx")

# Import local classes
from config import load_settings
from database.db_manager import DBManager
from events.event_manager import EventManager
from monitoring.monitor_service import MonitorService
from scheduler.scheduler import Scheduler
from state.state_manager import StateManager
from websocket.ws_manager import WebSocketManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


class DiscoverCURequest(BaseModel):
    ip: str
    name: str | None = None

settings = load_settings()
db_manager = DBManager()
state_manager = StateManager()
event_manager = EventManager()
ws_manager = WebSocketManager()

monitor_service = MonitorService(
    settings=settings,
    state_manager=state_manager,
    event_manager=event_manager,
    ws_manager=ws_manager,
    db_manager=db_manager
)

scheduler = Scheduler(
    interval_sec=settings.poll_interval_sec,
    monitor=monitor_service,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_manager.set_event_loop(asyncio.get_running_loop())
    # monitoring begins here
    scheduler.start()
    logger.info("Application started — monitoring %d CUs", len(settings.cus))
    yield
    scheduler.stop()
    logger.info("Application shut down")

app = FastAPI(
    title="Airspan Lab Monitor",
    description="PoC — Real-time telecom lab monitoring dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/state")
def get_state():
    return {
        "nodes": [s.to_dict() for s in state_manager.get_all()],
    }

@app.get("/api/events")
def get_events():
    return {
        "events": [e.to_dict() for e in event_manager.get_recent_events()],
    }

@app.get("/api/history")
def get_history(rn_id: str | None = None):
    return {
        "history": db_manager.get_status_history(limit=200, rn_id=rn_id),
    }


@app.post("/api/cus/discover")
def discover_cu(payload: DiscoverCURequest):
    try:
        discovered = monitor_service.discover_and_add_cu(payload.ip, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("CU discovery failed for %s", payload.ip)
        raise HTTPException(
            status_code=502,
            detail=f"Unable to discover CU at {payload.ip}: {exc}",
        ) from exc

    monitor_service.poll_all()

    return {
        "message": f"Discovered {len(discovered.rns)} RN(s) for {discovered.name}",
        "cu": {
            "name": discovered.name,
            "ip": discovered.ip,
            "rn_count": len(discovered.rns),
        },
        "nodes": [s.to_dict() for s in state_manager.get_all()],
    }


@app.delete("/api/cus")
def delete_cu(payload: DiscoverCURequest):
    try:
        removed = monitor_service.remove_cu(payload.ip)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("CU delete failed for %s", payload.ip)
        raise HTTPException(
            status_code=502,
            detail=f"Unable to delete CU at {payload.ip}: {exc}",
        ) from exc

    monitor_service.poll_all()

    return {
        "message": f"Removed {removed.name}",
        "cu": {
            "name": removed.name,
            "ip": removed.ip,
            "rn_count": len(removed.rns),
        },
        "nodes": [s.to_dict() for s in state_manager.get_all()],
    }

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        initial = {
            "type": "state_update",
            "nodes": [s.to_dict() for s in state_manager.get_all()],
            "recent_events": [e.to_dict() for e in event_manager.get_recent_events(limit=50)],
        }
        await ws.send_json(initial)
    except Exception:
        logger.exception("Error sending initial state")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
_frontend_dist = _frontend_dir / "dist"

# Serve Vite dist folder
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
else:
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
