"""
v01-B 통합 테스트 — Class CRUD (실제 Fuseki 연동)

테스트 환경:
  - dataset   : ontology
  - graph     : http://test.example.org/graph/class-test
  - namespace : http://test.example.org/class-test#

실행:
  cd backend && pytest tests/test_v01b_integration.py -v
"""

import re
import sys
from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "/Users/joono/Desktop/OnotologyViewer/backend")

from fuseki.sparql import query as sparql_query, update as sparql_update
from main import app

# ────────────────────────────────────────────────
# 상수
# ────────────────────────────────────────────────

DS    = "ontology"
GRAPH = "http://test.example.org/graph/class-test"
NS    = "http://test.example.org/class-test#"
NS2   = "http://other.example.org/ns#"       # TC05 다른 namespace

_DROP = f"DROP SILENT GRAPH <{GRAPH}>"


def _encode(iri: str) -> str:
    """IRI를 path segment 용도로 URL-인코딩한다."""
    return quote(iri, safe="")


def _ask(sparql: str) -> bool:
    """Fuseki에 ASK 쿼리를 직접 실행한다."""
    from SPARQLWrapper import JSON, SPARQLWrapper
    from config import settings
    sw = SPARQLWrapper(f"{settings.fuseki_base_url}/{DS}/sparql")
    sw.setHTTPAuth("BASIC")
    sw.setCredentials(settings.fuseki_admin_user, settings.fuseki_admin_password)
    sw.setQuery(sparql)
    sw.setReturnFormat(JSON)
    result = sw.query().convert()
    return result.get("boolean", False)


# ────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True, scope="module")
def clean_graph():
    """모듈 전·후 테스트 graph 초기화."""
    sparql_update(DS, _DROP)
    yield
    sparql_update(DS, _DROP)


# ────────────────────────────────────────────────
# TC01 — 빈 OOI에서 Class 목록 조회
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc01_empty_class_list(client):
    """
    트리플이 없는 OOI에서 Class 목록 조회 시 빈 리스트를 반환한다.
    """
    resp = await client.get(
        "/api/tbox/classes",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["classes"] == [], f"Expected empty list, got {body['classes']}"


# ────────────────────────────────────────────────
# TC02 — Class 생성 — 201 + IRI 형식 검증
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc02_create_class_returns_iri(client):
    """
    Class 생성 시 201 + namespace 접두사와 64자리 hex suffix를 가진 IRI를 반환한다.
    """
    resp = await client.post(
        "/api/tbox/classes",
        json={"dataset": DS, "graph": GRAPH, "namespace": NS,
              "label": "Person", "comment": "사람 클래스"},
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

    iri = resp.json()["iri"]
    assert iri.startswith(NS), f"IRI must start with namespace: {iri}"

    pattern = re.compile(r"^" + re.escape(NS) + r"[A-Z][A-Za-z]*_[0-9a-f]{64}$")
    assert pattern.match(iri), f"IRI format invalid: {iri}"


# ────────────────────────────────────────────────
# TC03 — 생성된 Class가 목록에 등장
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc03_created_class_in_list(client):
    """
    Person Class 생성 후 목록 조회 시 label='Person' 항목이 포함되어야 한다.
    """
    resp = await client.get(
        "/api/tbox/classes",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    assert resp.status_code == 200
    labels = [c["label"] for c in resp.json()["classes"]]
    assert "Person" in labels, f"'Person' not found in {labels}"


# ────────────────────────────────────────────────
# TC04 — Class 상세 조회 — 기본 필드
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc04_class_detail_fields(client):
    """
    Class 상세 조회 시 label, comment, individual_count=0,
    super_classes=[], sub_classes=[] 를 반환한다.
    """
    # 목록에서 Person IRI 추출
    list_resp = await client.get(
        "/api/tbox/classes",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    person = next(c for c in list_resp.json()["classes"] if c["label"] == "Person")
    iri = person["iri"]

    resp = await client.get(
        f"/api/tbox/classes/{_encode(iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
    d = resp.json()

    assert d["label"]            == "Person",  f"label mismatch: {d['label']}"
    assert d["comment"]          == "사람 클래스", f"comment mismatch: {d['comment']}"
    assert d["individual_count"] == 0,         f"Expected 0 individuals: {d['individual_count']}"
    assert d["super_classes"]    == [],        f"Expected no super: {d['super_classes']}"
    assert d["sub_classes"]      == [],        f"Expected no sub: {d['sub_classes']}"


# ────────────────────────────────────────────────
# TC05 — 다른 namespace Class는 목록 필터링
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc05_namespace_filter(client):
    """
    NS2 namespace로 직접 삽입한 Class는 NS 기준 목록 조회에 나타나지 않아야 한다.
    """
    # NS2 namespace IRI로 Class 직접 삽입
    foreign_iri = f"{NS2}Organization"
    sparql_update(DS, f"""
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
          GRAPH <{GRAPH}> {{
            <{foreign_iri}> a owl:Class ; rdfs:label "Organization" .
          }}
        }}
    """)

    resp = await client.get(
        "/api/tbox/classes",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    assert resp.status_code == 200
    iris = [c["iri"] for c in resp.json()["classes"]]
    assert foreign_iri not in iris, f"Foreign NS class must not appear: {iris}"


# ────────────────────────────────────────────────
# TC06 — label 수정 (PATCH)
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc06_patch_label(client):
    """
    PATCH로 label을 수정하면 204를 반환하고,
    이후 상세 조회에서 새 label이 반영되어야 한다.
    """
    list_resp = await client.get(
        "/api/tbox/classes",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    person = next(c for c in list_resp.json()["classes"] if c["label"] == "Person")
    iri = person["iri"]
    encoded = _encode(iri)

    patch_resp = await client.patch(
        f"/api/tbox/classes/{encoded}",
        json={"dataset": DS, "graph": GRAPH, "label": "Human"},
    )
    assert patch_resp.status_code == 204, f"Expected 204: {patch_resp.text}"

    detail = await client.get(
        f"/api/tbox/classes/{encoded}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert detail.json()["label"] == "Human", f"label not updated: {detail.json()['label']}"


# ────────────────────────────────────────────────
# TC07 — comment만 수정 (PATCH)
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc07_patch_comment_only(client):
    """
    comment만 PATCH 시 label은 유지되고 comment만 변경된다.
    """
    list_resp = await client.get(
        "/api/tbox/classes",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    person = next(c for c in list_resp.json()["classes"] if c["label"] == "Human")
    iri = person["iri"]
    encoded = _encode(iri)

    patch_resp = await client.patch(
        f"/api/tbox/classes/{encoded}",
        json={"dataset": DS, "graph": GRAPH, "comment": "수정된 코멘트"},
    )
    assert patch_resp.status_code == 204

    detail = await client.get(
        f"/api/tbox/classes/{encoded}",
        params={"dataset": DS, "graph": GRAPH},
    )
    d = detail.json()
    assert d["label"]   == "Human",     f"label must be unchanged: {d['label']}"
    assert d["comment"] == "수정된 코멘트", f"comment not updated: {d['comment']}"


# ────────────────────────────────────────────────
# TC08 — Individual 있는 Class 삭제 → Individual 연쇄 삭제
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc08_delete_class_cascades_individuals(client):
    """
    Individual이 존재하는 Class를 on_individual=delete 로 삭제하면
    해당 Individual의 모든 트리플(outgoing + incoming)도 함께 삭제된다.
    """
    # Animal Class 생성
    create_resp = await client.post(
        "/api/tbox/classes",
        json={"dataset": DS, "graph": GRAPH, "namespace": NS,
              "label": "Animal", "comment": "동물 클래스"},
    )
    assert create_resp.status_code == 201
    animal_iri = create_resp.json()["iri"]

    ind_iri      = f"{NS}Rex_individual"
    other_iri    = f"{NS}OtherNode"

    # Individual 트리플 삽입 (outgoing + incoming)
    sparql_update(DS, f"""
        PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
          GRAPH <{GRAPH}> {{
            <{ind_iri}> rdf:type      <{animal_iri}> ;
                        rdfs:label    "Rex" ;
                        <{NS}owns>    <{other_iri}> .
            <{other_iri}> <{NS}ownedBy> <{ind_iri}> .
          }}
        }}
    """)

    # Individual 존재 확인
    assert _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{ind_iri}> a <{animal_iri}> }} }}")

    # Class 삭제
    del_resp = await client.delete(
        f"/api/tbox/classes/{_encode(animal_iri)}",
        params={"dataset": DS, "graph": GRAPH, "on_individual": "delete"},
    )
    assert del_resp.status_code == 204

    # Individual 아웃고잉 소멸 확인
    assert not _ask(f"ASK {{ GRAPH <{GRAPH}> {{ <{ind_iri}> ?p ?o }} }}"), \
        "Individual outgoing triples must be deleted"

    # Individual 인커밍 소멸 확인
    assert not _ask(f"ASK {{ GRAPH <{GRAPH}> {{ ?s ?p <{ind_iri}> }} }}"), \
        "Individual incoming triples must be deleted"


# ────────────────────────────────────────────────
# TC09 — Class 삭제 후 목록에서 제거
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc09_deleted_class_not_in_list(client):
    """
    삭제된 Animal Class는 이후 목록 조회에 나타나지 않아야 한다.
    """
    resp = await client.get(
        "/api/tbox/classes",
        params={"dataset": DS, "graph": GRAPH, "namespace": NS},
    )
    assert resp.status_code == 200
    labels = [c["label"] for c in resp.json()["classes"]]
    assert "Animal" not in labels, f"Deleted class must not appear: {labels}"


# ────────────────────────────────────────────────
# TC10 — 존재하지 않는 Class 상세 조회 → 404
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tc10_nonexistent_class_returns_404(client):
    """
    Fuseki에 없는 IRI로 Class 상세 조회 시 404를 반환한다.
    """
    ghost_iri = f"{NS}GhostClass_does_not_exist"

    resp = await client.get(
        f"/api/tbox/classes/{_encode(ghost_iri)}",
        params={"dataset": DS, "graph": GRAPH},
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    assert "not found" in resp.json()["detail"].lower(), \
        f"Expected 'not found' in detail: {resp.json()['detail']}"
