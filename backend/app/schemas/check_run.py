from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class CheckRunCreate(BaseModel):
    monitor_id: int
    status_code: int
    is_success: bool
    dns_lookup_us: int = Field(0, description="DNS lookup time in microseconds")
    tcp_connect_us: int = Field(0, description="TCP connect duration in microseconds")
    tls_handshake_us: int = Field(0, description="TLS handshake duration in microseconds")
    ttfb_us: int = Field(0, description="Time to first byte in microseconds")
    total_duration_us: int = Field(..., description="Total execution time in microseconds")
    response_bytes: int = Field(0, description="Response payload size in bytes")
    error_message: Optional[str] = None
    checked_at: Optional[datetime] = None

class BatchIngestRequest(BaseModel):
    checks: List[CheckRunCreate] = Field(..., min_length=1, max_length=1000)

class CheckRunResponse(CheckRunCreate):
    id: int
    checked_at: datetime
    
    # Computed millisecond helpers for clean frontend consumption
    @property
    def total_duration_ms(self) -> float:
        return round(self.total_duration_us / 1000.0, 2)

    @property
    def ttfb_ms(self) -> float:
        return round(self.ttfb_us / 1000.0, 2)

    model_config = {"from_attributes": True}
