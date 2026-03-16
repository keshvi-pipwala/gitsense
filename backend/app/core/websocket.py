import asyncio
import json
from typing import Dict, List
from fastapi import WebSocket
from datetime import datetime, timezone
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_event(self, event_type: str, data: dict, status: str = "info"):
        await self.broadcast({
            "type": "event",
            "event_type": event_type,
            "status": status,
            "data": data,
        })

    async def broadcast_agent_step(self, pr_number: int, step: str, detail: str, status: str = "processing"):
        await self.broadcast({
            "type": "agent_step",
            "pr_number": pr_number,
            "step": step,
            "detail": detail,
            "status": status,
        })


manager = ConnectionManager()
