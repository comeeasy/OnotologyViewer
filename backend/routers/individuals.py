"""ABox — Individual CRUD 라우터."""

from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from services.individual import (
    create_individual,
    delete_individual,
    get_individual_detail,
    get_incompatible_properties,
    list_individuals,
    migrate_individual_class,
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


class MigrateClassBody(BaseModel):
    dataset:            str
    graph:              str
    new_class_iri:      str
    incompatible_props: str = "keep"   # "keep" | "delete"

    @field_validator("new_class_iri")
    @classmethod
    def must_be_http(cls, v: str) -> str:
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("new_class_iri must start with http:// or https://")
        return v

    @field_validator("incompatible_props")
    @classmethod
    def must_be_valid_option(cls, v: str) -> str:
        if v not in ("keep", "delete"):
            raise ValueError("incompatible_props must be 'keep' or 'delete'")
        return v


class MigrateClassResponse(BaseModel):
    old_class_iri:       str
    new_class_iri:       str
    deleted_properties:  list[str]


class MigratePreviewResponse(BaseModel):
    individual_iri:          str
    current_class_iri:       str
    new_class_iri:           str
    incompatible_properties: list[str]


# ────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────

@router.get("", response_model=IndividualsResponse)
def get_individuals(
    dataset:   str       = Query(...),
    graph:     str       = Query(...),
    namespace: list[str] = Query(...),
    class_iri: str | None = Query(None, description="Class IRI 필터 (optional)"),
):
    ns_list = [ns for ns in namespace if ns.strip()]
    if not ns_list:
        raise HTTPException(422, "namespace는 하나 이상 유효한 값을 제공해야 합니다.")
    try:
        inds = list_individuals(dataset, graph, ns_list, class_iri)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return IndividualsResponse(
        dataset=dataset, graph=graph, namespace=ns_list[0],
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


@router.get("/{iri:path}/class-migrate-preview", response_model=MigratePreviewResponse)
def get_class_migrate_preview(
    iri: str,
    dataset: str = Query(...),
    graph:   str = Query(...),
    new_class_iri: str = Query(...),
):
    """마이그레이션 시 비호환 property 목록 미리 조회."""
    ind_iri = unquote(iri)
    if ind_iri.endswith("/class-migrate-preview"):
        ind_iri = ind_iri[: -len("/class-migrate-preview")]
    try:
        detail = get_individual_detail(dataset, graph, ind_iri)
        if detail is None:
            raise HTTPException(404, f"Individual not found: {ind_iri}")
        old_class = detail["class_iri"]
        incompat = get_incompatible_properties(dataset, graph, ind_iri, old_class, new_class_iri)
        return MigratePreviewResponse(
            individual_iri=ind_iri,
            current_class_iri=old_class,
            new_class_iri=new_class_iri,
            incompatible_properties=incompat,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.patch("/{iri:path}/class", response_model=MigrateClassResponse)
def patch_individual_class(iri: str, body: MigrateClassBody):
    """Individual의 rdf:type(Class)을 변경한다."""
    ind_iri = unquote(iri)
    if ind_iri.endswith("/class"):
        ind_iri = ind_iri[: -len("/class")]
    try:
        result = migrate_individual_class(
            dataset=body.dataset, graph=body.graph,
            ind_iri=ind_iri, new_class_iri=body.new_class_iri,
            incompatible_props=body.incompatible_props,
        )
        return MigrateClassResponse(**result)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


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
