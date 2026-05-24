"""
v02-F 통합 테스트 — SPARQL Editor

TC01: POST /api/sparql/query → SELECT 결과 반환
TC02: POST /api/sparql/query → ASK 결과(boolean) 반환
TC03: SELECT — OOI Named Graph 자동 적용 (GRAPH wrapper)
TC04: POST /api/sparql/update → INSERT DATA 성공
TC05: POST /api/sparql/update → DELETE DATA 성공
TC06: SELECT LIMIT → 제한된 결과 수
TC07: 잘못된 SPARQL → 400
TC08: UPDATE 후 SELECT로 확인
TC09: SELECT 결과 없음 → 빈 배열
TC10: Graph wrapper — 다른 graph 데이터는 안 보임

실행:
  cd backend && pytest tests/test_v02f_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app
from fuseki.sparql import update as sparql_update

TEST_DS     = "ontology"
TEST_GRAPH  = "http://v02f-sparql-test.example.org/graph"
OTHER_GRAPH = "http://v02f-sparql-test.example.org/other-graph"
NS          = "http://v02f-sparql-test.example.org/ns#"


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _setup():
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{OTHER_GRAPH}>")
    sparql_update(TEST_DS, f"""
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{
        <{TEST_GRAPH}> a owl:Ontology .
        <{NS}Dog> a owl:Class ; rdfs:label "Dog" .
        <{NS}Cat> a owl:Class ; rdfs:label "Cat" .
        <{NS}Bird> a owl:Class ; rdfs:label "Bird" .
      }}
      GRAPH <{OTHER_GRAPH}> {{
        <{OTHER_GRAPH}> a owl:Ontology .
        <{NS}Fish> a owl:Class ; rdfs:label "Fish" .
      }}
    }}
    """)


@pytest.fixture(autouse=True, scope="module")
async def cleanup(client):
    _setup()
    yield
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{OTHER_GRAPH}>")


# ── TC01: SELECT 결과 반환 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_select_returns_results(client):
    """SELECT query → 결과 반환"""
    resp = await client.post("/api/sparql/query", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0


# ── TC02: ASK 결과(boolean) 반환 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_ask_returns_boolean(client):
    """ASK query → boolean 결과"""
    resp = await client.post("/api/sparql/query", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "query": f"ASK {{ <{NS}Dog> a <http://www.w3.org/2002/07/owl#Class> }}",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "boolean" in data
    assert data["boolean"] is True


# ── TC03: SELECT — GRAPH 자동 적용 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_graph_auto_wrap_select(client):
    """SELECT without explicit GRAPH → OOI graph에서만 결과 반환"""
    resp = await client.post("/api/sparql/query", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "query": "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?label WHERE { ?s rdfs:label ?label }",
    })
    assert resp.status_code == 200, resp.text
    labels = [r.get("label") for r in resp.json()["results"]]
    # Fish는 OTHER_GRAPH에만 있으므로 안 보여야 함
    assert "Fish" not in labels, f"Fish should not be visible: {labels}"
    assert "Dog" in labels, f"Dog should be visible: {labels}"


# ── TC04: INSERT DATA 성공 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_insert_data(client):
    """INSERT DATA → 데이터 삽입 성공"""
    resp = await client.post("/api/sparql/update", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "update": f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{ <{NS}Snake> a owl:Class ; rdfs:label "Snake" . }}
        """,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    # 확인: Snake가 삽입됐는지
    from fuseki.sparql import query as sparql_query
    rows = sparql_query(TEST_DS, f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label WHERE {{
      GRAPH <{TEST_GRAPH}> {{ <{NS}Snake> rdfs:label ?label . }}
    }}
    """)
    assert rows and rows[0]["label"] == "Snake"


# ── TC05: DELETE DATA 성공 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_delete_data(client):
    """DELETE DATA → 데이터 삭제 성공"""
    # 먼저 삭제할 데이터 삽입
    sparql_update(TEST_DS, f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{ <{NS}TempClass> a owl:Class . }}
    }}
    """)
    resp = await client.post("/api/sparql/update", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "update": f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        DELETE DATA {{ <{NS}TempClass> a owl:Class . }}
        """,
    })
    assert resp.status_code == 200, resp.text

    # 확인: TempClass가 삭제됐는지
    from fuseki.sparql import query as sparql_query
    rows = sparql_query(TEST_DS, f"""
    ASK {{ GRAPH <{TEST_GRAPH}> {{ <{NS}TempClass> a <http://www.w3.org/2002/07/owl#Class> . }} }}
    """)
    # ASK returns via raw SPARQLWrapper
    # Use the endpoint directly
    from fuseki.sparql import query
    q_rows = query(TEST_DS, f"""
    SELECT ?x WHERE {{
      GRAPH <{TEST_GRAPH}> {{ <{NS}TempClass> a ?x . }}
    }} LIMIT 1
    """)
    assert q_rows == [], f"TempClass should be deleted, got {q_rows}"


# ── TC06: SELECT LIMIT ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_select_limit(client):
    """SELECT LIMIT 2 → 최대 2개 결과"""
    resp = await client.post("/api/sparql/query", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 2",
    })
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert len(results) <= 2


# ── TC07: 잘못된 SPARQL → 400 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_invalid_sparql_400(client):
    """잘못된 SPARQL → 400"""
    resp = await client.post("/api/sparql/query", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "query": "THIS IS NOT SPARQL",
    })
    assert resp.status_code == 400, resp.text


# ── TC08: UPDATE 후 SELECT 확인 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_update_then_select(client):
    """INSERT 후 SELECT로 결과 확인"""
    label_val = "UpdateThenSelectTest"
    await client.post("/api/sparql/update", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "update": f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        INSERT DATA {{ <{NS}TestNode> a owl:Class ; rdfs:label "{label_val}" . }}
        """,
    })
    resp = await client.post("/api/sparql/query", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "query": f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?label WHERE {{ <{NS}TestNode> rdfs:label ?label }}
        """,
    })
    assert resp.status_code == 200, resp.text
    labels = [r.get("label") for r in resp.json()["results"]]
    assert label_val in labels


# ── TC09: SELECT 결과 없음 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_select_empty_result(client):
    """결과 없는 SELECT → 빈 배열"""
    resp = await client.post("/api/sparql/query", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "query": f"SELECT ?x WHERE {{ <{NS}NoSuchThing> ?p ?x }}",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["results"] == []


# ── TC10: GRAPH wrapper — 다른 graph 데이터 격리 ──────────────────────────

@pytest.mark.asyncio
async def test_tc10_graph_isolation(client):
    """OOI graph가 지정되면 다른 graph 데이터는 보이지 않음"""
    resp = await client.post("/api/sparql/query", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "query": f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?label WHERE {{ ?s rdfs:label ?label . FILTER(?label = "Fish") }}
        """,
    })
    assert resp.status_code == 200, resp.text
    # Fish는 OTHER_GRAPH에만 있으므로 결과가 비어야 함
    assert resp.json()["results"] == [], f"Fish should not be visible: {resp.json()}"
