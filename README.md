# Austin Housing Analysis

A real-data-driven analysis system to find the best places to rent in Austin, TX under a $1500 monthly budget, based on multiple quality-of-life parameters.

## 🚨 NO FAKE DATA POLICY

**This project operates under a strict NO FAKE DATA POLICY:**
- ✅ **Real data only** - All sources are legitimate (Redfin, Austin Open Data, crime databases)
- ✅ **Single CSV output** - No duplicate JSON/CSV pairs to avoid redundancy
- ❌ **No synthetic generation** - No random data creation anywhere in the codebase
- ❌ **No fake listings** - All property data comes from real rental websites

**Policy Status**: ✅ **FULLY IMPLEMENTED** (as of 2025-09-21)

## Project Overview

This project aims to balance affordability, safety, convenience, livability, and risk factors using data-driven analysis to determine the optimal rental locations in Austin, TX.

### Core Evaluation Parameters

1. **Affordability**
   - Rental listings under $1500
   - Bedrooms and square footage

2. **Safety**
   - Crime rates by neighborhood or census tract

3. **Commute & Accessibility**
   - Distance/time to downtown
   - Proximity to grocery stores, hospitals, schools, public transit

4. **Neighborhood Quality**
   - Walkability scores
   - School ratings
   - Community amenities (parks, libraries, gyms)

5. **Environmental Risk**
   - Flood zones (FEMA maps)
   - Natural disaster risk (hail, wildfire, storm surge, etc.)

## Real Data Sources

- **Real Rental Listings**: Live property data scraped from Redfin.com (15,666+ properties)
- **Precise Geocoding**: OpenStreetMap Nominatim API for exact property coordinates
- **Austin Crime Data**: Real crime statistics from City of Austin Open Data portal
- **HUD SAFMR Data**: Official 2025 fair market rents by ZIP code
- **Council District Boundaries**: Geographic boundaries for spatial analysis
- **Master Dataset**: Single authoritative CSV with all merged real data sources

### Rental Data Scraping Status

🟢 **Redfin Scraper**: ✅ WORKING - Actively scrapes real rental listings
🔴 **Zillow Scraper**: ❌ BLOCKED - Site returns 403 errors, currently disabled

**Note**: The project currently uses Redfin as the primary source for real rental data. Zillow scraper is disabled due to anti-bot measures.

## Project Structure

```
austin_housing/
├── app/                    # Streamlit dashboard application
│   ├── dashboard.py        # Main optimized dashboard (production)
│   ├── clean_map.py        # Clean map interface components
│   ├── property_scoring.py # Real data scoring algorithms
│   └── property_display.py # UI components and visualization
├── data/                   # Data directory (real data only)
│   ├── raw/                # Raw data files (SAFMR, crime, boundaries)
│   └── processed/          # Processed CSV files (single files only)
│       ├── master_properties.csv      # Single authoritative dataset
│       ├── redfin_listings_complete.csv # Real scraped listings
│       ├── geocoded_listings_progress.csv # Precise coordinates
│       └── austin_crime_2024.csv      # Real crime statistics
├── src/                    # Source code modules
│   ├── data/               # Data acquisition and processing
│   ├── scrapers/           # Real data scrapers (Redfin active)
│   ├── geocoding/          # Address-to-coordinate conversion
│   └── analysis/           # Data processing and analysis
├── generate_master_data.py # Master dataset generation script
├── run_dashboard.py        # Dashboard launcher script
├── pyproject.toml          # Poetry dependencies and commands
├── poetry.lock             # Poetry lock file
├── README.md               # Main project documentation (this file)
└── data.md                 # Comprehensive data sources and scraping guide
```

## Getting Started

### Prerequisites

- Python 3.12 or higher
- Poetry 2.0 or higher

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/austin_housing.git
   cd austin_housing
   ```

2. Install dependencies with Poetry:
   ```
   poetry install
   ```

### Quick Start (Real Data Pipeline)

#### 1. Collect Real Rental Data

```bash
# Scrape live rental listings from Redfin
poetry run scrape-redfin
```

#### 2. Geocode Property Addresses

```bash
# Convert addresses to precise coordinates
poetry run geocode-all
```

#### 3. Generate Master Dataset

```bash
# Merge all real data sources into single CSV
poetry run generate-data
```

#### 4. Launch Dashboard

```bash
# Run dashboard with real data
poetry run dashboard
```

**Dashboard URL**: http://localhost:8501

### Alternative Commands

```bash
# Run full pipeline (scrape + geocode + generate + dashboard)
poetry run python run_dashboard.py

# Individual data collection scripts
python src/data/austin_opendata_acquisition.py  # Crime data
python src/data/walkscore_acquisition.py        # Walkability (optional)
```

## Features (Real Data Only)

- **15,666+ Real Properties**: Live rental listings scraped from Redfin.com
- **Precise Property Locations**: Individual property pins with exact geocoded coordinates
- **Real Crime Data**: Actual Austin crime statistics for safety scoring
- **Single Master Dataset**: Authoritative CSV file with all merged real data
- **Performance Optimized**: Fast loading dashboard with pre-calculated scores
- **No Synthetic Data**: 100% real data sources, zero fake or random generation
- **CSV-Only Output**: Single file per dataset, no redundant JSON duplicates
- **Resume Capability**: Scraping and geocoding can resume from interruptions

### Dashboard Features

#### 🗺️ Interactive Property Map
- **Individual Property Pins**: Exact locations using geocoded coordinates (not ZIP centroids)
- **Color-coded Markers**: Green (8-10), Orange (5-8), Red (0-5) overall scores
- **Detailed Popups**: Score breakdowns, property details, direct listing links
- **ZIP Code Boundaries**: Optional overlay with selection capabilities
- **Zoom-responsive**: Adapts to user interaction with stable rendering

#### 🏠 Property Analysis
- **Sortable Property Table**: Filter by rent, scores, ZIP codes with instant sorting
- **Advanced Filtering**: Multiple criteria simultaneously (rent range, bedrooms, scores)
- **Score Transparency**: Detailed breakdown of how each property is scored
- **Export Functionality**: Download filtered results for offline analysis
- **Real-Time Updates**: Refresh data after running scrapers

#### 🏘️ Neighborhood Analysis
- **ZIP Code Summaries**: Average scores and property counts by area
- **Comparative Analysis**: Best/worst neighborhoods with recommendations
- **Score Distributions**: Visual insights into neighborhood quality patterns
- **Market Context**: Statistical summaries and key metrics

#### 📊 Transparent Scoring System
- **Weighted Algorithm**: Affordability (30%), Safety (25%), Accessibility (20%), Neighborhood (15%), Environment (10%)
- **0-10 Scale**: Normalized scores for easy comparison across all properties
- **Score Explanations**: Each score includes detailed calculation methodology
- **Real-Time Calculation**: Scores computed from live data sources

#### 🔧 Performance & Monitoring
- **Single Master Dataset**: Fast loading from authoritative CSV (15,666+ properties)
- **Pre-calculated Scores**: Instant dashboard loading with no runtime computation
- **Data Status Monitoring**: Timestamps show when data was last collected
- **Memory Optimized**: Handles large datasets efficiently

## 🏗️ Architecture & Optimization

### Streamlined Data Pipeline
The project uses a unified, optimized architecture that eliminates redundancy and ensures data authenticity:

```
Raw Data Sources → Master Dataset → Dashboard
     ↓                   ↓             ↓
- Redfin listings   master_properties.csv  Clean UI
- Geocoded coords   (single source)        Fast loading
- Crime data                               Stable maps
- SAFMR data
```

### Key Architectural Improvements
- **Data Consolidation**: Eliminated 16+ duplicate/redundant data files
- **Single Source of Truth**: Master dataset approach with `master_properties.csv`
- **Performance Optimization**: Pre-calculated scores, stable map rendering
- **Real Data Only**: 100% elimination of synthetic/fake data generation
- **CSV-Only Policy**: Single file per dataset, no JSON duplicates

### Technical Stack
- **Python 3.12** with Poetry 2.0 for dependency management
- **Streamlit** for interactive dashboard interface
- **Folium** for interactive maps with precise property locations
- **Pandas/GeoPandas** for data processing and spatial analysis
- **OpenStreetMap Nominatim** for free geocoding services
- **Real Data Sources**: Redfin, Austin Open Data, HUD SAFMR

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- City of Austin Open Data Portal
- U.S. Department of Housing and Urban Development (HUD)
- Zippopotam.us API
