"""
v02-I 통합 테스트 — Namespace 복수 선택

배경:
  모든 API가 namespace: str (단일)로 구현됨.
  v02-I에서 namespace 복수 전달을 지원한다.
  쿼리 파라미터: namespace=A&namespace=B (FILTER OR 조건)

테스트 데이터:
  dataset: ontology
  graph:   http://test.example.org/graph/v02i-test
  ns_a:    http://test.example.org/v02i/nsA/
  ns_b:    http://test.example.org/v02i/nsB/
  ns_c:    http://test.example.org/v02i/nsC/ (포함하지 않음 → 필터링)

TC01: GET /api/tbox/classes?namespace=nsA&namespace=nsB → nsA + nsB 클래스 반환
TC02: GET /api/tbox/classes?namespace=nsA → nsA 클래스만 반환
TC03: GET /api/tbox/classes?namespace=nsC → 없음 반환
TC04: GET /api/tbox/object-properties?namespace=nsA&namespace=nsB → nsA + nsB 프로퍼티
TC05: GET /api/tbox/data-properties?namespace=nsA&namespace=nsB → nsA + nsB 프로퍼티
TC06: GET /api/abox/individuals?namespace=nsA&namespace=nsB → nsA + nsB 인디비주얼
TC07: namespace 파라미터 없음 → 422
TC08: 빈 namespace 값 → 422
TC09: namespace 3개 전달 → 모두 포함
TC10: namespace 중복 전달 → 결과 중복 없음

실행:
  cd backend && pytest tests/test_v02i_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from fuseki.sparql import update as sparql_update
from main import app

DS  = "ontology"
G   = "http://test.example.org/graph/v02i-test"
NSA = "http://test.example.org/v02i/nsA/"
NSB = "http://test.example.org/v02i/nsB/"
NSC = "http://test.example.org/v02i/nsC/"

_DROP = f"DROP SILENT GRAPH <{G}>"
_SETUP = f"""
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
INSERT DATA {{
  GRAPH <{G}> {{
    <{NSA}ClassA1>  a owl:Class          ; rdfs:label "ClassA1" .
    <{NSA}ClassA2>  a owl:Class          ; rdfs:label "ClassA2" .
    <{NSB}ClassB1>  a owl:Class          ; rdfs:label "ClassB1" .
    <{NSA}PropA1>   a owl:ObjectProperty ; rdfs:label "PropA1" .
    <{NSB}PropB1>   a owl:ObjectProperty ; rdfs:label "PropB1" .
    <{NSA}DataA1>   a owl:DatatypeProperty ; rdfs:label "DataA1" ;
                    rdfs:domain <{NSA}ClassA1> .
    <{NSB}DataB1>   a owl:DatatypeProperty ; rdfs:label "DataB1" ;
                    rdfs:domain <{NSB}ClassB1> .
    <{NSA}IndA1>    a <{NSA}ClassA1>      .
    <{NSB}IndB1>    a <{NSB}ClassB1>      .
  }}
}}
"""


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True, scope="module")
def setup_graph():
    sparql_update(DS, _DROP)
    sparql_update(DS, _SETUP)
    yield
    sparql_update(DS, _DROP)


# ── TC01 — 복수 namespace → nsA+nsB 클래스 ────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_multi_namespace_classes(client):
    """namespace=nsA&namespace=nsB → nsA·nsB 양쪽 클래스를 반환한다."""
    resp = await client.get(
        f"/api/tbox/classes",
        params=[("dataset", DS), ("graph", G), ("namespace", NSA), ("namespace", NSB)],
    )
    assert resp.status_code == 200, resp.text
    iris = [c["iri"] for c in resp.json()["classes"]]
    assert f"{NSA}ClassA1" in iris
    assert f"{NSA}ClassA2" in iris
    assert f"{NSB}ClassB1" in iris


# ── TC02 — 단일 namespace → nsA만 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_single_namespace_only_a(client):
    """namespace=nsA → nsA 클래스만 반환하고 nsB 클래스는 없다."""
    resp = await client.get(
        f"/api/tbox/classes",
        params=[("dataset", DS), ("graph", G), ("namespace", NSA)],
    )
    iris = [c["iri"] for c in resp.json()["classes"]]
    assert f"{NSA}ClassA1" in iris
    assert f"{NSB}ClassB1" not in iris


# ── TC03 — nsC → 빈 결과 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_empty_namespace_result(client):
    """namespace=nsC는 해당 클래스가 없으므로 빈 목록을 반환한다."""
    resp = await client.get(
        f"/api/tbox/classes",
        params=[("dataset", DS), ("graph", G), ("namespace", NSC)],
    )
    assert resp.status_code == 200
    assert resp.json()["classes"] == []


# ── TC04 — ObjProp 복수 namespace ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_multi_namespace_objprops(client):
    """namespace=nsA&namespace=nsB → nsA·nsB Object Property 모두 반환."""
    resp = await client.get(
        f"/api/tbox/object-properties",
        params=[("dataset", DS), ("graph", G), ("namespace", NSA), ("namespace", NSB)],
    )
    assert resp.status_code == 200
    iris = [p["iri"] for p in resp.json()["object_properties"]]
    assert f"{NSA}PropA1" in iris
    assert f"{NSB}PropB1" in iris


# ── TC05 — DataProp 복수 namespace ────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_multi_namespace_dataprops(client):
    """namespace=nsA&namespace=nsB → nsA·nsB Data Property 모두 반환."""
    resp = await client.get(
        f"/api/tbox/data-properties",
        params=[("dataset", DS), ("graph", G), ("namespace", NSA), ("namespace", NSB)],
    )
    assert resp.status_code == 200
    iris = [p["iri"] for p in resp.json()["data_properties"]]
    assert f"{NSA}DataA1" in iris
    assert f"{NSB}DataB1" in iris


# ── TC06 — Individual 복수 namespace ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_multi_namespace_individuals(client):
    """namespace=nsA&namespace=nsB → nsA·nsB Individual 모두 반환."""
    resp = await client.get(
        f"/api/abox/individuals",
        params=[("dataset", DS), ("graph", G), ("namespace", NSA), ("namespace", NSB)],
    )
    assert resp.status_code == 200
    iris = [i["iri"] for i in resp.json()["individuals"]]
    assert f"{NSA}IndA1" in iris
    assert f"{NSB}IndB1" in iris


# ── TC07 — namespace 없음 → 422 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_missing_namespace_422(client):
    """namespace 파라미터가 없으면 422를 반환한다."""
    resp = await client.get(
        f"/api/tbox/classes",
        params=[("dataset", DS), ("graph", G)],
    )
    assert resp.status_code == 422, resp.text


# ── TC08 — 빈 namespace → 422 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_empty_namespace_422(client):
    """빈 namespace 값은 422를 반환한다."""
    resp = await client.get(
        f"/api/tbox/classes",
        params=[("dataset", DS), ("graph", G), ("namespace", "")],
    )
    assert resp.status_code == 422, resp.text


# ── TC09 — namespace 3개 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_three_namespaces(client):
    """namespace를 3개 전달해도 모두 포함한 결과를 반환한다."""
    resp = await client.get(
        f"/api/tbox/classes",
        params=[
            ("dataset", DS), ("graph", G),
            ("namespace", NSA), ("namespace", NSB), ("namespace", NSC),
        ],
    )
    assert resp.status_code == 200
    iris = [c["iri"] for c in resp.json()["classes"]]
    assert f"{NSA}ClassA1" in iris
    assert f"{NSB}ClassB1" in iris


# ── TC10 — 중복 namespace → 결과 중복 없음 ────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_duplicate_namespace_no_dup(client):
    """같은 namespace를 두 번 전달해도 결과에 중복이 없다."""
    resp = await client.get(
        f"/api/tbox/classes",
        params=[("dataset", DS), ("graph", G), ("namespace", NSA), ("namespace", NSA)],
    )
    assert resp.status_code == 200
    iris = [c["iri"] for c in resp.json()["classes"]]
    assert len(iris) == len(set(iris)), f"중복 발생: {iris}"
