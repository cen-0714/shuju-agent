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
    VALIDATED = "validated"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
