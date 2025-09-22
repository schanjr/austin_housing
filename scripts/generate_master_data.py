"""
Single master data generation script that consolidates all data sources
This replaces all the scattered data generation scripts with one unified pipeline
"""
import pandas as pd
from pathlib import Path
import logging
import sys
import argparse
from datetime import datetime

# Add paths for imports
root_dir = Path(__file__).parent.parent
app_dir = root_dir / "app"
src_dir = root_dir / "src"
sys.path.insert(0, str(app_dir))
sys.path.insert(0, str(src_dir))

from app.property_scoring import PropertyScorer
from src.data.listing_loader import listing_loader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MasterDataGenerator:
    """Single class to generate the master dataset from all sources."""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data" / "processed"
        self.scorer = PropertyScorer()
        
    def load_rental_listings(self):
        """Load rental listings from all sources."""
        logger.info("Loading rental listings...")
        
        # First try existing scored properties
        scored_path = self.data_dir / "properties_with_scores.csv"
        if scored_path.exists():
            logger.info("Loading existing scored properties...")
            properties_df = pd.read_csv(scored_path)
            logger.info(f"Loaded {len(properties_df)} properties with scores")
            return properties_df
        
        # Fallback to listing_loader
        listings_df = listing_loader.get_listings()
        
        if listings_df is None or listings_df.empty:
            logger.error("No rental listings found. Run scrapers first: poetry run scrape-all")
            return pd.DataFrame()
            
        logger.info(f"Loaded {len(listings_df)} rental listings")
        return listings_df
    
    def load_geocoded_coordinates(self):
        """Load geocoded coordinates if available."""
        geocoded_path = self.data_dir / "geocoded_listings_progress.csv"
        
        if geocoded_path.exists():
            logger.info("Loading geocoded coordinates...")
            geocoded_df = pd.read_csv(geocoded_path)
            logger.info(f"Loaded {len(geocoded_df)} geocoded properties")
            return geocoded_df
        else:
            logger.warning("No geocoded coordinates found. Run: poetry run geocode-all")
            return pd.DataFrame()
    
    def calculate_property_scores(self, properties_df):
        """Calculate scores for all properties."""
        # Check if properties already have scores
        score_columns = ['overall_score', 'affordability_score', 'safety_score', 
                        'accessibility_score', 'neighborhood_score', 'environment_score']
        
        if all(col in properties_df.columns for col in score_columns):
            logger.info("Properties already have scores - skipping calculation")
            return properties_df
        
        logger.info("Calculating property scores...")
        
        scored_properties = []
        total = len(properties_df)
        
        for idx, (_, property_data) in enumerate(properties_df.iterrows()):
            if idx % 1000 == 0:
                logger.info(f"Scoring progress: {idx}/{total} ({idx/total*100:.1f}%)")
            
            try:
                # Calculate scores
                scores = self.scorer.calculate_property_scores(property_data.to_dict())
                
                # Create scored property record
                scored_property = property_data.to_dict()
                scored_property.update({
                    'overall_score': scores['overall_score'],
                    'affordability_score': scores['scores']['affordability']['score'],
                    'safety_score': scores['scores']['safety']['score'],
                    'accessibility_score': scores['scores']['accessibility']['score'],
                    'neighborhood_score': scores['scores']['neighborhood']['score'],
                    'environment_score': scores['scores']['environment']['score'],
                    'affordability_explanation': scores['scores']['affordability']['explanation'],
                    'safety_explanation': scores['scores']['safety']['explanation'],
                    'accessibility_explanation': scores['scores']['accessibility']['explanation'],
                    'neighborhood_explanation': scores['scores']['neighborhood']['explanation'],
                    'environment_explanation': scores['scores']['environment']['explanation'],
                    'affordability_weight': scores['weights']['affordability'],
                    'safety_weight': scores['weights']['safety'],
                    'accessibility_weight': scores['weights']['accessibility'],
                    'neighborhood_weight': scores['weights']['neighborhood'],
                    'environment_weight': scores['weights']['environment']
                })
                
                scored_properties.append(scored_property)
                
            except Exception as e:
                logger.warning(f"Error scoring property {property_data.get('address', 'Unknown')}: {e}")
                continue
        
        logger.info(f"Successfully scored {len(scored_properties)} properties")
        return pd.DataFrame(scored_properties)
    
    def merge_geocoded_coordinates(self, properties_df, geocoded_df):
        """Merge geocoded coordinates and URLs with property data."""
        if geocoded_df.empty:
            logger.warning("No geocoded data to merge")
            return properties_df
        
        logger.info("Merging geocoded coordinates and URLs...")
        
        # Determine which columns to merge from geocoded data
        merge_columns = ['address', 'geocoded_lat', 'geocoded_lon']
        if 'listing_url' in geocoded_df.columns:
            merge_columns.append('listing_url')
            logger.info("Found listing_url column in geocoded data - will merge URLs")
        
        # Merge by address
        merged_df = properties_df.merge(
            geocoded_df[merge_columns], 
            on='address', 
            how='left'
        )
        
        # Use geocoded coordinates when available, fallback to original
        merged_df['latitude'] = merged_df['geocoded_lat'].fillna(merged_df.get('latitude', 0))
        merged_df['longitude'] = merged_df['geocoded_lon'].fillna(merged_df.get('longitude', 0))
        
        # Merge URLs if available from geocoded data
        if 'listing_url' in merged_df.columns:
            # Fill empty url column with listing_url values from geocoded data
            if 'url' not in merged_df.columns:
                merged_df['url'] = ''
            
            # Use listing_url from geocoded data when url is empty
            mask = (merged_df['url'] == '') | merged_df['url'].isna()
            merged_df.loc[mask, 'url'] = merged_df.loc[mask, 'listing_url'].fillna('')
            
            url_count = (merged_df['url'] != '').sum()
            logger.info(f"Merged URLs from geocoded data: {url_count} properties now have listing URLs")
        
        # Clean up intermediate columns
        merged_df = merged_df.drop(['geocoded_lat', 'geocoded_lon'], axis=1, errors='ignore')
        if 'listing_url' in merged_df.columns:
            merged_df = merged_df.drop(['listing_url'], axis=1, errors='ignore')
        
        geocoded_count = merged_df['latitude'].notna().sum()
        logger.info(f"Successfully merged coordinates for {geocoded_count} properties")
        
        return merged_df
    
    def standardize_url_column(self, properties_df):
        """Ensure URL column is properly mapped from listing_url field."""
        logger.info("Standardizing URL column...")
        
        # Map listing_url to url column if url is missing/empty
        if 'listing_url' in properties_df.columns:
            # Fill empty url column with listing_url values
            properties_df['url'] = properties_df.get('url', '').fillna('')
            mask = (properties_df['url'] == '') | properties_df['url'].isna()
            properties_df.loc[mask, 'url'] = properties_df.loc[mask, 'listing_url']
            
            url_count = properties_df['url'].notna().sum()
            non_empty_urls = (properties_df['url'] != '').sum()
            logger.info(f"Standardized URLs: {non_empty_urls} properties have listing URLs")
        else:
            logger.warning("No listing_url column found in properties data")
            # Ensure url column exists even if empty
            if 'url' not in properties_df.columns:
                properties_df['url'] = ''
        
        return properties_df
    
    def generate_master_dataset(self, force_rescore=False):
        """Generate the complete master dataset."""
        logger.info("=== MASTER DATA GENERATION STARTED ===")
        start_time = datetime.now()
        
        # Check if master dataset already exists and is recent
        master_path = self.data_dir / "master_properties.csv"
        if master_path.exists() and not force_rescore:
            logger.info("Master dataset already exists. Use --force to regenerate.")
            return master_path
        
        # Load rental listings
        properties_df = self.load_rental_listings()
        if properties_df.empty:
            logger.error("Cannot generate master dataset without rental listings")
            return None
        
        # Load geocoded coordinates
        geocoded_df = self.load_geocoded_coordinates()
        
        # Merge coordinates first
        properties_df = self.merge_geocoded_coordinates(properties_df, geocoded_df)
        
        # Standardize URL column mapping
        properties_df = self.standardize_url_column(properties_df)
        
        # Calculate property scores
        scored_df = self.calculate_property_scores(properties_df)
        
        if scored_df.empty:
            logger.error("Failed to generate scored properties")
            return None
        
        # Save master dataset
        scored_df.to_csv(master_path, index=False)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("=== MASTER DATA GENERATION COMPLETED ===")
        logger.info(f"Generated master dataset: {master_path}")
        logger.info(f"Total properties: {len(scored_df):,}")
        logger.info(f"Generation time: {duration}")
        
        # Show coordinate quality
        self._analyze_coordinate_quality(scored_df)
        
        return master_path
    
    def _analyze_coordinate_quality(self, df):
        """Analyze coordinate quality across ZIP codes."""
        logger.info("\n=== COORDINATE QUALITY ANALYSIS ===")
        
        sample_zips = ['78701', '78702', '78703', '78721', '78704']
        for zip_code in sample_zips:
            zip_data = df[df['zip_code'].astype(str) == zip_code]
            if len(zip_data) > 0:
                unique_coords = len(zip_data[['latitude', 'longitude']].drop_duplicates())
                logger.info(f"ZIP {zip_code}: {len(zip_data)} properties, {unique_coords} unique coordinates")

def main():
    """Main function with command line arguments."""
    parser = argparse.ArgumentParser(description='Generate master dataset for Austin Housing Dashboard')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if master dataset exists')
    
    args = parser.parse_args()
    
    generator = MasterDataGenerator()
    result = generator.generate_master_dataset(force_rescore=args.force)
    
    if result:
        print(f"\n✅ SUCCESS: Master dataset generated at {result}")
        print("🚀 Ready to run dashboard: poetry run dashboard")
    else:
        print("\n❌ FAILED: Could not generate master dataset")
        print("💡 Make sure to run scrapers first: poetry run scrape-all")
        sys.exit(1)

if __name__ == "__main__":
    main()
