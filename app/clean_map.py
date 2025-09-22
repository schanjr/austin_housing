"""
Clean, modern map interface with intuitive usability and aesthetics.
Replaces the confusing bubble approach with a clean design.
"""
import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from pathlib import Path
import logging
from folium import plugins

logger = logging.getLogger(__name__)

class CleanMap:
    def __init__(self):
        """Initialize the clean map interface."""
        self.austin_center = [30.2672, -97.7431]
    
    def create_property_map(self, properties_df, selected_zips=None):
        """Create a clean map showing individual property pins with listing links."""
        # Create base map with clean styling
        m = folium.Map(
            location=self.austin_center,
            zoom_start=11,
            tiles=None
        )
        
        # Add clean base tiles
        folium.TileLayer(
            tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            name="Clean Base Map",
            overlay=False,
            control=True
        ).add_to(m)
        
        # Add property pins (no boundaries)
        self._add_property_pins(m, properties_df, selected_zips)
        
        # Add clean controls
        folium.LayerControl().add_to(m)
        
        # Add zoom to fit button
        plugins.Fullscreen().add_to(m)
        
        return m
    
    
    def _add_property_pins(self, m, properties_df, selected_zips):
        """Add individual property pins at exact geocoded locations."""
        # Filter properties if ZIP codes are selected
        if selected_zips:
            filtered_df = properties_df[properties_df['zip_code'].astype(str).isin([str(z) for z in selected_zips])]
        else:
            filtered_df = properties_df
        
        # Create a feature group for individual properties (NO CLUSTERING)
        property_group = folium.FeatureGroup(name="Individual Properties").add_to(m)
        
        # Debug: Count valid coordinates
        valid_coords = 0
        total_properties = len(filtered_df)
        
        # Add individual property markers
        for idx, property_data in filtered_df.iterrows():
            # Use standard coordinate columns from master dataset
            lat = property_data.get('latitude', 0)
            lon = property_data.get('longitude', 0)
            
            # Skip properties without valid coordinates
            if lat == 0 or lon == 0 or pd.isna(lat) or pd.isna(lon):
                continue
            
            valid_coords += 1
            
            # Get property details
            address = property_data.get('address', 'Unknown Address')
            rent = property_data.get('rent', 0)
            bedrooms = property_data.get('bedrooms', 'N/A')
            bathrooms = property_data.get('bathrooms', 'N/A')
            sqft = property_data.get('sqft', 'N/A')
            overall_score = property_data.get('overall_score', 0)
            zip_code = property_data.get('zip_code', 'Unknown')
            listing_url = property_data.get('url', property_data.get('listing_url', ''))
            property_id = property_data.get('id', '')
            
            # Generate Redfin URL if we have property ID but no URL
            if not listing_url and property_id and 'redfin' in str(property_id).lower():
                # Extract numeric ID from redfin ID format
                numeric_id = str(property_id).replace('redfin-', '')
                listing_url = f"https://www.redfin.com/TX/Austin/{numeric_id}"
            
            # Clean color coding based on score
            if overall_score >= 7:
                color = '#28a745'  # Success green
                icon_color = 'white'
                icon = 'star'
            elif overall_score >= 5:
                color = '#ffc107'  # Warning yellow
                icon_color = 'black'
                icon = 'home'
            else:
                color = '#dc3545'  # Danger red
                icon_color = 'white'
                icon = 'home'
            
            # Clean, detailed popup
            popup_html = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                        font-size: 14px; padding: 15px; min-width: 300px; max-width: 350px;">
                <h4 style="margin: 0 0 15px 0; color: #333; font-weight: 600; line-height: 1.3;">
                    {address}
                </h4>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                    <div>
                        <p style="margin: 0; color: #666; font-size: 12px;">RENT</p>
                        <p style="margin: 0; font-weight: 600; font-size: 18px; color: #333;">
                            ${rent:,.0f}<span style="font-size: 12px; color: #666;">/mo</span>
                        </p>
                    </div>
                    <div>
                        <p style="margin: 0; color: #666; font-size: 12px;">SCORE</p>
                        <p style="margin: 0; font-weight: 600; font-size: 18px; color: {color};">
                            {overall_score:.1f}/10
                        </p>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                    <div>
                        <p style="margin: 0; color: #666; font-size: 12px;">BEDS</p>
                        <p style="margin: 0; font-weight: 500; color: #333;">{bedrooms}</p>
                    </div>
                    <div>
                        <p style="margin: 0; color: #666; font-size: 12px;">BATHS</p>
                        <p style="margin: 0; font-weight: 500; color: #333;">{bathrooms}</p>
                    </div>
                    <div>
                        <p style="margin: 0; color: #666; font-size: 12px;">SQFT</p>
                        <p style="margin: 0; font-weight: 500; color: #333;">{sqft}</p>
                    </div>
                </div>
                
                <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                    <p style="margin: 0; color: #666; font-size: 12px;">LOCATION</p>
                    <p style="margin: 5px 0 0 0; font-size: 13px; color: #333;">
                        ZIP {zip_code} • {lat:.4f}, {lon:.4f}
                    </p>
                </div>
                
                {f'''<div style="text-align: center; margin-top: 15px;">
                    <a href="{listing_url}" target="_blank" 
                       style="display: inline-block; background: #e31837; color: white; 
                              padding: 10px 20px; text-decoration: none; border-radius: 5px; 
                              font-weight: 600; font-size: 14px;">
                        🏠 View on Redfin
                    </a>
                </div>''' if listing_url else ''}
            </div>
            """
            
            # Add individual marker at exact geocoded location (NO CLUSTERING)
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=400),
                tooltip=f"{address} • ${rent:,.0f}/mo • {overall_score:.1f}/10",
                icon=folium.Icon(
                    color='red' if overall_score < 5 else 'orange' if overall_score < 7 else 'green',
                    icon='home',
                    prefix='fa'
                )
            ).add_to(property_group)
        
        # Log debug info
        logger.info(f"Added {valid_coords} individual property markers out of {total_properties} total properties")
    
    def create_overview_map(self, properties_df):
        """Create a clean overview map."""
        return self.create_property_map(properties_df)
    
    def create_detail_map(self, properties_df, selected_zips):
        """Create a detailed map focused on selected ZIP codes."""
        return self.create_property_map(properties_df, selected_zips)
