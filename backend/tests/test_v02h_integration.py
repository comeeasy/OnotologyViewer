"""
v02-H 통합 테스트 — Object Property inverseOf 설정

테스트 데이터:
  dataset: ontology
  graph:   http://test.example.org/graph/v02h-test
  ns:      http://test.example.org/v02h/
  prop_a:  http://test.example.org/v02h/hasParent
  prop_b:  http://test.example.org/v02h/hasChild

TC01: POST /api/tbox/object-properties/{iri}/inverse → inverseOf 추가
TC02: 추가 후 GET ObjProp detail → inverse_of 필드에 prop_b 포함
TC03: 양방향 확인 — prop_b detail에도 prop_a가 inverseOf로 나타남
TC04: DELETE /api/tbox/object-properties/{iri}/inverse → inverseOf 삭제
TC05: 삭제 후 GET detail → inverse_of 비어 있음
TC06: 동일 관계 중복 추가 → 멱등 (이미 있으면 OK, 중복 트리플 없음)
TC07: 존재하지 않는 property에 inverse 추가 → 404
TC08: inverse_iri 빈 문자열 → 422
TC09: inverse_iri가 http 미시작 → 422
TC10: 존재하지 않는 inverse 관계 삭제 → 204 (graceful, DELETE DATA는 오류 없음)

실행:
  cd backend && pytest tests/test_v02h_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from urllib.parse import quote
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from fuseki.sparql import update as sparql_update
from main import app

DS = "ontology"
G  = "http://test.example.org/graph/v02h-test"
NS = "http://test.example.org/v02h/"
PROP_A = f"{NS}hasParent"
PROP_B = f"{NS}hasChild"

_DROP = f"DROP SILENT GRAPH <{G}>"
_SETUP = f"""
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
INSERT DATA {{
  GRAPH <{G}> {{
    <{PROP_A}> a owl:ObjectProperty ; rdfs:label "hasParent" .
    <{PROP_B}> a owl:ObjectProperty ; rdfs:label "hasChild" .
  }}
}}
"""

def enc(iri: str) -> str:
    return quote(iri, safe="")


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


# ── TC01 — inverseOf 추가 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_add_inverse(client):
    """POST /inverse → 201, inverseOf 트리플이 삽입된다."""
    resp = await client.post(
        f"/api/tbox/object-properties/{enc(PROP_A)}/inverse",
        json={"dataset": DS, "graph": G, "inverse_iri": PROP_B},
    )
    assert resp.status_code == 201, resp.text


# ── TC02 — GET detail → inverse_of 포함 ───────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_detail_has_inverse(client):
    """inverseOf 추가 후 GET detail에 inverse_of 목록이 표시된다."""
    p = {"dataset": DS, "graph": G}
    resp = await client.get(f"/api/tbox/object-properties/{enc(PROP_A)}", params=p)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "inverse_of" in body, f"inverse_of 필드 없음: {body}"
    assert PROP_B in body["inverse_of"], f"{PROP_B} not in {body['inverse_of']}"


# ── TC03 — 양방향 확인 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_symmetric_inverse(client):
    """owl:inverseOf는 대칭적이므로 prop_b detail에도 prop_a가 나타난다."""
    p = {"dataset": DS, "graph": G}
    resp = await client.get(f"/api/tbox/object-properties/{enc(PROP_B)}", params=p)
    assert resp.status_code == 200
    body = resp.json()
    # owl:inverseOf 는 symmetric 이므로 SPARQL에서 양방향 조회
    inv = body.get("inverse_of", [])
    assert PROP_A in inv, f"{PROP_A} not in {inv} (prop_b detail)"


# ── TC04 — inverseOf 삭제 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_delete_inverse(client):
    """DELETE /inverse → 204, 관계 트리플이 삭제된다."""
    p = new_params = {"dataset": DS, "graph": G, "inverse_iri": PROP_B}
    resp = await client.delete(
        f"/api/tbox/object-properties/{enc(PROP_A)}/inverse",
        params=p,
    )
    assert resp.status_code == 204, resp.text


# ── TC05 — 삭제 후 detail → inverse_of 비어 있음 ──────────────────────────

@pytest.mark.asyncio
async def test_tc05_empty_after_delete(client):
    """inverseOf 삭제 후 GET detail의 inverse_of가 비어 있다."""
    p = {"dataset": DS, "graph": G}
    resp = await client.get(f"/api/tbox/object-properties/{enc(PROP_A)}", params=p)
    body = resp.json()
    inv = body.get("inverse_of", [])
    assert PROP_B not in inv, f"{PROP_B} still in {inv}"


# ── TC06 — 중복 추가 멱등 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_idempotent_add(client):
    """같은 inverseOf를 두 번 추가해도 트리플 중복이 없다."""
    body = {"dataset": DS, "graph": G, "inverse_iri": PROP_B}
    await client.post(f"/api/tbox/object-properties/{enc(PROP_A)}/inverse", json=body)
    await client.post(f"/api/tbox/object-properties/{enc(PROP_A)}/inverse", json=body)

    p = {"dataset": DS, "graph": G}
    resp = await client.get(f"/api/tbox/object-properties/{enc(PROP_A)}", params=p)
    inv = resp.json().get("inverse_of", [])
    assert inv.count(PROP_B) == 1, f"중복 발생: {inv}"


# ── TC07 — 존재하지 않는 property → 404 ───────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_nonexistent_property_404(client):
    """존재하지 않는 property IRI에 inverse 추가 시 404를 반환한다."""
    ghost = f"{NS}ghostProp"
    resp = await client.post(
        f"/api/tbox/object-properties/{enc(ghost)}/inverse",
        json={"dataset": DS, "graph": G, "inverse_iri": PROP_B},
    )
    assert resp.status_code == 404, resp.text


# ── TC08 — 빈 inverse_iri → 422 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_empty_inverse_iri_422(client):
    """inverse_iri가 빈 문자열이면 422를 반환한다."""
    resp = await client.post(
        f"/api/tbox/object-properties/{enc(PROP_A)}/inverse",
        json={"dataset": DS, "graph": G, "inverse_iri": ""},
    )
    assert resp.status_code == 422, resp.text


# ── TC09 — http 미시작 inverse_iri → 422 ──────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_non_http_inverse_iri_422(client):
    """inverse_iri가 http/https로 시작하지 않으면 422를 반환한다."""
    resp = await client.post(
        f"/api/tbox/object-properties/{enc(PROP_A)}/inverse",
        json={"dataset": DS, "graph": G, "inverse_iri": "urn:example:prop"},
    )
    assert resp.status_code == 422, resp.text


# ── TC10 — 없는 inverse 관계 삭제 → 204 graceful ─────────────────────────

@pytest.mark.asyncio
async def test_tc10_delete_nonexistent_inverse_graceful(client):
    """존재하지 않는 inverseOf 관계를 삭제해도 204로 응답한다 (멱등)."""
    ghost_prop = f"{NS}neverAdded"
    resp = await client.delete(
        f"/api/tbox/object-properties/{enc(PROP_A)}/inverse",
        params={"dataset": DS, "graph": G, "inverse_iri": ghost_prop},
    )
    assert resp.status_code == 204, resp.text
