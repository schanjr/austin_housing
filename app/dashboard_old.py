"""
Streamlit dashboard for Austin housing analysis.
This dashboard visualizes the best places to rent in Austin, TX based on safety,
accessibility, and other quality-of-life parameters.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static, st_folium
import sys
from pathlib import Path
import datetime
import json
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Add the src directory to the path so we can import our modules
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from src.data.data_acquisition import load_safmr_data, get_crime_data, get_council_districts, geocode_zip_codes
from src.data.listing_loader import listing_loader
from src.data.zip_boundaries import get_austin_zip_boundaries
from src.analysis.data_processing import (
    load_processed_data, filter_affordable_rentals, 
    calculate_crime_score, merge_zip_with_district
)
from app.rental_display import show_rental_listings, display_listings
from app.heat_map_layers import add_combined_heat_map_layer

# Define paths
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"

# Session state initialization moved to main() function to prevent timing issues
if 'map_click_data' not in st.session_state:
    st.session_state.map_click_data = None

# Page configuration
st.set_page_config(
    page_title="Austin Rental Analysis",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #424242;
    }
    .info-text {
        font-size: 1rem;
        color: #616161;
    }
    .highlight {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .explanation {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .data-source {
        font-size: 0.9rem;
        color: #757575;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def load_data():
    """Load all processed data or run acquisition if needed."""
    data = load_processed_data()
    
    # Check if we have the necessary data
    if not data or 'safmr' not in data:
        st.warning("Required data not found. Running data acquisition...")
        with st.spinner("Acquiring SAFMR data..."):
            safmr_df = load_safmr_data()
            data['safmr'] = safmr_df
        
        with st.spinner("Acquiring crime data..."):
            crime_df = get_crime_data()
            data['crime'] = crime_df
        
        with st.spinner("Acquiring council district boundaries..."):
            districts_gdf = get_council_districts()
            data['districts'] = districts_gdf
        
        # Extract ZIP codes from SAFMR data and geocode them
        if 'safmr' in data and data['safmr'] is not None:
            with st.spinner("Geocoding ZIP codes..."):
                zip_codes = data['safmr']['ZIP Code'].unique().tolist()
                geocoded_df = geocode_zip_codes(zip_codes)
                data['geocoded_zips'] = geocoded_df
    
    # Merge ZIP codes with districts if needed
    if ('geocoded_zips' in data and 'districts' in data and 
        data['geocoded_zips'] is not None and data['districts'] is not None and
        'zip_district' not in data):
        with st.spinner("Merging ZIP codes with council districts..."):
            data['zip_district'] = merge_zip_with_district(data['geocoded_zips'], data['districts'])
    
    return data

def create_map(df, lat_col='latitude', lon_col='longitude', data_dict=None, 
               popup_cols=None, zoom_start=11, max_rent=1500, bedroom_preferences=None, display_params=None):
    """Create an advanced map with dynamic circles and property-level markers based on zoom."""
    
    # Center the map on Austin
    austin_coords = [30.2672, -97.7431]
    m = folium.Map(
        location=austin_coords, 
        zoom_start=zoom_start,
        tiles="OpenStreetMap"
    )
    
    # Get ZIP code boundaries for choropleth (cache with TTL to allow refresh)
    @st.cache_data(ttl=300)  # Cache for 5 minutes, then refresh
    def load_zip_boundaries_cached():
        return get_austin_zip_boundaries()
    
    # Check if we need to clear cache for fresh data
    if st.session_state.get('clear_cache', False):
        load_zip_boundaries_cached.clear()
        st.session_state.clear_cache = False
    
    zip_boundaries = load_zip_boundaries_cached()
    
    if zip_boundaries is None or df.empty:
        return m
    
    # Get listing counts from data dump files
    listing_counts = listing_loader.get_listing_counts_by_zip(
        max_rent=max_rent, 
        bedrooms=bedroom_preferences
    )
    
    # Filter to only ZIP codes with listings
    zip_data_with_listings = []
    for _, zip_row in df.iterrows():
        # Use correct column name from geocoded data (lowercase 'zip_code')
        zip_code = str(zip_row['zip_code']).replace('.0', '')
        # Convert listing_counts keys to strings for proper comparison
        listing_counts_str = {str(k): v for k, v in listing_counts.items()}
        
        if zip_code in listing_counts_str:
            counts = listing_counts_str[zip_code]
            zip_data_with_listings.append({
                'zip_code': zip_code,
                'zillow_count': counts['zillow'],
                'redfin_count': counts['redfin'],
                'total_count': counts['total'],
                'latitude': zip_row.get('latitude', 30.2672),
                'longitude': zip_row.get('longitude', -97.7431)
            })
    
    if not zip_data_with_listings:
        st.warning("No rental listings found matching your criteria in any ZIP code.")
        return m
    
    # Filter ZIP boundaries to only include areas with listings
    zip_codes_with_listings = [item['zip_code'] for item in zip_data_with_listings]
    
    # Convert boundary ZIP codes to strings for proper comparison
    zip_boundaries['ZCTA5CE20'] = zip_boundaries['ZCTA5CE20'].astype(str)
    
    filtered_boundaries = zip_boundaries[zip_boundaries['ZCTA5CE20'].isin(zip_codes_with_listings)]
    
    # Create DataFrame for choropleth
    choropleth_data = pd.DataFrame(zip_data_with_listings)
    
    # Add single combined heat map layer to prevent flickering
    if not filtered_boundaries.empty and display_params and data_dict:
        add_combined_heat_map_layer(m, filtered_boundaries, data_dict, zip_data_with_listings, display_params)
    
    # Add ZIP-level circles (visible at zoom <= 13)
    zip_circle_group = folium.FeatureGroup(name="ZIP Code Circles")
    for item in zip_data_with_listings:
        zip_code = item['zip_code']
        total_count = item['total_count']
        lat = item['latitude']
        lon = item['longitude']
        
        # Dynamic circle size based on listing count
        if total_count <= 5:
            radius = 300
        elif total_count <= 15:
            radius = 600
        elif total_count <= 30:
            radius = 900
        else:
            radius = 1200
        
        # Circle color indicates listing availability
        if total_count >= 20:
            circle_color = '#2E7D32'  # Dark green - many listings
        elif total_count >= 10:
            circle_color = '#4CAF50'  # Green - good availability
        elif total_count >= 5:
            circle_color = '#FF9800'  # Orange - some listings
        else:
            circle_color = '#F44336'  # Red - few listings
        
        # Create popup with listing counts and buttons
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; width: 250px; padding: 12px;">
            <h4 style="margin: 0 0 10px 0; color: #333; font-size: 18px;">ZIP Code: {zip_code}</h4>
            <p style="margin: 6px 0; font-size: 15px;"><strong>Rental Listings:</strong> Available below</p>
            <p style="margin: 6px 0; font-size: 14px;"><strong>Total Listings:</strong> {total_count}</p>
            <div style="margin: 15px 0 10px 0;">
                <div style="color: #666; font-style: italic; font-size: 12px; margin: 8px 0;">🚫 Zillow listings disabled</div>
                {f'''<button onclick='window.open("https://www.redfin.com/zipcode/{zip_code}/rentals/filter/max-price=1.6k,min-beds=1,min-baths=1", "_blank");' 
                        style="background-color: #a02021; color: white; padding: 12px; border: none; border-radius: 6px; cursor: pointer; margin: 4px 0; font-size: 14px; width: 100%; font-weight: bold;">
                    🏠 View {item['redfin_count']} Redfin Listings
                </button>''' if item['redfin_count'] > 0 else ''}
            </div>
        </div>
        """
        
        # Add circle marker to group
        folium.Circle(
            location=[lat, lon],
            radius=radius,
            popup=folium.Popup(popup_html, max_width=280),
            color=circle_color,
            weight=3,
            fill=True,
            fillColor=circle_color,
            fillOpacity=0.4
        ).add_to(zip_circle_group)
    
    zip_circle_group.add_to(m)
    
    # Add individual property markers (visible at zoom >= 14)
    property_marker_group = folium.FeatureGroup(name="Individual Properties")
    
    # Get individual listings with geocoded addresses
    individual_listings = get_geocoded_listings(max_rent, bedroom_preferences)
    
    for _, listing in individual_listings.iterrows():
        # Use geocoded coordinates if available, otherwise skip
        if pd.notna(listing.get('geocoded_lat')) and pd.notna(listing.get('geocoded_lon')):
            lat = listing['geocoded_lat']
            lon = listing['geocoded_lon']
        else:
            continue  # Skip listings without precise coordinates
        
        # Create property marker popup
        rent = listing.get('rent', 'N/A')
        bedrooms = listing.get('bedrooms', 'N/A')
        bathrooms = listing.get('bathrooms', 'N/A')
        sqft = listing.get('sqft', 'N/A')
        address = listing.get('address', 'N/A')
        listing_url = listing.get('listing_url', '#')
        
        property_popup = f"""
        <div style="font-family: Arial, sans-serif; width: 280px; padding: 12px;">
            <h4 style="margin: 0 0 8px 0; color: #333; font-size: 16px;">${rent}/month</h4>
            <p style="margin: 4px 0; font-size: 13px; color: #666;">{address}</p>
            <p style="margin: 4px 0; font-size: 12px;">{bedrooms} BR • {bathrooms} BA • {sqft} sqft</p>
            <a href="{listing_url}" target="_blank" style="color: #a02021; text-decoration: none; font-weight: bold;">View Details →</a>
        </div>
        """
        
        # Color code by rent level
        if rent != 'N/A':
            if rent <= 1000:
                marker_color = 'green'
            elif rent <= 1500:
                marker_color = 'orange'
            else:
                marker_color = 'red'
        else:
            marker_color = 'gray'
        
        # Add property marker
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(property_popup, max_width=300),
            icon=folium.Icon(color=marker_color, icon='home', prefix='fa')
        ).add_to(property_marker_group)
    
    property_marker_group.add_to(m)
    
    # Add JavaScript for dynamic zoom-based layer switching
    zoom_js = """
    <script>
    function updateMarkersOnZoom() {
        var map = window[Object.keys(window).find(key => key.startsWith('map_'))];
        if (map) {
            // Function to toggle layers based on zoom
            function toggleLayers() {
                var zoom = map.getZoom();
                console.log('Current zoom level:', zoom);
                
                // Get layer control groups
                var zipCircles = null;
                var propertyMarkers = null;
                
                map.eachLayer(function(layer) {
                    if (layer.options && layer.options.name === 'ZIP Code Circles') {
                        zipCircles = layer;
                    } else if (layer.options && layer.options.name === 'Individual Properties') {
                        propertyMarkers = layer;
                    }
                });
                
                // Switch visibility based on zoom level
                if (zoom >= 14) {
                    // High zoom: show individual properties, hide ZIP circles
                    if (zipCircles) map.removeLayer(zipCircles);
                    if (propertyMarkers && !map.hasLayer(propertyMarkers)) map.addLayer(propertyMarkers);
                    console.log('High zoom - showing individual properties');
                } else {
                    // Low zoom: show ZIP circles, hide individual properties
                    if (propertyMarkers) map.removeLayer(propertyMarkers);
                    if (zipCircles && !map.hasLayer(zipCircles)) map.addLayer(zipCircles);
                    console.log('Low zoom - showing ZIP circles');
                }
            }
            
            // Initial toggle
            toggleLayers();
            
            // Toggle on zoom change
            map.on('zoomend', toggleLayers);
        }
    }
    
    // Call after map is loaded
    setTimeout(updateMarkersOnZoom, 1500);
    </script>
    """
    
    m.get_root().html.add_child(folium.Element(zoom_js))
    
    return m

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_geocoded_listings(max_rent=None, bedroom_preferences=None):
    """Get listings with precomputed geocoded coordinates for individual property display"""
    # Try to load precomputed geocoded data
    geocoded_file = PROCESSED_DATA_DIR / "geocoded_redfin_listings_complete.csv"
    
    if geocoded_file.exists():
        try:
            # Load precomputed geocoded data
            geocoded_df = pd.read_csv(geocoded_file)
            logger.info(f"Loaded {len(geocoded_df)} precomputed geocoded listings")
            
            # Apply filters
            filtered_df = geocoded_df.copy()
            
            if max_rent:
                filtered_df = filtered_df[filtered_df['rent'] <= max_rent]
            
            if bedroom_preferences:
                bedroom_values = []
                for b in bedroom_preferences:
                    if b == "Studio":
                        bedroom_values.append(0)
                    elif "Bedroom" in b:
                        bedroom_values.append(int(b.split()[0]))
                if bedroom_values:
                    filtered_df = filtered_df[filtered_df['bedrooms'].isin(bedroom_values)]
            
            return filtered_df
            
        except Exception as e:
            logger.error(f"Error loading geocoded data: {e}")
    
    # Fallback: use regular listings with ZIP centroids
    logger.warning("Geocoded data not found. Run 'poetry run geocode-all' to precompute coordinates.")
    return listing_loader.get_listings(max_rent=max_rent, bedrooms=bedroom_preferences)

def update_filters():
    """Update session state when filters change"""
    st.session_state.filter_changed = True
    st.session_state.last_update_time = datetime.datetime.now()

def display_listings(listings):
    """Display rental listings in a grid"""
    # Display listings in a grid
    cols = st.columns(2)
    for i, (_, listing) in enumerate(listings.iterrows()):
        col = cols[i % 2]
        with col:
            with st.container():
                # Determine the source logo/color
                if listing['source'].lower() == 'zillow':
                    source_color = "#1277e1"  # Zillow blue
                    source_name = "Zillow"
                else:
                    source_color = "#a02021"  # Redfin red
                    source_name = "Redfin"
                
                st.markdown(f"""
                <div style="border:1px solid #e0e0e0; border-radius:0.5rem; padding:1rem; margin-bottom:1rem; background-color:white;">
                    <div style="font-size:0.8rem; color:white; background-color:{source_color}; padding:2px 8px; border-radius:3px; display:inline-block; margin-bottom:5px;">{source_name}</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:#1E88E5;">${listing['rent']}/month</div>
                    <div style="font-weight:bold;">{listing['address']}, {listing['zip_code']}</div>
                    <div style="color:#616161;">
                        {int(listing['bedrooms'])} BR | {listing['bathrooms']} BA | {listing['sqft']} sqft
                    </div>
                    <div>Available: {listing['available_date']}</div>
                    <a href="{listing['listing_url']}" target="_blank">View Listing</a>
                </div>
                """, unsafe_allow_html=True)

def show_rental_listings_with_source(zip_code, max_rent, bedroom_preferences, source='all'):
    """Show rental listings for a specific ZIP code with source filtering using data dumps"""
    # Zillow is completely disabled - only show Redfin listings
    if source == 'zillow':
        st.error("🚫 Zillow listings are disabled. Only Redfin listings are available.")
        return
    
    source_name = 'Redfin' if source == 'redfin' else 'Redfin'
    st.subheader(f"{source_name} Rental Listings for ZIP Code {zip_code}")
    
    # Check if data is available
    if not listing_loader.data_available():
        st.error("No rental data available. Please run the Redfin scraper first using 'poetry run scrape-redfin'")
        return
    
    with st.spinner(f"Loading Redfin rental listings for ZIP code {zip_code}..."):
        # Get only Redfin listings from data dumps (Zillow is disabled)
        listings = listing_loader.get_listings(
            zip_code=zip_code, 
            max_rent=max_rent, 
            bedrooms=bedroom_preferences, 
            source='redfin'  # Force Redfin only
        )
    
    if listings.empty:
        st.warning(f"No Redfin rental listings found for ZIP code {zip_code} with your criteria.")
        st.info("Try running the Redfin scraper to get fresh data: `poetry run scrape-redfin`")
        return
    
    st.write(f"Found {len(listings)} Redfin rental listings under ${max_rent}/month")
    
    # Display the listings
    display_listings(listings)
    
    # Only show Redfin listings button (Zillow is disabled)
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("View Redfin Listings", key=f"redfin_{zip_code}"):
            show_rental_listings_with_source(zip_code, max_rent, bedroom_preferences, 'redfin')
    
    with col2:
        st.markdown("<div style='color: #666; font-style: italic; padding: 8px;'>🚫 Zillow listings disabled</div>", unsafe_allow_html=True)

def show_rental_listings(zip_code, max_rent, bedroom_preferences):
    """Show rental listings for a specific ZIP code using data dumps"""
    st.subheader(f"Redfin Rental Listings for ZIP Code {zip_code}")
    
    # Check if data is available
    if not listing_loader.data_available():
        st.error("No rental data available. Please run the Redfin scraper first using 'poetry run scrape-redfin'")
        return
    
    with st.spinner(f"Loading Redfin rental listings for ZIP code {zip_code}..."):
        # Get only Redfin listings from data dumps (Zillow is disabled)
        listings = listing_loader.get_listings(
            zip_code=zip_code, 
            max_rent=max_rent, 
            bedrooms=bedroom_preferences,
            source='redfin'  # Force Redfin only
        )
    
    if listings.empty:
        st.warning(f"No Redfin rental listings found for ZIP code {zip_code} with your criteria.")
        st.info("Try running the Redfin scraper to get fresh data: `poetry run scrape-redfin`")
        return
    
    st.write(f"Found {len(listings)} Redfin rental listings under ${max_rent}/month")
    
    # Only show Redfin listings (Zillow is completely disabled)
    display_listings(listings)

# Main app
def main():
    # Initialize session state first to prevent crashes
    if 'last_update_time' not in st.session_state:
        st.session_state.last_update_time = datetime.datetime.now()
    if 'filter_changed' not in st.session_state:
        st.session_state.filter_changed = True
    if 'max_rent' not in st.session_state:
        st.session_state.max_rent = 1500
    if 'selected_bedrooms' not in st.session_state:
        st.session_state.selected_bedrooms = ["1 Bedroom", "2 Bedrooms"]
    if 'display_params' not in st.session_state:
        st.session_state.display_params = {
            'safety_opacity': 0.0,
            'accessibility_opacity': 0.0,
            'neighborhood_opacity': 0.0,
            'environment_opacity': 0.0
        }
    if 'selected_zip' not in st.session_state:
        st.session_state.selected_zip = None
    
    # Header
    st.markdown('<p class="main-header">Austin Rental Analysis</p>', unsafe_allow_html=True)
    st.markdown('<p class="info-text">Find the best places to rent in Austin, TX under $1500/month</p>', 
                unsafe_allow_html=True)
    
    # Introduction and explanation
    with st.expander("📚 About This Dashboard", expanded=False):
        st.markdown("""
        <div class="explanation">
            <h3>What is this dashboard?</h3>
            <p>This interactive tool helps you find the best neighborhoods to rent in Austin, Texas based on your budget and preferences. 
            We provide independent heat map layers showing safety, accessibility, neighborhood quality, and environmental data.</p>
            
            <h3>How does it work?</h3>
            <p>Our analysis focuses on key quality-of-life factors:</p>
            <ul>
                <li><b>Safety</b>: We analyze crime data from the City of Austin to calculate safety scores for each area.</li>
                <li><b>Rental Availability</b>: Real-time rental listings from Redfin show current market availability.</li>
            </ul>
            <p>Use the opacity controls to highlight different factors on the map. The higher the safety score, the safer the area.</p>
            
            <h3>How to use this dashboard</h3>
            <ol>
                <li>Use the sidebar filters to set your maximum rent and bedroom preferences</li>
                <li>Adjust the importance of different factors using the weight sliders</li>
                <li>Explore the map to see which areas score highest</li>
                <li>Check the Rankings tab for a list of top ZIP codes</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("Filters & Settings")
    
    # Load data
    with st.spinner("Loading data..."):
        data = load_data()
    
    if not data or 'safmr' not in data:
        st.error("Failed to load required data. Please check the logs.")
        return
    
    # Sidebar filters
    st.sidebar.markdown("### Rental Preferences")
    max_rent = st.sidebar.slider(
        "Maximum Monthly Rent ($)",
        min_value=500,
        max_value=2000,
        value=st.session_state.max_rent,
        step=100,
        help="Set the maximum amount you're willing to pay in monthly rent",
        on_change=update_filters
    )
    st.session_state.max_rent = max_rent
    
    # Bedroom preference
    bedroom_options = ["Studio", "1 Bedroom", "2 Bedrooms", "3 Bedrooms", "4 Bedrooms"]
    selected_bedrooms = st.sidebar.multiselect(
        "Bedroom Preference",
        options=bedroom_options,
        default=st.session_state.selected_bedrooms,
        help="Select the types of units you're interested in",
        on_change=update_filters
    )
    st.session_state.selected_bedrooms = selected_bedrooms
    
    # Factor weights with explanations
    st.sidebar.markdown("### Factor Weights")
    st.sidebar.markdown("Adjust how important each factor is to you:")
    
    with st.sidebar.expander("What do these factors mean?", expanded=False):
        st.markdown("""
        - **Safety**: Based on crime incident reports in the area - controls red color intensity
        - **Accessibility**: Proximity to downtown, transit, and amenities (coming soon) - controls blue color intensity
        - **Neighborhood Quality**: Schools, parks, and community features (coming soon) - controls green color intensity
        - **Environmental Risk**: Flood zones and natural hazards (coming soon) - controls yellow color intensity
        
        **How it works**: Higher opacity values make that factor more visible on the map. 
        Dangerous areas appear as dark red, safe areas as light red.
        """)
    
    st.sidebar.markdown("### 🎨 Map Display Controls")
    st.sidebar.markdown("*Adjust opacity to highlight different factors on the map*")
    
    safety_opacity = st.sidebar.slider("🔴 Safety Layer Opacity", 0.0, 1.0, st.session_state.display_params['safety_opacity'], 0.1, 
                                      on_change=update_filters, key="safety_opacity",
                                      help="Higher values show safety data more prominently. Dangerous areas = dark red, safe areas = light red")
    accessibility_opacity = st.sidebar.slider("🔵 Accessibility Layer Opacity", 0.0, 1.0, st.session_state.display_params['accessibility_opacity'], 0.1,
                                            on_change=update_filters, key="accessibility_opacity",
                                            help="Coming soon - will control blue color intensity for transit/downtown proximity")
    neighborhood_opacity = st.sidebar.slider("🟢 Neighborhood Quality Opacity", 0.0, 1.0, st.session_state.display_params['neighborhood_opacity'], 0.1,
                                           on_change=update_filters, key="neighborhood_opacity",
                                           help="Coming soon - will control green color intensity for schools/parks")
    environment_opacity = st.sidebar.slider("🟡 Environmental Risk Opacity", 0.0, 1.0, st.session_state.display_params['environment_opacity'], 0.1,
                                          on_change=update_filters, key="environment_opacity",
                                          help="Coming soon - will control yellow color intensity for flood zones")
    
    # Update display parameters
    st.session_state.display_params = {
        'safety_opacity': safety_opacity,
        'accessibility_opacity': accessibility_opacity,
        'neighborhood_opacity': neighborhood_opacity,
        'environment_opacity': environment_opacity
    }
    
    # Add a refresh button that clears all caches
    if st.sidebar.button("Refresh Map"):
        st.session_state.filter_changed = True
        st.session_state.clear_cache = True
        # Clear Streamlit caches
        st.cache_data.clear()
        # Refresh listing loader data
        listing_loader.refresh_data()
        st.success("Map refreshed! All caches cleared.")
    
    # Data source information and scraper status
    with st.sidebar.expander("Data Sources & Scraper Status", expanded=False):
        # Get data statistics
        data_stats = listing_loader.get_data_stats()
        
        st.markdown("""
        <div class="data-source">
            <p><b>Rental Data:</b> HUD Small Area Fair Market Rents (SAFMR) FY 2025</p>
            <p><b>Crime Data:</b> City of Austin Open Data Portal (2024)</p>
            <p><b>Geographic Data:</b> City of Austin Council Districts</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("**Scraped Listings Status:**")
        if data_stats['total_count'] > 0:
            st.success(f"✅ {data_stats['total_count']} listings available")
            
            # Show Redfin status (working)
            if data_stats['redfin_count'] > 0:
                st.write(f"🟢 Redfin: {data_stats['redfin_count']} listings (WORKING)")
            else:
                st.write("🔴 Redfin: 0 listings - run scraper")
            
            # Show Zillow status (completely disabled)
            st.write("🚫 Zillow: DISABLED (no listings loaded)")
            
            st.write(f"• ZIP codes covered: {len(data_stats['zip_codes'])}")
            if data_stats['last_updated']:
                st.write(f"• Last updated: {data_stats['last_updated'][:19]}")
        else:
            st.warning("⚠️ No scraped data available")
            st.write("Run Redfin scraper to get fresh data:")
            st.code("poetry run scrape-redfin")
            st.info("💡 Note: Zillow scraper is disabled due to 403 blocking")
        
        if st.button("Refresh Data", help="Reload data from dump files"):
            # Clear all caches and reload data
            st.cache_data.clear()
            listing_loader.refresh_data()
            st.session_state.clear_cache = True
            st.success("Data refreshed successfully!")
            st.rerun()
    
    # Geocoding status section
    with st.sidebar.expander("🗺️ Geocoding Status", expanded=False):
        geocoded_file = PROCESSED_DATA_DIR / "geocoded_redfin_listings_complete.csv"
        
        if geocoded_file.exists():
            try:
                geocoded_df = pd.read_csv(geocoded_file)
                success_count = len(geocoded_df[geocoded_df.get('geocoded_status', '') == 'success'])
                total_count = len(geocoded_df)
                
                st.success(f"✅ Geocoded data available!")
                st.write(f"• Total listings: {total_count}")
                st.write(f"• Successfully geocoded: {success_count}")
                st.write(f"• Success rate: {success_count/total_count*100:.1f}%")
                
                if success_count < total_count * 0.8:  # Less than 80% success
                    st.warning("⚠️ Low geocoding success rate. Consider re-running geocoding.")
                
            except Exception as e:
                st.error(f"Error reading geocoded data: {e}")
        else:
            st.warning("⚠️ No geocoded data found")
            st.write("**To enable individual property markers:**")
            st.code("poetry run geocode-all")
            st.write("This will:")
            st.write("• Use 10 threads for fast processing")
            st.write("• Save progress incrementally")
            st.write("• Show exact property locations on map")
            st.write("• Enable zoom-based property view")
            
            if st.button("📍 Run Geocoding", help="Start geocoding process"):
                st.info("Run this command in your terminal:")
                st.code("poetry run geocode-all --workers 10")
                st.write("The process will run in the background and save progress as it goes.")
    
    # Process data based on filters
    with st.spinner("Analyzing data..."):
        # Filter for affordable rentals
        affordable_df = filter_affordable_rentals(
            data['safmr'], 
            max_rent=max_rent, 
            bedroom_preferences=selected_bedrooms
        )
        
        # Update the data dictionary with filtered rentals
        data['affordable'] = affordable_df
        
        # Independent heat map layers system - no more livability calculations
        # Each layer is controlled by opacity sliders in the sidebar
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs(["Map View", "Rankings", "Rental Listings", "Data Explorer"])
    
    with tab1:
        st.markdown('<p class="sub-header">Rental Opportunities Map</p>', unsafe_allow_html=True)
        
        # Map explanation
        st.markdown("""
        <div class="explanation">
            This map shows Austin ZIP codes with <b>independent heat map layers</b> that you can control with opacity sliders. 
            Each layer shows different data: <b>🔴 Safety (Red)</b>, <b>🔵 Accessibility (Blue)</b>, <b>🟢 Neighborhood (Green)</b>, <b>🟡 Environment (Yellow)</b>.
            Set opacity to <b>0</b> to hide a layer completely, or <b>1.0</b> for maximum intensity. 
            Circle markers show rental listing availability.
        </div>
        """, unsafe_allow_html=True)
        
        if 'geocoded_zips' in data and data['geocoded_zips'] is not None:
            # Use geocoded ZIP codes directly (no more livability scores)
            map_df = data['geocoded_zips']
            
            # Create map with heat map layers
            popup_cols = ['zip_code']
            m = create_map(
                map_df, 
                data_dict=data,  # Pass full data dictionary for heat map layers
                popup_cols=popup_cols,
                max_rent=max_rent,
                bedroom_preferences=selected_bedrooms,
                display_params=st.session_state.display_params
            )
            
            # Display map
            st.markdown("### 🗺️ Multi-Layer Heat Map Visualization")
            st.markdown("**Use opacity sliders to control heat map layers**: 🔴 Safety, 🔵 Accessibility, 🟢 Neighborhood, 🟡 Environment. Set to 0 to hide completely.")
            
            # Add a filter change indicator
            if st.session_state.filter_changed:
                st.success("Map updated with your filter changes!")
                st.session_state.filter_changed = False
            
            # Check if geocoded data is available
            geocoded_file = PROCESSED_DATA_DIR / "geocoded_redfin_listings_complete.csv"
            if geocoded_file.exists():
                st.info("💡 **Zoom Tip**: Zoom out to see ZIP code areas, zoom in (14+) to see individual property locations!")
            else:
                st.warning("⚠️ **Geocoded data not found**: Individual property markers not available. Run `poetry run geocode-all` to enable precise property locations.")
            
            # Display the map with stable key to prevent unnecessary re-renders
            st_folium(m, width=1000, height=600, key="austin_heat_map")
            
            # Add JavaScript to handle map button clicks
            components_js = """
                <script>
                window.addEventListener('message', function(e) {
                    console.log('Received message:', e.data);
                    if (e.data && e.data.type === 'rental_click' && e.data.zipCode) {
                        // Store the ZIP code and source in session state
                        const data = {
                            zipCode: e.data.zipCode,
                            source: e.data.source
                        };
                        
                        console.log('Setting component value:', data);
                        
                        // Use the Streamlit event system to handle this
                        if (window.parent.Streamlit) {
                            window.parent.Streamlit.setComponentValue(data);
                        }
                        
                        // Switch to the Rental Listings tab
                        setTimeout(() => {
                            const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
                            console.log('Found tabs:', tabs.length);
                            if (tabs && tabs.length >= 3) {
                                tabs[2].click();  // Click the third tab (Rental Listings)
                                console.log('Clicked rental listings tab');
                            }
                        }, 100);
                    }
                });
                </script>
            """
            st.components.v1.html(components_js, height=0)
        else:
            st.warning("Geocoded ZIP codes not available. Map cannot be displayed.")
    
    with tab2:
        st.markdown('<p class="sub-header">Data Layer Information</p>', unsafe_allow_html=True)
        
        # Data layers explanation
        st.markdown("""
        <div class="explanation">
            This section shows information about the independent heat map layers available on the map.
            Each layer can be controlled separately using opacity sliders.
            <ul>
                <li><b>🔴 Safety Layer:</b> Red heat map showing crime risk (dark red = dangerous areas)</li>
                <li><b>🔵 Accessibility Layer:</b> Blue heat map for transit/downtown proximity (coming soon)</li>
                <li><b>🟢 Neighborhood Layer:</b> Green heat map for schools/parks quality (coming soon)</li>
                <li><b>🟡 Environment Layer:</b> Yellow heat map for flood zones/hazards (coming soon)</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Show data layer status instead of livability rankings
        st.subheader("🗺️ Heat Map Layer Status")
        
        layer_status = {
            "🔴 Safety": "✅ Active - Crime data available",
            "🔵 Accessibility": "🚧 Coming Soon - Transit data integration",
            "🟢 Neighborhood": "🚧 Coming Soon - Schools/parks data",
            "🟡 Environment": "🚧 Coming Soon - Flood zone data"
        }
        
        for layer, status in layer_status.items():
            st.write(f"**{layer}**: {status}")
        
        # Show rental data availability
        st.subheader("📊 Rental Data Status")
        if listing_loader.data_available():
            counts = listing_loader.get_listing_counts_by_zip()
            total_listings = sum(zip_data['total'] for zip_data in counts.values())
            st.success(f"✅ {total_listings} rental listings available across {len(counts)} ZIP codes")
        else:
            st.warning("⚠️ No rental data available. Run `poetry run scrape-redfin` to collect data.")
        
        # Remove all livability ranking code
        if False:  # Disabled livability rankings
            # Display top ZIP codes
            st.markdown("### Top 10 Most Livable ZIP Codes")
            
            # Sort by livability score
            top_zips = livability_df.sort_values('livability_score', ascending=False).head(10)
            
            # Display as a table
            if not top_zips.empty:
                # Select columns to display
                display_cols = ['ZIP Code', 'livability_score']
                
                # Add affordability columns if available
                affordable_cols = [col for col in top_zips.columns if col.startswith('Affordable_')]
                display_cols.extend(affordable_cols)
                
                # Add crime score if available
                if 'crime_score' in top_zips.columns:
                    display_cols.append('crime_score')
                
                # Format the table
                formatted_df = top_zips[display_cols].copy()
                
                # Rename columns for better display
                column_renames = {
                    'livability_score': 'Livability Score',
                    'crime_score': 'Safety Score'
                }
                
                for col in affordable_cols:
                    bedroom_type = col.split('_')[1]
                    column_renames[col] = f"{bedroom_type} BR Affordable"
                
                formatted_df = formatted_df.rename(columns=column_renames)
                
                # Format numeric columns
                for col in formatted_df.columns:
                    if col not in ['ZIP Code']:
                        if 'Affordable' in col:
                            # Convert boolean to Yes/No
                            formatted_df[col] = formatted_df[col].map({True: 'Yes', False: 'No'})
                        else:
                            # Format scores to 2 decimal places
                            formatted_df[col] = formatted_df[col].map(lambda x: f"{x:.2f}")
                
                st.dataframe(formatted_df, width='stretch')
                
                # Create bar chart of livability scores
                fig = px.bar(
                    top_zips,
                    x='ZIP Code',
                    y='livability_score',
                    title='Livability Scores by ZIP Code',
                    labels={'livability_score': 'Livability Score', 'ZIP Code': 'ZIP Code'},
                    color='livability_score',
                    color_continuous_scale='RdYlGn'
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.warning("No ZIP codes match your criteria.")
        else:
            st.warning("Livability scores could not be calculated. Check data availability.")
    
    with tab3:
        st.markdown('<p class="sub-header">Rental Listings</p>', unsafe_allow_html=True)
        
        # Rental listings explanation
        st.markdown("""
        <div class="explanation">
            This section shows rental listings for the selected ZIP code.
        </div>
        """, unsafe_allow_html=True)
        
        # Add a callback to handle map click events
        map_click = st.session_state.get("_component_value")
        if map_click and isinstance(map_click, dict) and 'zipCode' in map_click:
            zip_code = map_click['zipCode']
            source = map_click.get('source', 'all')
            st.session_state["_component_value"] = None  # Clear after using
            show_rental_listings_with_source(zip_code, max_rent, selected_bedrooms, source)
        # Check if we have a selected ZIP code from session state
        elif st.session_state.selected_zip:
            show_rental_listings(st.session_state.selected_zip, max_rent, selected_bedrooms)
            st.session_state.selected_zip = None  # Clear after using
        # Otherwise, show ZIP code selection dropdown
        else:
            # Check if scraped data is available
            if not listing_loader.data_available():
                st.warning("No scraped rental data available.")
                st.info("To get rental listings, please run the Redfin scraper:")
                st.code("poetry run scrape-redfin")
                st.markdown("This will scrape rental listings from Redfin for all Austin ZIP codes.")
                st.info("💡 Note: Zillow scraper is currently disabled due to 403 blocking by the website.")
            else:
                # Show available ZIP codes from scraped data
                data_stats = listing_loader.get_data_stats()
                available_zips = sorted(data_stats['zip_codes'])
                
                if available_zips:
                    selected_zip = st.selectbox(
                        "Select ZIP code to view rental listings:",
                        options=available_zips,
                        help=f"Showing {len(available_zips)} ZIP codes with available listings"
                    )
                    
                    if st.button("Show Rentals"):
                        show_rental_listings(selected_zip, max_rent, selected_bedrooms)
                else:
                    st.warning("No ZIP codes with rental listings found.")
    
    with tab4:
        st.markdown('<p class="sub-header">Data Explorer</p>', unsafe_allow_html=True)
        
        # Data explorer explanation
        st.markdown("""
        <div class="explanation">
            This section lets you explore the raw data used in our analysis. Select a dataset from the dropdown to view its contents.
            <ul>
                <li><b>SAFMR Data:</b> HUD's Small Area Fair Market Rent estimates by ZIP code</li>
                <li><b>Crime Data:</b> Incident counts by council district</li>
                <li><b>Affordable Housing:</b> Subsidized housing inventory</li>
                <li><b>Heat Map Layers:</b> Independent data visualizations (Safety, Accessibility, Neighborhood, Environment)</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Select dataset to explore
        dataset_option = st.selectbox(
            "Select dataset to explore",
            options=["SAFMR Data", "Crime Data", "Affordable Housing", "Heat Map Layer Data"]
        )
        
        if dataset_option == "SAFMR Data" and 'safmr' in data:
            st.dataframe(data['safmr'], width='stretch')
        elif dataset_option == "Crime Data" and 'crime' in data:
            st.dataframe(data['crime'], width='stretch')
        elif dataset_option == "Affordable Housing" and 'housing' in data:
            st.dataframe(data['housing'], width='stretch')
        elif dataset_option == "Heat Map Layer Data":
            st.info("Heat map layers use processed data from Crime, SAFMR, and other sources. Select individual datasets above to explore the underlying data.")
        else:
            st.warning(f"Selected dataset '{dataset_option}' is not available.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div class="info-text">
        <p>Data sources: HUD SAFMR, City of Austin Open Data Portal</p>
        <p>This dashboard is for educational purposes only. Rental decisions should include additional research.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
