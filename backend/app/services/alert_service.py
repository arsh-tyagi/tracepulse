import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from backend.app.database import get_db
from backend.app.models.alert import AlertRule, AlertIncident
from backend.app.models.monitor import Monitor
from backend.app.models.check_run import CheckRun

logger = logging.getLogger("tracepulse.alert_service")

class AlertService:
    @staticmethod
    async def dispatch_webhook(webhook_url: str, title: str, details: Dict[str, Any], is_resolution: bool = False):
        """
        Dispatches non-blocking webhook payload to Slack, Discord, or generic receivers.
        """
        emoji = "✅" if is_resolution else "🚨"
        color = 65280 if is_resolution else 16711680 # Green vs Red

        # Standard multi-format payload
        payload = {
            "text": f"{emoji} *TracePulse Alert:* {title}\n```{details}```",
            "content": f"{emoji} **TracePulse Alert:** {title}",
            "embeds": [
                {
                    "title": title,
                    "color": color,
                    "fields": [
                        {"name": k, "value": str(v), "inline": True}
                        for k, v in details.items()
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ],
            "tracepulse_meta": {
                "event": "resolution" if is_resolution else "incident",
                **details
            }
        }

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post(webhook_url, json=payload)
                logger.info(f"Dispatched webhook to {webhook_url[:30]}... Response: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed to dispatch alert webhook to {webhook_url[:30]}... Error: {e}")

    @staticmethod
    async def evaluate_check_run(db: AsyncSession, check_run: Dict[str, Any]):
        """
        Evaluates a single check run against configured alert rules for that monitor.
        """
        monitor_id = check_run.get("monitor_id")
        if not monitor_id:
            return

        # Fetch active rules for this monitor
        rules_q = await db.execute(
            select(AlertRule).where(
                and_(AlertRule.monitor_id == monitor_id, AlertRule.is_active == True)
            )
        )
        rules = rules_q.scalars().all()
        if not rules:
            return

        # Check if there is currently an OPEN incident
        incident_q = await db.execute(
            select(AlertIncident).where(
                and_(AlertIncident.monitor_id == monitor_id, AlertIncident.status == "OPEN")
            )
        )
        open_incident = incident_q.scalar_one_or_none()

        is_success = check_run.get("is_success", False)
        total_latency_ms = check_run.get("total_duration_us", 0) / 1000.0

        for rule in rules:
            breach_detected = False
            breach_reason = ""

            if rule.rule_type == "CONSECUTIVE_FAILURES":
                if not is_success:
                    # Query recent runs to count consecutive failures
                    runs_q = await db.execute(
                        select(CheckRun.is_success)
                        .where(CheckRun.monitor_id == monitor_id)
                        .order_by(CheckRun.checked_at.desc())
                        .limit(rule.consecutive_count)
                    )
                    recent_successes = runs_q.scalars().all()
                    if len(recent_successes) >= rule.consecutive_count and all(not s for s in recent_successes):
                        breach_detected = True
                        breach_reason = f"{rule.consecutive_count} consecutive failed checks detected"
                elif open_incident:
                    # Target has recovered
                    open_incident.status = "RESOLVED"
                    open_incident.resolved_at = datetime.now(timezone.utc)
                    await db.commit()

                    asyncio.create_task(AlertService.dispatch_webhook(
                        webhook_url=rule.webhook_url,
                        title=f"Incident Resolved for Monitor #{monitor_id}",
                        details={"monitor_id": monitor_id, "status": "RESOLVED", "reason": "Endpoint responding normally"},
                        is_resolution=True
                    ))

            elif rule.rule_type == "LATENCY_THRESHOLD":
                if total_latency_ms > rule.threshold_value:
                    breach_detected = True
                    breach_reason = f"Latency {total_latency_ms:.1f}ms exceeded threshold {rule.threshold_value}ms"

            elif rule.rule_type == "STATUS_CODE_MISMATCH":
                status_code = check_run.get("status_code", 0)
                if status_code != int(rule.threshold_value):
                    breach_detected = True
                    breach_reason = f"HTTP Status {status_code} does not match expected {int(rule.threshold_value)}"

            # If breach detected and no incident already open, create incident & fire webhook
            if breach_detected and not open_incident:
                new_incident = AlertIncident(
                    monitor_id=monitor_id,
                    alert_rule_id=rule.id,
                    status="OPEN",
                    triggered_at=datetime.now(timezone.utc),
                    trigger_reason=breach_reason
                )
                db.add(new_incident)
                await db.commit()

                asyncio.create_task(AlertService.dispatch_webhook(
                    webhook_url=rule.webhook_url,
                    title=f"Breach Detected on Monitor #{monitor_id}",
                    details={
                        "monitor_id": monitor_id,
                        "rule_type": rule.rule_type,
                        "reason": breach_reason,
                        "latency_ms": round(total_latency_ms, 2),
                        "status_code": check_run.get("status_code")
                    },
                    is_resolution=False
                ))
