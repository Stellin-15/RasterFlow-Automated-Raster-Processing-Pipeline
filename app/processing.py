# app/processing.py (Updated Version)
import os
import subprocess
import rasterio
from osgeo import gdal

from .cache import RASTER_CACHE

TARGET_CRS = "EPSG:4326"  # WGS84

def process_raster(raw_path: str, raster_id: str):
    """
    The main processing pipeline function executed in the background.
    1. Reproject to WGS84 (EPSG:4326).
    2. Translate to a tile-friendly format. <--- NEW STEP
    3. Extract metadata.
    4. Generate map tiles.
    5. Update the cache with status and results.
    """
    try:
        processed_dir = f"data/processed/{raster_id}"
        os.makedirs(processed_dir, exist_ok=True)

        print(f"[{raster_id}] Starting processing...")

        # --- 1. Reproject Raster ---
        reprojected_path = f"{processed_dir}/reprojected.tif"
        gdal.Warp(reprojected_path, raw_path, dstSRS=TARGET_CRS)
        print(f"[{raster_id}] Reprojection complete.")

        # --- 2. THE FIX: Translate to a tile-friendly format (8-bit with scaling) ---
        # This converts any kind of raster (e.g., single-band float DEM)
        # into a simple 8-bit grayscale image that gdal2tiles can handle.
        tile_source_path = f"{processed_dir}/tile_source.tif"
        gdal.Translate(
            tile_source_path,
            reprojected_path,
            options="-ot Byte -scale"  # -ot Byte sets output to 8-bit, -scale automatically adjusts pixel values
        )
        print(f"[{raster_id}] Translation to byte format complete.")


        # --- 3. Extract Metadata from the reprojected file ---
        with rasterio.open(reprojected_path) as src:
            metadata = {
                "raster_id": raster_id,
                "crs": src.crs.to_string(),
                "bounds": list(src.bounds),
                "resolution": src.res,
                "band_count": src.count,
                "width": src.width,
                "height": src.height,
            }
        print(f"[{raster_id}] Metadata extraction complete.")

        # --- 4. Generate Tiles using gdal2tiles.py on the tile-friendly source ---
        tiles_path = f"{processed_dir}/tiles"
        command = [
            "gdal2tiles.py",
            "-z", "8-16",
            "--processes=4",
            tile_source_path,  # <--- Use the NEW translated file as input
            tiles_path,
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"[{raster_id}] Tiling complete.")

        # --- 5. Update Cache with final results ---
        RASTER_CACHE[raster_id].update({
            "status": "complete",
            "metadata": metadata,
            "files": {
                "reprojected": reprojected_path,
                "tiles_dir": tiles_path,
            },
        })
        print(f"[{raster_id}] Processing finished successfully.")

    except subprocess.CalledProcessError as e:
        # This is a special catch for the gdal2tiles command to see its output
        error_message = f"gdal2tiles.py failed with exit code {e.returncode}. Stderr: {e.stderr.strip()}"
        print(f"[{raster_id}] Processing failed: {error_message}")
        RASTER_CACHE[raster_id].update({
            "status": "failed",
            "message": error_message
        })
    except Exception as e:
        print(f"[{raster_id}] Processing failed: {e}")
        RASTER_CACHE[raster_id].update({
            "status": "failed",
            "message": str(e)
        })