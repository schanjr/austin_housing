"""
PyDeck-based clean map interface that maintains all original functionality.
Replaces Folium with PyDeck for better performance while keeping all features.
"""
import pydeck as pdk
import pandas as pd
import streamlit as st
import logging
from property_scoring import PropertyScorer

logger = logging.getLogger(__name__)

class PyDeckCleanMap:
    def __init__(self, custom_weights=None):
        """Initialize the PyDeck clean map interface."""
        self.austin_center = [30.2672, -97.7431]
        self.scorer = PropertyScorer(custom_weights=custom_weights)
    
    def create_property_map(self, properties_df, selected_zips=None):
        """Create a PyDeck map showing individual property pins with listing links."""
        # Filter properties if ZIP codes are selected
        if selected_zips:
            filtered_df = properties_df[properties_df['zip_code'].astype(str).isin([str(z) for z in selected_zips])]
        else:
            filtered_df = properties_df
        
        # Clean data - remove rows with missing coordinates
        filtered_df = filtered_df.dropna(subset=['latitude', 'longitude'])
        filtered_df = filtered_df[(filtered_df['latitude'] != 0) & (filtered_df['longitude'] != 0)]
        
        if filtered_df.empty:
            return None
        
        # Prepare data for PyDeck with color coding based on score
        map_data = []
        for idx, property_data in filtered_df.iterrows():
            lat = property_data.get('latitude', 0)
            lon = property_data.get('longitude', 0)
            overall_score = property_data.get('overall_score', 0)
            rent = property_data.get('rent', 0)
            address = property_data.get('address', 'Unknown Address')
            bedrooms = property_data.get('bedrooms', 'N/A')
            bathrooms = property_data.get('bathrooms', 'N/A')
            sqft = property_data.get('sqft', 'N/A')
            zip_code = property_data.get('zip_code', 'Unknown')
            listing_url = property_data.get('url', property_data.get('listing_url', ''))
            property_id = property_data.get('id', '')
            
            # Generate Redfin URL if we have property ID but no URL
            if not listing_url and property_id and 'redfin' in str(property_id).lower():
                numeric_id = str(property_id).replace('redfin-', '')
                listing_url = f"https://www.redfin.com/TX/Austin/{numeric_id}"
            
            # Color coding based on score (RGB values)
            if overall_score >= 7:
                color = [40, 167, 69, 200]  # Success green
            elif overall_score >= 5:
                color = [255, 193, 7, 200]  # Warning yellow
            else:
                color = [220, 53, 69, 200]  # Danger red
            
            # Get detailed score breakdown
            try:
                property_dict = {
                    'zip_code': zip_code,
                    'rent': rent
                }
                score_details = self.scorer.calculate_property_scores(property_dict)
                scores = score_details['scores']
                
                # Create detailed tooltip text
                tooltip_text = f"""
{address}
Rent: ${rent:,.0f}/mo | Score: {overall_score:.1f}/10
Beds: {bedrooms} | Baths: {bathrooms} | Sqft: {sqft}
ZIP: {zip_code}

Score Breakdown:
💰 Affordability: {scores['affordability']['score']:.1f}/10 ({scores['affordability']['weight']:.0%})
🛡️ Safety: {scores['safety']['score']:.1f}/10 ({scores['safety']['weight']:.0%})
🚶 Accessibility: {scores['accessibility']['score']:.1f}/10 ({scores['accessibility']['weight']:.0%})
🏘️ Neighborhood: {scores['neighborhood']['score']:.1f}/10 ({scores['neighborhood']['weight']:.0%})
🌿 Environment: {scores['environment']['score']:.1f}/10 ({scores['environment']['weight']:.0%})

{f'🏠 Click to view listing: {listing_url}' if listing_url else 'No listing URL available'}
                """.strip()
                
            except Exception as e:
                logger.error(f"Error calculating score breakdown: {e}")
                tooltip_text = f"""
{address}
Rent: ${rent:,.0f}/mo | Score: {overall_score:.1f}/10
Beds: {bedrooms} | Baths: {bathrooms} | Sqft: {sqft}
ZIP: {zip_code}

{f'🏠 Click to view listing: {listing_url}' if listing_url else 'No listing URL available'}
                """.strip()
            
            # Format values properly for PyDeck tooltips
            formatted_rent = f"{rent:,.0f}" if pd.notna(rent) and rent > 0 else "N/A"
            formatted_score = f"{overall_score:.1f}" if pd.notna(overall_score) else "N/A"
            formatted_bedrooms = str(int(bedrooms)) if pd.notna(bedrooms) else "N/A"
            formatted_bathrooms = str(int(bathrooms)) if pd.notna(bathrooms) else "N/A"
            formatted_sqft = str(int(sqft)) if pd.notna(sqft) and sqft > 0 else "N/A"
            
            # Create simple button text for tooltip (no JavaScript)
            if listing_url and listing_url != '#':
                button_html = '''<div style="background: #e31837; color: white; padding: 6px 12px; 
                                           border-radius: 4px; text-align: center; font-size: 11px; font-weight: 600;">
                                    🏠 Click property right side of the map to view listing
                                </div>'''
            else:
                button_html = '<p style="margin: 0; font-size: 11px; color: #666;">No listing URL available</p>'
            
            map_data.append({
                'latitude': lat,
                'longitude': lon,
                'address': address,
                'rent': formatted_rent,
                'overall_score': formatted_score,
                'bedrooms': formatted_bedrooms,
                'bathrooms': formatted_bathrooms,
                'sqft': formatted_sqft,
                'zip_code': str(zip_code),
                'listing_url': listing_url if listing_url else '#',
                'button_html': button_html,
                'color': color,
                'tooltip': tooltip_text,
                'size': 100  # Fixed size for all markers
            })
        
        # Convert to DataFrame for PyDeck
        map_df = pd.DataFrame(map_data)
        
        # Create ScatterplotLayer for individual properties
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            id="properties",  # Required for selection state
            get_position=["longitude", "latitude"],
            get_color="color",
            get_radius="size",
            pickable=True,
            auto_highlight=True,
            radius_scale=1,
            radius_min_pixels=8,
            radius_max_pixels=15
        )
        
        # Set viewport to Austin center
        view_state = pdk.ViewState(
            longitude=-97.7431,
            latitude=30.2672,
            zoom=11,
            min_zoom=8,
            max_zoom=16,
            pitch=0,
            bearing=0,
        )
        
        # Create deck with detailed tooltip
        deck = pdk.Deck(
            layers=[scatter_layer],
            initial_view_state=view_state,
            tooltip={
                "html": """
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                           font-size: 12px; padding: 15px; min-width: 300px; max-width: 400px;
                           background: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                    <h4 style="margin: 0 0 10px 0; color: #333; font-weight: 600; line-height: 1.3;">
                        {address}
                    </h4>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px;">
                        <div>
                            <p style="margin: 0; color: #666; font-size: 11px;">RENT</p>
                            <p style="margin: 0; font-weight: 600; font-size: 16px; color: #333;">
                                ${rent}<span style="font-size: 11px; color: #666;">/mo</span>
                            </p>
                        </div>
                        <div>
                            <p style="margin: 0; color: #666; font-size: 11px;">SCORE</p>
                            <p style="margin: 0; font-weight: 600; font-size: 16px; color: #333;">
                                {overall_score}/10
                            </p>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 10px;">
                        <div>
                            <p style="margin: 0; color: #666; font-size: 11px;">BEDS</p>
                            <p style="margin: 0; font-weight: 500; color: #333;">{bedrooms}</p>
                        </div>
                        <div>
                            <p style="margin: 0; color: #666; font-size: 11px;">BATHS</p>
                            <p style="margin: 0; font-weight: 500; color: #333;">{bathrooms}</p>
                        </div>
                        <div>
                            <p style="margin: 0; color: #666; font-size: 11px;">SQFT</p>
                            <p style="margin: 0; font-weight: 500; color: #333;">{sqft}</p>
                        </div>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 8px; border-radius: 5px; margin-bottom: 10px;">
                        <p style="margin: 0; color: #666; font-size: 11px;">LOCATION</p>
                        <p style="margin: 2px 0 0 0; font-size: 12px; color: #333;">
                            ZIP {zip_code}
                        </p>
                    </div>
                    
                    <div style="text-align: center; margin-top: 10px;">
                        {button_html}
                    </div>
                </div>
                """,
                "style": {"backgroundColor": "transparent", "color": "black"}
            }
        )
        
        # Store the map data for click handling
        self.current_map_data = map_df
        
        return deck
    
    def handle_map_click(self, clicked_data):
        """Handle map clicks to show listing links."""
        if clicked_data and 'index' in clicked_data:
            try:
                clicked_index = clicked_data['index']
                if hasattr(self, 'current_map_data') and clicked_index < len(self.current_map_data):
                    property_data = self.current_map_data.iloc[clicked_index]
                    listing_url = property_data.get('listing_url', '')
                    address = property_data.get('address', 'Unknown')
                    
                    if listing_url:
                        st.success(f"🏠 **{address}**")
                        st.markdown(f"[🔗 View Listing on Redfin]({listing_url})")
                    else:
                        st.info(f"🏠 **{address}** - No listing URL available")
                        
            except Exception as e:
                logger.error(f"Error handling map click: {e}")
    
    def create_overview_map(self, properties_df):
        """Create a clean overview map."""
        return self.create_property_map(properties_df)
    
    def create_detail_map(self, properties_df, selected_zips):
        """Create a detailed map focused on selected ZIP codes."""
        return self.create_property_map(properties_df, selected_zips)
