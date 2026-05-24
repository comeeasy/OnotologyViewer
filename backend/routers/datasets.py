"""Dataset 목록 조회 + Fuseki 연결 확인."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fuseki.client import list_datasets, ping

router = APIRouter(prefix="/api", tags=["datasets"])


# ---------- Response models ----------

class Dataset(BaseModel):
    name: str
    state: str


class DatasetsResponse(BaseModel):
    datasets: list[Dataset]


class HealthResponse(BaseModel):
    status: str


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
