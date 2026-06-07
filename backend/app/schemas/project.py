from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from app.schemas.node import NodeResponse
from app.schemas.edge import EdgeResponse
from app.schemas.mst import MSTLatestResponse


def _validate_name_length(v: str) -> str:
    """Validate name is at least 3 characters."""
    if len(v.strip()) < 3:
        raise ValueError("El nombre debe tener al menos 3 caracteres")
    return v.strip()


class ProjectCreate(BaseModel):
    name: str = Field(..., description="Project name (min 3 characters)")
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_name_length(v)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Project name (min 3 characters)")
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_name_length(v)
        return v


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