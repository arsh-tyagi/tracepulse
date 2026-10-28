from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class AlertRuleBase(BaseModel):
    monitor_id: int
    rule_type: str = Field(..., pattern="^(CONSECUTIVE_FAILURES|LATENCY_THRESHOLD|STATUS_CODE_MISMATCH)$")
    threshold_value: float = Field(..., description="E.g., 500 for 500ms latency or 3 for 3 consecutive failures")
    consecutive_count: int = Field(1, ge=1, le=100)
    webhook_url: str = Field(..., max_length=2048, json_schema_extra={"example": "https://hooks.slack.com/services/..."})
    is_active: bool = Field(True)

class AlertRuleCreate(AlertRuleBase):
    pass

class AlertRuleResponse(AlertRuleBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}

class AlertIncidentResponse(BaseModel):
    id: int
    monitor_id: int
    alert_rule_id: Optional[int] = None
    status: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    trigger_reason: str

    model_config = {"from_attributes": True}
