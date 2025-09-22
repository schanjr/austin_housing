import os
import json
import pandas as pd
import geopandas as gpd
import requests
from pathlib import Path
import zipfile
import io

ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
RAW_DATA_DIR = ROOT_DIR / "data" / "raw"

def get_austin_zip_boundaries():
    """
    Get GeoJSON boundaries for Austin ZIP codes.
    
    Returns:
        geopandas.GeoDataFrame: GeoDataFrame with ZIP code boundaries
    """
    # Define the path for cached boundaries
    boundaries_path = PROCESSED_DATA_DIR / "austin_zip_boundaries.gpkg"
    
    # Check if we already have the data
    if boundaries_path.exists():
        print(f"Loading ZIP code boundaries from {boundaries_path}")
        return gpd.read_file(boundaries_path)
    
    print("Fetching Austin ZIP code boundaries...")
    
    # Define the URL for the Census Bureau's ZIP Code Tabulation Areas (ZCTAs)
    # This is a public dataset with ZIP code boundaries
    url = "https://www2.census.gov/geo/tiger/TIGER2022/ZCTA520/tl_2022_us_zcta520.zip"
    
    try:
        # Download the ZIP file
        response = requests.get(url)
        response.raise_for_status()
        
        # Save the raw ZIP file
        zip_path = RAW_DATA_DIR / "zcta520.zip"
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        # Extract the shapefile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(RAW_DATA_DIR / "zcta520")
        
        # Load the shapefile
        shapefile_path = RAW_DATA_DIR / "zcta520" / "tl_2022_us_zcta520.shp"
        all_zips = gpd.read_file(shapefile_path)
        
        # Filter to Austin ZIP codes (starting with 787 or 786)
        austin_zips = all_zips[all_zips['ZCTA5CE20'].str.startswith(('787', '786'))]
        
        # Save to GeoPackage format
        austin_zips.to_file(boundaries_path, driver="GPKG")
        
        print(f"Austin ZIP code boundaries saved to {boundaries_path}")
        return austin_zips
    
    except Exception as e:
        print(f"Error fetching ZIP code boundaries: {e}")
        
        # If we can't fetch the data, create a simple placeholder
        # This will allow the app to continue working without ZIP boundaries
        geocoded_zips_path = PROCESSED_DATA_DIR / "geocoded_zips.csv"
        if geocoded_zips_path.exists():
            geocoded_df = pd.read_csv(geocoded_zips_path)
            
            # Create buffer around points to simulate ZIP code areas
            point_gdf = gpd.GeoDataFrame(
                geocoded_df,
                geometry=gpd.points_from_xy(geocoded_df.longitude, geocoded_df.latitude),
                crs="EPSG:4326"
            )
            
            # Create buffer of ~2km around each point
            buffer_gdf = point_gdf.copy()
            buffer_gdf['geometry'] = point_gdf.geometry.buffer(0.02)
            
            # Add ZCTA5CE20 column for compatibility
            buffer_gdf['ZCTA5CE20'] = buffer_gdf['zip_code']
            
            # Save to GeoPackage format
            buffer_gdf.to_file(boundaries_path, driver="GPKG")
            
            print(f"Created placeholder ZIP code boundaries and saved to {boundaries_path}")
            return buffer_gdf
        
        return None

if __name__ == "__main__":
    # Test the function
    zip_boundaries = get_austin_zip_boundaries()
    if zip_boundaries is not None:
        print(f"Retrieved {len(zip_boundaries)} ZIP code boundaries")
        print(zip_boundaries.head())
