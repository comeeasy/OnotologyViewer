"""
v05 Step 3 — REST API Importer 단위 테스트

시나리오:
  S1  단순 GET → JSON 배열 5개
  S2  Bearer 토큰 인증 헤더 전송
  S3  API Key 헤더 인증
  S4  Offset 페이지네이션 (page=1,2 각 3개 → 6개)
  S5  Cursor 페이지네이션 (nextCursor 방식)
  S6  Link 헤더 페이지네이션 (RFC 5988)
  S7  max_pages 제한 (초과 시 중단)
  S8  응답 에러 처리 (non-200 → ImportError)
  S9  data_path 적용 ($.results[*] 중첩 추출)
  S10 타임아웃 처리 (TimeoutError → ImportError)

실행:
  cd backend && python -m pytest tests/test_v05_step3_rest.py -v
"""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.datasource_import.rest_importer import RestImporter, ImportError as RestImportError
from services.datasource_import.base import (
    ImporterConfig,
    ClassMappingConfig,
    PropMappingConfig,
)

BOOK_CLASS = "http://library.org/onto#Book"
TITLE_PROP = "http://library.org/onto#title"
ISBN_PROP  = "http://library.org/onto#isbn"
RDF_TYPE   = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def make_rest_config(url: str, extra: dict | None = None) -> ImporterConfig:
    """REST connection_info JSON 으로 ImporterConfig 생성."""
    conn_info = {"url": url, **(extra or {})}
    return ImporterConfig(
        connection_info=json.dumps(conn_info),
        mappings=[
            ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                property_mappings=[
                    PropMappingConfig("title", TITLE_PROP),
                    PropMappingConfig("isbn",  ISBN_PROP),
                ],
            )
        ],
    )


# ── 공통 mock 헬퍼 ─────────────────────────────────────────────────────────────

def _mock_response(data, status=200, headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.headers = headers or {}
    r.raise_for_status = MagicMock(side_effect=None if status < 400 else Exception(f"HTTP {status}"))
    return r


# ── S1: 단순 GET JSON 배열 ─────────────────────────────────────────────────────

class TestS1SimpleGet:
    def test_fetch_rows_count(self, monkeypatch):
        data = [{"isbn": f"isbn-{i}", "title": f"Book {i}"} for i in range(5)]

        import services.datasource_import.rest_importer as mod
        monkeypatch.setattr(mod.httpx, "get", lambda url, **kw: _mock_response(data))

        cfg = make_rest_config("https://api.example.com/books")
        rows = RestImporter(cfg).fetch_rows()
        assert len(rows) == 5

    def test_type_triples(self, monkeypatch):
        data = [{"isbn": f"isbn-{i}", "title": f"Book {i}"} for i in range(5)]

        import services.datasource_import.rest_importer as mod
        monkeypatch.setattr(mod.httpx, "get", lambda url, **kw: _mock_response(data))

        cfg = make_rest_config("https://api.example.com/books")
        triples = RestImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 5


# ── S2: Bearer 토큰 인증 ───────────────────────────────────────────────────────

class TestS2BearerAuth:
    def test_auth_header_sent(self, monkeypatch):
        captured_headers = {}
        data = [{"isbn": "978-1", "title": "Secure Book"}]

        import services.datasource_import.rest_importer as mod

        def mock_get(url, headers=None, **kw):
            captured_headers.update(headers or {})
            return _mock_response(data)

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config(
            "https://api.example.com/books",
            {"auth": {"type": "bearer", "token": "my-secret-token"}},
        )
        RestImporter(cfg).fetch_rows()
        assert "Authorization" in captured_headers
        assert captured_headers["Authorization"] == "Bearer my-secret-token"


# ── S3: API Key 헤더 인증 ──────────────────────────────────────────────────────

class TestS3ApiKeyAuth:
    def test_apikey_header_sent(self, monkeypatch):
        captured_headers = {}
        data = [{"isbn": "978-1", "title": "Key Book"}]

        import services.datasource_import.rest_importer as mod

        def mock_get(url, headers=None, **kw):
            captured_headers.update(headers or {})
            return _mock_response(data)

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config(
            "https://api.example.com/books",
            {"auth": {"type": "apikey", "header": "X-API-Key", "token": "key123"}},
        )
        RestImporter(cfg).fetch_rows()
        assert "X-API-Key" in captured_headers
        assert captured_headers["X-API-Key"] == "key123"


# ── S4: Offset 페이지네이션 ────────────────────────────────────────────────────

class TestS4OffsetPagination:
    def test_offset_pagination_total(self, monkeypatch):
        """page=1: 3개, page=2: 3개 → 합계 6개."""
        call_count = 0

        import services.datasource_import.rest_importer as mod

        def mock_get(url, params=None, headers=None, **kw):
            nonlocal call_count
            call_count += 1
            offset = (params or {}).get("page", 1)
            if offset == 1:
                return _mock_response([{"isbn": f"isbn-{i}", "title": f"B{i}"} for i in range(3)])
            elif offset == 2:
                return _mock_response([{"isbn": f"isbn-{i+3}", "title": f"B{i+3}"} for i in range(3)])
            else:
                return _mock_response([])  # 빈 페이지 → 종료

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config(
            "https://api.example.com/books",
            {"pagination": {"type": "offset", "offset_param": "page", "limit_param": "size", "limit": 3}},
        )
        rows = RestImporter(cfg).fetch_rows()
        assert len(rows) == 6

    def test_offset_called_multiple_times(self, monkeypatch):
        call_count = 0

        import services.datasource_import.rest_importer as mod

        def mock_get(url, params=None, headers=None, **kw):
            nonlocal call_count
            call_count += 1
            page = (params or {}).get("page", 1)
            if page <= 2:
                return _mock_response([{"isbn": f"isbn-p{page}", "title": "T"}])
            return _mock_response([])

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config(
            "https://api.example.com/books",
            {"pagination": {"type": "offset", "offset_param": "page", "limit_param": "size", "limit": 1}},
        )
        RestImporter(cfg).fetch_rows()
        assert call_count >= 2


# ── S5: Cursor 페이지네이션 ────────────────────────────────────────────────────

class TestS5CursorPagination:
    def test_cursor_collects_all(self, monkeypatch):
        """cursor → 2번 호출 → 합계 4개."""
        pages = [
            {"items": [{"isbn": "isbn-1"}, {"isbn": "isbn-2"}], "nextCursor": "cur2"},
            {"items": [{"isbn": "isbn-3"}, {"isbn": "isbn-4"}], "nextCursor": None},
        ]
        call_idx = [0]

        import services.datasource_import.rest_importer as mod

        def mock_get(url, params=None, headers=None, **kw):
            page = pages[call_idx[0]]
            call_idx[0] += 1
            return _mock_response(page)

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config(
            "https://api.example.com/books",
            {
                "data_path": "$.items[*]",
                "pagination": {
                    "type": "cursor",
                    "cursor_field": "nextCursor",
                    "cursor_param": "cursor",
                },
            },
        )
        rows = RestImporter(cfg).fetch_rows()
        assert len(rows) == 4


# ── S6: Link 헤더 페이지네이션 ────────────────────────────────────────────────

class TestS6LinkHeaderPagination:
    def test_link_header_follows_next(self, monkeypatch):
        """Link: <url>; rel="next" 헤더를 따라 두 번 호출."""
        pages = [
            (
                [{"isbn": "isbn-1"}, {"isbn": "isbn-2"}],
                {"link": '<https://api.example.com/books?page=2>; rel="next"'},
            ),
            ([{"isbn": "isbn-3"}], {}),  # next 없음 → 종료
        ]
        call_idx = [0]

        import services.datasource_import.rest_importer as mod

        def mock_get(url, params=None, headers=None, **kw):
            data, hdrs = pages[call_idx[0]]
            call_idx[0] += 1
            return _mock_response(data, headers=hdrs)

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config(
            "https://api.example.com/books",
            {"pagination": {"type": "link_header"}},
        )
        rows = RestImporter(cfg).fetch_rows()
        assert len(rows) == 3


# ── S7: max_pages 제한 ────────────────────────────────────────────────────────

class TestS7MaxPages:
    def test_stops_at_max_pages(self, monkeypatch):
        """max_pages=2 이면 3페이지 이상 호출하지 않음."""
        call_count = 0

        import services.datasource_import.rest_importer as mod

        def mock_get(url, params=None, headers=None, **kw):
            nonlocal call_count
            call_count += 1
            page = (params or {}).get("page", 1)
            return _mock_response([{"isbn": f"isbn-{page}"}])

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config(
            "https://api.example.com/books",
            {
                "max_pages": 2,
                "pagination": {"type": "offset", "offset_param": "page", "limit_param": "size", "limit": 1},
            },
        )
        rows = RestImporter(cfg).fetch_rows()
        assert call_count <= 2
        assert len(rows) == 2


# ── S8: 응답 에러 처리 ────────────────────────────────────────────────────────

class TestS8ErrorHandling:
    def test_http_error_raises_import_error(self, monkeypatch):
        import httpx as real_httpx
        import services.datasource_import.rest_importer as mod

        def mock_get(url, **kw):
            raise real_httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config("https://api.example.com/books")
        with pytest.raises(RestImportError) as exc_info:
            RestImporter(cfg).fetch_rows()
        assert "429" in str(exc_info.value) or "HTTP" in str(exc_info.value)


# ── S9: data_path 적용 ────────────────────────────────────────────────────────

class TestS9DataPath:
    def test_data_path_extracts_nested(self, monkeypatch):
        """$.results[*] 경로로 중첩 응답에서 배열 추출."""
        data = {
            "total": 5,
            "results": [{"isbn": f"isbn-{i}", "title": f"Book {i}"} for i in range(5)],
        }

        import services.datasource_import.rest_importer as mod
        monkeypatch.setattr(mod.httpx, "get", lambda url, **kw: _mock_response(data))

        cfg = make_rest_config(
            "https://api.example.com/books",
            {"data_path": "$.results[*]"},
        )
        rows = RestImporter(cfg).fetch_rows()
        assert len(rows) == 5


# ── S10: 타임아웃 처리 ────────────────────────────────────────────────────────

class TestS10Timeout:
    def test_timeout_raises_import_error(self, monkeypatch):
        import httpx as real_httpx
        import services.datasource_import.rest_importer as mod

        def mock_get(url, **kw):
            raise real_httpx.TimeoutException("Request timed out")

        monkeypatch.setattr(mod.httpx, "get", mock_get)

        cfg = make_rest_config("https://api.example.com/books")
        with pytest.raises(RestImportError) as exc_info:
            RestImporter(cfg).fetch_rows()
        assert "timeout" in str(exc_info.value).lower() or "timed" in str(exc_info.value).lower()
