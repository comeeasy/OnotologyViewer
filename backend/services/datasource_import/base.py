"""
v05 — Datasource Import Engine: 기반 타입 및 추상 클래스

설계 원칙:
- AbstractImporter: fetch_rows() 구현 + generate_triples() 공통 로직
- 기존 services/datasources.py 에 일절 의존하지 않음 (독립 모듈)
- Triple 은 불변 dataclass; predicate/object 는 IRI 또는 literal
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# ── XSD 상수 ──────────────────────────────────────────────────────────────────

XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE    = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS_LABEL  = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_PK_SAFE_RE = re.compile(r"[^A-Za-z0-9_\-]")  # 허용: 알파벳, 숫자, _, -


# ── 데이터 클래스 ──────────────────────────────────────────────────────────────

@dataclass
class Triple:
    """RDF 트리플 표현.

    is_literal=False → object 는 IRI
    is_literal=True  → object 는 리터럴 (datatype 필수)
    """
    subject: str
    predicate: str
    object: str
    datatype: str | None = None   # is_literal=True 일 때 XSD datatype IRI
    is_literal: bool = False


@dataclass
class PropMappingConfig:
    """소스 필드 → 온톨로지 프로퍼티 매핑."""
    source_field: str       # CSV 컬럼명 or JSON key (dot notation 지원)
    target_property: str    # owl:DatatypeProperty or owl:ObjectProperty IRI


@dataclass
class ClassMappingConfig:
    """소스 데이터셋 → 온톨로지 클래스 매핑."""
    target_class: str               # owl:Class IRI
    identifier_field: str           # PK 필드명 (IRI 생성에 사용)
    property_mappings: list[PropMappingConfig] = field(default_factory=list)
    # JSON/REST 전용: 배열 진입점 JSONPath (ex. "$.books[*]")
    json_path: str = ""
    # RDB 전용: 커스텀 SQL 쿼리 (없으면 connection_info 의 query 사용)
    sql_query: str = ""
    # rdfs:label / rdfs:comment 자동 생성 소스 필드 (빈 문자열이면 생략)
    label_field: str = ""
    comment_field: str = ""


@dataclass
class ImporterConfig:
    """Importer 초기화에 필요한 모든 설정."""
    connection_info: str                       # 파일 경로, URL, JSON 문자열
    mappings: list[ClassMappingConfig] = field(default_factory=list)


# ── 유틸 함수 ──────────────────────────────────────────────────────────────────

def make_pk_safe(pk_value: str) -> str:
    """PK 값을 IRI-safe 문자열로 변환 (알파벳·숫자·_·- 외 → _)."""
    return _PK_SAFE_RE.sub("_", pk_value)


def infer_xsd_type(value: str) -> tuple[str, str]:
    """문자열 값에서 XSD 데이터타입을 추론.

    Returns:
        (datatype_iri, normalized_value)
    """
    stripped = value.strip()

    # Boolean
    if stripped.lower() in ("true", "false"):
        return f"{XSD}boolean", stripped.lower()

    # Integer (소수점 없는 정수)
    try:
        int(stripped)
        return f"{XSD}integer", stripped
    except ValueError:
        pass

    # Decimal (소수점 포함 실수)
    try:
        float(stripped)
        return f"{XSD}decimal", stripped
    except ValueError:
        pass

    # ISO dateTime (2024-01-15T...)
    if _ISO_DATETIME_RE.match(stripped):
        return f"{XSD}dateTime", stripped

    # ISO date (2024-01-15)
    if _ISO_DATE_RE.match(stripped):
        return f"{XSD}date", stripped

    # 기본값: string
    return f"{XSD}string", stripped


def get_nested_value(row: dict, field_path: str) -> Any:
    """점(.) 구분 경로로 중첩 dict에서 값을 추출.

    예: "meta.year" → row["meta"]["year"]
    JSONPath 표기($.)는 jsonpath-ng 를 사용하는 JsonImporter에서 처리.
    """
    parts = field_path.split(".")
    val: Any = row
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


# ── Abstract Base ──────────────────────────────────────────────────────────────

class AbstractImporter(ABC):
    """모든 Importer가 구현해야 할 기반 클래스.

    서브클래스 구현 의무:
      - fetch_rows() : 소스에서 raw 딕셔너리 목록을 가져온다.

    선택적 오버라이드:
      - fetch_rows_for_mapping(mapping) : 매핑별 row 필터링 (JSON/REST 전용).
    """

    def __init__(self, config: ImporterConfig) -> None:
        self.config = config

    @abstractmethod
    def fetch_rows(self) -> list[dict]:
        """소스에서 모든 레코드를 list[dict] 형태로 반환."""
        ...

    def fetch_rows_for_mapping(self, mapping: ClassMappingConfig) -> list[dict]:
        """특정 ClassMapping에 사용할 rows를 반환.

        기본 구현: 전체 rows 반환 (CSV/RDB 에 적합).
        JSON/REST 는 json_path를 적용하여 오버라이드.
        """
        return self.fetch_rows()

    # ── 트리플 생성 ──────────────────────────────────────────────────────────

    def generate_triples(self) -> list[Triple]:
        """모든 ClassMapping을 적용하여 RDF 트리플 목록 생성."""
        result: list[Triple] = []
        for mapping in self.config.mappings:
            rows = self.fetch_rows_for_mapping(mapping)
            result.extend(self._apply_mapping(rows, mapping))
        return result

    def _make_label_comment_triples(
        self,
        individual_iri: str,
        row: dict,
        mapping: ClassMappingConfig,
        get_val_fn=None,
    ) -> list[Triple]:
        """rdfs:label / rdfs:comment 트리플 생성 헬퍼.

        get_val_fn: (row, field_path) → value   (기본: get_nested_value)
        """
        if get_val_fn is None:
            get_val_fn = get_nested_value
        result: list[Triple] = []

        if mapping.label_field:
            val = get_val_fn(row, mapping.label_field)
            if val is not None and str(val).strip():
                result.append(Triple(
                    subject=individual_iri,
                    predicate=RDFS_LABEL,
                    object=str(val).strip(),
                    datatype=f"{XSD}string",
                    is_literal=True,
                ))

        if mapping.comment_field:
            val = get_val_fn(row, mapping.comment_field)
            if val is not None and str(val).strip():
                result.append(Triple(
                    subject=individual_iri,
                    predicate=RDFS_COMMENT,
                    object=str(val).strip(),
                    datatype=f"{XSD}string",
                    is_literal=True,
                ))

        return result

    def _apply_mapping(
        self, rows: list[dict], mapping: ClassMappingConfig
    ) -> list[Triple]:
        """하나의 ClassMapping을 rows에 적용 → Triple 목록 반환.

        중복 PK 처리: last-wins (upsert).
        빈 값 처리: None 또는 빈 문자열 필드는 트리플 생략.
        """
        # 1) PK 기준 dedup (last-wins)
        pk_to_row: dict[str, dict] = {}
        for row in rows:
            raw_pk = row.get(mapping.identifier_field)
            if raw_pk is None or str(raw_pk).strip() == "":
                continue  # PK 없는 행 스킵
            pk_safe = make_pk_safe(str(raw_pk))
            pk_to_row[pk_safe] = row  # 마지막 행으로 덮어씀

        # 2) 트리플 생성
        triples: list[Triple] = []
        for pk_safe, row in pk_to_row.items():
            individual_iri = f"{mapping.target_class}_{pk_safe}"

            # rdf:type 트리플
            triples.append(Triple(
                subject=individual_iri,
                predicate=RDF_TYPE,
                object=mapping.target_class,
                is_literal=False,
            ))

            # rdfs:label / rdfs:comment 자동 생성
            triples.extend(self._make_label_comment_triples(individual_iri, row, mapping))

            # PropertyMapping 트리플
            for pm in mapping.property_mappings:
                raw_val = get_nested_value(row, pm.source_field)
                if raw_val is None or str(raw_val).strip() == "":
                    continue  # 빈 값 스킵
                datatype, normalized = infer_xsd_type(str(raw_val))
                triples.append(Triple(
                    subject=individual_iri,
                    predicate=pm.target_property,
                    object=normalized,
                    datatype=datatype,
                    is_literal=True,
                ))

        return triples

    # ── SPARQL 변환 ───────────────────────────────────────────────────────────

    def triples_to_sparql_insert(self, triples: list[Triple], graph_iri: str) -> str:
        """Triple 목록을 SPARQL INSERT DATA 문으로 변환.

        대용량 대비 청크 분할은 호출자 책임.
        """
        lines: list[str] = []
        for t in triples:
            if t.is_literal:
                escaped = t.object.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                lines.append(f'  <{t.subject}> <{t.predicate}> "{escaped}"^^<{t.datatype}> .')
            else:
                lines.append(f"  <{t.subject}> <{t.predicate}> <{t.object}> .")
        body = "\n".join(lines)
        return f"INSERT DATA {{\n  GRAPH <{graph_iri}> {{\n{body}\n  }}\n}}"
