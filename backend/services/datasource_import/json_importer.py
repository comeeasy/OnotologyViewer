"""
v05 — JSON Importer

지원:
- 로컬 파일 경로 (UTF-8)
- HTTP/HTTPS URL (httpx 사용)
- JSONPath 배열 추출 (jsonpath-ng 사용, 없으면 단순 경로 파서 폴백)
- dot notation 중첩 필드 접근 (base.get_nested_value)
- null/missing 값 자동 스킵
"""

from __future__ import annotations

import json
from typing import Any

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

from .base import AbstractImporter, ImporterConfig, ClassMappingConfig


def _apply_jsonpath(data: Any, path: str) -> list:
    """JSONPath 표현식을 data에 적용하여 매칭된 값 목록 반환.

    jsonpath-ng 가 있으면 사용, 없으면 단순 경로 파서 폴백.
    경로가 없으면 data 자체(배열 or 단일 객체)를 반환.
    """
    if not path:
        # 경로 없음: data가 배열이면 배열 반환, dict면 [dict]
        if isinstance(data, list):
            return data
        return [data]

    try:
        from jsonpath_ng import parse as jp_parse  # type: ignore
        expr = jp_parse(path)
        return [m.value for m in expr.find(data)]
    except ImportError:
        pass

    # 폴백: 단순 경로 파서 (점 구분 + [*] 배열 전개)
    return _simple_path(data, path)


def _simple_path(data: Any, path: str) -> list:
    """jsonpath-ng 없이 사용하는 단순 경로 파서.

    지원:
      $.key.subkey[*]  →  data["key"]["subkey"] (배열 전개)
      key.subkey       →  data["key"]["subkey"]
    """
    # $ 제거
    p = path.lstrip("$").lstrip(".")
    # [*] 배열 인덱서 처리
    p = p.replace("[*]", "")

    parts = [seg for seg in p.split(".") if seg]
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            current = [item.get(part) if isinstance(item, dict) else None for item in current]
        else:
            return []
        if current is None:
            return []

    if isinstance(current, list):
        return current
    return [current]


class JsonImporter(AbstractImporter):
    """JSON 소스 (로컬 파일 또는 URL) 를 읽어 Triple 목록을 생성.

    - ClassMappingConfig.json_path 가 있으면 JSONPath로 배열 추출
    - 없으면 최상위 배열 or dict 의 첫 번째 배열 값 사용
    """

    def __init__(self, config: ImporterConfig) -> None:
        super().__init__(config)
        self._cache: Any = None  # JSON 파싱 결과 캐시

    def _load_raw(self) -> Any:
        """JSON 문서 전체를 파싱하여 반환 (캐시 적용)."""
        if self._cache is not None:
            return self._cache
        conn = self.config.connection_info
        if conn.startswith(("http://", "https://")):
            if httpx is None:  # pragma: no cover
                raise ImportError("httpx is required for URL sources.")
            resp = httpx.get(conn, timeout=10, follow_redirects=True)
            resp.raise_for_status()
            self._cache = resp.json()
        else:
            with open(conn, encoding="utf-8") as f:
                self._cache = json.load(f)
        return self._cache

    def fetch_rows(self) -> list[dict]:
        """json_path 없을 때 기본 fetch: 최상위 배열 or dict 의 첫 번째 배열."""
        data = self._load_raw()
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            # 첫 번째 리스트 값 반환
            for v in data.values():
                if isinstance(v, list):
                    return [r for r in v if isinstance(r, dict)]
            return [data]
        return []

    def fetch_rows_for_mapping(self, mapping: ClassMappingConfig) -> list[dict]:
        """ClassMapping.json_path 가 있으면 해당 경로의 배열 반환."""
        data = self._load_raw()
        if mapping.json_path:
            matched = _apply_jsonpath(data, mapping.json_path)
            return [r for r in matched if isinstance(r, dict)]
        return self.fetch_rows()

    def _get_field_value_extended(self, row: dict, field_path: str):
        """dot notation + list value 처리.

        배열 값이면 첫 번째 요소를 문자열로 반환 (S8 시나리오).
        """
        from .base import get_nested_value
        val = get_nested_value(row, field_path)
        if isinstance(val, list):
            # 배열 → 첫 번째 요소 or 직렬화
            return val[0] if val else None
        return val

    def _apply_mapping(self, rows, mapping):
        """base._apply_mapping 을 오버라이드하여 확장 필드 추출 지원."""
        from .base import Triple, RDF_TYPE, make_pk_safe, infer_xsd_type

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
                get_val_fn=lambda r, f: self._get_field_value_extended(r, f),
            ))
            for pm in mapping.property_mappings:
                raw_val = self._get_field_value_extended(row, pm.source_field)
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
