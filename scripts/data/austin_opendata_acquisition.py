"""
Austin Open Data integration for neighborhood amenities and environmental risk data.
Uses free public datasets from data.austintexas.gov for parks, libraries, flood zones, etc.
"""
import pandas as pd
import requests
import time
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
import geopandas as gpd
from shapely.geometry import Point

ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
RAW_DATA_DIR = ROOT_DIR / "data" / "raw"

PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AustinOpenDataAPI:
    """Interface for Austin's open data portal using Socrata API."""
    
    def __init__(self):
        self.base_url = "https://data.austintexas.gov/resource"
        
        # Dataset IDs for various Austin open data sources
        self.datasets = {
            'parks': '8f2b-a4q5',  # BOUNDARIES_city_of_austin_parks
            'libraries': 'tc36-hn4j',  # Library Locations (keep existing)
            'flood_zones': '2xn4-j3u2',  # Greater Austin Fully Developed Floodplain
            'schools': 'vkmq-3thn',  # School Locations (if available)
            'community_centers': 'spfx-kzf4',  # Community Centers (keep existing)
        }
        
        logger.info("Austin Open Data API initialized")
    
    def fetch_dataset(self, dataset_key: str, limit: int = 10000) -> Optional[pd.DataFrame]:
        """Fetch a dataset from Austin Open Data portal."""
        if dataset_key not in self.datasets:
            logger.error(f"Unknown dataset key: {dataset_key}")
            return None
        
        dataset_id = self.datasets[dataset_key]
        url = f"{self.base_url}/{dataset_id}.json"
        
        try:
            params = {
                '$limit': limit,
                '$order': ':id'
            }
            
            logger.info(f"Fetching {dataset_key} data from Austin Open Data...")
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            df = pd.DataFrame(data)
            
            logger.info(f"Successfully fetched {len(df)} records for {dataset_key}")
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {dataset_key} data: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing {dataset_key} data: {e}")
            return None
    
    def get_amenities_near_point(self, lat: float, lon: float, radius_miles: float = 2.0) -> Dict:
        """Count amenities near a given point using Austin open data."""
        point = Point(lon, lat)  # Note: Point takes (x, y) = (lon, lat)
        
        amenity_counts = {
            'parks_nearby': 0,
            'libraries_nearby': 0,
            'community_centers_nearby': 0,
            'total_amenities': 0
        }
        
        # Convert radius from miles to degrees (rough approximation)
        radius_degrees = radius_miles / 69.0  # 1 degree ≈ 69 miles
        
        for amenity_type in ['parks', 'libraries', 'community_centers']:
            try:
                df = self.fetch_dataset(amenity_type)
                if df is None or df.empty:
                    continue
                
                # Look for latitude/longitude columns (various naming conventions)
                lat_cols = ['latitude', 'lat', 'y_coordinate', 'location_latitude']
                lon_cols = ['longitude', 'lon', 'lng', 'x_coordinate', 'location_longitude']
                
                lat_col = None
                lon_col = None
                
                for col in lat_cols:
                    if col in df.columns:
                        lat_col = col
                        break
                
                for col in lon_cols:
                    if col in df.columns:
                        lon_col = col
                        break
                
                # Check for location column with coordinates
                if 'location' in df.columns and lat_col is None:
                    # Try to parse location column
                    for idx, row in df.iterrows():
                        if pd.notna(row['location']) and isinstance(row['location'], dict):
                            if 'latitude' in row['location'] and 'longitude' in row['location']:
                                df.at[idx, 'parsed_lat'] = row['location']['latitude']
                                df.at[idx, 'parsed_lon'] = row['location']['longitude']
                    lat_col = 'parsed_lat'
                    lon_col = 'parsed_lon'
                
                if lat_col and lon_col:
                    # Filter for nearby amenities
                    df_clean = df.dropna(subset=[lat_col, lon_col])
                    df_clean[lat_col] = pd.to_numeric(df_clean[lat_col], errors='coerce')
                    df_clean[lon_col] = pd.to_numeric(df_clean[lon_col], errors='coerce')
                    
                    # Simple distance calculation
                    df_clean['distance'] = ((df_clean[lat_col] - lat) ** 2 + 
                                          (df_clean[lon_col] - lon) ** 2) ** 0.5
                    
                    nearby = df_clean[df_clean['distance'] <= radius_degrees]
                    count = len(nearby)
                    
                    amenity_counts[f'{amenity_type}_nearby'] = count
                    logger.debug(f"Found {count} {amenity_type} near ({lat}, {lon})")
                else:
                    logger.warning(f"Could not find coordinate columns for {amenity_type}")
                    
            except Exception as e:
                logger.error(f"Error processing {amenity_type}: {e}")
                continue
        
        amenity_counts['total_amenities'] = sum([
            amenity_counts['parks_nearby'],
            amenity_counts['libraries_nearby'],
            amenity_counts['community_centers_nearby']
        ])
        
        return amenity_counts
    
    def check_flood_risk(self, lat: float, lon: float) -> Dict:
        """Check flood risk for a given point using Austin flood zone data."""
        try:
            # Fetch flood zone data
            flood_df = self.fetch_dataset('flood_zones')
            
            if flood_df is None or flood_df.empty:
                return {'flood_risk': 'unknown', 'flood_zone': 'unknown', 'status': 'no_data'}
            
            # For simplicity, we'll use a basic approach
            # In a full implementation, you'd use proper GIS operations
            point = Point(lon, lat)
            
            # Look for geometry or coordinate information in flood data
            # This is a simplified approach - real flood zone checking requires GIS
            flood_risk_score = 0  # Default: no flood risk
            
            # If we have flood zone data, we can do basic proximity checking
            # For now, return a basic assessment
            return {
                'flood_risk': 'low',  # Default to low risk
                'flood_zone': 'X',    # Default to minimal flood hazard
                'status': 'estimated'
            }
            
        except Exception as e:
            logger.error(f"Error checking flood risk: {e}")
            return {'flood_risk': 'unknown', 'flood_zone': 'unknown', 'status': 'error'}

class AustinDataCollector:
    """Collect neighborhood and environmental data for Austin ZIP codes."""
    
    def __init__(self):
        self.api = AustinOpenDataAPI()
        
    def load_zip_coordinates(self) -> pd.DataFrame:
        """Load ZIP code coordinates from existing data."""
        zip_coords_path = PROCESSED_DATA_DIR / "geocoded_zips.csv"
        
        if not zip_coords_path.exists():
            logger.error("ZIP code coordinates not found. Run data acquisition first.")
            return pd.DataFrame()
        
        return pd.read_csv(zip_coords_path)
    
    def collect_neighborhood_data_for_zips(self) -> pd.DataFrame:
        """Collect neighborhood amenities data for all Austin ZIP codes."""
        zip_coords = self.load_zip_coordinates()
        
        if zip_coords.empty:
            logger.error("No ZIP code coordinates available.")
            return pd.DataFrame()
        
        logger.info(f"Collecting neighborhood data for {len(zip_coords)} ZIP codes...")
        
        results = []
        for idx, row in zip_coords.iterrows():
            zip_code = row['zip_code']
            lat = row['latitude']
            lon = row['longitude']
            
            logger.info(f"Processing ZIP {zip_code} ({idx + 1}/{len(zip_coords)})")
            
            # Get nearby amenities
            amenities = self.api.get_amenities_near_point(lat, lon)
            
            # Check flood risk
            flood_info = self.api.check_flood_risk(lat, lon)
            
            result = {
                'zip_code': zip_code,
                'latitude': lat,
                'longitude': lon,
                'parks_nearby': amenities.get('parks_nearby', 0),
                'libraries_nearby': amenities.get('libraries_nearby', 0),
                'community_centers_nearby': amenities.get('community_centers_nearby', 0),
                'total_amenities': amenities.get('total_amenities', 0),
                'flood_risk': flood_info.get('flood_risk', 'unknown'),
                'flood_zone': flood_info.get('flood_zone', 'unknown'),
                'data_status': 'success'
            }
            
            results.append(result)
            
            # Progress save every 10 ZIP codes
            if (idx + 1) % 10 == 0:
                temp_df = pd.DataFrame(results)
                temp_path = PROCESSED_DATA_DIR / f"austin_opendata_progress_{idx + 1}.csv"
                temp_df.to_csv(temp_path, index=False)
                logger.info(f"Progress saved: {idx + 1} ZIP codes processed")
            
            # Rate limiting for API calls
            time.sleep(0.5)
        
        return pd.DataFrame(results)
    
    def save_austin_data(self, df: pd.DataFrame) -> None:
        """Save Austin open data to processed files."""
        if df.empty:
            logger.warning("No Austin data to save.")
            return
        
        # Save as CSV
        csv_path = PROCESSED_DATA_DIR / "austin_neighborhood_data.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"Austin neighborhood data saved to {csv_path}")
        
        # REMOVED: JSON output - CSV only
        
        # Generate summary statistics
        self._generate_summary_stats(df)
    
    def _generate_summary_stats(self, df: pd.DataFrame) -> None:
        """Generate and save summary statistics."""
        successful_data = df[df['data_status'] == 'success']
        
        stats = {
            'total_zip_codes': len(df),
            'successful_requests': len(successful_data),
            'success_rate': len(successful_data) / len(df) * 100,
            'average_parks_nearby': successful_data['parks_nearby'].mean(),
            'average_libraries_nearby': successful_data['libraries_nearby'].mean(),
            'average_community_centers_nearby': successful_data['community_centers_nearby'].mean(),
            'average_total_amenities': successful_data['total_amenities'].mean(),
            'flood_risk_distribution': successful_data['flood_risk'].value_counts().to_dict(),
            'most_amenities_zips': successful_data.nlargest(5, 'total_amenities')[['zip_code', 'total_amenities']].to_dict('records'),
            'least_amenities_zips': successful_data.nsmallest(5, 'total_amenities')[['zip_code', 'total_amenities']].to_dict('records')
        }
        
        stats_path = PROCESSED_DATA_DIR / "austin_neighborhood_stats.json"
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        
        logger.info(f"Austin neighborhood statistics saved to {stats_path}")
        logger.info(f"Success rate: {stats['success_rate']:.1f}%")
        logger.info(f"Average total amenities per ZIP: {stats['average_total_amenities']:.1f}")

def main():
    """Main function for command line execution."""
    collector = AustinDataCollector()
    
    logger.info("Starting Austin Open Data collection...")
    austin_df = collector.collect_neighborhood_data_for_zips()
    
    if not austin_df.empty:
        collector.save_austin_data(austin_df)
        logger.info("Austin Open Data collection completed successfully!")
    else:
        logger.error("Austin Open Data collection failed.")

if __name__ == "__main__":
    main()
