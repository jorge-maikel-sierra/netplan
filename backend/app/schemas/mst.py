from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class MSTEdgeResponse(BaseModel):
    edge_id: UUID
    node_a: str
    node_b: str
    cost: float


class MSTCalculateResponse(BaseModel):
    result_id: UUID
    algorithm: str
    total_cost: float
    mst_edges: List[MSTEdgeResponse]
    nodes_connected: int
    calculated_at: datetime


class MSTLatestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    algorithm: str
    total_cost: float
    edge_ids: List[UUID]
    calculated_at: datetime