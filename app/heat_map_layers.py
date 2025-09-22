"""
Independent heat map layers for Austin Housing dashboard.
Each layer can be controlled by opacity sliders (0=invisible, 1=full intensity).
"""
import pandas as pd
import folium
import streamlit as st

def create_safety_heat_map(boundaries, data_dict, zip_data, opacity):
    """
    Create red heat map layer for safety data.
    Higher crime = higher intensity (more red)
    """
    if opacity <= 0:
        return None
    
    # Create safety data for all ZIP codes with listings using real crime data
    safety_data = []
    for item in zip_data:
        zip_code = item['zip_code']
        # Get real safety intensity from crime data
        safety_intensity = get_safety_score_for_zip(zip_code, data_dict)
        safety_data.append({
            'zip_code': zip_code,
            'safety_intensity': safety_intensity
        })
    
    if not safety_data:
        return None
    
    safety_df = pd.DataFrame(safety_data)
    
    try:
        choropleth = folium.Choropleth(
            geo_data=boundaries,
            name='🔴 Safety Heat Map',
            data=safety_df,
            columns=['zip_code', 'safety_intensity'],
            key_on='feature.properties.ZCTA5CE20',
            fill_color='Reds',
            fill_opacity=opacity,
            line_opacity=0.1,
            line_color='white',
            line_weight=1,
            legend_name='Safety Risk (Red = More Dangerous)',
            smooth_factor=0
        )
        return choropleth
    except Exception as e:
        st.error(f"Error creating safety heat map: {e}")
        return None

def create_accessibility_heat_map(boundaries, data_dict, zip_data, opacity):
    """
    Create blue heat map layer for accessibility data.
    Lower walkability/transit = higher intensity (more blue)
    """
    if opacity <= 0:
        return None
    
    # Create accessibility data using real WalkScore data
    accessibility_data = []
    for item in zip_data:
        zip_code = item['zip_code']
        # Get real accessibility intensity from WalkScore data
        accessibility_intensity = get_accessibility_score_for_zip(zip_code)
        accessibility_data.append({
            'zip_code': zip_code,
            'accessibility_intensity': accessibility_intensity
        })
    
    if not accessibility_data:
        return None
    
    accessibility_df = pd.DataFrame(accessibility_data)
    
    try:
        choropleth = folium.Choropleth(
            geo_data=boundaries,
            name='🔵 Accessibility Heat Map',
            data=accessibility_df,
            columns=['zip_code', 'accessibility_intensity'],
            key_on='feature.properties.ZCTA5CE20',
            fill_color='Blues',
            fill_opacity=opacity,
            line_opacity=0.1,
            line_color='white',
            line_weight=1,
            legend_name='Accessibility (Blue = Less Accessible)',
            smooth_factor=0
        )
        return choropleth
    except Exception as e:
        st.error(f"Error creating accessibility heat map: {e}")
        return None

def create_neighborhood_heat_map(boundaries, data_dict, zip_data, opacity):
    """
    Create green heat map layer for neighborhood quality.
    Poor neighborhood quality = higher intensity (more green)
    Uses walkability scores as proxy for neighborhood amenities and quality.
    """
    if opacity <= 0:
        return None
    
    # Create neighborhood data using walkability as proxy for neighborhood quality
    neighborhood_data = []
    for item in zip_data:
        zip_code = item['zip_code']
        # Use inverse of walkability as neighborhood quality proxy
        # Higher walkability = better neighborhood = lower intensity (less green)
        neighborhood_intensity = get_neighborhood_score_for_zip(zip_code)
        neighborhood_data.append({
            'zip_code': zip_code,
            'neighborhood_intensity': neighborhood_intensity
        })
    
    if not neighborhood_data:
        return None
    
    neighborhood_df = pd.DataFrame(neighborhood_data)
    
    try:
        choropleth = folium.Choropleth(
            geo_data=boundaries,
            name='🟢 Neighborhood Heat Map',
            data=neighborhood_df,
            columns=['zip_code', 'neighborhood_intensity'],
            key_on='feature.properties.ZCTA5CE20',
            fill_color='Greens',
            fill_opacity=opacity,
            line_opacity=0.1,
            line_color='white',
            line_weight=1,
            legend_name='Neighborhood Quality (Green = Lower Quality)',
            smooth_factor=0
        )
        return choropleth
    except Exception as e:
        st.error(f"Error creating neighborhood heat map: {e}")
        return None

def create_environment_heat_map(boundaries, data_dict, zip_data, opacity):
    """
    Create yellow heat map layer for environmental risk.
    Higher environmental risk = higher intensity (more yellow)
    Uses distance from downtown as proxy for environmental factors.
    """
    if opacity <= 0:
        return None
    
    # Create environmental data using distance from downtown as proxy
    environment_data = []
    for item in zip_data:
        zip_code = item['zip_code']
        # Use distance from downtown as environmental risk proxy
        environment_intensity = get_environment_score_for_zip(zip_code)
        environment_data.append({
            'zip_code': zip_code,
            'environment_intensity': environment_intensity
        })
    
    if not environment_data:
        return None
    
    environment_df = pd.DataFrame(environment_data)
    
    try:
        choropleth = folium.Choropleth(
            geo_data=boundaries,
            name='🟡 Environment Heat Map',
            data=environment_df,
            columns=['zip_code', 'environment_intensity'],
            key_on='feature.properties.ZCTA5CE20',
            fill_color='YlOrRd',
            fill_opacity=opacity,
            line_opacity=0.1,
            line_color='white',
            line_weight=1,
            legend_name='Environmental Risk (Yellow = Higher Risk)',
            smooth_factor=0
        )
        return choropleth
    except Exception as e:
        st.error(f"Error creating environment heat map: {e}")
        return None

def create_combined_heat_map(boundaries, data_dict, zip_data, display_params):
    """
    Create a single combined heat map layer that blends all 4 data sources
    based on opacity settings. This eliminates flickering from multiple layer additions.
    """
    if not display_params or boundaries is None or boundaries.empty:
        return None
    
    try:
        # Get opacity weights
        safety_weight = display_params.get('safety_opacity', 0)
        accessibility_weight = display_params.get('accessibility_opacity', 0)
        neighborhood_weight = display_params.get('neighborhood_opacity', 0)
        environment_weight = display_params.get('environment_opacity', 0)
        
        # If all weights are 0, don't create any layer
        if safety_weight + accessibility_weight + neighborhood_weight + environment_weight == 0:
            return None
        
        # Create combined data for each ZIP code
        combined_data = []
        
        for item in zip_data:
            zip_code = item['zip_code']
            
            # Get individual scores (normalized 0-1)
            safety_score = get_safety_score(zip_code, data_dict) if safety_weight > 0 else 0
            accessibility_score = get_accessibility_score(zip_code) if accessibility_weight > 0 else 0
            neighborhood_score = get_neighborhood_score(zip_code) if neighborhood_weight > 0 else 0
            environment_score = get_environment_score(zip_code) if environment_weight > 0 else 0
            
            # Calculate weighted combined score
            total_weight = safety_weight + accessibility_weight + neighborhood_weight + environment_weight
            if total_weight > 0:
                combined_score = (
                    (safety_score * safety_weight) +
                    (accessibility_score * accessibility_weight) +
                    (neighborhood_score * neighborhood_weight) +
                    (environment_score * environment_weight)
                ) / total_weight
            else:
                combined_score = 0
            
            combined_data.append({
                'zip_code': zip_code,
                'combined_score': combined_score
            })
        
        # Create DataFrame for the combined layer
        df = pd.DataFrame(combined_data)
        
        # Determine color scheme based on dominant layer
        if safety_weight >= max(accessibility_weight, neighborhood_weight, environment_weight):
            colormap = 'Reds'
            name = 'Safety-Focused Heat Map'
        elif accessibility_weight >= max(neighborhood_weight, environment_weight):
            colormap = 'Blues'
            name = 'Accessibility-Focused Heat Map'
        elif neighborhood_weight >= environment_weight:
            colormap = 'Greens'
            name = 'Neighborhood-Focused Heat Map'
        else:
            colormap = 'YlOrRd'
            name = 'Environment-Focused Heat Map'
        
        # Create single choropleth layer
        choropleth = folium.Choropleth(
            geo_data=boundaries,
            data=df,
            columns=['zip_code', 'combined_score'],
            key_on='feature.properties.ZCTA5CE20',
            fill_color=colormap,
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name=name,
            smooth_factor=0
        )
        
        return choropleth
        
    except Exception as e:
        st.error(f"Error creating combined heat map: {e}")
        return None

def get_safety_score_for_zip(zip_code, data_dict):
    """Get safety intensity (0-100) for heat map visualization for a ZIP code."""
    try:
        # Load ZIP district mapping and crime data
        from pathlib import Path
        import pandas as pd
        
        ROOT_DIR = Path(__file__).parent.parent.parent
        PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
        
        # Load ZIP to district mapping
        zip_district_path = PROCESSED_DATA_DIR / "zip_district.csv"
        crime_path = PROCESSED_DATA_DIR / "austin_crime_2024.csv"
        
        if not zip_district_path.exists() or not crime_path.exists():
            return 50  # Default neutral score
        
        zip_district_df = pd.read_csv(zip_district_path)
        crime_df = pd.read_csv(crime_path)
        
        # Find council district for this ZIP code
        zip_row = zip_district_df[zip_district_df['zip_code'] == int(zip_code)]
        if zip_row.empty:
            return 50  # Default neutral score
        
        council_district = zip_row['council_district'].iloc[0]
        
        # Find crime incidents for this district
        crime_row = crime_df[crime_df['council_district'] == council_district]
        if crime_row.empty:
            return 50  # Default neutral score
        
        incidents = crime_row['incidents'].iloc[0]
        
        # Normalize to 0-100 scale (higher crime = higher intensity)
        max_incidents = crime_df['incidents'].max()
        min_incidents = crime_df['incidents'].min()
        
        if max_incidents > min_incidents:
            # Scale to 20-80 range for better visualization
            normalized = (incidents - min_incidents) / (max_incidents - min_incidents)
            safety_intensity = 20 + (normalized * 60)
        else:
            safety_intensity = 50
        
        return int(safety_intensity)
        
    except Exception as e:
        return 50  # Default neutral score on error

def get_safety_score(zip_code, data_dict):
    """Get normalized safety score (0-1) for a ZIP code."""
    try:
        # Use the same logic but return 0-1 scale
        intensity = get_safety_score_for_zip(zip_code, data_dict)
        # Convert from intensity (higher = more dangerous) to safety score (higher = safer)
        return 1.0 - ((intensity - 20) / 60)  # Invert the scale
    except:
        return 0.5

def get_accessibility_score_for_zip(zip_code):
    """Get accessibility intensity (0-100) for heat map visualization for a ZIP code."""
    try:
        # Load WalkScore data
        from pathlib import Path
        import pandas as pd
        
        ROOT_DIR = Path(__file__).parent.parent.parent
        PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
        
        # Load WalkScore data
        walkscore_path = PROCESSED_DATA_DIR / "walkscore_data.csv"
        
        if not walkscore_path.exists():
            return 50  # Default neutral score
        
        walkscore_df = pd.read_csv(walkscore_path)
        
        # Find WalkScore data for this ZIP code
        zip_row = walkscore_df[walkscore_df['zip_code'] == float(zip_code)]
        if zip_row.empty:
            return 50  # Default neutral score
        
        # Combine walk score and transit score for overall accessibility
        walk_score = zip_row['walk_score'].iloc[0]
        transit_score = zip_row['transit_score'].iloc[0]
        
        # Calculate combined accessibility score (weighted average)
        combined_score = (walk_score * 0.7) + (transit_score * 0.3)
        
        # Convert to intensity scale (lower accessibility = higher intensity for visualization)
        # Invert the scale so low walkability shows as high intensity (more blue)
        accessibility_intensity = 100 - combined_score
        
        # Scale to 20-80 range for better visualization
        scaled_intensity = 20 + (accessibility_intensity * 0.6)
        
        return int(scaled_intensity)
        
    except Exception as e:
        return 50  # Default neutral score on error

def get_accessibility_score(zip_code):
    """Get normalized accessibility score (0-1) for a ZIP code."""
    try:
        # Use the same logic but return 0-1 scale
        intensity = get_accessibility_score_for_zip(zip_code)
        # Convert from intensity (higher = less accessible) to accessibility score (higher = more accessible)
        return 1.0 - ((intensity - 20) / 60)  # Invert the scale
    except:
        return 0.5

def get_neighborhood_score_for_zip(zip_code):
    """Get neighborhood quality intensity (0-100) for heat map visualization for a ZIP code."""
    try:
        # Use walkability data as proxy for neighborhood quality
        # Higher walkability typically correlates with better amenities, transit, etc.
        from pathlib import Path
        import pandas as pd
        
        ROOT_DIR = Path(__file__).parent.parent.parent
        PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
        
        # Load WalkScore data
        walkscore_path = PROCESSED_DATA_DIR / "walkscore_data.csv"
        
        if not walkscore_path.exists():
            return 50  # Default neutral score
        
        walkscore_df = pd.read_csv(walkscore_path)
        
        # Find WalkScore data for this ZIP code
        zip_row = walkscore_df[walkscore_df['zip_code'] == float(zip_code)]
        if zip_row.empty:
            return 50  # Default neutral score
        
        # Use walk score as proxy for neighborhood quality
        walk_score = zip_row['walk_score'].iloc[0]
        
        # Convert to intensity scale (lower walkability = higher intensity for visualization)
        # Invert the scale so low walkability shows as high intensity (more green)
        neighborhood_intensity = 100 - walk_score
        
        # Scale to 20-80 range for better visualization
        scaled_intensity = 20 + (neighborhood_intensity * 0.6)
        
        return int(scaled_intensity)
        
    except Exception as e:
        return 50  # Default neutral score on error

def get_neighborhood_score(zip_code):
    """Get normalized neighborhood score (0-1) for a ZIP code."""
    try:
        # Use the same logic but return 0-1 scale
        intensity = get_neighborhood_score_for_zip(zip_code)
        # Convert from intensity (higher = worse neighborhood) to quality score (higher = better)
        return 1.0 - ((intensity - 20) / 60)  # Invert the scale
    except:
        return 0.5

def get_environment_score_for_zip(zip_code):
    """Get environmental risk intensity (0-100) for heat map visualization for a ZIP code."""
    try:
        # Use distance from downtown Austin as proxy for environmental risk
        # Closer to downtown = higher pollution, noise, etc. = higher environmental risk
        from pathlib import Path
        import pandas as pd
        
        ROOT_DIR = Path(__file__).parent.parent.parent
        PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
        
        # Load ZIP coordinates
        zip_coords_path = PROCESSED_DATA_DIR / "geocoded_zips.csv"
        
        if not zip_coords_path.exists():
            return 50  # Default neutral score
        
        zip_coords_df = pd.read_csv(zip_coords_path)
        
        # Find coordinates for this ZIP code
        zip_row = zip_coords_df[zip_coords_df['zip_code'] == float(zip_code)]
        if zip_row.empty:
            return 50  # Default neutral score
        
        lat = zip_row['latitude'].iloc[0]
        lon = zip_row['longitude'].iloc[0]
        
        # Downtown Austin coordinates
        downtown_lat, downtown_lon = 30.2672, -97.7431
        
        # Calculate distance from downtown (simple Euclidean distance)
        distance = ((lat - downtown_lat) ** 2 + (lon - downtown_lon) ** 2) ** 0.5
        
        # Convert distance to environmental risk intensity
        # Closer to downtown = higher risk = higher intensity
        # Scale distance (0-0.3 degrees ≈ 0-20 miles) to intensity (20-80)
        max_distance = 0.3  # Roughly 20 miles
        normalized_distance = min(distance / max_distance, 1.0)
        
        # Invert: closer = higher risk
        risk_factor = 1.0 - normalized_distance
        
        # Scale to 20-80 range for visualization
        environment_intensity = 20 + (risk_factor * 60)
        
        return int(environment_intensity)
        
    except Exception as e:
        return 50  # Default neutral score on error

def get_environment_score(zip_code):
    """Get normalized environment score (0-1) for a ZIP code."""
    try:
        # Use the same logic but return 0-1 scale
        intensity = get_environment_score_for_zip(zip_code)
        # Convert from intensity (higher = worse environment) to quality score (higher = better)
        return 1.0 - ((intensity - 20) / 60)  # Invert the scale
    except:
        return 0.5

def add_combined_heat_map_layer(map_obj, boundaries, data_dict, zip_data, display_params):
    """
    Add a single combined heat map layer to prevent flickering from multiple layers.
    """
    combined_layer = create_combined_heat_map(boundaries, data_dict, zip_data, display_params)
    if combined_layer:
        combined_layer.add_to(map_obj)
