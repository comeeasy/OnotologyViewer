"""Namespace 목록 조회 및 상호 포함 관계 조회."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Literal

from fuseki.sparql import query as sparql_query
from services.namespace import classify, get_prefix

router = APIRouter(prefix="/api/datasets", tags=["namespaces"])


# ---------- SPARQL ----------

# Named Graph 내 모든 subject IRI에서 base IRI를 추출한다.
# - REPLACE 패턴: 마지막 '#' 또는 '/' 이후 문자열을 제거 → base IRI만 남김
# - FILTER: IRI가 http로 시작하는 것만 (blank node, literal 제거)
# - FILTER(isIRI): subject가 IRI인 것만
_Q_NS_IN_GRAPH = """
SELECT DISTINCT ?ns WHERE {{
  GRAPH <{graph}> {{
    ?s ?p ?o .
    FILTER(isIRI(?s))
    BIND(REPLACE(str(?s), "(#|/)[^#/]*$", "$1") AS ?ns)
  }}
  FILTER(STRSTARTS(str(?ns), "http"))
}}
"""

# dataset 전체 그래프를 가로질러 모든 namespace를 한 번에 추출한다.
_Q_ALL_NS = """
SELECT DISTINCT ?ns WHERE {
  GRAPH ?g {
    ?s ?p ?o .
    FILTER(isIRI(?s))
    BIND(REPLACE(str(?s), "(#|/)[^#/]*$", "$1") AS ?ns)
  }
  FILTER(STRSTARTS(str(?ns), "http"))
}
"""

# 특정 base IRI로 시작하는 subject가 있는 Named Graph를 찾는다.
_Q_GRAPHS_FOR_NS = """
SELECT DISTINCT ?g WHERE {{
  GRAPH ?g {{
    ?s ?p ?o .
    FILTER(isIRI(?s))
    FILTER(STRSTARTS(str(?s), "{base_iri}"))
  }}
}}
"""


# ---------- Response models ----------

class Namespace(BaseModel):
    base_iri: str
    prefix: str | None          # Universal이면 canonical prefix, Custom이면 None
    type: Literal["custom", "universal"]


class NamespacesResponse(BaseModel):
    namespaces: list[Namespace]


class GraphNamespacesResponse(BaseModel):
    graph: str
    namespaces: list[Namespace]


class NamespaceGraphsResponse(BaseModel):
    namespace: str
    type: Literal["custom", "universal"]
    graphs: list[str]


# ---------- Helper ----------

def _to_namespace(base_iri: str) -> Namespace:
    return Namespace(
        base_iri=base_iri,
        prefix=get_prefix(base_iri),
        type=classify(base_iri),
    )


# ---------- Endpoints ----------

@router.get("/{ds}/namespaces", response_model=NamespacesResponse)
def get_all_namespaces(ds: str):
    """
    dataset 전체 Named Graph에 걸쳐 중복 없이 모든 Namespace를 반환한다.
    Custom / Universal 구분 포함.
    """
    rows = sparql_query(ds, _Q_ALL_NS)
    return NamespacesResponse(namespaces=[_to_namespace(r["ns"]) for r in rows])


@router.get("/{ds}/graphs/namespaces", response_model=GraphNamespacesResponse)
def get_namespaces_in_graph(
    ds: str,
    graph: str = Query(..., description="Named Graph IRI"),
):
    """
    특정 Named Graph에 속한 Namespace 목록을 반환한다.

    Args:
        ds:    Fuseki dataset 명
        graph: Named Graph IRI (query param)
    """
    rows = sparql_query(ds, _Q_NS_IN_GRAPH.format(graph=graph))
    return GraphNamespacesResponse(
        graph=graph,
        namespaces=[_to_namespace(r["ns"]) for r in rows],
    )


@router.get("/{ds}/namespaces/graphs", response_model=NamespaceGraphsResponse)
def get_graphs_for_namespace(
    ds: str,
    namespace: str = Query(..., description="Namespace base IRI"),
):
    """
    특정 Namespace(base IRI)가 포함된 Named Graph 목록을 반환한다.

    Args:
        ds:        Fuseki dataset 명
        namespace: base IRI (query param)
    """
    rows = sparql_query(ds, _Q_GRAPHS_FOR_NS.format(base_iri=namespace))
    return NamespaceGraphsResponse(
        namespace=namespace,
        type=classify(namespace),
        graphs=[r["g"] for r in rows],
    )
