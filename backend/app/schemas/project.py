from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from app.schemas.node import NodeResponse
from app.schemas.edge import EdgeResponse
from app.schemas.mst import MSTLatestResponse


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str]
    nodes: List[NodeResponse] = []
    edges: List[EdgeResponse] = []
    last_result: Optional[MSTLatestResponse] = None