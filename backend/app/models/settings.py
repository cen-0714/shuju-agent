from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)

    seller_accounts: Mapped[list["SellerAccount"]] = relationship(back_populates="organization")


class SellerAccount(TimestampMixin, Base):
    __tablename__ = "seller_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    display_name: Mapped[str] = mapped_column(String(200))
    amazon_seller_id: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True)

    organization: Mapped[Organization] = relationship(back_populates="seller_accounts")
    marketplaces: Mapped[list["Marketplace"]] = relationship(back_populates="seller_account")

    __table_args__ = (UniqueConstraint("organization_id", "amazon_seller_id"),)


class Marketplace(TimestampMixin, Base):
    __tablename__ = "marketplaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(40))
    country_code: Mapped[str] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(80))
    currency_code: Mapped[str] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(default=True)

    seller_account: Mapped[SellerAccount] = relationship(back_populates="marketplaces")

    __table_args__ = (UniqueConstraint("seller_account_id", "marketplace_id"),)
