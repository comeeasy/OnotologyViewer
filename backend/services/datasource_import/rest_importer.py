"""
v05 — REST API Importer

connection_info: JSON 문자열
{
  "url": "https://api.example.com/books",
  "auth": {
    "type": "bearer|apikey|basic",
    "token": "...",
    "header": "X-API-Key"          // apikey 전용
  },
  "pagination": {
    "type": "offset|cursor|link_header|none",
    "limit_param": "size",          // offset 전용
    "offset_param": "page",         // offset 전용
    "limit": 100,
    "cursor_field": "nextCursor",   // cursor 전용
    "cursor_param": "cursor"        // cursor 전용
  },
  "data_path": "$.results[*]",      // 응답에서 배열 진입점
  "max_pages": 10
}
"""

from __future__ import annotations

import json
import re
from typing import Any

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore


class ImportError(Exception):
    """REST API 호출 실패 시 발생."""


from .base import AbstractImporter, ImporterConfig
from .json_importer import _apply_jsonpath


class RestImporter(AbstractImporter):
    """REST API 소스를 읽어 Triple 목록을 생성."""

    def __init__(self, config: ImporterConfig) -> None:
        super().__init__(config)
        try:
            self._conn: dict = json.loads(config.connection_info)
        except (json.JSONDecodeError, TypeError):
            self._conn = {"url": config.connection_info}

    # ── 공개 인터페이스 ────────────────────────────────────────────────────────

    def fetch_rows(self) -> list[dict]:
        """페이지네이션을 처리하며 모든 레코드를 가져온다."""
        url: str = self._conn.get("url", "")
        auth_headers = self._build_auth_headers()
        pagination = self._conn.get("pagination", {})
        pag_type = pagination.get("type", "none") if pagination else "none"
        data_path: str = self._conn.get("data_path", "")
        max_pages: int = int(self._conn.get("max_pages", 50))

        if pag_type == "offset":
            return self._fetch_offset(url, auth_headers, pagination, data_path, max_pages)
        elif pag_type == "cursor":
            return self._fetch_cursor(url, auth_headers, pagination, data_path, max_pages)
        elif pag_type == "link_header":
            return self._fetch_link_header(url, auth_headers, data_path, max_pages)
        else:
            return self._fetch_single(url, auth_headers, data_path)

    # ── 인증 헤더 ──────────────────────────────────────────────────────────────

    def _build_auth_headers(self) -> dict:
        auth = self._conn.get("auth", {})
        if not auth:
            return {}
        auth_type = auth.get("type", "")
        token = auth.get("token", "")
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {token}"}
        elif auth_type == "apikey":
            header_name = auth.get("header", "X-API-Key")
            return {header_name: token}
        elif auth_type == "basic":
            import base64
            credentials = base64.b64encode(token.encode()).decode()
            return {"Authorization": f"Basic {credentials}"}
        return {}

    # ── 단일 요청 ──────────────────────────────────────────────────────────────

    def _fetch_single(self, url: str, headers: dict, data_path: str) -> list[dict]:
        response = self._get(url, headers=headers)
        return self._extract_rows(response.json(), data_path)

    # ── Offset 페이지네이션 ────────────────────────────────────────────────────

    def _fetch_offset(
        self,
        url: str,
        headers: dict,
        pagination: dict,
        data_path: str,
        max_pages: int,
    ) -> list[dict]:
        offset_param = pagination.get("offset_param", "page")
        limit_param  = pagination.get("limit_param", "limit")
        limit        = int(pagination.get("limit", 100))

        all_rows: list[dict] = []
        page = 1
        for _ in range(max_pages):
            params = {offset_param: page, limit_param: limit}
            resp = self._get(url, headers=headers, params=params)
            rows = self._extract_rows(resp.json(), data_path)
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < limit:
                break  # 마지막 페이지
            page += 1
        return all_rows

    # ── Cursor 페이지네이션 ────────────────────────────────────────────────────

    def _fetch_cursor(
        self,
        url: str,
        headers: dict,
        pagination: dict,
        data_path: str,
        max_pages: int,
    ) -> list[dict]:
        cursor_field = pagination.get("cursor_field", "nextCursor")
        cursor_param = pagination.get("cursor_param", "cursor")

        all_rows: list[dict] = []
        cursor = None
        for _ in range(max_pages):
            params = {cursor_param: cursor} if cursor else {}
            resp = self._get(url, headers=headers, params=params)
            data = resp.json()
            rows = self._extract_rows(data, data_path)
            all_rows.extend(rows)

            # 다음 커서 추출
            if isinstance(data, dict):
                next_cursor = data.get(cursor_field)
            else:
                next_cursor = None
            if not next_cursor:
                break
            cursor = next_cursor
        return all_rows

    # ── Link 헤더 페이지네이션 ────────────────────────────────────────────────

    def _fetch_link_header(
        self,
        url: str,
        headers: dict,
        data_path: str,
        max_pages: int,
    ) -> list[dict]:
        all_rows: list[dict] = []
        current_url: str | None = url
        for _ in range(max_pages):
            if not current_url:
                break
            resp = self._get(current_url, headers=headers)
            rows = self._extract_rows(resp.json(), data_path)
            all_rows.extend(rows)
            current_url = self._parse_link_header(resp.headers.get("link", ""))
        return all_rows

    @staticmethod
    def _parse_link_header(link_header: str) -> str | None:
        """RFC 5988 Link 헤더에서 rel="next" URL 추출."""
        if not link_header:
            return None
        # 예: <https://api.example.com/books?page=2>; rel="next"
        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        return match.group(1) if match else None

    # ── 공통 GET ──────────────────────────────────────────────────────────────

    def _get(self, url: str, headers: dict | None = None, params: dict | None = None):
        if httpx is None:  # pragma: no cover
            raise ImportError("httpx is required. pip install httpx")
        try:
            return httpx.get(url, headers=headers or {}, params=params, timeout=30)
        except httpx.TimeoutException as e:
            raise ImportError(f"Request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise ImportError(f"HTTP error {e.response.status_code}: {e}") from e
        except Exception as e:
            if "timeout" in str(e).lower() or "timed" in str(e).lower():
                raise ImportError(f"Request timed out: {e}") from e
            raise ImportError(f"Request failed: {e}") from e

    # ── 응답 데이터 추출 ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_rows(data: Any, data_path: str) -> list[dict]:
        """data_path JSONPath 로 배열 추출."""
        matched = _apply_jsonpath(data, data_path)
        return [r for r in matched if isinstance(r, dict)]
