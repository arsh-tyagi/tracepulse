from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator, ConfigDict
import json

BLOCKED_SSRF_HOSTS = {"169.254.169.254", "metadata.google.internal", "instance-data"}

def validate_safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("Target URL scheme must be 'http' or 'https'")
    if not parsed.netloc:
        raise ValueError("Target URL must have a valid host")
    
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    if hostname in BLOCKED_SSRF_HOSTS:
        raise ValueError(f"Probing cloud metadata address '{hostname}' is prohibited for security reasons.")
    return url

def validate_safe_headers(headers_str: Optional[str]) -> Optional[str]:
    if not headers_str:
        return None
    try:
        parsed = json.loads(headers_str)
        if not isinstance(parsed, dict):
            raise ValueError("headers_json must serialize to a JSON object")
        for k, v in parsed.items():
            if not isinstance(k, str) or not isinstance(v, (str, int, float)):
                raise ValueError("Header keys and values must be strings or primitives")
            k_str, v_str = str(k), str(v)
            if any(c in k_str or c in v_str for c in ('\r', '\n')):
                raise ValueError("Header keys and values cannot contain newline characters (CRLF injection prevented)")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Invalid JSON in headers_json: {e}")
    return headers_str

class MonitorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, json_schema_extra={"example": "Production Auth API"})
    target_url: str = Field(..., max_length=2048, json_schema_extra={"example": "https://api.example.com/health"})
    http_method: str = Field("GET", pattern="^(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH)$")
    headers_json: Optional[str] = Field(None, json_schema_extra={"example": '{"Authorization": "Bearer token"}'})
    body_payload: Optional[str] = Field(None, json_schema_extra={"example": '{"test": true}'})
    check_interval_sec: int = Field(10, ge=2, le=3600, description="Interval in seconds between probes")
    timeout_ms: int = Field(5000, ge=500, le=60000, description="Request timeout in milliseconds")
    expected_status: int = Field(200, ge=100, le=599, description="Expected HTTP response status code")
    is_active: bool = Field(True, description="Whether monitoring is active")

    @field_validator("target_url")
    def validate_url(cls, v):
        return validate_safe_url(v)

    @field_validator("headers_json")
    def validate_headers(cls, v):
        return validate_safe_headers(v)

class MonitorCreate(MonitorBase):
    pass

class MonitorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    target_url: Optional[str] = Field(None, max_length=2048)
    http_method: Optional[str] = Field(None, pattern="^(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH)$")
    headers_json: Optional[str] = None
    body_payload: Optional[str] = None
    check_interval_sec: Optional[int] = Field(None, ge=2, le=3600)
    timeout_ms: Optional[int] = Field(None, ge=500, le=60000)
    expected_status: Optional[int] = Field(None, ge=100, le=599)
    is_active: Optional[bool] = None

    @field_validator("target_url")
    def validate_url(cls, v):
        if v is not None:
            return validate_safe_url(v)
        return v

    @field_validator("headers_json")
    def validate_headers(cls, v):
        return validate_safe_headers(v)

class MonitorResponse(MonitorBase):
    id: int
    created_at: datetime
    updated_at: datetime
    latest_status_code: Optional[int] = None
    latest_latency_ms: Optional[float] = None
    uptime_24h_percent: Optional[float] = None
    active_incidents_count: int = 0

    model_config = ConfigDict(from_attributes=True)
