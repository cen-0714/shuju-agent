import gzip
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class DownloadedReportDocument:
    content: bytes
    filename: str


class AmazonReportDownloadError(Exception):
    pass


def download_report_document(
    *,
    url: str,
    report_document_id: str,
    compression_algorithm: str | None,
    timeout_seconds: int = 30,
    transport: httpx.BaseTransport | None = None,
) -> DownloadedReportDocument:
    try:
        with httpx.Client(timeout=timeout_seconds, transport=transport) as client:
            response = client.get(url)
            response.raise_for_status()
        content = response.content
        if compression_algorithm == "GZIP":
            content = gzip.decompress(content)
    except Exception as exc:
        raise AmazonReportDownloadError(f"Amazon report document download failed: {exc}") from exc

    return DownloadedReportDocument(
        content=content,
        filename=f"{report_document_id}.json",
    )
