import uuid
import os
from typing import List # <--- IMPORT LIST FOR BATCH PROCESSING
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from osgeo import gdal

from .cache import RASTER_CACHE
# IMPORT THE NEW BATCH RESPONSE MODEL
from .models import RasterMetadata, JobStatus, BatchJobResponse
from .processing import process_raster

app = FastAPI(title="RasterFlow MVP")

# --- CORS MIDDLEWARE ---
# This allows the frontend (running in a browser) to communicate with the backend.
origins = [
    "*",  # Allows all origins, for development purposes.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)
# --- END CORS MIDDLEWARE ---


@app.post("/v1/rasters", response_model=JobStatus, status_code=202)
async def upload_raster(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Accepts a raster file, saves it, validates it, and starts the processing pipeline.
    """
    raster_id = str(uuid.uuid4())
    raw_dir = "data/raw"
    os.makedirs(raw_dir, exist_ok=True)
    
    raw_path = os.path.join(raw_dir, f"{raster_id}_{file.filename}")

    with open(raw_path, "wb") as buffer:
        buffer.write(await file.read())

    try:
        ds = gdal.Open(raw_path)
        if ds is None:
            raise ValueError("GDAL could not open the file. It may be corrupted or not a valid raster format.")
        ds = None
    except Exception as e:
        os.remove(raw_path)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid raster file provided. Error: {e}"
        )

    # Add filename to the cache for better tracking
    RASTER_CACHE[raster_id] = {"status": "processing", "filename": file.filename}
    background_tasks.add_task(process_raster, raw_path, raster_id)
    return JobStatus(
        raster_id=raster_id, 
        status="processing", 
        message="Upload accepted and validated.",
        filename=file.filename
    )

# --- NEW BATCH UPLOAD ENDPOINT ---
@app.post("/v1/rasters/batch", response_model=BatchJobResponse, status_code=202)
async def upload_raster_batch(
    background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)
):
    """
    Accepts a batch of raster files, validates each, and starts processing for valid files.
    """
    successful_jobs = []
    failed_uploads = []
    raw_dir = "data/raw"
    os.makedirs(raw_dir, exist_ok=True)

    for file in files:
        raster_id = str(uuid.uuid4())
        raw_path = os.path.join(raw_dir, f"{raster_id}_{file.filename}")

        # Save the uploaded file
        with open(raw_path, "wb") as buffer:
            buffer.write(await file.read())

        # Validate the saved file
        try:
            ds = gdal.Open(raw_path)
            if ds is None:
                raise ValueError("GDAL could not open the file.")
            ds = None # Close dataset

            # If valid, create the job
            RASTER_CACHE[raster_id] = {"status": "processing", "filename": file.filename}
            background_tasks.add_task(process_raster, raw_path, raster_id)
            successful_jobs.append(
                JobStatus(
                    raster_id=raster_id, 
                    status="processing", 
                    message="Upload accepted and validated.",
                    filename=file.filename
                )
            )

        except Exception as e:
            # If invalid, log the failure and clean up
            os.remove(raw_path)
            failed_uploads.append({"filename": file.filename, "error": str(e)})

    return BatchJobResponse(
        successful_jobs=successful_jobs, failed_uploads=failed_uploads
    )
# --- END NEW ENDPOINT ---


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
def download_reprocessed_raster(raster_id: str):
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