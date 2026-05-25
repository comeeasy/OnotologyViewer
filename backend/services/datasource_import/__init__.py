"""
v05 — Datasource Import Engine

진입점: import_datasource(dataset, graph, ds_iri) → ImportResult
각 Importer는 AbstractImporter 를 구현.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .base import AbstractImporter, ImporterConfig, Triple, ClassMappingConfig, PropMappingConfig

# 모듈 레벨 import — 테스트에서 patch 가능
try:
    from services.datasources import get_datasource
    from fuseki.sparql import update as sparql_update
except ImportError:  # pragma: no cover — Fuseki 없는 환경(단위 테스트)
    get_datasource = None  # type: ignore
    sparql_update = None   # type: ignore


@dataclass
class ImportResult:
    """Import 실행 결과 요약."""
    imported_individuals: int = 0
    inserted_triples: int = 0
    skipped_rows: int = 0
    errors: list[str] = field(default_factory=list)
    graph: str = ""


def get_importer(ds_type: str, config: ImporterConfig) -> AbstractImporter:
    """ds_type 에 맞는 Importer 인스턴스를 반환."""
    if ds_type == "csv":
        from .csv_importer import CsvImporter
        return CsvImporter(config)
    elif ds_type == "json":
        from .json_importer import JsonImporter
        return JsonImporter(config)
    elif ds_type == "rest":
        from .rest_importer import RestImporter
        return RestImporter(config)
    elif ds_type == "rdb":
        from .rdb_importer import RdbImporter
        return RdbImporter(config)
    else:
        raise ValueError(f"지원하지 않는 datasource 유형: {ds_type!r}")


def import_datasource(
    dataset: str,
    graph: str,
    ds_iri: str,
    *,
    batch_size: int = 500,
) -> ImportResult:
    """
    Fuseki 에서 Datasource 매핑 정보를 읽어 Import 실행.

    Args:
        dataset: Fuseki dataset 이름
        graph:   Named Graph IRI
        ds_iri:  Datasource IRI
        batch_size: INSERT DATA 당 트리플 수 (대용량 처리용)

    Returns:
        ImportResult
    """
    # 1) Datasource 설정 로드 (기존 서비스 사용)
    ds_info = get_datasource(dataset, graph, ds_iri)

    # 2) ImporterConfig 구성 (Fuseki 매핑 → dataclass 변환)
    mappings: list[ClassMappingConfig] = []
    for m in ds_info.get("mappings", []):
        prop_mappings = [
            PropMappingConfig(
                source_field=pm["source_field"],
                target_property=pm["target_property"],
            )
            for pm in m.get("property_mappings", [])
        ]
        mappings.append(ClassMappingConfig(
            target_class=m["target_class"],
            identifier_field=m["identifier_field"],
            property_mappings=prop_mappings,
            label_field=m.get("label_field", ""),
            comment_field=m.get("comment_field", ""),
        ))

    config = ImporterConfig(
        connection_info=ds_info["connection_info"],
        mappings=mappings,
    )

    # 3) Importer 선택 및 트리플 생성
    result = ImportResult(graph=graph)
    importer = get_importer(ds_info["ds_type"], config)

    try:
        triples = importer.generate_triples()
    except Exception as exc:
        result.errors.append(f"데이터 읽기 실패: {exc}")
        return result

    if not triples:
        return result

    # 4) Individual별 upsert (DELETE + INSERT)
    #    같은 subject 묶음 단위로 처리
    by_subject: dict[str, list[Triple]] = defaultdict(list)
    for t in triples:
        by_subject[t.subject].append(t)

    result.imported_individuals = len(by_subject)

    # 5) DELETE 기존 트리플 (upsert = 덮어쓰기)
    for subj in by_subject:
        try:
            sparql_update(dataset, f"""
            DELETE WHERE {{
              GRAPH <{graph}> {{
                <{subj}> ?p ?o .
              }}
            }}
            """)
        except Exception as exc:
            result.errors.append(f"DELETE 실패 ({subj}): {exc}")

    # 6) INSERT DATA (배치 처리)
    all_triples = triples
    for i in range(0, len(all_triples), batch_size):
        chunk = all_triples[i: i + batch_size]
        sparql_stmt = importer.triples_to_sparql_insert(chunk, graph)
        try:
            sparql_update(dataset, sparql_stmt)
            result.inserted_triples += len(chunk)
        except Exception as exc:
            result.errors.append(f"INSERT 실패 (batch {i // batch_size}): {exc}")

    return result
