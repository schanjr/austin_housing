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
from typing import List, Dict, Optional

ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ZillowScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
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

    def scrape_zip_code(self, zip_code: str, max_rent: int = 2000, max_pages: int = 3) -> List[Dict]:
        """Scrape rental listings for a specific ZIP code"""
        listings = []
        logger.info(f"Scraping Zillow for ZIP code {zip_code}")
        
        try:
            for page in range(1, max_pages + 1):
                page_listings = self._scrape_page(zip_code, max_rent, page)
                listings.extend(page_listings)
                
                if len(page_listings) == 0:
                    logger.info(f"No more listings found for {zip_code} on page {page}")
                    break
                    
                time.sleep(random.uniform(2, 4))
                
        except Exception as e:
            logger.error(f"Error scraping ZIP code {zip_code}: {e}")
            
        logger.info(f"Found {len(listings)} listings for ZIP code {zip_code}")
        return listings

    def _scrape_page(self, zip_code: str, max_rent: int, page: int) -> List[Dict]:
        """Scrape a single page of listings"""
        listings = []
        
        try:
            # Try multiple URL approaches
            urls_to_try = [
                f"https://www.zillow.com/{zip_code}/rentals/",
                f"https://www.zillow.com/homes/{zip_code}_rb/",
                f"https://www.zillow.com/homes/for_rent/{zip_code}/"
            ]
            
            for search_url in urls_to_try:
                try:
                    logger.debug(f"Trying URL: {search_url}")
                    
                    # Add random delay to avoid rate limiting
                    time.sleep(random.uniform(1, 3))
                    
                    response = self.session.get(search_url, timeout=15)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Check if we got a valid page (not blocked)
                        if "Access to this page has been denied" in response.text:
                            logger.warning(f"Access denied for {search_url}")
                            continue
                            
                        listing_cards = self._find_listing_cards(soup)
                        
                        if listing_cards:
                            logger.info(f"Found {len(listing_cards)} potential listings on {search_url}")
                            
                            for card in listing_cards:
                                try:
                                    listing = self._extract_listing_data(card, zip_code)
                                    if listing and listing.get('rent', 0) <= max_rent:
                                        listings.append(listing)
                                except Exception as e:
                                    logger.debug(f"Error parsing listing card: {e}")
                                    continue
                            
                            break  # Success, no need to try other URLs
                        else:
                            logger.debug(f"No listing cards found on {search_url}")
                    else:
                        logger.warning(f"HTTP {response.status_code} for {search_url}")
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request failed for {search_url}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping page {page} for ZIP {zip_code}: {e}")
            
        return listings

    def _build_search_url(self, zip_code: str, max_rent: int, page: int) -> str:
        """Build Zillow search URL using simpler approach"""
        # Use simpler URL structure that's less likely to be blocked
        base_url = f"https://www.zillow.com/{zip_code}/rentals/"
        
        # Add basic filters as URL parameters
        params = {
            'searchQueryState': json.dumps({
                "pagination": {"currentPage": page},
                "usersSearchTerm": f"{zip_code}, TX",
                "mapBounds": {},
                "regionSelection": [{"regionId": zip_code, "regionType": 7}],
                "isMapVisible": False,
                "filterState": {
                    "price": {"max": max_rent},
                    "monthlyPayment": {"max": max_rent},
                    "isForRent": {"value": True}
                },
                "isListVisible": True
            })
        }
        
        return f"{base_url}?{urlencode(params)}"

    def _find_listing_cards(self, soup: BeautifulSoup) -> List:
        """Find listing cards in the page"""
        selectors = [
            # Modern Zillow selectors
            'div[data-testid="property-card"]',
            'article[data-testid="property-card"]',
            'div[data-testid="list-card"]',
            'article[data-testid="list-card"]',
            # Legacy selectors
            'div.ListItem-c11n-8-84-3__sc-10e22w8-0',
            'article.list-card',
            'div.list-card',
            # Generic selectors
            'div[class*="list-card"]',
            'article[class*="list-card"]',
            'div[class*="property-card"]',
            'article[class*="property-card"]'
        ]
        
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.debug(f"Found {len(cards)} cards with selector: {selector}")
                return cards
        
        # If no cards found, log page content for debugging
        logger.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
        logger.debug(f"Page contains 'rental' or 'rent': {'rental' in soup.get_text().lower() or 'rent' in soup.get_text().lower()}")
        logger.warning("No listing cards found with any selector")
        return []

    def _extract_listing_data(self, card, zip_code: str) -> Optional[Dict]:
        """Extract comprehensive listing data from a card"""
        try:
            listing = {
                "id": None,
                "address": None,
                "zip_code": zip_code,
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
                "source": "zillow",
                "scraped_at": datetime.datetime.now().isoformat()
            }
            
            # Extract price
            price_elem = card.select_one('[data-testid="property-card-price"], .price, [aria-label*="price"]')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                rent_match = re.search(r'\$?([\d,]+)', price_text.replace(',', ''))
                if rent_match:
                    listing['rent'] = int(rent_match.group(1))
            
            # Extract address
            address_elem = card.select_one('[data-testid="property-card-addr"], address, .list-card-addr')
            if address_elem:
                listing['address'] = address_elem.get_text(strip=True)
            
            # Extract bedrooms
            beds_elem = card.select_one('[data-testid="property-card-beds"], .beds, [aria-label*="bed"]')
            if beds_elem:
                beds_text = beds_elem.get_text(strip=True)
                beds_match = re.search(r'(\d+)', beds_text)
                if beds_match:
                    listing['bedrooms'] = int(beds_match.group(1))
                elif 'studio' in beds_text.lower():
                    listing['bedrooms'] = 0
            
            # Extract bathrooms
            baths_elem = card.select_one('[data-testid="property-card-baths"], .baths, [aria-label*="bath"]')
            if baths_elem:
                baths_text = baths_elem.get_text(strip=True)
                baths_match = re.search(r'(\d+(?:\.\d+)?)', baths_text)
                if baths_match:
                    listing['bathrooms'] = float(baths_match.group(1))
            
            # Extract square footage
            sqft_elem = card.select_one('[data-testid="property-card-sqft"], .sqft, [aria-label*="sqft"]')
            if sqft_elem:
                sqft_text = sqft_elem.get_text(strip=True)
                sqft_match = re.search(r'([\d,]+)', sqft_text.replace(',', ''))
                if sqft_match:
                    listing['sqft'] = int(sqft_match.group(1))
            
            # Extract listing URL
            link_elem = card.select_one('a[href*="/homedetails/"], a[href*="/rental/"]')
            if link_elem and link_elem.get('href'):
                href = link_elem['href']
                if href.startswith('/'):
                    listing['listing_url'] = f"https://www.zillow.com{href}"
                else:
                    listing['listing_url'] = href
                
                # Generate unique ID from URL
                listing['id'] = f"zillow-{hash(listing['listing_url'])}"
            
            # Extract images
            img_elems = card.select('img[src*="zillow"], img[data-src*="zillow"]')
            for img in img_elems[:3]:  # Limit to 3 images
                img_url = img.get('src') or img.get('data-src')
                if img_url and img_url not in listing['image_urls']:
                    listing['image_urls'].append(img_url)
            
            # Extract property type
            type_elem = card.select_one('.property-type, [data-testid="property-type"]')
            if type_elem:
                listing['property_type'] = type_elem.get_text(strip=True)
            
            # Set default available date
            listing['available_date'] = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # Validate required fields
            if listing['rent'] and listing['address'] and listing['listing_url']:
                return listing
            else:
                logger.debug(f"Missing required fields for listing: {listing}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting listing data: {e}")
            return None

    def scrape_all_zip_codes(self, max_rent: int = 2000, max_pages: int = 3) -> None:
        """Scrape all Austin ZIP codes and save to data dump"""
        zip_codes = self.get_austin_zip_codes()
        all_listings = []
        
        logger.info(f"Starting Zillow scraping for {len(zip_codes)} ZIP codes")
        
        for i, zip_code in enumerate(zip_codes, 1):
            logger.info(f"Processing ZIP code {zip_code} ({i}/{len(zip_codes)})")
            
            try:
                listings = self.scrape_zip_code(zip_code, max_rent, max_pages)
                all_listings.extend(listings)
                
                # Progress logged - no intermediate saves needed (CSV only)
                
                # Rate limiting
                time.sleep(random.uniform(3, 6))
                
            except Exception as e:
                logger.error(f"Failed to scrape ZIP code {zip_code}: {e}")
                continue
        
        # Save final results - CSV only
        self._save_listings_csv(all_listings, "zillow_listings_complete.csv")
        
        logger.info(f"Completed Zillow scraping. Total listings: {len(all_listings)}")

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
    scraper = ZillowScraper()
    scraper.scrape_all_zip_codes(max_rent=2000, max_pages=3)

if __name__ == "__main__":
    main()
