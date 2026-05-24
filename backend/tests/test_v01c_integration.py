"""
v01-C 통합 테스트 — Object Property CRUD (실제 Fuseki 연동)

실행: cd backend && pytest tests/test_v01c_integration.py -v
"""

import re
import sys
from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from fuseki.sparql import update as sparql_update
from main import app

DS    = "ontology"
GRAPH = "http://test.example.org/graph/oprop-test"
NS    = "http://test.example.org/oprop-test#"

_DROP = f"DROP SILENT GRAPH <{GRAPH}>"

# 테스트용 domain / range Class
CLS_PERSON = f"{NS}PersonClass"
CLS_ORG    = f"{NS}OrgClass"

def _encode(iri: str) -> str:
    return quote(iri, safe="")

def _ask(sparql: str) -> bool:
    from SPARQLWrapper import JSON, SPARQLWrapper
    from config import settings
    sw = SPARQLWrapper(f"{settings.fuseki_base_url}/{DS}/sparql")
    sw.setHTTPAuth("BASIC")
    sw.setCredentials(settings.fuseki_admin_user, settings.fuseki_admin_password)
    sw.setQuery(sparql); sw.setReturnFormat(JSON)
    return sw.query().convert().get("boolean", False)


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True, scope="module")
def clean_graph():
    sparql_update(DS, _DROP)
    # 테스트용 Class 삽입
    sparql_update(DS, f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        INSERT DATA {{
          GRAPH <{GRAPH}> {{
            <{CLS_PERSON}> a owl:Class .
            <{CLS_ORG}>    a owl:Class .
          }}
        }}
    """)
    yield
    sparql_update(DS, _DROP)


# ── TC01 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc01_empty_list(client):
    """빈 OOI에서 Object Property 목록은 비어있다."""
    resp = await client.get(
        "/api/tbox/object-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    assert resp.status_code == 200
    assert resp.json()["object_properties"] == []


# ── TC02 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc02_create_returns_iri(client):
    """생성 시 201 + namespace 접두사 + 64hex suffix IRI 반환."""
    resp = await client.post(
        "/api/tbox/object-properties",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "label": "knows", "domain": CLS_PERSON, "range": CLS_PERSON,
            "characteristics": [],
        },
    )
    assert resp.status_code == 201, resp.text
    iri = resp.json()["iri"]
    assert iri.startswith(NS)
    assert re.match(r"^" + re.escape(NS) + r"[A-Z][A-Za-z]*_[0-9a-f]{64}$", iri), \
        f"IRI format invalid: {iri}"


# ── TC03 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc03_created_prop_in_list(client):
    """생성 후 목록에 label, domain, range 포함."""
    resp = await client.get(
        "/api/tbox/object-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    assert resp.status_code == 200
    props = resp.json()["object_properties"]
    assert len(props) == 1
    p = props[0]
    assert p["label"]  == "knows",      f"label: {p['label']}"
    assert p["domain"] == CLS_PERSON,   f"domain: {p['domain']}"
    assert p["range"]  == CLS_PERSON,   f"range: {p['range']}"


# ── TC04 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc04_detail_no_characteristics(client):
    """상세 조회 — characteristics 없는 경우 빈 리스트."""
    props = (await client.get(
        "/api/tbox/object-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["object_properties"]
    iri = props[0]["iri"]

    resp = await client.get(
        f"/api/tbox/object-properties/{_encode(iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["label"]           == "knows"
    assert d["domain"]          == CLS_PERSON
    assert d["range"]           == CLS_PERSON
    assert d["characteristics"] == [], f"Expected no chars: {d['characteristics']}"


# ── TC05 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc05_create_with_characteristics(client):
    """Transitive + Symmetric characteristics 포함 생성."""
    resp = await client.post(
        "/api/tbox/object-properties",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "label": "worksFor", "domain": CLS_PERSON, "range": CLS_ORG,
            "characteristics": ["Transitive", "Functional"],
        },
    )
    assert resp.status_code == 201, resp.text


# ── TC06 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc06_characteristics_in_detail(client):
    """Transitive + Functional characteristics 상세 조회에서 확인."""
    props = (await client.get(
        "/api/tbox/object-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["object_properties"]
    worksFor = next(p for p in props if p["label"] == "worksFor")

    resp = await client.get(
        f"/api/tbox/object-properties/{_encode(worksFor['iri'])}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 200
    chars = set(resp.json()["characteristics"])
    assert "Transitive" in chars, f"Transitive missing: {chars}"
    assert "Functional" in chars, f"Functional missing: {chars}"


# ── TC07 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc07_patch_label_domain_range_chars(client):
    """PATCH로 label, domain, range, characteristics 수정."""
    props = (await client.get(
        "/api/tbox/object-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["object_properties"]
    worksFor = next(p for p in props if p["label"] == "worksFor")
    iri = worksFor["iri"]
    encoded = _encode(iri)

    patch = await client.patch(
        f"/api/tbox/object-properties/{encoded}",
        json={
            "dataset": DS, "graph": GRAPH,
            "label": "affiliatedWith",
            "domain": CLS_PERSON,
            "range":  CLS_ORG,
            "characteristics": ["Symmetric"],
        },
    )
    assert patch.status_code == 204, patch.text

    detail = (await client.get(
        f"/api/tbox/object-properties/{encoded}",
        params={"dataset": DS, "graph": GRAPH},
    )).json()
    assert detail["label"]           == "affiliatedWith"
    assert detail["range"]           == CLS_ORG
    assert set(detail["characteristics"]) == {"Symmetric"}


# ── TC08 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc08_delete_cascades_relations(client):
    """DELETE → Individual 간 해당 Property 관계 트리플 소멸."""
    # "memberOf" Property 생성
    create_resp = await client.post(
        "/api/tbox/object-properties",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "label": "memberOf", "domain": CLS_PERSON, "range": CLS_ORG,
            "characteristics": [],
        },
    )
    prop_iri = create_resp.json()["iri"]

    # Individual 관계 삽입
    ind_a = f"{NS}Alice"
    ind_b = f"{NS}AcmeCorp"
    sparql_update(DS, f"""
        INSERT DATA {{
          GRAPH <{GRAPH}> {{
            <{ind_a}> <{prop_iri}> <{ind_b}> .
          }}
        }}
    """)
    assert _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{ind_a}> <{prop_iri}> <{ind_b}> }} }}")

    # Property 삭제
    del_resp = await client.delete(
        f"/api/tbox/object-properties/{_encode(prop_iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert del_resp.status_code == 204

    # 관계 트리플 소멸 확인
    assert not _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{ind_a}> <{prop_iri}> ?o }} }}"), \
        "Relation triple must be deleted"
    # Property 선언 소멸 확인
    assert not _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{prop_iri}> ?p ?o }} }}"), \
        "Property declaration must be deleted"


# ── TC09 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc09_deleted_prop_not_in_list(client):
    """삭제된 'memberOf' Property는 목록에 없다."""
    resp = await client.get(
        "/api/tbox/object-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    labels = [p["label"] for p in resp.json()["object_properties"]]
    assert "memberOf" not in labels, f"Deleted prop still in list: {labels}"


# ── TC10 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc10_nonexistent_prop_returns_404(client):
    """없는 IRI 상세 조회 → 404."""
    ghost = f"{NS}GhostProp_does_not_exist"
    resp = await client.get(
        f"/api/tbox/object-properties/{_encode(ghost)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
