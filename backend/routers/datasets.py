"""Dataset 목록 조회 + 생성 + 삭제 + Fuseki 연결 확인 (v02-A)."""

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from fuseki.client import create_dataset, delete_dataset, list_datasets, ping

router = APIRouter(prefix="/api", tags=["datasets"])

# 삭제 보호 dataset 목록
_PROTECTED = {"ontology"}

# dataset 이름 허용 패턴: 영문·숫자·하이픈·밑줄만 허용
_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


# ---------- Response models ----------

class Dataset(BaseModel):
    name: str
    state: str


class DatasetsResponse(BaseModel):
    datasets: list[Dataset]


class HealthResponse(BaseModel):
    status: str


class CreateDatasetBody(BaseModel):
    name: str
    db_type: str = "tdb2"

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("dataset 이름은 비어 있을 수 없습니다.")
        if not _NAME_RE.match(v):
            raise ValueError(
                "dataset 이름은 영문·숫자·하이픈·밑줄만 허용됩니다 (특수문자 불가)."
            )
        return v


class CreateDatasetResponse(BaseModel):
    name: str


# ---------- Endpoints ----------

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Fuseki 서버 연결 상태를 확인한다."""
    if not await ping():
        raise HTTPException(status_code=503, detail="Fuseki 서버에 연결할 수 없습니다.")
    return HealthResponse(status="ok")


@router.get("/datasets", response_model=DatasetsResponse)
async def get_datasets():
    """Fuseki에 등록된 모든 dataset 목록을 반환한다."""
    datasets = await list_datasets()
    return DatasetsResponse(datasets=[Dataset(**ds) for ds in datasets])


@router.post("/datasets", response_model=CreateDatasetResponse, status_code=201)
async def post_dataset(body: CreateDatasetBody):
    """Fuseki에 새 TDB2 dataset을 생성한다."""
    # 중복 확인
    existing = await list_datasets()
    names = [d["name"] for d in existing]
    if body.name in names:
        raise HTTPException(409, f"Dataset '{body.name}'이(가) 이미 존재합니다.")
    try:
        await create_dataset(body.name, body.db_type)
    except Exception as e:
        raise HTTPException(500, f"Dataset 생성 실패: {e}")
    return CreateDatasetResponse(name=body.name)


@router.delete("/datasets/{name}", status_code=204)
async def delete_dataset_endpoint(name: str):
    """Fuseki에서 dataset을 삭제한다. 보호된 dataset은 삭제 불가."""
    if name in _PROTECTED:
        raise HTTPException(400, f"Dataset '{name}'은(는) 삭제가 보호되어 있습니다.")
    # 존재 확인
    existing = await list_datasets()
    names = [d["name"] for d in existing]
    if name not in names:
        raise HTTPException(404, f"Dataset '{name}'을(를) 찾을 수 없습니다.")
    try:
        await delete_dataset(name)
    except Exception as e:
        raise HTTPException(500, f"Dataset 삭제 실패: {e}")
