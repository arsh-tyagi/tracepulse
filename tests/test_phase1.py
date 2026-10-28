import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.database import init_db_engine

@pytest.mark.asyncio
async def test_full_phase1_flow():
    # 1. Initialize DB
    await init_db_engine()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        health_resp = await client.get("/api/v1/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["status"] == "healthy"
        print("Health Check:", health_data)

        # 2. Create Monitor
        monitor_payload = {
            "name": "Cloudflare Test Probe",
            "target_url": "https://1.1.1.1/cdn-cgi/trace",
            "http_method": "GET",
            "check_interval_sec": 5,
            "timeout_ms": 4000,
            "expected_status": 200,
            "is_active": True
        }
        create_resp = await client.post("/api/v1/monitors", json=monitor_payload)
        assert create_resp.status_code == 201
        monitor_data = create_resp.json()
        monitor_id = monitor_data["id"]
        assert monitor_data["name"] == "Cloudflare Test Probe"
        print(f"Created Monitor ID: {monitor_id}")

        # 3. List Monitors
        list_resp = await client.get("/api/v1/monitors")
        assert list_resp.status_code == 200
        monitors_list = list_resp.json()
        assert any(m["id"] == monitor_id for m in monitors_list)
        print(f"Total Monitors Listed: {len(monitors_list)}")

        # 4. Trigger On-Demand Probe (/test)
        test_resp = await client.post(f"/api/v1/monitors/{monitor_id}/test")
        assert test_resp.status_code == 200
        test_run = test_resp.json()
        assert test_run["monitor_id"] == monitor_id
        assert test_run["status_code"] in [200, 301, 302]
        assert test_run["total_duration_us"] > 0
        print(f"Probe Execution Successful! Latency: {test_run['total_duration_us']}us, Status: {test_run['status_code']}")

        # 5. Test Batch Ingestion Endpoint (/internal/ingest)
        batch_payload = {
            "checks": [
                {
                    "monitor_id": monitor_id,
                    "status_code": 200,
                    "is_success": True,
                    "dns_lookup_us": 1200,
                    "tcp_connect_us": 4500,
                    "tls_handshake_us": 8500,
                    "ttfb_us": 18000,
                    "total_duration_us": 22000,
                    "response_bytes": 1024,
                    "error_message": None
                },
                {
                    "monitor_id": monitor_id,
                    "status_code": 200,
                    "is_success": True,
                    "dns_lookup_us": 1100,
                    "tcp_connect_us": 4200,
                    "tls_handshake_us": 8300,
                    "ttfb_us": 17500,
                    "total_duration_us": 21000,
                    "response_bytes": 1024,
                    "error_message": None
                }
            ]
        }
        ingest_resp = await client.post("/api/v1/internal/ingest", json=batch_payload)
        assert ingest_resp.status_code == 201
        assert ingest_resp.json()["ingested_count"] == 2
        print("Batch Ingestion verified: 2 records stored")

        # 6. Create Alert Rule
        rule_payload = {
            "monitor_id": monitor_id,
            "rule_type": "CONSECUTIVE_FAILURES",
            "threshold_value": 3.0,
            "consecutive_count": 3,
            "webhook_url": "https://webhook.site/test-hook",
            "is_active": True
        }
        rule_resp = await client.post("/api/v1/alerts/rules", json=rule_payload)
        assert rule_resp.status_code == 201
        print("Alert Rule created successfully:", rule_resp.json()["id"])

if __name__ == "__main__":
    asyncio.run(test_full_phase1_flow())
