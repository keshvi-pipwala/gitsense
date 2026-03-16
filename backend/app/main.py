import asyncio
import json
import redis.asyncio as aioredis
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.websocket import manager
from app.api.webhook import router as webhook_router
from app.api.routes import router as api_router

setup_logging()
logger = get_logger(__name__)

# Redis subscriber for agent step broadcasts from Celery workers
_redis_subscriber_task = None


async def redis_subscriber():
    """Subscribe to Redis pub/sub and broadcast agent steps to WebSocket clients."""
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe("agent_steps")
        logger.info("Redis pub/sub subscriber started")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await manager.broadcast({
                        "type": "agent_step",
                        **data,
                    })
                except Exception as e:
                    logger.warning(f"Error broadcasting agent step: {e}")
    except Exception as e:
        logger.error(f"Redis subscriber error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_subscriber_task
    # Create DB tables if they don't exist (for dev convenience)
    try:
        from app.db.session import engine
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"Could not create tables: {e}")

    _redis_subscriber_task = asyncio.create_task(redis_subscriber())
    logger.info(f"GitSense v{settings.APP_VERSION} started")
    yield
    if _redis_subscriber_task:
        _redis_subscriber_task.cancel()


app = FastAPI(
    title="GitSense API",
    description="Autonomous AI Agent for Codebase Intelligence",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router, tags=["Webhooks"])
app.include_router(api_router, prefix="/api", tags=["API"])


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await manager.send_personal_message(
            {"type": "connected", "message": "GitSense live stream connected"},
            websocket,
        )
        while True:
            # Keep connection alive — client sends pings
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/")
def root():
    return {
        "name": "GitSense",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
