"""
Helper module for displaying rental listings in the dashboard.
"""
import streamlit as st
from src.data.listing_loader import listing_loader

def show_rental_listings(zip_code, max_rent, bedroom_preferences):
    """Show rental listings for a specific ZIP code using ListingLoader"""
    st.subheader(f"Rental Listings for ZIP Code {zip_code}")
    
    with st.spinner(f"Loading rental listings for ZIP code {zip_code}..."):
        # Get all listings using ListingLoader (only Redfin data - Zillow is disabled)
        listings = listing_loader.get_listings(
            zip_code=zip_code, 
            max_rent=max_rent, 
            bedrooms=bedroom_preferences
        )
    
    if listings.empty:
        st.warning(f"No rental listings found for ZIP code {zip_code} with your criteria.")
        return
    
    # Count listings by source (only Redfin - Zillow is disabled)
    redfin_count = len(listings[listings['source'] == 'redfin']) if 'source' in listings.columns else len(listings)
    
    st.write(f"Found {len(listings)} Redfin rental listings under ${max_rent}/month")
    
    # Only show Redfin listings (Zillow is completely disabled)
    display_listings(listings)

def display_listings(listings):
    """Display rental listings in a grid"""
    # Display listings in a grid
    cols = st.columns(2)
    for i, (_, listing) in enumerate(listings.iterrows()):
        col = cols[i % 2]
        with col:
            with st.container():
                # Only Redfin listings (Zillow is disabled)
                source_color = "#a02021"  # Redfin red
                source_name = "Redfin"
                
                st.markdown(f"""
                <div style="border:1px solid #e0e0e0; border-radius:0.5rem; padding:1rem; margin-bottom:1rem; background-color:white;">
                    <div style="font-size:0.8rem; color:white; background-color:{source_color}; padding:2px 8px; border-radius:3px; display:inline-block; margin-bottom:5px;">{source_name}</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:#1E88E5;">${listing['rent']}/month</div>
                    <div style="font-weight:bold;">{listing['address']}, {listing['zip_code']}</div>
                    <div style="color:#616161;">
                        {int(listing['bedrooms'])} BR | {listing['bathrooms']} BA | {listing.get('sqft', 'N/A')} sqft
                    </div>
                    <div>Available: {listing.get('available_date', 'Now')}</div>
                    <a href="{listing.get('listing_url', f'https://www.redfin.com/zipcode/{listing["zip_code"]}/rentals')}" target="_blank">View on Redfin</a>
                </div>
                """, unsafe_allow_html=True)
