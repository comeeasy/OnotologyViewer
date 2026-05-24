"""
v03-A 통합 테스트 — SHACL 검증 룰 시각화

TC01: NodeShape 생성 (sh:targetClass 지정) → 201, shape IRI 반환
TC02: NodeShape 목록 조회 → shapes 리스트
TC03: NodeShape 상세 조회 → NodeShape + PropertyShapes
TC04: PropertyShape 추가 (sh:minCount, sh:path 등)
TC05: PropertyShape 삭제
TC06: NodeShape 삭제 (연결 PropertyShape 연쇄 삭제)
TC07: 적합한 그래프 검증 → conforms=True
TC08: 위반 그래프 검증 → conforms=False, violations 목록
TC09: Individual 단위 검증 → 해당 individual 위반만 필터
TC10: 존재하지 않는 Shape 조회 → 404

실행:
  cd backend && pytest tests/test_v03a_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app
from fuseki.sparql import update as sparql_update, query as sparql_query

TEST_DS     = "ontology"
TEST_GRAPH  = "http://v03a-shacl-test.example.org/graph"
SHACL_GRAPH = "http://v03a-shacl-test.example.org/graph/shacl"
NS          = "http://v03a-shacl-test.example.org/ns#"

CREATED_SHAPE_IRI = None
CREATED_PROP_SHAPE_IRI = None


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _setup():
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{SHACL_GRAPH}>")
    sparql_update(TEST_DS, f"""
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{
        <{TEST_GRAPH}> a owl:Ontology .

        # Class
        <{NS}Person> a owl:Class ; rdfs:label "Person" .
        <{NS}Animal> a owl:Class ; rdfs:label "Animal" .

        # Properties
        <{NS}hasName> a owl:DatatypeProperty ;
            rdfs:domain <{NS}Person> ;
            rdfs:range xsd:string .
        <{NS}hasAge> a owl:DatatypeProperty ;
            rdfs:domain <{NS}Person> ;
            rdfs:range xsd:integer .

        # Valid individual (has hasName)
        <{NS}alice> a <{NS}Person> ;
            rdfs:label "Alice" ;
            <{NS}hasName> "Alice"^^xsd:string ;
            <{NS}hasAge> "30"^^xsd:integer .

        # Invalid individual (missing hasName - will violate minCount=1)
        <{NS}bob> a <{NS}Person> ;
            rdfs:label "Bob" .
      }}
    }}
    """)


@pytest.fixture(autouse=True, scope="module")
async def cleanup(client):
    _setup()
    yield
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{SHACL_GRAPH}>")


# ── TC01: NodeShape 생성 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_create_node_shape(client):
    """NodeShape 생성 → 201, shape IRI 반환"""
    global CREATED_SHAPE_IRI
    resp = await client.post("/api/shacl/shapes", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "target_class": f"{NS}Person",
        "label": "PersonShape",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "shape_iri" in data
    assert data["shape_iri"].startswith("http")
    CREATED_SHAPE_IRI = data["shape_iri"]


# ── TC02: NodeShape 목록 조회 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_list_shapes(client):
    """NodeShape 목록 조회 → shapes 리스트"""
    resp = await client.get("/api/shacl/shapes", params={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    iris = [s["shape_iri"] for s in data]
    assert CREATED_SHAPE_IRI in iris


# ── TC03: NodeShape 상세 조회 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_get_shape_detail(client):
    """NodeShape 상세 조회 → target_class, label, property_shapes"""
    from urllib.parse import quote
    encoded = quote(CREATED_SHAPE_IRI, safe='')
    resp = await client.get(f"/api/shacl/shapes/{encoded}", params={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["shape_iri"] == CREATED_SHAPE_IRI
    assert data["target_class"] == f"{NS}Person"
    assert data["label"] == "PersonShape"
    assert "property_shapes" in data
    assert isinstance(data["property_shapes"], list)


# ── TC04: PropertyShape 추가 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_add_property_shape(client):
    """PropertyShape 추가 (minCount=1, path=hasName)"""
    global CREATED_PROP_SHAPE_IRI
    from urllib.parse import quote
    encoded = quote(CREATED_SHAPE_IRI, safe='')
    resp = await client.post(f"/api/shacl/shapes/{encoded}/properties", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "path": f"{NS}hasName",
        "min_count": 1,
        "datatype": "http://www.w3.org/2001/XMLSchema#string",
        "label": "hasNameConstraint",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "prop_shape_iri" in data
    CREATED_PROP_SHAPE_IRI = data["prop_shape_iri"]

    # 상세 조회로 PropertyShape 포함 확인
    resp2 = await client.get(f"/api/shacl/shapes/{encoded}", params={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    detail = resp2.json()
    prop_iris = [p["prop_shape_iri"] for p in detail["property_shapes"]]
    assert CREATED_PROP_SHAPE_IRI in prop_iris


# ── TC05: PropertyShape 삭제 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_delete_property_shape(client):
    """PropertyShape 삭제"""
    # 추가 PropertyShape 하나 더 만들어서 삭제
    from urllib.parse import quote
    encoded_shape = quote(CREATED_SHAPE_IRI, safe='')

    create_resp = await client.post(f"/api/shacl/shapes/{encoded_shape}/properties", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "path": f"{NS}hasAge",
        "min_count": 0,
        "label": "hasAgeConstraint",
    })
    assert create_resp.status_code == 201
    temp_prop_iri = create_resp.json()["prop_shape_iri"]

    encoded_prop = quote(temp_prop_iri, safe='')
    del_resp = await client.delete(
        f"/api/shacl/shapes/{encoded_shape}/properties/{encoded_prop}",
        params={"dataset": TEST_DS, "graph": TEST_GRAPH},
    )
    assert del_resp.status_code == 200, del_resp.text

    # 상세 조회에서 사라졌는지 확인
    resp2 = await client.get(f"/api/shacl/shapes/{encoded_shape}", params={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    prop_iris = [p["prop_shape_iri"] for p in resp2.json()["property_shapes"]]
    assert temp_prop_iri not in prop_iris


# ── TC06: NodeShape 삭제 (연쇄 삭제) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_delete_node_shape(client):
    """NodeShape 삭제 → 연결 PropertyShape 연쇄 삭제"""
    # 새 shape 생성
    create_resp = await client.post("/api/shacl/shapes", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "target_class": f"{NS}Animal",
        "label": "AnimalShape",
    })
    assert create_resp.status_code == 201
    temp_shape_iri = create_resp.json()["shape_iri"]

    from urllib.parse import quote
    encoded = quote(temp_shape_iri, safe='')

    # PropertyShape 추가
    await client.post(f"/api/shacl/shapes/{encoded}/properties", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "path": f"{NS}hasName",
        "min_count": 1,
    })

    # NodeShape 삭제
    del_resp = await client.delete(f"/api/shacl/shapes/{encoded}", params={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    assert del_resp.status_code == 200, del_resp.text

    # 목록에서 사라졌는지 확인
    list_resp = await client.get("/api/shacl/shapes", params={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    iris = [s["shape_iri"] for s in list_resp.json()]
    assert temp_shape_iri not in iris


# ── TC07: 적합한 그래프 검증 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_validate_conforms(client):
    """alice (유효한 individual)만 포함한 그래프 → conforms=True"""
    # alice용 그래프 생성
    VALID_GRAPH = f"http://v03a-valid.example.org/graph"
    VALID_SHACL = f"{VALID_GRAPH}/shacl"
    try:
        sparql_update(TEST_DS, f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        INSERT DATA {{
          GRAPH <{VALID_GRAPH}> {{
            <{VALID_GRAPH}> a owl:Ontology .
            <{NS}Person> a owl:Class .
            <{NS}hasName> a owl:DatatypeProperty ; rdfs:domain <{NS}Person> ; rdfs:range xsd:string .
            <{NS}alice> a <{NS}Person> ; <{NS}hasName> "Alice"^^xsd:string .
          }}
        }}
        """)

        # shape 생성 + PropertyShape 추가
        shape_resp = await client.post("/api/shacl/shapes", json={
            "dataset": TEST_DS,
            "graph": VALID_GRAPH,
            "target_class": f"{NS}Person",
            "label": "ValidPersonShape",
        })
        assert shape_resp.status_code == 201
        v_shape_iri = shape_resp.json()["shape_iri"]
        from urllib.parse import quote
        encoded = quote(v_shape_iri, safe='')
        await client.post(f"/api/shacl/shapes/{encoded}/properties", json={
            "dataset": TEST_DS,
            "graph": VALID_GRAPH,
            "path": f"{NS}hasName",
            "min_count": 1,
        })

        # 검증
        resp = await client.post("/api/shacl/validate", json={
            "dataset": TEST_DS,
            "graph": VALID_GRAPH,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "conforms" in data
        assert data["conforms"] is True
        assert data["violations"] == []

    finally:
        sparql_update(TEST_DS, f"DROP SILENT GRAPH <{VALID_GRAPH}>")
        sparql_update(TEST_DS, f"DROP SILENT GRAPH <{VALID_SHACL}>")


# ── TC08: 위반 그래프 검증 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_validate_violations(client):
    """bob (hasName 없음) 포함 → conforms=False, violations 목록"""
    resp = await client.post("/api/shacl/validate", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "conforms" in data
    # bob은 hasName이 없으므로 minCount=1 위반
    assert data["conforms"] is False
    assert len(data["violations"]) > 0
    # violation에 focus_node나 message가 있어야 함
    v = data["violations"][0]
    assert "focus_node" in v or "message" in v


# ── TC09: Individual 단위 검증 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_validate_individual(client):
    """bob 개별 검증 → bob의 위반만 반환"""
    resp = await client.post("/api/shacl/validate/individual", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "individual_iri": f"{NS}bob",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "conforms" in data
    assert data["conforms"] is False
    # alice 위반은 없고 bob만 위반
    for v in data["violations"]:
        focus = v.get("focus_node", "")
        assert "bob" in focus or focus == ""  # focus_node가 bob이어야


# ── TC10: 존재하지 않는 Shape 조회 → 404 ─────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_get_nonexistent_shape_404(client):
    """존재하지 않는 Shape IRI → 404"""
    from urllib.parse import quote
    fake_iri = f"{NS}NonExistentShape_xyz"
    encoded = quote(fake_iri, safe='')
    resp = await client.get(f"/api/shacl/shapes/{encoded}", params={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    assert resp.status_code == 404, resp.text
