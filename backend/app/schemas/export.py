from pydantic import BaseModel


class PDFExportRequest(BaseModel):
    map_image_base64: str


class PDFExportResponse(BaseModel):
    """Response metadata for export endpoints."""
    filename: str
    content_type: str