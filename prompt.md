## Project Goal

Determine the best places to rent in Austin, TX under a monthly budget of $1500 or less, based on multiple quality-of-life parameters.

We want to balance affordability, safety, convenience, livability, and risk factors using data-driven analysis.

## Dependencies
Check all md files on the same level of directory of this file. Read, understand, and adhere to what is described in each of the md file. Follow the instructions provided. 

## Core Evaluation Parameters

The following features will shape our analysis. Data availability will dictate feasibility.
1. Affordability
  - Rental listings under $1500
  - Bedrooms and square footage 
2. Safety
  - Crime rates by neighborhood or census tract
3. Commute & Accessibility
  - Distance/time to downtown
  - Proximity to grocery stores, hospitals, schools, public transit
4. Neighborhood Quality
  - Walkability scores
  - School ratings
  - Community amenities (parks, libraries, gyms)
5. Environmental Risk
  - Flood zones (FEMA maps)
  - Natural disaster risk (hail, wildfire, storm surge, etc.)
6. Market Trends (optional)
  - Rental price history by ZIP code
  - Vacancy rates

## Data Sources (Target)

Here’s where we can fetch or request the necessary datasets:

Housing / Rentals
- Zillow API or scrape (rent price, bedrooms, sq ft, neighborhood trends)
- Rent.com / Apartments.com (manual or scrape)
- Craigslist (messy, but feasible if cleaned)

Crime & Safety
- City of Austin Open Data Portal (https://data.austintexas.gov) – crime incidents by location
- FBI Crime Data Explorer (broader statistics)

Commute & Accessibility
- Google Maps API / OpenStreetMap – travel time to downtown, transit accessibility
- WalkScore API (walkability, transit score, bike score)
- USDA Food Access Research Atlas – food deserts data

Environmental Risk
- FEMA Flood Map Service Center (flood zones)
- NOAA hazard datasets (storm, wildfire risk)
- City of Austin environmental datasets

Neighborhood Quality
- GreatSchools API for school ratings
- Parks/amenities data from City of Austin Open Data Portal
- Census Bureau / American Community Survey for demographics, income, etc.

## Suggested Libraries
- Data Wrangling: pandas, geopandas
- Visualization: matplotlib, plotly, folium (for maps)
- APIs & Requests: requests, googlemaps, walkscore
- Streamlit: for building the interactive dashboard

## Project Setup
- Use Poetry 2 for dependency management
- Adhere to the code style rules outlined in "House Rules & Code Style".
- Organize repository into:
  - data/ → raw & processed datasets
  - notebooks/ → exploratory analysis
  - src/ → data pipelines & analysis scripts
  - app/ → Streamlit dashboard
  - PROMPT.md → project brain

## Expert Strategy

As the “AI Real Estate Analyst,” the path to answering “Where is the best place to rent in Austin?” involves:
1. Data Acquisition  
  Collect raw datasets for rentals, crime, commute, amenities, and environmental risks.
2. Feature Engineering  
  Normalize each dataset to the neighborhood or census tract level. Build features such as:
  - Crime incidents per 1,000 residents
  - Commute time by car/transit to downtown
  - Flood risk indicator
  - Rent per square foot
  - Walkability/transit score
3. Scoring Framework  
  Create a composite livability index using weighted parameters. Example:
  - 30% affordability
  - 25% safety
  - 20% commute & accessibility
  - 15% neighborhood quality
  - 10% environmental risk
  - (Weights adjustable in the dashboard)
4. Analysis  
  Rank neighborhoods based on this composite score under the rent cap.
5. Visualization  
  - Interactive map of Austin neighborhoods (colored by livability index)
  - Filter by rent budget, number of bedrooms, commute tolerance, etc.

## Future Extensions
- Incorporate real-time rental listings via APIs or scraping
- Forecast rent trends using time series models
- Include user personalization (e.g., weigh school quality higher if user has children)
- Compare Austin against other Texas cities for context
