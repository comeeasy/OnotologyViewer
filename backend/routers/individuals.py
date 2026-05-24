"""ABox — Individual CRUD 라우터."""

from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.individual import (
    create_individual,
    delete_individual,
    get_individual_detail,
    list_individuals,
    update_individual,
)

router = APIRouter(prefix="/api/abox/individuals", tags=["individuals"])


# ────────────────────────────────────────────────
# Models
# ────────────────────────────────────────────────

class IndividualSummary(BaseModel):
    iri:       str
    label:     str | None
    class_iri: str


class IndividualsResponse(BaseModel):
    dataset:     str
    graph:       str
    namespace:   str
    individuals: list[IndividualSummary]


class OutgoingRelation(BaseModel):
    property:   str
    value:      str
    value_type: str   # "iri" | "literal"


class IncomingRelation(BaseModel):
    subject:  str
    property: str


class IndividualDetail(BaseModel):
    iri:       str
    class_iri: str
    label:     str | None
    comment:   str | None
    outgoing:  list[OutgoingRelation]
    incoming:  list[IncomingRelation]


class DataPropertyValue(BaseModel):
    property_iri: str
    value:        str
    datatype:     str   # xsd shortname


class ObjectPropertyRelation(BaseModel):
    property_iri: str
    target_iri:   str


class CreateIndividualBody(BaseModel):
    dataset:           str
    graph:             str
    namespace:         str
    class_iri:         str
    label:             str
    comment:           str | None = None
    iri:               str | None = None    # None → 자동 생성
    data_properties:   list[DataPropertyValue] = []
    object_properties: list[ObjectPropertyRelation] = []


class CreateIndividualResponse(BaseModel):
    iri: str


class ObjectPropertyUpdate(BaseModel):
    property_iri: str
    target_iri:   str
    action:       str = "add"   # "add" | "remove"


class UpdateIndividualBody(BaseModel):
    dataset:                  str
    graph:                    str
    label:                    str | None = None
    comment:                  str | None = None
    data_property_updates:    list[DataPropertyValue] = []
    object_property_updates:  list[ObjectPropertyUpdate] = []


# ────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────

@router.get("", response_model=IndividualsResponse)
def get_individuals(
    dataset:   str = Query(...),
    graph:     str = Query(...),
    namespace: str = Query(...),
    class_iri: str | None = Query(None, description="Class IRI 필터 (optional)"),
):
    try:
        inds = list_individuals(dataset, graph, namespace, class_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return IndividualsResponse(
        dataset=dataset, graph=graph, namespace=namespace,
        individuals=[IndividualSummary(**i) for i in inds],
    )


@router.post("", response_model=CreateIndividualResponse, status_code=201)
def post_individual(body: CreateIndividualBody):
    try:
        iri = create_individual(
            dataset=body.dataset, graph=body.graph,
            namespace=body.namespace, class_iri=body.class_iri,
            label=body.label, comment=body.comment,
            iri=body.iri,
            data_properties=[dp.model_dump() for dp in body.data_properties],
            object_properties=[op.model_dump() for op in body.object_properties],
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return CreateIndividualResponse(iri=iri)


@router.get("/{iri:path}", response_model=IndividualDetail)
def get_individual(
    iri: str,
    dataset: str = Query(...),
    graph:   str = Query(...),
):
    ind_iri = unquote(iri)
    try:
        detail = get_individual_detail(dataset, graph, ind_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if detail is None:
        raise HTTPException(404, f"Individual not found: {ind_iri}")
    return IndividualDetail(**detail)


@router.patch("/{iri:path}", status_code=204)
def patch_individual(iri: str, body: UpdateIndividualBody):
    ind_iri = unquote(iri)
    try:
        update_individual(
            dataset=body.dataset, graph=body.graph, ind_iri=ind_iri,
            label=body.label, comment=body.comment,
            data_property_updates=[u.model_dump() for u in body.data_property_updates],
            object_property_updates=[u.model_dump() for u in body.object_property_updates],
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/{iri:path}", status_code=204)
def delete_individual_endpoint(
    iri: str,
    dataset: str = Query(...),
    graph:   str = Query(...),
):
    ind_iri = unquote(iri)
    try:
        delete_individual(dataset, graph, ind_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))
