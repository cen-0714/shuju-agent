from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx


class AmazonReportsRateLimitError(Exception):
    def __init__(self, retry_after: str | None) -> None:
        super().__init__("Amazon Reports API rate limited the request")
        self.retry_after = retry_after


class AmazonReportsAPIError(Exception):
    pass


@dataclass(frozen=True)
class AmazonReportStatus:
    report_id: str
    processing_status: str
    report_document_id: str | None


@dataclass(frozen=True)
class AmazonReportDocument:
    report_document_id: str
    url: str
    compression_algorithm: str | None


class AmazonReportsClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def create_report(
        self,
        *,
        access_token: str,
        amazon_report_type: str,
        marketplace_ids: list[str],
        date_range_start: date,
        date_range_end: date,
        report_options: dict[str, Any],
    ) -> str:
        payload = {
            "reportType": amazon_report_type,
            "marketplaceIds": marketplace_ids,
            "dataStartTime": f"{date_range_start.isoformat()}T00:00:00Z",
            "dataEndTime": f"{date_range_end.isoformat()}T23:59:59Z",
            "reportOptions": report_options,
        }
        response = self._request(
            "POST",
            "/reports/2021-06-30/reports",
            access_token=access_token,
            json=payload,
        )
        report_id = response.json().get("reportId")
        if not report_id:
            raise AmazonReportsAPIError("Amazon createReport response did not include reportId")
        return str(report_id)

    def get_report(self, *, access_token: str, report_id: str) -> AmazonReportStatus:
        response = self._request(
            "GET",
            f"/reports/2021-06-30/reports/{report_id}",
            access_token=access_token,
        )
        payload = response.json()
        return AmazonReportStatus(
            report_id=str(payload.get("reportId") or report_id),
            processing_status=str(payload.get("processingStatus") or ""),
            report_document_id=payload.get("reportDocumentId"),
        )

    def get_report_document(
        self,
        *,
        access_token: str,
        report_document_id: str,
    ) -> AmazonReportDocument:
        response = self._request(
            "GET",
            f"/reports/2021-06-30/documents/{report_document_id}",
            access_token=access_token,
        )
        payload = response.json()
        url = payload.get("url")
        if not url:
            raise AmazonReportsAPIError("Amazon getReportDocument response did not include url")
        return AmazonReportDocument(
            report_document_id=str(payload.get("reportDocumentId") or report_document_id),
            url=str(url),
            compression_algorithm=payload.get("compressionAlgorithm"),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        **kwargs: Any,
    ) -> httpx.Response:
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            response = client.request(
                method,
                f"{self.base_url}{path}",
                headers={"x-amz-access-token": access_token},
                **kwargs,
            )
        if response.status_code in {401, 403}:
            raise PermissionError("Amazon Reports API permission denied")
        if response.status_code == 429:
            raise AmazonReportsRateLimitError(response.headers.get("retry-after"))
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AmazonReportsAPIError(str(exc)) from exc
        return response
