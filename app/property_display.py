"""
Property display and visualization module for Austin Housing dashboard.
Replaces complex heat maps with intuitive property-focused interface.
"""
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional
import logging
from property_scoring import PropertyScorer

logger = logging.getLogger(__name__)

class PropertyDisplay:
    """Handle property visualization and user interface."""
    
    def __init__(self):
        self.scorer = PropertyScorer()
        
    def create_property_map(self, properties_df: pd.DataFrame, selected_filters: Dict = None) -> folium.Map:
        """Create a clean map with property markers (no heat maps)."""
        try:
            # Center map on Austin
            austin_center = [30.2672, -97.7431]
            m = folium.Map(location=austin_center, zoom_start=11)
            
            # Apply filters if provided
            filtered_df = self._apply_filters(properties_df, selected_filters or {})
            
            # Add property markers
            for idx, property_data in filtered_df.iterrows():
                self._add_property_marker(m, property_data)
            
            return m
            
        except Exception as e:
            logger.error(f"Error creating property map: {e}")
            # Return basic map as fallback
            return folium.Map(location=[30.2672, -97.7431], zoom_start=11)
    
    def _apply_filters(self, df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
        """Apply user-selected filters to property data."""
        filtered_df = df.copy()
        
        try:
            # Rent range filter
            if 'max_rent' in filters and filters['max_rent']:
                filtered_df = filtered_df[filtered_df['rent'] <= filters['max_rent']]
            
            # Minimum score filters
            if 'min_overall_score' in filters and filters['min_overall_score']:
                filtered_df = filtered_df[filtered_df['overall_score'] >= filters['min_overall_score']]
            
            if 'min_safety_score' in filters and filters['min_safety_score']:
                filtered_df = filtered_df[filtered_df['safety_score'] >= filters['min_safety_score']]
            
            if 'min_walkability' in filters and filters['min_walkability']:
                filtered_df = filtered_df[filtered_df['accessibility_score'] >= filters['min_walkability']]
            
            # ZIP code filter
            if 'selected_zips' in filters and filters['selected_zips']:
                filtered_df = filtered_df[filtered_df['zip_code'].isin(filters['selected_zips'])]
            
            return filtered_df
            
        except Exception as e:
            logger.error(f"Error applying filters: {e}")
            return df
    
    def _add_property_marker(self, map_obj: folium.Map, property_data: pd.Series):
        """Add a single property marker to the map."""
        try:
            # Calculate scores for this property
            scores = self.scorer.calculate_property_scores(property_data.to_dict())
            
            # Determine marker color based on overall score
            overall_score = scores['overall_score']
            if overall_score >= 8.0:
                color = 'green'
                icon = 'star'
            elif overall_score >= 6.0:
                color = 'blue'
                icon = 'home'
            elif overall_score >= 4.0:
                color = 'orange'
                icon = 'home'
            else:
                color = 'red'
                icon = 'home'
            
            # Create detailed popup content
            popup_html = self._create_property_popup(property_data, scores)
            
            # Add marker
            folium.Marker(
                location=[property_data['latitude'], property_data['longitude']],
                popup=folium.Popup(popup_html, max_width=400),
                tooltip=f"${property_data['rent']}/month - Score: {overall_score}/10",
                icon=folium.Icon(color=color, icon=icon, prefix='fa')
            ).add_to(map_obj)
            
        except Exception as e:
            logger.error(f"Error adding property marker: {e}")
    
    def _create_property_popup(self, property_data: pd.Series, scores: Dict) -> str:
        """Create detailed HTML popup for property."""
        try:
            overall_score = scores['overall_score']
            score_details = scores['scores']
            
            # Build HTML popup
            html = f"""
            <div style="width: 350px; font-family: Arial, sans-serif;">
                <h4 style="margin: 0; color: #1f77b4;">🏠 {property_data.get('address', 'Property')}</h4>
                <p style="margin: 5px 0; font-size: 14px; color: #666;">
                    📍 ZIP {property_data.get('zip_code', 'Unknown')} | 
                    💰 ${property_data.get('rent', 0):,.0f}/month
                </p>
                
                <div style="background: #f0f8ff; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    <h5 style="margin: 0; color: #1f77b4;">📊 Overall Score: {overall_score}/10</h5>
                </div>
                
                <div style="margin: 10px 0;">
                    <h6 style="margin: 5px 0; color: #333;">Score Breakdown:</h6>
            """
            
            # Add individual scores
            score_icons = {
                'affordability': '💰',
                'safety': '🛡️',
                'accessibility': '🚶',
                'neighborhood': '🏛️',
                'environment': '🌱'
            }
            
            for category, details in score_details.items():
                score = details['score']
                explanation = details['explanation']
                weight = details['weight']
                icon = score_icons.get(category, '📊')
                
                # Color code the score
                if score >= 8.0:
                    score_color = '#28a745'  # Green
                elif score >= 6.0:
                    score_color = '#17a2b8'  # Blue
                elif score >= 4.0:
                    score_color = '#ffc107'  # Yellow
                else:
                    score_color = '#dc3545'  # Red
                
                html += f"""
                    <div style="margin: 5px 0; padding: 5px; background: #f8f9fa; border-radius: 3px;">
                        <span style="font-weight: bold;">{icon} {category.title()}</span>
                        <span style="color: {score_color}; font-weight: bold; float: right;">{score}/10</span>
                        <br>
                        <small style="color: #666;">{explanation}</small>
                        <small style="color: #999; float: right;">Weight: {weight:.0%}</small>
                    </div>
                """
            
            # Add property details if available
            if hasattr(property_data, 'bedrooms') and property_data.get('bedrooms'):
                html += f"<p><strong>🛏️ Bedrooms:</strong> {property_data['bedrooms']}</p>"
            
            if hasattr(property_data, 'source') and property_data.get('source'):
                html += f"<p><strong>🔗 Source:</strong> {property_data['source']}</p>"
            
            html += "</div>"
            
            return html
            
        except Exception as e:
            logger.error(f"Error creating property popup: {e}")
            return f"<div>Property: ${property_data.get('rent', 0)}/month</div>"
    
    def create_property_table(self, properties_df: pd.DataFrame, selected_filters: Dict = None) -> pd.DataFrame:
        """Create a sortable table of properties with scores."""
        try:
            # Apply filters
            filtered_df = self._apply_filters(properties_df, selected_filters or {})
            
            if filtered_df.empty:
                return pd.DataFrame()
            
            # Calculate scores for all properties
            scored_properties = []
            for idx, property_data in filtered_df.iterrows():
                scores = self.scorer.calculate_property_scores(property_data.to_dict())
                
                scored_property = {
                    'Address': property_data.get('address', 'Unknown'),
                    'ZIP': property_data.get('zip_code', ''),
                    'Rent': f"${property_data.get('rent', 0):,.0f}",
                    'Overall Score': f"{scores['overall_score']:.1f}/10",
                    'Safety': f"{scores['scores']['safety']['score']:.1f}/10",
                    'Walkability': f"{scores['scores']['accessibility']['score']:.1f}/10",
                    'Neighborhood': f"{scores['scores']['neighborhood']['score']:.1f}/10",
                    'Environment': f"{scores['scores']['environment']['score']:.1f}/10",
                    'Bedrooms': property_data.get('bedrooms', 'N/A'),
                    'Source': property_data.get('source', 'Unknown'),
                    # Keep numeric values for sorting
                    '_rent_numeric': property_data.get('rent', 0),
                    '_overall_numeric': scores['overall_score'],
                    '_safety_numeric': scores['scores']['safety']['score'],
                    '_walkability_numeric': scores['scores']['accessibility']['score'],
                    '_neighborhood_numeric': scores['scores']['neighborhood']['score'],
                    '_environment_numeric': scores['scores']['environment']['score']
                }
                scored_properties.append(scored_property)
            
            return pd.DataFrame(scored_properties)
            
        except Exception as e:
            logger.error(f"Error creating property table: {e}")
            return pd.DataFrame()
    
    def create_neighborhood_summary(self, properties_df: pd.DataFrame) -> pd.DataFrame:
        """Create neighborhood summary by ZIP code."""
        try:
            if properties_df.empty:
                return pd.DataFrame()
            
            # Group by ZIP code
            zip_groups = properties_df.groupby('zip_code')
            
            summaries = []
            for zip_code, group in zip_groups:
                try:
                    # Get ZIP summary from scorer
                    zip_summary = self.scorer.get_zip_summary(str(zip_code))
                    
                    # Calculate property statistics
                    avg_rent = group['rent'].mean()
                    property_count = len(group)
                    rent_range = f"${group['rent'].min():,.0f} - ${group['rent'].max():,.0f}"
                    
                    summary = {
                        'ZIP Code': zip_code,
                        'Properties': property_count,
                        'Avg Rent': f"${avg_rent:,.0f}",
                        'Rent Range': rent_range,
                        'Overall Score': f"{zip_summary.get('overall_score', 0):.1f}/10",
                        'Safety': f"{zip_summary.get('safety_score', 0):.1f}/10",
                        'Walkability': f"{zip_summary.get('accessibility_score', 0):.1f}/10",
                        'Neighborhood': f"{zip_summary.get('neighborhood_score', 0):.1f}/10",
                        'Environment': f"{zip_summary.get('environment_score', 0):.1f}/10",
                        'Best For': self._get_zip_recommendation(zip_summary),
                        # Keep numeric values for sorting
                        '_avg_rent_numeric': avg_rent,
                        '_overall_numeric': zip_summary.get('overall_score', 0),
                        '_safety_numeric': zip_summary.get('safety_score', 0),
                        '_walkability_numeric': zip_summary.get('accessibility_score', 0)
                    }
                    summaries.append(summary)
                except Exception as e:
                    logger.warning(f"Error processing ZIP {zip_code}: {e}")
                    # Add basic summary without scores
                    summary = {
                        'ZIP Code': zip_code,
                        'Properties': len(group),
                        'Avg Rent': f"${group['rent'].mean():,.0f}",
                        'Rent Range': f"${group['rent'].min():,.0f} - ${group['rent'].max():,.0f}",
                        'Overall Score': "N/A",
                        'Safety': "N/A",
                        'Walkability': "N/A",
                        'Neighborhood': "N/A",
                        'Environment': "N/A",
                        'Best For': "Data unavailable",
                        '_avg_rent_numeric': group['rent'].mean(),
                        '_overall_numeric': 0,
                        '_safety_numeric': 0,
                        '_walkability_numeric': 0
                    }
                    summaries.append(summary)
            
            return pd.DataFrame(summaries).sort_values('_overall_numeric', ascending=False)
            
        except Exception as e:
            logger.error(f"Error creating neighborhood summary: {e}")
            return pd.DataFrame()
    
    def _get_zip_recommendation(self, zip_summary: Dict) -> str:
        """Generate recommendation for what type of renter this ZIP is best for."""
        try:
            safety_score = zip_summary['safety_score']
            walkability_score = zip_summary['accessibility_score']
            neighborhood_score = zip_summary['neighborhood_score']
            environment_score = zip_summary['environment_score']
            
            recommendations = []
            
            if walkability_score >= 7.0:
                recommendations.append("Car-free living")
            if safety_score >= 8.0:
                recommendations.append("Families")
            if neighborhood_score >= 7.0:
                recommendations.append("Young professionals")
            if environment_score >= 7.0:
                recommendations.append("Quiet lifestyle")
            if walkability_score >= 6.0 and neighborhood_score >= 6.0:
                recommendations.append("Urban convenience")
            
            if not recommendations:
                if safety_score >= 6.0:
                    recommendations.append("Budget-conscious")
                else:
                    recommendations.append("Value seekers")
            
            return ", ".join(recommendations[:2])  # Limit to 2 recommendations
            
        except Exception as e:
            logger.error(f"Error generating ZIP recommendation: {e}")
            return "General living"
    
    def create_score_distribution_chart(self, properties_df: pd.DataFrame) -> go.Figure:
        """Create a chart showing score distributions."""
        try:
            if properties_df.empty:
                return go.Figure()
            
            # Calculate scores for all properties
            all_scores = []
            for idx, property_data in properties_df.iterrows():
                scores = self.scorer.calculate_property_scores(property_data.to_dict())
                all_scores.append({
                    'Overall': scores['overall_score'],
                    'Safety': scores['scores']['safety']['score'],
                    'Walkability': scores['scores']['accessibility']['score'],
                    'Neighborhood': scores['scores']['neighborhood']['score'],
                    'Environment': scores['scores']['environment']['score']
                })
            
            scores_df = pd.DataFrame(all_scores)
            
            # Create box plot
            fig = go.Figure()
            
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
            for i, column in enumerate(scores_df.columns):
                fig.add_trace(go.Box(
                    y=scores_df[column],
                    name=column,
                    marker_color=colors[i % len(colors)]
                ))
            
            fig.update_layout(
                title="Score Distribution Across All Properties",
                yaxis_title="Score (0-10)",
                xaxis_title="Score Category",
                height=400
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating score distribution chart: {e}")
            return go.Figure()
    
    def render_filter_sidebar(self) -> Dict:
        """Render filter controls in sidebar and return selected filters."""
        st.sidebar.header("🔍 Property Filters")
        
        filters = {}
        
        # Rent filter
        filters['max_rent'] = st.sidebar.slider(
            "Maximum Rent",
            min_value=500,
            max_value=5000,
            value=1500,
            step=50,
            help="Filter properties by maximum monthly rent"
        )
        
        # Score filters
        st.sidebar.subheader("Minimum Scores")
        
        filters['min_overall_score'] = st.sidebar.slider(
            "Overall Score",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.5,
            help="Minimum overall livability score"
        )
        
        filters['min_safety_score'] = st.sidebar.slider(
            "Safety Score",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.5,
            help="Minimum safety score"
        )
        
        filters['min_walkability'] = st.sidebar.slider(
            "Walkability Score",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.5,
            help="Minimum walkability/accessibility score"
        )
        
        # ZIP code filter
        if hasattr(self.scorer, 'zip_coords') and not self.scorer.zip_coords.empty:
            available_zips = sorted(self.scorer.zip_coords['zip_code'].unique())
            filters['selected_zips'] = st.sidebar.multiselect(
                "ZIP Codes",
                options=available_zips,
                default=[],
                help="Select specific ZIP codes (leave empty for all)"
            )
        
        return filters
