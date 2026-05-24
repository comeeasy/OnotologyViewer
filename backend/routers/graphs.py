"""Named Graph 목록 조회 + 생성 + 삭제."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fuseki.sparql import query as sparql_query, update as sparql_update

router = APIRouter(prefix="/api/datasets", tags=["graphs"])


# ── SPARQL ─────────────────────────────────────────────
_Q_GRAPHS = "SELECT DISTINCT ?g WHERE { GRAPH ?g { } }"

# Named Graph을 "생성"하려면 트리플을 하나 삽입해야 한다.
# owl:Ontology 선언을 심어두면 온톨로지 관리 도구와 호환된다.
_U_CREATE_GRAPH = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
INSERT DATA {{
  GRAPH <{graph}> {{
    <{graph}> a owl:Ontology .
    {label_triple}
  }}
}}
"""

# Named Graph 전체 삭제
_U_DROP_GRAPH = "DROP SILENT GRAPH <{graph}>"


# ── Response / Request models ──────────────────────────
class GraphsResponse(BaseModel):
    dataset: str
    graphs: list[str]


class CreateGraphBody(BaseModel):
    graph: str          # Named Graph IRI
    label: str | None = None


class CreateGraphResponse(BaseModel):
    graph: str


# ── Endpoints ──────────────────────────────────────────

@router.get("/{ds}/graphs", response_model=GraphsResponse)
def get_graphs(ds: str):
    """dataset 안의 모든 Named Graph IRI 목록을 반환한다."""
    rows = sparql_query(ds, _Q_GRAPHS)
    return GraphsResponse(dataset=ds, graphs=[r["g"] for r in rows])


@router.post("/{ds}/graphs", response_model=CreateGraphResponse, status_code=201)
def create_graph(ds: str, body: CreateGraphBody):
    """Named Graph을 생성한다. (owl:Ontology 선언 트리플 삽입)"""
    if not body.graph.startswith("http"):
        raise HTTPException(422, "graph IRI는 http로 시작해야 합니다.")
    label_triple = (
        f'<{body.graph}> <http://www.w3.org/2000/01/rdf-schema#label> "{body.label}" .'
        if body.label else ""
    )
    try:
        sparql_update(ds, _U_CREATE_GRAPH.format(graph=body.graph, label_triple=label_triple))
    except Exception as e:
        raise HTTPException(500, str(e))
    return CreateGraphResponse(graph=body.graph)


@router.delete("/{ds}/graphs", status_code=204)
def delete_graph(ds: str, graph: str):
    """Named Graph과 그 안의 모든 트리플을 삭제한다."""
    if not graph.startswith("http"):
        raise HTTPException(422, "graph IRI는 http로 시작해야 합니다.")
    try:
        sparql_update(ds, _U_DROP_GRAPH.format(graph=graph))
    except Exception as e:
        raise HTTPException(500, str(e))
