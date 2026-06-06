from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class NodeBase(BaseModel):
    name: str
    type: str = Field(default="city", pattern="^(city|tower|datacenter)$")
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class NodeCreate(NodeBase):
    pass


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = Field(default=None, pattern="^(city|tower|datacenter)$")
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class NodeResponse(NodeBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    created_at: datetime


class NodeImportRow(BaseModel):
    nombre: str
    latitud: float
    longitud: float
    tipo: Optional[str] = "city"


class NodeImportResult(BaseModel):
    imported: int
    skipped: int
    errors: List[dict]