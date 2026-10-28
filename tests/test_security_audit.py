import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.database import init_db_engine

@pytest.mark.asyncio
async def test_security_guards():
    await init_db_engine()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print("\n=== EXECUTING SECURITY AUDIT TEST SUITE ===")

        # 1. SSRF Guard: Cloud metadata address rejection
        ssrf_resp = await client.post("/api/v1/monitors", json={
            "name": "Malicious Cloud Metadata Probe",
            "target_url": "http://169.254.169.254/latest/meta-data/",
            "check_interval_sec": 5,
            "timeout_ms": 2000,
            "expected_status": 200
        })
        assert ssrf_resp.status_code == 422
        print("SSRF Guard Verified: Cloud metadata (169.254.169.254) blocked with 422.")

        # 2. SSRF Guard: Disallowed protocols (file://, gopher://, ftp://)
        file_scheme_resp = await client.post("/api/v1/monitors", json={
            "name": "File Scheme Probe",
            "target_url": "file:///etc/passwd",
            "check_interval_sec": 5,
            "timeout_ms": 2000,
            "expected_status": 200
        })
        assert file_scheme_resp.status_code == 422
        print("Protocol Guard Verified: file:// scheme blocked with 422.")

        # 3. CRLF Header Injection Prevention
        crlf_resp = await client.post("/api/v1/monitors", json={
            "name": "CRLF Injection Probe",
            "target_url": "https://httpbin.org/get",
            "headers_json": '{"X-Custom": "safe_value\\r\\nEvil-Header: injected"}',
            "check_interval_sec": 5,
            "timeout_ms": 2000,
            "expected_status": 200
        })
        assert crlf_resp.status_code == 422
        print("CRLF Injection Guard Verified: Newlines in headers blocked with 422.")

        # 4. SQL Injection Immunity
        sqli_payload = "'; DROP TABLE monitors; --"
        sqli_resp = await client.post("/api/v1/monitors", json={
            "name": sqli_payload,
            "target_url": "https://httpbin.org/get",
            "check_interval_sec": 5,
            "timeout_ms": 2000,
            "expected_status": 200
        })
        assert sqli_resp.status_code == 201
        created_monitor = sqli_resp.json()
        assert created_monitor["name"] == sqli_payload

        # Verify table still exists and data was parameterized
        list_resp = await client.get("/api/v1/monitors")
        assert list_resp.status_code == 200
        assert any(m["id"] == created_monitor["id"] for m in list_resp.json())
        print("SQL Injection Immunity Verified: Parameterized queries preserved database integrity.")

        # 5. Invalid Check Interval and Timeout Bounds
        bounds_resp = await client.post("/api/v1/monitors", json={
            "name": "Invalid Bounds Probe",
            "target_url": "https://httpbin.org/get",
            "check_interval_sec": 1, # minimum is 2
            "timeout_ms": 100,       # minimum is 500
            "expected_status": 200
        })
        assert bounds_resp.status_code == 422
        print("Bounds Validation Verified: Out-of-bounds parameters rejected with 422.")

        print("=== ALL SECURITY CONTROLS VERIFIED SUCCESSFULLY ===\n")

if __name__ == "__main__":
    asyncio.run(test_security_guards())
