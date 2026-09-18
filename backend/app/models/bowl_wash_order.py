from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 状态机：open -> washing -> done；open / washing 均可 -> void
BOWL_WASH_STATUSES = ("open", "washing", "done", "void")
ACTIVE_BOWL_WASH_STATUSES = ("open", "washing")
TERMINAL_BOWL_WASH_STATUSES = ("done", "void")


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    mill: Mapped["Mill"] = relationship("Mill", back_populates="bowl_wash_orders")
