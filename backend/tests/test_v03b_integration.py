"""
v03-B 통합 테스트 — SPARQL 기반 추론 Rule

TC01: 규칙 생성 (label + condition + consequence) → 201, rule IRI 반환
TC02: 규칙 목록 조회 → rules 리스트
TC03: 규칙 상세 조회 → label, condition, consequence 포함
TC04: 규칙 수정 (label, description)
TC05: 규칙 삭제
TC06: 규칙 적용 미리보기 → inferred triples 반환
TC07: 빈 결과 규칙 적용 → empty list
TC08: 규칙 결과 Materialization → 저장 확인
TC09: 잘못된 SPARQL condition → 422
TC10: 존재하지 않는 규칙 → 404

실행:
  cd backend && pytest tests/test_v03b_integration.py -v
"""

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from main import app
from fuseki.sparql import update as sparql_update, query as sparql_query

TEST_DS    = "ontology"
TEST_GRAPH = "http://v03b-rules-test.example.org/graph"
RULES_GRAPH = "http://v03b-rules-test.example.org/graph/rules"
NS         = "http://v03b-rules-test.example.org/ns#"

CREATED_RULE_IRI = None


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _setup():
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{RULES_GRAPH}>")
    sparql_update(TEST_DS, f"""
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
    INSERT DATA {{
      GRAPH <{TEST_GRAPH}> {{
        <{TEST_GRAPH}> a owl:Ontology .

        # Class hierarchy: GoldenRetriever subClassOf Dog subClassOf Animal
        <{NS}Animal>   a owl:Class ; rdfs:label "Animal" .
        <{NS}Dog>      a owl:Class ; rdfs:subClassOf <{NS}Animal> .
        <{NS}GoldenRetriever> a owl:Class ; rdfs:subClassOf <{NS}Dog> .

        # Properties
        <{NS}hasOwner> a owl:ObjectProperty ; rdfs:domain <{NS}Animal> .
        <{NS}isOwnedBy> a owl:ObjectProperty .

        # Individuals
        <{NS}buddy>  a <{NS}GoldenRetriever> ; rdfs:label "Buddy" .
        <{NS}alice>  a <{NS}Animal> ; rdfs:label "Alice" ;
                     <{NS}hasOwner> <{NS}bob_person> .
      }}
    }}
    """)


@pytest.fixture(autouse=True, scope="module")
async def cleanup(client):
    _setup()
    yield
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{RULES_GRAPH}>")
    sparql_update(TEST_DS, f"DROP SILENT GRAPH <{TEST_GRAPH}/materialized>")


# ── TC01: 규칙 생성 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_create_rule(client):
    """규칙 생성 → 201, rule IRI 반환"""
    global CREATED_RULE_IRI
    # Rule: if ?x a GoldenRetriever then ?x a Dog
    resp = await client.post("/api/rules", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "GoldenRetriever is Dog",
        "description": "모든 GoldenRetriever는 Dog이다",
        "condition": f"?x a <{NS}GoldenRetriever> .",
        "consequence": f"?x a <{NS}Dog> .",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "rule_iri" in data
    assert data["rule_iri"].startswith("http")
    CREATED_RULE_IRI = data["rule_iri"]


# ── TC02: 규칙 목록 조회 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_list_rules(client):
    """규칙 목록 조회 → rules 리스트"""
    resp = await client.get("/api/rules", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    iris = [r["rule_iri"] for r in data]
    assert CREATED_RULE_IRI in iris


# ── TC03: 규칙 상세 조회 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_get_rule_detail(client):
    """규칙 상세 조회 → label, condition, consequence 포함"""
    from urllib.parse import quote
    encoded = quote(CREATED_RULE_IRI, safe='')
    resp = await client.get(f"/api/rules/{encoded}", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["rule_iri"] == CREATED_RULE_IRI
    assert "label" in data
    assert "condition" in data
    assert "consequence" in data
    assert data["label"] == "GoldenRetriever is Dog"


# ── TC04: 규칙 수정 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_update_rule(client):
    """규칙 수정 (label 변경)"""
    from urllib.parse import quote
    encoded = quote(CREATED_RULE_IRI, safe='')
    resp = await client.patch(f"/api/rules/{encoded}", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "GoldenRetriever is also Dog (updated)",
    })
    assert resp.status_code == 200, resp.text

    # 변경 확인
    detail_resp = await client.get(
        f"/api/rules/{encoded}",
        params={"dataset": TEST_DS, "graph": TEST_GRAPH},
    )
    assert detail_resp.json()["label"] == "GoldenRetriever is also Dog (updated)"


# ── TC05: 규칙 삭제 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_delete_rule(client):
    """규칙 삭제"""
    # 임시 규칙 생성
    create_resp = await client.post("/api/rules", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "Temp Rule",
        "condition": f"?x a <{NS}Dog> .",
        "consequence": f"?x a <{NS}Animal> .",
    })
    temp_iri = create_resp.json()["rule_iri"]

    from urllib.parse import quote
    encoded = quote(temp_iri, safe='')
    del_resp = await client.delete(f"/api/rules/{encoded}", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    assert del_resp.status_code == 200, del_resp.text

    # 목록에서 사라졌는지 확인
    list_resp = await client.get("/api/rules", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    iris = [r["rule_iri"] for r in list_resp.json()]
    assert temp_iri not in iris


# ── TC06: 규칙 적용 미리보기 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_apply_rule_preview(client):
    """규칙 적용 미리보기 → inferred triples 반환"""
    from urllib.parse import quote
    encoded = quote(CREATED_RULE_IRI, safe='')
    resp = await client.post(f"/api/rules/{encoded}/apply", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "inferred_triples" in data
    assert isinstance(data["inferred_triples"], list)
    # buddy는 GoldenRetriever이므로 buddy a Dog 추론되어야 함
    triples = data["inferred_triples"]
    subj_obj_pairs = [(t["s"], t["o"]) for t in triples]
    assert (f"{NS}buddy", f"{NS}Dog") in subj_obj_pairs, \
        f"Expected ({NS}buddy, {NS}Dog) in {subj_obj_pairs}"


# ── TC07: 빈 결과 규칙 ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_empty_result_rule(client):
    """매칭 없는 규칙 → 빈 결과"""
    # NonExistentClass는 그래프에 없음
    create_resp = await client.post("/api/rules", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "No match rule",
        "condition": f"?x a <{NS}NonExistentClass> .",
        "consequence": f"?x a <{NS}SomethingElse> .",
    })
    assert create_resp.status_code == 201
    empty_rule_iri = create_resp.json()["rule_iri"]

    from urllib.parse import quote
    encoded = quote(empty_rule_iri, safe='')
    resp = await client.post(f"/api/rules/{encoded}/apply", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["inferred_triples"] == []

    # 정리
    await client.delete(f"/api/rules/{encoded}", params={"dataset": TEST_DS, "graph": TEST_GRAPH})


# ── TC08: 규칙 결과 Materialization ──────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_materialize_rule(client):
    """규칙 결과 Materialization → 저장 확인"""
    from urllib.parse import quote
    encoded = quote(CREATED_RULE_IRI, safe='')

    # 미리보기
    preview_resp = await client.post(f"/api/rules/{encoded}/apply", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    inferred = preview_resp.json()["inferred_triples"]
    assert len(inferred) > 0

    # Materialization
    mat_resp = await client.post(f"/api/rules/{encoded}/materialize", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
    })
    assert mat_resp.status_code == 200, mat_resp.text
    mat_data = mat_resp.json()
    assert "materialized_graph" in mat_data
    assert mat_data["materialized_count"] > 0

    # Fuseki에서 실제 확인
    mat_graph = mat_data["materialized_graph"]
    rows = sparql_query(TEST_DS, f"""
    SELECT ?s ?o WHERE {{
      GRAPH <{mat_graph}> {{
        ?s a ?o .
      }}
    }} LIMIT 1
    """)
    assert len(rows) > 0


# ── TC09: 잘못된 SPARQL condition → 422 ──────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_invalid_sparql_422(client):
    """잘못된 SPARQL condition → 422"""
    resp = await client.post("/api/rules", json={
        "dataset": TEST_DS,
        "graph": TEST_GRAPH,
        "label": "Bad SPARQL Rule",
        "condition": "INVALID SPARQL {{ garbage }}}",
        "consequence": f"?x a <{NS}Anything> .",
    })
    # 422 또는 400 반환
    assert resp.status_code in (400, 422), resp.text


# ── TC10: 존재하지 않는 규칙 → 404 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_get_nonexistent_rule_404(client):
    """존재하지 않는 규칙 → 404"""
    from urllib.parse import quote
    fake_iri = f"{NS}NonExistentRule_xyz"
    encoded = quote(fake_iri, safe='')
    resp = await client.get(f"/api/rules/{encoded}", params={"dataset": TEST_DS, "graph": TEST_GRAPH})
    assert resp.status_code == 404, resp.text
