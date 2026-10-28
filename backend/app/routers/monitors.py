from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, case
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from backend.app.database import get_db
from backend.app.models.monitor import Monitor
from backend.app.models.check_run import CheckRun
from backend.app.models.alert import AlertIncident
from backend.app.schemas.monitor import MonitorCreate, MonitorUpdate, MonitorResponse
from backend.app.schemas.check_run import CheckRunResponse
from backend.app.services.probe_service import execute_probe_sync

router = APIRouter(prefix="/monitors", tags=["Monitors"])

@router.get("", response_model=List[MonitorResponse])
async def list_monitors(db: AsyncSession = Depends(get_db)):
    """
    List all configured synthetic monitors with their latest status, latency, and 24h SLA.
    """
    result = await db.execute(select(Monitor).order_by(Monitor.id.asc()))
    monitors = result.scalars().all()

    response_list = []
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    for m in monitors:
        # Get latest check run
        latest_run_q = await db.execute(
            select(CheckRun)
            .where(CheckRun.monitor_id == m.id)
            .order_by(CheckRun.checked_at.desc())
            .limit(1)
        )
        latest_run = latest_run_q.scalar_one_or_none()

        # Calculate 24h SLA
        sla_q = await db.execute(
            select(
                func.count(CheckRun.id).label("total"),
                func.sum(case((CheckRun.is_success == True, 1), else_=0)).label("successful")
            ).where(
                and_(
                    CheckRun.monitor_id == m.id,
                    CheckRun.checked_at >= twenty_four_hours_ago
                )
            )
        )
        sla_row = sla_q.first()
        total_checks = sla_row[0] if sla_row and sla_row[0] else 0
        successful_checks = sla_row[1] if sla_row and sla_row[1] else 0
        
        uptime_pct = round((successful_checks / total_checks * 100.0), 2) if total_checks > 0 else 100.0

        # Open incidents count
        incidents_q = await db.execute(
            select(func.count(AlertIncident.id))
            .where(and_(AlertIncident.monitor_id == m.id, AlertIncident.status == "OPEN"))
        )
        open_incidents = incidents_q.scalar() or 0

        item = MonitorResponse(
            id=m.id,
            name=m.name,
            target_url=m.target_url,
            http_method=m.http_method,
            headers_json=m.headers_json,
            body_payload=m.body_payload,
            check_interval_sec=m.check_interval_sec,
            timeout_ms=m.timeout_ms,
            expected_status=m.expected_status,
            is_active=m.is_active,
            created_at=m.created_at,
            updated_at=m.updated_at,
            latest_status_code=latest_run.status_code if latest_run else None,
            latest_latency_ms=round(latest_run.total_duration_us / 1000.0, 2) if latest_run else None,
            uptime_24h_percent=uptime_pct,
            active_incidents_count=open_incidents
        )
        response_list.append(item)

    return response_list

@router.get("/active/targets")
async def get_active_targets(db: AsyncSession = Depends(get_db)):
    """
    Lightweight target-list endpoint for the C++ / Python probe daemon to fetch active targets.
    """
    result = await db.execute(
        select(Monitor).where(Monitor.is_active == True)
    )
    monitors = result.scalars().all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "url": m.target_url,
            "method": m.http_method,
            "headers_json": m.headers_json,
            "body": m.body_payload,
            "interval_sec": m.check_interval_sec,
            "timeout_ms": m.timeout_ms,
            "expected_status": m.expected_status
        }
        for m in monitors
    ]

@router.post("", response_model=MonitorResponse, status_code=status.HTTP_201_CREATED)
async def create_monitor(payload: MonitorCreate, db: AsyncSession = Depends(get_db)):
    monitor = Monitor(
        name=payload.name,
        target_url=payload.target_url,
        http_method=payload.http_method,
        headers_json=payload.headers_json,
        body_payload=payload.body_payload,
        check_interval_sec=payload.check_interval_sec,
        timeout_ms=payload.timeout_ms,
        expected_status=payload.expected_status,
        is_active=payload.is_active
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)

    return MonitorResponse(
        id=monitor.id,
        name=monitor.name,
        target_url=monitor.target_url,
        http_method=monitor.http_method,
        headers_json=monitor.headers_json,
        body_payload=monitor.body_payload,
        check_interval_sec=monitor.check_interval_sec,
        timeout_ms=monitor.timeout_ms,
        expected_status=monitor.expected_status,
        is_active=monitor.is_active,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
        uptime_24h_percent=100.0,
        active_incidents_count=0
    )

@router.get("/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(monitor_id: int, db: AsyncSession = Depends(get_db)):
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor with ID {monitor_id} not found")
    
    # Latest run
    latest_run_q = await db.execute(
        select(CheckRun).where(CheckRun.monitor_id == monitor_id).order_by(CheckRun.checked_at.desc()).limit(1)
    )
    latest_run = latest_run_q.scalar_one_or_none()

    return MonitorResponse(
        id=monitor.id,
        name=monitor.name,
        target_url=monitor.target_url,
        http_method=monitor.http_method,
        headers_json=monitor.headers_json,
        body_payload=monitor.body_payload,
        check_interval_sec=monitor.check_interval_sec,
        timeout_ms=monitor.timeout_ms,
        expected_status=monitor.expected_status,
        is_active=monitor.is_active,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
        latest_status_code=latest_run.status_code if latest_run else None,
        latest_latency_ms=round(latest_run.total_duration_us / 1000.0, 2) if latest_run else None,
        uptime_24h_percent=100.0
    )

@router.put("/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(monitor_id: int, payload: MonitorUpdate, db: AsyncSession = Depends(get_db)):
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor with ID {monitor_id} not found")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(monitor, k, v)

    await db.commit()
    await db.refresh(monitor)
    return monitor

@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(monitor_id: int, db: AsyncSession = Depends(get_db)):
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor with ID {monitor_id} not found")
    await db.delete(monitor)
    await db.commit()
    return None

@router.post("/{monitor_id}/test", response_model=CheckRunResponse)
async def test_monitor_now(monitor_id: int, db: AsyncSession = Depends(get_db)):
    """
    Synchronously triggers an on-demand probe for this monitor,
    records the microsecond metrics into check_runs, and returns the result.
    """
    monitor = await db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor with ID {monitor_id} not found")

    result = execute_probe_sync(
        target_url=monitor.target_url,
        method=monitor.http_method,
        headers_json=monitor.headers_json,
        body_payload=monitor.body_payload,
        timeout_ms=monitor.timeout_ms,
        expected_status=monitor.expected_status
    )

    check_record = CheckRun(
        monitor_id=monitor.id,
        status_code=result.status_code,
        is_success=result.is_success,
        dns_lookup_us=result.dns_lookup_us,
        tcp_connect_us=result.tcp_connect_us,
        tls_handshake_us=result.tls_handshake_us,
        ttfb_us=result.ttfb_us,
        total_duration_us=result.total_duration_us,
        response_bytes=result.response_bytes,
        error_message=result.error_message
    )
    db.add(check_record)
    await db.commit()
    await db.refresh(check_record)

    return check_record
