from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class NormalizedBusinessDaily(Base):
    __tablename__ = "normalized_business_daily"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_dataset_id: Mapped[int] = mapped_column(ForeignKey("raw_datasets.id"))
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    report_date: Mapped[date] = mapped_column(Date)
    asin: Mapped[str | None] = mapped_column(String(20))
    sku: Mapped[str | None] = mapped_column(String(120))
    ordered_product_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    units_ordered: Mapped[int] = mapped_column(default=0)
    sessions: Mapped[int] = mapped_column(default=0)
    page_views: Mapped[int] = mapped_column(default=0)
    conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    buy_box_percentage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    raw_dataset = relationship("RawDataset")
    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")


class NormalizedOrderDaily(Base):
    __tablename__ = "normalized_order_daily"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_dataset_id: Mapped[int] = mapped_column(ForeignKey("raw_datasets.id"))
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    report_date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(120), index=True)
    asin: Mapped[str | None] = mapped_column(String(20))
    product_name: Mapped[str | None] = mapped_column(String(500))
    currency: Mapped[str] = mapped_column(String(3))
    units_ordered: Mapped[int] = mapped_column(default=0)
    ordered_product_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    order_count: Mapped[int] = mapped_column(default=0)

    raw_dataset = relationship("RawDataset")
    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")


class NormalizedInventoryDaily(Base):
    __tablename__ = "normalized_inventory_daily"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_dataset_id: Mapped[int] = mapped_column(ForeignKey("raw_datasets.id"))
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    report_date: Mapped[date] = mapped_column(Date)
    sku: Mapped[str] = mapped_column(String(120))
    asin: Mapped[str] = mapped_column(String(20))
    fulfillment_channel: Mapped[str | None] = mapped_column(String(80))
    available_quantity: Mapped[int] = mapped_column(default=0)
    listing_status: Mapped[str] = mapped_column(String(80))
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    is_active_listing: Mapped[bool] = mapped_column(Boolean, default=False)

    raw_dataset = relationship("RawDataset")
    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")


class NormalizedAdsSearchTermDaily(Base):
    __tablename__ = "normalized_ads_search_term_daily"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_dataset_id: Mapped[int] = mapped_column(ForeignKey("raw_datasets.id"))
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    report_date: Mapped[date] = mapped_column(Date)
    campaign_name: Mapped[str] = mapped_column(String(255))
    search_term: Mapped[str] = mapped_column(String(500))
    impressions: Mapped[int] = mapped_column(default=0)
    clicks: Mapped[int] = mapped_column(default=0)
    spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    attributed_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    attributed_orders: Mapped[int] = mapped_column(default=0)

    raw_dataset = relationship("RawDataset")
    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")
