from app.domain.enums import DataSource
from app.services.adapters.base import DataSourceAdapter, RawDatasetEnvelope


class AdsAPIReportAdapter(DataSourceAdapter):
    source = DataSource.ADS_API

    def build_envelope(self, *args: object, **kwargs: object) -> RawDatasetEnvelope:
        raise RuntimeError("Amazon Ads API adapter is not enabled in the MVP")
