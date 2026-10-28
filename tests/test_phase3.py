import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.database import init_db_engine

@pytest.mark.asyncio
async def test_phase3_analytics_and_alerts():
    await init_db_engine()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a monitor
        mon_resp = await client.post("/api/v1/monitors", json={
            "name": "Phase 3 Analytics Monitor",
            "target_url": "https://httpbin.org/get",
            "check_interval_sec": 5,
            "timeout_ms": 3000,
            "expected_status": 200
        })
        assert mon_resp.status_code == 201
        monitor_id = mon_resp.json()["id"]

        # 2. Ingest 10 sample runs (varying latencies: 20ms, 40ms, 60ms, 120ms, 250ms...)
        checks = []
        for i in range(1, 11):
            checks.append({
                "monitor_id": monitor_id,
                "status_code": 200,
                "is_success": True,
                "dns_lookup_us": 2000,
                "tcp_connect_us": 3000,
                "tls_handshake_us": 5000,
                "ttfb_us": 10000 * i,
                "total_duration_us": 20000 * i,
                "response_bytes": 500,
                "error_message": None
            })

        ingest_resp = await client.post("/api/v1/internal/ingest", json={"checks": checks})
        assert ingest_resp.status_code == 201

        # 3. Query SLA Analytics
        sla_resp = await client.get(f"/api/v1/monitors/{monitor_id}/sla")
        assert sla_resp.status_code == 200
        sla_data = sla_resp.json()["sla"]
        assert sla_data["24h"]["uptime_percent"] == 100.0
        assert sla_data["24h"]["total_checks"] == 10
        print("SLA 24h result:", sla_data["24h"])

        # 4. Query Percentiles
        perc_resp = await client.get(f"/api/v1/monitors/{monitor_id}/percentiles?hours=24")
        assert perc_resp.status_code == 200
        p_data = perc_resp.json()["percentiles"]
        assert p_data["sample_count"] == 10
        assert p_data["p50_ms"] > 0
        assert p_data["p99_ms"] >= p_data["p50_ms"]
        print("Percentiles result:", p_data)

        # 5. Query Chart.js Timeseries
        ts_resp = await client.get(f"/api/v1/monitors/{monitor_id}/metrics?limit=10")
        assert ts_resp.status_code == 200
        ts_data = ts_resp.json()["data"]
        assert len(ts_data) == 10
        print(f"Chart Timeseries Data Points: {len(ts_data)}, latest total: {ts_data[-1]['total_ms']}ms")

        # 6. Test Alert Rule & Consecutive Failure Incident Trigger
        rule_resp = await client.post("/api/v1/alerts/rules", json={
            "monitor_id": monitor_id,
            "rule_type": "CONSECUTIVE_FAILURES",
            "threshold_value": 2.0,
            "consecutive_count": 2,
            "webhook_url": "https://webhook.site/test-receiver",
            "is_active": True
        })
        assert rule_resp.status_code == 201

        # Ingest 2 consecutive failure checks to trigger alert incident
        failed_checks = [
            {
                "monitor_id": monitor_id,
                "status_code": 500,
                "is_success": False,
                "dns_lookup_us": 1000,
                "tcp_connect_us": 1000,
                "tls_handshake_us": 0,
                "ttfb_us": 5000,
                "total_duration_us": 10000,
                "response_bytes": 0,
                "error_message": "HTTP 500 Server Error"
            },
            {
                "monitor_id": monitor_id,
                "status_code": 500,
                "is_success": False,
                "dns_lookup_us": 1000,
                "tcp_connect_us": 1000,
                "tls_handshake_us": 0,
                "ttfb_us": 5000,
                "total_duration_us": 10000,
                "response_bytes": 0,
                "error_message": "HTTP 500 Server Error"
            }
        ]
        await client.post("/api/v1/internal/ingest", json={"checks": failed_checks})

        # Verify incident is OPEN
        incidents_resp = await client.get("/api/v1/alerts/incidents?status_filter=OPEN")
        assert incidents_resp.status_code == 200
        open_incidents = incidents_resp.json()
        assert any(inc["monitor_id"] == monitor_id and inc["status"] == "OPEN" for inc in open_incidents)
        print("Alert Incident opened successfully:", open_incidents[0]["trigger_reason"])

        # Ingest 1 successful check to trigger resolution
        recovery_check = [{
            "monitor_id": monitor_id,
            "status_code": 200,
            "is_success": True,
            "dns_lookup_us": 1000,
            "tcp_connect_us": 2000,
            "tls_handshake_us": 2000,
            "ttfb_us": 5000,
            "total_duration_us": 12000,
            "response_bytes": 500,
            "error_message": None
        }]
        await client.post("/api/v1/internal/ingest", json={"checks": recovery_check})

        # Verify incident is RESOLVED
        incidents_resolved_resp = await client.get("/api/v1/alerts/incidents?status_filter=RESOLVED")
        assert incidents_resolved_resp.status_code == 200
        resolved_incidents = incidents_resolved_resp.json()
        assert any(inc["monitor_id"] == monitor_id and inc["status"] == "RESOLVED" for inc in resolved_incidents)
        print("Alert Incident resolved successfully!")

if __name__ == "__main__":
    asyncio.run(test_phase3_analytics_and_alerts())
