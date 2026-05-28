from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    source: Mapped[str] = mapped_column(String(40))
    report_type: Mapped[str] = mapped_column(String(80))
    date_range_start: Mapped[date] = mapped_column(Date)
    date_range_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")
    raw_dataset: Mapped["RawDataset | None"] = relationship(
        back_populates="import_job", uselist=False
    )


class RawDataset(TimestampMixin, Base):
    __tablename__ = "raw_datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"))
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    source: Mapped[str] = mapped_column(String(40))
    report_type: Mapped[str] = mapped_column(String(80))
    date_range_start: Mapped[date] = mapped_column(Date)
    date_range_end: Mapped[date] = mapped_column(Date)
    schema_version: Mapped[str] = mapped_column(String(80))
    raw_file_path: Mapped[str] = mapped_column(String(500))
    raw_file_checksum: Mapped[str] = mapped_column(String(128))
    row_count: Mapped[int] = mapped_column(Integer)
    data_status: Mapped[str] = mapped_column(String(40))
    data_version: Mapped[str] = mapped_column(String(120))
    source_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    import_job: Mapped[ImportJob] = relationship(back_populates="raw_dataset")
    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")
    raw_rows: Mapped[list["RawReportRow"]] = relationship(back_populates="raw_dataset")

    __table_args__ = (
        UniqueConstraint("seller_account_id", "marketplace_id", "report_type", "raw_file_checksum"),
    )


class RawReportRow(Base):
    __tablename__ = "raw_report_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_dataset_id: Mapped[int] = mapped_column(ForeignKey("raw_datasets.id"))
    row_number: Mapped[int] = mapped_column(Integer)
    row_json: Mapped[str] = mapped_column(Text)

    raw_dataset: Mapped[RawDataset] = relationship(back_populates="raw_rows")
