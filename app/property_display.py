"""
Property display and visualization module for Austin Housing dashboard.
Contains chart creation functions for the dashboard.
"""
import pandas as pd
import plotly.graph_objects as go
import logging
from property_scoring import PropertyScorer

logger = logging.getLogger(__name__)

class PropertyDisplay:
    """Handle property visualization and chart creation."""
    
    def __init__(self):
        self.scorer = PropertyScorer()
    
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
