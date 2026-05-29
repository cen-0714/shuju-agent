from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.settings import SellerAccount


class AmazonAuthorization(TimestampMixin, Base):
    __tablename__ = "amazon_authorizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    selling_partner_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    seller_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("seller_accounts.id"), nullable=True, index=True
    )
    lwa_client_id: Mapped[str] = mapped_column(String(255))
    refresh_token_encrypted: Mapped[str] = mapped_column(Text)
    token_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    seller_account: Mapped["SellerAccount | None"] = relationship()
