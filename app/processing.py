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
    2. Extract metadata.
    3. Generate map tiles.
    4. Update the cache with status and results.
    """
    try:
        processed_dir = f"data/processed/{raster_id}"
        os.makedirs(processed_dir, exist_ok=True)

        print(f"[{raster_id}] Starting processing...")

        # --- 1. Reproject Raster ---
        reprojected_path = f"{processed_dir}/reprojected.tif"
        gdal.Warp(reprojected_path, raw_path, dstSRS=TARGET_CRS)
        print(f"[{raster_id}] Reprojection complete.")

        # --- 2. Extract Metadata from the reprojected file ---
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

        # --- 3. Generate Tiles using gdal2tiles.py ---
        tiles_path = f"{processed_dir}/tiles"
        # We use subprocess to call the command-line utility, which is robust.
        # Options: -z '8-16' specifies zoom levels, --processes=4 uses 4 cores.
        # Note: gdal2tiles generates tiles in a TMS scheme by default.
        command = [
            "gdal2tiles.py",
            "-z", "8-16",
            "--processes=4",
            reprojected_path,
            tiles_path,
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"[{raster_id}] Tiling complete.")

        # --- 4. Update Cache with final results ---
        RASTER_CACHE[raster_id].update({
            "status": "complete",
            "metadata": metadata,
            "files": {
                "reprojected": reprojected_path,
                "tiles_dir": tiles_path,
            },
        })
        print(f"[{raster_id}] Processing finished successfully.")

    except Exception as e:
        print(f"[{raster_id}] Processing failed: {e}")
        RASTER_CACHE[raster_id].update({
            "status": "failed",
            "message": str(e)
        })