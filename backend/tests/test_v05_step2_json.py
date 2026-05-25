"""
v05 Step 2 — JSON Importer 단위 테스트
실제 JSON 파일을 사용하는 순수 Python 테스트 (Fuseki 불필요).

시나리오:
  S1  Flat JSON 배열 → 5개 fetch_rows, rdf:type 5개
  S2  JSONPath: 배열 추출 ($.data.books[*]) → 2개
  S3  중첩 필드 dot notation (meta.title) → 값 추출
  S4  null 값 처리 → null 필드 트리플 생략
  S5  깊은 중첩 JSONPath ($.data.books[*]) 검증
  S6  URL JSON 소스 → httpx mock
  S7  datetime 값 → xsd:dateTime 추론
  S8  배열 값 필드 → 첫 번째 요소 사용 (또는 문자열 변환)
  S9  빈 배열 [] → 0 individuals, 에러 없음
  S10 복수 ClassMapping (books + authors 각각 json_path로 분리)

실행:
  cd backend && python -m pytest tests/test_v05_step2_json.py -v
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.datasource_import.json_importer import JsonImporter
from services.datasource_import.base import (
    ImporterConfig,
    ClassMappingConfig,
    PropMappingConfig,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# ── 공통 상수 ──────────────────────────────────────────────────────────────────

BOOK_CLASS   = "http://library.org/onto#Book"
AUTHOR_CLASS = "http://library.org/onto#Author"
TITLE_PROP   = "http://library.org/onto#title"
ISBN_PROP    = "http://library.org/onto#isbn"
YEAR_PROP    = "http://library.org/onto#publishYear"
AUTHOR_NAME_PROP = "http://library.org/onto#authorName"
RDF_TYPE     = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_INTEGER  = "http://www.w3.org/2001/XMLSchema#integer"
XSD_DATETIME = "http://www.w3.org/2001/XMLSchema#dateTime"


def simple_cfg(conn: str) -> ImporterConfig:
    """books.json (flat 배열) 용 기본 설정."""
    return ImporterConfig(
        connection_info=conn,
        mappings=[
            ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                property_mappings=[
                    PropMappingConfig("title",       TITLE_PROP),
                    PropMappingConfig("isbn",        ISBN_PROP),
                    PropMappingConfig("publishYear", YEAR_PROP),
                ],
            )
        ],
    )


# ── S1: Flat JSON 배열 ─────────────────────────────────────────────────────────

class TestS1FlatJsonArray:
    def test_fetch_rows_count(self):
        cfg = simple_cfg(os.path.join(FIXTURES, "books.json"))
        rows = JsonImporter(cfg).fetch_rows()
        assert len(rows) == 5

    def test_fetch_rows_first_isbn(self):
        cfg = simple_cfg(os.path.join(FIXTURES, "books.json"))
        rows = JsonImporter(cfg).fetch_rows()
        assert rows[0]["isbn"] == "978-89-6848-101-8"

    def test_type_triples_count(self):
        cfg = simple_cfg(os.path.join(FIXTURES, "books.json"))
        triples = JsonImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 5

    def test_type_triples_class(self):
        cfg = simple_cfg(os.path.join(FIXTURES, "books.json"))
        triples = JsonImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert all(t.object == BOOK_CLASS for t in type_t)


# ── S2: JSONPath 배열 추출 ─────────────────────────────────────────────────────

class TestS2JsonPathArray:
    def test_jsonpath_extracts_books(self):
        """$.data.books[*] 경로로 배열 추출."""
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books_nested.json"),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS,
                    identifier_field="isbn",
                    json_path="$.data.books[*]",
                    property_mappings=[
                        PropMappingConfig("isbn", ISBN_PROP),
                    ],
                )
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 2

    def test_jsonpath_iris_correct(self):
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books_nested.json"),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS,
                    identifier_field="isbn",
                    json_path="$.data.books[*]",
                    property_mappings=[],
                )
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        iris = {t.subject for t in triples}
        assert f"{BOOK_CLASS}_978-1" in iris
        assert f"{BOOK_CLASS}_978-2" in iris


# ── S3: 중첩 필드 dot notation ─────────────────────────────────────────────────

class TestS3NestedDotNotation:
    def test_nested_title_extracted(self):
        """meta.title 경로로 중첩 값 추출."""
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books_nested.json"),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS,
                    identifier_field="isbn",
                    json_path="$.data.books[*]",
                    property_mappings=[
                        PropMappingConfig("meta.title", TITLE_PROP),
                    ],
                )
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        title_t = [t for t in triples if t.predicate == TITLE_PROP]
        assert len(title_t) == 2
        titles = {t.object for t in title_t}
        assert "Nested Book 1" in titles
        assert "Nested Book 2" in titles

    def test_nested_year_extracted(self):
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books_nested.json"),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS,
                    identifier_field="isbn",
                    json_path="$.data.books[*]",
                    property_mappings=[
                        PropMappingConfig("meta.year", YEAR_PROP),
                    ],
                )
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        year_t = [t for t in triples if t.predicate == YEAR_PROP]
        assert year_t[0].datatype == XSD_INTEGER


# ── S4: null 값 처리 ───────────────────────────────────────────────────────────

class TestS4NullValue:
    def test_null_field_skipped(self, tmp_path):
        jf = tmp_path / "null.json"
        jf.write_text('[{"isbn":"978-1","title":null}]', encoding="utf-8")
        cfg = ImporterConfig(
            connection_info=str(jf),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS, identifier_field="isbn",
                    property_mappings=[PropMappingConfig("title", TITLE_PROP)],
                )
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        title_t = [t for t in triples if t.predicate == TITLE_PROP]
        assert len(title_t) == 0

    def test_individual_still_created_without_null_field(self, tmp_path):
        jf = tmp_path / "null.json"
        jf.write_text('[{"isbn":"978-1","title":null}]', encoding="utf-8")
        cfg = ImporterConfig(
            connection_info=str(jf),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS, identifier_field="isbn",
                    property_mappings=[PropMappingConfig("title", TITLE_PROP)],
                )
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 1


# ── S5: 깊은 중첩 JSONPath ─────────────────────────────────────────────────────

class TestS5DeepJsonPath:
    def test_two_levels_deep(self):
        """$.data.books[*] 2단계 진입점."""
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books_nested.json"),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS,
                    identifier_field="isbn",
                    json_path="$.data.books[*]",
                    property_mappings=[],
                )
            ],
        )
        rows = JsonImporter(cfg).fetch_rows_for_mapping(
            cfg.mappings[0]
        )
        assert len(rows) == 2
        assert rows[0]["isbn"] == "978-1"


# ── S6: URL JSON 소스 ─────────────────────────────────────────────────────────

class TestS6UrlJsonSource:
    def test_url_json_fetch(self, monkeypatch):
        payload = [{"isbn": "978-url-1", "title": "URL Book"}]

        class _MockResponse:
            def raise_for_status(self): pass
            def json(self): return payload

        class _MockHttpx:
            @staticmethod
            def get(url, **kwargs): return _MockResponse()

        import services.datasource_import.json_importer as mod
        monkeypatch.setattr(mod, "httpx", _MockHttpx)

        cfg = simple_cfg("https://example.com/books.json")
        rows = JsonImporter(cfg).fetch_rows()
        assert rows[0]["isbn"] == "978-url-1"

    def test_url_json_triples(self, monkeypatch):
        payload = [{"isbn": "978-url-1", "title": "URL Book"}]

        class _MockResponse:
            def raise_for_status(self): pass
            def json(self): return payload

        class _MockHttpx:
            @staticmethod
            def get(url, **kwargs): return _MockResponse()

        import services.datasource_import.json_importer as mod
        monkeypatch.setattr(mod, "httpx", _MockHttpx)

        cfg = simple_cfg("https://example.com/books.json")
        triples = JsonImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 1


# ── S7: datetime 값 타입 추론 ──────────────────────────────────────────────────

class TestS7DatetimeType:
    def test_datetime_datatype(self, tmp_path):
        jf = tmp_path / "dt.json"
        jf.write_text(
            '[{"isbn":"978-1","publishedAt":"2024-01-15T00:00:00Z"}]',
            encoding="utf-8",
        )
        DT_PROP = "http://library.org/onto#publishedAt"
        cfg = ImporterConfig(
            connection_info=str(jf),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS, identifier_field="isbn",
                    property_mappings=[PropMappingConfig("publishedAt", DT_PROP)],
                )
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        dt_t = [t for t in triples if t.predicate == DT_PROP]
        assert dt_t[0].datatype == XSD_DATETIME


# ── S8: 배열 값 필드 ───────────────────────────────────────────────────────────

class TestS8ArrayFieldValue:
    def test_list_value_stringified(self, tmp_path):
        """배열 값은 첫 번째 요소 또는 문자열로 변환."""
        jf = tmp_path / "arr.json"
        jf.write_text(
            '[{"isbn":"978-1","tags":["owl","rdf","sparql"]}]',
            encoding="utf-8",
        )
        TAG_PROP = "http://library.org/onto#tags"
        cfg = ImporterConfig(
            connection_info=str(jf),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS, identifier_field="isbn",
                    property_mappings=[PropMappingConfig("tags", TAG_PROP)],
                )
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        tag_t = [t for t in triples if t.predicate == TAG_PROP]
        # 배열 → 첫 번째 요소 OR 직렬화 — 어느 쪽이든 트리플 1개 생성
        assert len(tag_t) == 1


# ── S9: 빈 배열 ───────────────────────────────────────────────────────────────

class TestS9EmptyArray:
    def test_empty_array_zero_individuals(self, tmp_path):
        jf = tmp_path / "empty.json"
        jf.write_text("[]", encoding="utf-8")
        cfg = simple_cfg(str(jf))
        triples = JsonImporter(cfg).generate_triples()
        assert len(triples) == 0

    def test_empty_array_no_exception(self, tmp_path):
        jf = tmp_path / "empty.json"
        jf.write_text("[]", encoding="utf-8")
        cfg = simple_cfg(str(jf))
        rows = JsonImporter(cfg).fetch_rows()
        assert rows == []


# ── S10: 복수 ClassMapping (books + authors 분리) ─────────────────────────────

class TestS10MultipleClassMappings:
    def test_books_and_authors_separately(self):
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books_with_authors.json"),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS,
                    identifier_field="isbn",
                    json_path="$.books[*]",
                    property_mappings=[PropMappingConfig("title", TITLE_PROP)],
                ),
                ClassMappingConfig(
                    target_class=AUTHOR_CLASS,
                    identifier_field="authorId",
                    json_path="$.authors[*]",
                    property_mappings=[PropMappingConfig("name", AUTHOR_NAME_PROP)],
                ),
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        book_types   = [t for t in triples if t.predicate == RDF_TYPE and t.object == BOOK_CLASS]
        author_types = [t for t in triples if t.predicate == RDF_TYPE and t.object == AUTHOR_CLASS]
        assert len(book_types) == 2
        assert len(author_types) == 2

    def test_author_iris_correct(self):
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books_with_authors.json"),
            mappings=[
                ClassMappingConfig(
                    target_class=AUTHOR_CLASS,
                    identifier_field="authorId",
                    json_path="$.authors[*]",
                    property_mappings=[],
                ),
            ],
        )
        triples = JsonImporter(cfg).generate_triples()
        iris = {t.subject for t in triples}
        assert f"{AUTHOR_CLASS}_auth-001" in iris
        assert f"{AUTHOR_CLASS}_auth-002" in iris
