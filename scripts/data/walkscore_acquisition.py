"""
WalkScore API integration for Austin housing analysis.
Downloads walkability, transit, and bike scores for ZIP codes.
"""
import requests
import pandas as pd
import time
import logging
from pathlib import Path
from typing import Dict, Optional
import json

ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
RAW_DATA_DIR = ROOT_DIR / "data" / "raw"

PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WalkScoreAPI:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.walkscore.com/score"
        
        if not api_key:
            logger.warning("No WalkScore API key provided. Using demo mode with limited functionality.")
    
    def get_walkscore(self, address: str, lat: float, lon: float) -> Optional[Dict]:
        """Get WalkScore, Transit Score, and Bike Score for a location."""
        if not self.api_key:
            # Return demo data for testing without API key
            return self._get_demo_score(lat, lon)
        
        params = {
            'format': 'json',
            'address': address,
            'lat': lat,
            'lon': lon,
            'wsapikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Rate limiting - WalkScore allows 5000 calls per day
            time.sleep(0.1)  # 10 calls per second max
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching WalkScore for {address}: {e}")
            return None
    
    def _get_demo_score(self, lat: float, lon: float) -> Dict:
        """Generate realistic demo scores based on location within Austin."""
        # Downtown Austin coordinates
        downtown_lat, downtown_lon = 30.2672, -97.7431
        
        # Calculate distance from downtown (rough approximation)
        distance = ((lat - downtown_lat) ** 2 + (lon - downtown_lon) ** 2) ** 0.5
        
        # Generate realistic scores based on distance from downtown
        if distance < 0.05:  # Very close to downtown
            walk_score = 85 + int(distance * 100) % 15
            transit_score = 75 + int(distance * 150) % 20
            bike_score = 80 + int(distance * 120) % 15
        elif distance < 0.15:  # Urban areas
            walk_score = 60 + int(distance * 200) % 25
            transit_score = 50 + int(distance * 180) % 30
            bike_score = 65 + int(distance * 160) % 20
        else:  # Suburban areas
            walk_score = 25 + int(distance * 300) % 35
            transit_score = 15 + int(distance * 250) % 25
            bike_score = 35 + int(distance * 200) % 30
        
        return {
            'status': 1,
            'walkscore': min(100, max(0, walk_score)),
            'transit': {
                'score': min(100, max(0, transit_score))
            },
            'bike': {
                'score': min(100, max(0, bike_score))
            },
            'description': self._get_walk_description(walk_score)
        }
    
    def _get_walk_description(self, score: int) -> str:
        """Get walkability description based on score."""
        if score >= 90:
            return "Walker's Paradise"
        elif score >= 70:
            return "Very Walkable"
        elif score >= 50:
            return "Somewhat Walkable"
        elif score >= 25:
            return "Car-Dependent"
        else:
            return "Car-Dependent (Minimal Transit)"

class WalkScoreDataCollector:
    def __init__(self, api_key: str = None):
        self.api = WalkScoreAPI(api_key)
        
    def load_zip_coordinates(self) -> pd.DataFrame:
        """Load ZIP code coordinates from existing data."""
        zip_coords_path = PROCESSED_DATA_DIR / "geocoded_zips.csv"
        
        if not zip_coords_path.exists():
            logger.error("ZIP code coordinates not found. Run data acquisition first.")
            return pd.DataFrame()
        
        return pd.read_csv(zip_coords_path)
    
    def collect_walkscores_for_zips(self) -> pd.DataFrame:
        """Collect WalkScore data for all Austin ZIP codes."""
        zip_coords = self.load_zip_coordinates()
        
        if zip_coords.empty:
            logger.error("No ZIP code coordinates available.")
            return pd.DataFrame()
        
        logger.info(f"Collecting WalkScore data for {len(zip_coords)} ZIP codes...")
        
        results = []
        for idx, row in zip_coords.iterrows():
            zip_code = row['zip_code']
            lat = row['latitude']
            lon = row['longitude']
            
            # Create address for API call
            address = f"ZIP {zip_code}, Austin, TX"
            
            logger.info(f"Processing ZIP {zip_code} ({idx + 1}/{len(zip_coords)})")
            
            score_data = self.api.get_walkscore(address, lat, lon)
            
            if score_data and score_data.get('status') == 1:
                result = {
                    'zip_code': zip_code,
                    'latitude': lat,
                    'longitude': lon,
                    'walk_score': score_data.get('walkscore', 0),
                    'transit_score': score_data.get('transit', {}).get('score', 0),
                    'bike_score': score_data.get('bike', {}).get('score', 0),
                    'walk_description': score_data.get('description', 'Unknown'),
                    'status': 'success'
                }
            else:
                result = {
                    'zip_code': zip_code,
                    'latitude': lat,
                    'longitude': lon,
                    'walk_score': 0,
                    'transit_score': 0,
                    'bike_score': 0,
                    'walk_description': 'Data unavailable',
                    'status': 'failed'
                }
            
            results.append(result)
            
            # Progress save every 10 ZIP codes
            if (idx + 1) % 10 == 0:
                temp_df = pd.DataFrame(results)
                temp_path = PROCESSED_DATA_DIR / f"walkscore_data_progress_{idx + 1}.csv"
                temp_df.to_csv(temp_path, index=False)
                logger.info(f"Progress saved: {idx + 1} ZIP codes processed")
        
        return pd.DataFrame(results)
    
    def save_walkscore_data(self, df: pd.DataFrame) -> None:
        """Save WalkScore data to processed files."""
        if df.empty:
            logger.warning("No WalkScore data to save.")
            return
        
        # Save as CSV
        csv_path = PROCESSED_DATA_DIR / "walkscore_data.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"WalkScore data saved to {csv_path}")
        
        # REMOVED: JSON output - CSV only
        
        # Generate summary statistics
        self._generate_summary_stats(df)
    
    def _generate_summary_stats(self, df: pd.DataFrame) -> None:
        """Generate and save summary statistics."""
        stats = {
            'total_zip_codes': len(df),
            'successful_requests': len(df[df['status'] == 'success']),
            'failed_requests': len(df[df['status'] == 'failed']),
            'success_rate': len(df[df['status'] == 'success']) / len(df) * 100,
            'average_walk_score': df[df['walk_score'] > 0]['walk_score'].mean(),
            'average_transit_score': df[df['transit_score'] > 0]['transit_score'].mean(),
            'average_bike_score': df[df['bike_score'] > 0]['bike_score'].mean(),
            'top_walkable_zips': df.nlargest(5, 'walk_score')[['zip_code', 'walk_score']].to_dict('records'),
            'top_transit_zips': df.nlargest(5, 'transit_score')[['zip_code', 'transit_score']].to_dict('records')
        }
        
        # REMOVED: JSON stats output - keeping only CSV data
        logger.info("WalkScore statistics calculated (no JSON output)")
        logger.info(f"Success rate: {stats['success_rate']:.1f}%")
        logger.info(f"Average walk score: {stats['average_walk_score']:.1f}")

def main():
    """Main function for command line execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect WalkScore data for Austin ZIP codes')
    parser.add_argument('--api-key', help='WalkScore API key (optional - will use demo data if not provided)')
    args = parser.parse_args()
    
    collector = WalkScoreDataCollector(args.api_key)
    
    logger.info("Starting WalkScore data collection...")
    walkscore_df = collector.collect_walkscores_for_zips()
    
    if not walkscore_df.empty:
        collector.save_walkscore_data(walkscore_df)
        logger.info("WalkScore data collection completed successfully!")
    else:
        logger.error("WalkScore data collection failed.")

if __name__ == "__main__":
    main()
