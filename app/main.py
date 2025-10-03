# app/main.py (Updated Version)
import uuid
import os
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from osgeo import gdal

from .cache import RASTER_CACHE
from .models import RasterMetadata, JobStatus
from .processing import process_raster

app = FastAPI(title="RasterFlow MVP")

@app.post("/v1/rasters", response_model=JobStatus, status_code=202)
async def upload_raster(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Accepts a raster file, saves it, validates it, and starts the processing pipeline.
    """
    raster_id = str(uuid.uuid4())
    raw_dir = "data/raw"
    os.makedirs(raw_dir, exist_ok=True)
    
    raw_path = os.path.join(raw_dir, f"{raster_id}_{file.filename}")

    # Save the uploaded file
    with open(raw_path, "wb") as buffer:
        buffer.write(await file.read())

    # --- NEW VALIDATION STEP ---
    # Try to open the file with GDAL. If it fails, it's not a valid raster.
    try:
        ds = gdal.Open(raw_path)
        if ds is None:
            raise ValueError("GDAL could not open the file. It may be corrupted or not a valid raster format.")
        ds = None # Close the dataset
    except Exception as e:
        os.remove(raw_path) # Clean up the invalid saved file
        raise HTTPException(
            status_code=400, # Bad Request
            detail=f"Invalid raster file provided. Error: {e}"
        )
    # --- END VALIDATION STEP ---

    # Initialize job status in cache
    RASTER_CACHE[raster_id] = {"status": "processing"}
    
    # Add the processing task to the background
    background_tasks.add_task(process_raster, raw_path, raster_id)
    
    return JobStatus(raster_id=raster_id, status="processing", message="Upload accepted and validated.")


# ... (the rest of the file remains the same) ...

@app.get("/v1/rasters/{raster_id}/status", response_model=JobStatus)
def get_raster_status(raster_id: str):
    job = RASTER_CACHE.get(raster_id)
    if not job:
        raise HTTPException(status_code=404, detail="Raster ID not found.")
    return JobStatus(raster_id=raster_id, **job)

@app.get("/v1/rasters/{raster_id}/metadata", response_model=RasterMetadata)
def get_raster_metadata(raster_id: str):
    job = RASTER_CACHE.get(raster_id)
    if not job or job.get("status") != "complete":
        raise HTTPException(status_code=404, detail="Raster not found or not yet processed.")
    return RasterMetadata(**job["metadata"])

@app.get("/v1/rasters/{raster_id}/download")
def download_reprojected_raster(raster_id: str):
    job = RASTER_CACHE.get(raster_id)
    if not job or job.get("status") != "complete":
        raise HTTPException(status_code=404, detail="Raster not found or not yet processed.")
    
    file_path = job["files"]["reprojected"]
    return FileResponse(path=file_path, media_type='image/tiff', filename='reprojected.tif')

@app.get("/v1/rasters/{raster_id}/tiles/{z}/{x}/{y}.png")
def get_map_tile(raster_id: str, z: int, x: int, y: int):
    job = RASTER_CACHE.get(raster_id)
    if not job or job.get("status") != "complete":
        raise HTTPException(status_code=404, detail="Tiles not found for this raster ID.")

    tile_path = os.path.join(job["files"]["tiles_dir"], str(z), str(x), f"{y}.png")
    
    if not os.path.exists(tile_path):
        raise HTTPException(status_code=404, detail="Tile not found.")
        
    return FileResponse(tile_path, media_type='image/png')