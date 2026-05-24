"""Individual (ABox) CRUD 서비스 — SPARQL 기반."""

from fuseki.sparql import query as sparql_query, update as sparql_update
from services.iri import generate_iri
from services.class_ import _esc, _validate_iri

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

# ────────────────────────────────────────────────
# SPARQL 템플릿
# ────────────────────────────────────────────────

_Q_LIST = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?ind ?label ?class WHERE {{
  GRAPH <{graph}> {{
    ?ind  a      ?class .
    ?class a     owl:Class .
    FILTER(isIRI(?ind))
    FILTER(STRSTARTS(str(?ind), "{namespace}"))
    OPTIONAL {{ ?ind rdfs:label ?label }}
    {class_filter}
  }}
}}
"""

_Q_BASE = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?class ?label ?comment WHERE {{
  GRAPH <{graph}> {{
    <{ind_iri}> a ?class .
    FILTER(isIRI(?class))
    OPTIONAL {{ <{ind_iri}> rdfs:label   ?label }}
    OPTIONAL {{ <{ind_iri}> rdfs:comment ?comment }}
  }}
}}
"""

_Q_OUTGOING = """
SELECT ?prop ?value WHERE {{
  GRAPH <{graph}> {{
    <{ind_iri}> ?prop ?value .
    FILTER(?prop != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
  }}
}}
"""

_Q_INCOMING = """
SELECT ?subj ?prop WHERE {{
  GRAPH <{graph}> {{
    ?subj ?prop <{ind_iri}> .
    FILTER(isIRI(?subj))
  }}
}}
"""

_U_INSERT_BASE = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

INSERT DATA {{
  GRAPH <{graph}> {{
    <{ind_iri}> a <{class_iri}> ;
      rdfs:label "{label}" .
    {comment_triple}
    {extra_triples}
  }}
}}
"""

_U_UPD_LABEL = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE {{ GRAPH <{graph}> {{ <{ind_iri}> rdfs:label ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{ind_iri}> rdfs:label "{value}" }} }}
WHERE  {{ GRAPH <{graph}> {{ <{ind_iri}> a ?c .
                              OPTIONAL {{ <{ind_iri}> rdfs:label ?v }} }} }}
"""

_U_UPD_COMMENT = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
DELETE {{ GRAPH <{graph}> {{ <{ind_iri}> rdfs:comment ?v }} }}
INSERT {{ GRAPH <{graph}> {{ <{ind_iri}> rdfs:comment "{value}" }} }}
WHERE  {{ GRAPH <{graph}> {{ <{ind_iri}> a ?c .
                              OPTIONAL {{ <{ind_iri}> rdfs:comment ?v }} }} }}
"""

_U_DEL_DP_VALUE = """
DELETE {{ GRAPH <{graph}> {{ <{ind_iri}> <{prop_iri}> ?v }} }}
WHERE  {{ GRAPH <{graph}> {{ <{ind_iri}> <{prop_iri}> ?v }} }}
"""

_U_INS_DP_VALUE = """
INSERT DATA {{
  GRAPH <{graph}> {{
    <{ind_iri}> <{prop_iri}> "{value}"^^<{datatype_iri}> .
  }}
}}
"""

_U_INS_OP_VALUE = """
INSERT DATA {{
  GRAPH <{graph}> {{
    <{ind_iri}> <{prop_iri}> <{target_iri}> .
  }}
}}
"""

_U_DEL_OP_VALUE = """
DELETE DATA {{
  GRAPH <{graph}> {{
    <{ind_iri}> <{prop_iri}> <{target_iri}> .
  }}
}}
"""

_U_DEL_OUTGOING = """
DELETE WHERE {{ GRAPH <{graph}> {{ <{ind_iri}> ?p ?o }} }}
"""

_U_DEL_INCOMING = """
DELETE WHERE {{ GRAPH <{graph}> {{ ?s ?p <{ind_iri}> }} }}
"""

# ────────────────────────────────────────────────
# 헬퍼
# ────────────────────────────────────────────────

def _datatype_iri(xsd_short: str) -> str:
    from services.data_property import XSD_RANGES
    iri = XSD_RANGES.get(xsd_short)
    if iri is None:
        raise ValueError(f"지원하지 않는 xsd datatype: {xsd_short!r}")
    return iri


# ────────────────────────────────────────────────
# 공개 함수
# ────────────────────────────────────────────────

def list_individuals(
    dataset: str,
    graph: str,
    namespace: str,
    class_iri: str | None = None,
) -> list[dict]:
    _validate_iri(graph); _validate_iri(namespace)
    if class_iri:
        _validate_iri(class_iri)
        class_filter = f'FILTER(?class = <{class_iri}>)'
    else:
        class_filter = ""
    rows = sparql_query(dataset, _Q_LIST.format(
        graph=graph, namespace=namespace, class_filter=class_filter
    ))
    return [
        {"iri": r["ind"], "label": r.get("label"), "class_iri": r["class"]}
        for r in rows
    ]


def get_individual_detail(dataset: str, graph: str, ind_iri: str) -> dict | None:
    _validate_iri(graph); _validate_iri(ind_iri)
    base = sparql_query(dataset, _Q_BASE.format(graph=graph, ind_iri=ind_iri))
    if not base:
        return None
    r = base[0]

    out_rows = sparql_query(dataset, _Q_OUTGOING.format(graph=graph, ind_iri=ind_iri))
    outgoing = [
        {
            "property":  row["prop"],
            "value":     row["value"],
            "value_type": "iri" if row["value"].startswith("http") else "literal",
        }
        for row in out_rows
    ]

    in_rows = sparql_query(dataset, _Q_INCOMING.format(graph=graph, ind_iri=ind_iri))
    incoming = [{"subject": row["subj"], "property": row["prop"]} for row in in_rows]

    return {
        "iri":       ind_iri,
        "class_iri": r["class"],
        "label":     r.get("label"),
        "comment":   r.get("comment"),
        "outgoing":  outgoing,
        "incoming":  incoming,
    }


def create_individual(
    dataset: str,
    graph: str,
    namespace: str,
    class_iri: str,
    label: str,
    comment: str | None = None,
    iri: str | None = None,
    data_properties: list[dict] | None = None,
    object_properties: list[dict] | None = None,
) -> str:
    """
    Individual을 생성하고 IRI를 반환한다.

    data_properties:   [{"property_iri": ..., "value": ..., "datatype": "string"|...}]
    object_properties: [{"property_iri": ..., "target_iri": ...}]
    """
    _validate_iri(graph); _validate_iri(namespace); _validate_iri(class_iri)

    ind_iri = iri if iri else generate_iri(namespace, label, graph)
    _validate_iri(ind_iri)

    comment_triple = f'<{ind_iri}> <http://www.w3.org/2000/01/rdf-schema#comment> "{_esc(comment)}" .' if comment else ""

    extra = []
    for dp in (data_properties or []):
        _validate_iri(dp["property_iri"])
        dtype = _datatype_iri(dp["datatype"])
        extra.append(f'<{ind_iri}> <{dp["property_iri"]}> "{_esc(str(dp["value"]))}"^^<{dtype}> .')

    for op in (object_properties or []):
        _validate_iri(op["property_iri"]); _validate_iri(op["target_iri"])
        extra.append(f'<{ind_iri}> <{op["property_iri"]}> <{op["target_iri"]}> .')

    sparql_update(
        dataset,
        _U_INSERT_BASE.format(
            graph=graph, ind_iri=ind_iri, class_iri=class_iri,
            label=_esc(label),
            comment_triple=comment_triple,
            extra_triples="\n    ".join(extra),
        ),
    )
    return ind_iri


def update_individual(
    dataset: str,
    graph: str,
    ind_iri: str,
    label: str | None = None,
    comment: str | None = None,
    data_property_updates: list[dict] | None = None,
    object_property_updates: list[dict] | None = None,
) -> None:
    """
    Individual의 label, comment, data property 값, object property 관계를 수정한다.

    data_property_updates:   [{"property_iri": ..., "value": ..., "datatype": ...}]
    object_property_updates: [{"property_iri": ..., "target_iri": ..., "action": "add" | "remove"}]
    """
    _validate_iri(graph); _validate_iri(ind_iri)

    if label is not None:
        sparql_update(dataset, _U_UPD_LABEL.format(graph=graph, ind_iri=ind_iri, value=_esc(label)))
    if comment is not None:
        sparql_update(dataset, _U_UPD_COMMENT.format(graph=graph, ind_iri=ind_iri, value=_esc(comment)))
    for upd in (data_property_updates or []):
        _validate_iri(upd["property_iri"])
        dtype = _datatype_iri(upd["datatype"])
        sparql_update(dataset, _U_DEL_DP_VALUE.format(graph=graph, ind_iri=ind_iri, prop_iri=upd["property_iri"]))
        sparql_update(dataset, _U_INS_DP_VALUE.format(
            graph=graph, ind_iri=ind_iri,
            prop_iri=upd["property_iri"],
            value=_esc(str(upd["value"])),
            datatype_iri=dtype,
        ))
    for upd in (object_property_updates or []):
        _validate_iri(upd["property_iri"]); _validate_iri(upd["target_iri"])
        action = upd.get("action", "add")
        if action == "add":
            sparql_update(dataset, _U_INS_OP_VALUE.format(
                graph=graph, ind_iri=ind_iri,
                prop_iri=upd["property_iri"],
                target_iri=upd["target_iri"],
            ))
        elif action == "remove":
            sparql_update(dataset, _U_DEL_OP_VALUE.format(
                graph=graph, ind_iri=ind_iri,
                prop_iri=upd["property_iri"],
                target_iri=upd["target_iri"],
            ))
        else:
            raise ValueError(f"object_property_updates action은 'add' 또는 'remove'여야 합니다: {action!r}")


def delete_individual(dataset: str, graph: str, ind_iri: str) -> None:
    """Individual 삭제 — outgoing 후 incoming 순서로 제거."""
    _validate_iri(graph); _validate_iri(ind_iri)
    sparql_update(dataset, _U_DEL_INCOMING.format(graph=graph, ind_iri=ind_iri))
    sparql_update(dataset, _U_DEL_OUTGOING.format(graph=graph, ind_iri=ind_iri))
