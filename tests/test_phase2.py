import pytest
import sys
import os

# Add root path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.probe_service import execute_probe_sync

def test_probe_success():
    result = execute_probe_sync(
        target_url="https://1.1.1.1/cdn-cgi/trace",
        method="GET",
        timeout_ms=5000,
        expected_status=200
    )
    print("Cloudflare Probe Result:", result.to_dict())
    assert result.status_code == 200
    assert result.is_success is True
    assert result.total_duration_us > 0
    assert result.ttfb_us > 0
    assert result.error_message is None

def test_probe_dns_or_connection_failure():
    result = execute_probe_sync(
        target_url="https://non-existent-probe-domain-404-fail.org/ping",
        method="GET",
        timeout_ms=2000,
        expected_status=200
    )
    print("Failed Probe Result:", result.to_dict())
    assert result.is_success is False
    assert result.error_message is not None

def test_probe_status_code_mismatch():
    result = execute_probe_sync(
        target_url="https://1.1.1.1/cdn-cgi/trace",
        method="GET",
        timeout_ms=5000,
        expected_status=404  # Deliberately expect 404 to verify mismatch detection
    )
    print("Mismatch Probe Result:", result.to_dict())
    assert result.status_code == 200
    assert result.is_success is False
    assert "!= expected 404" in result.error_message or "Expected 404" in result.error_message

if __name__ == "__main__":
    test_probe_success()
    test_probe_dns_or_connection_failure()
    test_probe_status_code_mismatch()
    print("Phase 2 tests passed successfully!")
