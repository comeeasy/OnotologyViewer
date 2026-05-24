"""Object Property CRUD 서비스 — SPARQL 기반."""

from fuseki.sparql import query as sparql_query, update as sparql_update
from services.iri import generate_iri
from services.class_ import _esc, _validate_iri

# ────────────────────────────────────────────────
# Characteristics 매핑
# ────────────────────────────────────────────────

OWL_BASE = "http://www.w3.org/2002/07/owl#"

CHARACTERISTICS: dict[str, str] = {
    "Functional":        f"{OWL_BASE}FunctionalProperty",
    "InverseFunctional": f"{OWL_BASE}InverseFunctionalProperty",
    "Transitive":        f"{OWL_BASE}TransitiveProperty",
    "Symmetric":         f"{OWL_BASE}SymmetricProperty",
    "Asymmetric":        f"{OWL_BASE}AsymmetricProperty",
    "Reflexive":         f"{OWL_BASE}ReflexiveProperty",
    "Irreflexive":       f"{OWL_BASE}IrreflexiveProperty",
}
_CHAR_IRI_TO_NAME = {v: k for k, v in CHARACTERISTICS.items()}

# ────────────────────────────────────────────────
# SPARQL 템플릿
# ────────────────────────────────────────────────

_Q_LIST = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?prop ?label ?domain ?range WHERE {{
  GRAPH <{graph}> {{
    ?prop a owl:ObjectProperty .
    OPTIONAL {{ ?prop rdfs:label  ?label }}
    OPTIONAL {{ ?prop rdfs:domain ?domain }}
    OPTIONAL {{ ?prop rdfs:range  ?range }}
    FILTER(STRSTARTS(str(?prop), "{namespace}"))
  }}
}}
"""

_Q_BASE = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label ?domain ?range WHERE {{
  GRAPH <{graph}> {{
    <{prop_iri}> a owl:ObjectProperty .
    OPTIONAL {{ <{prop_iri}> rdfs:label  ?label }}
    OPTIONAL {{ <{prop_iri}> rdfs:domain ?domain }}
    OPTIONAL {{ <{prop_iri}> rdfs:range  ?range }}
  }}
}}
"""

_Q_CHARS = """
SELECT ?char WHERE {{
  GRAPH <{graph}> {{
    <{prop_iri}> a ?char .
    FILTER(?char != <http://www.w3.org/2002/07/owl#ObjectProperty>)
    FILTER(STRSTARTS(str(?char), "http://www.w3.org/2002/07/owl#"))
  }}
}}
"""

_U_INSERT = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

INSERT DATA {{
  GRAPH <{graph}> {{
    <{prop_iri}> a owl:ObjectProperty ;
      rdfs:label "{label}" .
    {domain_triple}
    {range_triple}
    {char_triples}
  }}
}}
"""

_U_UPD_LABEL = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:label ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:label "{value}" }} }}
WHERE  {{ GRAPH <{graph}> {{ <{prop_iri}> a <http://www.w3.org/2002/07/owl#ObjectProperty> .
                              OPTIONAL {{ <{prop_iri}> rdfs:label ?v }} }} }}
"""

_U_UPD_DOMAIN = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:domain ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:domain <{value}> }} }}
WHERE  {{ GRAPH <{graph}> {{ <{prop_iri}> a <http://www.w3.org/2002/07/owl#ObjectProperty> .
                              OPTIONAL {{ <{prop_iri}> rdfs:domain ?v }} }} }}
"""

_U_UPD_RANGE = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:range ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{prop_iri}> rdfs:range <{value}> }} }}
WHERE  {{ GRAPH <{graph}> {{ <{prop_iri}> a <http://www.w3.org/2002/07/owl#ObjectProperty> .
                              OPTIONAL {{ <{prop_iri}> rdfs:range ?v }} }} }}
"""

_U_DEL_CHARS = """
DELETE {{ GRAPH <{graph}> {{ <{prop_iri}> a ?char }} }}
WHERE  {{
  GRAPH <{graph}> {{
    <{prop_iri}> a ?char .
    FILTER(?char != <http://www.w3.org/2002/07/owl#ObjectProperty>)
    FILTER(STRSTARTS(str(?char), "http://www.w3.org/2002/07/owl#"))
  }}
}}
"""

_U_INS_CHARS = """
INSERT DATA {{
  GRAPH <{graph}> {{
    {char_triples}
  }}
}}
"""

# Delete 단계
_U_DEL_RELATIONS = """
DELETE {{ GRAPH <{graph}> {{ ?s <{prop_iri}> ?o }} }}
WHERE  {{ GRAPH <{graph}> {{ ?s <{prop_iri}> ?o }} }}
"""

_U_DEL_PROP = """
DELETE WHERE {{ GRAPH <{graph}> {{ <{prop_iri}> ?p ?o }} }}
"""


# ────────────────────────────────────────────────
# 헬퍼
# ────────────────────────────────────────────────

def _char_triples(prop_iri: str, characteristics: list[str]) -> str:
    lines = []
    for name in characteristics:
        iri = CHARACTERISTICS.get(name)
        if iri is None:
            raise ValueError(f"알 수 없는 characteristic: {name!r}")
        lines.append(f"    <{prop_iri}> a <{iri}> .")
    return "\n".join(lines)


# ────────────────────────────────────────────────
# 공개 함수
# ────────────────────────────────────────────────

def list_object_properties(dataset: str, graph: str, namespace: str) -> list[dict]:
    _validate_iri(graph); _validate_iri(namespace)
    rows = sparql_query(dataset, _Q_LIST.format(graph=graph, namespace=namespace))
    return [
        {
            "iri":    r["prop"],
            "label":  r.get("label"),
            "domain": r.get("domain"),
            "range":  r.get("range"),
        }
        for r in rows
    ]


def get_object_property_detail(dataset: str, graph: str, prop_iri: str) -> dict | None:
    _validate_iri(graph); _validate_iri(prop_iri)
    base = sparql_query(dataset, _Q_BASE.format(graph=graph, prop_iri=prop_iri))
    if not base:
        return None
    r = base[0]
    chars_rows = sparql_query(dataset, _Q_CHARS.format(graph=graph, prop_iri=prop_iri))
    characteristics = [
        _CHAR_IRI_TO_NAME[row["char"]]
        for row in chars_rows
        if row["char"] in _CHAR_IRI_TO_NAME
    ]
    return {
        "iri":             prop_iri,
        "label":           r.get("label"),
        "domain":          r.get("domain"),
        "range":           r.get("range"),
        "characteristics": characteristics,
    }


def create_object_property(
    dataset: str,
    graph: str,
    namespace: str,
    label: str,
    domain: str | None = None,
    range_: str | None = None,
    characteristics: list[str] | None = None,
) -> str:
    _validate_iri(graph); _validate_iri(namespace)
    if domain: _validate_iri(domain)
    if range_: _validate_iri(range_)
    characteristics = characteristics or []

    prop_iri = generate_iri(namespace, label, graph)
    char_block = _char_triples(prop_iri, characteristics)
    domain_triple = f"<{prop_iri}> rdfs:domain <{domain}> ." if domain else ""
    range_triple  = f"<{prop_iri}> rdfs:range  <{range_}> ." if range_ else ""

    sparql_update(
        dataset,
        _U_INSERT.format(
            graph=graph,
            prop_iri=prop_iri,
            label=_esc(label),
            domain_triple=domain_triple,
            range_triple=range_triple,
            char_triples=char_block,
        ),
    )
    return prop_iri


def update_object_property(
    dataset: str,
    graph: str,
    prop_iri: str,
    label: str | None = None,
    domain: str | None = None,
    range_: str | None = None,
    characteristics: list[str] | None = None,
) -> None:
    _validate_iri(graph); _validate_iri(prop_iri)
    fmt = dict(graph=graph, prop_iri=prop_iri)

    if label is not None:
        sparql_update(dataset, _U_UPD_LABEL.format(**fmt, value=_esc(label)))
    if domain is not None:
        _validate_iri(domain)
        sparql_update(dataset, _U_UPD_DOMAIN.format(**fmt, value=domain))
    if range_ is not None:
        _validate_iri(range_)
        sparql_update(dataset, _U_UPD_RANGE.format(**fmt, value=range_))
    if characteristics is not None:
        char_block = "\n".join(
            f"    <{prop_iri}> a <{CHARACTERISTICS[n]}> ."
            for n in characteristics
            if n in CHARACTERISTICS
        )
        sparql_update(dataset, _U_DEL_CHARS.format(**fmt))
        if char_block:
            sparql_update(dataset, _U_INS_CHARS.format(
                graph=graph, char_triples=char_block
            ))


def delete_object_property(dataset: str, graph: str, prop_iri: str) -> None:
    _validate_iri(graph); _validate_iri(prop_iri)
    fmt = dict(graph=graph, prop_iri=prop_iri)
    sparql_update(dataset, _U_DEL_RELATIONS.format(**fmt))
    sparql_update(dataset, _U_DEL_PROP.format(**fmt))
