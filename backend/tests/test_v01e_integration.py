"""
v01-E 통합 테스트 — Individual CRUD (실제 Fuseki 연동)

실행: cd backend && pytest tests/test_v01e_integration.py -v
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
GRAPH = "http://test.example.org/graph/individual-test"
NS    = "http://test.example.org/ind-test#"

CLS_PERSON = f"{NS}Person"
CLS_ORG    = f"{NS}Organization"
PROP_KNOWS = f"{NS}knows"
PROP_AGE   = f"{NS}hasAge"

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
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
          GRAPH <{GRAPH}> {{
            <{CLS_PERSON}> a owl:Class ; rdfs:label "Person" .
            <{CLS_ORG}>    a owl:Class ; rdfs:label "Organization" .
            <{PROP_KNOWS}> a owl:ObjectProperty ; rdfs:domain <{CLS_PERSON}> ; rdfs:range <{CLS_PERSON}> .
            <{PROP_AGE}>   a owl:DatatypeProperty ; rdfs:domain <{CLS_PERSON}> ;
                           rdfs:range <http://www.w3.org/2001/XMLSchema#integer> .
          }}
        }}
    """)
    yield
    sparql_update(DS, _DROP)


# ── TC01 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc01_empty_list(client):
    """빈 OOI에서 Individual 목록은 비어있다."""
    resp = await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    assert resp.status_code == 200
    assert resp.json()["individuals"] == []


# ── TC02 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc02_create_returns_iri(client):
    """생성 시 201 + namespace 접두사 + 64hex suffix IRI."""
    resp = await client.post(
        "/api/abox/individuals",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "class_iri": CLS_PERSON, "label": "Alice",
            "comment": "테스트 사용자",
        },
    )
    assert resp.status_code == 201, resp.text
    iri = resp.json()["iri"]
    assert iri.startswith(NS)
    assert re.match(r"^" + re.escape(NS) + r"[A-Z][A-Za-z]*_[0-9a-f]{64}$", iri), \
        f"IRI format invalid: {iri}"


# ── TC03 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc03_list_and_class_filter(client):
    """목록 반영 + class_iri 필터링."""
    # Bob (Person) 추가
    await client.post(
        "/api/abox/individuals",
        json={"dataset": DS, "graph": GRAPH, "namespace": NS,
              "class_iri": CLS_PERSON, "label": "Bob"},
    )
    # Acme (Organization) 추가
    await client.post(
        "/api/abox/individuals",
        json={"dataset": DS, "graph": GRAPH, "namespace": NS,
              "class_iri": CLS_ORG, "label": "Acme"},
    )

    # 전체 목록
    all_resp = await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    all_labels = {i["label"] for i in all_resp.json()["individuals"]}
    assert {"Alice", "Bob", "Acme"} <= all_labels

    # Person 필터
    person_resp = await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS, "class_iri": CLS_PERSON},
    )
    person_labels = {i["label"] for i in person_resp.json()["individuals"]}
    assert "Acme" not in person_labels, f"Org must not appear in Person filter: {person_labels}"
    assert "Alice" in person_labels


# ── TC04 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc04_detail_basic_fields(client):
    """상세 조회 — class_iri, label, comment, outgoing/incoming 빈 리스트."""
    inds = (await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS, "class_iri": CLS_PERSON},
    )).json()["individuals"]
    alice = next(i for i in inds if i["label"] == "Alice")
    iri = alice["iri"]

    resp = await client.get(
        f"/api/abox/individuals/{_encode(iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["label"]     == "Alice"
    assert d["comment"]   == "테스트 사용자"
    assert d["class_iri"] == CLS_PERSON
    # rdfs:label은 outgoing에서 제외되지 않지만 rdf:type은 제외됨
    types = [o["property"] for o in d["outgoing"]]
    assert "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" not in types, \
        "rdf:type must not appear in outgoing"
    assert d["incoming"] == []


# ── TC05 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc05_create_with_properties(client):
    """Object Property + Data Property 포함 생성 → 상세 outgoing 확인."""
    inds = (await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS, "class_iri": CLS_PERSON},
    )).json()["individuals"]
    bob = next(i for i in inds if i["label"] == "Bob")
    alice = next(i for i in inds if i["label"] == "Alice")

    # Charlie: knows=Alice, age=30
    resp = await client.post(
        "/api/abox/individuals",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "class_iri": CLS_PERSON, "label": "Charlie",
            "data_properties":   [{"property_iri": PROP_AGE,   "value": "30",        "datatype": "integer"}],
            "object_properties": [{"property_iri": PROP_KNOWS, "target_iri": alice["iri"]}],
        },
    )
    assert resp.status_code == 201
    charlie_iri = resp.json()["iri"]

    detail = (await client.get(
        f"/api/abox/individuals/{_encode(charlie_iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )).json()
    outgoing_props = {o["property"] for o in detail["outgoing"]}
    assert PROP_AGE   in outgoing_props, f"hasAge not in outgoing: {outgoing_props}"
    assert PROP_KNOWS in outgoing_props, f"knows not in outgoing: {outgoing_props}"


# ── TC06 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc06_incoming_reflected(client):
    """Charlie가 Alice를 knows로 가리킬 때 Alice의 incoming에 반영."""
    inds = (await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["individuals"]
    alice = next(i for i in inds if i["label"] == "Alice")

    detail = (await client.get(
        f"/api/abox/individuals/{_encode(alice['iri'])}",
        params={"dataset": DS, "graph": GRAPH},
    )).json()
    incoming_props = {r["property"] for r in detail["incoming"]}
    assert PROP_KNOWS in incoming_props, f"knows not in incoming: {incoming_props}"


# ── TC07 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc07_patch_label_and_data_property(client):
    """PATCH — label 수정 + data property 값 수정."""
    inds = (await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["individuals"]
    charlie = next(i for i in inds if i["label"] == "Charlie")
    iri = charlie["iri"]
    encoded = _encode(iri)

    patch = await client.patch(
        f"/api/abox/individuals/{encoded}",
        json={
            "dataset": DS, "graph": GRAPH,
            "label": "Charles",
            "data_property_updates": [
                {"property_iri": PROP_AGE, "value": "31", "datatype": "integer"}
            ],
        },
    )
    assert patch.status_code == 204, patch.text

    detail = (await client.get(
        f"/api/abox/individuals/{encoded}",
        params={"dataset": DS, "graph": GRAPH},
    )).json()
    assert detail["label"] == "Charles"
    age_val = next(
        o["value"] for o in detail["outgoing"] if o["property"] == PROP_AGE
    )
    assert age_val == "31", f"age must be 31: {age_val}"


# ── TC08 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc08_delete_removes_outgoing(client):
    """DELETE → 해당 Individual의 outgoing 트리플 모두 소멸."""
    inds = (await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["individuals"]
    charles = next(i for i in inds if i["label"] == "Charles")
    iri = charles["iri"]

    del_resp = await client.delete(
        f"/api/abox/individuals/{_encode(iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert del_resp.status_code == 204

    assert not _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{iri}> ?p ?o }} }}"), \
        "Outgoing triples must be deleted"


# ── TC09 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc09_delete_removes_incoming(client):
    """DELETE → 다른 Individual이 가리키던 incoming 트리플도 소멸."""
    inds = (await client.get(
        "/api/abox/individuals",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )).json()["individuals"]
    alice = next(i for i in inds if i["label"] == "Alice")
    alice_iri = alice["iri"]

    # Dave → knows → Alice 관계 삽입
    dave_resp = await client.post(
        "/api/abox/individuals",
        json={
            "dataset": DS, "graph": GRAPH, "namespace": NS,
            "class_iri": CLS_PERSON, "label": "Dave",
            "object_properties": [{"property_iri": PROP_KNOWS, "target_iri": alice_iri}],
        },
    )
    dave_iri = dave_resp.json()["iri"]
    assert _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{dave_iri}> <{PROP_KNOWS}> <{alice_iri}> }} }}")

    # Alice 삭제
    await client.delete(
        f"/api/abox/individuals/{_encode(alice_iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )

    # Dave → Alice 인커밍 트리플 소멸 확인
    assert not _ask(
        f"ASK {{ GRAPH <{GRAPH}> {{ ?s ?p <{alice_iri}> }} }}"
    ), "Incoming triples to Alice must be deleted"

    # Dave 자체는 유지
    assert _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{dave_iri}> ?p ?o }} }}"), \
        "Dave must still exist"


# ── TC10 ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc10_nonexistent_returns_404(client):
    """없는 IRI 상세 조회 → 404."""
    ghost = f"{NS}GhostPerson_nope"
    resp = await client.get(
        f"/api/abox/individuals/{_encode(ghost)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
