"""
v05 — RDB Importer

connection_info: JSON 문자열
{
  "dialect": "sqlite",        // sqlite | postgresql | mysql
  "url": "sqlite:///path/to/db.sqlite",
  "query": "SELECT * FROM books"  // 글로벌 쿼리 (ClassMapping.sql_query 가 있으면 무시)
}

지원 dialect:
  - sqlite     (표준 sqlalchemy + 내장 드라이버)
  - postgresql (psycopg2-binary 필요)
  - mysql      (pymysql 필요)
"""

from __future__ import annotations

import json
from typing import Any

try:
    from sqlalchemy import create_engine, text  # type: ignore
except ImportError:  # pragma: no cover
    create_engine = None  # type: ignore
    text = None  # type: ignore

from .base import AbstractImporter, ImporterConfig, ClassMappingConfig, Triple, RDF_TYPE, make_pk_safe, infer_xsd_type


class ImportError(Exception):
    """RDB 연결/쿼리 실패 시 발생."""


_SUPPORTED_DIALECTS = {"sqlite", "postgresql", "mysql"}


class RdbImporter(AbstractImporter):
    """관계형 DB 소스를 읽어 Triple 목록을 생성."""

    def __init__(self, config: ImporterConfig) -> None:
        super().__init__(config)
        try:
            self._conn: dict = json.loads(config.connection_info)
        except (json.JSONDecodeError, TypeError):
            self._conn = {}

    # ── dialect 검증 ───────────────────────────────────────────────────────────

    def _validate_dialect(self) -> str:
        dialect = self._conn.get("dialect", "").lower()
        if dialect not in _SUPPORTED_DIALECTS:
            raise ImportError(
                f"지원하지 않는 dialect: '{dialect}'. "
                f"지원 목록: {sorted(_SUPPORTED_DIALECTS)}"
            )
        return dialect

    # ── 엔진 생성 ──────────────────────────────────────────────────────────────

    def _create_engine(self):
        if create_engine is None:  # pragma: no cover
            raise ImportError("sqlalchemy is required. pip install sqlalchemy")
        self._validate_dialect()
        url = self._conn.get("url", "")
        if not url:
            raise ImportError("connection_info에 'url' 필드가 없습니다.")
        try:
            return create_engine(url)
        except Exception as e:
            raise ImportError(f"DB 연결 실패: {e}") from e

    # ── 쿼리 실행 ──────────────────────────────────────────────────────────────

    def _run_query(self, query: str) -> list[dict]:
        """SQL 쿼리를 실행하고 dict 목록을 반환."""
        engine = self._create_engine()
        try:
            with engine.connect() as conn:
                result = conn.execute(text(query))
                columns = list(result.keys())
                rows = []
                for row in result.fetchall():
                    rows.append(dict(zip(columns, row)))
                return rows
        except ImportError:
            raise
        except Exception as e:
            raise ImportError(f"쿼리 실행 실패: {e}") from e

    # ── 공개 인터페이스 ────────────────────────────────────────────────────────

    def fetch_rows(self) -> list[dict]:
        """글로벌 query로 모든 행을 가져온다."""
        self._validate_dialect()  # dialect 먼저 검증
        query = self._conn.get("query", "")
        if not query:
            raise ImportError("connection_info에 'query' 필드가 없습니다.")
        return self._run_query(query)

    def fetch_rows_for_mapping(self, mapping: ClassMappingConfig) -> list[dict]:
        """ClassMapping.sql_query 가 있으면 그 쿼리를, 없으면 글로벌 query를 사용."""
        if mapping.sql_query:
            return self._run_query(mapping.sql_query)
        return self.fetch_rows()

    def generate_triples(self) -> list[Triple]:
        """모든 ClassMapping에 대해 트리플을 생성."""
        all_triples: list[Triple] = []
        for mapping in self.config.mappings:
            rows = self.fetch_rows_for_mapping(mapping)
            all_triples.extend(self._apply_mapping(rows, mapping))
        return all_triples

    # ── 매핑 적용 ─────────────────────────────────────────────────────────────

    def _apply_mapping(self, rows: list[dict], mapping: ClassMappingConfig) -> list[Triple]:
        """행 목록에서 Triple 목록을 생성 (NULL 스킵, last-wins 중복 제거)."""
        pk_to_row: dict[str, dict] = {}
        for row in rows:
            raw_pk = row.get(mapping.identifier_field)
            if raw_pk is None or str(raw_pk).strip() == "":
                continue
            pk_safe = make_pk_safe(str(raw_pk))
            pk_to_row[pk_safe] = row

        triples: list[Triple] = []
        for pk_safe, row in pk_to_row.items():
            individual_iri = f"{mapping.target_class}_{pk_safe}"
            triples.append(Triple(
                subject=individual_iri,
                predicate=RDF_TYPE,
                object=mapping.target_class,
                is_literal=False,
            ))
            # rdfs:label / rdfs:comment (label_field 지정 시)
            triples.extend(self._make_label_comment_triples(
                individual_iri, row, mapping,
                get_val_fn=lambda r, f: r.get(f),
            ))
            for pm in mapping.property_mappings:
                raw_val = row.get(pm.source_field)
                if raw_val is None or str(raw_val).strip() == "":
                    continue
                datatype, normalized = infer_xsd_type(str(raw_val))
                triples.append(Triple(
                    subject=individual_iri,
                    predicate=pm.target_property,
                    object=normalized,
                    datatype=datatype,
                    is_literal=True,
                ))
        return triples
