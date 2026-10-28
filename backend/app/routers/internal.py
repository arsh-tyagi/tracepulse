from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from backend.app.database import get_db
from backend.app.models.check_run import CheckRun
from backend.app.schemas.check_run import BatchIngestRequest
from backend.app.config import settings
from backend.app.routers.sse import broadcast_sse_event
from backend.app.services.alert_service import AlertService

router = APIRouter(prefix="/internal", tags=["Internal Probe Ingestion"])

@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def batch_ingest_probe_runs(
    payload: BatchIngestRequest,
    db: AsyncSession = Depends(get_db),
    x_probe_key: Optional[str] = Header(None)
):
    """
    High-throughput internal endpoint called by the C++ Probe Daemon or Python Poller.
    Accepts batches of up to 1000 probe runs, batch-inserts into database,
    and dispatches live notifications to SSE and Alert Evaluators.
    """
    if settings.INTERNAL_INGEST_KEY and x_probe_key and x_probe_key != settings.INTERNAL_INGEST_KEY:
        raise HTTPException(status_code=403, detail="Invalid probe ingestion key")

    records = []
    for item in payload.checks:
        record = CheckRun(
            monitor_id=item.monitor_id,
            status_code=item.status_code,
            is_success=item.is_success,
            dns_lookup_us=item.dns_lookup_us,
            tcp_connect_us=item.tcp_connect_us,
            tls_handshake_us=item.tls_handshake_us,
            ttfb_us=item.ttfb_us,
            total_duration_us=item.total_duration_us,
            response_bytes=item.response_bytes,
            error_message=item.error_message,
            checked_at=item.checked_at or datetime.now(timezone.utc)
        )
        records.append(record)

    db.add_all(records)
    await db.commit()

    # Broadcast event for live SSE streaming & evaluate alert rules
    for item in payload.checks:
        item_dict = item.model_dump()
        broadcast_sse_event("probe_result", item_dict)
        try:
            await AlertService.evaluate_check_run(db, item_dict)
        except Exception:
            pass

    return {
        "status": "success",
        "ingested_count": len(records),
        "received_at": datetime.now(timezone.utc).isoformat()
    }
