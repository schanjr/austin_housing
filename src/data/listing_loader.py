import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import logging
import os

ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ListingLoader:
    def __init__(self):
        self.zillow_data = None
        self.redfin_data = None
        self._file_timestamps = {}
        self._load_data()
    
    def _load_data(self):
        """Load data from dump files"""
        try:
            # Zillow data is DISABLED - do not load any Zillow listings
            self.zillow_data = None
            logger.info("Zillow listings disabled - not loading any Zillow data")
                
            # Load Redfin data
            redfin_path = PROCESSED_DATA_DIR / "redfin_listings_complete.csv"
            if redfin_path.exists():
                # Check if file has been modified since last load
                current_timestamp = os.path.getmtime(redfin_path)
                last_timestamp = self._file_timestamps.get('redfin', 0)
                
                if current_timestamp > last_timestamp or self.redfin_data is None:
                    logger.info(f"Loading Redfin data (file modified: {current_timestamp > last_timestamp})")
                    self.redfin_data = pd.read_csv(redfin_path)
                    # Convert string representations back to lists for image_urls and amenities
                    for col in ['image_urls', 'amenities']:
                        if col in self.redfin_data.columns:
                            self.redfin_data[col] = self.redfin_data[col].apply(
                                lambda x: eval(x) if pd.notna(x) and x != '[]' and x != '' else []
                            )
                    self._file_timestamps['redfin'] = current_timestamp
                    logger.info(f"Loaded {len(self.redfin_data)} Redfin listings")
                else:
                    logger.debug("Redfin data already up to date")
            else:
                logger.warning("Redfin data dump not found")
                self.redfin_data = None
                
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    def get_listings(self, zip_code: str = None, max_rent: int = None, 
                    bedrooms: List[str] = None, source: str = None) -> pd.DataFrame:
        """Get filtered listings from data dumps"""
        all_listings = []
        
        # Collect data from requested sources
        # Zillow is DISABLED - skip all Zillow data
        if source is None or source.lower() == 'zillow':
            if source and source.lower() == 'zillow':
                logger.warning("Zillow listings are disabled - returning empty results")
            # Do not load any Zillow data
        
        if source is None or source.lower() == 'redfin':
            if self.redfin_data is not None:
                all_listings.append(self.redfin_data.copy())
        
        if not all_listings:
            logger.warning("No data available")
            return pd.DataFrame()
        
        # Combine all data
        combined_df = pd.concat(all_listings, ignore_index=True)
        
        # Apply filters
        filtered_df = combined_df.copy()
        
        if zip_code:
            # Handle both string and integer ZIP codes
            zip_code_str = str(zip_code)
            try:
                zip_code_int = int(zip_code)
            except (ValueError, TypeError):
                zip_code_int = None
            
            # Filter for both string and integer representations
            if zip_code_int:
                filtered_df = filtered_df[
                    (filtered_df['zip_code'] == zip_code_str) | 
                    (filtered_df['zip_code'] == zip_code_int)
                ]
            else:
                filtered_df = filtered_df[filtered_df['zip_code'] == zip_code_str]
        
        if max_rent:
            filtered_df = filtered_df[filtered_df['rent'] <= max_rent]
        
        if bedrooms:
            bedroom_values = []
            for b in bedrooms:
                if b == "Studio":
                    bedroom_values.append(0)
                elif "Bedroom" in b:
                    bedroom_values.append(int(b.split()[0]))
            if bedroom_values:
                filtered_df = filtered_df[filtered_df['bedrooms'].isin(bedroom_values)]
        
        if source and source.lower() in ['zillow', 'redfin']:
            filtered_df = filtered_df[filtered_df['source'].str.lower() == source.lower()]
        
        return filtered_df
    
    def get_listing_counts_by_zip(self, max_rent: int = None, 
                                 bedrooms: List[str] = None) -> Dict[str, Dict[str, int]]:
        """Get listing counts by ZIP code and source"""
        counts = {}
        
        # Get all listings with filters
        all_listings = self.get_listings(max_rent=max_rent, bedrooms=bedrooms)
        
        if all_listings.empty:
            return counts
        
        # Group by ZIP code and source
        grouped = all_listings.groupby(['zip_code', 'source']).size().reset_index(name='count')
        
        for _, row in grouped.iterrows():
            zip_code = str(row['zip_code'])  # Convert numpy.int64 to string
            source = row['source']
            count = row['count']
            
            if zip_code not in counts:
                counts[zip_code] = {'zillow': 0, 'redfin': 0, 'total': 0}
            
            counts[zip_code][source] = count
            counts[zip_code]['total'] += count
        
        return counts
    
    def get_listing_details(self, listing_id: str) -> Optional[Dict]:
        """Get detailed information for a specific listing"""
        all_data = []
        if self.zillow_data is not None:
            all_data.append(self.zillow_data)
        if self.redfin_data is not None:
            all_data.append(self.redfin_data)
        
        for df in all_data:
            matching = df[df['id'] == listing_id]
            if not matching.empty:
                return matching.iloc[0].to_dict()
        
        return None
    
    def get_listings_with_coordinates(self, zip_code: str = None, max_rent: int = None,
                                    bedrooms: List[str] = None, source: str = None) -> pd.DataFrame:
        """Get listings that have coordinate information for mapping"""
        listings = self.get_listings(zip_code, max_rent, bedrooms, source)
        
        # Filter for listings with coordinates (if available)
        # For now, we'll use ZIP code centroids, but this could be enhanced
        # with actual property coordinates if scraped
        return listings
    
    def refresh_data(self):
        """Force reload data from dump files, ignoring timestamps"""
        logger.info("Force refreshing all data from dump files...")
        # Clear timestamps to force reload
        self._file_timestamps.clear()
        # Clear existing data
        self.zillow_data = None
        self.redfin_data = None
        # Reload everything
        self._load_data()
        logger.info("Data refresh completed")
    
    def data_available(self) -> bool:
        """Check if any data is available"""
        # Auto-refresh if files have been updated
        self._load_data()
        return self.zillow_data is not None or self.redfin_data is not None
    
    def get_data_stats(self) -> Dict:
        """Get statistics about loaded data"""
        stats = {
            'zillow_count': 0,  # Zillow is disabled
            'redfin_count': len(self.redfin_data) if self.redfin_data is not None else 0,
            'total_count': 0,
            'zip_codes': set(),
            'last_updated': None
        }
        
        # Zillow data is disabled - skip all Zillow processing
        
        if self.redfin_data is not None:
            stats['zip_codes'].update(self.redfin_data['zip_code'].unique())
            if 'scraped_at' in self.redfin_data.columns:
                stats['last_updated'] = self.redfin_data['scraped_at'].max()
        
        stats['total_count'] = stats['redfin_count']  # Only Redfin data
        stats['zip_codes'] = list(stats['zip_codes'])
        
        return stats

# Global instance
listing_loader = ListingLoader()
