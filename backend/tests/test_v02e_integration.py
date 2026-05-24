"""
v02-E 통합 테스트 — Individual Class 마이그레이션

TC01: 호환 가능한 클래스로 마이그레이션 → rdf:type 변경 확인
TC02: 비호환 property가 있을 때 keep 옵션 → property 보존
TC03: 비호환 property가 있을 때 delete 옵션 → property 삭제
TC04: 마이그레이션 미리보기 → 비호환 prop 목록 반환
TC05: 존재하지 않는 클래스로 마이그레이션 → 404
TC06: 존재하지 않는 Individual 마이그레이션 → 404
TC07: 같은 클래스로 마이그레이션 → 성공 (no-op)
TC08: 잘못된 new_class_iri → 422
TC09: 마이그레이션 후 새 클래스의 individual 목록에 포함
TC10: property 없는 Individual 마이그레이션 → 성공

실행:
  cd backend && pytest tests/test_v02e_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app
from fuseki.sparql import query as sparql_query, update as sparql_update

TEST_DS    = "ontology"
TEST_GRAPH = "http://v02e-migrate-test.example.org/graph"
NS         = "http://v02e-migrate-test.example.org/ns#"

CLASS_A  = f"{NS}ClassA"
CLASS_B  = f"{NS}ClassB"
PROP_AGE = f"{NS}hasAge"    # domain = ClassA (not ClassB)
PROP_NAME = f"{NS}hasName"  # domain = ClassA and ClassB (compatible)

IND_ALICE = f"{NS}Alice"
IND_BOB   = f"{NS}Bob"
IND_CAROL = f"{NS}Carol"     # no properties


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _setup_graph():
    """테스트 그래프 초기화: ClassA/ClassB + properties + individuals."""
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"""
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{
        <{TEST_GRAPH}> a owl:Ontology .

        <{CLASS_A}>  a owl:Class ; rdfs:label "ClassA" .
        <{CLASS_B}>  a owl:Class ; rdfs:label "ClassB" .

        # hasAge: domain = ClassA only → 비호환 prop for ClassB migration
        <{PROP_AGE}> a owl:DatatypeProperty ;
            rdfs:label "hasAge" ;
            rdfs:domain <{CLASS_A}> ;
            rdfs:range  xsd:integer .

        # hasName: domain = ClassA and ClassB → 호환 prop
        <{PROP_NAME}> a owl:DatatypeProperty ;
            rdfs:label "hasName" ;
            rdfs:domain <{CLASS_A}> ;
            rdfs:domain <{CLASS_B}> ;
            rdfs:range  xsd:string .

        # Alice: ClassA individual with both hasAge and hasName
        <{IND_ALICE}> a <{CLASS_A}> ;
            rdfs:label "Alice" ;
            <{PROP_AGE}>  "30"^^xsd:integer ;
            <{PROP_NAME}> "Alice Smith"^^xsd:string .

        # Bob: ClassA individual with only hasName (compatible)
        <{IND_BOB}> a <{CLASS_A}> ;
            rdfs:label "Bob" ;
            <{PROP_NAME}> "Bob Jones"^^xsd:string .

        # Carol: ClassA individual with no properties
        <{IND_CAROL}> a <{CLASS_A}> ;
            rdfs:label "Carol" .
      }}
    }}
    """)


@pytest.fixture(autouse=True, scope="module")
async def cleanup(client):
    _setup_graph()
    yield
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")


# ── TC01: 호환 클래스 마이그레이션 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_migrate_compatible_class(client):
    """Bob(ClassA → ClassB) — hasName은 양쪽에 도메인 있으므로 호환"""
    from urllib.parse import quote
    iri_enc = quote(IND_BOB, safe="")
    resp = await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": CLASS_B,
            "incompatible_props": "keep",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["new_class_iri"] == CLASS_B

    # 확인: rdf:type이 ClassB 로 바뀌었는지
    rows = sparql_query(TEST_DS, f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?class WHERE {{
      GRAPH <{TEST_GRAPH}> {{ <{IND_BOB}> rdf:type ?class . }}
    }}
    """)
    classes = [r["class"] for r in rows]
    assert CLASS_B in classes, f"Expected {CLASS_B} in {classes}"
    assert CLASS_A not in classes, f"ClassA should be removed, got {classes}"


# ── TC02: 비호환 prop — keep ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_migrate_with_incompatible_keep(client):
    """Alice(ClassA → ClassB), incompatible_props='keep' → hasAge 보존"""
    from urllib.parse import quote
    _setup_graph()  # Alice를 ClassA로 리셋
    iri_enc = quote(IND_ALICE, safe="")
    resp = await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": CLASS_B,
            "incompatible_props": "keep",
        },
    )
    assert resp.status_code == 200, resp.text

    # hasAge 값이 보존되어야 함
    rows = sparql_query(TEST_DS, f"""
    SELECT ?v WHERE {{
      GRAPH <{TEST_GRAPH}> {{ <{IND_ALICE}> <{PROP_AGE}> ?v . }}
    }}
    """)
    assert len(rows) == 1, f"hasAge should be preserved, got {rows}"
    assert rows[0]["v"] == "30"


# ── TC03: 비호환 prop — delete ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_migrate_with_incompatible_delete(client):
    """Alice(ClassA → ClassB), incompatible_props='delete' → hasAge 삭제"""
    from urllib.parse import quote
    _setup_graph()  # Alice를 ClassA로 리셋
    iri_enc = quote(IND_ALICE, safe="")
    resp = await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": CLASS_B,
            "incompatible_props": "delete",
        },
    )
    assert resp.status_code == 200, resp.text

    # hasAge 트리플이 삭제되어야 함
    rows = sparql_query(TEST_DS, f"""
    SELECT ?v WHERE {{
      GRAPH <{TEST_GRAPH}> {{ <{IND_ALICE}> <{PROP_AGE}> ?v . }}
    }}
    """)
    assert rows == [], f"hasAge should be deleted, got {rows}"

    # hasName은 보존
    rows2 = sparql_query(TEST_DS, f"""
    SELECT ?v WHERE {{
      GRAPH <{TEST_GRAPH}> {{ <{IND_ALICE}> <{PROP_NAME}> ?v . }}
    }}
    """)
    assert len(rows2) == 1, f"hasName should be preserved"


# ── TC04: 마이그레이션 미리보기 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_migrate_preview(client):
    """GET preview → 비호환 prop 목록 반환"""
    from urllib.parse import quote
    _setup_graph()  # Alice를 ClassA로 리셋
    iri_enc = quote(IND_ALICE, safe="")
    resp = await client.get(
        f"/api/abox/individuals/{iri_enc}/class-migrate-preview",
        params={"dataset": TEST_DS, "graph": TEST_GRAPH, "new_class_iri": CLASS_B},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "incompatible_properties" in data
    # hasAge는 비호환 (ClassB에 domain 없음)
    assert PROP_AGE in data["incompatible_properties"], \
        f"Expected {PROP_AGE} in incompatible: {data['incompatible_properties']}"


# ── TC05: 존재하지 않는 클래스 → 404 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_nonexistent_class_404(client):
    from urllib.parse import quote
    iri_enc = quote(IND_ALICE, safe="")
    resp = await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": f"{NS}NonExistentClass",
            "incompatible_props": "keep",
        },
    )
    assert resp.status_code == 404, resp.text


# ── TC06: 존재하지 않는 Individual → 404 ─────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_nonexistent_individual_404(client):
    from urllib.parse import quote
    fake = f"{NS}FakeIndividual"
    iri_enc = quote(fake, safe="")
    resp = await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": CLASS_B,
            "incompatible_props": "keep",
        },
    )
    assert resp.status_code == 404, resp.text


# ── TC07: 같은 클래스로 마이그레이션 → 성공 ─────────────────────────────

@pytest.mark.asyncio
async def test_tc07_migrate_same_class(client):
    """Carol(ClassA → ClassA) — no-op, success"""
    from urllib.parse import quote
    _setup_graph()
    iri_enc = quote(IND_CAROL, safe="")
    resp = await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": CLASS_A,
            "incompatible_props": "keep",
        },
    )
    assert resp.status_code == 200, resp.text

    rows = sparql_query(TEST_DS, f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?class WHERE {{
      GRAPH <{TEST_GRAPH}> {{ <{IND_CAROL}> rdf:type ?class . }}
    }}
    """)
    assert any(r["class"] == CLASS_A for r in rows)


# ── TC08: 잘못된 new_class_iri → 422 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_invalid_class_iri_422(client):
    from urllib.parse import quote
    iri_enc = quote(IND_CAROL, safe="")
    resp = await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": "not-a-valid-iri",
            "incompatible_props": "keep",
        },
    )
    assert resp.status_code == 422, resp.text


# ── TC09: 마이그레이션 후 새 클래스 individual 목록에 포함 ──────────────

@pytest.mark.asyncio
async def test_tc09_appears_in_new_class_list(client):
    """Carol(ClassA → ClassB) 후 ClassB individual 목록에 Carol 포함"""
    from urllib.parse import quote
    _setup_graph()
    iri_enc = quote(IND_CAROL, safe="")
    await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": CLASS_B,
            "incompatible_props": "keep",
        },
    )
    resp = await client.get(
        "/api/abox/individuals",
        params={"dataset": TEST_DS, "graph": TEST_GRAPH, "namespace": NS, "class_iri": CLASS_B},
    )
    assert resp.status_code == 200, resp.text
    iris = [i["iri"] for i in resp.json()["individuals"]]
    assert IND_CAROL in iris, f"Carol should be in ClassB list: {iris}"
    assert IND_ALICE not in iris, f"Alice should not be in ClassB list (still ClassA)"


# ── TC10: property 없는 Individual 마이그레이션 ───────────────────────────

@pytest.mark.asyncio
async def test_tc10_migrate_no_properties(client):
    """Carol (property 없음) 마이그레이션 → 성공"""
    from urllib.parse import quote
    _setup_graph()
    iri_enc = quote(IND_CAROL, safe="")
    resp = await client.patch(
        f"/api/abox/individuals/{iri_enc}/class",
        json={
            "dataset": TEST_DS,
            "graph": TEST_GRAPH,
            "new_class_iri": CLASS_B,
            "incompatible_props": "delete",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["new_class_iri"] == CLASS_B
    assert data["deleted_properties"] == []
