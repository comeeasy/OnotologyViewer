"""
v03-C 통합 테스트 — Datasource 매핑

TC01: Datasource 생성 (csv type) → 201, datasource IRI 반환
TC02: Datasource 목록 조회 → datasources 리스트
TC03: Datasource 상세 조회 → name, type, connectionInfo 포함
TC04: Datasource 수정 (label 변경)
TC05: Datasource 삭제
TC06: Class 매핑 추가 → 201, mapping IRI 반환
TC07: Property 매핑 추가
TC08: 매핑 삭제
TC09: 잘못된 타입 → 422
TC10: 존재하지 않는 Datasource → 404

실행:
  cd backend && pytest tests/test_v03c_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app
from fuseki.sparql import update as sparql_update

TEST_DS     = "ontology"
TEST_GRAPH  = "http://v03c-ds-test.example.org/graph"
DS_GRAPH    = "http://v03c-ds-test.example.org/graph/datasources"
NS          = "http://v03c-ds-test.example.org/ns#"

CREATED_DS_IRI      = None
CREATED_MAPPING_IRI = None
CREATED_PROP_MAP_IRI = None


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _setup():
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{DS_GRAPH}>")
    sparql_update(TEST_DS, f"""
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{
        <{TEST_GRAPH}> a owl:Ontology .
        <{NS}Person> a owl:Class ; rdfs:label "Person" .
        <{NS}hasName> a owl:DatatypeProperty ; rdfs:domain <{NS}Person> .
        <{NS}hasAge> a owl:DatatypeProperty ; rdfs:domain <{NS}Person> .
      }}
    }}
    """)


@pytest.fixture(autouse=True, scope="module")
async def cleanup(client):
    _setup()
    yield
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{DS_GRAPH}>")


# ── TC01: Datasource 생성 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_create_datasource(client):
    """Datasource 생성 → 201, datasource IRI 반환"""
    global CREATED_DS_IRI
    resp = await client.post("/api/datasources", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "People CSV",
        "ds_type": "csv",
        "connection_info": "/data/people.csv",
        "description": "사람 데이터 CSV 파일",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "datasource_iri" in data
    assert data["datasource_iri"].startswith("http")
    CREATED_DS_IRI = data["datasource_iri"]


# ── TC02: Datasource 목록 조회 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_list_datasources(client):
    """Datasource 목록 조회"""
    resp = await client.get("/api/datasources", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    iris = [d["datasource_iri"] for d in data]
    assert CREATED_DS_IRI in iris


# ── TC03: Datasource 상세 조회 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_get_datasource_detail(client):
    """Datasource 상세 조회 → label, type, connectionInfo"""
    from urllib.parse import quote
    encoded = quote(CREATED_DS_IRI, safe='')
    resp = await client.get(f"/api/datasources/{encoded}", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["datasource_iri"] == CREATED_DS_IRI
    assert data["label"] == "People CSV"
    assert data["ds_type"] == "csv"
    assert data["connection_info"] == "/data/people.csv"
    assert "mappings" in data
    assert isinstance(data["mappings"], list)


# ── TC04: Datasource 수정 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_update_datasource(client):
    """Datasource 수정 (label 변경)"""
    from urllib.parse import quote
    encoded = quote(CREATED_DS_IRI, safe='')
    resp = await client.patch(f"/api/datasources/{encoded}", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "People CSV (updated)",
    })
    assert resp.status_code == 200, resp.text

    # 변경 확인
    detail_resp = await client.get(
        f"/api/datasources/{encoded}",
        params={"dataset": TEST_DS, "graph": TEST_GRAPH},
    )
    assert detail_resp.json()["label"] == "People CSV (updated)"


# ── TC05: Datasource 삭제 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_delete_datasource(client):
    """Datasource 삭제"""
    # 임시 datasource 생성
    create_resp = await client.post("/api/datasources", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "Temp DS",
        "ds_type": "json",
        "connection_info": "http://api.example.org/data",
    })
    temp_iri = create_resp.json()["datasource_iri"]

    from urllib.parse import quote
    encoded = quote(temp_iri, safe='')
    del_resp = await client.delete(f"/api/datasources/{encoded}", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    assert del_resp.status_code == 200, del_resp.text

    # 목록에서 사라졌는지 확인
    list_resp = await client.get("/api/datasources", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    iris = [d["datasource_iri"] for d in list_resp.json()]
    assert temp_iri not in iris


# ── TC06: Class 매핑 추가 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_add_class_mapping(client):
    """Class 매핑 추가 → 201, mapping IRI 반환"""
    global CREATED_MAPPING_IRI
    from urllib.parse import quote
    encoded = quote(CREATED_DS_IRI, safe='')
    resp = await client.post(f"/api/datasources/{encoded}/mappings", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "target_class": f"{NS}Person",
        "identifier_field": "person_id",
        "label": "PersonMapping",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "mapping_iri" in data
    CREATED_MAPPING_IRI = data["mapping_iri"]


# ── TC07: Property 매핑 추가 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_add_property_mapping(client):
    """Property 매핑 추가"""
    global CREATED_PROP_MAP_IRI
    from urllib.parse import quote
    encoded_ds = quote(CREATED_DS_IRI, safe='')
    encoded_map = quote(CREATED_MAPPING_IRI, safe='')
    resp = await client.post(
        f"/api/datasources/{encoded_ds}/mappings/{encoded_map}/properties",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "source_field": "name",
            "target_property": f"{NS}hasName",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "prop_mapping_iri" in data
    CREATED_PROP_MAP_IRI = data["prop_mapping_iri"]

    # 상세 조회 확인
    detail_resp = await client.get(
        f"/api/datasources/{encoded_ds}",
        params={"dataset": TEST_DS, "graph": TEST_GRAPH},
    )
    detail = detail_resp.json()
    # mappings에 property mappings 포함
    mapping_data = next((m for m in detail["mappings"] if m["mapping_iri"] == CREATED_MAPPING_IRI), None)
    assert mapping_data is not None
    prop_iris = [p["prop_mapping_iri"] for p in mapping_data.get("property_mappings", [])]
    assert CREATED_PROP_MAP_IRI in prop_iris


# ── TC08: 매핑 삭제 ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_delete_mapping(client):
    """매핑 삭제"""
    # 임시 매핑 생성
    from urllib.parse import quote
    encoded_ds = quote(CREATED_DS_IRI, safe='')
    create_resp = await client.post(f"/api/datasources/{encoded_ds}/mappings", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "target_class": f"{NS}Person",
        "identifier_field": "temp_id",
        "label": "TempMapping",
    })
    temp_map_iri = create_resp.json()["mapping_iri"]

    encoded_map = quote(temp_map_iri, safe='')
    del_resp = await client.delete(
        f"/api/datasources/{encoded_ds}/mappings/{encoded_map}",
        params={"dataset": TEST_DS, "graph": TEST_GRAPH},
    )
    assert del_resp.status_code == 200, del_resp.text

    # 상세에서 사라졌는지 확인
    detail_resp = await client.get(
        f"/api/datasources/{encoded_ds}",
        params={"dataset": TEST_DS, "graph": TEST_GRAPH},
    )
    mapping_iris = [m["mapping_iri"] for m in detail_resp.json()["mappings"]]
    assert temp_map_iri not in mapping_iris


# ── TC09: 잘못된 타입 → 422 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_invalid_type_422(client):
    """잘못된 ds_type → 422"""
    resp = await client.post("/api/datasources", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "Bad DS",
        "ds_type": "invalid_type_xyz",
        "connection_info": "http://example.org",
    })
    assert resp.status_code == 422, resp.text


# ── TC10: 존재하지 않는 Datasource → 404 ────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_get_nonexistent_ds_404(client):
    """존재하지 않는 Datasource → 404"""
    from urllib.parse import quote
    fake_iri = f"{NS}NonExistentDS_xyz"
    encoded = quote(fake_iri, safe='')
    resp = await client.get(f"/api/datasources/{encoded}", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    assert resp.status_code == 404, resp.text
