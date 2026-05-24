"""
v02-C 통합 테스트 — Namespace CRUD (선언·prefix 수정·IRI 일괄 치환·삭제)

TC01: POST /api/datasets/{ds}/graphs/namespaces → 새 namespace 선언 (201)
TC02: 선언 후 GET namespaces → prefix와 함께 반환
TC03: PATCH prefix 수정 → 새 prefix로 갱신
TC04: GET rename-preview → 영향받는 triple 수 반환
TC05: POST rename → 모든 subject IRI가 새 namespace로 갱신
TC06: POST rename → object로 등장하는 IRI도 갱신
TC07: DELETE namespace → 선언 + subject 트리플 모두 삭제
TC08: 중복 namespace 선언 → 409 Conflict
TC09: 존재하지 않는 namespace prefix 수정 → 404
TC10: 잘못된 IRI (http 아님) 선언 → 422

실행:
  cd backend && pytest tests/test_v02c_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app
from fuseki.sparql import query as sparql_query, update as sparql_update

TEST_DS    = "ontology"
TEST_GRAPH = "http://v02c-ns-test.example.org/graph"
OLD_NS     = "http://v02c-ns-test.example.org/ont#"
NEW_NS     = "http://v02c-ns-renamed.example.org/ont#"


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _drop_graph():
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")


def _seed_graph():
    """테스트용 그래프에 OLD_NS 기반 트리플을 삽입."""
    sparql_update(TEST_DS, f"""
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{
        <{TEST_GRAPH}> a owl:Ontology .
        <{OLD_NS}Person>  a owl:Class ; rdfs:label "Person" .
        <{OLD_NS}Vehicle> a owl:Class ; rdfs:label "Vehicle" .
        <{OLD_NS}drives> a owl:ObjectProperty ;
            rdfs:domain <{OLD_NS}Person> ;
            rdfs:range  <{OLD_NS}Vehicle> .
      }}
    }}
    """)


@pytest.fixture(autouse=True, scope="module")
async def cleanup(client):
    await _drop_graph()
    yield
    await _drop_graph()


# ── TC01: 새 namespace 선언 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_declare_namespace(client):
    """POST namespaces → 201"""
    await _drop_graph()
    _seed_graph()
    resp = await client.post(
        f"/api/datasets/{TEST_DS}/graphs/namespaces",
        json={"graph": TEST_GRAPH, "ns_iri": OLD_NS, "prefix": "v02c"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["ns_iri"] == OLD_NS
    assert data["prefix"] == "v02c"


# ── TC02: 선언 후 목록에 prefix 포함 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_namespace_appears_with_prefix(client):
    """GET namespaces → declared namespace에 prefix 반환"""
    resp = await client.get(
        f"/api/datasets/{TEST_DS}/graphs/namespaces",
        params={"graph": TEST_GRAPH},
    )
    assert resp.status_code == 200, resp.text
    namespaces = resp.json()["namespaces"]
    # OLD_NS 가 prefix='v02c' 로 목록에 있어야 한다
    found = next((n for n in namespaces if n["base_iri"] == OLD_NS), None)
    assert found is not None, f"{OLD_NS} not in namespaces"
    assert found["prefix"] == "v02c"


# ── TC03: prefix 수정 ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_update_prefix(client):
    """PATCH prefix → 새 prefix로 갱신"""
    resp = await client.patch(
        f"/api/datasets/{TEST_DS}/graphs/namespaces",
        json={"graph": TEST_GRAPH, "ns_iri": OLD_NS, "prefix": "renamed"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["prefix"] == "renamed"

    # 확인: GET에서도 갱신된 prefix 반환
    resp2 = await client.get(
        f"/api/datasets/{TEST_DS}/graphs/namespaces",
        params={"graph": TEST_GRAPH},
    )
    found = next((n for n in resp2.json()["namespaces"] if n["base_iri"] == OLD_NS), None)
    assert found is not None
    assert found["prefix"] == "renamed"


# ── TC04: rename preview ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_rename_preview(client):
    """GET rename-preview → 영향받는 triple 수 반환 (≥ 1)"""
    resp = await client.get(
        f"/api/datasets/{TEST_DS}/graphs/namespaces/rename-preview",
        params={"graph": TEST_GRAPH, "old_ns": OLD_NS, "new_ns": NEW_NS},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "affected_triples" in data
    # OLD_NS로 시작하는 subject: Person, Vehicle, drives → 트리플 여러 개
    # domain/range object도 포함되므로 >= 5
    assert data["affected_triples"] >= 5


# ── TC05: rename → subject IRI 갱신 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_rename_subjects(client):
    """POST rename → 모든 subject IRI가 NEW_NS로 갱신"""
    resp = await client.post(
        f"/api/datasets/{TEST_DS}/graphs/namespaces/rename",
        json={"graph": TEST_GRAPH, "old_ns": OLD_NS, "new_ns": NEW_NS},
    )
    assert resp.status_code == 200, resp.text

    # OLD_NS subject가 없어야 함
    rows_old = sparql_query(TEST_DS, f"""
    SELECT ?s WHERE {{
      GRAPH <{TEST_GRAPH}> {{
        ?s ?p ?o .
        FILTER(STRSTARTS(str(?s), "{OLD_NS}"))
      }}
    }} LIMIT 1
    """)
    assert rows_old == [], f"Old IRI subjects still present: {rows_old}"

    # NEW_NS subject가 있어야 함
    rows_new = sparql_query(TEST_DS, f"""
    SELECT ?s WHERE {{
      GRAPH <{TEST_GRAPH}> {{
        ?s ?p ?o .
        FILTER(STRSTARTS(str(?s), "{NEW_NS}"))
      }}
    }} LIMIT 1
    """)
    assert len(rows_new) > 0, "New IRI subjects not found"


# ── TC06: rename → object IRI도 갱신 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_rename_objects(client):
    """rename 후 object IRI도 NEW_NS로 갱신"""
    # domain/range 는 object 위치에 OLD_NS IRI를 가지고 있었음
    rows_old_obj = sparql_query(TEST_DS, f"""
    SELECT ?o WHERE {{
      GRAPH <{TEST_GRAPH}> {{
        ?s ?p ?o .
        FILTER(STRSTARTS(str(?o), "{OLD_NS}") && isIRI(?o))
      }}
    }} LIMIT 1
    """)
    assert rows_old_obj == [], f"Old IRI objects still present: {rows_old_obj}"

    rows_new_obj = sparql_query(TEST_DS, f"""
    SELECT ?o WHERE {{
      GRAPH <{TEST_GRAPH}> {{
        ?s ?p ?o .
        FILTER(STRSTARTS(str(?o), "{NEW_NS}") && isIRI(?o))
      }}
    }} LIMIT 1
    """)
    assert len(rows_new_obj) > 0, "New IRI objects not found"


# ── TC07: namespace 선언 삭제 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_delete_namespace(client):
    """DELETE namespaces → 선언 + subject 트리플 모두 삭제"""
    # 새 graph / namespace로 다시 세팅
    TEST_GRAPH2 = "http://v02c-del-test.example.org/graph"
    DEL_NS = "http://v02c-del-test.example.org/ns#"
    try:
        sparql_update(TEST_DS, f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
          GRAPH <{TEST_GRAPH2}> {{
            <{TEST_GRAPH2}> a owl:Ontology .
            <{DEL_NS}Foo> a owl:Class ; rdfs:label "Foo" .
          }}
        }}
        """)
        # declare
        await client.post(
            f"/api/datasets/{TEST_DS}/graphs/namespaces",
            json={"graph": TEST_GRAPH2, "ns_iri": DEL_NS, "prefix": "del"},
        )
        # delete
        resp = await client.delete(
            f"/api/datasets/{TEST_DS}/graphs/namespaces",
            params={"graph": TEST_GRAPH2, "ns_iri": DEL_NS},
        )
        assert resp.status_code == 204, resp.text

        # DEL_NS subject 트리플이 모두 삭제되어야 함
        rows = sparql_query(TEST_DS, f"""
        SELECT ?s WHERE {{
          GRAPH <{TEST_GRAPH2}> {{
            ?s ?p ?o .
            FILTER(STRSTARTS(str(?s), "{DEL_NS}"))
          }}
        }} LIMIT 1
        """)
        assert rows == [], f"Namespace subjects still present: {rows}"
    finally:
        sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH2}>")


# ── TC08: 중복 선언 → 409 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_duplicate_declare_409(client):
    """이미 선언된 namespace를 다시 선언 → 409"""
    # TC05에서 rename 되어 NEW_NS가 남아있으므로, NEW_NS를 선언했다 가정하고 다시 선언
    # 먼저 fresh namespace 세팅
    TEST_GRAPH3 = "http://v02c-dup-test.example.org/graph"
    DUP_NS = "http://v02c-dup-test.example.org/ns#"
    try:
        sparql_update(TEST_DS, f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        INSERT DATA {{
          GRAPH <{TEST_GRAPH3}> {{
            <{TEST_GRAPH3}> a owl:Ontology .
          }}
        }}
        """)
        r1 = await client.post(
            f"/api/datasets/{TEST_DS}/graphs/namespaces",
            json={"graph": TEST_GRAPH3, "ns_iri": DUP_NS, "prefix": "dup"},
        )
        assert r1.status_code == 201, r1.text

        r2 = await client.post(
            f"/api/datasets/{TEST_DS}/graphs/namespaces",
            json={"graph": TEST_GRAPH3, "ns_iri": DUP_NS, "prefix": "dup2"},
        )
        assert r2.status_code == 409, r2.text
    finally:
        sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH3}>")


# ── TC09: 존재하지 않는 namespace prefix 수정 → 404 ──────────────────────

@pytest.mark.asyncio
async def test_tc09_patch_nonexistent_404(client):
    """선언되지 않은 namespace의 prefix 수정 → 404"""
    resp = await client.patch(
        f"/api/datasets/{TEST_DS}/graphs/namespaces",
        json={
            "graph": TEST_GRAPH,
            "ns_iri": "http://nonexistent-ns.example.org/ns#",
            "prefix": "nope",
        },
    )
    assert resp.status_code == 404, resp.text


# ── TC10: 잘못된 IRI → 422 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_invalid_iri_422(client):
    """http(s) 아닌 IRI → 422"""
    resp = await client.post(
        f"/api/datasets/{TEST_DS}/graphs/namespaces",
        json={"graph": TEST_GRAPH, "ns_iri": "ftp://bad-iri.example.org/ns#", "prefix": "bad"},
    )
    assert resp.status_code == 422, resp.text
