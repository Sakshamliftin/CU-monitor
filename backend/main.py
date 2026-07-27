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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
def get_history():
    return {
        "history": db_manager.get_status_history(limit=200),
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
