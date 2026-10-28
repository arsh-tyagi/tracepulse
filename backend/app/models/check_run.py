from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from backend.app.database import Base

if TYPE_CHECKING:
    from backend.app.models.monitor import Monitor

class CheckRun(Base):
    __tablename__ = "check_runs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    monitor_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    
    # Microsecond Latency Breakdown
    dns_lookup_us: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tcp_connect_us: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tls_handshake_us: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    ttfb_us: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_duration_us: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    response_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    monitor: Mapped["Monitor"] = relationship("Monitor", back_populates="check_runs")

    __table_args__ = (
        Index("idx_check_runs_monitor_time", "monitor_id", "checked_at"),
        Index("idx_check_runs_time", "checked_at"),
    )
