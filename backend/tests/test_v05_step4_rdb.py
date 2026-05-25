"""
v05 Step 4 — RDB Importer 단위 테스트 (SQLite 중심)

시나리오:
  S1  SQLite: SELECT * FROM books → 5 individuals
  S2  SQLite: JOIN (books + authors) → author_name 포함 트리플
  S3  SQLite: WHERE 조건 → 필터링된 결과
  S4  SQLite: NULL 컬럼 → NULL 필드 트리플 생략
  S5  SQLite: 날짜 컬럼 → xsd:date 추론
  S6  SQLite: 대용량 (1000행) → 1000 individuals
  S7  SQLite: 복합 PK (isbn + edition 연결) → 복합 PK IRI
  S8  SQLite: 복수 ClassMapping (books + authors 테이블)
  S9  잘못된 dialect → ImportError
  S10 잘못된 connection URL → ImportError

실행:
  cd backend && python -m pytest tests/test_v05_step4_rdb.py -v
"""

import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.datasource_import.rdb_importer import RdbImporter, ImportError as RdbImportError
from services.datasource_import.base import (
    ImporterConfig,
    ClassMappingConfig,
    PropMappingConfig,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

BOOK_CLASS   = "http://library.org/onto#Book"
AUTHOR_CLASS = "http://library.org/onto#Author"
TITLE_PROP   = "http://library.org/onto#title"
ISBN_PROP    = "http://library.org/onto#isbn"
YEAR_PROP    = "http://library.org/onto#publishYear"
AUTHOR_NAME_PROP = "http://library.org/onto#authorName"
RDF_TYPE     = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_INTEGER  = "http://www.w3.org/2001/XMLSchema#integer"
XSD_DATE     = "http://www.w3.org/2001/XMLSchema#date"


# ── SQLite 픽스처 ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sqlite_db(tmp_path_factory):
    """테스트용 SQLite DB 생성."""
    db_dir = tmp_path_factory.mktemp("db")
    db_path = str(db_dir / "library.sqlite")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
    CREATE TABLE books (
        isbn TEXT PRIMARY KEY,
        title TEXT,
        author_name TEXT,
        publish_year INTEGER,
        publisher TEXT,
        pub_date TEXT
    );
    INSERT INTO books VALUES
        ('978-89-6848-101-8','시맨틱 웹 입문','홍길동',2024,'한빛미디어','2024-03-01'),
        ('978-89-6848-102-5','온톨로지 설계','이영희',2023,'위키북스','2023-06-15'),
        ('978-89-6848-103-2','SPARQL 마스터','박철수',2024,'한빛미디어','2024-01-10'),
        ('978-89-6848-104-9','지식 표현과 추론','김민지',2023,'위키북스','2023-09-20'),
        ('978-89-6848-105-6','RDF와 연결 데이터','최동현',2025,'한빛미디어','2025-02-28');

    CREATE TABLE authors (
        author_id TEXT PRIMARY KEY,
        name TEXT,
        affiliation TEXT
    );
    INSERT INTO authors VALUES
        ('auth-001','홍길동','서울대학교'),
        ('auth-002','이영희','KAIST'),
        ('auth-003','박철수','연세대학교');

    CREATE TABLE books_with_null (
        isbn TEXT PRIMARY KEY,
        title TEXT
    );
    INSERT INTO books_with_null VALUES
        ('978-null-1', NULL),
        ('978-null-2', 'Non-null Title');
    """)
    conn.commit()
    conn.close()
    return db_path


def make_rdb_config(db_path: str, query: str, extra_mappings=None) -> ImporterConfig:
    conn_info = json.dumps({
        "dialect": "sqlite",
        "url": f"sqlite:///{db_path}",
        "query": query,
    })
    mappings = extra_mappings or [
        ClassMappingConfig(
            target_class=BOOK_CLASS,
            identifier_field="isbn",
            property_mappings=[
                PropMappingConfig("title",       TITLE_PROP),
                PropMappingConfig("isbn",        ISBN_PROP),
                PropMappingConfig("publish_year", YEAR_PROP),
            ],
        )
    ]
    return ImporterConfig(connection_info=conn_info, mappings=mappings)


# ── S1: SELECT * FROM books ────────────────────────────────────────────────────

class TestS1SelectAll:
    def test_fetch_rows_count(self, sqlite_db):
        cfg = make_rdb_config(sqlite_db, "SELECT * FROM books")
        rows = RdbImporter(cfg).fetch_rows()
        assert len(rows) == 5

    def test_type_triples_count(self, sqlite_db):
        cfg = make_rdb_config(sqlite_db, "SELECT * FROM books")
        triples = RdbImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 5

    def test_iri_format(self, sqlite_db):
        cfg = make_rdb_config(sqlite_db, "SELECT * FROM books")
        triples = RdbImporter(cfg).generate_triples()
        iris = {t.subject for t in triples}
        assert f"{BOOK_CLASS}_978-89-6848-101-8" in iris


# ── S2: JOIN 쿼리 ─────────────────────────────────────────────────────────────

class TestS2JoinQuery:
    def test_join_author_name(self, sqlite_db):
        """books JOIN authors → author_name 포함 트리플."""
        query = """
        SELECT b.isbn, b.title, a.name AS author_name
        FROM books b
        JOIN authors a ON b.author_name = a.name
        """
        cfg = make_rdb_config(
            sqlite_db, query,
            extra_mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[
                    PropMappingConfig("title",       TITLE_PROP),
                    PropMappingConfig("author_name", AUTHOR_NAME_PROP),
                ],
            )],
        )
        triples = RdbImporter(cfg).generate_triples()
        author_t = [t for t in triples if t.predicate == AUTHOR_NAME_PROP]
        assert len(author_t) >= 1


# ── S3: WHERE 조건 ────────────────────────────────────────────────────────────

class TestS3WhereFilter:
    def test_where_year_filter(self, sqlite_db):
        cfg = make_rdb_config(sqlite_db, "SELECT * FROM books WHERE publish_year > 2023")
        rows = RdbImporter(cfg).fetch_rows()
        assert all(int(r["publish_year"]) > 2023 for r in rows)
        assert len(rows) >= 1  # 2024, 2025년 데이터 있음

    def test_filtered_count(self, sqlite_db):
        cfg = make_rdb_config(sqlite_db, "SELECT * FROM books WHERE publish_year = 2024")
        rows = RdbImporter(cfg).fetch_rows()
        assert len(rows) == 2  # 2024년 책 2권


# ── S4: NULL 컬럼 처리 ────────────────────────────────────────────────────────

class TestS4NullColumn:
    def test_null_title_skipped(self, sqlite_db):
        cfg = make_rdb_config(
            sqlite_db, "SELECT * FROM books_with_null",
            extra_mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[PropMappingConfig("title", TITLE_PROP)],
            )],
        )
        triples = RdbImporter(cfg).generate_triples()
        # isbn=978-null-1: title=NULL → title 트리플 없음
        subj = f"{BOOK_CLASS}_978-null-1"
        title_t = [t for t in triples if t.subject == subj and t.predicate == TITLE_PROP]
        assert len(title_t) == 0

    def test_null_individual_still_created(self, sqlite_db):
        cfg = make_rdb_config(
            sqlite_db, "SELECT * FROM books_with_null",
            extra_mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[PropMappingConfig("title", TITLE_PROP)],
            )],
        )
        triples = RdbImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 2


# ── S5: 날짜 컬럼 ─────────────────────────────────────────────────────────────

class TestS5DateColumn:
    def test_date_datatype(self, sqlite_db):
        DATE_PROP = "http://library.org/onto#pubDate"
        cfg = make_rdb_config(
            sqlite_db, "SELECT isbn, pub_date FROM books",
            extra_mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[PropMappingConfig("pub_date", DATE_PROP)],
            )],
        )
        triples = RdbImporter(cfg).generate_triples()
        date_t = [t for t in triples if t.predicate == DATE_PROP]
        assert len(date_t) == 5
        for t in date_t:
            assert t.datatype == XSD_DATE


# ── S6: 대용량 (1000행) ───────────────────────────────────────────────────────

class TestS6LargeTable:
    def test_1000_rows(self, tmp_path):
        db_path = str(tmp_path / "large.sqlite")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, name TEXT)")
        conn.executemany(
            "INSERT INTO items VALUES (?, ?)",
            [(f"item-{i:04d}", f"Item {i}") for i in range(1000)],
        )
        conn.commit(); conn.close()

        cfg = make_rdb_config(
            db_path, "SELECT * FROM items",
            extra_mappings=[ClassMappingConfig(
                target_class="http://example.org/Item", identifier_field="id",
                property_mappings=[],
            )],
        )
        rows = RdbImporter(cfg).fetch_rows()
        assert len(rows) == 1000

    def test_1000_type_triples(self, tmp_path):
        db_path = str(tmp_path / "large2.sqlite")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, name TEXT)")
        conn.executemany(
            "INSERT INTO items VALUES (?, ?)",
            [(f"item-{i:04d}", f"Item {i}") for i in range(1000)],
        )
        conn.commit(); conn.close()

        cfg = make_rdb_config(
            db_path, "SELECT * FROM items",
            extra_mappings=[ClassMappingConfig(
                target_class="http://example.org/Item", identifier_field="id",
                property_mappings=[],
            )],
        )
        triples = RdbImporter(cfg).generate_triples()
        type_t = [t for t in triples if t.predicate == RDF_TYPE]
        assert len(type_t) == 1000


# ── S7: 복합 PK ───────────────────────────────────────────────────────────────

class TestS7CompositePk:
    def test_composite_pk_iri(self, tmp_path):
        db_path = str(tmp_path / "comp.sqlite")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE editions (isbn TEXT, edition INTEGER, title TEXT)")
        conn.execute("INSERT INTO editions VALUES ('978-1', 2, 'Book 2nd Ed')")
        conn.commit(); conn.close()

        # 복합 PK: isbn_edition 컬럼을 SQL에서 생성
        cfg = make_rdb_config(
            db_path,
            "SELECT isbn || '_' || edition AS pk_field, title FROM editions",
            extra_mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="pk_field",
                property_mappings=[PropMappingConfig("title", TITLE_PROP)],
            )],
        )
        triples = RdbImporter(cfg).generate_triples()
        iris = {t.subject for t in triples}
        assert f"{BOOK_CLASS}_978-1_2" in iris


# ── S8: 복수 ClassMapping ─────────────────────────────────────────────────────

class TestS8MultipleClassMappings:
    def test_books_and_authors(self, sqlite_db):
        AUTHOR_NAME2 = "http://library.org/onto#name"
        AFFIL_PROP   = "http://library.org/onto#affiliation"

        cfg = ImporterConfig(
            connection_info=json.dumps({
                "dialect": "sqlite",
                "url": f"sqlite:///{sqlite_db}",
                "query": "SELECT * FROM books",
            }),
            mappings=[
                ClassMappingConfig(
                    target_class=BOOK_CLASS, identifier_field="isbn",
                    sql_query="SELECT * FROM books",
                    property_mappings=[PropMappingConfig("title", TITLE_PROP)],
                ),
                ClassMappingConfig(
                    target_class=AUTHOR_CLASS, identifier_field="author_id",
                    sql_query="SELECT * FROM authors",
                    property_mappings=[PropMappingConfig("name", AUTHOR_NAME2)],
                ),
            ],
        )
        triples = RdbImporter(cfg).generate_triples()
        book_t   = [t for t in triples if t.predicate == RDF_TYPE and t.object == BOOK_CLASS]
        author_t = [t for t in triples if t.predicate == RDF_TYPE and t.object == AUTHOR_CLASS]
        assert len(book_t) == 5
        assert len(author_t) == 3


# ── S9: 잘못된 dialect ────────────────────────────────────────────────────────

class TestS9InvalidDialect:
    def test_unsupported_dialect_raises(self):
        cfg = ImporterConfig(
            connection_info=json.dumps({"dialect": "oracle", "url": "oracle://..."}),
            mappings=[],
        )
        with pytest.raises(RdbImportError) as exc_info:
            RdbImporter(cfg).fetch_rows()
        assert "지원하지 않는" in str(exc_info.value) or "unsupported" in str(exc_info.value).lower()


# ── S10: 잘못된 connection URL ───────────────────────────────────────────────

class TestS10InvalidUrl:
    def test_bad_url_raises(self):
        cfg = ImporterConfig(
            connection_info=json.dumps({
                "dialect": "sqlite",
                "url": "sqlite:////nonexistent/path/that/does/not/exist.db",
                "query": "SELECT * FROM books",
            }),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS, identifier_field="isbn",
                property_mappings=[],
            )],
        )
        with pytest.raises((RdbImportError, Exception)):
            RdbImporter(cfg).fetch_rows()
