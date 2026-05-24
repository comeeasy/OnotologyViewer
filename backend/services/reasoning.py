"""v02-G Reasoning Service — owlrl + rdflib 기반 OWL/RDFS 추론."""

import httpx
import rdflib
from rdflib import Graph
import owlrl

import config_state

MAX_PREVIEW = 1000

SUPPORTED_REASONERS = {
    "RDFS":   owlrl.RDFS_Semantics,
    "OWL_RL": owlrl.OWLRL_Semantics,
    "RDFS_OWL_RL": owlrl.RDFS_OWLRL_Semantics,
}


def _export_graph_ttl(dataset: str, graph: str) -> str:
    """Fuseki에서 Named Graph를 TTL 형식으로 export."""
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


def _rdflib_graph_from_ttl(ttl_content: str) -> Graph:
    """TTL 문자열을 rdflib.Graph로 파싱."""
    g = Graph()
    g.parse(data=ttl_content, format="turtle")
    return g


def _get_original_triples(g: Graph) -> set[tuple]:
    """추론 전 원본 트리플 집합 반환."""
    return {(str(s), str(p), str(o)) for s, p, o in g}


def run_reasoning(
    dataset: str,
    graph: str,
    reasoner: str,
) -> dict:
    """
    Named Graph를 export하여 owlrl로 추론한 후
    추론된 새 트리플 목록을 반환한다.

    Returns:
        {
          "inferred_triples": [{"s": ..., "p": ..., "o": ...}, ...],
          "total_inferred": int,
          "truncated": bool,
        }

    Raises:
        ValueError: 지원하지 않는 reasoner (→ 422)
    """
    if reasoner not in SUPPORTED_REASONERS:
        raise ValueError(f"지원하지 않는 reasoner: {reasoner!r}. 지원: {list(SUPPORTED_REASONERS)}")

    cls = SUPPORTED_REASONERS[reasoner]

    # Fuseki에서 TTL export
    ttl = _export_graph_ttl(dataset, graph)

    # rdflib 그래프 파싱
    g = _rdflib_graph_from_ttl(ttl)
    original = _get_original_triples(g)

    # 추론 실행
    owlrl.DeductiveClosure(cls, datatype_axioms=False).expand(g)

    # 추론된 새 트리플 계산
    inferred = []
    for s, p, o in g:
        triple = (str(s), str(p), str(o))
        if triple not in original:
            inferred.append({"s": str(s), "p": str(p), "o": str(o)})

    total = len(inferred)
    truncated = total > MAX_PREVIEW
    return {
        "inferred_triples": inferred[:MAX_PREVIEW],
        "total_inferred": total,
        "truncated": truncated,
    }


def materialize(
    dataset: str,
    graph: str,
    inferred_triples: list[dict],
) -> dict:
    """
    추론된 트리플을 {graph}/inferred Named Graph에 삽입한다.

    Returns:
        {"inferred_graph": ..., "materialized_count": int}
    """
    inferred_graph = f"{graph}/inferred"

    if not inferred_triples:
        return {"inferred_graph": inferred_graph, "materialized_count": 0}

    # SPARQL INSERT DATA 구성
    # 최대 500개씩 배치
    def _is_iri(term: str) -> bool:
        return term.startswith("http://") or term.startswith("https://")

    def _is_bnode(term: str) -> bool:
        return term.startswith("_:")

    def _format_term(term: str) -> str:
        if _is_iri(term):
            return f"<{term}>"
        elif _is_bnode(term):
            return term
        else:
            # Literal: escape special chars
            escaped = term.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            return f'"{escaped}"'

    # Fuseki는 literal을 subject로 허용하지 않으므로 필터링
    valid_triples = [
        t for t in inferred_triples
        if _is_iri(t["s"]) or _is_bnode(t["s"])
    ]

    from fuseki.sparql import update as sparql_update

    batch_size = 500
    for i in range(0, len(valid_triples), batch_size):
        batch = valid_triples[i:i + batch_size]
        triples_str = "\n    ".join(
            f"{_format_term(t['s'])} {_format_term(t['p'])} {_format_term(t['o'])} ."
            for t in batch
        )
        sparql_update(dataset, f"""
        INSERT DATA {{
          GRAPH <{inferred_graph}> {{
            {triples_str}
          }}
        }}
        """)

    return {
        "inferred_graph": inferred_graph,
        "materialized_count": len(valid_triples),
    }


def check_consistency(dataset: str, graph: str) -> dict:
    """
    owlrl OWL_RL reasoner로 일관성 검사를 실행한다.
    오류는 ERRNS(http://www.daml.org/2002/03/agents/agent-ont#error) 트리플로 감지한다.

    Returns:
        {"consistent": bool, "details": str | list[str]}
    """
    ttl = _export_graph_ttl(dataset, graph)
    g = _rdflib_graph_from_ttl(ttl)

    try:
        owlrl.DeductiveClosure(
            owlrl.OWLRL_Semantics,
            datatype_axioms=False,
        ).expand(g)
    except Exception as e:
        return {"consistent": False, "details": str(e)}

    # owlrl가 오류를 ERRNS 트리플로 기록한다
    ERRNS = rdflib.URIRef("http://www.daml.org/2002/03/agents/agent-ont#error")
    errors = [str(o) for _, p, o in g if p == ERRNS]

    if errors:
        return {"consistent": False, "details": errors}
    return {"consistent": True, "details": "일관성 검사 통과"}
