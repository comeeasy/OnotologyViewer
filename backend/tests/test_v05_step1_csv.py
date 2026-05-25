"""
v05 Step 1 — CSV Importer 단위 테스트
실제 데이터 파일을 사용하는 순수 Python 테스트 (Fuseki 불필요).

시나리오:
  S1  기본 flat CSV → 5행 fetch_rows, rdf:type 트리플 5개
  S2  빈 값 필드 → 빈 값 필드는 트리플 생략, 있는 필드는 정상 생성
  S3  PK 특수문자 (ISBN 대시) → IRI에 대시 그대로 보존
  S4  쉼표 포함 필드 (따옴표 처리) → Foo, Bar 정상 파싱
  S5  UTF-8 BOM 파일 → BOM 제거 후 정상 파싱
  S6  대용량 CSV (1000행) → 1000개 fetch_rows
  S7  숫자 타입 자동 추론 → publishYear = xsd:integer
  S8  중복 PK (upsert) → 마지막 행으로 덮어쓰기
  S9  URL CSV 소스 → httpx mock 사용
  S10 복수 ClassMapping → Book + Author 각각 individual 생성

실행:
  cd backend && python -m pytest tests/test_v05_step1_csv.py -v
"""

import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.datasource_import.csv_importer import CsvImporter
from services.datasource_import.base import (
    ImporterConfig,
    ClassMappingConfig,
    PropMappingConfig,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# ── 공통 IRI 상수 ──────────────────────────────────────────────────────────────

BOOK_CLASS   = "http://library.org/onto#Book"
AUTHOR_CLASS = "http://library.org/onto#Author"
TITLE_PROP   = "http://library.org/onto#title"
ISBN_PROP    = "http://library.org/onto#isbn"
YEAR_PROP    = "http://library.org/onto#publishYear"
AUTHOR_NAME_PROP = "http://library.org/onto#authorName"
RDF_TYPE     = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_INTEGER  = "http://www.w3.org/2001/XMLSchema#integer"


def make_config(conn: str, id_field: str = "isbn") -> ImporterConfig:
    """books.csv 용 기본 ImporterConfig 생성."""
    return ImporterConfig(
        connection_info=conn,
        mappings=[
            ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field=id_field,
                property_mappings=[
                    PropMappingConfig(source_field="title",       target_property=TITLE_PROP),
                    PropMappingConfig(source_field="isbn",        target_property=ISBN_PROP),
                    PropMappingConfig(source_field="publishYear", target_property=YEAR_PROP),
                ],
            )
        ],
    )


# ── S1: 기본 flat CSV ──────────────────────────────────────────────────────────

class TestS1BasicFlatCsv:
    def test_fetch_rows_count(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        rows = CsvImporter(cfg).fetch_rows()
        assert len(rows) == 5

    def test_fetch_rows_first_isbn(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        rows = CsvImporter(cfg).fetch_rows()
        assert rows[0]["isbn"] == "978-89-6848-101-8"

    def test_fetch_rows_first_title(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        rows = CsvImporter(cfg).fetch_rows()
        assert rows[0]["title"] == "시맨틱 웹 입문"

    def test_triples_type_count(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        triples = CsvImporter(cfg).generate_triples()
        type_triples = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_triples) == 5

    def test_triples_type_object(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        triples = CsvImporter(cfg).generate_triples()
        type_triples = [t for t in triples if t.predicate == RDF_TYPE]
        assert all(t.object == BOOK_CLASS for t in type_triples)

    def test_iri_format(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        triples = CsvImporter(cfg).generate_triples()
        type_triples = [t for t in triples if t.predicate == RDF_TYPE]
        subjects = {t.subject for t in type_triples}
        assert f"{BOOK_CLASS}_978-89-6848-101-8" in subjects


# ── S2: 빈 값 처리 ─────────────────────────────────────────────────────────────

class TestS2EmptyOptionalField:
    def test_title_present(self):
        """비어있지 않은 title 필드는 트리플 생성."""
        cfg = make_config(os.path.join(FIXTURES, "books_with_empty.csv"))
        triples = CsvImporter(cfg).generate_triples()
        subj = f"{BOOK_CLASS}_978-89-9999-001-0"
        prop_iris = {t.predicate for t in triples if t.subject == subj}
        assert TITLE_PROP in prop_iris

    def test_empty_authorname_no_triple(self):
        """빈 authorName(매핑 없음) 행에서 authorName 트리플이 없어야 함."""
        # authorName은 매핑에 없으므로 원래 트리플이 없음 — 빈 값 필터 확인
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books_with_empty.csv"),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS,
                    identifier_field="isbn",
                    property_mappings=[
                        PropMappingConfig("title",       TITLE_PROP),
                        PropMappingConfig("authorName",  AUTHOR_NAME_PROP),  # 빈 값 필드
                    ],
                )
            ],
        )
        triples = CsvImporter(cfg).generate_triples()
        subj = f"{BOOK_CLASS}_978-89-9999-001-0"
        # 첫 번째 행: authorName="" → 트리플 없음
        author_triples = [
            t for t in triples
            if t.subject == subj and t.predicate == AUTHOR_NAME_PROP
        ]
        assert len(author_triples) == 0

    def test_empty_field_individual_still_created(self):
        """빈 optional 필드가 있어도 individual은 생성된다."""
        cfg = make_config(os.path.join(FIXTURES, "books_with_empty.csv"))
        triples = CsvImporter(cfg).generate_triples()
        type_triples = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_triples) == 2  # books_with_empty.csv는 2행


# ── S3: PK 특수문자 (ISBN 대시) ────────────────────────────────────────────────

class TestS3PkSpecialChars:
    def test_dash_preserved_in_iri(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        triples = CsvImporter(cfg).generate_triples()
        iris = {t.subject for t in triples}
        assert f"{BOOK_CLASS}_978-89-6848-101-8" in iris

    def test_all_five_iris_present(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        triples = CsvImporter(cfg).generate_triples()
        iris = {t.subject for t in triples}
        for isbn in [
            "978-89-6848-101-8", "978-89-6848-102-5", "978-89-6848-103-2",
            "978-89-6848-104-9", "978-89-6848-105-6",
        ]:
            assert f"{BOOK_CLASS}_{isbn}" in iris


# ── S4: 쉼표 포함 필드 (따옴표 처리) ───────────────────────────────────────────

class TestS4QuotedCommas:
    def test_comma_inside_quotes(self, tmp_path):
        csv_file = tmp_path / "quoted.csv"
        csv_file.write_text('isbn,title\n"978-1","Foo, Bar"\n', encoding="utf-8")
        cfg = make_config(str(csv_file))
        rows = CsvImporter(cfg).fetch_rows()
        assert rows[0]["title"] == "Foo, Bar"

    def test_triple_object_correct(self, tmp_path):
        csv_file = tmp_path / "quoted.csv"
        csv_file.write_text('isbn,title\n"978-1","Foo, Bar"\n', encoding="utf-8")
        cfg = make_config(str(csv_file))
        triples = CsvImporter(cfg).generate_triples()
        title_t = [t for t in triples if t.predicate == TITLE_PROP]
        assert title_t[0].object == "Foo, Bar"


# ── S5: UTF-8 BOM ──────────────────────────────────────────────────────────────

class TestS5Utf8Bom:
    def test_bom_stripped_from_column_name(self, tmp_path):
        csv_file = tmp_path / "bom.csv"
        csv_file.write_bytes(
            b"\xef\xbb\xbf" + "isbn,title\n978-1,BOM Test\n".encode("utf-8")
        )
        cfg = make_config(str(csv_file))
        rows = CsvImporter(cfg).fetch_rows()
        # BOM이 컬럼명에 붙지 않아야 함
        assert "isbn" in rows[0]
        assert rows[0]["isbn"] == "978-1"

    def test_bom_value_correct(self, tmp_path):
        csv_file = tmp_path / "bom.csv"
        csv_file.write_bytes(
            b"\xef\xbb\xbf" + "isbn,title\n978-1,BOM Test\n".encode("utf-8")
        )
        cfg = make_config(str(csv_file))
        rows = CsvImporter(cfg).fetch_rows()
        assert rows[0]["title"] == "BOM Test"


# ── S6: 대용량 CSV (1000행) ────────────────────────────────────────────────────

class TestS6LargeCsv:
    def test_1000_rows(self, tmp_path):
        csv_file = tmp_path / "large.csv"
        lines = ["isbn,title"] + [f"isbn-{i:04d},Book {i}" for i in range(1000)]
        csv_file.write_text("\n".join(lines), encoding="utf-8")
        cfg = make_config(str(csv_file))
        rows = CsvImporter(cfg).fetch_rows()
        assert len(rows) == 1000

    def test_1000_type_triples(self, tmp_path):
        csv_file = tmp_path / "large.csv"
        lines = ["isbn,title"] + [f"isbn-{i:04d},Book {i}" for i in range(1000)]
        csv_file.write_text("\n".join(lines), encoding="utf-8")
        cfg = make_config(str(csv_file))
        triples = CsvImporter(cfg).generate_triples()
        type_triples = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_triples) == 1000


# ── S7: 숫자 타입 자동 추론 ────────────────────────────────────────────────────

class TestS7TypeInference:
    def test_integer_datatype(self):
        cfg = make_config(os.path.join(FIXTURES, "books.csv"))
        triples = CsvImporter(cfg).generate_triples()
        year_triples = [t for t in triples if t.predicate == YEAR_PROP]
        assert len(year_triples) == 5
        for t in year_triples:
            assert t.datatype == XSD_INTEGER

    def test_boolean_type(self, tmp_path):
        csv_file = tmp_path / "bool.csv"
        csv_file.write_text("isbn,active\n978-1,true\n978-2,false\n", encoding="utf-8")
        ACTIVE_PROP = "http://library.org/onto#active"
        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[PropMappingConfig("active", ACTIVE_PROP)],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        active_t = [t for t in triples if t.predicate == ACTIVE_PROP]
        assert all(t.datatype == "http://www.w3.org/2001/XMLSchema#boolean" for t in active_t)

    def test_date_type(self, tmp_path):
        csv_file = tmp_path / "date.csv"
        csv_file.write_text("isbn,pubDate\n978-1,2024-03-15\n", encoding="utf-8")
        DATE_PROP = "http://library.org/onto#pubDate"
        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[PropMappingConfig("pubDate", DATE_PROP)],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        date_t = [t for t in triples if t.predicate == DATE_PROP]
        assert date_t[0].datatype == "http://www.w3.org/2001/XMLSchema#date"

    def test_string_fallback(self, tmp_path):
        csv_file = tmp_path / "str.csv"
        csv_file.write_text("isbn,note\n978-1,한글 문자열\n", encoding="utf-8")
        NOTE_PROP = "http://library.org/onto#note"
        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[PropMappingConfig("note", NOTE_PROP)],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        note_t = [t for t in triples if t.predicate == NOTE_PROP]
        assert note_t[0].datatype == "http://www.w3.org/2001/XMLSchema#string"


# ── S8: 중복 PK (upsert) ──────────────────────────────────────────────────────

class TestS8DuplicatePk:
    def test_last_row_wins(self, tmp_path):
        csv_file = tmp_path / "dup.csv"
        csv_file.write_text(
            "isbn,title\n978-1,First\n978-1,Second\n", encoding="utf-8"
        )
        cfg = make_config(str(csv_file))
        triples = CsvImporter(cfg).generate_triples()
        title_triples = [
            t for t in triples
            if t.predicate == TITLE_PROP and "978-1" in t.subject
        ]
        assert len(title_triples) == 1
        assert title_triples[0].object == "Second"

    def test_only_one_type_triple(self, tmp_path):
        csv_file = tmp_path / "dup.csv"
        csv_file.write_text(
            "isbn,title\n978-1,First\n978-1,Second\n", encoding="utf-8"
        )
        cfg = make_config(str(csv_file))
        triples = CsvImporter(cfg).generate_triples()
        type_triples = [t for t in triples if t.predicate == RDF_TYPE and "978-1" in t.subject]
        assert len(type_triples) == 1


# ── S9: URL CSV 소스 (httpx mock) ─────────────────────────────────────────────

class TestS9UrlCsvSource:
    def test_url_csv_fetch(self, monkeypatch):
        csv_content = "isbn,title\n978-url-1,URL Book\n978-url-2,Another\n"

        class _MockResponse:
            text = csv_content
            def raise_for_status(self): pass

        class _MockHttpx:
            @staticmethod
            def get(url, **kwargs):
                return _MockResponse()

        import services.datasource_import.csv_importer as mod
        monkeypatch.setattr(mod, "httpx", _MockHttpx)

        cfg = make_config("https://example.com/books.csv")
        rows = CsvImporter(cfg).fetch_rows()
        assert len(rows) == 2
        assert rows[0]["isbn"] == "978-url-1"

    def test_url_csv_triples(self, monkeypatch):
        csv_content = "isbn,title\n978-url-1,URL Book\n"

        class _MockResponse:
            text = csv_content
            def raise_for_status(self): pass

        class _MockHttpx:
            @staticmethod
            def get(url, **kwargs):
                return _MockResponse()

        import services.datasource_import.csv_importer as mod
        monkeypatch.setattr(mod, "httpx", _MockHttpx)

        cfg = make_config("https://example.com/books.csv")
        triples = CsvImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 1


# ── S10: 복수 ClassMapping ─────────────────────────────────────────────────────

class TestS10MultipleClassMappings:
    def test_two_class_types(self, tmp_path):
        csv_file = tmp_path / "multi.csv"
        csv_file.write_text(
            "isbn,title,authorId,authorName\n"
            "978-1,Book A,author-1,홍길동\n"
            "978-2,Book B,author-2,이영희\n",
            encoding="utf-8",
        )
        config = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS, identifier_field="isbn",
                    property_mappings=[PropMappingConfig("title", TITLE_PROP)],
                ),
                ClassMappingConfig(
                    target_class=AUTHOR_CLASS, identifier_field="authorId",
                    property_mappings=[PropMappingConfig("authorName", AUTHOR_NAME_PROP)],
                ),
            ],
        )
        triples = CsvImporter(config).generate_triples()
        book_types   = [t for t in triples if t.predicate == RDF_TYPE and t.object == BOOK_CLASS]
        author_types = [t for t in triples if t.predicate == RDF_TYPE and t.object == AUTHOR_CLASS]
        assert len(book_types) == 2
        assert len(author_types) == 2

    def test_book_iris_correct(self, tmp_path):
        csv_file = tmp_path / "multi.csv"
        csv_file.write_text(
            "isbn,title,authorId,authorName\n"
            "978-1,Book A,author-1,홍길동\n",
            encoding="utf-8",
        )
        config = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS, identifier_field="isbn",
                    property_mappings=[PropMappingConfig("title", TITLE_PROP)],
                ),
                ClassMappingConfig(
                    target_class=AUTHOR_CLASS, identifier_field="authorId",
                    property_mappings=[PropMappingConfig("authorName", AUTHOR_NAME_PROP)],
                ),
            ],
        )
        triples = CsvImporter(config).generate_triples()
        iris = {t.subject for t in triples}
        assert f"{BOOK_CLASS}_978-1" in iris
        assert f"{AUTHOR_CLASS}_author-1" in iris
