"""
v03-D 통합 테스트 — Universal Namespace import UI

TC01: Universal NS 목록 조회 → 12개 이상 반환
TC02: foaf NS import → 201, 그래프에 vann:prefix 선언 추가
TC03: schema NS import → 201
TC04: 이미 선언된 NS import → 409 Conflict
TC05: skos NS import → 201, graph에서 SPARQL로 확인
TC06: 알 수 없는 prefix → 422
TC07: dcterms NS import → 201
TC08: prov NS import → 201
TC09: import 후 navigator namespace 목록에 반영 확인
TC10: 커스텀 prefix (Universal 목록에 없음) import 시도 → 422

실행:
  cd backend && pytest tests/test_v03d_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app
from fuseki.sparql import update as sparql_update, query as sparql_query

TEST_DS    = "ontology"
TEST_GRAPH = "http://v03d-universal-ns.example.org/graph"


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _setup():
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{
        <{TEST_GRAPH}> a owl:Ontology .
      }}
    }}
    """)


@pytest.fixture(autouse=True, scope="module")
async def cleanup(client):
    _setup()
    yield
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")


# ── TC01: Universal NS 목록 조회 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_list_universal_namespaces(client):
    """Universal NS 목록 → 12개 이상"""
    resp = await client.get("/api/namespaces/universal")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 12
    # 기본 접두사 포함 확인
    prefixes = [ns["prefix"] for ns in data]
    for expected in ["rdf", "rdfs", "owl", "xsd", "foaf", "schema"]:
        assert expected in prefixes, f"{expected} missing from universal ns list"


# ── TC02: foaf NS import ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_import_foaf(client):
    """foaf NS import → 201"""
    resp = await client.post("/api/namespaces/universal/import", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "prefix": "foaf",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "ns_iri" in data
    assert "foaf" in data["ns_iri"].lower() or "xmlns" in data["ns_iri"]


# ── TC03: schema NS import ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_import_schema(client):
    """schema NS import → 201"""
    resp = await client.post("/api/namespaces/universal/import", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "prefix": "schema",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "schema.org" in data["ns_iri"]


# ── TC04: 이미 선언된 NS import → 409 ────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_import_duplicate_409(client):
    """이미 선언된 NS import → 409"""
    # foaf는 TC02에서 이미 추가됨
    resp = await client.post("/api/namespaces/universal/import", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "prefix": "foaf",
    })
    assert resp.status_code == 409, resp.text


# ── TC05: skos import + SPARQL 확인 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_import_skos_and_verify(client):
    """skos NS import → 201, 그래프에서 SPARQL로 확인"""
    resp = await client.post("/api/namespaces/universal/import", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "prefix": "skos",
    })
    assert resp.status_code == 201, resp.text

    # SPARQL로 vann:preferredNamespacePrefix 확인
    rows = sparql_query(TEST_DS, f"""
    PREFIX vann: <http://purl.org/vocab/vann/>
    SELECT ?ns ?prefix WHERE {{
      GRAPH <{TEST_GRAPH}> {{
        ?ns vann:preferredNamespacePrefix "skos" .
        BIND("skos" AS ?prefix)
      }}
    }}
    """)
    assert len(rows) > 0, "skos not declared in graph"


# ── TC06: 알 수 없는 prefix → 422 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_unknown_prefix_422(client):
    """Universal 목록에 없는 prefix → 422"""
    resp = await client.post("/api/namespaces/universal/import", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "prefix": "totally_unknown_xyz_prefix",
    })
    assert resp.status_code == 422, resp.text


# ── TC07: dcterms import ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_import_dcterms(client):
    """dcterms NS import → 201"""
    resp = await client.post("/api/namespaces/universal/import", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "prefix": "dcterms",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "purl.org/dc/terms" in data["ns_iri"]


# ── TC08: prov import ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_import_prov(client):
    """prov NS import → 201"""
    resp = await client.post("/api/namespaces/universal/import", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "prefix": "prov",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "prov" in data["ns_iri"].lower() or "w3.org/ns/prov" in data["ns_iri"]


# ── TC09: import 후 navigator 목록에 반영 ────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_after_import_namespace_list_updated(client):
    """import 후 namespace 목록 API에서 확인"""
    resp = await client.get(
        f"/api/datasets/{TEST_DS}/graphs/namespaces",
        params={"graph": TEST_GRAPH},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # GraphNamespacesResponse: {"graph": ..., "namespaces": [...]}
    ns_list = data.get("namespaces", data) if isinstance(data, dict) else data
    ns_iris = [n["base_iri"] for n in ns_list]
    # 적어도 하나 이상의 universal NS가 포함되어야 함
    foaf_iri = "http://xmlns.com/foaf/0.1/"
    assert foaf_iri in ns_iris or any("foaf" in iri for iri in ns_iris), \
        f"foaf not found in namespaces: {ns_iris}"


# ── TC10: 커스텀 prefix import 시도 → 422 ────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_custom_prefix_not_universal_422(client):
    """Custom(알 수 없는) prefix → 422"""
    resp = await client.post("/api/namespaces/universal/import", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "prefix": "myCustomNs",
    })
    assert resp.status_code == 422, resp.text
