"""
v02-D 통합 테스트 — Class 계층 편집 (subClassOf 추가/삭제)

테스트 데이터:
  dataset: ontology
  graph:   http://test.example.org/graph/v02d-test
  ns:      http://test.example.org/v02d/

  Animal   (최상위)
  Mammal   (Animal의 하위)
  Dog      (Mammal의 하위)
  Cat      (Mammal의 하위)
  Vehicle  (무관한 Class)

TC01: POST /super-classes → Animal을 Mammal의 상위 Class로 추가
TC02: 추가 후 GET detail → super_classes에 Animal 포함, sub_classes에 Mammal 포함
TC03: POST → Mammal을 Dog의 상위 Class로 추가 (2-depth 계층)
TC04: GET Dog detail → super_classes에 Mammal 포함
TC05: DELETE /super-classes/{parent} → Animal-Mammal 관계 삭제
TC06: 삭제 후 Mammal detail → super_classes에 Animal 없음
TC07: 순환 참조 방지 — Mammal을 Dog의 상위 추가 상태에서 Dog를 Mammal 상위로 추가 → 400
TC08: 존재하지 않는 child class에 super 추가 → 404
TC09: 존재하지 않는 parent class에 super 추가 → 404
TC10: 없는 관계 DELETE → 204 graceful

실행:
  cd backend && pytest tests/test_v02d_integration.py -v
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
G  = "http://test.example.org/graph/v02d-test"
NS = "http://test.example.org/v02d/"

CLS_ANIMAL  = f"{NS}Animal"
CLS_MAMMAL  = f"{NS}Mammal"
CLS_DOG     = f"{NS}Dog"
CLS_CAT     = f"{NS}Cat"
CLS_VEHICLE = f"{NS}Vehicle"

_DROP = f"DROP SILENT GRAPH <{G}>"
_SETUP = f"""
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
INSERT DATA {{
  GRAPH <{G}> {{
    <{CLS_ANIMAL}>  a owl:Class ; rdfs:label "Animal" .
    <{CLS_MAMMAL}>  a owl:Class ; rdfs:label "Mammal" .
    <{CLS_DOG}>     a owl:Class ; rdfs:label "Dog" .
    <{CLS_CAT}>     a owl:Class ; rdfs:label "Cat" .
    <{CLS_VEHICLE}> a owl:Class ; rdfs:label "Vehicle" .
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


# ── TC01 — Animal을 Mammal의 상위로 추가 ───────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_add_super_class(client):
    """POST /super-classes → 201, Mammal subClassOf Animal 트리플 삽입."""
    resp = await client.post(
        f"/api/tbox/classes/{enc(CLS_MAMMAL)}/super-classes",
        json={"dataset": DS, "graph": G, "parent_iri": CLS_ANIMAL},
    )
    assert resp.status_code == 201, resp.text


# ── TC02 — Mammal detail에 Animal 포함 ────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_detail_has_super_class(client):
    """추가 후 Mammal detail의 super_classes에 Animal이 포함된다."""
    p = {"dataset": DS, "graph": G, "namespace": NS}
    resp = await client.get(f"/api/tbox/classes/{enc(CLS_MAMMAL)}", params=p)
    assert resp.status_code == 200
    body = resp.json()
    assert CLS_ANIMAL in body["super_classes"], f"Animal not in {body['super_classes']}"


# ── TC03 — Mammal을 Dog의 상위로 추가 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_add_second_super_class(client):
    """Dog subClassOf Mammal 추가 → 201."""
    resp = await client.post(
        f"/api/tbox/classes/{enc(CLS_DOG)}/super-classes",
        json={"dataset": DS, "graph": G, "parent_iri": CLS_MAMMAL},
    )
    assert resp.status_code == 201, resp.text


# ── TC04 — Dog detail에 Mammal 포함 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_dog_detail_has_mammal(client):
    """Dog detail의 super_classes에 Mammal이 포함된다."""
    p = {"dataset": DS, "graph": G, "namespace": NS}
    resp = await client.get(f"/api/tbox/classes/{enc(CLS_DOG)}", params=p)
    body = resp.json()
    assert CLS_MAMMAL in body["super_classes"]


# ── TC05 — Animal-Mammal 관계 삭제 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_delete_super_class(client):
    """DELETE /super-classes/{parent} → 204."""
    resp = await client.delete(
        f"/api/tbox/classes/{enc(CLS_MAMMAL)}/super-classes/{enc(CLS_ANIMAL)}",
        params={"dataset": DS, "graph": G},
    )
    assert resp.status_code == 204, resp.text


# ── TC06 — 삭제 후 Animal 없음 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_super_class_removed(client):
    """삭제 후 Mammal detail의 super_classes에 Animal이 없다."""
    p = {"dataset": DS, "graph": G, "namespace": NS}
    resp = await client.get(f"/api/tbox/classes/{enc(CLS_MAMMAL)}", params=p)
    body = resp.json()
    assert CLS_ANIMAL not in body["super_classes"]


# ── TC07 — 순환 참조 방지 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_circular_reference_rejected(client):
    """Mammal이 Dog의 상위인 상태에서 Dog를 Mammal의 상위로 추가하면 400을 반환한다."""
    # TC03에서 Dog subClassOf Mammal 을 추가했음
    resp = await client.post(
        f"/api/tbox/classes/{enc(CLS_MAMMAL)}/super-classes",
        json={"dataset": DS, "graph": G, "parent_iri": CLS_DOG},
    )
    assert resp.status_code == 400, f"Expected 400 (circular ref), got {resp.status_code}"


# ── TC08 — 존재하지 않는 child → 404 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_nonexistent_child_404(client):
    """존재하지 않는 child class에 super 추가 시 404를 반환한다."""
    ghost = f"{NS}GhostClass"
    resp = await client.post(
        f"/api/tbox/classes/{enc(ghost)}/super-classes",
        json={"dataset": DS, "graph": G, "parent_iri": CLS_ANIMAL},
    )
    assert resp.status_code == 404, resp.text


# ── TC09 — 존재하지 않는 parent → 404 ────────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_nonexistent_parent_404(client):
    """존재하지 않는 parent class를 상위로 추가 시 404를 반환한다."""
    ghost = f"{NS}GhostParent"
    resp = await client.post(
        f"/api/tbox/classes/{enc(CLS_CAT)}/super-classes",
        json={"dataset": DS, "graph": G, "parent_iri": ghost},
    )
    assert resp.status_code == 404, resp.text


# ── TC10 — 없는 관계 DELETE → 204 graceful ────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_delete_nonexistent_relation_graceful(client):
    """존재하지 않는 subClassOf 관계를 삭제해도 204로 응답한다."""
    resp = await client.delete(
        f"/api/tbox/classes/{enc(CLS_CAT)}/super-classes/{enc(CLS_VEHICLE)}",
        params={"dataset": DS, "graph": G},
    )
    assert resp.status_code == 204, resp.text
