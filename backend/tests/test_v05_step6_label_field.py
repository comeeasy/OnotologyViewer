"""
v05 Step 6 — label_field / comment_field 단위 테스트

시나리오:
  S1  label_field 지정 → rdfs:label 트리플 자동 생성
  S2  comment_field 지정 → rdfs:comment 트리플 자동 생성
  S3  label_field + comment_field 동시 지정
  S4  label_field 미지정(빈 문자열) → rdfs:label 트리플 없음
  S5  label_field 의 값이 NULL/빈 값 → rdfs:label 트리플 생략
  S6  CSV 소스에서 label_field 동작
  S7  JSON 소스에서 label_field 동작
  S8  RDB 소스에서 label_field 동작
  S9  ImporterConfig 빌드 시 label_field 전달 확인
  S10 label_field 로 import된 individual이 label을 가짐 (mock Fuseki)

실행:
  cd backend && python -m pytest tests/test_v05_step6_label_field.py -v
"""

import json
import os
import sqlite3
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.datasource_import.base import (
    ClassMappingConfig, PropMappingConfig, ImporterConfig,
    RDFS_LABEL, RDFS_COMMENT, RDF_TYPE,
)
from services.datasource_import.csv_importer import CsvImporter
from services.datasource_import.json_importer import JsonImporter
from services.datasource_import.rdb_importer import RdbImporter
from services.datasource_import import import_datasource, ImportResult

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

BOOK_CLASS  = "http://library.org/onto#Book"
TITLE_PROP  = "http://library.org/onto#title"
ISBN_PROP   = "http://library.org/onto#isbn"
XSD_STRING  = "http://www.w3.org/2001/XMLSchema#string"

DATASET = "ontology"
GRAPH   = "http://example.org/graph"
DS_IRI  = "http://example.org/graph/datasources/Datasource_test_label"


# ── S1: label_field → rdfs:label 트리플 ────────────────────────────────────

class TestS1LabelField:
    def test_rdfs_label_generated(self, tmp_path):
        """label_field='title' → rdfs:label 트리플 생성."""
        csv_file = tmp_path / "books.csv"
        csv_file.write_text("isbn,title\n978-1,시맨틱 웹\n", encoding="utf-8")

        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                label_field="title",
                property_mappings=[],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        label_t = [t for t in triples if t.predicate == RDFS_LABEL]
        assert len(label_t) == 1
        assert label_t[0].object == "시맨틱 웹"
        assert label_t[0].is_literal is True

    def test_rdfs_label_subject_correct(self, tmp_path):
        csv_file = tmp_path / "books.csv"
        csv_file.write_text("isbn,title\n978-1,Test Book\n", encoding="utf-8")

        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                label_field="title",
                property_mappings=[],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        label_t = [t for t in triples if t.predicate == RDFS_LABEL]
        assert label_t[0].subject == f"{BOOK_CLASS}_978-1"


# ── S2: comment_field → rdfs:comment 트리플 ────────────────────────────────

class TestS2CommentField:
    def test_rdfs_comment_generated(self, tmp_path):
        """comment_field='description' → rdfs:comment 트리플 생성."""
        csv_file = tmp_path / "books.csv"
        csv_file.write_text("isbn,description\n978-1,This is a great book.\n", encoding="utf-8")

        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                comment_field="description",
                property_mappings=[],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        comment_t = [t for t in triples if t.predicate == RDFS_COMMENT]
        assert len(comment_t) == 1
        assert comment_t[0].object == "This is a great book."


# ── S3: label_field + comment_field 동시 지정 ─────────────────────────────

class TestS3BothFields:
    def test_both_label_and_comment(self, tmp_path):
        csv_file = tmp_path / "books.csv"
        csv_file.write_text("isbn,title,desc\n978-1,My Book,A description.\n", encoding="utf-8")

        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                label_field="title",
                comment_field="desc",
                property_mappings=[],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        label_t   = [t for t in triples if t.predicate == RDFS_LABEL]
        comment_t = [t for t in triples if t.predicate == RDFS_COMMENT]
        assert len(label_t) == 1
        assert len(comment_t) == 1
        assert label_t[0].object == "My Book"
        assert comment_t[0].object == "A description."

    def test_total_triple_count(self, tmp_path):
        """rdf:type + rdfs:label + rdfs:comment = 3 triples."""
        csv_file = tmp_path / "books.csv"
        csv_file.write_text("isbn,title,desc\n978-1,My Book,Desc.\n", encoding="utf-8")

        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                label_field="title",
                comment_field="desc",
                property_mappings=[],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        assert len(triples) == 3


# ── S4: label_field 미지정 → rdfs:label 없음 ──────────────────────────────

class TestS4NoLabelField:
    def test_no_label_triple_when_not_configured(self, tmp_path):
        csv_file = tmp_path / "books.csv"
        csv_file.write_text("isbn,title\n978-1,Book\n", encoding="utf-8")

        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                # label_field 미지정 (기본값 "")
                property_mappings=[PropMappingConfig("title", TITLE_PROP)],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        label_t = [t for t in triples if t.predicate == RDFS_LABEL]
        assert len(label_t) == 0


# ── S5: label_field 값이 빈 값 → rdfs:label 생략 ──────────────────────────

class TestS5EmptyLabelValue:
    def test_empty_label_value_skipped(self, tmp_path):
        """title 컬럼이 비어 있으면 rdfs:label 트리플 생략."""
        csv_file = tmp_path / "books.csv"
        csv_file.write_text("isbn,title\n978-1,\n978-2,Real Title\n", encoding="utf-8")

        cfg = ImporterConfig(
            connection_info=str(csv_file),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                label_field="title",
                property_mappings=[],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        label_t = [t for t in triples if t.predicate == RDFS_LABEL]
        # 978-2 만 rdfs:label 생성 (978-1 은 빈 값이므로 생략)
        assert len(label_t) == 1
        assert label_t[0].object == "Real Title"


# ── S6: CSV 소스 label_field ─────────────────────────────────────────────

class TestS6CsvLabelField:
    def test_csv_multiple_rows_labels(self):
        """books.csv fixture: title → rdfs:label 5개."""
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books.csv"),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                label_field="title",
                property_mappings=[],
            )],
        )
        triples = CsvImporter(cfg).generate_triples()
        label_t = [t for t in triples if t.predicate == RDFS_LABEL]
        assert len(label_t) == 5
        labels = {t.object for t in label_t}
        assert "시맨틱 웹 입문" in labels


# ── S7: JSON 소스 label_field ─────────────────────────────────────────────

class TestS7JsonLabelField:
    def test_json_label_field(self):
        """books.json fixture: title → rdfs:label."""
        cfg = ImporterConfig(
            connection_info=os.path.join(FIXTURES, "books.json"),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                label_field="title",
                property_mappings=[],
            )],
        )
        triples = JsonImporter(cfg).generate_triples()
        label_t = [t for t in triples if t.predicate == RDFS_LABEL]
        assert len(label_t) == 5


# ── S8: RDB 소스 label_field ─────────────────────────────────────────────

class TestS8RdbLabelField:
    def test_rdb_label_field(self, tmp_path):
        """SQLite books 테이블: title → rdfs:label."""
        db_path = str(tmp_path / "books.sqlite")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE books (isbn TEXT PRIMARY KEY, title TEXT)")
        conn.execute("INSERT INTO books VALUES ('978-1', 'RDB Book')")
        conn.commit()
        conn.close()

        cfg = ImporterConfig(
            connection_info=json.dumps({
                "dialect": "sqlite",
                "url": f"sqlite:///{db_path}",
                "query": "SELECT * FROM books",
            }),
            mappings=[ClassMappingConfig(
                target_class=BOOK_CLASS,
                identifier_field="isbn",
                label_field="title",
                property_mappings=[],
            )],
        )
        triples = RdbImporter(cfg).generate_triples()
        label_t = [t for t in triples if t.predicate == RDFS_LABEL]
        assert len(label_t) == 1
        assert label_t[0].object == "RDB Book"


# ── S9: import_datasource 에서 label_field 전달 확인 ─────────────────────

class TestS9ImportDatasourceLabelField:
    def test_label_field_passed_from_ds_info(self):
        """ds_info 매핑에 label_field 가 있으면 ImporterConfig 에 전달."""
        ds_info = {
            "datasource_iri": DS_IRI,
            "label": "Test",
            "ds_type": "csv",
            "connection_info": os.path.join(FIXTURES, "books.csv"),
            "description": None,
            "mappings": [{
                "mapping_iri": "http://example.org/m1",
                "target_class": BOOK_CLASS,
                "identifier_field": "isbn",
                "label": None,
                "label_field": "title",
                "comment_field": "",
                "property_mappings": [],
            }],
        }

        import services.datasource_import as sdi
        with patch.object(sdi, "get_datasource", return_value=ds_info), \
             patch.object(sdi, "sparql_update"):
            result = import_datasource(DATASET, GRAPH, DS_IRI)

        assert result.imported_individuals == 5
        assert result.inserted_triples > 0
        # inserted_triples = 5 rdf:type + 5 rdfs:label = 10
        assert result.inserted_triples >= 10


# ── S10: import 결과 individual이 rdfs:label을 가짐 ───────────────────────

class TestS10ImportedHasLabel:
    def test_inserted_triples_include_label(self):
        """INSERT된 SPARQL에 rdfs:label 포함 확인."""
        ds_info = {
            "datasource_iri": DS_IRI,
            "label": "Test",
            "ds_type": "csv",
            "connection_info": os.path.join(FIXTURES, "books.csv"),
            "description": None,
            "mappings": [{
                "mapping_iri": "http://example.org/m1",
                "target_class": BOOK_CLASS,
                "identifier_field": "isbn",
                "label": None,
                "label_field": "title",
                "comment_field": "",
                "property_mappings": [],
            }],
        }

        sparql_calls: list[str] = []

        def capture_update(dataset, sparql):
            sparql_calls.append(sparql)

        import services.datasource_import as sdi
        with patch.object(sdi, "get_datasource", return_value=ds_info), \
             patch.object(sdi, "sparql_update", side_effect=capture_update):
            import_datasource(DATASET, GRAPH, DS_IRI)

        # INSERT DATA 문에 rdfs:label 포함 여부 확인
        insert_stmts = [s for s in sparql_calls if "INSERT DATA" in s]
        assert any("www.w3.org/2000/01/rdf-schema#label" in s for s in insert_stmts), \
            f"rdfs:label not found in INSERT statements: {insert_stmts}"
