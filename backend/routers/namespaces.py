"""Namespace 목록 조회 및 CRUD (v02-C)."""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, field_validator
from typing import Literal

from fuseki.sparql import query as sparql_query
from services.namespace import classify, get_prefix
import services.namespace_crud as ns_crud

router = APIRouter(prefix="/api/datasets", tags=["namespaces"])


# ---------- SPARQL ----------

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

_Q_GRAPHS_FOR_NS = """
SELECT DISTINCT ?g WHERE {{
  GRAPH ?g {{
    ?s ?p ?o .
    FILTER(isIRI(?s))
    FILTER(STRSTARTS(str(?s), "{base_iri}"))
  }}
}}
"""

# 선언된 namespace prefix 목록 (graph 내 vann:preferredNamespacePrefix)
_Q_DECLARED_IN_GRAPH = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX vann: <http://purl.org/vocab/vann/>
SELECT ?ns ?prefix WHERE {{
  GRAPH <{graph}> {{
    ?ns a owl:Ontology ;
        vann:preferredNamespacePrefix ?prefix .
  }}
  FILTER(STRSTARTS(str(?ns), "http"))
}}
"""


# ---------- Response models ----------

class Namespace(BaseModel):
    base_iri: str
    prefix: str | None
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


class DeclareNsBody(BaseModel):
    graph: str
    ns_iri: str
    prefix: str

    @field_validator("ns_iri")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("ns_iri must start with http:// or https://")
        return v


class PatchNsBody(BaseModel):
    graph: str
    ns_iri: str
    prefix: str


class RenameNsBody(BaseModel):
    graph: str
    old_ns: str
    new_ns: str


class NsDeclResponse(BaseModel):
    ns_iri: str
    prefix: str


class RenamePreviewResponse(BaseModel):
    affected_triples: int
    old_ns: str
    new_ns: str


class RenameResponse(BaseModel):
    old_ns: str
    new_ns: str
    affected_triples: int


# ---------- Helper ----------

def _to_namespace(base_iri: str, declared_prefixes: dict[str, str] | None = None) -> Namespace:
    """
    declared_prefixes: {ns_iri: prefix} — graph에 명시적으로 선언된 prefix
    Custom namespace도 선언이 있으면 해당 prefix 반환.
    """
    ns_type = classify(base_iri)
    if declared_prefixes and base_iri in declared_prefixes:
        prefix = declared_prefixes[base_iri]
    else:
        prefix = get_prefix(base_iri)
    return Namespace(base_iri=base_iri, prefix=prefix, type=ns_type)


def _get_declared_prefixes(dataset: str, graph: str) -> dict[str, str]:
    """graph에서 vann:preferredNamespacePrefix 선언을 조회."""
    rows = sparql_query(dataset, _Q_DECLARED_IN_GRAPH.format(graph=graph))
    return {r["ns"]: r["prefix"] for r in rows}


# ---------- Endpoints ----------

@router.get("/{ds}/namespaces", response_model=NamespacesResponse)
def get_all_namespaces(ds: str):
    rows = sparql_query(ds, _Q_ALL_NS)
    return NamespacesResponse(namespaces=[_to_namespace(r["ns"]) for r in rows])


@router.get("/{ds}/graphs/namespaces/rename-preview", response_model=RenamePreviewResponse)
def get_rename_preview(
    ds: str,
    graph: str = Query(...),
    old_ns: str = Query(...),
    new_ns: str = Query(...),
):
    """IRI 치환 시 영향받는 triple 수 미리 조회 (읽기 전용)."""
    result = ns_crud.preview_rename(ds, graph, old_ns, new_ns)
    return RenamePreviewResponse(**result)


@router.get("/{ds}/graphs/namespaces", response_model=GraphNamespacesResponse)
def get_namespaces_in_graph(
    ds: str,
    graph: str = Query(..., description="Named Graph IRI"),
):
    """
    그래프 내 namespace 목록 반환.
    - Custom: 명시 선언된(vann:preferredNamespacePrefix) 것만 포함
    - Universal: 그래프 내 subject IRI에서 감지된 것 포함
    """
    rows = sparql_query(ds, _Q_NS_IN_GRAPH.format(graph=graph))
    declared = _get_declared_prefixes(ds, graph)

    result: list[Namespace] = []
    seen: set[str] = set()
    for r in rows:
        ns = r["ns"]
        if ns in seen:
            continue
        seen.add(ns)
        ns_type = classify(ns)
        if ns_type == "custom" and ns not in declared:
            # 선언되지 않은 custom namespace는 노출하지 않음
            continue
        result.append(_to_namespace(ns, declared))

    return GraphNamespacesResponse(graph=graph, namespaces=result)


@router.post("/{ds}/graphs/namespaces", response_model=NsDeclResponse, status_code=201)
def post_namespace(ds: str, body: DeclareNsBody):
    """새 namespace를 graph에 선언 (vann:preferredNamespacePrefix 트리플 삽입)."""
    try:
        result = ns_crud.declare_namespace(ds, body.graph, body.ns_iri, body.prefix)
        return NsDeclResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/{ds}/graphs/namespaces", response_model=NsDeclResponse)
def patch_namespace(ds: str, body: PatchNsBody):
    """namespace prefix 선언 트리플을 교체한다."""
    try:
        result = ns_crud.update_prefix(ds, body.graph, body.ns_iri, body.prefix)
        return NsDeclResponse(**result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{ds}/graphs/namespaces/rename", response_model=RenameResponse)
def post_rename_namespace(ds: str, body: RenameNsBody):
    """graph 내에서 old_ns → new_ns IRI 일괄 치환."""
    result = ns_crud.rename_namespace(ds, body.graph, body.old_ns, body.new_ns)
    return RenameResponse(**result)


@router.delete("/{ds}/graphs/namespaces", status_code=204)
def delete_namespace(
    ds: str,
    graph: str = Query(...),
    ns_iri: str = Query(...),
):
    """namespace 선언 + 해당 namespace의 모든 subject 트리플 삭제."""
    try:
        ns_crud.delete_namespace(ds, graph, ns_iri)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ds}/namespaces/graphs", response_model=NamespaceGraphsResponse)
def get_graphs_for_namespace(
    ds: str,
    namespace: str = Query(..., description="Namespace base IRI"),
):
    rows = sparql_query(ds, _Q_GRAPHS_FOR_NS.format(base_iri=namespace))
    return NamespaceGraphsResponse(
        namespace=namespace,
        type=classify(namespace),
        graphs=[r["g"] for r in rows],
    )
