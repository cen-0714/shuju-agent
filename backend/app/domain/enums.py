from enum import StrEnum


class Region(StrEnum):
    AMERICAS = "americas"
    EUROPE = "europe"
    FAR_EAST = "far_east"


class DataSource(StrEnum):
    MANUAL_FILE = "manual_file"
    SP_API = "sp_api"
    ADS_API = "ads_api"


class ReportType(StrEnum):
    BUSINESS_REPORT = "business_report"
    INVENTORY_REPORT = "inventory_report"
    ADS_CAMPAIGN_REPORT = "ads_campaign_report"
    ADS_TARGETING_REPORT = "ads_targeting_report"
    ADS_SEARCH_TERM_REPORT = "ads_search_term_report"


class DataStatus(StrEnum):
    PRELIMINARY = "preliminary"
    STABLE = "stable"
    FINAL = "final"


class ImportJobStatus(StrEnum):
    PENDING = "pending"
    PREVIEWED = "previewed"
    VALIDATED = "validated"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DELETED = "deleted"


class ReportScopeType(StrEnum):
    ALL_STORES = "all_stores"
    SINGLE_STORE = "single_store"


class ReportKind(StrEnum):
    SINGLE_DAY = "single_day"
    DATE_RANGE = "date_range"


class ReportStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    FAILED = "failed"


class LLMStatus(StrEnum):
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AmazonOAuthSessionStatus(StrEnum):
    CREATED = "created"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    FAILED = "failed"


class AmazonAuthorizationStatus(StrEnum):
    ACTIVE = "active"
    FAILED = "failed"
    REVOKED = "revoked"


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
