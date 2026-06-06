from pydantic import BaseModel


class PDFExportRequest(BaseModel):
    map_image_base64: str