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

SELECT ?class ?label ?comment WHERE {{
  GRAPH <{graph}> {{
    ?class a owl:Class .
    OPTIONAL {{ ?class rdfs:label ?label }}
    OPTIONAL {{ ?class rdfs:comment ?comment }}
    FILTER(STRSTARTS(str(?class), "{namespace}"))
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


# ────────────────────────────────────────────────
# 공개 함수
# ────────────────────────────────────────────────

def list_classes(dataset: str, graph: str, namespace: str) -> list[dict]:
    """OOI 범위 내 Class 목록 반환."""
    _validate_iri(graph)
    _validate_iri(namespace)
    rows = sparql_query(dataset, _Q_LIST.format(graph=graph, namespace=namespace))
    return [
        {
            "iri":     r["class"],
            "label":   r.get("label"),
            "comment": r.get("comment"),
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


def delete_class(dataset: str, graph: str, class_iri: str, on_individual: str = "delete") -> None:
    """
    Class 삭제 (3단계).

    on_individual:
      "delete" — 소속 Individual 및 관련 트리플 모두 삭제
    """
    _validate_iri(graph)
    _validate_iri(class_iri)

    if on_individual != "delete":
        raise NotImplementedError(f"on_individual='{on_individual}' 은 v02에서 지원됩니다.")

    fmt = dict(graph=graph, class_iri=class_iri)

    # 1a) Individual 인커밍 트리플 먼저 삭제 (rdf:type 삭제 전에)
    sparql_update(dataset, _U_DEL_IND_INCOMING.format(**fmt))
    # 1b) Individual 아웃고잉 트리플 삭제 (rdf:type 포함)
    sparql_update(dataset, _U_DEL_IND_OUTGOING.format(**fmt))
    # 2) domain / range 참조 제거
    sparql_update(dataset, _U_DEL_DOMAIN_RANGE.format(**fmt))
    # 3) Class 선언 삭제
    sparql_update(dataset, _U_DEL_CLASS.format(**fmt))
