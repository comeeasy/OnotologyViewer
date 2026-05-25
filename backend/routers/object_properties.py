"""TBox — Object Property CRUD 라우터."""

from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from services.object_property import (
    add_inverse_of,
    create_object_property,
    delete_object_property,
    get_object_property_detail,
    list_object_properties,
    remove_inverse_of,
    update_object_property,
)

router = APIRouter(prefix="/api/tbox/object-properties", tags=["object-properties"])


# ────────────────────────────────────────────────
# Models
# ────────────────────────────────────────────────

class ObjectPropertySummary(BaseModel):
    source_graph: str | None = None
    iri:    str
    label:  str | None
    domain: str | None
    range:  str | None


class ObjectPropertiesResponse(BaseModel):
    dataset:             str
    graph:               str
    namespace:           str
    object_properties:   list[ObjectPropertySummary]


class ObjectPropertyDetail(BaseModel):
    iri:             str
    label:           str | None
    domain:          str | None
    range:           str | None
    characteristics: list[str]
    inverse_of:      list[str] = []


class InverseOfBody(BaseModel):
    dataset:     str
    graph:       str
    inverse_iri: str

    @field_validator("inverse_iri")
    @classmethod
    def inv_must_be_http(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("inverse_iri는 빈 문자열일 수 없습니다.")
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("inverse_iri는 http:// 또는 https://로 시작해야 합니다.")
        return v


class CreateObjectPropertyBody(BaseModel):
    dataset:         str
    graph:           str
    namespace:       str
    label:           str
    domain:          str | None = None   # optional — 나중에 수정 가능
    range:           str | None = None   # optional — 나중에 수정 가능
    characteristics: list[str] = []


class CreateObjectPropertyResponse(BaseModel):
    iri: str


class UpdateObjectPropertyBody(BaseModel):
    dataset:         str
    graph:           str
    label:           str | None = None
    domain:          str | None = None
    range:           str | None = None
    characteristics: list[str] | None = None


# ────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────

@router.get("", response_model=ObjectPropertiesResponse)
def get_object_properties(
    dataset:   str       = Query(...),
    graph:     list[str] = Query(..., description="Named Graph IRI (복수 허용)"),
    namespace: list[str] = Query(...),
):
    graphs  = [g for g in graph if g.strip()]
    ns_list = [ns for ns in namespace if ns.strip()]
    if not graphs:
        raise HTTPException(422, "graph는 하나 이상 유효한 값을 제공해야 합니다.")
    if not ns_list:
        raise HTTPException(422, "namespace는 하나 이상 유효한 값을 제공해야 합니다.")
    try:
        props = list_object_properties(dataset, graphs, ns_list)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return ObjectPropertiesResponse(
        dataset=dataset, graph=graphs[0], namespace=ns_list[0],
        object_properties=[ObjectPropertySummary(**p) for p in props],
    )


@router.post("", response_model=CreateObjectPropertyResponse, status_code=201)
def post_object_property(body: CreateObjectPropertyBody):
    try:
        iri = create_object_property(
            dataset=body.dataset, graph=body.graph, namespace=body.namespace,
            label=body.label, domain=body.domain, range_=body.range,
            characteristics=body.characteristics,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return CreateObjectPropertyResponse(iri=iri)


@router.get("/{iri:path}", response_model=ObjectPropertyDetail)
def get_object_property(
    iri: str,
    dataset: str = Query(...),
    graph:   str = Query(...),
):
    prop_iri = unquote(iri)
    try:
        detail = get_object_property_detail(dataset, graph, prop_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if detail is None:
        raise HTTPException(404, f"Object Property not found: {prop_iri}")
    return ObjectPropertyDetail(**detail)


@router.patch("/{iri:path}", status_code=204)
def patch_object_property(iri: str, body: UpdateObjectPropertyBody):
    prop_iri = unquote(iri)
    try:
        update_object_property(
            dataset=body.dataset, graph=body.graph, prop_iri=prop_iri,
            label=body.label, domain=body.domain, range_=body.range,
            characteristics=body.characteristics,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/{iri:path}/inverse", status_code=201)
def post_inverse_of(iri: str, body: InverseOfBody):
    """Object Property에 owl:inverseOf 관계를 추가한다."""
    prop_iri = unquote(iri)
    # /inverse suffix를 제거한 실제 IRI 복원
    if prop_iri.endswith("/inverse"):
        prop_iri = prop_iri[: -len("/inverse")]
    try:
        add_inverse_of(body.dataset, body.graph, prop_iri, body.inverse_iri)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(404, msg)
        raise HTTPException(422, msg)


@router.delete("/{iri:path}/inverse", status_code=204)
def delete_inverse_of(
    iri:         str,
    dataset:     str = Query(...),
    graph:       str = Query(...),
    inverse_iri: str = Query(...),
):
    """Object Property의 owl:inverseOf 관계를 삭제한다."""
    prop_iri = unquote(iri)
    if prop_iri.endswith("/inverse"):
        prop_iri = prop_iri[: -len("/inverse")]
    try:
        remove_inverse_of(dataset, graph, prop_iri, inverse_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/{iri:path}", status_code=204)
def delete_object_property_endpoint(
    iri:     str,
    dataset: str = Query(...),
    graph:   str = Query(...),
):
    prop_iri = unquote(iri)
    try:
        delete_object_property(dataset, graph, prop_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))
