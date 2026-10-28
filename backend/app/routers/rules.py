from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List

from backend.app.database import get_db
from backend.app.models.alert import AlertRule, AlertIncident
from backend.app.models.monitor import Monitor
from backend.app.schemas.alert import AlertRuleCreate, AlertRuleResponse, AlertIncidentResponse

router = APIRouter(prefix="/alerts", tags=["Alerts & Incidents"])

@router.get("/rules", response_model=List[AlertRuleResponse])
async def list_alert_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertRule).order_by(AlertRule.id.desc()))
    return result.scalars().all()

@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(payload: AlertRuleCreate, db: AsyncSession = Depends(get_db)):
    # Validate monitor exists
    monitor = await db.get(Monitor, payload.monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor {payload.monitor_id} does not exist")

    rule = AlertRule(
        monitor_id=payload.monitor_id,
        rule_type=payload.rule_type,
        threshold_value=payload.threshold_value,
        consecutive_count=payload.consecutive_count,
        webhook_url=payload.webhook_url,
        is_active=payload.is_active
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    await db.delete(rule)
    await db.commit()
    return None

@router.get("/incidents", response_model=List[AlertIncidentResponse])
async def list_incidents(status_filter: str = "ALL", db: AsyncSession = Depends(get_db)):
    query = select(AlertIncident).order_by(AlertIncident.triggered_at.desc())
    if status_filter.upper() in ["OPEN", "RESOLVED"]:
        query = query.where(AlertIncident.status == status_filter.upper())
    result = await db.execute(query)
    return result.scalars().all()
