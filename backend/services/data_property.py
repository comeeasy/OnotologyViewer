"""Data Property CRUD 서비스 — SPARQL 기반."""

from fuseki.sparql import query as sparql_query, update as sparql_update
from services.iri import generate_iri
from services.class_ import _esc, _validate_iri

OWL_BASE = "http://www.w3.org/2002/07/owl#"
OWL_FUNCTIONAL = f"{OWL_BASE}FunctionalProperty"

XSD_RANGES = {
    "string":   "http://www.w3.org/2001/XMLSchema#string",
    "integer":  "http://www.w3.org/2001/XMLSchema#integer",
    "float":    "http://www.w3.org/2001/XMLSchema#float",
    "boolean":  "http://www.w3.org/2001/XMLSchema#boolean",
    "dateTime": "http://www.w3.org/2001/XMLSchema#dateTime",
    "anyURI":   "http://www.w3.org/2001/XMLSchema#anyURI",
}

# ────────────────────────────────────────────────
# SPARQL 템플릿
# ────────────────────────────────────────────────

_Q_LIST = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?prop ?label ?domain ?range WHERE {{
  GRAPH <{graph}> {{
    ?prop a owl:DatatypeProperty .
    OPTIONAL {{ ?prop rdfs:label  ?label }}
    OPTIONAL {{ ?prop rdfs:domain ?domain }}
    OPTIONAL {{ ?prop rdfs:range  ?range }}
    FILTER({ns_filter})
  }}
}}
"""

_Q_BASE = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label ?domain ?range WHERE {{
  GRAPH <{graph}> {{
    <{prop_iri}> a owl:DatatypeProperty .
    OPTIONAL {{ <{prop_iri}> rdfs:label  ?label }}
    OPTIONAL {{ <{prop_iri}> rdfs:domain ?domain }}
    OPTIONAL {{ <{prop_iri}> rdfs:range  ?range }}
  }}
}}
"""

_Q_FUNCTIONAL = """
ASK {{
  GRAPH <{graph}> {{
    <{prop_iri}> a <{functional_iri}> .
  }}
}}
"""

_U_INSERT = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

INSERT DATA {{
  GRAPH <{graph}> {{
    <{prop_iri}> a owl:DatatypeProperty ;
      rdfs:label  "{label}" ;
      rdfs:domain <{domain}> ;
      rdfs:range  <{range}> .
    {functional_triple}
  }}
}}
"""

_U_UPD_LABEL = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:label ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:label "{value}" }} }}
WHERE  {{ GRAPH <{graph}> {{ <{prop_iri}> a <{owl_dtype}> .
                              OPTIONAL {{ <{prop_iri}> rdfs:label ?v }} }} }}
"""

_U_UPD_DOMAIN = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:domain ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:domain <{value}> }} }}
WHERE  {{ GRAPH <{graph}> {{ <{prop_iri}> a <{owl_dtype}> .
                              OPTIONAL {{ <{prop_iri}> rdfs:domain ?v }} }} }}
"""

_U_UPD_RANGE = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:range ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:range <{value}> }} }}
WHERE  {{ GRAPH <{graph}> {{ <{prop_iri}> a <{owl_dtype}> .
                              OPTIONAL {{ <{prop_iri}> rdfs:range ?v }} }} }}
"""

_U_ADD_FUNCTIONAL = """
INSERT DATA {{
  GRAPH <{graph}> {{ <{prop_iri}> a <{functional_iri}> . }}
}}
"""

_U_DEL_FUNCTIONAL = """
DELETE WHERE {{
  GRAPH <{graph}> {{ <{prop_iri}> a <{functional_iri}> . }}
}}
"""

_U_DEL_VALUES = """
DELETE {{ GRAPH <{graph}> {{ ?ind <{prop_iri}> ?val }} }}
WHERE  {{ GRAPH <{graph}> {{ ?ind <{prop_iri}> ?val }} }}
"""

_U_DEL_PROP = """
DELETE WHERE {{ GRAPH <{graph}> {{ <{prop_iri}> ?p ?o }} }}
"""

_OWL_DTYPE = f"{OWL_BASE}DatatypeProperty"

# ────────────────────────────────────────────────
# 공개 함수
# ────────────────────────────────────────────────

def _ns_filter(namespaces: list[str]) -> str:
    return " || ".join(f'STRSTARTS(str(?prop), "{ns}")' for ns in namespaces)


def list_data_properties(dataset: str, graph: str, namespace: str | list[str]) -> list[dict]:
    _validate_iri(graph)
    ns_list = [namespace] if isinstance(namespace, str) else list(namespace)
    if not ns_list:
        raise ValueError("namespace는 하나 이상 제공해야 합니다.")
    for ns in ns_list:
        _validate_iri(ns)
    rows = sparql_query(dataset, _Q_LIST.format(graph=graph, ns_filter=_ns_filter(ns_list)))
    return [{"iri": r["prop"], "label": r.get("label"),
             "domain": r.get("domain"), "range": r.get("range")} for r in rows]


def get_data_property_detail(dataset: str, graph: str, prop_iri: str) -> dict | None:
    _validate_iri(graph); _validate_iri(prop_iri)
    base = sparql_query(dataset, _Q_BASE.format(graph=graph, prop_iri=prop_iri))
    if not base:
        return None
    r = base[0]
    # functional 여부: SPARQLWrapper ASK 직접 사용
    from SPARQLWrapper import JSON, SPARQLWrapper
    from config import settings
    sw = SPARQLWrapper(f"{settings.fuseki_base_url}/{dataset}/sparql")
    sw.setHTTPAuth("BASIC")
    sw.setCredentials(settings.fuseki_admin_user, settings.fuseki_admin_password)
    sw.setQuery(_Q_FUNCTIONAL.format(graph=graph, prop_iri=prop_iri, functional_iri=OWL_FUNCTIONAL))
    sw.setReturnFormat(JSON)
    functional = sw.query().convert().get("boolean", False)

    return {
        "iri":        prop_iri,
        "label":      r.get("label"),
        "domain":     r.get("domain"),
        "range":      r.get("range"),
        "functional": functional,
    }


def create_data_property(
    dataset: str,
    graph: str,
    namespace: str,
    label: str,
    domain: str,
    range_xsd: str,
    functional: bool = False,
) -> str:
    """Data Property를 생성하고 신규 IRI를 반환한다."""
    _validate_iri(graph); _validate_iri(namespace); _validate_iri(domain)

    range_iri = XSD_RANGES.get(range_xsd)
    if range_iri is None:
        raise ValueError(f"지원하지 않는 xsd range: {range_xsd!r}. 허용값: {list(XSD_RANGES)}")

    prop_iri = generate_iri(namespace, label, graph)
    func_triple = f"<{prop_iri}> a <{OWL_FUNCTIONAL}> ." if functional else ""
    sparql_update(
        dataset,
        _U_INSERT.format(
            graph=graph, prop_iri=prop_iri,
            label=_esc(label), domain=domain,
            range=range_iri, functional_triple=func_triple,
        ),
    )
    return prop_iri


def update_data_property(
    dataset: str,
    graph: str,
    prop_iri: str,
    label: str | None = None,
    domain: str | None = None,
    range_xsd: str | None = None,
    functional: bool | None = None,
) -> None:
    _validate_iri(graph); _validate_iri(prop_iri)
    fmt = dict(graph=graph, prop_iri=prop_iri, owl_dtype=_OWL_DTYPE)

    if label is not None:
        sparql_update(dataset, _U_UPD_LABEL.format(**fmt, value=_esc(label)))
    if domain is not None:
        _validate_iri(domain)
        sparql_update(dataset, _U_UPD_DOMAIN.format(**fmt, value=domain))
    if range_xsd is not None:
        range_iri = XSD_RANGES.get(range_xsd)
        if range_iri is None:
            raise ValueError(f"지원하지 않는 xsd range: {range_xsd!r}")
        sparql_update(dataset, _U_UPD_RANGE.format(**fmt, value=range_iri))
    if functional is not None:
        if functional:
            sparql_update(dataset, _U_ADD_FUNCTIONAL.format(graph=graph, prop_iri=prop_iri, functional_iri=OWL_FUNCTIONAL))
        else:
            sparql_update(dataset, _U_DEL_FUNCTIONAL.format(graph=graph, prop_iri=prop_iri, functional_iri=OWL_FUNCTIONAL))


def delete_data_property(dataset: str, graph: str, prop_iri: str) -> None:
    _validate_iri(graph); _validate_iri(prop_iri)
    sparql_update(dataset, _U_DEL_VALUES.format(graph=graph, prop_iri=prop_iri))
    sparql_update(dataset, _U_DEL_PROP.format(graph=graph, prop_iri=prop_iri))
