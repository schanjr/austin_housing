"""
Multi-threaded geocoding script for Austin Housing listings.
Precomputes precise coordinates for all rental listings using concurrent processing.
"""
import pandas as pd
import requests
import time
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import sys
from typing import Dict, Tuple, Optional, List
import os
import re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import random
from tqdm import tqdm

# Setup paths
ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(PROCESSED_DATA_DIR / 'geocoding.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Thread-safe file writing
write_lock = Lock()

class GeocodingService:
    def __init__(self, max_workers: int = 10, rate_limit_delay: float = 0.2, google_api_key: str = None):
        self.max_workers = max_workers
        self.rate_limit_delay = rate_limit_delay
        self.google_api_key = google_api_key
        self.request_count = 0
        self.session_start_time = time.time()
        self._init_session()
        
    def _init_session(self):
        """Initialize a fresh session to avoid rate limiting"""
        if hasattr(self, 'session'):
            self.session.close()
        
        self.session = requests.Session()
        
        # Comprehensive browser headers - 20+ realistic combinations
        browser_configs = [
            # Chrome on macOS variations
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.8,es;q=0.6',
                'Accept-Encoding': 'gzip, deflate, br',
                'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"'
            },
            # Chrome on Windows variations
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            },
            # Firefox variations
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1'
            },
            {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1'
            },
            # Safari variations
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            },
            # Edge variations
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            },
            # Mobile browsers
            {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"'
            }
        ]
        
        # Select browser config based on request count
        selected_config = browser_configs[self.request_count % len(browser_configs)]
        
        # Update session headers with selected configuration
        self.session.headers.update(selected_config)
        
        # Add common headers that all browsers have
        self.session.headers.update({
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        self.session_start_time = time.time()
        logger.info(f"Initialized fresh session #{self.request_count} with {selected_config['User-Agent'][:50]}...")
        
    def _should_refresh_session(self) -> bool:
        """Check if we should refresh the session to avoid rate limiting (aggressive)"""
        # AGGRESSIVE: Refresh session every 25-30 requests or every 5 minutes
        refresh_interval = random.randint(25, 30)  # Randomize to avoid patterns
        return (self.request_count > 0 and 
                (self.request_count % refresh_interval == 0 or 
                 time.time() - self.session_start_time > 300))
        
    def geocode_with_google_api(self, address: str) -> Tuple[Optional[float], Optional[float]]:
        """Geocode using Google Geocoding API (requires API key)"""
        if not self.google_api_key:
            return None, None
            
        try:
            base_url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': address,
                'key': self.google_api_key,
                'bounds': '30.0,-98.2|30.6,-97.4',  # Austin area bounds
                'region': 'us'
            }
            
            response = self.session.get(base_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'OK' and data['results']:
                    location = data['results'][0]['geometry']['location']
                    lat = float(location['lat'])
                    lon = float(location['lng'])
                    
                    # Validate coordinates are in Austin area
                    if 30.0 <= lat <= 30.6 and -98.2 <= lon <= -97.4:
                        return lat, lon
                        
        except Exception as e:
            logger.warning(f"Google API geocoding failed for {address}: {e}")
            
        return None, None
    
    def clean_address_for_geocoding(self, address: str) -> Tuple[str, bool]:
        """Clean address and return (cleaned_address, has_unit_number)"""
        # Remove building/complex names before pipe
        clean_address = address.replace('|', ',').strip()
        if '|' in address:
            parts = address.split('|')
            if len(parts) > 1:
                clean_address = parts[1].strip()
        
        # Check if address has unit/apartment numbers
        has_unit = bool(re.search(r'\b(unit|apt|apartment|#|suite)\s*[a-z0-9\-]+', clean_address, re.IGNORECASE))
        
        # Remove unit numbers for better geocoding success
        if has_unit:
            # Remove common unit patterns
            patterns_to_remove = [
                r'\bunit\s+[a-z0-9\-]+',
                r'\bapt\s+[a-z0-9\-]+', 
                r'\bapartment\s+[a-z0-9\-]+',
                r'\bsuite\s+[a-z0-9\-]+',
                r'#[a-z0-9\-]+',
                r'\s+[a-z]\d+[\-\d]*$',  # Pattern like A7-28 at end
            ]
            
            for pattern in patterns_to_remove:
                clean_address = re.sub(pattern, '', clean_address, flags=re.IGNORECASE)
            
            # Clean up extra spaces and commas
            clean_address = re.sub(r'\s+', ' ', clean_address).strip()
            clean_address = re.sub(r',\s*,', ',', clean_address)
        
        return clean_address, has_unit
    
    def add_unit_offset(self, lat: float, lon: float, has_unit: bool) -> Tuple[float, float]:
        """Add small random offset to simulate different units in same building"""
        if not has_unit:
            return lat, lon
            
        # Add small random offset (roughly 10-50 meters)
        lat_offset = random.uniform(-0.0002, 0.0002)  # ~22 meters
        lon_offset = random.uniform(-0.0002, 0.0002)  # ~22 meters
        
        return lat + lat_offset, lon + lon_offset
    
    def geocode_with_google_maps_scraping(self, address: str) -> Tuple[Optional[float], Optional[float]]:
        """Geocode by scraping Google Maps (free but slower) with anti-rate-limiting"""
        try:
            # Check if we should refresh session to avoid rate limiting
            if self._should_refresh_session():
                logger.info("Refreshing session to avoid rate limiting...")
                self._init_session()
                # Add extra delay after session refresh to simulate "fresh start"
                time.sleep(random.uniform(5, 10))
            
            self.request_count += 1
            
            # Clean address and check for unit numbers
            clean_address, has_unit = self.clean_address_for_geocoding(address)
            logger.debug(f"Cleaned address: '{address}' -> '{clean_address}' (has_unit: {has_unit})")
            
            encoded_address = quote_plus(clean_address)
            
            # Use Google Maps search URL (works better than place URL)
            url = f"https://www.google.com/maps/search/{encoded_address}"
            
            # AGGRESSIVE progressive delay strategy - match faster session refresh
            base_delay = self.rate_limit_delay
            if self.request_count > 150:
                base_delay *= 4  # 4x delay after 150 requests
            elif self.request_count > 100:
                base_delay *= 3  # 3x delay after 100 requests
            elif self.request_count > 50:
                base_delay *= 2  # 2x delay after 50 requests
            
            # Add significant randomization to avoid detection patterns
            delay = random.uniform(base_delay * 1.5, base_delay * 3.5)
            time.sleep(delay)
            
            # Use the comprehensive headers from the current session (already set in _init_session)
            # This includes all the realistic browser-specific headers
            headers = dict(self.session.headers)
            
            # Override Accept-Encoding to avoid compression issues
            headers['Accept-Encoding'] = 'gzip, deflate'
            
            try:
                response = self.session.get(url, headers=headers, timeout=15, allow_redirects=True)
                
                if response.status_code == 429:
                    # Rate limited - force session refresh and longer delay
                    logger.warning(f"Rate limited (429) - forcing session refresh and longer delay")
                    self._init_session()
                    time.sleep(random.uniform(30, 60))  # Long delay after rate limit
                    return None, None
                elif response.status_code != 200:
                    logger.debug(f"Bad status code: {response.status_code}")
                    return None, None
        
                # Get the HTML content
                try:
                    if response.encoding:
                        content = response.text
                    else:
                        content = response.content.decode('utf-8', errors='ignore')
                except Exception as decode_error:
                    logger.debug(f"Content decode error: {decode_error}")
                    return None, None
                
                logger.debug(f"Got content length: {len(content)} characters")
                
                # Look for coordinates in page content using the working pattern from debug
                coord_patterns = [
                    r'center.*?(-?\d+\.\d+).*?(-?\d+\.\d+)',  # This pattern works!
                    r'"lat":(-?\d+\.\d+),"lng":(-?\d+\.\d+)',
                    r'"latitude":(-?\d+\.\d+),"longitude":(-?\d+\.\d+)',
                    r'\[(-?\d+\.\d+),(-?\d+\.\d+)\]',
                    r'@(-?\d+\.\d+),(-?\d+\.\d+)',
                    r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)'
                ]
                
                for pattern in coord_patterns:
                    matches = re.findall(pattern, content)
                    for match in matches:
                        try:
                            lat, lon = float(match[0]), float(match[1])
                            if 30.0 <= lat <= 30.6 and -98.2 <= lon <= -97.4:
                                # Add small offset for unit numbers
                                final_lat, final_lon = self.add_unit_offset(lat, lon, has_unit)
                                logger.debug(f"✅ Found coordinates: {final_lat}, {final_lon}")
                                return final_lat, final_lon
                        except (ValueError, IndexError):
                            continue
                
                logger.debug(f"No coordinates found in content for {clean_address}")
                
            except Exception as e:
                logger.debug(f"Request failed: {e}")
                                
        except Exception as e:
            logger.warning(f"Google Maps scraping failed for {address}: {e}")
            
        return None, None
    
    
    def geocode_address(self, address: str, retries: int = 3) -> Tuple[Optional[float], Optional[float]]:
        """Geocode a single address with multiple methods and robust retry logic"""
        for attempt in range(retries):
            try:
                # Method 1: Try Google Geocoding API if API key is available
                if self.google_api_key:
                    lat, lon = self.geocode_with_google_api(address)
                    if lat and lon:
                        # Success - no logging needed
                        return lat, lon
                
                # Method 2: Try Google Maps scraping (free but slower)
                lat, lon = self.geocode_with_google_maps_scraping(address)
                if lat and lon:
                    # Success - no logging needed
                    return lat, lon
                
                # If geocoding failed, wait 30 seconds before retry (as requested)
                if attempt < retries - 1:
                    logger.warning(f"Geocoding attempt {attempt + 1} failed for {address}, waiting 30 seconds before retry...")
                    time.sleep(30)  # Wait 30 seconds before retry as requested
                    
            except Exception as e:
                logger.warning(f"Geocoding attempt {attempt + 1} failed for {address}: {e}")
                if attempt < retries - 1:
                    logger.info("Waiting 30 seconds before retry...")
                    time.sleep(30)  # Wait 30 seconds before retry as requested
        
        # No fallback - return None if all attempts failed
        logger.error(f"All geocoding attempts failed for {address} - no fallback used")
        return None, None
    
    def process_listing(self, listing_data: Dict) -> Dict:
        """Process a single listing and add geocoded coordinates"""
        listing_id = listing_data.get('id', 'unknown')
        address = listing_data.get('address', '')
        
        # Skip if address is empty or already geocoded
        if not address or 'Austin, TX' not in address:
            logger.debug(f"Skipping {listing_id}: invalid address")
            return listing_data
        
        # Geocode the address - no fallback, only real geocoding
        lat, lon = self.geocode_address(address)
        
        if lat and lon:
            listing_data['geocoded_lat'] = lat
            listing_data['geocoded_lon'] = lon
            listing_data['geocoded_status'] = 'success'
            # Success - no logging needed
        else:
            # NO FALLBACK - leave coordinates empty if geocoding fails
            listing_data['geocoded_lat'] = None
            listing_data['geocoded_lon'] = None
            listing_data['geocoded_status'] = 'failed'
            logger.error(f"Geocoding failed for {listing_id}: {address} - no coordinates assigned")
        
        return listing_data

class GeocodingManager:
    def __init__(self, input_file: str, output_file: str, max_workers: int = 1):
        self.input_file = PROCESSED_DATA_DIR / input_file
        self.output_file = PROCESSED_DATA_DIR / output_file
        self.max_workers = max_workers
        self.geocoding_service = GeocodingService(max_workers)  # Will be replaced in main()
        
    def load_existing_progress(self) -> set:
        """Load existing geocoded listing IDs (both successful and failed attempts)"""
        existing_ids = set()
        
        # Load all IDs from the geocoded progress file (includes both successful and failed)
        if self.output_file.exists():
            try:
                df = pd.read_csv(self.output_file)
                existing_ids = set(df['id'].astype(str))
                logger.info(f"Loaded {len(existing_ids)} already processed listing IDs")
            except Exception as e:
                logger.warning(f"Could not load existing data: {e}")
        
        return existing_ids
    
    def save_progress(self, completed_listings: List[Dict]):
        """Save completed listings to CSV, avoiding duplicates"""
        if not completed_listings:
            return
        
        with write_lock:
            new_df = pd.DataFrame(completed_listings)
            
            if self.output_file.exists():
                # Load existing data to check for duplicates
                existing_df = pd.read_csv(self.output_file)
                existing_ids = set(existing_df['id'].astype(str))
                
                # Filter out listings that already exist
                new_listings = [l for l in completed_listings if str(l['id']) not in existing_ids]
                
                if new_listings:
                    new_df = pd.DataFrame(new_listings)
                    new_df.to_csv(self.output_file, mode='a', header=False, index=False)
                    
                    # Log summary
                    successful_count = len([l for l in new_listings if l.get('geocoded_status') == 'success'])
                    failed_count = len(new_listings) - successful_count
                    if failed_count > 0:
                        logger.info(f"Batch: {successful_count} successful, {failed_count} failed")
                else:
                    logger.debug("All listings in batch already exist - skipping save")
            else:
                # First time - create new file
                new_df.to_csv(self.output_file, index=False)
                
                # Log summary
                successful_count = len([l for l in completed_listings if l.get('geocoded_status') == 'success'])
                failed_count = len(completed_listings) - successful_count
                if failed_count > 0:
                    logger.info(f"Batch: {successful_count} successful, {failed_count} failed")
    
    def geocode_all_listings(self, batch_size: int = 50):
        """Main method to geocode all listings with multi-threading"""
        logger.info("Starting geocoding process...")
        
        # Load input data
        if not self.input_file.exists():
            logger.error(f"Input file not found: {self.input_file}")
            return
        
        df = pd.read_csv(self.input_file)
        logger.info(f"Loaded {len(df)} listings from {self.input_file}")
        
        # Load existing progress (set of processed IDs)
        existing_ids = self.load_existing_progress()
        
        # Filter out already processed listings
        remaining_listings = []
        for _, row in df.iterrows():
            if str(row['id']) not in existing_ids:
                remaining_listings.append(row.to_dict())
        
        logger.info(f"Processing {len(remaining_listings)} remaining listings (skipping {len(existing_ids)} already done)")
        
        if not remaining_listings:
            logger.info("All listings already geocoded!")
            return
        
        # Process in batches with threading and progress bar
        completed_count = 0
        batch_results = []
        
        # Initialize progress bar
        progress_bar = tqdm(total=len(remaining_listings), desc="Geocoding", unit="listings", ncols=100)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_listing = {
                executor.submit(self.geocoding_service.process_listing, listing): listing
                for listing in remaining_listings
            }
            
            # Process completed jobs
            for future in as_completed(future_to_listing):
                try:
                    result = future.result()
                    batch_results.append(result)
                    completed_count += 1
                    
                    # Update progress bar
                    progress_bar.update(1)
                    
                    # Save progress in batches with delay to prevent rate limiting
                    if len(batch_results) >= batch_size:
                        self.save_progress(batch_results)
                        batch_results = []
                        # Add delay between batches to prevent rate limiting
                        if completed_count < len(remaining_listings):  # Don't delay after last batch
                            delay_seconds = 10
                            progress_bar.set_description(f"Geocoding (waiting {delay_seconds}s)")
                            time.sleep(delay_seconds)
                            progress_bar.set_description("Geocoding")
                        
                except Exception as e:
                    logger.error(f"Error processing listing: {e}")
                    progress_bar.update(1)  # Still update progress even on error
        
        # Close progress bar
        progress_bar.close()
        
        # Save any remaining results
        if batch_results:
            self.save_progress(batch_results)
        
        logger.info(f"Geocoding completed! Processed {completed_count} listings")
        
        # Create final consolidated file
        self.create_final_output()
    
    def create_final_output(self):
        """Create final consolidated geocoded file"""
        try:
            # Load all data (original + existing + new)
            original_df = pd.read_csv(self.input_file)
            
            if self.output_file.exists():
                geocoded_df = pd.read_csv(self.output_file)
                
                # Merge on ID to get geocoded coordinates
                final_df = original_df.merge(
                    geocoded_df[['id', 'geocoded_lat', 'geocoded_lon', 'geocoded_status']], 
                    on='id', 
                    how='left'
                )
                
                # NO FALLBACK - keep geocoded coordinates as None if geocoding failed
                # Only use successfully geocoded coordinates
                final_df['geocoded_status'] = final_df['geocoded_status'].fillna('not_processed')
                
                # Save final file
                final_output = PROCESSED_DATA_DIR / f"geocoded_{self.input_file.name}"
                final_df.to_csv(final_output, index=False)
                
                logger.info(f"Created final geocoded file: {final_output}")
                
                # Log statistics
                success_count = len(final_df[final_df['geocoded_status'] == 'success'])
                failed_count = len(final_df[final_df['geocoded_status'] == 'failed'])
                not_processed_count = len(final_df[final_df['geocoded_status'] == 'not_processed'])
                
                logger.info(f"Geocoding statistics:")
                logger.info(f"  Successfully geocoded: {success_count}")
                logger.info(f"  Failed geocoding: {failed_count}")
                logger.info(f"  Not processed: {not_processed_count}")
                logger.info(f"  Success rate: {success_count/(success_count+failed_count+not_processed_count)*100:.1f}%")
                
        except Exception as e:
            logger.error(f"Error creating final output: {e}")

def main():
    """Main function for command line execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Geocode Austin housing listings using Google Maps')
    parser.add_argument('--input', default='redfin_listings_complete.csv', 
                       help='Input CSV file name')
    parser.add_argument('--output', default='geocoded_listings_progress.csv', 
                       help='Output CSV file name')
    parser.add_argument('--workers', type=int, default=5, 
                       help='Number of worker threads (reduced for Google Maps)')
    parser.add_argument('--batch-size', type=int, default=25, 
                       help='Batch size for progress saving')
    parser.add_argument('--google-api-key', 
                       help='Google Geocoding API key (optional, will use scraping if not provided)')
    
    args = parser.parse_args()
    
    # Check for API key in environment if not provided
    google_api_key = args.google_api_key or os.getenv('GOOGLE_GEOCODING_API_KEY')
    
    if google_api_key:
        logger.info(f"Using Google Geocoding API with {args.workers} workers")
    else:
        logger.info(f"Using Google Maps scraping with {args.workers} workers (slower but free)")
        logger.info("Tip: Set GOOGLE_GEOCODING_API_KEY environment variable for faster processing")
    
    # Create geocoding service with Google API key
    geocoding_service = GeocodingService(
        max_workers=args.workers,
        rate_limit_delay=0.5 if not google_api_key else 0.1,  # Slower for scraping
        google_api_key=google_api_key
    )
    
    manager = GeocodingManager(
        input_file=args.input,
        output_file=args.output,
        max_workers=args.workers
    )
    manager.geocoding_service = geocoding_service  # Use our custom service
    
    manager.geocode_all_listings(batch_size=args.batch_size)

if __name__ == "__main__":
    main()
