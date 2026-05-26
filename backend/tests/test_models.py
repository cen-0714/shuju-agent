from sqlalchemy import text

from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.domain.enums import DataSource, DataStatus, Region, ReportType


def test_settings_defaults_to_local_storage() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")

    assert settings.APP_ENV == "local"
    assert settings.STORAGE_ROOT.endswith("backend/storage")


def test_domain_enums_have_required_values() -> None:
    assert Region.AMERICAS.value == "americas"
    assert DataSource.MANUAL_FILE.value == "manual_file"
    assert ReportType.BUSINESS_REPORT.value == "business_report"
    assert DataStatus.PRELIMINARY.value == "preliminary"


def test_session_factory_executes_sql() -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        value = session.execute(text("select 1")).scalar_one()

    assert value == 1
