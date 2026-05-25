"""Individual (ABox) CRUD 서비스 — SPARQL 기반."""

from fuseki.sparql import query as sparql_query, query_with_types, update as sparql_update
from services.iri import generate_iri
from services.class_ import _esc, _validate_iri, graph_values_clause

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

# ────────────────────────────────────────────────
# SPARQL 템플릿
# ────────────────────────────────────────────────

_Q_LIST = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?_g ?ind ?label ?class WHERE {{
  {graph_values}
  GRAPH ?_g {{
    ?ind  a      ?class .
    ?class a     owl:Class .
    FILTER(isIRI(?ind))
    FILTER({ns_filter})
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

_Q_LABELS_BATCH = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?iri ?label WHERE {{
  GRAPH <{graph}> {{
    VALUES ?iri {{ {iris} }}
    OPTIONAL {{ ?iri rdfs:label ?label }}
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

def _ns_filter(namespaces: list[str]) -> str:
    return " || ".join(f'STRSTARTS(str(?ind), "{ns}")' for ns in namespaces)


def list_individuals(
    dataset: str,
    graphs: str | list[str],
    namespace: str | list[str],
    class_iri: str | None = None,
) -> list[dict]:
    graph_list = [graphs] if isinstance(graphs, str) else list(graphs)
    for g in graph_list:
        _validate_iri(g)
    ns_list = [namespace] if isinstance(namespace, str) else list(namespace)
    if not ns_list:
        raise ValueError("namespace는 하나 이상 제공해야 합니다.")
    for ns in ns_list:
        _validate_iri(ns)
    if class_iri:
        _validate_iri(class_iri)
        class_filter = f'FILTER(?class = <{class_iri}>)'
    else:
        class_filter = ""
    rows = sparql_query(dataset, _Q_LIST.format(
        graph_values=graph_values_clause(graph_list),
        ns_filter=_ns_filter(ns_list),
        class_filter=class_filter,
    ))
    return [
        {"source_graph": r.get("_g"), "iri": r["ind"], "label": r.get("label"), "class_iri": r["class"]}
        for r in rows
    ]


def get_individual_detail(dataset: str, graph: str, ind_iri: str) -> dict | None:
    _validate_iri(graph); _validate_iri(ind_iri)
    base = sparql_query(dataset, _Q_BASE.format(graph=graph, ind_iri=ind_iri))
    if not base:
        return None
    r = base[0]

    out_rows_raw = query_with_types(dataset, _Q_OUTGOING.format(graph=graph, ind_iri=ind_iri))
    outgoing = []
    for row in out_rows_raw:
        prop = row["prop"]["value"]
        val_binding = row["value"]
        val_type = val_binding.get("type", "")
        val_value = val_binding["value"]
        if val_type == "uri":
            outgoing.append({"property": prop, "value": val_value, "value_type": "iri", "datatype": None})
        else:
            # literal or typed-literal
            raw_dt = val_binding.get("datatype", "http://www.w3.org/2001/XMLSchema#string")
            # shortname 변환: .../XMLSchema#integer → integer
            dt_short = raw_dt.split("#")[-1] if "#" in raw_dt else raw_dt.split("/")[-1]
            outgoing.append({"property": prop, "value": val_value, "value_type": "literal", "datatype": dt_short})

    in_rows = sparql_query(dataset, _Q_INCOMING.format(graph=graph, ind_iri=ind_iri))
    incoming = [{"subject": row["subj"], "property": row["prop"]} for row in in_rows]

    # ── IRI 값들의 label 배치 조회 ──────────────────────────
    iri_values  = [o["value"] for o in outgoing if o["value_type"] == "iri"]
    iri_subjects = [i["subject"] for i in incoming]
    all_iris = list(set(iri_values + iri_subjects))
    label_map: dict[str, str | None] = {}
    if all_iris:
        iris_str = " ".join(f"<{iri}>" for iri in all_iris)
        try:
            lb_rows = sparql_query(dataset, _Q_LABELS_BATCH.format(graph=graph, iris=iris_str))
            label_map = {row["iri"]: row.get("label") for row in lb_rows}
        except Exception:
            pass  # label 조회 실패 시 무시

    for o in outgoing:
        o["value_label"] = label_map.get(o["value"]) if o["value_type"] == "iri" else None
    for i in incoming:
        i["subject_label"] = label_map.get(i["subject"])

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


# ── v02-E: Class 마이그레이션 ────────────────────────────────────────────

_Q_IND_CLASS = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?class WHERE {{
  GRAPH <{graph}> {{
    <{ind_iri}> rdf:type ?class .
    ?class a owl:Class .
  }}
}} LIMIT 1
"""

_Q_CLASS_EXISTS = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
ASK {{ GRAPH <{graph}> {{ <{class_iri}> a owl:Class . }} }}
"""

_Q_INCOMPATIBLE_PROPS = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?prop WHERE {{
  GRAPH <{graph}> {{
    <{ind_iri}> ?prop ?val .
    FILTER(?prop NOT IN (
      <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>,
      <http://www.w3.org/2000/01/rdf-schema#label>,
      <http://www.w3.org/2000/01/rdf-schema#comment>
    ))
    ?prop rdfs:domain <{old_class}> .
    FILTER NOT EXISTS {{
      ?prop rdfs:domain <{new_class}> .
    }}
  }}
}}
"""

_U_CHANGE_CLASS = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
DELETE {{ GRAPH <{graph}> {{ <{ind_iri}> rdf:type <{old_class}> }} }}
INSERT {{ GRAPH <{graph}> {{ <{ind_iri}> rdf:type <{new_class}> }} }}
WHERE  {{ GRAPH <{graph}> {{ <{ind_iri}> rdf:type <{old_class}> }} }}
"""

_U_DEL_PROP_VALUES = """
DELETE {{ GRAPH <{graph}> {{ <{ind_iri}> <{prop_iri}> ?v }} }}
WHERE  {{ GRAPH <{graph}> {{ <{ind_iri}> <{prop_iri}> ?v }} }}
"""


def _class_exists(dataset: str, graph: str, class_iri: str) -> bool:
    from SPARQLWrapper import JSON, SPARQLWrapper
    import config_state
    sw = SPARQLWrapper(f"{config_state.base_url()}/{dataset}/sparql")
    user, pw = config_state.auth()
    sw.setHTTPAuth("BASIC"); sw.setCredentials(user, pw)
    sw.setQuery(_Q_CLASS_EXISTS.format(graph=graph, class_iri=class_iri))
    sw.setReturnFormat(JSON)
    res = sw.query().convert()
    return bool(res.get("boolean", False))


def get_incompatible_properties(
    dataset: str, graph: str, ind_iri: str,
    old_class: str, new_class: str,
) -> list[str]:
    """Individual이 사용하는 property 중 new_class에 도메인 없는 것들 반환."""
    rows = sparql_query(dataset, _Q_INCOMPATIBLE_PROPS.format(
        graph=graph, ind_iri=ind_iri,
        old_class=old_class, new_class=new_class,
    ))
    return [r["prop"] for r in rows]


def migrate_individual_class(
    dataset: str,
    graph: str,
    ind_iri: str,
    new_class_iri: str,
    incompatible_props: str,  # "keep" | "delete"
) -> dict:
    """
    Individual의 rdf:type을 new_class_iri로 변경한다.

    incompatible_props:
        "keep"   — 비호환 property 값 보존 (OWL 비준수 가능)
        "delete" — 비호환 property 값 삭제

    Returns:
        {"old_class_iri": ..., "new_class_iri": ..., "deleted_properties": [...]}

    Raises:
        KeyError: Individual 또는 Class가 존재하지 않음 (→ 404)
        ValueError: 잘못된 IRI (→ 422)
    """
    _validate_iri(graph); _validate_iri(ind_iri); _validate_iri(new_class_iri)

    # Individual 존재 확인
    detail = get_individual_detail(dataset, graph, ind_iri)
    if detail is None:
        raise KeyError(f"Individual not found: {ind_iri}")

    old_class = detail["class_iri"]

    # 새 Class 존재 확인
    if not _class_exists(dataset, graph, new_class_iri):
        raise KeyError(f"Class not found: {new_class_iri}")

    # 비호환 property 찾기
    incompat = get_incompatible_properties(dataset, graph, ind_iri, old_class, new_class_iri)

    # 비호환 property 삭제 (delete 옵션)
    deleted = []
    if incompatible_props == "delete":
        for prop in incompat:
            sparql_update(dataset, _U_DEL_PROP_VALUES.format(
                graph=graph, ind_iri=ind_iri, prop_iri=prop,
            ))
            deleted.append(prop)

    # rdf:type 교체
    sparql_update(dataset, _U_CHANGE_CLASS.format(
        graph=graph, ind_iri=ind_iri,
        old_class=old_class, new_class=new_class_iri,
    ))

    return {
        "old_class_iri": old_class,
        "new_class_iri": new_class_iri,
        "deleted_properties": deleted,
    }
