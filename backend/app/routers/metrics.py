from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from backend.app.database import get_db
from backend.app.services.analytics import AnalyticsService
from backend.app.models.monitor import Monitor

router = APIRouter(prefix="/monitors", tags=["Metrics & SLA Analytics"])

@router.get("/{monitor_id}/metrics")
async def get_monitor_metrics(
    monitor_id: int,
    limit: int = Query(60, ge=5, le=500),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the latest time-series data points with microsecond latency decomposition for charting.
    """
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    timeseries = await AnalyticsService.get_timeseries_breakdown(db, monitor_id, limit=limit)
    return {
        "monitor_id": monitor_id,
        "name": monitor.name,
        "count": len(timeseries),
        "data": timeseries
    }

@router.get("/{monitor_id}/sla")
async def get_monitor_sla(
    monitor_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns rolling SLA compliance percentages for 24h, 7d, and 30d windows.
    """
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    sla_data = await AnalyticsService.get_monitor_sla(db, monitor_id)
    return {
        "monitor_id": monitor_id,
        "name": monitor.name,
        "sla": sla_data
    }

@router.get("/{monitor_id}/percentiles")
async def get_monitor_percentiles(
    monitor_id: int,
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns latency percentiles (P50, P90, P95, P99) and average TTFB over the specified window.
    """
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    percentiles = await AnalyticsService.get_latency_percentiles(db, monitor_id, hours=hours)
    return {
        "monitor_id": monitor_id,
        "window_hours": hours,
        "percentiles": percentiles
    }
