from pydantic import BaseModel
from typing import List, Tuple

class JobStatus(BaseModel):
    raster_id: str
    status: str
    message: str | None = None
    filename: str | None = None # Added for better tracking in batch jobs

class RasterMetadata(BaseModel):
    raster_id: str
    crs: str
    bounds: List[float]
    resolution: Tuple[float, float]
    band_count: int
    width: int
    height: int

# --- NEW MODEL FOR BATCH RESPONSE ---
class BatchJobResponse(BaseModel):
    successful_jobs: List[JobStatus]
    failed_uploads: List[dict]