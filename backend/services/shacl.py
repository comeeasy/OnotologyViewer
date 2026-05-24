"""v03-A SHACL Service — pyshacl 기반 Shape 관리 + 검증."""

import uuid
import httpx
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, URIRef, Literal
from pyshacl import validate as pyshacl_validate

import config_state
from fuseki.sparql import query as sparql_query, update as sparql_update

SH = Namespace("http://www.w3.org/ns/shacl#")
SHACL_NS = "http://www.w3.org/ns/shacl#"

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _shacl_graph_iri(graph: str) -> str:
    """OOI 그래프의 SHACL 서브그래프 IRI."""
    return f"{graph}/shacl"


def _gen_iri(base_iri: str, suffix: str) -> str:
    """UUID 기반 IRI 생성."""
    uid = uuid.uuid4().hex
    sep = "#" if "#" not in base_iri else ""
    if base_iri.endswith("#") or base_iri.endswith("/"):
        return f"{base_iri}{suffix}_{uid}"
    return f"{base_iri}/{suffix}_{uid}"


def _export_graph_ttl(dataset: str, graph: str) -> str:
    """Fuseki에서 Named Graph를 TTL로 export (빈 그래프는 빈 문자열 반환)."""
    url = f"{config_state.base_url()}/{dataset}"
    user, pw = config_state.auth()
    try:
        r = httpx.get(
            url,
            params={"graph": graph},
            headers={"Accept": "text/turtle"},
            auth=(user, pw),
            timeout=30,
        )
        r.raise_for_status()
        return r.text
    except httpx.HTTPStatusError:
        return ""


def _rdflib_graph_from_ttl(ttl: str) -> Graph:
    g = Graph()
    if ttl.strip():
        g.parse(data=ttl, format="turtle")
    return g


# ──────────────────────────────────────────────────────────────────────────────
# SHACL Shape CRUD
# ──────────────────────────────────────────────────────────────────────────────

def create_node_shape(
    dataset: str,
    graph: str,
    target_class: str,
    label: str | None = None,
) -> dict:
    """
    NodeShape를 SHACL 서브그래프에 생성한다.

    Returns:
        {"shape_iri": ..., "target_class": ..., "label": ...}
    """
    shacl_graph = _shacl_graph_iri(graph)

    # IRI 생성: SHACL 그래프 IRI를 base로
    shape_iri = _gen_iri(shacl_graph, "NodeShape")

    label_triple = ""
    if label:
        escaped = label.replace('"', '\\"')
        label_triple = f'<{shape_iri}> rdfs:label "{escaped}" .'

    sparql_update(dataset, f"""
    PREFIX sh:   <{SHACL_NS}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    INSERT DATA {{
      GRAPH <{shacl_graph}> {{
        <{shape_iri}> a sh:NodeShape ;
            sh:targetClass <{target_class}> .
        {label_triple}
      }}
    }}
    """)
    return {"shape_iri": shape_iri, "target_class": target_class, "label": label}


def list_shapes(dataset: str, graph: str) -> list[dict]:
    """
    SHACL 서브그래프에 있는 NodeShape 목록을 반환한다.

    Returns:
        [{"shape_iri": ..., "target_class": ..., "label": ...}, ...]
    """
    shacl_graph = _shacl_graph_iri(graph)
    rows = sparql_query(dataset, f"""
    PREFIX sh:   <{SHACL_NS}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?shape ?target ?label WHERE {{
      GRAPH <{shacl_graph}> {{
        ?shape a sh:NodeShape ;
               sh:targetClass ?target .
        OPTIONAL {{ ?shape rdfs:label ?label }}
      }}
    }}
    ORDER BY ?shape
    """)
    return [
        {
            "shape_iri": r["shape"],
            "target_class": r["target"],
            "label": r.get("label"),
        }
        for r in rows
    ]


def get_shape_detail(dataset: str, graph: str, shape_iri: str) -> dict:
    """
    NodeShape 상세 정보 (PropertyShape 목록 포함).

    Returns:
        {
          "shape_iri": ...,
          "target_class": ...,
          "label": ...,
          "property_shapes": [{
              "prop_shape_iri": ...,
              "path": ...,
              "min_count": ...,
              "max_count": ...,
              "datatype": ...,
              "label": ...,
          }, ...]
        }

    Raises:
        KeyError: shape not found (→ 404)
    """
    shacl_graph = _shacl_graph_iri(graph)

    # NodeShape 기본 정보
    node_rows = sparql_query(dataset, f"""
    PREFIX sh:   <{SHACL_NS}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?target ?label WHERE {{
      GRAPH <{shacl_graph}> {{
        <{shape_iri}> a sh:NodeShape ;
                      sh:targetClass ?target .
        OPTIONAL {{ <{shape_iri}> rdfs:label ?label }}
      }}
    }}
    """)
    if not node_rows:
        raise KeyError(f"Shape not found: {shape_iri}")

    target_class = node_rows[0]["target"]
    label = node_rows[0].get("label")

    # 연결된 PropertyShape 목록
    prop_rows = sparql_query(dataset, f"""
    PREFIX sh:   <{SHACL_NS}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?ps ?path ?minCount ?maxCount ?datatype ?plabel WHERE {{
      GRAPH <{shacl_graph}> {{
        <{shape_iri}> sh:property ?ps .
        ?ps sh:path ?path .
        OPTIONAL {{ ?ps sh:minCount ?minCount }}
        OPTIONAL {{ ?ps sh:maxCount ?maxCount }}
        OPTIONAL {{ ?ps sh:datatype ?datatype }}
        OPTIONAL {{ ?ps rdfs:label ?plabel }}
      }}
    }}
    ORDER BY ?ps
    """)

    property_shapes = [
        {
            "prop_shape_iri": r["ps"],
            "path": r["path"],
            "min_count": int(r["minCount"]) if r.get("minCount") else None,
            "max_count": int(r["maxCount"]) if r.get("maxCount") else None,
            "datatype": r.get("datatype"),
            "label": r.get("plabel"),
        }
        for r in prop_rows
    ]

    return {
        "shape_iri": shape_iri,
        "target_class": target_class,
        "label": label,
        "property_shapes": property_shapes,
    }


def add_property_shape(
    dataset: str,
    graph: str,
    shape_iri: str,
    path: str,
    min_count: int | None = None,
    max_count: int | None = None,
    datatype: str | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    pattern: str | None = None,
    label: str | None = None,
) -> dict:
    """
    NodeShape에 PropertyShape를 추가한다.

    Raises:
        KeyError: NodeShape not found (→ 404)
    """
    # shape 존재 확인
    get_shape_detail(dataset, graph, shape_iri)

    shacl_graph = _shacl_graph_iri(graph)
    ps_iri = _gen_iri(shacl_graph, "PropertyShape")

    constraints = []
    if min_count is not None:
        constraints.append(f"sh:minCount {min_count} ;")
    if max_count is not None:
        constraints.append(f"sh:maxCount {max_count} ;")
    if datatype:
        constraints.append(f"sh:datatype <{datatype}> ;")
    if min_length is not None:
        constraints.append(f"sh:minLength {min_length} ;")
    if max_length is not None:
        constraints.append(f"sh:maxLength {max_length} ;")
    if pattern:
        escaped = pattern.replace('"', '\\"')
        constraints.append(f'sh:pattern "{escaped}" ;')
    if label:
        escaped = label.replace('"', '\\"')
        constraints.append(f'rdfs:label "{escaped}" ;')

    constraints_ttl = "\n        ".join(constraints)

    sparql_update(dataset, f"""
    PREFIX sh:   <{SHACL_NS}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    INSERT DATA {{
      GRAPH <{shacl_graph}> {{
        <{ps_iri}> a sh:PropertyShape ;
            sh:path <{path}> ;
            {constraints_ttl}
            .
        <{shape_iri}> sh:property <{ps_iri}> .
      }}
    }}
    """)
    return {"prop_shape_iri": ps_iri, "path": path}


def delete_property_shape(
    dataset: str,
    graph: str,
    shape_iri: str,
    prop_shape_iri: str,
) -> dict:
    """PropertyShape를 삭제하고 NodeShape로부터 링크를 제거한다.

    Raises:
        KeyError: PropertyShape not found (→ 404)
    """
    shacl_graph = _shacl_graph_iri(graph)

    # 존재 확인
    check = sparql_query(dataset, f"""
    PREFIX sh: <{SHACL_NS}>
    ASK {{
      GRAPH <{shacl_graph}> {{
        <{prop_shape_iri}> a sh:PropertyShape .
      }}
    }}
    """)
    # ASK 쿼리 결과 체크 (SPARQLWrapper는 ASK를 다르게 반환하므로 list로 확인)
    if not check:
        # fallback: check via SELECT
        rows = sparql_query(dataset, f"""
        PREFIX sh: <{SHACL_NS}>
        SELECT ?s WHERE {{
          GRAPH <{shacl_graph}> {{
            <{prop_shape_iri}> a sh:PropertyShape .
            BIND(<{prop_shape_iri}> AS ?s)
          }}
        }} LIMIT 1
        """)
        if not rows:
            raise KeyError(f"PropertyShape not found: {prop_shape_iri}")

    # NodeShape → PropertyShape 링크 삭제
    sparql_update(dataset, f"""
    PREFIX sh: <{SHACL_NS}>
    DELETE DATA {{
      GRAPH <{shacl_graph}> {{
        <{shape_iri}> sh:property <{prop_shape_iri}> .
      }}
    }}
    """)

    # PropertyShape 트리플 전체 삭제
    sparql_update(dataset, f"""
    DELETE WHERE {{
      GRAPH <{shacl_graph}> {{
        <{prop_shape_iri}> ?p ?o .
      }}
    }}
    """)

    return {"deleted": prop_shape_iri}


def delete_node_shape(
    dataset: str,
    graph: str,
    shape_iri: str,
) -> dict:
    """
    NodeShape와 연결된 모든 PropertyShape를 삭제한다.

    Raises:
        KeyError: Shape not found (→ 404)
    """
    detail = get_shape_detail(dataset, graph, shape_iri)
    shacl_graph = _shacl_graph_iri(graph)

    # PropertyShape 연쇄 삭제
    for ps in detail["property_shapes"]:
        sparql_update(dataset, f"""
        DELETE WHERE {{
          GRAPH <{shacl_graph}> {{
            <{ps['prop_shape_iri']}> ?p ?o .
          }}
        }}
        """)

    # NodeShape 삭제
    sparql_update(dataset, f"""
    DELETE WHERE {{
      GRAPH <{shacl_graph}> {{
        <{shape_iri}> ?p ?o .
      }}
    }}
    """)

    return {"deleted": shape_iri}


# ──────────────────────────────────────────────────────────────────────────────
# SHACL Validation
# ──────────────────────────────────────────────────────────────────────────────

def _parse_violations(results_graph: Graph) -> list[dict]:
    """pyshacl 결과 그래프에서 violation 목록을 추출한다."""
    SH_VR = URIRef(f"{SHACL_NS}ValidationResult")
    SH_FN = URIRef(f"{SHACL_NS}focusNode")
    SH_RM = URIRef(f"{SHACL_NS}resultMessage")
    SH_RP = URIRef(f"{SHACL_NS}resultPath")
    SH_SS = URIRef(f"{SHACL_NS}sourceShape")
    SH_SVR = URIRef(f"{SHACL_NS}resultSeverity")

    violations = []
    for vr in results_graph.subjects(RDF.type, SH_VR):
        focus = results_graph.value(vr, SH_FN)
        message = results_graph.value(vr, SH_RM)
        path = results_graph.value(vr, SH_RP)
        source_shape = results_graph.value(vr, SH_SS)
        severity = results_graph.value(vr, SH_SVR)

        violations.append({
            "focus_node": str(focus) if focus else None,
            "message": str(message) if message else None,
            "result_path": str(path) if path else None,
            "source_shape": str(source_shape) if source_shape else None,
            "severity": str(severity) if severity else None,
        })
    return violations


def validate_graph(dataset: str, graph: str) -> dict:
    """
    OOI 그래프 전체를 SHACL 검증한다.

    Returns:
        {
          "conforms": bool,
          "violations": [{"focus_node": ..., "message": ..., ...}, ...]
        }
    """
    shacl_graph_iri = _shacl_graph_iri(graph)

    # 데이터 그래프와 SHACL 그래프 TTL export
    data_ttl = _export_graph_ttl(dataset, graph)
    shacl_ttl = _export_graph_ttl(dataset, shacl_graph_iri)

    if not shacl_ttl.strip():
        # SHACL shapes 없으면 항상 통과
        return {"conforms": True, "violations": []}

    data_graph = _rdflib_graph_from_ttl(data_ttl)
    shacl_g = _rdflib_graph_from_ttl(shacl_ttl)

    conforms, results_graph, _ = pyshacl_validate(
        data_graph=data_graph,
        shacl_graph=shacl_g,
        inference='rdfs',
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
    )

    violations = _parse_violations(results_graph)
    return {"conforms": conforms, "violations": violations}


def validate_individual(dataset: str, graph: str, individual_iri: str) -> dict:
    """
    특정 Individual에 대한 SHACL 검증 결과를 반환한다.
    (전체 그래프 검증 후 focus_node가 해당 IRI인 위반만 필터링)

    Returns:
        {"conforms": bool, "violations": [...]}
    """
    result = validate_graph(dataset, graph)
    filtered = [
        v for v in result["violations"]
        if v.get("focus_node") == individual_iri
    ]
    conforms = len(filtered) == 0
    return {"conforms": conforms, "violations": filtered}
