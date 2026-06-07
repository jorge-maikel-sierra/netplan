from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class EdgeBase(BaseModel):
    node_a_id: UUID
    node_b_id: UUID
    cost: float = Field(ge=0)
    constraint_type: str = Field(default="normal", pattern="^(normal|mandatory|forbidden)$")


class EdgeCreate(EdgeBase):
    pass


class EdgeUpdate(BaseModel):
    cost: Optional[float] = Field(default=None, ge=0)
    constraint_type: Optional[str] = Field(default=None, pattern="^(normal|mandatory|forbidden)$")


class EdgeConstraintUpdate(BaseModel):
    constraint_type: str = Field(pattern="^(normal|mandatory|forbidden)$")


class EdgeResponse(EdgeBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    created_at: datetime


class EdgeImportResult(BaseModel):
    imported: int
    skipped: int
    errors: List[dict]