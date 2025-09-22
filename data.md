# Austin Housing Analysis: Data Sources and Methodology

This document provides a comprehensive overview of the data sources used in the Austin rental analysis project, how they are processed, and how they contribute to our livability calculations.

## 🚨 NO FAKE DATA POLICY

**The Austin Housing Dashboard project operates under a strict NO FAKE DATA POLICY:**

- ✅ **Real data only** - All sources must be legitimate (Redfin, Austin Open Data, crime databases, etc.)
- ✅ **Single CSV output** - No duplicate JSON/CSV pairs to avoid redundancy
- ❌ **No synthetic generation** - No random data creation anywhere in the codebase
- ❌ **No fake listings** - All property data comes from real rental websites

**Policy Status**: ✅ **FULLY IMPLEMENTED** (as of 2025-09-21)

## Current Data Pipeline Architecture

### Master Dataset Generation
The project uses a **single master dataset** approach:
- **Input**: Multiple real data sources (scraped listings, geocoded coordinates, crime data, SAFMR)
- **Processing**: `generate_master_data.py` merges all sources with calculated scores
- **Output**: Single `master_properties.csv` file (15,666+ real properties)
- **Dashboard**: Loads exclusively from master dataset for optimal performance

### Data File Structure (CSV Only)
```
data/processed/
├── master_properties.csv          # Single authoritative dataset
├── properties_with_scores.csv     # Real scored properties
├── geocoded_listings_progress.csv # Real geocoded coordinates
├── austin_crime_2024.csv         # Real crime data
├── austin_safmr.csv              # Real SAFMR data
└── redfin_listings_complete.csv  # Real scraped listings
```

## Data Sources Currently Used

### 1. Real Rental Listings (Primary Source)

**What it is:** Live rental property listings scraped from legitimate real estate websites.

**Sources:** 
- Redfin.com (active)
- Zillow.com (disabled due to blocking)

**Location:** `data/processed/redfin_listings_complete.csv`

**How to collect:** `poetry run scrape-redfin`

**What it contains:**
- Real addresses and ZIP codes
- Actual rental prices and availability
- Property details (bedrooms, bathrooms, sqft)
- Listing URLs and images
- Scraped timestamps

**How it's used:**
- Primary source for all property listings
- Base data for scoring and analysis
- Geocoded for precise map locations

### 2. Geocoded Property Coordinates

**What it is:** Precise latitude/longitude coordinates for individual property addresses.

**Source:** OpenStreetMap Nominatim API (free geocoding service)

**Location:** `data/processed/geocoded_listings_progress.csv`

**How to generate:** `poetry run geocode-all`

**What it contains:**
- Exact property coordinates (not ZIP centroids)
- Geocoding success/failure status
- Address matching information

**How it's used:**
- Individual property pins on interactive maps
- Eliminates coordinate stacking issues
- Enables precise property location display

### 3. HUD Small Area Fair Market Rents (SAFMR) FY 2025

**What it is:** The Small Area Fair Market Rents (SAFMR) dataset from the U.S. Department of Housing and Urban Development (HUD) provides estimated fair market rents at the ZIP code level.

**Location:** `data/raw/fy2025_safmrs_revised.xlsx`

**How to access:** Load with pandas using `pd.read_excel('data/raw/fy2025_safmrs_revised.xlsx', sheet_name='SAFMRs')`

**What it contains:**
- ZIP codes for the Austin-Round Rock metropolitan area
- Fair market rent estimates for different unit sizes (studio, 1-bedroom, 2-bedroom, etc.)
- Geographic information about each ZIP code area

**How it's used in our analysis:**
- Primary data source for affordability calculations
- Identifies ZIP codes with rental options under $1,500 monthly
- Contributes 30% to the overall livability score

### 4. Austin Crime Data (Real Crime Statistics)

**What it is:** Real crime incident data from the City of Austin's police department.

**Source:** City of Austin Open Data portal API

**Location:** `data/processed/austin_crime_2024.csv`

**How to collect:** `python src/data/austin_opendata_acquisition.py`

**What it contains:**
- Real crime incidents by location and type
- Geographic coordinates for crime mapping
- Temporal crime patterns and trends

**How it's used:**
- Safety scoring for individual properties and ZIP codes
- Contributes 25% to overall property livability score
- Enables crime density mapping and analysis

### 3. Council District Boundaries

**What it is:** Geographic boundary data for Austin City Council districts, used to map ZIP codes to their respective council districts.

**Source:** City of Austin Open Data portal (`w3v2-cj58` dataset)

**How to access:** Download GeoJSON from `https://data.austintexas.gov/resource/w3v2-cj58.geojson`

**What it contains:**
- Geographic boundaries (MultiPolygon features)
- District names and numbers
- Administrative metadata

**How it's used in our analysis:**
- Enables spatial joining of ZIP codes to council districts
- Allows crime data (by district) to be associated with ZIP codes
- Critical for integrating different geographic data sources

### 4. Affordable Housing Inventory

**What it is:** A dataset of housing projects that have received subsidies or participated in City of Austin developer incentive programs.

**Source:** City of Austin Open Data portal (`ifzc-3xz8` dataset)

**How to access:** Download JSON from `https://data.austintexas.gov/api/views/ifzc-3xz8/rows.json?accessType=DOWNLOAD`

**What it contains:**
- Property details (name, address, ZIP code)
- Geographic coordinates (latitude/longitude)
- Unit counts by bedroom size
- Available amenities

**How it's used in our analysis:**
- Supplementary data for affordable housing options
- Provides context for ZIP code affordability analysis
- Helps identify areas with subsidized housing options

### 5. ZIP Code Geocoding Data

**What it is:** Geographic coordinate data (latitude/longitude) for ZIP code centroids, used to place ZIP codes on maps and perform spatial analysis.

**Source:** Zippopotam.us API

**How to access:** API endpoint `https://api.zippopotam.us/us/{ZIP}`

**What it contains:**
- ZIP code identifiers
- Latitude and longitude coordinates
- Place names associated with ZIP codes

**How it's used in our analysis:**
- Enables mapping of ZIP codes on interactive maps
- Allows spatial joining with council district boundaries
- Facilitates visualization of livability scores by location

## Real Data Collection and Scraping

### Available Scraper Commands (Real Data Only)

```bash
# Scrape real Redfin listings (ACTIVE)
poetry run scrape-redfin

# Note: Zillow scraper disabled due to 403 blocking
# poetry run scrape-zillow  # ❌ DISABLED

# Geocode property addresses to precise coordinates  
poetry run geocode-all

# Generate master dataset with all real data sources
poetry run generate-data

# Run dashboard with real data
poetry run dashboard
```

### Scraper Features and Architecture

#### Real Data Collection Process
1. **ZIP Code Discovery**: Scrapers automatically discover Austin ZIP codes from SAFMR data
2. **Systematic Scraping**: Each ZIP code is scraped with rate limiting and error handling
3. **Progress Tracking**: Partial results saved every 10 ZIP codes to prevent data loss
4. **Resume Capability**: Can resume from interruptions without losing progress

#### Data Output (CSV Only)
Scrapers generate **single CSV files only** in `data/processed/`:
- `redfin_listings_complete.csv` - Real Redfin rental listings (15,666+ properties)
- `geocoded_listings_progress.csv` - Precise property coordinates
- `master_properties.csv` - Merged dataset with all real data sources

**No JSON Files**: All JSON output removed to enforce single-file policy and eliminate redundancy.

#### Scraper Status
- ✅ **Redfin Scraper**: Active - collecting real rental listings with ZIP-code based scraping
- ✅ **Geocoding**: Active - converting addresses to precise coordinates using OpenStreetMap
- ✅ **Master Dataset**: Active - single authoritative CSV with all merged real data
- ❌ **Zillow Scraper**: Disabled due to anti-bot blocking (403 errors)

#### Error Handling and Monitoring
- **Rate Limiting**: Built-in delays between requests (2-6 seconds)
- **Retry Logic**: Automatic retries for failed requests
- **Graceful Degradation**: Continues scraping other ZIP codes if one fails
- **Progress Preservation**: Incremental saves prevent data loss
- **Comprehensive Logging**: INFO, DEBUG, ERROR, and WARNING levels

### 2. Data Processing Steps

1. **Real Rental Data Scraping:**
   - Scrapes live listings from Redfin.com
   - Extracts real addresses, prices, property details
   - Saves to single CSV file (no JSON duplicates)
   - Rate-limited and resumable scraping

2. **Property Geocoding:**
   - Converts real addresses to precise coordinates
   - Uses OpenStreetMap Nominatim API (free)
   - Multi-threaded processing for performance
   - Incremental progress saving with resume capability

3. **Master Dataset Generation:**
   - Merges all real data sources into single CSV
   - Calculates property scores using real data
   - Prioritizes CSV data over any legacy JSON
   - Creates authoritative dataset for dashboard

4. **Dashboard Data Loading:**
   - Loads exclusively from master CSV dataset
   - No synthetic data generation anywhere
   - Real-time filtering and analysis
   - Performance optimized for 15,000+ properties

### 2. Data Processing and Integration

1. **Spatial Joining:**
   - Convert geocoded ZIP codes to a GeoDataFrame with point geometries
   - Perform a spatial join with council district boundaries
   - Result: Each ZIP code is associated with its containing council district

2. **Crime Score Calculation:**
   - Normalize crime incidents by council district
   - Calculate a safety score where higher values indicate safer areas
   - Formula: `crime_score = 1 - ((incidents - min_incidents) / (max_incidents - min_incidents))`

3. **Affordability Filtering:**
   - For each ZIP code, check which unit sizes (studio, 1BR, 2BR, etc.) have rents under $1,500
   - Create boolean indicators for affordability of each unit type
   - Calculate an overall affordability score based on the proportion of affordable unit types

### 3. Livability Index Calculation

The livability index is a weighted composite score calculated as follows:

1. **Base Components:**
   - Affordability Score: Proportion of unit types under $1,500 (30% weight)
   - Safety Score: Normalized crime rate by district (25% weight)
   - Accessibility: Currently not implemented (20% weight placeholder)
   - Neighborhood Quality: Currently not implemented (15% weight placeholder)
   - Environmental Risk: Currently not implemented (10% weight placeholder)

2. **Formula:**
   ```
   livability_score = (0.3 * affordability_score + 0.25 * safety_score) * 100
   ```

3. **Interpretation:**
   - Higher scores indicate more livable areas based on our criteria
   - Maximum possible score is 100
   - Current implementation includes only affordability and safety components

## Data Sources Not Yet Implemented

### 1. Walkability and Transit Scores

**What it would provide:** Metrics for pedestrian-friendliness and public transit access by location.

**Potential source:** WalkScore API

**How it would enhance analysis:** Would contribute to the accessibility and neighborhood quality components of the livability index.

### 2. School Ratings

**What it would provide:** Educational quality metrics by school district or attendance zone.

**Potential source:** GreatSchools API

**How it would enhance analysis:** Would contribute to the neighborhood quality component of the livability index, especially important for families with children.

### 3. Environmental Risk Data

**What it would provide:** Information about flood zones, wildfire risk, and other environmental hazards.

**Potential sources:** FEMA Flood Map Service Center, NOAA hazard datasets

**How it would enhance analysis:** Would populate the currently empty environmental risk component of the livability index.

### 4. Amenities and Points of Interest

**What it would provide:** Proximity to grocery stores, hospitals, parks, and other amenities.

**Potential sources:** Google Places API, OpenStreetMap

**How it would enhance analysis:** Would contribute to the accessibility and neighborhood quality components of the livability index.

## Data Limitations and Considerations

1. **Temporal Relevance:** Crime data is from 2024, while SAFMR data is for FY 2025. This temporal mismatch should be considered when interpreting results.

2. **Spatial Aggregation:** Crime data is aggregated at the council district level, which is coarser than ZIP codes. This means all ZIP codes within the same district receive the same safety score.

3. **Missing Components:** The current livability index only implements two of the five planned components (affordability and safety). The remaining components (accessibility, neighborhood quality, and environmental risk) are placeholders with weights but no actual data.

4. **Data Access Issues:** Some APIs (particularly on data.austintexas.gov) may return HTTP 403 errors when accessed programmatically. Using API tokens or browser-based downloads may be necessary in some cases.