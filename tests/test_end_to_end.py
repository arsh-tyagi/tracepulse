import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.database import init_db_engine

@pytest.mark.asyncio
async def test_end_to_end_monitoring_lifecycle():
    await init_db_engine()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a monitor
        mon_resp = await client.post("/api/v1/monitors", json={
            "name": "Integration Test Target",
            "target_url": "https://1.1.1.1/cdn-cgi/trace",
            "http_method": "GET",
            "check_interval_sec": 5,
            "timeout_ms": 3000,
            "expected_status": 200
        })
        assert mon_resp.status_code == 201
        monitor_id = mon_resp.json()["id"]

        # 2. Ingest batch of check runs
        checks_batch = [
            {
                "monitor_id": monitor_id,
                "status_code": 200,
                "is_success": True,
                "dns_lookup_us": 1500,
                "tcp_connect_us": 3200,
                "tls_handshake_us": 6500,
                "ttfb_us": 18000,
                "total_duration_us": 28000,
                "response_bytes": 256,
                "error_message": None
            },
            {
                "monitor_id": monitor_id,
                "status_code": 200,
                "is_success": True,
                "dns_lookup_us": 1400,
                "tcp_connect_us": 3100,
                "tls_handshake_us": 6400,
                "ttfb_us": 17500,
                "total_duration_us": 27500,
                "response_bytes": 256,
                "error_message": None
            }
        ]

        ingest_resp = await client.post("/api/v1/internal/ingest", json={"checks": checks_batch})
        assert ingest_resp.status_code == 201
        assert ingest_resp.json()["ingested_count"] == 2

        # 3. Query SLA uptime
        sla_resp = await client.get(f"/api/v1/monitors/{monitor_id}/sla")
        assert sla_resp.status_code == 200
        sla_body = sla_resp.json()
        assert "sla" in sla_body
        assert sla_body["sla"]["24h"]["uptime_percent"] == 100.0

        # 4. Query percentiles
        perc_resp = await client.get(f"/api/v1/monitors/{monitor_id}/percentiles?hours=24")
        assert perc_resp.status_code == 200
        perc_body = perc_resp.json()
        assert perc_body["percentiles"]["sample_count"] >= 2

        # 5. Verify UI index endpoint serves HTML
        ui_resp = await client.get("/")
        assert ui_resp.status_code == 200
        assert "<!DOCTYPE html>" in ui_resp.text
        assert "TracePulse" in ui_resp.text
