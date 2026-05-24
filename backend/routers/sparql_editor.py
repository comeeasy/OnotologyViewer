"""v02-F SPARQL Editor — OOI Named Graph 자동 적용."""

import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fuseki.sparql import query as sparql_query, update as sparql_update

router = APIRouter(prefix="/api/sparql", tags=["sparql-editor"])

# ── SPARQL auto-wrap 유틸 ────────────────────────────────────────────────

_QUERY_TYPE = re.compile(r'^\s*(SELECT|ASK|CONSTRUCT|DESCRIBE)\b', re.IGNORECASE)
_WHERE_CLAUSE = re.compile(r'\bWHERE\s*\{', re.IGNORECASE)
_ASK_CLAUSE = re.compile(r'\bASK\s*\{', re.IGNORECASE)
_UPDATE_DATA = re.compile(r'\b(INSERT|DELETE)\s+DATA\s*\{', re.IGNORECASE)
_UPDATE_WHERE = re.compile(r'\bWHERE\s*\{', re.IGNORECASE)


def _find_matching_brace(s: str, start: int) -> int:
    """
    s[start:] 의 첫 번째 '{' 이후부터 짝 맞는 '}'의 위치를 반환한다.
    start는 이미 '{' 다음 문자 인덱스.
    반환값: '}'에 해당하는 s의 index.
    """
    depth = 1
    i = start
    while i < len(s) and depth > 0:
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
        i += 1
    return i - 1  # position of closing }


def _wrap_block(sparql: str, pattern_match_end: int, graph_iri: str) -> str:
    """pattern_match_end 이후 블록을 GRAPH <iri> { ... } 로 감싼다."""
    close = _find_matching_brace(sparql, pattern_match_end)
    body = sparql[pattern_match_end:close]
    return (
        sparql[:pattern_match_end]
        + f" GRAPH <{graph_iri}> {{{body}}}"
        + sparql[close:]
    )


def wrap_query(sparql: str, graph_iri: str) -> str:
    """
    SELECT / CONSTRUCT / DESCRIBE 의 WHERE 절, 또는 ASK 의 패턴 블록을
    GRAPH <graph_iri> { ... } 로 감싼다.
    """
    # WHERE { ... } (SELECT, CONSTRUCT, DESCRIBE)
    m = _WHERE_CLAUSE.search(sparql)
    if m:
        return _wrap_block(sparql, m.end(), graph_iri)
    # ASK { ... } (no WHERE keyword for simple ASK)
    m = _ASK_CLAUSE.search(sparql)
    if m:
        return _wrap_block(sparql, m.end(), graph_iri)
    return sparql


def wrap_update(sparql: str, graph_iri: str) -> str:
    """
    INSERT DATA { ... } 또는 DELETE DATA { ... } 의 데이터 블록,
    또는 DELETE/INSERT ... WHERE { ... } 의 WHERE 절을
    GRAPH <graph_iri> { ... } 로 감싼다.
    """
    # INSERT DATA or DELETE DATA
    m = _UPDATE_DATA.search(sparql)
    if m:
        return _wrap_block(sparql, m.end(), graph_iri)
    # DELETE/INSERT ... WHERE
    m = _UPDATE_WHERE.search(sparql)
    if m:
        return _wrap_block(sparql, m.end(), graph_iri)
    return sparql


# ── Models ───────────────────────────────────────────────────────────────

class SparqlQueryBody(BaseModel):
    dataset: str
    graph:   str
    query:   str


class SparqlQueryResponse(BaseModel):
    query_type: str   # "select" | "ask"
    results: list[dict] = []
    boolean: bool | None = None


class SparqlUpdateBody(BaseModel):
    dataset: str
    graph:   str
    update:  str


class SparqlUpdateResponse(BaseModel):
    success: bool
    message: str = "업데이트가 성공적으로 실행되었습니다."


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/query", response_model=SparqlQueryResponse)
def post_sparql_query(body: SparqlQueryBody):
    """
    SPARQL SELECT / ASK 쿼리 실행.
    WHERE 절이 GRAPH <ooi_graph> { ... } 로 자동 감싸진다.
    """
    sparql = wrap_query(body.query.strip(), body.graph)

    is_ask = bool(re.match(r'\s*ASK\b', body.query, re.IGNORECASE))

    try:
        if is_ask:
            # ASK: SPARQLWrapper returns boolean
            from SPARQLWrapper import JSON, SPARQLWrapper
            import config_state
            sw = SPARQLWrapper(f"{config_state.base_url()}/{body.dataset}/sparql")
            user, pw = config_state.auth()
            sw.setHTTPAuth("BASIC")
            sw.setCredentials(user, pw)
            sw.setQuery(sparql)
            sw.setReturnFormat(JSON)
            result = sw.query().convert()
            return SparqlQueryResponse(
                query_type="ask",
                boolean=bool(result.get("boolean", False)),
            )
        else:
            rows = sparql_query(body.dataset, sparql)
            return SparqlQueryResponse(query_type="select", results=rows)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/update", response_model=SparqlUpdateResponse)
def post_sparql_update(body: SparqlUpdateBody):
    """
    SPARQL UPDATE (INSERT/DELETE) 실행.
    INSERT DATA / DELETE DATA 블록이 GRAPH <ooi_graph> { ... } 로 자동 감싸진다.
    """
    sparql = wrap_update(body.update.strip(), body.graph)
    try:
        sparql_update(body.dataset, sparql)
        return SparqlUpdateResponse(success=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
