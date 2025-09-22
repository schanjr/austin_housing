"""
New property-focused dashboard for Austin Housing analysis.
Replaces complex heat maps with intuitive property scoring and visualization.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import logging
from pathlib import Path
import sys

# Add the app directory to the path for imports
app_dir = Path(__file__).parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from property_scoring import PropertyScorer
from property_display import PropertyDisplay
from clean_map import CleanMap

# Import data loading functions from existing modules
sys.path.insert(0, str(app_dir.parent / "src"))
from src.data.listing_loader import listing_loader
from analysis.data_processing import load_processed_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_property_table_from_precalc(properties_df):
    """Create property table from pre-calculated scores for instant performance."""
    try:
        # Create display table with pre-calculated scores
        display_properties = []
        
        for _, row in properties_df.iterrows():
            # Get listing URL
            listing_url = row.get('url', row.get('listing_url', ''))
            property_id = row.get('id', '')
            address = row.get('address', 'Unknown')
            
            # Generate Redfin URL if we have property ID but no URL
            if not listing_url and property_id and 'redfin' in str(property_id).lower():
                numeric_id = str(property_id).replace('redfin-', '')
                listing_url = f"https://www.redfin.com/TX/Austin/{numeric_id}"
            
            # If still no URL, create Redfin search link with instructions
            if not listing_url and address != 'Unknown':
                # Create Redfin search URL and format with instructions
                redfin_search_url = "https://www.redfin.com/city/30818/TX/Austin"
                listing_url = f"🔍 Search on Redfin: {redfin_search_url} (Copy & paste: {address})"
            
            display_property = {
                'Address': address,
                'ZIP': row.get('zip_code', ''),
                'Rent': f"${row.get('rent', 0):,.0f}",
                'Overall Score': f"{row.get('overall_score', 0):.1f}/10",
                'Safety': f"{row.get('safety_score', 0):.1f}/10",
                'Walkability': f"{row.get('accessibility_score', 0):.1f}/10",
                'Neighborhood': f"{row.get('neighborhood_score', 0):.1f}/10",
                'Environment': f"{row.get('environment_score', 0):.1f}/10",
                'Bedrooms': row.get('bedrooms', 'N/A'),
                'Source': row.get('source', 'Unknown'),
                'Listing Link': listing_url if listing_url else 'N/A',
                '_rent_numeric': row.get('rent', 0),
                '_overall_numeric': row.get('overall_score', 0),
                '_safety_numeric': row.get('safety_score', 0),
                '_walkability_numeric': row.get('accessibility_score', 0),
                '_neighborhood_numeric': row.get('neighborhood_score', 0),
                '_environment_numeric': row.get('environment_score', 0)
            }
            display_properties.append(display_property)
        
        return pd.DataFrame(display_properties)
        
    except Exception as e:
        logger.error(f"Error creating property table from pre-calculated scores: {e}")
        return pd.DataFrame()

def create_neighborhood_summary_from_precalc(properties_df):
    """Create neighborhood summary from pre-calculated scores for instant performance."""
    try:
        # Group by ZIP code and calculate averages
        zip_groups = properties_df.groupby('zip_code').agg({
            'overall_score': ['mean', 'count'],
            'safety_score': 'mean',
            'accessibility_score': 'mean', 
            'neighborhood_score': 'mean',
            'environment_score': 'mean',
            'rent': 'mean'
        }).round(1)
        
        # Flatten column names
        zip_groups.columns = ['Overall Score', 'Property Count', 'Safety', 'Walkability', 'Neighborhood', 'Environment', 'Avg Rent']
        
        # Format for display
        zip_summary = []
        for zip_code, row in zip_groups.iterrows():
            summary = {
                'ZIP Code': zip_code,
                'Properties': int(row['Property Count']),
                'Overall Score': f"{row['Overall Score']:.1f}/10",
                'Safety': f"{row['Safety']:.1f}/10",
                'Walkability': f"{row['Walkability']:.1f}/10", 
                'Neighborhood': f"{row['Neighborhood']:.1f}/10",
                'Environment': f"{row['Environment']:.1f}/10",
                'Avg Rent': f"${row['Avg Rent']:,.0f}",
                '_overall_numeric': row['Overall Score'],
                '_safety_numeric': row['Safety'],
                '_walkability_numeric': row['Walkability'],
                '_neighborhood_numeric': row['Neighborhood'],
                '_environment_numeric': row['Environment'],
                '_rent_numeric': row['Avg Rent']
            }
            zip_summary.append(summary)
        
        # Sort by overall score
        zip_df = pd.DataFrame(zip_summary).sort_values('_overall_numeric', ascending=False)
        return zip_df
        
    except Exception as e:
        logger.error(f"Error creating neighborhood summary from pre-calculated scores: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def load_property_data():
    """Load the single master dataset with all property data."""
    try:
        # Load the master dataset - ONE authoritative source
        master_path = Path(__file__).parent.parent / "data" / "processed" / "master_properties.csv"
        
        if master_path.exists():
            logger.info("Loading master property dataset...")
            # Optimize data loading with specific dtypes for better performance
            dtype_dict = {
                'zip_code': 'str',  # Pre-convert to string to avoid repeated astype calls
                'rent': 'float32',  # Use float32 instead of float64 for memory efficiency
                'bedrooms': 'float32',
                'overall_score': 'float32',
                'safety_score': 'float32',
                'accessibility_score': 'float32',
                'neighborhood_score': 'float32',
                'environment_score': 'float32'
            }
            properties_df = pd.read_csv(master_path, dtype=dtype_dict)
            logger.info(f"Loaded {len(properties_df)} properties from master dataset")
            return properties_df
        else:
            # Fallback to original loading if pre-calculated scores don't exist
            logger.warning("Pre-calculated scores not found, loading original data...")
            listings_data = listing_loader.get_listings()
            
            if listings_data is None or listings_data.empty:
                st.error("No rental listings data available. Please run data collection first.")
                return pd.DataFrame()
            
            logger.info(f"Loaded {len(listings_data)} properties (without pre-calculated scores)")
            return listings_data
        
    except Exception as e:
        logger.error(f"Error loading property data: {e}")
        st.error(f"Error loading property data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def get_filter_ranges(properties_df):
    """Pre-calculate filter ranges to avoid repeated computations."""
    return {
        'rent_min': int(properties_df['rent'].min()),
        'rent_max': int(properties_df['rent'].max()),
        'available_bedrooms': sorted([x for x in properties_df['bedrooms'].unique() if pd.notna(x)]),
        'available_zips': sorted(properties_df['zip_code'].unique())
    }

@st.cache_data(show_spinner=False)
def apply_filters_optimized(properties_df, zip_codes, rent_range, min_bedrooms, min_overall_score, 
                           min_safety_score, min_walkability_score, min_neighborhood_score, min_environment_score):
    """Optimized filtering function with caching."""
    # Single-pass filtering with all conditions
    mask = (
        properties_df['zip_code'].isin(zip_codes) &
        (properties_df['rent'] >= rent_range[0]) &
        (properties_df['rent'] <= rent_range[1]) &
        (properties_df['bedrooms'] >= min_bedrooms) &
        (properties_df['overall_score'] >= min_overall_score) &
        (properties_df['safety_score'] >= min_safety_score) &
        (properties_df['accessibility_score'] >= min_walkability_score) &
        (properties_df['neighborhood_score'] >= min_neighborhood_score) &
        (properties_df['environment_score'] >= min_environment_score)
    )
    return properties_df[mask].copy()

# Removed custom CSS - using Streamlit native components instead

def main():
    """Main dashboard application."""
    st.set_page_config(
        page_title="Austin Housing Dashboard",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Clean header using Streamlit native components
    st.title("🏠 Austin Housing Dashboard")
    st.markdown("**Find the perfect rental property with detailed scoring and real data**")
    st.divider()
    
    # Initialize components
    property_display = PropertyDisplay()
    
    # Load data with error handling
    try:
        with st.spinner("Loading property data..."):
            properties_df = load_property_data()
        
        if properties_df.empty:
            st.error("No property data available. Please check data sources.")
            st.stop()
        
        # Initialize components
        property_display = PropertyDisplay()
        clean_map = CleanMap()
        
        # Clean Sidebar Design using Streamlit native components
        with st.sidebar:
            st.header("🎯 Area Selection")
            
            # Initialize selected ZIP codes in session state
            if 'selected_zips' not in st.session_state:
                st.session_state.selected_zips = ['78701', '78702', '78703']  # Default selection
            
            # Get pre-calculated filter ranges for performance
            filter_ranges = get_filter_ranges(properties_df)
            available_zips = filter_ranges['available_zips']
            
            st.write("**Select ZIP codes to explore:**")
            
            # Quick action buttons using Streamlit columns
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ All", key="select_all", help="Select all available ZIP codes", width="stretch"):
                    st.session_state.selected_zips = available_zips
                    st.rerun()
            
            with col2:
                if st.button("❌ Clear", key="clear_all", help="Clear all ZIP code selections", width="stretch"):
                    st.session_state.selected_zips = []
                    st.rerun()
            
            # Main ZIP code multiselect
            selected_zips = st.multiselect(
                "Available ZIP Codes:",
                options=available_zips,
                default=st.session_state.selected_zips,
                help="Choose specific areas to view properties"
            )
            
            # Update session state
            st.session_state.selected_zips = selected_zips if selected_zips else st.session_state.selected_zips
            
            # Show selection summary using native Streamlit components
            if st.session_state.selected_zips:
                st.success(f"📍 {len(st.session_state.selected_zips)} ZIP codes selected")
            else:
                st.warning("⚠️ Please select at least one ZIP code")
        
        # Early exit if no ZIP codes selected
        if not st.session_state.selected_zips:
            st.warning("Please select at least one ZIP code to view properties.")
            st.stop()
        
        # Advanced Filters Section using Streamlit native components
        with st.sidebar:
            st.header("🔍 Advanced Filters")
            
            # Use pre-calculated ranges for better performance
            rent_min = filter_ranges['rent_min']
            rent_max = filter_ranges['rent_max']
            available_bedrooms = filter_ranges['available_bedrooms']
            
            # Rent Range Filter
            st.subheader("💰 Rent Range")
            
            rent_range = st.slider(
                "Monthly Rent ($)",
                min_value=rent_min,
                max_value=rent_max,
                value=(rent_min, min(3000, rent_max)),
                step=50,
                help="Filter properties by rent range"
            )
            
            # Show selected range using native info box
            st.info(f"Selected range: ${rent_range[0]:,} - ${rent_range[1]:,} per month")
            
            # Bedrooms Filter
            st.subheader("🛏️ Bedrooms")
            min_bedrooms = st.selectbox(
                "Minimum Bedrooms",
                options=[0] + available_bedrooms,
                index=0,
                help="Minimum number of bedrooms required"
            )
            
            # Overall Score Filter
            st.subheader("⭐ Overall Score")
            min_overall_score = st.slider(
                "Minimum Overall Score",
                min_value=0.0,
                max_value=10.0,
                value=0.0,
                step=0.1,
                help="Minimum overall livability score (0-10)"
            )
            
            # Individual Score Filters using native expanders
            st.subheader("📊 Individual Scores")
            
            with st.expander("🛡️ Safety Score"):
                min_safety_score = st.slider(
                    "Minimum Safety Score",
                    min_value=0.0,
                    max_value=10.0,
                    value=0.0,
                    step=0.1,
                    key="safety_filter",
                    help="Filter by minimum safety score"
                )
                if min_safety_score > 0:
                    st.caption(f"Showing properties with safety score ≥ {min_safety_score:.1f}")
            
            with st.expander("🚶 Walkability Score"):
                min_walkability_score = st.slider(
                    "Minimum Walkability Score",
                    min_value=0.0,
                    max_value=10.0,
                    value=0.0,
                    step=0.1,
                    key="walkability_filter",
                    help="Filter by minimum accessibility/walkability score"
                )
                if min_walkability_score > 0:
                    st.caption(f"Showing properties with walkability score ≥ {min_walkability_score:.1f}")
            
            with st.expander("🏛️ Neighborhood Score"):
                min_neighborhood_score = st.slider(
                    "Minimum Neighborhood Score",
                    min_value=0.0,
                    max_value=10.0,
                    value=0.0,
                    step=0.1,
                    key="neighborhood_filter",
                    help="Filter by minimum neighborhood quality score"
                )
                if min_neighborhood_score > 0:
                    st.caption(f"Showing properties with neighborhood score ≥ {min_neighborhood_score:.1f}")
            
            with st.expander("🌱 Environment Score"):
                min_environment_score = st.slider(
                    "Minimum Environment Score",
                    min_value=0.0,
                    max_value=10.0,
                    value=0.0,
                    step=0.1,
                    key="environment_filter",
                    help="Filter by minimum environmental quality score"
                )
                if min_environment_score > 0:
                    st.caption(f"Showing properties with environment score ≥ {min_environment_score:.1f}")
            
            # Filter Reset Button using native Streamlit button
            st.divider()
            if st.button("🔄 Reset All Filters", help="Reset all filters to default values", key="reset_filters", width="stretch"):
                st.rerun()
        
        # Apply all filters using optimized cached function
        filtered_df = apply_filters_optimized(
            properties_df,
            st.session_state.selected_zips,
            rent_range,
            min_bedrooms,
            min_overall_score,
            min_safety_score,
            min_walkability_score,
            min_neighborhood_score,
            min_environment_score
        )
        
        # Enhanced status display using Streamlit native components
        with st.sidebar:
            total_properties = len(properties_df)
            filtered_count = len(filtered_df)
            filter_percentage = (filtered_count / total_properties * 100) if total_properties > 0 else 0
            
            # Status display using native metrics
            st.divider()
            st.metric(
                "Properties Found", 
                f"{filtered_count:,}",
                delta=f"{filter_percentage:.1f}% of total"
            )
            
            # Show active filters summary using native components
            active_filters = []
            if rent_range != (rent_min, rent_max):
                active_filters.append(f"Rent: ${rent_range[0]:,}-${rent_range[1]:,}")
            if min_bedrooms > 0:
                active_filters.append(f"Beds: {min_bedrooms}+")
            if min_overall_score > 0:
                active_filters.append(f"Score: {min_overall_score:.1f}+")
            if min_safety_score > 0:
                active_filters.append(f"Safety: {min_safety_score:.1f}+")
            if min_walkability_score > 0:
                active_filters.append(f"Walk: {min_walkability_score:.1f}+")
            if min_neighborhood_score > 0:
                active_filters.append(f"Neighborhood: {min_neighborhood_score:.1f}+")
            if min_environment_score > 0:
                active_filters.append(f"Environment: {min_environment_score:.1f}+")
            
            if active_filters:
                filters_text = " • ".join(active_filters)
                st.info(f"🔍 **Active Filters:** {filters_text}")
            else:
                st.success("✓ No filters applied - showing all properties in selected areas")
        
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")
        logger.error(f"Dashboard loading error: {e}")
        st.stop()
    
    # Main content area using Streamlit native layout
    col1, col2 = st.columns([2, 1], gap="large")
    
    with col1:
        # Clean section header using native components
        st.header("🗺️ Property Map")
        st.caption("Interactive map showing filtered properties with direct listing links")
        
        if not filtered_df.empty:
            # Optimize map rendering for large datasets
            with st.spinner("Loading property map..."):
                # Limit map markers for performance - sample if too many properties
                map_df = filtered_df
                if len(filtered_df) > 1000:
                    st.info(f"📍 Showing sample of {min(1000, len(filtered_df))} properties on map for performance. All {len(filtered_df)} properties are included in stats and filtering.")
                    map_df = filtered_df.sample(n=1000, random_state=42)  # Consistent sampling
                
                property_map = clean_map.create_property_map(
                    map_df, 
                    selected_zips=st.session_state.selected_zips
                )
                # Use stable key based on filter state to prevent unnecessary re-rendering
                filter_hash = hash(str(sorted(st.session_state.selected_zips)) + str(rent_range) + str(min_bedrooms) + str(min_overall_score))
                map_key = f"map_{filter_hash}"
                map_data = st_folium(property_map, width=700, height=500, key=map_key)
            
            # Native info display
            st.info("📍 Property pins show exact locations with direct links to listings")
            
            # Handle property clicks with native feedback
            if map_data and map_data.get('last_object_clicked_tooltip'):
                clicked_item = map_data['last_object_clicked_tooltip']
                st.success(f"🏠 **Selected**: {clicked_item}")
            
            # Native caption
            st.caption(f"Displaying {len(filtered_df):,} properties in ZIP codes: {', '.join(st.session_state.selected_zips)}")
        else:
            # Native empty state
            st.warning("🔍 **No properties match your filters**")
            st.info("Try adjusting your criteria to see more results")
    
    with col2:
        # Clean section header using native components
        st.header("📊 Quick Stats")
        st.caption("Key insights from filtered properties")
        
        if not filtered_df.empty:
            # Calculate comprehensive statistics efficiently
            stats = {
                'avg_rent': filtered_df['rent'].mean(),
                'min_rent': filtered_df['rent'].min(),
                'max_rent': filtered_df['rent'].max(),
                'avg_overall_score': filtered_df['overall_score'].mean(),
                'avg_bedrooms': filtered_df['bedrooms'].mean()
            }
            
            # Native metrics using Streamlit's built-in components
            st.metric(
                "Properties Found", 
                f"{len(filtered_df):,}",
                delta=f"{filter_percentage:.1f}% of total"
            )
            
            st.metric(
                "Average Rent", 
                f"${stats['avg_rent']:,.0f}",
                delta=f"Range: ${stats['min_rent']:,.0f} - ${stats['max_rent']:,.0f}"
            )
            
            quality = 'Excellent' if stats['avg_overall_score'] >= 8 else 'Good' if stats['avg_overall_score'] >= 6 else 'Fair' if stats['avg_overall_score'] >= 4 else 'Poor'
            st.metric(
                "Average Score", 
                f"{stats['avg_overall_score']:.1f}/10",
                delta=f"{quality} Quality"
            )
            
            # Rent distribution
            st.write("**💰 Rent Distribution:**")
            rent_ranges = {
                "Under $1,000": len(filtered_df[filtered_df['rent'] < 1000]),
                "$1,000-$1,500": len(filtered_df[(filtered_df['rent'] >= 1000) & (filtered_df['rent'] < 1500)]),
                "$1,500-$2,000": len(filtered_df[(filtered_df['rent'] >= 1500) & (filtered_df['rent'] < 2000)]),
                "$2,000+": len(filtered_df[filtered_df['rent'] >= 2000])
            }
            
            for range_name, count in rent_ranges.items():
                if count > 0:
                    percentage = (count / len(filtered_df)) * 100
                    st.write(f"• {range_name}: {count} ({percentage:.1f}%)")
            
            # Score quality breakdown
            st.write("**⭐ Score Quality:**")
            score_ranges = {
                "Excellent (8.0+)": len(filtered_df[filtered_df['overall_score'] >= 8.0]),
                "Good (6.0-7.9)": len(filtered_df[(filtered_df['overall_score'] >= 6.0) & (filtered_df['overall_score'] < 8.0)]),
                "Fair (4.0-5.9)": len(filtered_df[(filtered_df['overall_score'] >= 4.0) & (filtered_df['overall_score'] < 6.0)]),
                "Poor (<4.0)": len(filtered_df[filtered_df['overall_score'] < 4.0])
            }
            
            for quality, count in score_ranges.items():
                if count > 0:
                    percentage = (count / len(filtered_df)) * 100
                    st.write(f"• {quality}: {count} ({percentage:.1f}%)")
            
            # Top ZIP codes with more details
            if len(filtered_df) > 0:
                st.write("**🏘️ Top Areas:**")
                top_zips = filtered_df.groupby('zip_code').agg({
                    'zip_code': 'count',
                    'rent': 'mean',
                    'overall_score': 'mean'
                }).round(1)
                top_zips.columns = ['count', 'avg_rent', 'avg_score']
                top_zips = top_zips.sort_values('count', ascending=False).head(3)
                
                for zip_code, row in top_zips.iterrows():
                    st.write(f"• **{zip_code}**: {int(row['count'])} properties")
                    st.write(f"  Avg: ${row['avg_rent']:,.0f}, Score: {row['avg_score']:.1f}")
        else:
            st.info("No properties match your current filter criteria.")
            st.write("**💡 Try adjusting:**")
            st.write("• Expanding rent range")
            st.write("• Lowering minimum scores")
            st.write("• Reducing bedroom requirements")
            st.write("• Adding more ZIP codes")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Property List", "🏘️ Neighborhoods", "📈 Score Analysis", "ℹ️ About Scoring"])
    
    with tab1:
        st.subheader("Property Details")
        
        if not filtered_df.empty:
            # Simple approach - show all properties from selected ZIP codes
            st.success(f"⚡ Showing all {len(filtered_df)} properties from selected ZIP codes!")
            
            # Create property table from pre-calculated scores (simple, no caching)
            property_table = create_property_table_from_precalc(filtered_df)
            
            if not property_table.empty:
                # Add sorting options
                sort_col1, sort_col2 = st.columns([1, 1])
                
                with sort_col1:
                    sort_by = st.selectbox(
                        "Sort by:",
                        options=["Overall Score", "Rent", "Safety", "Walkability", "Neighborhood", "Environment"],
                        index=0
                    )
                
                with sort_col2:
                    sort_order = st.selectbox(
                        "Order:",
                        options=["Highest First", "Lowest First"],
                        index=0
                    )
                
                # Simple sorting - no complex caching
                numeric_col = f"_{sort_by.lower().replace(' ', '_')}_numeric"
                if sort_by == "Overall Score":
                    numeric_col = "_overall_numeric"
                elif sort_by == "Rent":
                    numeric_col = "_rent_numeric"
                elif sort_by == "Walkability":
                    numeric_col = "_walkability_numeric"
                
                if numeric_col in property_table.columns:
                    ascending = sort_order == "Lowest First"
                    property_table_sorted = property_table.sort_values(numeric_col, ascending=ascending)
                else:
                    property_table_sorted = property_table
                
                # Simple table display - no caching
                display_columns = [col for col in property_table_sorted.columns if not col.startswith('_')]
                st.dataframe(
                    property_table_sorted[display_columns],
                    width="stretch",
                    height=400
                )
                
                # Download option
                csv = property_table_sorted[display_columns].to_csv(index=False)
                st.download_button(
                    label="📥 Download Property List",
                    data=csv,
                    file_name="austin_properties.csv",
                    mime="text/csv"
                )
        else:
            st.info("No properties to display with current filters.")
    
    with tab2:
        st.subheader("Neighborhood Analysis")
        
        if not filtered_df.empty:
            # Simple neighborhood analysis for selected ZIP codes
            st.info(f"Analyzing {len(st.session_state.selected_zips)} selected ZIP codes")
            neighborhood_summary = create_neighborhood_summary_from_precalc(filtered_df)
            
            if not neighborhood_summary.empty:
                st.write("**ZIP Code Comparison:**")
                
                # Display neighborhood table
                display_columns = [col for col in neighborhood_summary.columns if not col.startswith('_')]
                st.dataframe(
                    neighborhood_summary[display_columns],
                    width="stretch",
                    height=300
                )
                
                # Neighborhood insights
                st.write("**Insights:**")
                
                # Best overall neighborhood
                if not neighborhood_summary.empty:
                    best_zip = neighborhood_summary.iloc[0]
                    overall_score = best_zip.get('Overall Score', best_zip.get('Overall', 'N/A'))
                    st.success(f"🏆 **Best Overall:** ZIP {best_zip['ZIP Code']} (Score: {overall_score})")
                
                    # Most affordable
                    if '_avg_rent_numeric' in neighborhood_summary.columns:
                        cheapest_zip = neighborhood_summary.sort_values('_avg_rent_numeric').iloc[0]
                        st.info(f"💰 **Most Affordable:** ZIP {cheapest_zip['ZIP Code']} (Avg: {cheapest_zip.get('Avg Rent', 'N/A')})")
                    
                    # Safest
                    if '_safety_numeric' in neighborhood_summary.columns:
                        safest_zip = neighborhood_summary.sort_values('_safety_numeric', ascending=False).iloc[0]
                        st.info(f"🛡️ **Safest:** ZIP {safest_zip['ZIP Code']} (Safety: {safest_zip.get('Safety', 'N/A')})")
                    
                    # Most walkable
                    if '_walkability_numeric' in neighborhood_summary.columns:
                        walkable_zip = neighborhood_summary.sort_values('_walkability_numeric', ascending=False).iloc[0]
                        st.info(f"🚶 **Most Walkable:** ZIP {walkable_zip['ZIP Code']} (Walkability: {walkable_zip.get('Walkability', 'N/A')})")
        else:
            st.info("No neighborhood data to display with current filters.")
    
    with tab3:
        st.subheader("Score Distribution Analysis")
        
        if not filtered_df.empty:
            # Create score distribution chart
            score_chart = property_display.create_score_distribution_chart(filtered_df)
            st.plotly_chart(score_chart, width="stretch")
            
            # Score correlation analysis
            st.write("**Score Insights:**")
            
            # Calculate some basic statistics
            scorer = PropertyScorer()
            all_scores = []
            for idx, property_data in filtered_df.iterrows():
                scores = scorer.calculate_property_scores(property_data.to_dict())
                all_scores.append({
                    'rent': property_data['rent'],
                    'overall': scores['overall_score'],
                    'safety': scores['scores']['safety']['score'],
                    'walkability': scores['scores']['accessibility']['score'],
                    'neighborhood': scores['scores']['neighborhood']['score'],
                    'environment': scores['scores']['environment']['score']
                })
            
            scores_analysis_df = pd.DataFrame(all_scores)
            
            if len(scores_analysis_df) > 1:
                # Rent vs Score correlation
                rent_score_corr = scores_analysis_df['rent'].corr(scores_analysis_df['overall'])
                if rent_score_corr > 0.3:
                    st.info(f"📈 Higher rent properties tend to have better overall scores (correlation: {rent_score_corr:.2f})")
                elif rent_score_corr < -0.3:
                    st.info(f"📉 Lower rent properties tend to have better overall scores (correlation: {rent_score_corr:.2f})")
                else:
                    st.info(f"📊 Rent and overall score show weak correlation (correlation: {rent_score_corr:.2f})")
                
                # Best value properties
                scores_analysis_df['value_score'] = scores_analysis_df['overall'] / (scores_analysis_df['rent'] / 1000)
                best_value_idx = scores_analysis_df['value_score'].idxmax()
                best_value_rent = scores_analysis_df.loc[best_value_idx, 'rent']
                best_value_score = scores_analysis_df.loc[best_value_idx, 'overall']
                
                st.success(f"💎 **Best Value:** ${best_value_rent:,.0f}/month with {best_value_score:.1f}/10 score")
        else:
            st.info("No score data to analyze with current filters.")
    
    with tab4:
        st.subheader("About the Scoring System")
        
        st.markdown("""
        ### 📊 How Properties Are Scored
        
        Each property receives an **Overall Score (0-10)** based on five key factors:
        
        #### 💰 Affordability (30% weight)
        - How much under your $1,500 budget the rent is
        - More savings = higher score
        
        #### 🛡️ Safety (25% weight)
        - Based on real Austin crime data by council district
        - Lower crime incidents = higher score
        
        #### 🚶 Accessibility (20% weight)
        - Real WalkScore data including walkability, transit, and bike scores
        - Better walkability = higher score
        
        #### 🏛️ Neighborhood Quality (15% weight)
        - Uses walkability as proxy for amenities and neighborhood quality
        - More walkable areas typically have better amenities
        
        #### 🌱 Environmental Quality (10% weight)
        - Based on distance from downtown Austin
        - Further from downtown = less pollution/noise = higher score
        
        ### 🎯 Score Interpretation
        - **8.0-10.0**: Excellent choice
        - **6.0-7.9**: Good option
        - **4.0-5.9**: Acceptable with trade-offs
        - **0.0-3.9**: Consider carefully
        
        ### 📍 Map Legend
        - 🟢 **Green Star**: Excellent properties (8.0+ score)
        - 🔵 **Blue House**: Good properties (6.0-7.9 score)
        - 🟠 **Orange House**: Acceptable properties (4.0-5.9 score)
        - 🔴 **Red House**: Lower-scored properties (<4.0 score)
        
        ### 📈 Data Sources
        All scores use **real data**:
        - Austin crime statistics (2024)
        - WalkScore API data
        - HUD SAFMR affordability data
        - Geographic distance calculations
        
        **No synthetic or random data is used!**
        """)

if __name__ == "__main__":
    main()
