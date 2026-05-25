"""
OntologyReasoningEngine — RDFS/OWL-RL 추론 구체화 서비스.

역할
----
각 서비스(class_, individual 등)가 온톨로지를 수정한 뒤 이 모듈의 hook을
호출하면, 필요한 추론 결과를 Fuseki 그래프에 자동으로 구체화(materialize)한다.

그래프 이중화 전략
-----------------
- main graph   `{graph}`              : 사용자가 명시한 asserted 트리플
- inferred graph `{graph}__inferred`  : 추론된 트리플 (이 모듈만 기록)

지원 규칙
---------
  rdfs9  : X rdf:type C, C rdfs:subClassOf D  →  X rdf:type D
  rdfs11 : A subClassOf B, B subClassOf C      →  A subClassOf C  (SPARQL property path 활용)
  owlrl  : full_materialize 시 RDFS_Semantics 전체 (domain/range 기반 타입 추론 포함)
"""

from __future__ import annotations

import httpx
import rdflib
from rdflib import Graph, URIRef
import owlrl

from fuseki.sparql import query as sparql_query, update as sparql_update
import config_state

# ── 상수 ────────────────────────────────────────────────────────────────────

RDF_TYPE  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDF_TYPE_U = URIRef(RDF_TYPE)
OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
RDFS_SUB  = "http://www.w3.org/2000/01/rdf-schema#subClassOf"


def _inferred_graph(graph: str) -> str:
    """추론 결과 저장용 named graph IRI."""
    return graph + "__inferred"


# ── SPARQL 템플릿 ────────────────────────────────────────────────────────────

# 개인의 asserted rdf:type 목록 (main 그래프)
_Q_DIRECT_TYPES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT DISTINCT ?class WHERE {{
  GRAPH <{graph}> {{
    <{ind_iri}> rdf:type ?class .
    FILTER(isIRI(?class))
  }}
}}
"""

# 클래스의 모든 직접 상위 클래스 (main 그래프에서 1-hop)
_Q_SUPER_ONE_HOP = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?parent WHERE {{
  GRAPH <{graph}> {{
    <{class_iri}> rdfs:subClassOf ?parent .
    FILTER(isIRI(?parent))
  }}
}}
"""

# 클래스의 모든 전이적 상위 클래스 (rdfs:subClassOf+)
_Q_ANCESTORS = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?ancestor WHERE {{
  GRAPH <{graph}> {{
    <{class_iri}> rdfs:subClassOf+ ?ancestor .
    FILTER(isIRI(?ancestor))
  }}
}}
"""

# 특정 클래스를 직접 rdf:type 으로 갖는 개인 목록 (main 그래프)
_Q_DIRECT_INDIVIDUALS = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?ind WHERE {{
  GRAPH <{graph}> {{
    ?ind rdf:type <{class_iri}> .
    FILTER(isIRI(?ind))
  }}
}}
"""

# 개인이 이미 __inferred 에 갖고 있는 rdf:type 목록
_Q_INFERRED_TYPES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?class WHERE {{
  GRAPH <{inferred_graph}> {{
    <{ind_iri}> rdf:type ?class .
    FILTER(isIRI(?class))
  }}
}}
"""

# __inferred 에서 개인의 모든 rdf:type 삭제
_U_CLEAR_INFERRED_TYPES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
DELETE {{
  GRAPH <{inferred_graph}> {{ <{ind_iri}> rdf:type ?c }}
}}
WHERE {{
  GRAPH <{inferred_graph}> {{ <{ind_iri}> rdf:type ?c }}
}}
"""

# __inferred 에 rdf:type 삽입
_U_INSERT_INFERRED_TYPE = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
INSERT DATA {{
  GRAPH <{inferred_graph}> {{
    <{ind_iri}> rdf:type <{class_iri}> .
  }}
}}
"""

# __inferred 전체 초기화
_U_CLEAR_ALL_INFERRED = """
DELETE WHERE {{ GRAPH <{inferred_graph}> {{ ?s ?p ?o }} }}
"""

# __inferred 에 여러 rdf:type 한 번에 삽입
_U_INSERT_INFERRED_TYPES_BULK = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
INSERT DATA {{
  GRAPH <{inferred_graph}> {{
    {triples}
  }}
}}
"""

# main 그래프의 모든 개인 목록
_Q_ALL_INDIVIDUALS = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
SELECT DISTINCT ?ind ?class WHERE {{
  GRAPH <{graph}> {{
    ?ind rdf:type ?class .
    ?class a owl:Class .
    FILTER(isIRI(?ind))
  }}
}}
"""

# 개인이 사용하는 property 목록 + 각 domain (main 그래프)
_Q_PROP_DOMAINS = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?prop ?domain WHERE {{
  GRAPH <{graph}> {{
    <{ind_iri}> ?prop ?val .
    FILTER(?prop NOT IN (
      <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>,
      <http://www.w3.org/2000/01/rdf-schema#label>,
      <http://www.w3.org/2000/01/rdf-schema#comment>
    ))
    ?prop rdfs:domain ?domain .
    FILTER(isIRI(?domain))
  }}
}}
"""


# ── 공개 함수 ────────────────────────────────────────────────────────────────

def get_ancestor_classes(dataset: str, graph: str, class_iri: str) -> list[str]:
    """
    rdfs:subClassOf+ 경로로 class_iri 의 모든 전이적 상위 클래스를 반환한다.

    Parameters
    ----------
    dataset : Fuseki dataset 명
    graph   : Named Graph IRI (main)
    class_iri : 대상 클래스 IRI

    Returns
    -------
    list[str] — 상위 클래스 IRI 목록 (빈 리스트 가능)
    """
    rows = sparql_query(dataset, _Q_ANCESTORS.format(graph=graph, class_iri=class_iri))
    return [r["ancestor"] for r in rows]


def materialize_individual(dataset: str, graph: str, ind_iri: str) -> list[str]:
    """
    개인(ind_iri)의 asserted rdf:type 기반으로 ancestor types를
    ``{graph}__inferred`` 그래프에 구체화한다.

    기존 inferred types는 일단 유지하고 누락된 것만 추가한다.
    전면 교체하려면 clear_inferred_types() 먼저 호출할 것.

    Returns
    -------
    list[str] — 새로 삽입된 type IRI 목록
    """
    inferred_g = _inferred_graph(graph)

    # 1. 현재 asserted rdf:type 목록
    direct_types = [r["class"] for r in sparql_query(
        dataset, _Q_DIRECT_TYPES.format(graph=graph, ind_iri=ind_iri)
    )]
    if not direct_types:
        return []

    # 2. 각 direct type 의 ancestor 를 합산
    all_ancestors: set[str] = set()
    for dt in direct_types:
        all_ancestors.update(get_ancestor_classes(dataset, graph, dt))

    # direct types 자체는 ancestor 에서 제외 (이미 main 그래프에 있음)
    to_infer = all_ancestors - set(direct_types)
    if not to_infer:
        return []

    # 3. 이미 __inferred 에 있는 타입은 중복 삽입 방지
    existing = {r["class"] for r in sparql_query(
        dataset, _Q_INFERRED_TYPES.format(inferred_graph=inferred_g, ind_iri=ind_iri)
    )}
    new_types = to_infer - existing
    if not new_types:
        return []

    # 4. 일괄 INSERT
    triples = "\n    ".join(
        f"<{ind_iri}> <{RDF_TYPE}> <{t}> ."
        for t in new_types
    )
    sparql_update(dataset, _U_INSERT_INFERRED_TYPES_BULK.format(
        inferred_graph=inferred_g,
        triples=triples,
    ))

    return list(new_types)


def clear_inferred_types(dataset: str, graph: str, ind_iri: str) -> None:
    """
    개인의 inferred rdf:type 트리플을 ``{graph}__inferred`` 에서 모두 제거한다.

    migrate_individual_class() 처럼 asserted type 이 바뀌기 전에 호출해야
    이전 계층 기반 inferred types 가 깔끔하게 정리된다.
    """
    inferred_g = _inferred_graph(graph)
    sparql_update(dataset, _U_CLEAR_INFERRED_TYPES.format(
        inferred_graph=inferred_g,
        ind_iri=ind_iri,
    ))


def on_class_hierarchy_change(dataset: str, graph: str, changed_class_iri: str) -> None:
    """
    addSuperClass / removeSuperClass 직후 호출한다.

    changed_class_iri 를 직접 rdf:type 으로 갖는 모든 개인에 대해
    inferred types 를 초기화한 뒤 재구체화한다.

    Parameters
    ----------
    changed_class_iri : 계층이 변경된 클래스 IRI
    """
    rows = sparql_query(
        dataset,
        _Q_DIRECT_INDIVIDUALS.format(graph=graph, class_iri=changed_class_iri),
    )
    for row in rows:
        ind = row["ind"]
        clear_inferred_types(dataset, graph, ind)
        materialize_individual(dataset, graph, ind)


def get_incompatible_properties(
    dataset: str,
    graph: str,
    ind_iri: str,
    new_class_iri: str,
) -> list[str]:
    """
    개인이 사용하는 property 중 new_class_iri 와 호환되지 않는 것들을 반환한다.

    호환 기준: property 의 rdfs:domain 이 new_class_iri 자신이거나
              new_class_iri 의 ancestor class 이면 호환.

    SPARQL FILTER NOT EXISTS 방식을 Python 집합 연산으로 교체하여
    Fuseki named graph 컨텍스트 문제를 해결한다.

    Returns
    -------
    list[str] — 비호환 property IRI 목록 (빈 리스트 = 모두 호환)
    """
    # 1. new_class 의 ancestor set (자기 자신 포함)
    ancestors = set(get_ancestor_classes(dataset, graph, new_class_iri))
    ancestors.add(new_class_iri)

    # 2. 개인이 사용하는 property + domain 조회
    rows = sparql_query(dataset, _Q_PROP_DOMAINS.format(
        graph=graph, ind_iri=ind_iri,
    ))

    # 3. domain ∉ ancestors → 비호환
    incompatible: list[str] = []
    seen: set[str] = set()
    for row in rows:
        prop   = row["prop"]
        domain = row["domain"]
        if prop in seen:
            continue
        if domain not in ancestors:
            incompatible.append(prop)
            seen.add(prop)

    return incompatible


def full_materialize(dataset: str, graph: str) -> dict:
    """
    owlrl RDFS_Semantics 기반으로 전체 그래프를 재구체화한다.

    1. ``{graph}__inferred`` 초기화
    2. main 그래프 TTL export → rdflib 파싱
    3. owlrl.DeductiveClosure(RDFS_Semantics).expand()
    4. 추론된 rdf:type 트리플 → Fuseki __inferred 삽입

    Returns
    -------
    {"added": int} — 새로 삽입된 트리플 수
    """
    inferred_g = _inferred_graph(graph)

    # 1. __inferred 초기화
    sparql_update(dataset, _U_CLEAR_ALL_INFERRED.format(inferred_graph=inferred_g))

    # 2. TTL export
    ttl = _export_graph_ttl(dataset, graph)
    if not ttl.strip():
        return {"added": 0}

    # 3. rdflib + owlrl 추론
    g = Graph()
    g.parse(data=ttl, format="turtle")
    original_types = {
        (str(s), str(p), str(o))
        for s, p, o in g
        if str(p) == RDF_TYPE
    }

    # ABox individual 판별: OWL/RDFS vocab 타입을 가진 TBox 리소스 제외
    _TBOX_TYPES = {
        "http://www.w3.org/2002/07/owl#Class",
        "http://www.w3.org/2002/07/owl#ObjectProperty",
        "http://www.w3.org/2002/07/owl#DatatypeProperty",
        "http://www.w3.org/2002/07/owl#AnnotationProperty",
        "http://www.w3.org/2002/07/owl#Ontology",
        "http://www.w3.org/2002/07/owl#TransitiveProperty",
        "http://www.w3.org/2002/07/owl#FunctionalProperty",
        "http://www.w3.org/2002/07/owl#InverseFunctionalProperty",
        "http://www.w3.org/2002/07/owl#SymmetricProperty",
        "http://www.w3.org/2002/07/owl#AsymmetricProperty",
        "http://www.w3.org/2002/07/owl#ReflexiveProperty",
        "http://www.w3.org/2002/07/owl#IrreflexiveProperty",
    }
    # 원본 그래프에서 ABox individual subjects 추출
    abox_subjects: set[str] = {
        str(s) for s, p, o in g
        if str(p) == RDF_TYPE
        and isinstance(s, URIRef)
        and isinstance(o, URIRef)
        and str(o) not in _TBOX_TYPES
    }

    owlrl.DeductiveClosure(owlrl.RDFS_Semantics, rdfs_closure=True, axiomatic_triples=False).expand(g)

    # 4. 추론으로 새로 생긴 rdf:type 트리플만 수집
    #    - subject, object 모두 URIRef 이어야 함 (BNode/Literal 제외)
    #    - ABox individual subject 만 포함 (TBox/스키마 레벨 제외)
    #    - object 가 rdfs:Resource / owl:Thing 등 상위 공리 타입이면 제외
    #    - 원본에 없던 것만
    _UPPER_TYPES = {
        "http://www.w3.org/2000/01/rdf-schema#Resource",
        "http://www.w3.org/2000/01/rdf-schema#Class",
        "http://www.w3.org/2002/07/owl#Thing",
        "http://www.w3.org/2002/07/owl#Class",
    }
    new_type_triples: list[tuple[str, str]] = []
    for s, p, o in g:
        if str(p) != RDF_TYPE:
            continue
        if not (isinstance(s, URIRef) and isinstance(o, URIRef)):
            continue
        if str(s) not in abox_subjects:
            continue  # TBox 리소스, 스키마 레벨 제외
        if str(o) in _UPPER_TYPES:
            continue  # 공리 상위 타입 제외
        triple_key = (str(s), str(p), str(o))
        if triple_key in original_types:
            continue
        new_type_triples.append((str(s), str(o)))

    if not new_type_triples:
        return {"added": 0}

    # 5. 배치 INSERT (1000건 단위)
    added = 0
    batch_size = 500
    for i in range(0, len(new_type_triples), batch_size):
        batch = new_type_triples[i : i + batch_size]
        triples_str = "\n    ".join(
            f"<{s}> <{RDF_TYPE}> <{o}> ." for s, o in batch
        )
        sparql_update(dataset, _U_INSERT_INFERRED_TYPES_BULK.format(
            inferred_graph=inferred_g,
            triples=triples_str,
        ))
        added += len(batch)

    return {"added": added}


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _export_graph_ttl(dataset: str, graph: str) -> str:
    """Fuseki named graph를 TTL 형식으로 export."""
    url = f"{config_state.base_url()}/{dataset}"
    user, pw = config_state.auth()
    r = httpx.get(
        url,
        params={"graph": graph},
        headers={"Accept": "text/turtle"},
        auth=(user, pw),
        timeout=30,
    )
    r.raise_for_status()
    return r.text
