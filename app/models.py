from pydantic import BaseModel
from typing import List, Tuple

class RasterMetadata(BaseModel):
    raster_id: str
    crs: str
    bounds: List[float]
    resolution: Tuple[float, float]
    band_count: int
    width: int
    height: int

class JobStatus(BaseModel):
    raster_id: str
    status: str
    message: str | None = None