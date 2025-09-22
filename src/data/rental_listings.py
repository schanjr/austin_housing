import os
import json
import pandas as pd
import requests
from pathlib import Path
import datetime
import time
# Removed random import - no more fake data generation
from bs4 import BeautifulSoup
import re
from urllib.parse import urlencode, quote_plus

# Define paths
ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_rental_listings(zip_code, max_rent=1500, bedrooms=None, force_refresh=False, source=None):
    """
    Get real rental listings for a specific ZIP code from Zillow and Redfin.
    
    Args:
        zip_code (str): ZIP code to get listings for
        max_rent (int): Maximum monthly rent
        bedrooms (list): List of bedroom preferences (e.g., ["1", "2"])
        force_refresh (bool): If True, fetch new data even if existing data is recent
        source (str): Filter by source ('zillow', 'redfin', or None for all)
        
    Returns:
        pandas.DataFrame: Real rental listings data with actual URLs
    """
    # Define the path for cached listings
    listings_path = PROCESSED_DATA_DIR / f"real_rental_listings_{zip_code}_{max_rent}.csv"
    
    # Check if we have recent data (less than 4 hours old for real data)
    if listings_path.exists() and not force_refresh:
        modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(listings_path))
        current_time = datetime.datetime.now()
        
        # If data is less than 4 hours old, use cached data
        if (current_time - modified_time).total_seconds() < 14400:  # 4 hours
            print(f"Using cached real rental listings for ZIP code {zip_code}")
            try:
                listings_df = pd.read_csv(listings_path)
                
                # Apply filters
                if max_rent:
                    listings_df = listings_df[listings_df['rent'] <= max_rent]
                
                if bedrooms:
                    bedroom_values = []
                    for b in bedrooms:
                        if b == "Studio":
                            bedroom_values.append(0)
                        elif "Bedroom" in b:
                            bedroom_values.append(int(b.split()[0]))
                    if bedroom_values:
                        listings_df = listings_df[listings_df['bedrooms'].isin(bedroom_values)]
                
                # Filter by source if specified
                if source and 'source' in listings_df.columns:
                    listings_df = listings_df[listings_df['source'].str.lower() == source.lower()]
                
                return listings_df
            except Exception as e:
                print(f"Error reading cached data: {e}")
    
    print(f"Fetching real rental listings for ZIP code {zip_code}")
    
    # Fetch real data from both sources
    all_listings = []
    
    if not source or source.lower() == 'zillow':
        zillow_listings = fetch_zillow_rentals(zip_code, max_rent, bedrooms)
        all_listings.extend(zillow_listings)
    
    if not source or source.lower() == 'redfin':
        redfin_listings = fetch_redfin_rentals(zip_code, max_rent, bedrooms)
        all_listings.extend(redfin_listings)
    
    # Convert to DataFrame
    if all_listings:
        listings_df = pd.DataFrame(all_listings)
        
        # Save to CSV
        listings_df.to_csv(listings_path, index=False)
        print(f"Saved {len(listings_df)} real rental listings for ZIP code {zip_code}")
        
        # Filter by source if specified
        if source:
            listings_df = listings_df[listings_df['source'].str.lower() == source.lower()]
        
        return listings_df
    else:
        print(f"No rental listings found for ZIP code {zip_code}")
        return pd.DataFrame()

def fetch_zillow_rentals(zip_code, max_rent=1500, bedrooms=None):
    """
    Fetch real rental listings from Zillow for a specific ZIP code.
    """
    listings = []
    try:
        # Construct Zillow search URL for rentals
        base_url = "https://www.zillow.com/homes/for_rent/"
        params = {
            'searchQueryState': json.dumps({
                "pagination": {},
                "usersSearchTerm": zip_code,
                "mapBounds": {},
                "regionSelection": [{"regionId": zip_code, "regionType": 7}],
                "isMapVisible": True,
                "filterState": {
                    "fr": {"value": True},  # For rent
                    "mp": {"max": max_rent} if max_rent else {},
                    "beds": {"min": min([int(b.split()[0]) for b in bedrooms if "Bedroom" in b])} if bedrooms else {}
                },
                "isListVisible": True
            })
        }
        
        search_url = f"{base_url}?{urlencode(params)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for rental listings in the page
            listing_cards = soup.find_all('div', {'data-testid': 'property-card'}) or soup.find_all('article', class_=re.compile('list-card'))
            
            for card in listing_cards[:10]:  # Limit to 10 listings
                try:
                    # Extract listing details
                    price_elem = card.find('span', {'data-testid': 'property-card-price'}) or card.find('div', class_=re.compile('price'))
                    address_elem = card.find('address', {'data-testid': 'property-card-addr'}) or card.find('address')
                    beds_elem = card.find('span', {'data-testid': 'property-card-beds'}) or card.find('span', text=re.compile(r'\d+\s*bd'))
                    baths_elem = card.find('span', {'data-testid': 'property-card-baths'}) or card.find('span', text=re.compile(r'\d+\s*ba'))
                    sqft_elem = card.find('span', {'data-testid': 'property-card-sqft'}) or card.find('span', text=re.compile(r'\d+\s*sqft'))
                    link_elem = card.find('a', href=True)
                    
                    if price_elem and address_elem and link_elem:
                        # Parse price
                        price_text = price_elem.get_text(strip=True)
                        rent_match = re.search(r'\$?([\d,]+)', price_text.replace(',', ''))
                        rent = int(rent_match.group(1)) if rent_match else 0
                        
                        # Skip if over max rent
                        if max_rent and rent > max_rent:
                            continue
                        
                        # Parse bedrooms
                        beds_text = beds_elem.get_text(strip=True) if beds_elem else "1"
                        beds_match = re.search(r'(\d+)', beds_text)
                        bedrooms_count = int(beds_match.group(1)) if beds_match else 1
                        
                        # Parse bathrooms
                        baths_text = baths_elem.get_text(strip=True) if baths_elem else "1"
                        baths_match = re.search(r'(\d+(?:\.\d+)?)', baths_text)
                        bathrooms_count = float(baths_match.group(1)) if baths_match else 1.0
                        
                        # Parse square footage
                        sqft_text = sqft_elem.get_text(strip=True) if sqft_elem else "800"
                        sqft_match = re.search(r'([\d,]+)', sqft_text.replace(',', ''))
                        sqft = int(sqft_match.group(1)) if sqft_match else 800
                        
                        # Get full URL
                        listing_url = link_elem['href']
                        if listing_url.startswith('/'):
                            listing_url = f"https://www.zillow.com{listing_url}"
                        
                        listing = {
                            "id": f"zillow-{zip_code}-{len(listings)}",
                            "address": address_elem.get_text(strip=True),
                            "zip_code": zip_code,
                            "bedrooms": bedrooms_count,
                            "bathrooms": bathrooms_count,
                            "rent": rent,
                            "sqft": sqft,
                            "available_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                            "listing_url": listing_url,
                            "source": "zillow"
                        }
                        
                        listings.append(listing)
                        
                except Exception as e:
                    print(f"Error parsing Zillow listing: {e}")
                    continue
                    
        print(f"Found {len(listings)} Zillow rentals for ZIP {zip_code}")
        
    except Exception as e:
        print(f"Error fetching Zillow rentals for ZIP {zip_code}: {e}")
    
    return listings

def fetch_redfin_rentals(zip_code, max_rent=1500, bedrooms=None):
    """
    Fetch real rental listings from Redfin for a specific ZIP code.
    """
    listings = []
    try:
        # Construct Redfin search URL for rentals
        base_url = f"https://www.redfin.com/zipcode/{zip_code}/filter/property-type=house+condo+townhouse,include=forsale+forrent"
        
        if max_rent:
            base_url += f",max-price={max_rent}"
        
        if bedrooms:
            min_beds = min([int(b.split()[0]) for b in bedrooms if "Bedroom" in b])
            base_url += f",min-beds={min_beds}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(base_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for rental listings
            listing_cards = soup.find_all('div', class_=re.compile('HomeCard')) or soup.find_all('div', {'data-testid': 'property-card'})
            
            for card in listing_cards[:8]:  # Limit to 8 listings
                try:
                    # Extract listing details
                    price_elem = card.find('span', class_=re.compile('price')) or card.find('div', class_=re.compile('price'))
                    address_elem = card.find('div', class_=re.compile('address')) or card.find('span', class_=re.compile('address'))
                    beds_elem = card.find('span', text=re.compile(r'\d+\s*bed'))
                    baths_elem = card.find('span', text=re.compile(r'\d+\s*bath'))
                    sqft_elem = card.find('span', text=re.compile(r'\d+\s*sq'))
                    link_elem = card.find('a', href=True)
                    
                    if price_elem and address_elem and link_elem:
                        # Parse price
                        price_text = price_elem.get_text(strip=True)
                        rent_match = re.search(r'\$?([\d,]+)', price_text.replace(',', ''))
                        rent = int(rent_match.group(1)) if rent_match else 0
                        
                        # Skip if over max rent
                        if max_rent and rent > max_rent:
                            continue
                        
                        # Parse bedrooms
                        beds_text = beds_elem.get_text(strip=True) if beds_elem else "1"
                        beds_match = re.search(r'(\d+)', beds_text)
                        bedrooms_count = int(beds_match.group(1)) if beds_match else 1
                        
                        # Parse bathrooms
                        baths_text = baths_elem.get_text(strip=True) if baths_elem else "1"
                        baths_match = re.search(r'(\d+(?:\.\d+)?)', baths_text)
                        bathrooms_count = float(baths_match.group(1)) if baths_match else 1.0
                        
                        # Parse square footage
                        sqft_text = sqft_elem.get_text(strip=True) if sqft_elem else "750"
                        sqft_match = re.search(r'([\d,]+)', sqft_text.replace(',', ''))
                        sqft = int(sqft_match.group(1)) if sqft_match else 750
                        
                        # Get full URL
                        listing_url = link_elem['href']
                        if listing_url.startswith('/'):
                            listing_url = f"https://www.redfin.com{listing_url}"
                        
                        listing = {
                            "id": f"redfin-{zip_code}-{len(listings)}",
                            "address": address_elem.get_text(strip=True),
                            "zip_code": zip_code,
                            "bedrooms": bedrooms_count,
                            "bathrooms": bathrooms_count,
                            "rent": rent,
                            "sqft": sqft,
                            "available_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                            "listing_url": listing_url,
                            "source": "redfin"
                        }
                        
                        listings.append(listing)
                        
                except Exception as e:
                    print(f"Error parsing Redfin listing: {e}")
                    continue
                    
        print(f"Found {len(listings)} Redfin rentals for ZIP {zip_code}")
        
    except Exception as e:
        print(f"Error fetching Redfin rentals for ZIP {zip_code}: {e}")
    
    return listings

# REMOVED: generate_sample_listings function - no more fake data generation

if __name__ == "__main__":
    # Test the function with real data only
    test_zip = "78701"
    listings_df = get_rental_listings(test_zip, max_rent=1800)
    print(f"Found {len(listings_df)} real listings for ZIP code {test_zip}")
    print(listings_df.head())
