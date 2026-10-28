from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.monitor import Monitor

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monitor_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'CONSECUTIVE_FAILURES', 'LATENCY_THRESHOLD', 'STATUS_CODE_MISMATCH'
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    consecutive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    webhook_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    monitor: Mapped["Monitor"] = relationship("Monitor", back_populates="alert_rules")

    __table_args__ = (
        Index("idx_alert_rules_monitor", "monitor_id", "is_active"),
    )

class AlertIncident(Base):
    __tablename__ = "alert_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monitor_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)
    alert_rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")  # 'OPEN', 'RESOLVED'
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger_reason: Mapped[str] = mapped_column(String(1024), nullable=False)

    monitor: Mapped["Monitor"] = relationship("Monitor", back_populates="incidents")

    __table_args__ = (
        Index("idx_incidents_monitor_status", "monitor_id", "status"),
        Index("idx_incidents_time", "triggered_at"),
    )
