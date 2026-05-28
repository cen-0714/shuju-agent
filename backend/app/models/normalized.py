from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
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
