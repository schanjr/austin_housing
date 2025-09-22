"""
Data processing module for Austin housing analysis.
"""
import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"

def load_processed_data():
    data = {}
    
    safmr_path = PROCESSED_DATA_DIR / "austin_safmr.csv"
    if safmr_path.exists():
        data['safmr'] = pd.read_csv(safmr_path)
    
    crime_path = PROCESSED_DATA_DIR / "austin_crime_2024.csv"
    if crime_path.exists():
        data['crime'] = pd.read_csv(crime_path)
    
    districts_path = PROCESSED_DATA_DIR / "council_districts.gpkg"
    if districts_path.exists():
        data['districts'] = gpd.read_file(districts_path)
    
    housing_path = PROCESSED_DATA_DIR / "affordable_housing.csv"
    if housing_path.exists():
        data['housing'] = pd.read_csv(housing_path)
    
    geocoded_path = PROCESSED_DATA_DIR / "geocoded_zips.csv"
    if geocoded_path.exists():
        data['geocoded_zips'] = pd.read_csv(geocoded_path)
    
    return data

def fix_data_types():
    print("Fixing data type issues in processed data files...")
    
    crime_path = PROCESSED_DATA_DIR / "austin_crime_2024.csv"
    if crime_path.exists():
        crime_df = pd.read_csv(crime_path)
        crime_df = crime_df.dropna(subset=['council_district'])
        crime_df['council_district'] = crime_df['council_district'].astype(str)
        crime_df.to_csv(crime_path, index=False)
        print(f"Fixed council_district data type in {crime_path}")
    
    zip_district_path = PROCESSED_DATA_DIR / "zip_district.csv"
    if zip_district_path.exists():
        zip_district_df = pd.read_csv(zip_district_path)
        zip_district_df = zip_district_df.dropna(subset=['council_district'])
        zip_district_df['council_district'] = zip_district_df['council_district'].astype(str)
        zip_district_df.to_csv(zip_district_path, index=False)
        print(f"Fixed council_district data type in {zip_district_path}")
    
    print("Data type fixes completed.")

def filter_affordable_rentals(safmr_df, max_rent=1500, bedroom_preferences=None):
    df = safmr_df.copy()
    
    # Map bedroom preferences to FMR column names
    bedroom_mapping = {
        "Studio": "FMR_0",
        "1 Bedroom": "FMR_1",
        "2 Bedrooms": "FMR_2",
        "3 Bedrooms": "FMR_3",
        "4 Bedrooms": "FMR_4"
    }
    
    # Get all bedroom columns if no preferences specified
    if not bedroom_preferences:
        bedroom_cols = [col for col in df.columns if col.startswith('FMR_')]
    else:
        bedroom_cols = [bedroom_mapping[pref] for pref in bedroom_preferences if pref in bedroom_mapping]
        # If no valid preferences, use all columns
        if not bedroom_cols:
            bedroom_cols = [col for col in df.columns if col.startswith('FMR_')]
    
    # Ensure all columns exist in the dataframe
    bedroom_cols = [col for col in bedroom_cols if col in df.columns]
    
    # Create masks for each bedroom type that's under the max rent
    masks = []
    for col in bedroom_cols:
        masks.append(df[col] <= max_rent)
    
    if masks:
        # ZIP codes that have at least one unit type under the max rent
        combined_mask = masks[0]
        for mask in masks[1:]:
            combined_mask = combined_mask | mask
        
        filtered_df = df[combined_mask].copy()
        
        # Add affordability flags for each unit type
        all_bedroom_cols = [col for col in df.columns if col.startswith('FMR_')]
        for col in all_bedroom_cols:
            bedroom_type = col.split('_')[1]
            filtered_df[f'Affordable_{bedroom_type}'] = filtered_df[col] <= max_rent
        
        return filtered_df
    
    return df

def calculate_crime_score(crime_df):
    if crime_df is None or crime_df.empty:
        return None
    
    df = crime_df.copy()
    
    if 'incidents' in df.columns:
        df['incidents'] = pd.to_numeric(df['incidents'], errors='coerce')
    
    if 'incidents' in df.columns:
        max_incidents = df['incidents'].max()
        min_incidents = df['incidents'].min()
        
        if max_incidents > min_incidents:
            df['crime_score'] = 1 - ((df['incidents'] - min_incidents) / (max_incidents - min_incidents))
        else:
            df['crime_score'] = 1.0
    
    return df

def merge_zip_with_district(geocoded_zips_df, districts_gdf):
    if geocoded_zips_df is None or districts_gdf is None:
        return None
    
    gdf = gpd.GeoDataFrame(
        geocoded_zips_df, 
        geometry=gpd.points_from_xy(geocoded_zips_df.longitude, geocoded_zips_df.latitude),
        crs="EPSG:4326"
    )
    
    if districts_gdf.crs != gdf.crs:
        districts_gdf = districts_gdf.to_crs(gdf.crs)
    
    joined = gpd.sjoin(gdf, districts_gdf, how="left", predicate="within")
    
    result = joined[['zip_code', 'district_number', 'latitude', 'longitude']].copy()
    
    result = result.rename(columns={'district_number': 'council_district'})
    
    return result

def create_livability_index(data_dict, weights=None):
    if not data_dict:
        return None
    
    if weights is None:
        weights = {
            'affordability': 0.3,
            'safety': 0.25,
            'accessibility': 0.2,
            'neighborhood': 0.15,
            'environment': 0.1
        }
    
    safmr_df = data_dict.get('safmr')
    crime_df = data_dict.get('crime')
    zip_district_df = data_dict.get('zip_district')
    
    if safmr_df is None:
        return None
    
    livability_df = filter_affordable_rentals(safmr_df)
    
    # Initialize component scores
    livability_df['affordability_score'] = 0.0
    livability_df['safety_score'] = 0.5  # Default value if no crime data
    
    # Calculate affordability score
    affordable_cols = [col for col in livability_df.columns if col.startswith('Affordable_')]
    if affordable_cols:
        livability_df['affordability_score'] = livability_df[affordable_cols].sum(axis=1) / len(affordable_cols)
    
    # Calculate safety score if crime data is available
    if crime_df is not None and zip_district_df is not None:
        crime_scores = calculate_crime_score(crime_df)
        
        if crime_scores is not None:
            zip_district_df = zip_district_df.copy()
            crime_scores = crime_scores.copy()
            
            zip_district_df['council_district'] = zip_district_df['council_district'].astype(str)
            crime_scores['council_district'] = crime_scores['council_district'].astype(str)
            
            merged = pd.merge(
                zip_district_df,
                crime_scores,
                on='council_district',
                how='left'
            )
            
            livability_df = pd.merge(
                livability_df,
                merged[['zip_code', 'crime_score']],
                left_on='ZIP Code',
                right_on='zip_code',
                how='left'
            )
            
            # Set safety score from crime data
            livability_df['safety_score'] = livability_df['crime_score'].fillna(0.5)
    
    # Calculate the weighted livability score
    livability_df['livability_score'] = (
        weights['affordability'] * livability_df['affordability_score'] +
        weights['safety'] * livability_df['safety_score']
        # Future components will be added here
    )
    
    # Normalize to 0-100 scale
    livability_df['livability_score'] = livability_df['livability_score'] / (weights['affordability'] + weights['safety']) * 100
    
    return livability_df

def process_data():
    data = load_processed_data()
    
    if not data:
        print("No processed data found. Please run data acquisition first.")
        return None
    
    fix_data_types()
    
    if 'geocoded_zips' in data and 'districts' in data:
        print("Merging ZIP codes with council districts...")
        data['zip_district'] = merge_zip_with_district(data['geocoded_zips'], data['districts'])
        
        if data['zip_district'] is not None:
            output_path = PROCESSED_DATA_DIR / "zip_district.csv"
            data['zip_district'].to_csv(output_path, index=False)
            print(f"ZIP code to district mapping saved to {output_path}")
    
    print("Creating livability index...")
    livability_df = create_livability_index(data)
    
    if livability_df is not None:
        output_path = PROCESSED_DATA_DIR / "livability_index.csv"
        livability_df.to_csv(output_path, index=False)
        print(f"Livability index saved to {output_path}")
        
        if 'livability_score' in livability_df.columns:
            top_zips = livability_df.sort_values('livability_score', ascending=False).head(10)
            print("\nTop 10 most livable ZIP codes:")
            print(top_zips[['ZIP Code', 'livability_score']])
    
    return livability_df

if __name__ == "__main__":
    print("Loading processed data...")
    process_data()
