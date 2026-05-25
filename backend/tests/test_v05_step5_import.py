"""
v05 Step 5 — Import Engine 통합 단위 테스트

시나리오:
  S1  get_importer: csv → CsvImporter
  S2  get_importer: json → JsonImporter
  S3  get_importer: rest → RestImporter
  S4  get_importer: rdb  → RdbImporter
  S5  get_importer: 알 수 없는 타입 → ValueError
  S6  import_datasource: CSV 소스 → triples INSERT (Fuseki mock)
  S7  import_datasource: 빈 트리플 → skipped (INSERT 없음)
  S8  import_datasource: importer 예외 → result.errors 에 메시지
  S9  ImportResult dataclass 기본값 검증
  S10 FastAPI 엔드포인트: POST /api/datasources/{iri}/import → 200 + ImportResult JSON
  S11 FastAPI 엔드포인트: 없는 Datasource IRI → 404

실행:
  cd backend && python -m pytest tests/test_v05_step5_import.py -v
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.datasource_import import get_importer, import_datasource, ImportResult
from services.datasource_import.base import ImporterConfig, ClassMappingConfig, PropMappingConfig
from services.datasource_import.csv_importer import CsvImporter
from services.datasource_import.json_importer import JsonImporter
from services.datasource_import.rest_importer import RestImporter
from services.datasource_import.rdb_importer import RdbImporter

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

BOOK_CLASS = "http://library.org/onto#Book"
TITLE_PROP  = "http://library.org/onto#title"
ISBN_PROP   = "http://library.org/onto#isbn"
RDF_TYPE    = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

DATASET = "ontology"
GRAPH   = "http://example.org/graph"
DS_IRI  = "http://example.org/graph/datasources/Datasource_test01"


def _simple_config(conn: str) -> ImporterConfig:
    return ImporterConfig(
        connection_info=conn,
        mappings=[ClassMappingConfig(
            target_class=BOOK_CLASS,
            identifier_field="isbn",
            property_mappings=[PropMappingConfig("title", TITLE_PROP)],
        )],
    )


# ── S1~S4: get_importer 팩토리 ─────────────────────────────────────────────────

class TestS1GetImporterCsv:
    def test_returns_csv_importer(self):
        cfg = _simple_config("dummy.csv")
        assert isinstance(get_importer("csv", cfg), CsvImporter)


class TestS2GetImporterJson:
    def test_returns_json_importer(self):
        cfg = _simple_config("dummy.json")
        assert isinstance(get_importer("json", cfg), JsonImporter)


class TestS3GetImporterRest:
    def test_returns_rest_importer(self):
        cfg = _simple_config(json.dumps({"url": "https://api.example.com/books"}))
        assert isinstance(get_importer("rest", cfg), RestImporter)


class TestS4GetImporterRdb:
    def test_returns_rdb_importer(self):
        cfg = _simple_config(json.dumps({"dialect": "sqlite", "url": "sqlite:///x.db", "query": "SELECT 1"}))
        assert isinstance(get_importer("rdb", cfg), RdbImporter)


# ── S5: 알 수 없는 타입 ───────────────────────────────────────────────────────

class TestS5UnknownType:
    def test_raises_value_error(self):
        cfg = _simple_config("x")
        with pytest.raises(ValueError) as exc_info:
            get_importer("excel", cfg)
        assert "excel" in str(exc_info.value).lower() or "지원" in str(exc_info.value)


# ── S6: import_datasource CSV mock ────────────────────────────────────────────

class TestS6ImportDatasourceCsv:
    def test_csv_import_success(self):
        """CSV 파일에서 import → triples INSERT 호출 확인."""
        ds_info = {
            "datasource_iri": DS_IRI,
            "label": "Test Books",
            "ds_type": "csv",
            "connection_info": os.path.join(FIXTURES, "books.csv"),
            "description": None,
            "mappings": [
                {
                    "mapping_iri": "http://example.org/m1",
                    "target_class": BOOK_CLASS,
                    "identifier_field": "isbn",
                    "label": None,
                    "property_mappings": [
                        {"prop_mapping_iri": "http://example.org/p1", "source_field": "title", "target_property": TITLE_PROP},
                    ],
                }
            ],
        }

        import services.datasource_import as sdi
        with patch.object(sdi, "get_datasource", return_value=ds_info), \
             patch.object(sdi, "sparql_update") as mock_update:
            result = import_datasource(DATASET, GRAPH, DS_IRI)

        assert result.imported_individuals == 5
        assert result.inserted_triples > 0
        assert len(result.errors) == 0
        # sparql_update 가 호출됐는지 (DELETE + INSERT)
        assert mock_update.call_count >= 1

    def test_csv_import_result_graph(self):
        """result.graph == 입력 GRAPH."""
        ds_info = {
            "datasource_iri": DS_IRI,
            "label": "Test",
            "ds_type": "csv",
            "connection_info": os.path.join(FIXTURES, "books.csv"),
            "description": None,
            "mappings": [
                {
                    "mapping_iri": "http://example.org/m1",
                    "target_class": BOOK_CLASS,
                    "identifier_field": "isbn",
                    "label": None,
                    "property_mappings": [],
                }
            ],
        }

        import services.datasource_import as sdi
        with patch.object(sdi, "get_datasource", return_value=ds_info), \
             patch.object(sdi, "sparql_update"):
            result = import_datasource(DATASET, GRAPH, DS_IRI)

        assert result.graph == GRAPH


# ── S7: 빈 트리플 ─────────────────────────────────────────────────────────────

class TestS7EmptyTriples:
    def test_no_insert_on_empty(self):
        """매핑은 있지만 identifier_field 가 없어 트리플이 0개인 경우."""
        ds_info = {
            "datasource_iri": DS_IRI,
            "label": "Empty",
            "ds_type": "csv",
            "connection_info": os.path.join(FIXTURES, "books.csv"),
            "description": None,
            "mappings": [
                {
                    "mapping_iri": "http://example.org/m1",
                    "target_class": BOOK_CLASS,
                    "identifier_field": "nonexistent_pk",  # 존재하지 않는 필드
                    "label": None,
                    "property_mappings": [],
                }
            ],
        }

        import services.datasource_import as sdi
        with patch.object(sdi, "get_datasource", return_value=ds_info), \
             patch.object(sdi, "sparql_update") as mock_update:
            result = import_datasource(DATASET, GRAPH, DS_IRI)

        assert result.imported_individuals == 0
        assert result.inserted_triples == 0
        # 트리플이 없으면 sparql_update 호출 없음
        mock_update.assert_not_called()


# ── S8: importer 예외 → result.errors ────────────────────────────────────────

class TestS8ImporterException:
    def test_importer_error_captured(self):
        """importer.generate_triples() 예외 → result.errors 에 기록."""
        ds_info = {
            "datasource_iri": DS_IRI,
            "label": "Bad",
            "ds_type": "csv",
            "connection_info": "/nonexistent/path/to/file.csv",  # 없는 파일
            "description": None,
            "mappings": [
                {
                    "mapping_iri": "http://example.org/m1",
                    "target_class": BOOK_CLASS,
                    "identifier_field": "isbn",
                    "label": None,
                    "property_mappings": [],
                }
            ],
        }

        import services.datasource_import as sdi
        with patch.object(sdi, "get_datasource", return_value=ds_info), \
             patch.object(sdi, "sparql_update"):
            result = import_datasource(DATASET, GRAPH, DS_IRI)

        assert len(result.errors) >= 1
        assert result.imported_individuals == 0


# ── S9: ImportResult 기본값 ───────────────────────────────────────────────────

class TestS9ImportResultDefaults:
    def test_defaults(self):
        r = ImportResult()
        assert r.imported_individuals == 0
        assert r.inserted_triples == 0
        assert r.skipped_rows == 0
        assert r.errors == []
        assert r.graph == ""


# ── S10 & S11: FastAPI 엔드포인트 ─────────────────────────────────────────────

try:
    from fastapi.testclient import TestClient
    from main import app
    HAS_FASTAPI = True
except Exception:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI 앱 임포트 불가")
class TestS10ImportEndpoint:
    def test_import_endpoint_success(self):
        """POST /api/datasources/{iri}/import → 200 + ImportResult."""
        from fastapi.testclient import TestClient
        from main import app

        mock_result = ImportResult(
            imported_individuals=5,
            inserted_triples=10,
            skipped_rows=0,
            errors=[],
            graph=GRAPH,
        )

        with patch("routers.datasources.import_datasource", return_value=mock_result):
            client = TestClient(app)
            encoded_iri = DS_IRI.replace("/", "%2F").replace(":", "%3A")
            resp = client.post(
                f"/api/datasources/{encoded_iri}/import",
                params={"dataset": DATASET, "graph": GRAPH},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["imported_individuals"] == 5
        assert data["inserted_triples"] == 10
        assert data["errors"] == []

    def test_import_endpoint_with_errors(self):
        """오류가 있는 Import 결과도 200 반환."""
        from fastapi.testclient import TestClient
        from main import app

        mock_result = ImportResult(
            imported_individuals=3,
            inserted_triples=6,
            skipped_rows=2,
            errors=["batch 0 실패"],
            graph=GRAPH,
        )

        with patch("routers.datasources.import_datasource", return_value=mock_result):
            client = TestClient(app)
            encoded_iri = DS_IRI.replace("/", "%2F").replace(":", "%3A")
            resp = client.post(
                f"/api/datasources/{encoded_iri}/import",
                params={"dataset": DATASET, "graph": GRAPH},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["skipped_rows"] == 2
        assert len(data["errors"]) == 1


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI 앱 임포트 불가")
class TestS11ImportEndpoint404:
    def test_not_found_datasource(self):
        """존재하지 않는 ds_iri → 404."""
        from fastapi.testclient import TestClient
        from main import app

        with patch("routers.datasources.import_datasource", side_effect=KeyError("not found")):
            client = TestClient(app)
            encoded_iri = "http%3A%2F%2Fexample.org%2Fnonexistent"
            resp = client.post(
                f"/api/datasources/{encoded_iri}/import",
                params={"dataset": DATASET, "graph": GRAPH},
            )

        assert resp.status_code == 404
