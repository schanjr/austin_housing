import os
import json
import pandas as pd
import requests
from pathlib import Path
import datetime
import time
import random
from bs4 import BeautifulSoup
import re
from urllib.parse import urlencode, quote_plus
import logging
import sys
from typing import List, Dict, Optional, Set

ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RedfinScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Load ZIP code centroids for coordinate fallback
        self.zip_centroids = self._load_zip_centroids()
        
    def _load_zip_centroids(self) -> Dict[str, tuple]:
        """Load ZIP code centroids for coordinate mapping"""
        # Austin ZIP code centroids (approximate centers)
        return {
            '78701': (30.2672, -97.7431),  # Downtown
            '78702': (30.2515, -97.7323),  # East Austin
            '78703': (30.2849, -97.7881),  # West Austin
            '78704': (30.2322, -97.7697),  # South Austin
            '78705': (30.2849, -97.7431),  # UT Area
            '78712': (30.2849, -97.7431),  # UT Campus
            '78717': (30.4518, -97.8147),  # Cedar Park
            '78719': (30.1133, -97.8428),  # Southwest Austin
            '78721': (30.2515, -97.7031),  # East Austin
            '78722': (30.2849, -97.7031),  # East Austin
            '78723': (30.3072, -97.6789),  # Northeast Austin
            '78724': (30.2515, -97.6539),  # East Austin
            '78725': (30.2322, -97.6539),  # Southeast Austin
            '78726': (30.4518, -97.8647),  # Cedar Park
            '78727': (30.4072, -97.7431),  # North Austin
            '78728': (30.4072, -97.8147),  # North Austin
            '78729': (30.4518, -97.8647),  # Cedar Park
            '78730': (30.3849, -97.8881),  # West Lake Hills
            '78731': (30.3349, -97.7881),  # North Austin
            '78732': (30.3849, -97.9381),  # West Lake Hills
            '78733': (30.3349, -97.9381),  # West Austin
            '78734': (30.2849, -97.9881),  # West Lake Hills
            '78735': (30.2322, -97.8881),  # Southwest Austin
            '78736': (30.2849, -97.9381),  # West Austin
            '78737': (30.1822, -97.9381),  # Southwest Austin
            '78738': (30.3349, -98.0381),  # West Austin
            '78739': (30.2322, -97.9881),  # Southwest Austin
            '78741': (30.2322, -97.7197),  # South Austin
            '78742': (30.2072, -97.6789),  # Southeast Austin
            '78744': (30.1822, -97.7197),  # South Austin
            '78745': (30.2072, -97.7697),  # South Austin
            '78746': (30.2849, -97.8381),  # West Austin
            '78747': (30.1572, -97.8147),  # Southwest Austin
            '78748': (30.1322, -97.7697),  # South Austin
            '78749': (30.1822, -97.8147),  # Southwest Austin
            '78750': (30.4072, -97.8647),  # North Austin
            '78751': (30.3072, -97.7431),  # North Austin
            '78752': (30.3349, -97.7031),  # North Austin
            '78753': (30.3849, -97.6789),  # North Austin
            '78754': (30.3849, -97.6289),  # Northeast Austin
            '78756': (30.3349, -97.7431),  # North Austin
            '78757': (30.3849, -97.7431),  # North Austin
            '78758': (30.4518, -97.7031),  # North Austin
            '78759': (30.4072, -97.7431),  # North Austin
            # Austin metro area ZIP codes (786xx range)
            '78613': (30.5057, -97.8203),  # Cedar Park
            '78617': (30.1328, -97.5547),  # Del Valle
            '78620': (30.6379, -97.6781),  # Hutto
            '78621': (30.2849, -97.6289),  # East Austin
            '78626': (30.6657, -97.6781),  # Georgetown
            '78628': (30.6657, -97.6781),  # Georgetown
            '78634': (30.6379, -97.6781),  # Hutto
            '78641': (30.5879, -97.6781),  # Leander
            '78645': (30.1328, -97.5547),  # Manchaca
            '78652': (30.5879, -97.6781),  # Leander
            '78653': (30.5879, -97.6781),  # Leander/Cedar Park area
            '78660': (30.5879, -97.6781),  # Pflugerville
            '78664': (30.4379, -97.6203),  # Round Rock
            '78665': (30.5379, -97.6781),  # Round Rock
            '78681': (30.5379, -97.6781),  # Round Rock
            '78682': (30.5879, -97.6781),  # Round Rock
            '78683': (30.5879, -97.6781),  # Austin/Round Rock
            # Additional Austin area ZIP codes (788xx range)
            '78801': (30.2672, -97.7431),  # Austin (general)
            '78802': (30.2672, -97.7431),  # Austin (general)
        }
    
    def get_austin_zip_codes(self) -> List[str]:
        """Get list of Austin ZIP codes from SAFMR data"""
        try:
            safmr_path = ROOT_DIR / "data" / "processed" / "austin_safmr.csv"
            if safmr_path.exists():
                safmr_df = pd.read_csv(safmr_path)
                return safmr_df['ZIP Code'].astype(str).unique().tolist()
            else:
                logger.warning("SAFMR data not found, using default Austin ZIP codes")
                return [
                    "78701", "78702", "78703", "78704", "78705", "78712", "78717", 
                    "78719", "78721", "78722", "78723", "78724", "78725", "78726", 
                    "78727", "78728", "78729", "78730", "78731", "78732", "78733", 
                    "78734", "78735", "78736", "78737", "78738", "78739", "78741", 
                    "78742", "78744", "78745", "78746", "78747", "78748", "78749", 
                    "78750", "78751", "78752", "78753", "78754", "78756", "78757", 
                    "78758", "78759"
                ]
        except Exception as e:
            logger.error(f"Error getting ZIP codes: {e}")
            return []

    def scrape_rentals_by_zip(self, zip_code: str, max_rent: int = 5000, max_pages: int = 9) -> List[Dict]:
        """Scrape rental listings from Redfin for a specific ZIP code"""
        listings = []
        logger.info(f"Starting Redfin scraping for ZIP {zip_code} with max rent ${max_rent}")
        
        try:
            for page in range(1, max_pages + 1):
                logger.info(f"Scraping ZIP {zip_code}, page {page}...")
                
                page_listings = self._scrape_page_by_zip(zip_code, max_rent, page)
                
                if not page_listings:
                    logger.info(f"No more listings found for ZIP {zip_code} on page {page}")
                    break
                
                listings.extend(page_listings)
                logger.info(f"Found {len(page_listings)} listings on page {page}. ZIP {zip_code} total: {len(listings)}")
                
                # Be respectful with rate limiting
                delay = random.uniform(2, 6)
                logger.info(f"Waiting {delay:.1f} seconds before next page...")
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Error during scraping ZIP {zip_code}: {e}")
            
        logger.info(f"Completed Redfin scraping for ZIP {zip_code}. Found {len(listings)} listings")
        return listings

    def _scrape_page_by_zip(self, zip_code: str, max_rent: int, page: int) -> List[Dict]:
        """Scrape a single page of rental listings for a specific ZIP code"""
        listings = []
        
        try:
            search_url = self._build_search_url_by_zip(zip_code, max_rent, page)
            logger.info(f"Scraping ZIP {zip_code}, page {page}: {search_url}")
            
            response = self.session.get(search_url, timeout=15)
            
            if response.status_code == 403:
                logger.error(f"Redfin blocked request (403) for ZIP {zip_code}, page {page}")
                return []
            elif response.status_code != 200:
                logger.error(f"Failed to fetch ZIP {zip_code}, page {page}: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Use the working selector for Redfin rental cards
            listing_cards = soup.select('.MapHomeCard')
            
            if not listing_cards:
                logger.warning(f"No MapHomeCard elements found for ZIP {zip_code}, page {page}")
                # Try alternative selectors
                listing_cards = soup.select('.HomeCard')
                if listing_cards:
                    logger.info(f"Found {len(listing_cards)} HomeCard elements instead")
            
            logger.info(f"Found {len(listing_cards)} property cards for ZIP {zip_code}, page {page}")
            
            for card in listing_cards:
                try:
                    listing = self._extract_listing_data(card)
                    if listing and listing.get('rent'):
                        # Filter by max_rent and ensure it's in the target ZIP code
                        if listing['rent'] <= max_rent and listing.get('zip_code') == zip_code:
                            listings.append(listing)
                except Exception as e:
                    logger.debug(f"Error parsing listing card: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping ZIP {zip_code}, page {page}: {e}")
            
        return listings

    def _build_search_url_by_zip(self, zip_code: str, max_rent: int = 5000, page: int = 1) -> str:
        """Build Redfin rental search URL for specific ZIP code"""
        base_url = f"https://www.redfin.com/zipcode/{zip_code}/rentals/filter"
        
        # Convert max_rent to Redfin format (e.g., 1500 -> "1.5k", 5000 -> "5k")
        if max_rent >= 1000:
            max_price_str = f"{max_rent/1000:.1f}k".replace('.0k', 'k')
        else:
            max_price_str = str(max_rent)
        
        # Build URL with filters
        url = f"{base_url}/max-price={max_price_str}/page-{page}"
        
        return url

    def _find_listing_cards(self, soup: BeautifulSoup) -> List:
        """Find listing cards in the page"""
        selectors = [
            'div.HomeCard',
            'div[data-testid="property-card"]',
            'div.SearchResultsItem',
            'div.MapHomeCard'
        ]
        
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.debug(f"Found {len(cards)} cards with selector: {selector}")
                return cards
                
        logger.warning("No listing cards found with any selector")
        return []

    def _extract_listing_data(self, card) -> Optional[Dict]:
        """Extract listing data from a Redfin property card using improved patterns"""
        try:
            listing = {
                "id": None,
                "address": None,
                "zip_code": None,
                "latitude": None,
                "longitude": None,
                "bedrooms": None,
                "bathrooms": None,
                "rent": None,
                "sqft": None,
                "available_date": None,
                "listing_url": None,
                "image_urls": [],
                "description": None,
                "amenities": [],
                "property_type": None,
                "pet_policy": None,
                "parking": None,
                "source": "redfin",
                "scraped_at": datetime.datetime.now().isoformat()
            }
            
            # Get card text for pattern matching
            card_text = card.get_text(separator=' ', strip=True)
            
            # Extract price - Redfin shows prices in various formats
            price_patterns = [
                r'\$(\d{1,4}(?:,\d{3})*)\+?/mo',  # $960+/mo
                r'\$(\d{1,4}(?:,\d{3})*)',        # $960, $1,100
                r'(\d+)\s*bd:\s*\$(\d{1,4}(?:,\d{3})*)',  # 1 bd: $1,100
                r'Studio:\s*\$(\d{1,4}(?:,\d{3})*)'       # Studio: $1,050
            ]
            
            rent = None
            for pattern in price_patterns:
                matches = re.findall(pattern, card_text)
                if matches:
                    if isinstance(matches[0], tuple):
                        # For patterns with multiple groups, take the price group
                        price_str = matches[0][-1]  # Last group is usually the price
                    else:
                        price_str = matches[0]
                    
                    try:
                        rent = int(price_str.replace(',', ''))
                        # Filter out unreasonably high prices (likely sale prices)
                        if rent > 10000:
                            continue
                        break
                    except ValueError:
                        continue
            
            if not rent:
                # Try to find any dollar amount that looks reasonable for rent
                all_prices = re.findall(r'\$(\d{1,4}(?:,\d{3})*)', card_text)
                for price_str in all_prices:
                    try:
                        price = int(price_str.replace(',', ''))
                        if 300 <= price <= 5000:  # Reasonable rent range
                            rent = price
                            break
                    except ValueError:
                        continue
            
            if not rent:
                return None
            
            listing['rent'] = rent
            
            # Extract bedrooms and bathrooms
            bed_bath_patterns = [
                r'(\d+)\s+bed[s]?\s*[,•·]?\s*(\d+(?:\.\d+)?)\s+bath[s]?',
                r'(\d+)\s+bd[s]?\s*[,•·]?\s*(\d+(?:\.\d+)?)\s+ba[s]?',
                r'Studio',  # Special case for studio apartments
                r'(\d+)\s*bd:\s*\$\d+',  # "1 bd: $1100" format
            ]
            
            bedrooms = None
            bathrooms = None
            
            # Check for studio first
            if re.search(r'Studio', card_text, re.IGNORECASE):
                bedrooms = 0
                bathrooms = 1.0
            else:
                for pattern in bed_bath_patterns[:2]:  # Skip the bd: pattern for bed/bath extraction
                    match = re.search(pattern, card_text, re.IGNORECASE)
                    if match and len(match.groups()) >= 2:
                        bedrooms = int(match.group(1))
                        bathrooms = float(match.group(2))
                        break
                
                # If no bed/bath found, try to extract from "1 bd:" format
                if bedrooms is None:
                    bd_match = re.search(r'(\d+)\s*bd:', card_text, re.IGNORECASE)
                    if bd_match:
                        bedrooms = int(bd_match.group(1))
                        bathrooms = 1.0  # Default assumption
            
            listing['bedrooms'] = bedrooms
            listing['bathrooms'] = bathrooms
            
            # Extract square footage
            sqft_patterns = [
                r'(\d{1,4}(?:,\d{3})*)\s+sq\.?\s*ft',
                r'(\d{3,4})\s*-\s*(\d{3,4})\s+sq\s*ft',  # Range like "400-545 sq ft"
                r'(\d{1,4}(?:,\d{3})*)\s+sqft'
            ]
            
            square_feet = None
            for pattern in sqft_patterns:
                match = re.search(pattern, card_text, re.IGNORECASE)
                if match:
                    if len(match.groups()) > 1:  # Range format
                        # Take the larger number from range
                        square_feet = int(match.group(2))
                    else:
                        square_feet = int(match.group(1).replace(',', ''))
                    break
            
            listing['sqft'] = square_feet
            
            # Extract address and property URL
            links = card.find_all('a', href=True)
            property_links = [link for link in links if '/home/' in link.get('href', '') or '/TX/' in link.get('href', '') or '/apartment/' in link.get('href', '')]
            
            if property_links:
                address = property_links[0].get_text().strip()
                href = property_links[0]['href']
                
                # Build full URL
                if href.startswith('http'):
                    property_url = href
                else:
                    property_url = f"https://www.redfin.com{href}"
                
                listing['address'] = address
                listing['listing_url'] = property_url
                
                # Generate unique ID from URL
                listing['id'] = f"redfin-{abs(hash(property_url))}"
                
                # Extract ZIP code from address - look specifically for Austin ZIP codes (787xx)
                # Extract ZIP code by splitting address and working backwards
                # ZIP code is typically the last 5-digit number in the address
                address_parts = address.split()
                zip_code_found = None
                
                # Work backwards through address parts to find 5-digit ZIP code
                for part in reversed(address_parts):
                    # Remove any trailing punctuation and check if it's a 5-digit number
                    clean_part = re.sub(r'[^\d]', '', part)
                    if len(clean_part) == 5 and clean_part.isdigit():
                        # Check if it's an Austin area ZIP code (787xx or nearby areas)
                        if clean_part.startswith(('787', '786', '788')):
                            zip_code_found = clean_part
                            break
                
                if zip_code_found:
                    listing['zip_code'] = zip_code_found
                else:
                    # Skip listings without valid Austin area ZIP codes
                    logger.warning(f"No valid Austin ZIP code found in address: {address}")
                    return None
                
                # Add coordinates using ZIP code centroid
                if listing['zip_code'] in self.zip_centroids:
                    lat, lon = self.zip_centroids[listing['zip_code']]
                    listing['latitude'] = lat
                    listing['longitude'] = lon
                else:
                    logger.warning(f"No coordinates available for ZIP code: {listing['zip_code']}")
                    # Use default Austin coordinates as fallback
                    listing['latitude'] = 30.2672  # Austin city center
                    listing['longitude'] = -97.7431
            
            # Extract image URL
            images = card.find_all('img')
            if images:
                for img in images[:3]:  # Limit to 3 images
                    img_src = img.get('src', '') or img.get('data-src', '')
                    if img_src and 'redfin.com' in img_src:
                        listing['image_urls'].append(img_src)
            
            # Extract property type from card text
            property_type = self._extract_property_type(card_text)
            listing['property_type'] = property_type
            
            # Extract pet policy from card text
            pet_policy = self._extract_pet_policy(card_text)
            listing['pet_policy'] = pet_policy
            
            # Extract parking information from card text
            parking = self._extract_parking_info(card_text)
            listing['parking'] = parking
            
            # Set default values for missing fields
            listing.setdefault('address', 'Austin, TX')
            listing.setdefault('listing_url', '')
            # Don't set default ZIP code - we want to skip invalid entries
            if not listing.get('zip_code'):
                logger.warning(f"Skipping listing without valid ZIP code: {listing.get('address', 'Unknown')}")
                return None
            listing.setdefault('available_date', datetime.datetime.now().strftime("%Y-%m-%d"))
            
            # Validate required fields
            if listing['rent'] and listing['address']:
                return listing
            else:
                logger.debug(f"Missing required fields for listing: rent={listing['rent']}, address={listing['address']}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting listing data: {e}")
            return None
    
    def _extract_property_type(self, card_text: str) -> Optional[str]:
        """Extract property type from card text based on test findings"""
        card_text_lower = card_text.lower()
        
        # Property type patterns found in testing
        property_types = {
            'studio': ['studio'],
            'apartment': ['apartment'],
            'house': ['house', 'single family'],
            'condo': ['condo', 'condominium'],
            'townhouse': ['townhouse', 'townhome'],
            'duplex': ['duplex']
        }
        
        for prop_type, keywords in property_types.items():
            for keyword in keywords:
                if keyword in card_text_lower:
                    return prop_type.title()
        
        # Default inference based on bedroom count and context
        if 'studio' in card_text_lower:
            return 'Studio'
        elif any(word in card_text_lower for word in ['bd:', 'bed', 'bedroom']):
            # If it has bedrooms and no specific type, likely apartment
            return 'Apartment'
        
        return None
    
    def _extract_pet_policy(self, card_text: str) -> Optional[str]:
        """Extract pet policy from card text based on test findings"""
        card_text_lower = card_text.lower()
        
        # Pet policy patterns found in testing
        if 'pets welcome' in card_text_lower:
            return 'Pets Welcome'
        elif 'dogs welcome' in card_text_lower:
            return 'Dogs Welcome'
        elif 'cats welcome' in card_text_lower:
            return 'Cats Welcome'
        elif 'pet friendly' in card_text_lower:
            return 'Pet Friendly'
        elif 'no pets' in card_text_lower:
            return 'No Pets'
        elif any(word in card_text_lower for word in ['pet deposit', 'pet fee']):
            return 'Pets Allowed (Fee Required)'
        
        return None
    
    def _extract_parking_info(self, card_text: str) -> Optional[str]:
        """Extract parking information from card text based on test findings"""
        card_text_lower = card_text.lower()
        
        # Parking patterns found in testing - check specific patterns first
        garage_match = re.search(r'(\d+)[-\s]*car\s*garage', card_text_lower)
        if garage_match:
            return f"{garage_match.group(1)}-Car Garage"
        elif 'covered parking' in card_text_lower:
            return 'Covered Parking'
        elif 'assigned parking' in card_text_lower:
            return 'Assigned Parking'
        elif 'street parking' in card_text_lower:
            return 'Street Parking'
        elif 'garage' in card_text_lower:
            return 'Garage'
        elif 'parking' in card_text_lower:
            return 'Parking Available'
        elif 'carport' in card_text_lower:
            return 'Carport'
        
        return None

    def _get_processed_zip_codes(self, csv_file: str) -> Set[str]:
        """Get set of ZIP codes that have already been processed"""
        csv_path = PROCESSED_DATA_DIR / csv_file
        processed_zips = set()
        
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                if 'zip_code' in df.columns:
                    processed_zips = set(df['zip_code'].astype(str).unique())
                    logger.info(f"Found {len(processed_zips)} already processed ZIP codes")
            except Exception as e:
                logger.warning(f"Error reading existing CSV: {e}")
        
        return processed_zips
    
    def _append_listings_to_csv(self, listings: List[Dict], csv_file: str) -> None:
        """Append listings to CSV file incrementally with duplicate prevention"""
        if not listings:
            return
            
        csv_path = PROCESSED_DATA_DIR / csv_file
        new_df = pd.DataFrame(listings)
        
        # Convert list columns to strings for CSV
        for col in new_df.columns:
            if new_df[col].dtype == 'object':
                new_df[col] = new_df[col].apply(lambda x: str(x) if isinstance(x, list) else x)
        
        if csv_path.exists():
            # Load existing data to check for duplicates
            existing_df = pd.read_csv(csv_path)
            existing_ids = set(existing_df['id'].astype(str)) if 'id' in existing_df.columns else set()
            
            # Filter out listings that already exist
            new_listings = [listing for listing in listings if str(listing['id']) not in existing_ids]
            
            if new_listings:
                filtered_df = pd.DataFrame(new_listings)
                # Convert list columns to strings for CSV
                for col in filtered_df.columns:
                    if filtered_df[col].dtype == 'object':
                        filtered_df[col] = filtered_df[col].apply(lambda x: str(x) if isinstance(x, list) else x)
                
                filtered_df.to_csv(csv_path, mode='a', header=False, index=False)
                logger.info(f"Appended {len(new_listings)} new listings to {csv_path} (skipped {len(listings) - len(new_listings)} duplicates)")
            else:
                logger.info(f"All {len(listings)} listings already exist in {csv_path} - skipping")
        else:
            # First time - create new file
            new_df.to_csv(csv_path, index=False)
            logger.info(f"Created {csv_path} with {len(listings)} listings")
    
    def _remove_duplicates_from_csv(self, csv_file: str):
        """Remove duplicate listings from CSV file based on address and rent"""
        # Handle both full paths and just filenames
        if '/' in csv_file or '\\' in csv_file:
            csv_path = Path(csv_file)  # Full path provided
        else:
            csv_path = PROCESSED_DATA_DIR / csv_file  # Just filename provided
        
        if not csv_path.exists():
            logger.warning(f"CSV file {csv_path} does not exist, skipping duplicate removal")
            return
        
        try:
            # Load the CSV file
            df = pd.read_csv(csv_path)
            original_count = len(df)
            
            if original_count == 0:
                logger.info("CSV file is empty, no duplicates to remove")
                return
            
            # Remove duplicates based on key fields
            # Use address and rent as primary deduplication keys
            # Also consider listing_url if available
            dedup_columns = ['address', 'rent']
            
            # Add listing_url to deduplication if it exists and has values
            if 'listing_url' in df.columns and df['listing_url'].notna().any():
                dedup_columns.append('listing_url')
            
            # Remove duplicates, keeping the first occurrence
            df_deduplicated = df.drop_duplicates(subset=dedup_columns, keep='first')
            
            duplicates_removed = original_count - len(df_deduplicated)
            
            if duplicates_removed > 0:
                # Save the deduplicated data back to CSV
                df_deduplicated.to_csv(csv_path, index=False)
                logger.info(f"Removed {duplicates_removed} duplicate listings from {csv_file}")
                logger.info(f"Final count: {len(df_deduplicated)} unique listings")
            else:
                logger.info(f"No duplicates found in {csv_file}")
                
        except Exception as e:
            logger.error(f"Error removing duplicates from {csv_file}: {e}")
    
    def scrape_all_rentals(self, max_rent: int = 5000, max_pages: int = 9, resume: bool = True) -> None:
        """Scrape all Austin rental listings by ZIP code and save incrementally"""
        csv_file = "redfin_listings_complete.csv"
        # REMOVED: json_file - no more JSON output, CSV only
        
        logger.info(f"Starting Redfin scraping by ZIP code with max rent ${max_rent}, max {max_pages} pages per ZIP")
        
        # Get all Austin ZIP codes
        all_zip_codes = self.get_austin_zip_codes()
        logger.info(f"Found {len(all_zip_codes)} Austin ZIP codes to process")
        
        # Get already processed ZIP codes if resuming
        processed_zips = set()
        if resume:
            processed_zips = self._get_processed_zip_codes(csv_file)
        
        # Filter out already processed ZIP codes
        remaining_zips = [zip_code for zip_code in all_zip_codes if zip_code not in processed_zips]
        logger.info(f"Processing {len(remaining_zips)} remaining ZIP codes (skipping {len(processed_zips)} already done)")
        
        all_listings = []
        total_processed = 0
        
        for i, zip_code in enumerate(remaining_zips, 1):
            logger.info(f"Processing ZIP {zip_code} ({i}/{len(remaining_zips)})...")
            
            try:
                zip_listings = self.scrape_rentals_by_zip(zip_code, max_rent, max_pages)
                
                if zip_listings:
                    # Append to CSV immediately
                    self._append_listings_to_csv(zip_listings, csv_file)
                    all_listings.extend(zip_listings)
                    total_processed += len(zip_listings)
                    logger.info(f"ZIP {zip_code}: Found {len(zip_listings)} listings. Total so far: {total_processed}")
                else:
                    logger.info(f"ZIP {zip_code}: No listings found")
                
                # Longer delay between ZIP codes to be respectful
                if i < len(remaining_zips):  # Don't wait after the last ZIP
                    delay = random.uniform(5, 10)
                    logger.info(f"Waiting {delay:.1f} seconds before next ZIP code...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error processing ZIP {zip_code}: {e}")
                continue
        
        # Completed scraping - CSV file already saved incrementally
        if all_listings:
            logger.info(f"Completed Redfin scraping. Total new listings: {len(all_listings)}")
            
            # Remove duplicates from the final CSV file
            logger.info("Removing duplicates from final CSV file...")
            self._remove_duplicates_from_csv(csv_file)
            
            # Log statistics
            avg_rent = sum(l['rent'] for l in all_listings if l['rent']) / len(all_listings)
            zip_codes = set(l['zip_code'] for l in all_listings if l['zip_code'])
            logger.info(f"Average rent: ${avg_rent:.0f}")
            logger.info(f"ZIP codes with listings: {len(zip_codes)}")
        else:
            logger.warning("No new listings found to save")

    # REMOVED: _save_listings method - no more JSON output, CSV only

    def _save_listings_csv(self, listings: List[Dict], filename: str) -> None:
        """Save listings to CSV file"""
        if not listings:
            return
            
        df = pd.DataFrame(listings)
        
        # Convert list columns to strings for CSV
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: str(x) if isinstance(x, list) else x)
        
        output_path = PROCESSED_DATA_DIR / filename
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(listings)} listings to {output_path}")

def main():
    """Main function for command line execution"""
    scraper = RedfinScraper()
    scraper.scrape_all_rentals(max_rent=5000, max_pages=9, resume=True)

if __name__ == "__main__":
    main()
