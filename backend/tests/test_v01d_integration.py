"""
v01-D 통합 테스트 — Data Property CRUD (실제 Fuseki 연동)

실행: cd backend && pytest tests/test_v01d_integration.py -v
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
GRAPH = "http://test.example.org/graph/dprop-test"
NS    = "http://test.example.org/dprop-test#"
NS2   = "http://other.example.org/dprop#"

CLS_PERSON = f"{NS}PersonClass"

_DROP = f"DROP SILENT GRAPH <{GRAPH}>"

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
    sparql_update(DS, f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        INSERT DATA {{
          GRAPH <{GRAPH}> {{ <{CLS_PERSON}> a owl:Class . }}
        }}
    """)
    yield
    sparql_update(DS, _DROP)


# ── TC01 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc01_empty_list(client):
    """빈 OOI에서 Data Property 목록은 비어있다."""
    resp = await client.get(
        "/api/tbox/data-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    assert resp.status_code == 200
    assert resp.json()["data_properties"] == []


# ── TC02 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc02_create_returns_iri(client):
    """생성 시 201 + namespace 접두사 + 64hex suffix IRI."""
    resp = await client.post(
        "/api/tbox/data-properties",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "label": "hasAge", "domain": CLS_PERSON,
            "range": "integer", "functional": False,
        },
    )
    assert resp.status_code == 201, resp.text
    iri = resp.json()["iri"]
    assert iri.startswith(NS)
    assert re.match(r"^" + re.escape(NS) + r"[A-Z][A-Za-z]*_[0-9a-f]{64}$", iri)


# ── TC03 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc03_created_prop_in_list(client):
    """생성 후 목록에 label, domain, range(xsd:integer) 포함."""
    resp = await client.get(
        "/api/tbox/data-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    props = resp.json()["data_properties"]
    assert len(props) == 1
    p = props[0]
    assert p["label"]  == "hasAge"
    assert p["domain"] == CLS_PERSON
    assert "integer" in p["range"], f"range must contain 'integer': {p['range']}"


# ── TC04 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc04_detail_functional_false(client):
    """상세 조회 — functional=False 확인."""
    props = (await client.get(
        "/api/tbox/data-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["data_properties"]
    iri = props[0]["iri"]

    resp = await client.get(
        f"/api/tbox/data-properties/{_encode(iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["label"]      == "hasAge"
    assert d["functional"] is False, f"Expected functional=False: {d['functional']}"


# ── TC05 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc05_create_functional_true(client):
    """functional=True로 생성 → 상세 조회에서 functional=True."""
    resp = await client.post(
        "/api/tbox/data-properties",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "label": "hasEmail", "domain": CLS_PERSON,
            "range": "string", "functional": True,
        },
    )
    assert resp.status_code == 201
    iri = resp.json()["iri"]

    detail = (await client.get(
        f"/api/tbox/data-properties/{_encode(iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )).json()
    assert detail["functional"] is True, f"Expected functional=True: {detail['functional']}"


# ── TC06 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc06_patch_label_range_functional(client):
    """PATCH — label, range, functional 수정."""
    props = (await client.get(
        "/api/tbox/data-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["data_properties"]
    hasAge = next(p for p in props if p["label"] == "hasAge")
    iri = hasAge["iri"]
    encoded = _encode(iri)

    patch = await client.patch(
        f"/api/tbox/data-properties/{encoded}",
        json={"dataset": DS, "graph": GRAPH,
              "label": "yearOfBirth", "range": "integer", "functional": True},
    )
    assert patch.status_code == 204, patch.text

    detail = (await client.get(
        f"/api/tbox/data-properties/{encoded}",
        params={"dataset": DS, "graph": GRAPH},
    )).json()
    assert detail["label"]      == "yearOfBirth"
    assert "integer" in detail["range"]
    assert detail["functional"] is True


# ── TC07 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc07_namespace_filter(client):
    """다른 namespace Data Property는 목록에 미포함."""
    sparql_update(DS, f"""
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
          GRAPH <{GRAPH}> {{
            <{NS2}foreignProp> a owl:DatatypeProperty ;
              rdfs:label "foreign" .
          }}
        }}
    """)
    resp = await client.get(
        "/api/tbox/data-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    iris = [p["iri"] for p in resp.json()["data_properties"]]
    assert f"{NS2}foreignProp" not in iris, "Foreign namespace prop must not appear"


# ── TC08 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc08_delete_cascades_values(client):
    """DELETE → Individual의 해당 Data Property 값 트리플 소멸."""
    create_resp = await client.post(
        "/api/tbox/data-properties",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "label": "hasScore", "domain": CLS_PERSON,
            "range": "float", "functional": False,
        },
    )
    prop_iri = create_resp.json()["iri"]
    ind = f"{NS}TestUser"

    sparql_update(DS, f"""
        INSERT DATA {{
          GRAPH <{GRAPH}> {{
            <{ind}> <{prop_iri}> "9.5"^^<http://www.w3.org/2001/XMLSchema#float> .
          }}
        }}
    """)
    assert _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{ind}> <{prop_iri}> ?v }} }}")

    del_resp = await client.delete(
        f"/api/tbox/data-properties/{_encode(prop_iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert del_resp.status_code == 204

    assert not _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{ind}> <{prop_iri}> ?v }} }}"), \
        "Data value triple must be deleted"
    assert not _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{prop_iri}> ?p ?o }} }}"), \
        "Property declaration must be deleted"


# ── TC09 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc09_deleted_prop_not_in_list(client):
    """삭제된 'hasScore' Property는 목록에 없다."""
    labels = [p["label"] for p in (await client.get(
        "/api/tbox/data-properties",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["data_properties"]]
    assert "hasScore" not in labels, f"Deleted prop in list: {labels}"


# ── TC10 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc10_nonexistent_returns_404(client):
    """없는 IRI 상세 조회 → 404."""
    ghost = f"{NS}GhostDataProp_nope"
    resp = await client.get(
        f"/api/tbox/data-properties/{_encode(ghost)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
