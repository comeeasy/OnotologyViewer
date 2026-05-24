"""Named Graph 목록 조회 + 생성 + 수정 + 삭제 + 상세 (v02-B)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from fuseki.sparql import query as sparql_query, update as sparql_update

router = APIRouter(prefix="/api/datasets", tags=["graphs"])


# ── SPARQL ─────────────────────────────────────────────
_Q_GRAPHS = "SELECT DISTINCT ?g WHERE { GRAPH ?g { } }"

_Q_GRAPH_DETAIL = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?label ?comment (COUNT(*) AS ?cnt) WHERE {{
  GRAPH <{graph}> {{
    ?s ?p ?o .
    OPTIONAL {{ <{graph}> rdfs:label   ?label   }}
    OPTIONAL {{ <{graph}> rdfs:comment ?comment }}
  }}
}}
GROUP BY ?label ?comment
"""

_Q_GRAPH_EXISTS = """
SELECT (COUNT(*) AS ?cnt) WHERE {{
  GRAPH <{graph}> {{ ?s ?p ?o }}
}}
"""

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

_U_UPD_LABEL = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
DELETE {{ GRAPH <{graph}> {{ <{graph}> rdfs:label ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{graph}> rdfs:label "{label}" }} }}
WHERE  {{ GRAPH <{graph}> {{ <{graph}> a owl:Ontology .
                              OPTIONAL {{ <{graph}> rdfs:label ?v }} }} }}
"""

_U_UPD_COMMENT = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
DELETE {{ GRAPH <{graph}> {{ <{graph}> rdfs:comment ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{graph}> rdfs:comment "{comment}" }} }}
WHERE  {{ GRAPH <{graph}> {{ <{graph}> a owl:Ontology .
                              OPTIONAL {{ <{graph}> rdfs:comment ?v }} }} }}
"""

_U_DROP_GRAPH = "DROP SILENT GRAPH <{graph}>"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _graph_exists(ds: str, graph: str) -> bool:
    rows = sparql_query(ds, _Q_GRAPH_EXISTS.format(graph=graph))
    return bool(rows) and int(rows[0].get("cnt", 0)) > 0


# ── Response / Request models ──────────────────────────

class GraphsResponse(BaseModel):
    dataset: str
    graphs:  list[str]


class CreateGraphBody(BaseModel):
    graph: str
    label: str | None = None


class CreateGraphResponse(BaseModel):
    graph: str


class GraphDetail(BaseModel):
    graph:        str
    label:        str | None
    comment:      str | None
    triple_count: int


class PatchGraphBody(BaseModel):
    graph:   str
    label:   str | None = None
    comment: str | None = None

    @field_validator("label")
    @classmethod
    def label_not_empty(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            raise ValueError("label은 빈 문자열일 수 없습니다.")
        return v


# ── Endpoints ──────────────────────────────────────────

@router.get("/{ds}/graphs", response_model=GraphsResponse)
def get_graphs(ds: str):
    """dataset 안의 모든 Named Graph IRI 목록을 반환한다."""
    rows = sparql_query(ds, _Q_GRAPHS)
    return GraphsResponse(dataset=ds, graphs=[r["g"] for r in rows])


@router.get("/{ds}/graphs/detail", response_model=GraphDetail)
def get_graph_detail(ds: str, graph: str = Query(..., description="Named Graph IRI")):
    """Named Graph의 label·comment·triple_count를 반환한다."""
    if not _graph_exists(ds, graph):
        raise HTTPException(404, f"Named Graph을 찾을 수 없습니다: {graph}")
    rows = sparql_query(ds, _Q_GRAPH_DETAIL.format(graph=graph))
    if not rows:
        raise HTTPException(404, f"Named Graph을 찾을 수 없습니다: {graph}")
    r = rows[0]
    return GraphDetail(
        graph=graph,
        label=r.get("label"),
        comment=r.get("comment"),
        triple_count=int(r.get("cnt", 0)),
    )


@router.post("/{ds}/graphs", response_model=CreateGraphResponse, status_code=201)
def create_graph(ds: str, body: CreateGraphBody):
    """Named Graph을 생성한다. (owl:Ontology 선언 트리플 삽입)"""
    if not body.graph.startswith("http"):
        raise HTTPException(422, "graph IRI는 http로 시작해야 합니다.")
    label_triple = (
        f'<{body.graph}> <http://www.w3.org/2000/01/rdf-schema#label> "{_esc(body.label)}" .'
        if body.label else ""
    )
    try:
        sparql_update(ds, _U_CREATE_GRAPH.format(graph=body.graph, label_triple=label_triple))
    except Exception as e:
        raise HTTPException(500, str(e))
    return CreateGraphResponse(graph=body.graph)


@router.patch("/{ds}/graphs", response_model=GraphDetail)
def patch_graph(ds: str, body: PatchGraphBody):
    """Named Graph의 label / comment를 수정한다."""
    if not _graph_exists(ds, body.graph):
        raise HTTPException(404, f"Named Graph을 찾을 수 없습니다: {body.graph}")
    try:
        if body.label is not None:
            sparql_update(ds, _U_UPD_LABEL.format(graph=body.graph, label=_esc(body.label)))
        if body.comment is not None:
            sparql_update(ds, _U_UPD_COMMENT.format(graph=body.graph, comment=_esc(body.comment)))
    except Exception as e:
        raise HTTPException(500, str(e))
    # 최신 상태 반환
    rows = sparql_query(ds, _Q_GRAPH_DETAIL.format(graph=body.graph))
    r = rows[0] if rows else {}
    return GraphDetail(
        graph=body.graph,
        label=r.get("label"),
        comment=r.get("comment"),
        triple_count=int(r.get("cnt", 0)),
    )


@router.delete("/{ds}/graphs", status_code=204)
def delete_graph(ds: str, graph: str):
    """Named Graph과 그 안의 모든 트리플을 삭제한다."""
    if not graph.startswith("http"):
        raise HTTPException(422, "graph IRI는 http로 시작해야 합니다.")
    try:
        sparql_update(ds, _U_DROP_GRAPH.format(graph=graph))
    except Exception as e:
        raise HTTPException(500, str(e))
