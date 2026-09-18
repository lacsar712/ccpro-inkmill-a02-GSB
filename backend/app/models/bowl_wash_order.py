from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

BOWL_WASH_STATUSES = ("open", "washing", "done", "void")
# 非终态：同一 Mill 同时只允许一个
BOWL_WASH_ACTIVE_STATUSES = ("open", "washing")
BOWL_WASH_TERMINAL_STATUSES = ("done", "void")


class BowlWashOrder(Base):
    __tablename__ = "bowl_wash_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mill_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mills.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    planned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    operator_name: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    mill: Mapped["Mill"] = relationship("Mill", back_populates="bowl_wash_orders")
