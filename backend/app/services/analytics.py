import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, case
from backend.app.models.check_run import CheckRun

class AnalyticsService:
    @staticmethod
    async def get_monitor_sla(db: AsyncSession, monitor_id: int) -> Dict[str, Any]:
        """
        Calculates rolling SLA uptime compliance for 24 hours, 7 days, and 30 days.
        """
        now = datetime.now(timezone.utc)
        windows = {
            "24h": now - timedelta(hours=24),
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
        }

        sla_results = {}
        for label, start_time in windows.items():
            query = select(
                func.count(CheckRun.id).label("total"),
                func.sum(case((CheckRun.is_success == True, 1), else_=0)).label("successful")
            ).where(
                and_(
                    CheckRun.monitor_id == monitor_id,
                    CheckRun.checked_at >= start_time
                )
            )
            result = await db.execute(query)
            row = result.first()
            total = row[0] if row and row[0] else 0
            successful = row[1] if row and row[1] else 0

            uptime_pct = round((successful / total * 100.0), 3) if total > 0 else 100.0
            sla_results[label] = {
                "uptime_percent": uptime_pct,
                "total_checks": total,
                "successful_checks": successful,
                "failed_checks": total - successful
            }

        return sla_results

    @staticmethod
    async def get_latency_percentiles(db: AsyncSession, monitor_id: int, hours: int = 24) -> Dict[str, Any]:
        """
        Calculates P50, P90, P95, P99 latencies in milliseconds over the requested window.
        Uses in-memory percentile calculation over indexed records for cross-database consistency.
        """
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = select(
            CheckRun.total_duration_us,
            CheckRun.ttfb_us,
            CheckRun.dns_lookup_us,
            CheckRun.tcp_connect_us,
            CheckRun.tls_handshake_us
        ).where(
            and_(
                CheckRun.monitor_id == monitor_id,
                CheckRun.checked_at >= start_time,
                CheckRun.is_success == True
            )
        ).order_by(CheckRun.total_duration_us.asc())

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return {
                "p50_ms": 0.0,
                "p90_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "avg_ttfb_ms": 0.0,
                "sample_count": 0
            }

        durations_ms = [r[0] / 1000.0 for r in rows]
        ttfbs_ms = [r[1] / 1000.0 for r in rows]

        def get_p(data: List[float], p: float) -> float:
            idx = int(math.ceil((p / 100.0) * len(data))) - 1
            return round(data[max(0, min(idx, len(data) - 1))], 2)

        return {
            "p50_ms": get_p(durations_ms, 50),
            "p90_ms": get_p(durations_ms, 90),
            "p95_ms": get_p(durations_ms, 95),
            "p99_ms": get_p(durations_ms, 99),
            "avg_ttfb_ms": round(sum(ttfbs_ms) / len(ttfbs_ms), 2),
            "sample_count": len(durations_ms)
        }

    @staticmethod
    async def get_timeseries_breakdown(db: AsyncSession, monitor_id: int, limit: int = 60) -> List[Dict[str, Any]]:
        """
        Retrieves the most recent check run timeseries breakdown for Chart.js rendering.
        """
        query = select(CheckRun).where(
            CheckRun.monitor_id == monitor_id
        ).order_by(CheckRun.checked_at.desc()).limit(limit)

        result = await db.execute(query)
        runs = list(reversed(result.scalars().all()))

        return [
            {
                "id": r.id,
                "checked_at": r.checked_at.isoformat() if r.checked_at else None,
                "status_code": r.status_code,
                "is_success": r.is_success,
                "dns_ms": round(r.dns_lookup_us / 1000.0, 2),
                "tcp_ms": round(r.tcp_connect_us / 1000.0, 2),
                "tls_ms": round(r.tls_handshake_us / 1000.0, 2),
                "ttfb_ms": round(r.ttfb_us / 1000.0, 2),
                "total_ms": round(r.total_duration_us / 1000.0, 2),
                "bytes": r.response_bytes,
                "error": r.error_message
            }
            for r in runs
        ]
