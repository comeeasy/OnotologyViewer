"""Class CRUD 서비스 — SPARQL 기반."""

from fuseki.sparql import query as sparql_query, update as sparql_update
from services.iri import generate_iri

# ────────────────────────────────────────────────
# 유틸
# ────────────────────────────────────────────────

def _esc(s: str) -> str:
    """SPARQL 문자열 리터럴 안전 이스케이프."""
    return (
        s.replace("\\", "\\\\")
         .replace('"',  '\\"')
         .replace("\n", "\\n")
         .replace("\r", "\\r")
         .replace("\t", "\\t")
    )


def _validate_iri(iri: str) -> str:
    """IRI 기본 검증 (SPARQL 인젝션 방지)."""
    if not (iri.startswith("http://") or iri.startswith("https://")):
        raise ValueError(f"IRI는 http(s)://로 시작해야 합니다: {iri!r}")
    for ch in ('"', "\\", "\n", "\r", "\t"):
        if ch in iri:
            raise ValueError(f"IRI에 허용되지 않는 문자가 포함되어 있습니다: {iri!r}")
    return iri


# ────────────────────────────────────────────────
# SPARQL 템플릿
# ────────────────────────────────────────────────

_Q_LIST = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?_g ?class ?label ?comment WHERE {{
  {graph_values}
  GRAPH ?_g {{
    ?class a owl:Class .
    OPTIONAL {{ ?class rdfs:label ?label }}
    OPTIONAL {{ ?class rdfs:comment ?comment }}
    FILTER({ns_filter})
  }}
}}
"""

_Q_SUPER_CLASSES = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?super WHERE {{
  GRAPH <{graph}> {{
    <{class_iri}> rdfs:subClassOf ?super .
    FILTER(isIRI(?super))
  }}
}}
"""

_Q_SUB_CLASSES = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?sub WHERE {{
  GRAPH <{graph}> {{
    ?sub rdfs:subClassOf <{class_iri}> .
    FILTER(isIRI(?sub))
  }}
}}
"""

_Q_OBJECT_PROPS = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?prop ?label ?role WHERE {{
  GRAPH <{graph}> {{
    ?prop a owl:ObjectProperty .
    OPTIONAL {{ ?prop rdfs:label ?label }}
    {{
      ?prop rdfs:domain <{class_iri}> .
      BIND("domain" AS ?role)
    }} UNION {{
      ?prop rdfs:range <{class_iri}> .
      BIND("range" AS ?role)
    }}
  }}
}}
"""

_Q_DATA_PROPS = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?prop ?label ?range WHERE {{
  GRAPH <{graph}> {{
    ?prop a owl:DatatypeProperty ;
          rdfs:domain <{class_iri}> .
    OPTIONAL {{ ?prop rdfs:label ?label }}
    OPTIONAL {{ ?prop rdfs:range ?range }}
  }}
}}
"""

_Q_INDIVIDUAL_COUNT = """
SELECT (COUNT(?ind) AS ?count) WHERE {{
  GRAPH <{graph}> {{
    ?ind a <{class_iri}> .
  }}
}}
"""

_Q_CLASS_BASE = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label ?comment WHERE {{
  GRAPH <{graph}> {{
    <{class_iri}> a owl:Class .
    OPTIONAL {{ <{class_iri}> rdfs:label ?label }}
    OPTIONAL {{ <{class_iri}> rdfs:comment ?comment }}
  }}
}}
"""

_U_INSERT = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

INSERT DATA {{
  GRAPH <{graph}> {{
    <{class_iri}> a owl:Class ;
      rdfs:label   "{label}" ;
      rdfs:comment "{comment}" .
  }}
}}
"""

_U_UPDATE_LABEL = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

DELETE {{ GRAPH <{graph}> {{ <{class_iri}> rdfs:label ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{class_iri}> rdfs:label "{value}" }} }}
WHERE  {{ GRAPH <{graph}> {{ <{class_iri}> a <http://www.w3.org/2002/07/owl#Class> .
                              OPTIONAL {{ <{class_iri}> rdfs:label ?v }} }} }}
"""

_U_UPDATE_COMMENT = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

DELETE {{ GRAPH <{graph}> {{ <{class_iri}> rdfs:comment ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{class_iri}> rdfs:comment "{value}" }} }}
WHERE  {{ GRAPH <{graph}> {{ <{class_iri}> a <http://www.w3.org/2002/07/owl#Class> .
                              OPTIONAL {{ <{class_iri}> rdfs:comment ?v }} }} }}
"""

# Delete — 3단계
# 1) Individual 아웃고잉 트리플 삭제
_U_DEL_IND_OUTGOING = """
DELETE {{ GRAPH <{graph}> {{ ?ind ?p ?o }} }}
WHERE  {{ GRAPH <{graph}> {{ ?ind a <{class_iri}> . ?ind ?p ?o . }} }}
"""
# 2) Individual 인커밍 트리플 삭제 (먼저 outgoing을 지우면 rdf:type도 없어지므로 별도 보관)
_U_DEL_IND_INCOMING = """
DELETE {{ GRAPH <{graph}> {{ ?s ?p ?ind }} }}
WHERE  {{ GRAPH <{graph}> {{ ?ind a <{class_iri}> . ?s ?p ?ind . }} }}
"""
# 3) domain / range 참조 제거
_U_DEL_DOMAIN_RANGE = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

DELETE {{
  GRAPH <{graph}> {{
    ?prop rdfs:domain <{class_iri}> .
    ?prop rdfs:range  <{class_iri}> .
  }}
}}
WHERE {{
  GRAPH <{graph}> {{
    {{ ?prop rdfs:domain <{class_iri}> }}
    UNION
    {{ ?prop rdfs:range  <{class_iri}> }}
  }}
}}
"""
# 4) Class 선언 삭제
_U_DEL_CLASS = """
DELETE WHERE {{ GRAPH <{graph}> {{ <{class_iri}> ?p ?o }} }}
"""


# subClassOf 편집 (v02-D)
_Q_IS_DESCENDANT = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
ASK {{
  GRAPH <{graph}> {{
    <{candidate_desc}> rdfs:subClassOf+ <{ancestor}> .
  }}
}}
"""

_U_INS_SUBCLASSOF = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
INSERT DATA {{
  GRAPH <{graph}> {{
    <{child}> rdfs:subClassOf <{parent}> .
  }}
}}
"""

_U_DEL_SUBCLASSOF = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE DATA {{
  GRAPH <{graph}> {{
    <{child}> rdfs:subClassOf <{parent}> .
  }}
}}
"""


# ────────────────────────────────────────────────
# 공개 함수
# ────────────────────────────────────────────────

def _ns_filter(namespaces: list[str]) -> str:
    """SPARQL FILTER 조건 생성: 하나 이상의 namespace STRSTARTS OR 조건."""
    conditions = [f'STRSTARTS(str(?class), "{ns}")' for ns in namespaces]
    return " || ".join(conditions)


def graph_values_clause(graphs: list[str]) -> str:
    """여러 Named Graph를 위한 SPARQL VALUES 절 생성.

    Returns:
        'VALUES ?_g { <g1> <g2> ... }' — 단일 그래프도 같은 형식 사용
    """
    vals = " ".join(f"<{g}>" for g in graphs)
    return f"VALUES ?_g {{ {vals} }}"


def list_classes(dataset: str, graphs: str | list[str], namespace: str | list[str]) -> list[dict]:
    """OOI 범위 내 Class 목록 반환.

    graphs: Named Graph IRI 하나 또는 목록 (복수 그래프 지원)
    namespace: Namespace base IRI 하나 또는 목록
    """
    graph_list = [graphs] if isinstance(graphs, str) else list(graphs)
    for g in graph_list:
        _validate_iri(g)
    ns_list = [namespace] if isinstance(namespace, str) else list(namespace)
    if not ns_list:
        raise ValueError("namespace는 하나 이상 제공해야 합니다.")
    for ns in ns_list:
        _validate_iri(ns)
    rows = sparql_query(dataset, _Q_LIST.format(
        graph_values=graph_values_clause(graph_list),
        ns_filter=_ns_filter(ns_list),
    ))
    return [
        {
            "source_graph": r.get("_g"),
            "iri":          r["class"],
            "label":        r.get("label"),
            "comment":      r.get("comment"),
        }
        for r in rows
    ]


def get_class_detail(dataset: str, graph: str, class_iri: str) -> dict | None:
    """
    Class 상세 정보 반환.
    - label, comment
    - super_classes / sub_classes (rdfs:subClassOf 계층)
    - object_properties (domain 또는 range)
    - data_properties (domain)
    - individual_count
    """
    _validate_iri(graph)
    _validate_iri(class_iri)

    base = sparql_query(dataset, _Q_CLASS_BASE.format(graph=graph, class_iri=class_iri))
    if not base:
        return None

    row = base[0]

    supers = [r["super"] for r in sparql_query(dataset, _Q_SUPER_CLASSES.format(graph=graph, class_iri=class_iri))]
    subs   = [r["sub"]   for r in sparql_query(dataset, _Q_SUB_CLASSES.format(graph=graph, class_iri=class_iri))]

    obj_props = [
        {"iri": r["prop"], "label": r.get("label"), "role": r["role"]}
        for r in sparql_query(dataset, _Q_OBJECT_PROPS.format(graph=graph, class_iri=class_iri))
    ]

    data_props = [
        {"iri": r["prop"], "label": r.get("label"), "range": r.get("range")}
        for r in sparql_query(dataset, _Q_DATA_PROPS.format(graph=graph, class_iri=class_iri))
    ]

    count_rows = sparql_query(dataset, _Q_INDIVIDUAL_COUNT.format(graph=graph, class_iri=class_iri))
    individual_count = int(count_rows[0]["count"]) if count_rows else 0

    return {
        "iri":              class_iri,
        "label":            row.get("label"),
        "comment":          row.get("comment"),
        "super_classes":    supers,
        "sub_classes":      subs,
        "object_properties": obj_props,
        "data_properties":  data_props,
        "individual_count": individual_count,
    }


def create_class(dataset: str, graph: str, namespace: str, label: str, comment: str) -> str:
    """Class를 생성하고 신규 IRI를 반환한다."""
    _validate_iri(graph)
    _validate_iri(namespace)

    class_iri = generate_iri(namespace, label, graph)
    sparql_update(
        dataset,
        _U_INSERT.format(
            graph=graph,
            class_iri=class_iri,
            label=_esc(label),
            comment=_esc(comment),
        ),
    )
    return class_iri


def update_class(
    dataset: str,
    graph: str,
    class_iri: str,
    label: str | None = None,
    comment: str | None = None,
) -> None:
    """label / comment 중 제공된 필드만 업데이트한다."""
    _validate_iri(graph)
    _validate_iri(class_iri)

    if label is None and comment is None:
        raise ValueError("label 또는 comment 중 하나 이상을 제공해야 합니다.")

    if label is not None:
        sparql_update(
            dataset,
            _U_UPDATE_LABEL.format(graph=graph, class_iri=class_iri, value=_esc(label)),
        )
    if comment is not None:
        sparql_update(
            dataset,
            _U_UPDATE_COMMENT.format(graph=graph, class_iri=class_iri, value=_esc(comment)),
        )


def _class_exists(dataset: str, graph: str, class_iri: str) -> bool:
    rows = sparql_query(dataset, _Q_CLASS_BASE.format(graph=graph, class_iri=class_iri))
    return bool(rows)


def _is_descendant(dataset: str, graph: str, candidate_desc: str, ancestor: str) -> bool:
    """candidate_desc 가 ancestor 의 직접/간접 하위 클래스인지 확인."""
    from fuseki.sparql import query as _q
    from SPARQLWrapper import JSON, SPARQLWrapper
    import config_state
    # ASK 쿼리 직접 실행
    sparql_str = _Q_IS_DESCENDANT.format(
        graph=graph, candidate_desc=candidate_desc, ancestor=ancestor,
    )
    endpoint = f"{config_state.base_url()}/{dataset}/sparql"
    sw = SPARQLWrapper(endpoint)
    user, pw = config_state.auth()
    sw.setHTTPAuth("BASIC")
    sw.setCredentials(user, pw)
    sw.setReturnFormat(JSON)
    sw.setQuery(sparql_str)
    result = sw.query().convert()
    return bool(result.get("boolean", False))


def add_super_class(dataset: str, graph: str, child_iri: str, parent_iri: str) -> None:
    """child rdfs:subClassOf parent 트리플을 삽입한다.

    Raises:
        ValueError("not found: child"): child class 미존재
        ValueError("not found: parent"): parent class 미존재
        ValueError("circular"): 순환 참조 발생
    """
    _validate_iri(graph); _validate_iri(child_iri); _validate_iri(parent_iri)
    if not _class_exists(dataset, graph, child_iri):
        raise ValueError(f"not found: child {child_iri}")
    if not _class_exists(dataset, graph, parent_iri):
        raise ValueError(f"not found: parent {parent_iri}")
    # 순환 참조 검사: parent가 child의 하위 클래스이면 사이클 발생
    if _is_descendant(dataset, graph, candidate_desc=parent_iri, ancestor=child_iri):
        raise ValueError(f"circular: {parent_iri} is already a descendant of {child_iri}")
    sparql_update(dataset, _U_INS_SUBCLASSOF.format(graph=graph, child=child_iri, parent=parent_iri))


def remove_super_class(dataset: str, graph: str, child_iri: str, parent_iri: str) -> None:
    """child rdfs:subClassOf parent 트리플을 삭제한다 (멱등)."""
    _validate_iri(graph); _validate_iri(child_iri); _validate_iri(parent_iri)
    sparql_update(dataset, _U_DEL_SUBCLASSOF.format(graph=graph, child=child_iri, parent=parent_iri))


_U_MIGRATE_IND_TYPE = """
DELETE {{ GRAPH <{graph}> {{ ?ind a <{old_class}> }} }}
INSERT {{ GRAPH <{graph}> {{ ?ind a <{new_class}> }} }}
WHERE  {{ GRAPH <{graph}> {{ ?ind a <{old_class}> }} }}
"""


def delete_class(
    dataset: str,
    graph: str,
    class_iri: str,
    on_individual: str = "delete",
    target_class_iri: str | None = None,
) -> None:
    """
    Class 삭제 (3단계).

    on_individual:
      "delete"  — 소속 Individual 및 관련 트리플 모두 삭제
      "migrate" — 소속 Individual의 rdf:type을 target_class_iri로 변경 후 Class 삭제
                  (target_class_iri 필수)
    """
    _validate_iri(graph)
    _validate_iri(class_iri)

    fmt = dict(graph=graph, class_iri=class_iri)

    if on_individual == "migrate":
        if not target_class_iri:
            raise ValueError("migrate 옵션에는 target_class_iri가 필요합니다.")
        _validate_iri(target_class_iri)
        # Individual rdf:type 교체
        sparql_update(
            dataset,
            _U_MIGRATE_IND_TYPE.format(
                graph=graph, old_class=class_iri, new_class=target_class_iri
            ),
        )
    elif on_individual == "delete":
        # 1a) Individual 인커밍 트리플 먼저 삭제 (rdf:type 삭제 전에)
        sparql_update(dataset, _U_DEL_IND_INCOMING.format(**fmt))
        # 1b) Individual 아웃고잉 트리플 삭제 (rdf:type 포함)
        sparql_update(dataset, _U_DEL_IND_OUTGOING.format(**fmt))
    else:
        raise ValueError(f"on_individual 값이 잘못됐습니다: {on_individual!r} (delete | migrate)")

    # 2) domain / range 참조 제거
    sparql_update(dataset, _U_DEL_DOMAIN_RANGE.format(**fmt))
    # 3) Class 선언 삭제
    sparql_update(dataset, _U_DEL_CLASS.format(**fmt))
