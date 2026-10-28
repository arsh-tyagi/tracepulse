from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.check_run import CheckRun
    from backend.app.models.alert import AlertRule, AlertIncident

class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    http_method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    headers_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_interval_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    expected_status: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    check_runs: Mapped[List["CheckRun"]] = relationship("CheckRun", back_populates="monitor", cascade="all, delete-orphan", passive_deletes=True)
    alert_rules: Mapped[List["AlertRule"]] = relationship("AlertRule", back_populates="monitor", cascade="all, delete-orphan", passive_deletes=True)
    incidents: Mapped[List["AlertIncident"]] = relationship("AlertIncident", back_populates="monitor", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        Index("idx_monitors_active", "is_active", "check_interval_sec"),
    )
