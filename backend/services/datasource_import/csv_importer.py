"""
v05 — CSV Importer

지원:
- 로컬 파일 경로 (UTF-8, UTF-8 BOM 자동 처리)
- HTTP/HTTPS URL (httpx 사용)
- 따옴표 포함 필드 (표준 csv.DictReader)
- 쉼표 포함 필드, 멀티라인 필드
"""

from __future__ import annotations

import csv
import io

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore  # 런타임 모킹 허용

from .base import AbstractImporter, ImporterConfig


class CsvImporter(AbstractImporter):
    """CSV 소스 (로컬 파일 또는 URL) 를 읽어 Triple 목록을 생성."""

    def fetch_rows(self) -> list[dict]:
        """CSV 전체를 읽어 list[dict] 반환.

        - URL: httpx.get() 으로 다운로드
        - 로컬: open() (utf-8-sig = BOM 자동 제거)
        """
        conn = self.config.connection_info
        text = self._load_text(conn)
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _load_text(self, conn: str) -> str:
        if conn.startswith(("http://", "https://")):
            if httpx is None:  # pragma: no cover
                raise ImportError("httpx is required for URL sources. pip install httpx")
            resp = httpx.get(conn, timeout=10, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        else:
            # utf-8-sig 인코딩: UTF-8 BOM (\xef\xbb\xbf) 자동 제거
            with open(conn, encoding="utf-8-sig") as f:
                return f.read()
