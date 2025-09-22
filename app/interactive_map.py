"""
Interactive map component with two-stage interface:
1. ZIP code boundary view - clickable ZIP code areas
2. Property detail view - individual property pins with exact locations
"""
import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class InteractiveMap:
    def __init__(self):
        """Initialize the interactive map with ZIP code boundaries."""
        self.austin_center = [30.2672, -97.7431]
        self.zip_boundaries = None
        self.load_zip_boundaries()
    
    def load_zip_boundaries(self):
        """Load ZIP code boundary data."""
        try:
            zip_path = Path(__file__).parent.parent / "data" / "processed" / "austin_zip_boundaries.gpkg"
            if zip_path.exists():
                self.zip_boundaries = gpd.read_file(zip_path)
                logger.info(f"Loaded ZIP code boundaries: {len(self.zip_boundaries)} ZIP codes")
            else:
                logger.warning("ZIP code boundaries file not found")
        except Exception as e:
            logger.error(f"Error loading ZIP code boundaries: {e}")
    
    def create_zip_code_map(self, properties_df):
        """Create map showing ZIP code boundaries with property counts."""
        # Create base map
        m = folium.Map(
            location=self.austin_center,
            zoom_start=11,
            tiles='OpenStreetMap'
        )
        
        if self.zip_boundaries is not None:
            # Calculate property counts per ZIP code
            zip_counts = properties_df['zip_code'].value_counts().to_dict()
            
            # Add ZIP code boundaries to map
            for idx, row in self.zip_boundaries.iterrows():
                zip_code = str(row.get('ZCTA5CE10', row.get('zip_code', 'Unknown')))
                property_count = zip_counts.get(zip_code, 0)
                
                # Color based on property count
                if property_count > 500:
                    color = '#d73027'  # Red for high density
                    fillColor = '#fee08b'
                elif property_count > 100:
                    color = '#f46d43'  # Orange for medium density
                    fillColor = '#fee08b'
                elif property_count > 0:
                    color = '#74add1'  # Blue for low density
                    fillColor = '#e0f3f8'
                else:
                    color = '#999999'  # Gray for no properties
                    fillColor = '#f7f7f7'
                
                # Create popup with ZIP code info
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <b>ZIP Code: {zip_code}</b><br>
                    Properties: {property_count}<br>
                    <i>Click to select this area</i>
                </div>
                """
                
                # Add ZIP code polygon
                folium.GeoJson(
                    row.geometry,
                    style_function=lambda x, color=color, fillColor=fillColor: {
                        'fillColor': fillColor,
                        'color': color,
                        'weight': 2,
                        'fillOpacity': 0.6,
                        'opacity': 0.8
                    },
                    popup=folium.Popup(popup_text, max_width=200),
                    tooltip=f"ZIP {zip_code}: {property_count} properties"
                ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 150px; height: 90px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p><b>Property Density</b></p>
        <p><i class="fa fa-square" style="color:#d73027"></i> High (500+)</p>
        <p><i class="fa fa-square" style="color:#f46d43"></i> Medium (100-500)</p>
        <p><i class="fa fa-square" style="color:#74add1"></i> Low (1-100)</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m
    
    def create_property_detail_map(self, properties_df, selected_zips=None):
        """Create map showing individual property pins with exact locations."""
        # Filter properties if ZIP codes are selected
        if selected_zips:
            filtered_df = properties_df[properties_df['zip_code'].isin(selected_zips)]
        else:
            filtered_df = properties_df
        
        # Create base map
        m = folium.Map(
            location=self.austin_center,
            zoom_start=12,
            tiles='OpenStreetMap'
        )
        
        # Add individual property markers
        for idx, property_data in filtered_df.iterrows():
            lat = property_data.get('latitude', 0)
            lon = property_data.get('longitude', 0)
            
            # Skip properties without valid coordinates
            if lat == 0 or lon == 0 or pd.isna(lat) or pd.isna(lon):
                continue
            
            # Get property details
            address = property_data.get('address', 'Unknown Address')
            rent = property_data.get('rent', 0)
            bedrooms = property_data.get('bedrooms', 'N/A')
            bathrooms = property_data.get('bathrooms', 'N/A')
            sqft = property_data.get('sqft', 'N/A')
            overall_score = property_data.get('overall_score', 0)
            zip_code = property_data.get('zip_code', 'Unknown')
            
            # Color based on overall score
            if overall_score >= 7:
                color = 'green'
                icon = 'star'
            elif overall_score >= 5:
                color = 'orange'
                icon = 'home'
            else:
                color = 'red'
                icon = 'home'
            
            # Create detailed popup
            popup_html = f"""
            <div style="font-family: Arial; font-size: 12px; width: 250px;">
                <h4 style="margin: 0 0 10px 0; color: #333;">{address}</h4>
                <p style="margin: 5px 0;"><b>Rent:</b> ${rent:,.0f}/month</p>
                <p style="margin: 5px 0;"><b>Bedrooms:</b> {bedrooms}</p>
                <p style="margin: 5px 0;"><b>Bathrooms:</b> {bathrooms}</p>
                <p style="margin: 5px 0;"><b>Square Feet:</b> {sqft}</p>
                <p style="margin: 5px 0;"><b>ZIP Code:</b> {zip_code}</p>
                <p style="margin: 5px 0;"><b>Overall Score:</b> {overall_score:.1f}/10</p>
                <hr style="margin: 10px 0;">
                <p style="margin: 5px 0; font-size: 10px; color: #666;">
                    Lat: {lat:.4f}, Lon: {lon:.4f}
                </p>
            </div>
            """
            
            # Add property marker
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{address} - ${rent:,.0f}/mo",
                icon=folium.Icon(color=color, icon=icon, prefix='fa')
            ).add_to(m)
        
        # Add property count info
        info_html = f'''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 200px; height: 60px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p><b>Property Details View</b></p>
        <p>Showing {len(filtered_df)} individual properties</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(info_html))
        
        return m
    
    def create_hybrid_map(self, properties_df, zoom_level=11, selected_zips=None):
        """Create map that shows ZIP boundaries at low zoom and properties at high zoom."""
        if zoom_level <= 12:
            # Show ZIP code boundaries for overview
            return self.create_zip_code_map(properties_df)
        else:
            # Show individual properties for detail
            return self.create_property_detail_map(properties_df, selected_zips)
    
    def get_zip_codes_from_click(self, map_data):
        """Extract ZIP codes from map click events."""
        selected_zips = []
        
        if map_data and 'last_object_clicked_tooltip' in map_data:
            tooltip = map_data['last_object_clicked_tooltip']
            # Extract ZIP code from tooltip (format: "ZIP 78701: 123 properties")
            if 'ZIP ' in tooltip:
                try:
                    zip_code = tooltip.split('ZIP ')[1].split(':')[0].strip()
                    selected_zips.append(zip_code)
                except:
                    pass
        
        return selected_zips
