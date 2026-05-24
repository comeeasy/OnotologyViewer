"""TBox — Data Property CRUD 라우터."""

from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.data_property import (
    create_data_property,
    delete_data_property,
    get_data_property_detail,
    list_data_properties,
    update_data_property,
)

router = APIRouter(prefix="/api/tbox/data-properties", tags=["data-properties"])


class DataPropertySummary(BaseModel):
    iri:    str
    label:  str | None
    domain: str | None
    range:  str | None


class DataPropertiesResponse(BaseModel):
    dataset:         str
    graph:           str
    namespace:       str
    data_properties: list[DataPropertySummary]


class DataPropertyDetail(BaseModel):
    iri:        str
    label:      str | None
    domain:     str | None
    range:      str | None
    functional: bool


class CreateDataPropertyBody(BaseModel):
    dataset:    str
    graph:      str
    namespace:  str
    label:      str
    domain:     str
    range:      str          # xsd shortname: string|integer|float|boolean|dateTime|anyURI
    functional: bool = False


class CreateDataPropertyResponse(BaseModel):
    iri: str


class UpdateDataPropertyBody(BaseModel):
    dataset:    str
    graph:      str
    label:      str | None = None
    domain:     str | None = None
    range:      str | None = None    # xsd shortname
    functional: bool | None = None


@router.get("", response_model=DataPropertiesResponse)
def get_data_properties(
    dataset:   str       = Query(...),
    graph:     str       = Query(...),
    namespace: list[str] = Query(...),
):
    ns_list = [ns for ns in namespace if ns.strip()]
    if not ns_list:
        raise HTTPException(422, "namespace는 하나 이상 유효한 값을 제공해야 합니다.")
    try:
        props = list_data_properties(dataset, graph, ns_list)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return DataPropertiesResponse(
        dataset=dataset, graph=graph, namespace=ns_list[0],
        data_properties=[DataPropertySummary(**p) for p in props],
    )


@router.post("", response_model=CreateDataPropertyResponse, status_code=201)
def post_data_property(body: CreateDataPropertyBody):
    try:
        iri = create_data_property(
            dataset=body.dataset, graph=body.graph, namespace=body.namespace,
            label=body.label, domain=body.domain,
            range_xsd=body.range, functional=body.functional,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return CreateDataPropertyResponse(iri=iri)


@router.get("/{iri:path}", response_model=DataPropertyDetail)
def get_data_property(
    iri: str,
    dataset: str = Query(...),
    graph:   str = Query(...),
):
    prop_iri = unquote(iri)
    try:
        detail = get_data_property_detail(dataset, graph, prop_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if detail is None:
        raise HTTPException(404, f"Data Property not found: {prop_iri}")
    return DataPropertyDetail(**detail)


@router.patch("/{iri:path}", status_code=204)
def patch_data_property(iri: str, body: UpdateDataPropertyBody):
    prop_iri = unquote(iri)
    try:
        update_data_property(
            dataset=body.dataset, graph=body.graph, prop_iri=prop_iri,
            label=body.label, domain=body.domain,
            range_xsd=body.range, functional=body.functional,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/{iri:path}", status_code=204)
def delete_data_property_endpoint(
    iri: str,
    dataset: str = Query(...),
    graph:   str = Query(...),
):
    prop_iri = unquote(iri)
    try:
        delete_data_property(dataset, graph, prop_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))
