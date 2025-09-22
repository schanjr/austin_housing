"""
Main script to run the entire Austin housing analysis pipeline.
This script orchestrates the data acquisition, processing, and analysis steps.
"""
import os
import sys
import argparse
from pathlib import Path

# Add the project root to the path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from src.data.data_acquisition import (
    load_safmr_data, 
    get_crime_data, 
    get_council_districts, 
    get_affordable_housing,
    geocode_zip_codes
)
from src.analysis.data_processing import (
    merge_zip_with_district,
    create_livability_index
)

def fix_data_types():
    """Fix data type issues in processed data files."""
    processed_dir = ROOT_DIR / "data" / "processed"
    print("\n=== Fixing Data Types ===")
    
    crime_path = processed_dir / "austin_crime_2024.csv"
    if crime_path.exists():
        import pandas as pd
        crime_df = pd.read_csv(crime_path)
        crime_df = crime_df.dropna(subset=['council_district'])
        crime_df['council_district'] = crime_df['council_district'].astype(str)
        crime_df.to_csv(crime_path, index=False)
        print(f"Fixed council_district data type in {crime_path}")
    
    zip_district_path = processed_dir / "zip_district.csv"
    if zip_district_path.exists():
        import pandas as pd
        zip_district_df = pd.read_csv(zip_district_path)
        zip_district_df = zip_district_df.dropna(subset=['council_district'])
        zip_district_df['council_district'] = zip_district_df['council_district'].astype(str)
        zip_district_df.to_csv(zip_district_path, index=False)
        print(f"Fixed council_district data type in {zip_district_path}")
    
    print("Data type fixes completed.")

def run_data_acquisition():
    """Run all data acquisition steps."""
    print("\n=== Running Data Acquisition ===")
    
    print("\nLoading SAFMR data...")
    safmr_df = load_safmr_data()
    
    print("\nFetching crime data...")
    crime_df = get_crime_data()
    
    print("\nFetching council district boundaries...")
    districts_gdf = get_council_districts()
    
    print("\nFetching affordable housing data...")
    housing_df = get_affordable_housing()
    
    # Extract ZIP codes from SAFMR data and geocode them
    if safmr_df is not None:
        zip_codes = safmr_df['ZIP Code'].unique().tolist()
        print(f"\nGeocoding {len(zip_codes)} ZIP codes...")
        geocoded_df = geocode_zip_codes(zip_codes)
    
    print("\nData acquisition completed!")

def run_data_processing():
    """Run all data processing steps."""
    print("\n=== Running Data Processing ===")
    
    # Import here to avoid circular imports
    from src.analysis.data_processing import load_processed_data
    
    print("\nLoading processed data...")
    data = load_processed_data()
    
    if not data:
        print("No processed data found. Please run data acquisition first.")
        return
    
    # Fix data types before processing
    fix_data_types()
    
    if 'geocoded_zips' in data and 'districts' in data:
        print("\nMerging ZIP codes with council districts...")
        data['zip_district'] = merge_zip_with_district(data['geocoded_zips'], data['districts'])
        
        # Save the merged data
        if data['zip_district'] is not None:
            output_path = ROOT_DIR / "data" / "processed" / "zip_district.csv"
            data['zip_district'].to_csv(output_path, index=False)
            print(f"ZIP code to district mapping saved to {output_path}")
    
    # Create livability index
    print("\nCreating livability index...")
    livability_df = create_livability_index(data)
    
    if livability_df is not None:
        # Save results
        output_path = ROOT_DIR / "data" / "processed" / "livability_index.csv"
        livability_df.to_csv(output_path, index=False)
        print(f"Livability index saved to {output_path}")
        
        # Display top 10 most livable ZIP codes
        if 'livability_score' in livability_df.columns:
            top_zips = livability_df.sort_values('livability_score', ascending=False).head(10)
            print("\nTop 10 most livable ZIP codes:")
            print(top_zips[['ZIP Code', 'livability_score']])
    
    print("\nData processing completed!")

def run_dashboard():
    """Run the Streamlit dashboard."""
    print("\n=== Running Dashboard ===")
    dashboard_path = ROOT_DIR / "app" / "dashboard.py"
    
    if not dashboard_path.exists():
        print(f"Dashboard file not found at {dashboard_path}")
        return
    
    print(f"Starting Streamlit dashboard from {dashboard_path}")
    print("To view the dashboard, open your browser and go to http://localhost:8501")
    print("Press Ctrl+C to stop the dashboard")
    
    # Use Poetry to run Streamlit
    python_path = sys.executable
    streamlit_cmd = f"{python_path} -m streamlit run {dashboard_path}"
    os.system(streamlit_cmd)

def main():
    """Main function to run the entire pipeline."""
    parser = argparse.ArgumentParser(description='Austin Housing Analysis Pipeline')
    parser.add_argument('--action', type=str, default='acquisition',
                        choices=['acquisition', 'processing', 'dashboard', 'full', 'fix-data'],
                        help='Action to perform: acquisition, processing, dashboard, full pipeline, or fix-data')
    
    # Check if running in interactive mode or with arguments
    if len(sys.argv) > 1:
        args = parser.parse_args()
        action = args.action
    else:
        # Default to acquisition if no arguments provided
        action = 'acquisition'
    
    print("=== Austin Housing Analysis Pipeline ===")
    print(f"Running action: {action}")
    
    if action == 'acquisition':
        run_data_acquisition()
    elif action == 'processing':
        run_data_processing()
    elif action == 'dashboard':
        run_dashboard()
    elif action == 'full':
        run_data_acquisition()
        run_data_processing()
        run_dashboard()
    elif action == 'fix-data':
        fix_data_types()
    else:
        print(f"Unknown action: {action}")

if __name__ == "__main__":
    main()
