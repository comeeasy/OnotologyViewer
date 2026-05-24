"""v02-C Namespace CRUD — 선언, prefix 수정, IRI 일괄 치환, 삭제."""

from fuseki.sparql import query as sparql_query, update as sparql_update

_VANN = "http://purl.org/vocab/vann/"
_OWL  = "http://www.w3.org/2002/07/owl#"


# ── SPARQL templates ──────────────────────────────────────────────────────

_Q_IS_DECLARED = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX vann: <http://purl.org/vocab/vann/>
ASK {{
  GRAPH <{graph}> {{
    <{ns_iri}> a owl:Ontology .
    <{ns_iri}> vann:preferredNamespacePrefix ?p .
  }}
}}
"""

_Q_GET_DECL = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX vann: <http://purl.org/vocab/vann/>
SELECT ?prefix WHERE {{
  GRAPH <{graph}> {{
    <{ns_iri}> a owl:Ontology ;
               vann:preferredNamespacePrefix ?prefix .
  }}
}}
"""

_U_DECLARE = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX vann: <http://purl.org/vocab/vann/>
INSERT DATA {{
  GRAPH <{graph}> {{
    <{ns_iri}> a owl:Ontology .
    <{ns_iri}> vann:preferredNamespacePrefix "{prefix}" .
  }}
}}
"""

_U_UPDATE_PREFIX = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX vann: <http://purl.org/vocab/vann/>
DELETE {{ GRAPH <{graph}> {{ <{ns_iri}> vann:preferredNamespacePrefix ?p }} }}
INSERT {{ GRAPH <{graph}> {{ <{ns_iri}> vann:preferredNamespacePrefix "{new_prefix}" }} }}
WHERE  {{
  GRAPH <{graph}> {{
    <{ns_iri}> a owl:Ontology ;
               vann:preferredNamespacePrefix ?p .
  }}
}}
"""

_Q_AFFECTED_SUBJECTS = """
SELECT DISTINCT ?s WHERE {{
  GRAPH <{graph}> {{
    ?s ?p ?o .
    FILTER(STRSTARTS(str(?s), "{old_ns}"))
  }}
}}
"""

_Q_AFFECTED_OBJECTS = """
SELECT DISTINCT ?o WHERE {{
  GRAPH <{graph}> {{
    ?s ?p ?o .
    FILTER(STRSTARTS(str(?o), "{old_ns}") && isIRI(?o))
  }}
}}
"""

_Q_COUNT_AFFECTED = """
SELECT (COUNT(*) AS ?cnt) WHERE {{
  GRAPH <{graph}> {{
    {{
      ?s ?p ?o .
      FILTER(STRSTARTS(str(?s), "{old_ns}"))
    }}
    UNION
    {{
      ?s ?p ?o .
      FILTER(STRSTARTS(str(?o), "{old_ns}") && isIRI(?o))
    }}
  }}
}}
"""

# subject 위치 rename: SPARQL 1.1 SUBSTR (1-based index)
_U_RENAME_SUBJECTS = """
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
DELETE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}
INSERT {{ GRAPH <{graph}> {{ ?new_s ?p ?o }} }}
WHERE {{
  GRAPH <{graph}> {{
    ?s ?p ?o .
    FILTER(STRSTARTS(str(?s), "{old_ns}"))
    BIND(IRI(CONCAT("{new_ns}", SUBSTR(str(?s), {suffix_start}))) AS ?new_s)
  }}
}}
"""

# object 위치 rename (IRI only)
_U_RENAME_OBJECTS = """
DELETE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}
INSERT {{ GRAPH <{graph}> {{ ?s ?p ?new_o }} }}
WHERE {{
  GRAPH <{graph}> {{
    ?s ?p ?o .
    FILTER(STRSTARTS(str(?o), "{old_ns}") && isIRI(?o))
    BIND(IRI(CONCAT("{new_ns}", SUBSTR(str(?o), {suffix_start}))) AS ?new_o)
  }}
}}
"""

_U_DELETE_NS_SUBJECTS = """
DELETE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}
WHERE {{
  GRAPH <{graph}> {{
    ?s ?p ?o .
    FILTER(STRSTARTS(str(?s), "{ns_iri}"))
  }}
}}
"""


# ── Public API ────────────────────────────────────────────────────────────

def is_declared(dataset: str, graph: str, ns_iri: str) -> bool:
    """namespace가 graph에 명시적으로 선언되어 있는지 확인."""
    rows = sparql_query(dataset, _Q_IS_DECLARED.format(graph=graph, ns_iri=ns_iri))
    # ASK returns boolean — SPARQLWrapper returns {"boolean": True/False}
    # but our query() flattens SELECT results. Use raw approach:
    from SPARQLWrapper import JSON, SPARQLWrapper
    import config_state
    sw = SPARQLWrapper(f"{config_state.base_url()}/{dataset}/sparql")
    user, pw = config_state.auth()
    sw.setHTTPAuth("BASIC")
    sw.setCredentials(user, pw)
    sw.setQuery(_Q_IS_DECLARED.format(graph=graph, ns_iri=ns_iri))
    sw.setReturnFormat(JSON)
    res = sw.query().convert()
    return bool(res.get("boolean", False))


def declare_namespace(dataset: str, graph: str, ns_iri: str, prefix: str) -> dict:
    """
    graph 에 namespace 선언 트리플을 삽입한다.

    Returns:
        {"ns_iri": ..., "prefix": ...}

    Raises:
        ValueError: 이미 선언된 namespace (→ 409)
    """
    if is_declared(dataset, graph, ns_iri):
        raise ValueError(f"Namespace already declared: {ns_iri}")
    sparql_update(dataset, _U_DECLARE.format(graph=graph, ns_iri=ns_iri, prefix=prefix))
    return {"ns_iri": ns_iri, "prefix": prefix}


def update_prefix(dataset: str, graph: str, ns_iri: str, new_prefix: str) -> dict:
    """
    namespace 의 prefix 선언 트리플을 교체한다.

    Raises:
        KeyError: 선언되지 않은 namespace (→ 404)
    """
    if not is_declared(dataset, graph, ns_iri):
        raise KeyError(f"Namespace not declared: {ns_iri}")
    sparql_update(dataset, _U_UPDATE_PREFIX.format(
        graph=graph, ns_iri=ns_iri, new_prefix=new_prefix,
    ))
    return {"ns_iri": ns_iri, "prefix": new_prefix}


def preview_rename(dataset: str, graph: str, old_ns: str, new_ns: str) -> dict:
    """
    IRI 치환 시 영향받는 triple 수를 미리 집계한다. (읽기 전용)

    Returns:
        {"affected_triples": int}
    """
    rows = sparql_query(dataset, _Q_COUNT_AFFECTED.format(graph=graph, old_ns=old_ns))
    cnt = int(rows[0]["cnt"]) if rows else 0
    return {"affected_triples": cnt, "old_ns": old_ns, "new_ns": new_ns}


def rename_namespace(dataset: str, graph: str, old_ns: str, new_ns: str) -> dict:
    """
    graph 내에서 old_ns로 시작하는 모든 subject/object IRI를 new_ns 기반으로 교체한다.

    SPARQL SUBSTR은 1-based 이므로 suffix_start = len(old_ns) + 1.

    Returns:
        {"old_ns": ..., "new_ns": ..., "affected_triples": int}
    """
    # 영향받는 triple 수 미리 계산
    preview = preview_rename(dataset, graph, old_ns, new_ns)
    affected = preview["affected_triples"]

    suffix_start = len(old_ns) + 1  # SPARQL SUBSTR 1-based

    # 1) subject 위치 rename
    sparql_update(dataset, _U_RENAME_SUBJECTS.format(
        graph=graph, old_ns=old_ns, new_ns=new_ns, suffix_start=suffix_start,
    ))

    # 2) object 위치 rename (IRI only)
    sparql_update(dataset, _U_RENAME_OBJECTS.format(
        graph=graph, old_ns=old_ns, new_ns=new_ns, suffix_start=suffix_start,
    ))

    return {"old_ns": old_ns, "new_ns": new_ns, "affected_triples": affected}


def delete_namespace(dataset: str, graph: str, ns_iri: str) -> None:
    """
    namespace 선언 트리플 + 해당 namespace의 모든 subject 트리플을 삭제한다.

    Raises:
        KeyError: 선언되지 않은 namespace (→ 404)
    """
    if not is_declared(dataset, graph, ns_iri):
        raise KeyError(f"Namespace not declared: {ns_iri}")
    # ns_iri 로 시작하는 모든 subject 트리플 삭제 (선언 트리플 포함)
    sparql_update(dataset, _U_DELETE_NS_SUBJECTS.format(graph=graph, ns_iri=ns_iri))
