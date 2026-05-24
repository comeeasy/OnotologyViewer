"""v03-C Datasource Service — Datasource 매핑 관리."""

import uuid
from fuseki.sparql import query as sparql_query, update as sparql_update

ONTO_NS = "http://ontologyviewer.io/ontology/datasource#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"

SUPPORTED_TYPES = {"csv", "json", "rest", "sparql"}


def _ds_graph_iri(graph: str) -> str:
    return f"{graph}/datasources"


def _gen_iri(base: str, suffix: str) -> str:
    uid = uuid.uuid4().hex
    if base.endswith("#") or base.endswith("/"):
        return f"{base}{suffix}_{uid}"
    return f"{base}/{suffix}_{uid}"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# ──────────────────────────────────────────────────────────────────────────────
# Datasource CRUD
# ──────────────────────────────────────────────────────────────────────────────

def create_datasource(
    dataset: str,
    graph: str,
    label: str,
    ds_type: str,
    connection_info: str,
    description: str | None = None,
) -> dict:
    """
    Datasource 생성.

    Raises:
        ValueError: 지원하지 않는 타입 (→ 422)
    """
    if ds_type not in SUPPORTED_TYPES:
        raise ValueError(f"지원하지 않는 ds_type: {ds_type!r}. 지원: {sorted(SUPPORTED_TYPES)}")

    ds_graph = _ds_graph_iri(graph)
    ds_iri = _gen_iri(ds_graph, "Datasource")

    esc_label = _escape(label)
    esc_type = _escape(ds_type)
    esc_conn = _escape(connection_info)

    desc_triple = ""
    if description:
        esc_desc = _escape(description)
        desc_triple = f'<{ds_iri}> rdfs:comment "{esc_desc}" .'

    sparql_update(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    INSERT DATA {{
      GRAPH <{ds_graph}> {{
        <{ds_iri}> a onto:Datasource ;
            rdfs:label "{esc_label}" ;
            onto:dsType "{esc_type}" ;
            onto:connectionInfo "{esc_conn}" .
        {desc_triple}
      }}
    }}
    """)
    return {
        "datasource_iri": ds_iri,
        "label": label,
        "ds_type": ds_type,
        "connection_info": connection_info,
        "description": description,
    }


def list_datasources(dataset: str, graph: str) -> list[dict]:
    ds_graph = _ds_graph_iri(graph)
    rows = sparql_query(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    SELECT ?ds ?label ?type ?conn ?desc WHERE {{
      GRAPH <{ds_graph}> {{
        ?ds a onto:Datasource ;
            onto:dsType ?type ;
            onto:connectionInfo ?conn .
        OPTIONAL {{ ?ds rdfs:label ?label }}
        OPTIONAL {{ ?ds rdfs:comment ?desc }}
      }}
    }}
    ORDER BY ?ds
    """)
    return [
        {
            "datasource_iri": r["ds"],
            "label": r.get("label"),
            "ds_type": r["type"],
            "connection_info": r["conn"],
            "description": r.get("desc"),
        }
        for r in rows
    ]


def get_datasource(dataset: str, graph: str, ds_iri: str) -> dict:
    """
    Datasource 상세 조회 (매핑 포함).

    Raises:
        KeyError: not found (→ 404)
    """
    ds_graph = _ds_graph_iri(graph)

    # Datasource 기본 정보
    rows = sparql_query(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    SELECT ?label ?type ?conn ?desc WHERE {{
      GRAPH <{ds_graph}> {{
        <{ds_iri}> a onto:Datasource ;
            onto:dsType ?type ;
            onto:connectionInfo ?conn .
        OPTIONAL {{ <{ds_iri}> rdfs:label ?label }}
        OPTIONAL {{ <{ds_iri}> rdfs:comment ?desc }}
      }}
    }}
    """)
    if not rows:
        raise KeyError(f"Datasource not found: {ds_iri}")

    r = rows[0]

    # 매핑 목록
    mappings = _get_mappings_for_ds(dataset, ds_graph, ds_iri)

    return {
        "datasource_iri": ds_iri,
        "label": r.get("label"),
        "ds_type": r["type"],
        "connection_info": r["conn"],
        "description": r.get("desc"),
        "mappings": mappings,
    }


def _get_mappings_for_ds(dataset: str, ds_graph: str, ds_iri: str) -> list[dict]:
    """Datasource에 연결된 모든 ClassMapping과 PropertyMapping 조회."""
    # ClassMapping 목록
    map_rows = sparql_query(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    SELECT ?mapping ?targetClass ?idField ?mlabel WHERE {{
      GRAPH <{ds_graph}> {{
        ?mapping a onto:ClassMapping ;
                 onto:datasource <{ds_iri}> ;
                 onto:targetClass ?targetClass ;
                 onto:identifierField ?idField .
        OPTIONAL {{ ?mapping rdfs:label ?mlabel }}
      }}
    }}
    ORDER BY ?mapping
    """)

    mappings = []
    for m in map_rows:
        mapping_iri = m["mapping"]
        # PropertyMapping 목록
        prop_rows = sparql_query(dataset, f"""
        PREFIX onto: <{ONTO_NS}>
        SELECT ?pm ?srcField ?targetProp WHERE {{
          GRAPH <{ds_graph}> {{
            ?pm a onto:PropertyMapping ;
                onto:classMapping <{mapping_iri}> ;
                onto:sourceField ?srcField ;
                onto:targetProperty ?targetProp .
          }}
        }}
        ORDER BY ?pm
        """)

        property_mappings = [
            {
                "prop_mapping_iri": p["pm"],
                "source_field": p["srcField"],
                "target_property": p["targetProp"],
            }
            for p in prop_rows
        ]

        mappings.append({
            "mapping_iri": mapping_iri,
            "target_class": m["targetClass"],
            "identifier_field": m["idField"],
            "label": m.get("mlabel"),
            "property_mappings": property_mappings,
        })

    return mappings


def update_datasource(
    dataset: str,
    graph: str,
    ds_iri: str,
    label: str | None = None,
    ds_type: str | None = None,
    connection_info: str | None = None,
    description: str | None = None,
) -> dict:
    """
    Datasource 수정.

    Raises:
        KeyError: not found (→ 404)
        ValueError: 잘못된 타입 (→ 422)
    """
    current = get_datasource(dataset, graph, ds_iri)
    ds_graph = _ds_graph_iri(graph)

    new_label = label if label is not None else current["label"]
    new_type = ds_type if ds_type is not None else current["ds_type"]
    new_conn = connection_info if connection_info is not None else current["connection_info"]
    new_desc = description if description is not None else current["description"]

    if new_type not in SUPPORTED_TYPES:
        raise ValueError(f"지원하지 않는 ds_type: {new_type!r}")

    # 기존 Datasource 트리플만 삭제 (매핑은 유지)
    sparql_update(dataset, f"""
    DELETE WHERE {{
      GRAPH <{ds_graph}> {{
        <{ds_iri}> ?p ?o .
      }}
    }}
    """)

    esc_label = _escape(new_label or "")
    esc_type = _escape(new_type)
    esc_conn = _escape(new_conn or "")

    desc_triple = ""
    if new_desc:
        esc_desc = _escape(new_desc)
        desc_triple = f'<{ds_iri}> rdfs:comment "{esc_desc}" .'

    sparql_update(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    INSERT DATA {{
      GRAPH <{ds_graph}> {{
        <{ds_iri}> a onto:Datasource ;
            rdfs:label "{esc_label}" ;
            onto:dsType "{esc_type}" ;
            onto:connectionInfo "{esc_conn}" .
        {desc_triple}
      }}
    }}
    """)
    return get_datasource(dataset, graph, ds_iri)


def delete_datasource(dataset: str, graph: str, ds_iri: str) -> dict:
    """
    Datasource와 연결된 모든 매핑 삭제.

    Raises:
        KeyError: not found (→ 404)
    """
    detail = get_datasource(dataset, graph, ds_iri)
    ds_graph = _ds_graph_iri(graph)

    # PropertyMapping → ClassMapping → Datasource 순서로 삭제
    for m in detail["mappings"]:
        for pm in m["property_mappings"]:
            sparql_update(dataset, f"""
            DELETE WHERE {{
              GRAPH <{ds_graph}> {{
                <{pm['prop_mapping_iri']}> ?p ?o .
              }}
            }}
            """)
        sparql_update(dataset, f"""
        DELETE WHERE {{
          GRAPH <{ds_graph}> {{
            <{m['mapping_iri']}> ?p ?o .
          }}
        }}
        """)

    sparql_update(dataset, f"""
    DELETE WHERE {{
      GRAPH <{ds_graph}> {{
        <{ds_iri}> ?p ?o .
      }}
    }}
    """)
    return {"deleted": ds_iri}


# ──────────────────────────────────────────────────────────────────────────────
# Mapping CRUD
# ──────────────────────────────────────────────────────────────────────────────

def add_class_mapping(
    dataset: str,
    graph: str,
    ds_iri: str,
    target_class: str,
    identifier_field: str,
    label: str | None = None,
) -> dict:
    """
    ClassMapping 추가.

    Raises:
        KeyError: Datasource not found (→ 404)
    """
    get_datasource(dataset, graph, ds_iri)  # 존재 확인
    ds_graph = _ds_graph_iri(graph)
    mapping_iri = _gen_iri(ds_graph, "ClassMapping")

    esc_field = _escape(identifier_field)

    label_triple = ""
    if label:
        esc_label = _escape(label)
        label_triple = f'<{mapping_iri}> rdfs:label "{esc_label}" .'

    sparql_update(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    PREFIX rdfs: <{RDFS_NS}>
    INSERT DATA {{
      GRAPH <{ds_graph}> {{
        <{mapping_iri}> a onto:ClassMapping ;
            onto:datasource <{ds_iri}> ;
            onto:targetClass <{target_class}> ;
            onto:identifierField "{esc_field}" .
        {label_triple}
      }}
    }}
    """)
    return {"mapping_iri": mapping_iri, "target_class": target_class, "identifier_field": identifier_field}


def delete_class_mapping(
    dataset: str,
    graph: str,
    ds_iri: str,
    mapping_iri: str,
) -> dict:
    """
    ClassMapping 삭제 (연결 PropertyMapping 연쇄 삭제).

    Raises:
        KeyError: mapping not found (→ 404)
    """
    ds_graph = _ds_graph_iri(graph)

    # 존재 확인
    rows = sparql_query(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    SELECT ?m WHERE {{
      GRAPH <{ds_graph}> {{
        <{mapping_iri}> a onto:ClassMapping ;
                        onto:datasource <{ds_iri}> .
        BIND(<{mapping_iri}> AS ?m)
      }}
    }} LIMIT 1
    """)
    if not rows:
        raise KeyError(f"ClassMapping not found: {mapping_iri}")

    # PropertyMapping 연쇄 삭제
    prop_rows = sparql_query(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    SELECT ?pm WHERE {{
      GRAPH <{ds_graph}> {{
        ?pm a onto:PropertyMapping ; onto:classMapping <{mapping_iri}> .
      }}
    }}
    """)
    for pr in prop_rows:
        sparql_update(dataset, f"""
        DELETE WHERE {{
          GRAPH <{ds_graph}> {{
            <{pr['pm']}> ?p ?o .
          }}
        }}
        """)

    sparql_update(dataset, f"""
    DELETE WHERE {{
      GRAPH <{ds_graph}> {{
        <{mapping_iri}> ?p ?o .
      }}
    }}
    """)
    return {"deleted": mapping_iri}


def add_property_mapping(
    dataset: str,
    graph: str,
    ds_iri: str,
    mapping_iri: str,
    source_field: str,
    target_property: str,
) -> dict:
    """
    PropertyMapping 추가.

    Raises:
        KeyError: ClassMapping not found (→ 404)
    """
    ds_graph = _ds_graph_iri(graph)

    # ClassMapping 존재 확인
    rows = sparql_query(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    SELECT ?m WHERE {{
      GRAPH <{ds_graph}> {{
        <{mapping_iri}> a onto:ClassMapping ; onto:datasource <{ds_iri}> .
        BIND(<{mapping_iri}> AS ?m)
      }}
    }} LIMIT 1
    """)
    if not rows:
        raise KeyError(f"ClassMapping not found: {mapping_iri}")

    pm_iri = _gen_iri(ds_graph, "PropertyMapping")
    esc_field = _escape(source_field)

    sparql_update(dataset, f"""
    PREFIX onto: <{ONTO_NS}>
    INSERT DATA {{
      GRAPH <{ds_graph}> {{
        <{pm_iri}> a onto:PropertyMapping ;
            onto:classMapping <{mapping_iri}> ;
            onto:sourceField "{esc_field}" ;
            onto:targetProperty <{target_property}> .
      }}
    }}
    """)
    return {
        "prop_mapping_iri": pm_iri,
        "source_field": source_field,
        "target_property": target_property,
    }
