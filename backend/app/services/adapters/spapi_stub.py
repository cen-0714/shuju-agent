from app.domain.enums import DataSource
from app.services.adapters.base import DataSourceAdapter, RawDatasetEnvelope


class SPAPIReportAdapter(DataSourceAdapter):
    source = DataSource.SP_API

    def build_envelope(self, *args: object, **kwargs: object) -> RawDatasetEnvelope:
        raise RuntimeError("SP-API adapter is not enabled in the MVP")
