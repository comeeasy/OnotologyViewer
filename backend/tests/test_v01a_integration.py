"""
v01-A 통합 테스트 — OOI Navigator (실제 Fuseki 연동)

테스트 데이터:
  - dataset : ontology
  - graph   : http://test.example.org/graph/integration-test
  - triples :
      <http://test.example.org/resource/Person1>  → Custom namespace
      <http://www.w3.org/2000/01/rdf-schema#Class> → Universal namespace (rdfs)

실행:
  cd backend && pytest tests/test_v01a_integration.py -v
"""

import re
import sys

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from fuseki.sparql import update as sparql_update
from main import app

# ────────────────────────────────────────────────
# 상수
# ────────────────────────────────────────────────

DS = "ontology"
TEST_GRAPH = "http://test.example.org/graph/integration-test"
CUSTOM_NS = "http://test.example.org/resource/"
UNIVERSAL_NS = "http://www.w3.org/2000/01/rdf-schema#"

_DROP_TEST_GRAPH = f"DROP SILENT GRAPH <{TEST_GRAPH}>"

_INSERT_TEST_TRIPLES = f"""
INSERT DATA {{
  GRAPH <{TEST_GRAPH}> {{
    <http://test.example.org/resource/Person1>
        <http://test.example.org/ontology/hasName> "Person One" .
    <http://www.w3.org/2000/01/rdf-schema#Class>
        <http://test.example.org/ontology/comment> "RDFS Class node" .
  }}
}}
"""


# ────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def client():
    """FastAPI 앱을 직접 마운트하는 AsyncClient — 서버 기동 불필요."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True, scope="module")
def clean_test_graph():
    """모든 테스트 전·후 테스트 graph 초기화."""
    sparql_update(DS, _DROP_TEST_GRAPH)  # before
    yield
    sparql_update(DS, _DROP_TEST_GRAPH)  # after


@pytest.fixture(scope="module")
def insert_test_data():
    """테스트 트리플을 Fuseki에 삽입한다 (once per module)."""
    sparql_update(DS, _INSERT_TEST_TRIPLES)


# ────────────────────────────────────────────────
# TC01 — Fuseki 헬스 체크
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_health_check(client):
    """
    Fuseki 서버가 정상 응답할 때 /api/health 는 200 OK + {"status": "ok"} 를 반환한다.
    """
    resp = await client.get("/api/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.json()
    assert body == {"status": "ok"}, f"Unexpected body: {body}"


# ────────────────────────────────────────────────
# TC02 — Dataset 목록에 'ontology' 포함
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_datasets_include_ontology(client):
    """
    /api/datasets 응답에 'ontology' dataset 이 active 상태로 포함되어야 한다.
    """
    resp = await client.get("/api/datasets")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    datasets = resp.json()["datasets"]

    names = [d["name"] for d in datasets]
    assert DS in names, f"'ontology' not found in {names}"

    onto = next(d for d in datasets if d["name"] == DS)
    assert onto["state"] == "active", f"Expected active, got {onto['state']}"


# ────────────────────────────────────────────────
# TC03 — INSERT 전: 테스트 Named Graph 없음
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_no_test_graph_before_insert(client):
    """
    트리플 INSERT 전에는 테스트 Named Graph IRI 가 목록에 없어야 한다.
    (clean_test_graph fixture 가 graph 를 삭제하므로 항상 clean 상태)
    """
    resp = await client.get(f"/api/datasets/{DS}/graphs")
    assert resp.status_code == 200
    graphs = resp.json()["graphs"]
    assert TEST_GRAPH not in graphs, f"Test graph should not exist yet, but found in {graphs}"


# ────────────────────────────────────────────────
# TC04 — INSERT 후 Named Graph 생성 확인
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_graph_created_after_insert(client, insert_test_data):
    """
    SPARQL INSERT DATA 실행 후 Named Graph IRI 가 목록에 등장해야 한다.
    """
    resp = await client.get(f"/api/datasets/{DS}/graphs")
    assert resp.status_code == 200
    graphs = resp.json()["graphs"]
    assert TEST_GRAPH in graphs, f"Expected {TEST_GRAPH} in {graphs}"


# ────────────────────────────────────────────────
# TC05 — Named Graph 내 Custom Namespace 추출
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_custom_namespace_in_graph(client, insert_test_data):
    """
    테스트 graph 의 namespace 목록에서 Custom IRI 의 base 가
    type='custom', prefix=None 으로 분류되어야 한다.
    """
    resp = await client.get(
        f"/api/datasets/{DS}/graphs/namespaces",
        params={"graph": TEST_GRAPH},
    )
    assert resp.status_code == 200
    namespaces = resp.json()["namespaces"]

    custom = next((n for n in namespaces if n["base_iri"] == CUSTOM_NS), None)
    assert custom is not None, f"{CUSTOM_NS} not found in {namespaces}"
    assert custom["type"] == "custom", f"Expected custom, got {custom['type']}"
    assert custom["prefix"] is None, f"Expected None prefix, got {custom['prefix']}"


# ────────────────────────────────────────────────
# TC06 — Named Graph 내 Universal Namespace 추출
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_universal_namespace_in_graph(client, insert_test_data):
    """
    테스트 graph 의 namespace 목록에서 rdfs base IRI 가
    type='universal', prefix='rdfs' 로 분류되어야 한다.
    """
    resp = await client.get(
        f"/api/datasets/{DS}/graphs/namespaces",
        params={"graph": TEST_GRAPH},
    )
    assert resp.status_code == 200
    namespaces = resp.json()["namespaces"]

    universal = next((n for n in namespaces if n["base_iri"] == UNIVERSAL_NS), None)
    assert universal is not None, f"{UNIVERSAL_NS} not found in {namespaces}"
    assert universal["type"] == "universal", f"Expected universal, got {universal['type']}"
    assert universal["prefix"] == "rdfs", f"Expected 'rdfs', got {universal['prefix']}"


# ────────────────────────────────────────────────
# TC07 — Dataset 전체 Namespace 조회
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_all_namespaces_in_dataset(client, insert_test_data):
    """
    /api/datasets/{ds}/namespaces 는 dataset 전체 graph 를 가로질러
    Custom 과 Universal namespace 를 모두 반환해야 한다.
    """
    resp = await client.get(f"/api/datasets/{DS}/namespaces")
    assert resp.status_code == 200
    namespaces = resp.json()["namespaces"]

    base_iris = [n["base_iri"] for n in namespaces]
    assert CUSTOM_NS in base_iris, f"Custom NS not found: {base_iris}"
    assert UNIVERSAL_NS in base_iris, f"Universal NS not found: {base_iris}"

    types = {n["base_iri"]: n["type"] for n in namespaces}
    assert types[CUSTOM_NS] == "custom"
    assert types[UNIVERSAL_NS] == "universal"


# ────────────────────────────────────────────────
# TC08 — Custom Namespace → Named Graphs 역방향 조회
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_custom_namespace_to_graphs(client, insert_test_data):
    """
    Custom namespace 로 역방향 조회 시 해당 namespace 가 속한
    Named Graph IRI 목록과 type='custom' 이 반환되어야 한다.
    """
    resp = await client.get(
        f"/api/datasets/{DS}/namespaces/graphs",
        params={"namespace": CUSTOM_NS},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["namespace"] == CUSTOM_NS
    assert body["type"] == "custom"
    assert TEST_GRAPH in body["graphs"], f"{TEST_GRAPH} not in {body['graphs']}"


# ────────────────────────────────────────────────
# TC09 — Universal Namespace → Named Graphs 역방향 조회
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_universal_namespace_to_graphs(client, insert_test_data):
    """
    Universal namespace (rdfs) 로 역방향 조회 시
    해당 namespace 가 속한 Named Graph 와 type='universal' 이 반환되어야 한다.
    """
    resp = await client.get(
        f"/api/datasets/{DS}/namespaces/graphs",
        params={"namespace": UNIVERSAL_NS},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["namespace"] == UNIVERSAL_NS
    assert body["type"] == "universal"
    assert TEST_GRAPH in body["graphs"], f"{TEST_GRAPH} not in {body['graphs']}"


# ────────────────────────────────────────────────
# TC10 — IRI Generator 고유성 보장 (100회)
# ────────────────────────────────────────────────

def test_tc10_iri_generator():
    """
    content-addressed IRI 생성기 검증.

    1) 같은 입력 (graph + label + 동일 timestamp) → 같은 IRI  [결정적]
    2) 다른 timestamp → 다른 IRI  [중복 허용]
    3) 다른 graph → 다른 IRI  [graph 스코프 분리]
    4) 다른 label → 다른 IRI
    5) 100개 연속 생성 시 모두 고유  [timestamp_ns 차이로 구분]
    6) 형식: {baseIRI}{PascalCaseSlug}_{64hex}
    """
    import time
    from unittest.mock import patch
    from services.iri import generate_iri

    BASE  = "http://test.example.org/onto#"
    GRAPH = "http://test.example.org/graph/main"
    LABEL = "person class"

    # ── 1) 결정적: 동일 timestamp → 동일 IRI
    fixed_ns = 1_700_000_000_000_000_000
    with patch("services.iri.time.time_ns", return_value=fixed_ns):
        iri_a = generate_iri(BASE, LABEL, GRAPH)
        iri_b = generate_iri(BASE, LABEL, GRAPH)
    assert iri_a == iri_b, "같은 입력이면 IRI가 같아야 한다"

    # ── 2) 다른 timestamp → 다른 IRI
    with patch("services.iri.time.time_ns", return_value=fixed_ns + 1):
        iri_c = generate_iri(BASE, LABEL, GRAPH)
    assert iri_a != iri_c, "timestamp 가 다르면 IRI 가 달라야 한다"

    # ── 3) 다른 graph → 다른 IRI
    with patch("services.iri.time.time_ns", return_value=fixed_ns):
        iri_other_graph = generate_iri(BASE, LABEL, "http://other.example.org/graph/x")
    assert iri_a != iri_other_graph, "graph 가 다르면 IRI 가 달라야 한다"

    # ── 4) 다른 label → 다른 IRI
    with patch("services.iri.time.time_ns", return_value=fixed_ns):
        iri_other_label = generate_iri(BASE, "organization", GRAPH)
    assert iri_a != iri_other_label, "label 이 다르면 IRI 가 달라야 한다"

    # ── 5) 연속 100개 고유성 (실제 timestamp_ns 사용)
    iris = [generate_iri(BASE, LABEL, GRAPH) for _ in range(100)]
    assert len(set(iris)) == 100, f"100개 중 중복 발생"

    # ── 6) 형식: base + PascalCaseSlug + _ + 64hex
    pattern = re.compile(
        r"^http://test\.example\.org/onto#"
        r"[A-Z][A-Za-z]*"       # PascalCase slug
        r"_[0-9a-f]{64}$"       # _ + 64자리 hex (SHA256)
    )
    for iri in iris:
        assert pattern.match(iri), f"IRI 형식 불일치: {iri}"
