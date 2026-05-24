"""v03-B Rule Service — SPARQL CONSTRUCT 기반 추론 규칙 관리."""

import uuid
from SPARQLWrapper import SPARQLWrapper, POST, JSON
from fuseki.sparql import query as sparql_query, update as sparql_update
import config_state

ONTO_NS = "http://ontologyviewer.io/ontology/rules#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
RDF_NS  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def _rules_graph_iri(graph: str) -> str:
    """OOI 그래프의 Rule 서브그래프 IRI."""
    return f"{graph}/rules"


def _materialized_graph_iri(graph: str) -> str:
    return f"{graph}/materialized"


def _gen_iri(base_iri: str, suffix: str) -> str:
    uid = uuid.uuid4().hex
    if base_iri.endswith("#") or base_iri.endswith("/"):
        return f"{base_iri}{suffix}_{uid}"
    return f"{base_iri}/{suffix}_{uid}"


def _escape_sparql_literal(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _validate_sparql_where(condition: str, dataset: str) -> None:
    """SPARQL WHERE 절이 유효한지 검증한다. 유효하지 않으면 ValueError 발생."""
    test_query = f"""
    SELECT * WHERE {{
      GRAPH <http://dummy.example.org/test> {{
        {condition}
      }}
    }} LIMIT 0
    """
    endpoint = f"{config_state.base_url()}/{dataset}/sparql"
    user, pw = config_state.auth()
    sw = SPARQLWrapper(endpoint)
    sw.setHTTPAuth("BASIC")
    sw.setCredentials(user, pw)
    sw.setReturnFormat(JSON)
    sw.setQuery(test_query)
    try:
        sw.query()
    except Exception as e:
        raise ValueError(f"잘못된 SPARQL condition: {e}") from e


# ──────────────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────────────

def create_rule(
    dataset: str,
    graph: str,
    label: str,
    condition: str,
    consequence: str,
    description: str | None = None,
) -> dict:
    """
    SPARQL 기반 추론 규칙을 생성한다.

    condition: SPARQL WHERE 절 패턴 (triple patterns only, 검증 후 저장)
    consequence: CONSTRUCT 템플릿 (triple patterns only)

    Raises:
        ValueError: 잘못된 SPARQL → 422
    """
    # SPARQL 유효성 검증
    _validate_sparql_where(condition, dataset)

    rules_graph = _rules_graph_iri(graph)
    rule_iri = _gen_iri(rules_graph, "Rule")

    esc_label = _escape_sparql_literal(label)
    esc_condition = _escape_sparql_literal(condition)
    esc_consequence = _escape_sparql_literal(consequence)

    desc_triple = ""
    if description:
        esc_desc = _escape_sparql_literal(description)
        desc_triple = f'<{rule_iri}> rdfs:comment "{esc_desc}" .'

    sparql_update(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    INSERT DATA {{
      GRAPH <{rules_graph}> {{
        <{rule_iri}> a onto:Rule ;
            rdfs:label "{esc_label}" ;
            onto:condition "{esc_condition}" ;
            onto:consequence "{esc_consequence}" .
        {desc_triple}
      }}
    }}
    """)
    return {
        "rule_iri": rule_iri,
        "label": label,
        "condition": condition,
        "consequence": consequence,
        "description": description,
    }


def list_rules(dataset: str, graph: str) -> list[dict]:
    """Rules 목록 반환."""
    rules_graph = _rules_graph_iri(graph)
    rows = sparql_query(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    SELECT ?rule ?label ?description WHERE {{
      GRAPH <{rules_graph}> {{
        ?rule a onto:Rule .
        OPTIONAL {{ ?rule rdfs:label ?label }}
        OPTIONAL {{ ?rule rdfs:comment ?description }}
      }}
    }}
    ORDER BY ?rule
    """)
    return [
        {
            "rule_iri": r["rule"],
            "label": r.get("label"),
            "description": r.get("description"),
        }
        for r in rows
    ]


def get_rule(dataset: str, graph: str, rule_iri: str) -> dict:
    """
    Rule 상세 조회.

    Raises:
        KeyError: not found (→ 404)
    """
    rules_graph = _rules_graph_iri(graph)
    rows = sparql_query(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    SELECT ?label ?condition ?consequence ?description WHERE {{
      GRAPH <{rules_graph}> {{
        <{rule_iri}> a onto:Rule ;
            onto:condition ?condition ;
            onto:consequence ?consequence .
        OPTIONAL {{ <{rule_iri}> rdfs:label ?label }}
        OPTIONAL {{ <{rule_iri}> rdfs:comment ?description }}
      }}
    }}
    """)
    if not rows:
        raise KeyError(f"Rule not found: {rule_iri}")
    r = rows[0]
    return {
        "rule_iri": rule_iri,
        "label": r.get("label"),
        "condition": r["condition"],
        "consequence": r["consequence"],
        "description": r.get("description"),
    }


def update_rule(
    dataset: str,
    graph: str,
    rule_iri: str,
    label: str | None = None,
    description: str | None = None,
    condition: str | None = None,
    consequence: str | None = None,
) -> dict:
    """
    Rule 수정.

    Raises:
        KeyError: not found (→ 404)
        ValueError: 잘못된 SPARQL (→ 422)
    """
    current = get_rule(dataset, graph, rule_iri)
    rules_graph = _rules_graph_iri(graph)

    if condition is not None:
        _validate_sparql_where(condition, dataset)

    new_label = label if label is not None else current["label"]
    new_description = description if description is not None else current["description"]
    new_condition = condition if condition is not None else current["condition"]
    new_consequence = consequence if consequence is not None else current["consequence"]

    # 기존 트리플 삭제 후 재삽입
    sparql_update(dataset, f"""
    DELETE WHERE {{
      GRAPH <{rules_graph}> {{
        <{rule_iri}> ?p ?o .
      }}
    }}
    """)

    esc_label = _escape_sparql_literal(new_label or "")
    esc_condition = _escape_sparql_literal(new_condition)
    esc_consequence = _escape_sparql_literal(new_consequence)

    desc_triple = ""
    if new_description:
        esc_desc = _escape_sparql_literal(new_description)
        desc_triple = f'<{rule_iri}> rdfs:comment "{esc_desc}" .'

    sparql_update(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    INSERT DATA {{
      GRAPH <{rules_graph}> {{
        <{rule_iri}> a onto:Rule ;
            rdfs:label "{esc_label}" ;
            onto:condition "{esc_condition}" ;
            onto:consequence "{esc_consequence}" .
        {desc_triple}
      }}
    }}
    """)
    return get_rule(dataset, graph, rule_iri)


def delete_rule(dataset: str, graph: str, rule_iri: str) -> dict:
    """
    Rule 삭제.

    Raises:
        KeyError: not found (→ 404)
    """
    get_rule(dataset, graph, rule_iri)  # 존재 확인
    rules_graph = _rules_graph_iri(graph)
    sparql_update(dataset, f"""
    DELETE WHERE {{
      GRAPH <{rules_graph}> {{
        <{rule_iri}> ?p ?o .
      }}
    }}
    """)
    return {"deleted": rule_iri}


# ──────────────────────────────────────────────────────────────────────────────
# Apply / Materialize
# ──────────────────────────────────────────────────────────────────────────────

def apply_rule(dataset: str, graph: str, rule_iri: str) -> dict:
    """
    규칙을 적용하여 추론된 트리플 미리보기를 반환한다.
    SPARQL CONSTRUCT를 사용한다.

    Returns:
        {"inferred_triples": [{"s": ..., "p": ..., "o": ...}, ...]}

    Raises:
        KeyError: rule not found (→ 404)
    """
    rule = get_rule(dataset, graph, rule_iri)
    condition = rule["condition"]
    consequence = rule["consequence"]

    # SPARQL CONSTRUCT 실행
    construct_query = f"""
    CONSTRUCT {{
      {consequence}
    }}
    WHERE {{
      GRAPH <{graph}> {{
        {condition}
      }}
    }}
    """

    endpoint = f"{config_state.base_url()}/{dataset}/sparql"
    user, pw = config_state.auth()

    import httpx
    r = httpx.post(
        endpoint,
        data={"query": construct_query},
        headers={"Accept": "application/n-triples"},
        auth=(user, pw),
        timeout=30,
    )
    r.raise_for_status()

    # N-Triples 파싱
    inferred = []
    for line in r.text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = _parse_ntriple_line(line)
        if parts:
            inferred.append(parts)

    return {"inferred_triples": inferred}


def _parse_ntriple_line(line: str) -> dict | None:
    """N-Triple 한 줄을 {"s": ..., "p": ..., "o": ...}로 파싱."""
    # 마지막 ' .' 제거
    if line.endswith(" ."):
        line = line[:-2].rstrip()
    elif line.endswith("."):
        line = line[:-1].rstrip()

    parts = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == '<':
            end = line.index('>', i)
            parts.append(line[i+1:end])
            i = end + 1
        elif c == '"':
            # literal: collect until closing "
            j = i + 1
            while j < len(line):
                if line[j] == '\\':
                    j += 2
                    continue
                if line[j] == '"':
                    break
                j += 1
            parts.append(line[i:j+1])
            i = j + 1
        elif c == '_':
            # blank node
            end = i
            while end < len(line) and not line[end].isspace():
                end += 1
            parts.append(line[i:end])
            i = end
        elif c.isspace():
            i += 1
        else:
            i += 1

    if len(parts) < 3:
        return None
    return {"s": parts[0], "p": parts[1], "o": parts[2]}


def materialize_rule(dataset: str, graph: str, rule_iri: str) -> dict:
    """
    규칙 결과를 {graph}/materialized 서브그래프에 저장한다.

    Returns:
        {"materialized_graph": ..., "materialized_count": int}

    Raises:
        KeyError: rule not found (→ 404)
    """
    result = apply_rule(dataset, graph, rule_iri)
    inferred = result["inferred_triples"]

    mat_graph = _materialized_graph_iri(graph)

    if not inferred:
        return {"materialized_graph": mat_graph, "materialized_count": 0}

    def _fmt(term: str) -> str:
        if term.startswith("http://") or term.startswith("https://"):
            return f"<{term}>"
        if term.startswith("_:"):
            return term
        return term  # literal (already quoted)

    def _is_valid_subject(s: str) -> bool:
        return (
            s.startswith("http://")
            or s.startswith("https://")
            or s.startswith("_:")
        )

    valid = [t for t in inferred if _is_valid_subject(t["s"])]

    batch_size = 500
    for i in range(0, len(valid), batch_size):
        batch = valid[i:i + batch_size]
        triples_str = "\n    ".join(
            f"{_fmt(t['s'])} {_fmt(t['p'])} {_fmt(t['o'])} ."
            for t in batch
        )
        sparql_update(dataset, f"""
        INSERT DATA {{
          GRAPH <{mat_graph}> {{
            {triples_str}
          }}
        }}
        """)

    return {"materialized_graph": mat_graph, "materialized_count": len(valid)}
