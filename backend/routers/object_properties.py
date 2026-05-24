"""TBox — Object Property CRUD 라우터."""

from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.object_property import (
    create_object_property,
    delete_object_property,
    get_object_property_detail,
    list_object_properties,
    update_object_property,
)

router = APIRouter(prefix="/api/tbox/object-properties", tags=["object-properties"])


# ────────────────────────────────────────────────
# Models
# ────────────────────────────────────────────────

class ObjectPropertySummary(BaseModel):
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
    dataset:   str = Query(...),
    graph:     str = Query(...),
    namespace: str = Query(...),
):
    try:
        props = list_object_properties(dataset, graph, namespace)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return ObjectPropertiesResponse(
        dataset=dataset, graph=graph, namespace=namespace,
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
