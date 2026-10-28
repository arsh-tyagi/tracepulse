import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger("tracepulse.sse")

router = APIRouter(prefix="/events", tags=["Real-Time Streaming"])

# Set of active client queues
_connected_clients = set()

def broadcast_sse_event(event_type: str, payload: dict):
    """
    Pushes an SSE event to all connected web browser clients.
    """
    message = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
    for queue in list(_connected_clients):
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            pass
        except Exception:
            _connected_clients.discard(queue)

async def sse_event_generator(request: Request) -> AsyncGenerator[str, None]:
    client_queue = asyncio.Queue(maxsize=100)
    _connected_clients.add(client_queue)
    logger.info(f"New SSE client connected. Active connections: {len(_connected_clients)}")

    # Initial connection handshake
    yield "event: connected\ndata: {\"status\": \"streaming_active\"}\n\n"

    try:
        while True:
            # Disconnect detection
            if await request.is_disconnected():
                break

            try:
                # Wait for next event or send 15s keep-alive heartbeat
                message = await asyncio.wait_for(client_queue.get(), timeout=15.0)
                yield message
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        _connected_clients.discard(client_queue)
        logger.info(f"SSE client disconnected. Active connections: {len(_connected_clients)}")

@router.get("/stream")
async def stream_events(request: Request):
    """
    Server-Sent Events endpoint for real-time telemetry streaming into the dashboard.
    """
    return StreamingResponse(
        sse_event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
