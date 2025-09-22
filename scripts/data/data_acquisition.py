"""
Data acquisition module for Austin housing analysis.
"""
import os
import json
import pandas as pd
import geopandas as gpd
import requests
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
RAW_DATA_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"

RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_safmr_data(file_path=None):
    if file_path is None:
        file_path = RAW_DATA_DIR / "fy2025_safmrs_revised.xlsx"
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SAFMR file not found at {file_path}")
    
    df = pd.read_excel(file_path, sheet_name='SAFMRs')
    austin_df = df[df['HUD Fair Market Rent Area Name'] == "Austin-Round Rock, TX MSA"].copy()
    
    output_path = PROCESSED_DATA_DIR / "austin_safmr.csv"
    austin_df.to_csv(output_path, index=False)
    
    print(f"Processed SAFMR data saved to {output_path}")
    return austin_df

def get_crime_data(year=2024, save=True):
    base_url = "https://data.austintexas.gov/resource/fdj4-gpfu.json"
    query = f"$query=SELECT council_district,count(incident_report_number) AS incidents " \
            f"WHERE occ_date >= '{year}-01-01' AND occ_date <= '{year}-12-31' " \
            f"GROUP BY council_district"
    
    url = f"{base_url}?{query}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        crime_df = pd.DataFrame(data)
        
        if 'incidents' in crime_df.columns:
            crime_df['incidents'] = pd.to_numeric(crime_df['incidents'])
        
        if save:
            output_path = PROCESSED_DATA_DIR / f"austin_crime_{year}.csv"
            crime_df.to_csv(output_path, index=False)
            print(f"Crime data saved to {output_path}")
        
        return crime_df
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching crime data: {e}")
        return None

def get_council_districts(save=True):
    url = "https://data.austintexas.gov/resource/w3v2-cj58.geojson"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        if save:
            raw_path = RAW_DATA_DIR / "council_districts.geojson"
            with open(raw_path, 'w') as f:
                json.dump(response.json(), f)
        
        gdf = gpd.read_file(url)
        
        if save:
            output_path = PROCESSED_DATA_DIR / "council_districts.gpkg"
            gdf.to_file(output_path, driver="GPKG")
            print(f"Council district boundaries saved to {output_path}")
        
        return gdf
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching council district boundaries: {e}")
        return None

def get_affordable_housing(save=True):
    url = "https://data.austintexas.gov/api/views/ifzc-3xz8/rows.json?accessType=DOWNLOAD"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if save:
            raw_path = RAW_DATA_DIR / "affordable_housing_raw.json"
            with open(raw_path, 'w') as f:
                json.dump(data, f)
        
        columns = data.get('meta', {}).get('view', {}).get('columns', [])
        column_names = [col.get('name') for col in columns]
        
        rows = data.get('data', [])
        housing_df = pd.DataFrame(rows, columns=column_names)
        
        if save:
            output_path = PROCESSED_DATA_DIR / "affordable_housing.csv"
            housing_df.to_csv(output_path, index=False)
            print(f"Affordable housing data saved to {output_path}")
        
        return housing_df
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching affordable housing data: {e}")
        return None

def geocode_zip_code(zip_code):
    url = f"https://api.zippopotam.us/us/{zip_code}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        lat = float(data.get('places', [{}])[0].get('latitude', 0))
        lng = float(data.get('places', [{}])[0].get('longitude', 0))
        
        return (lat, lng)
    
    except (requests.exceptions.RequestException, ValueError, IndexError) as e:
        print(f"Error geocoding ZIP code {zip_code}: {e}")
        return None

def geocode_zip_codes(zip_codes, save=True):
    results = []
    
    for zip_code in zip_codes:
        coords = geocode_zip_code(zip_code)
        if coords:
            results.append({
                'zip_code': zip_code,
                'latitude': coords[0],
                'longitude': coords[1]
            })
    
    geocoded_df = pd.DataFrame(results)
    
    if save and not geocoded_df.empty:
        output_path = PROCESSED_DATA_DIR / "geocoded_zips.csv"
        geocoded_df.to_csv(output_path, index=False)
        print(f"Geocoded ZIP codes saved to {output_path}")
    
    return geocoded_df

if __name__ == "__main__":
    print("Loading SAFMR data...")
    safmr_df = load_safmr_data()
    
    print("\nFetching crime data...")
    crime_df = get_crime_data()
    
    print("\nFetching council district boundaries...")
    districts_gdf = get_council_districts()
    
    print("\nFetching affordable housing data...")
    housing_df = get_affordable_housing()
    
    if safmr_df is not None:
        zip_codes = safmr_df['ZIP Code'].unique().tolist()
        print(f"\nGeocoding {len(zip_codes)} ZIP codes...")
        geocoded_df = geocode_zip_codes(zip_codes)
