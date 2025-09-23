"""
Property scoring system for Austin Housing dashboard.
Calculates detailed scores for individual properties based on real data.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class PropertyScorer:
    """Calculate comprehensive scores for rental properties."""
    
    def __init__(self, custom_weights=None):
        self.root_dir = Path(__file__).parent.parent
        self.processed_data_dir = self.root_dir / "data" / "processed"
        
        # Load all data sources
        self._load_data_sources()
        
        # Default score weights (must sum to 1.0)
        self.default_weights = {
            'affordability': 0.30,
            'safety': 0.25,
            'accessibility': 0.20,
            'neighborhood': 0.15,
            'environment': 0.10
        }
        
        # Use custom weights if provided, otherwise use defaults
        self.weights = custom_weights if custom_weights else self.default_weights.copy()
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Update scoring weights. Weights must sum to 1.0."""
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.01:  # Allow small floating point errors
            raise ValueError(f"Weights must sum to 1.0, got {total:.3f}")
        self.weights = new_weights.copy()
    
    def get_default_weights(self) -> Dict[str, float]:
        """Get the default scoring weights."""
        return self.default_weights.copy()
    
    def _load_data_sources(self):
        """Load all data sources needed for scoring."""
        try:
            # Load ZIP coordinates
            zip_coords_path = self.processed_data_dir / "geocoded_zips.csv"
            self.zip_coords = pd.read_csv(zip_coords_path) if zip_coords_path.exists() else pd.DataFrame()
            
            # Load WalkScore data
            walkscore_path = self.processed_data_dir / "walkscore_data.csv"
            self.walkscore_data = pd.read_csv(walkscore_path) if walkscore_path.exists() else pd.DataFrame()
            
            # Load crime data
            crime_path = self.processed_data_dir / "austin_crime_2024.csv"
            self.crime_data = pd.read_csv(crime_path) if crime_path.exists() else pd.DataFrame()
            
            # Load ZIP to district mapping
            zip_district_path = self.processed_data_dir / "zip_district.csv"
            self.zip_district = pd.read_csv(zip_district_path) if zip_district_path.exists() else pd.DataFrame()
            
            # Load SAFMR data
            safmr_path = self.processed_data_dir / "austin_safmr_2024.csv"
            self.safmr_data = pd.read_csv(safmr_path) if safmr_path.exists() else pd.DataFrame()
            
            logger.info("Data sources loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading data sources: {e}")
            # Initialize empty DataFrames as fallback
            self.zip_coords = pd.DataFrame()
            self.walkscore_data = pd.DataFrame()
            self.crime_data = pd.DataFrame()
            self.zip_district = pd.DataFrame()
            self.safmr_data = pd.DataFrame()
    
    def get_affordability_score(self, rent: float, zip_code: str) -> Tuple[float, str]:
        """Calculate affordability score (0-10) and explanation."""
        try:
            # Budget constraint: $1500/month
            budget = 1500
            
            if rent > budget:
                return 0.0, f"Over budget: ${rent} > ${budget}"
            
            # Calculate score based on how much under budget
            savings = budget - rent
            savings_percentage = savings / budget
            
            # Score from 5-10 based on savings (more savings = better score)
            score = 5.0 + (savings_percentage * 5.0)
            score = min(score, 10.0)
            
            explanation = f"${savings:.0f} under budget ({savings_percentage:.1%} savings)"
            
            return score, explanation
            
        except Exception as e:
            logger.error(f"Error calculating affordability score: {e}")
            return 5.0, "Unable to calculate affordability"
    
    def get_safety_score(self, zip_code: str) -> Tuple[float, str]:
        """Calculate safety score (0-10) and explanation."""
        try:
            if self.zip_district.empty or self.crime_data.empty:
                return 5.0, "Safety data unavailable"
            
            # Find council district for ZIP
            zip_row = self.zip_district[self.zip_district['zip_code'] == float(zip_code)]
            if zip_row.empty:
                return 5.0, "ZIP code not found in safety data"
            
            council_district = zip_row['council_district'].iloc[0]
            
            # Find crime data for district
            crime_row = self.crime_data[self.crime_data['council_district'] == council_district]
            if crime_row.empty:
                return 5.0, "Crime data not found for district"
            
            incidents = crime_row['incidents'].iloc[0]
            
            # Normalize against all districts (lower incidents = higher score)
            max_incidents = self.crime_data['incidents'].max()
            min_incidents = self.crime_data['incidents'].min()
            
            if max_incidents > min_incidents:
                normalized = (incidents - min_incidents) / (max_incidents - min_incidents)
                # Invert: lower crime = higher score
                score = 10.0 * (1.0 - normalized)
            else:
                score = 5.0
            
            # Create explanation
            if score >= 8.0:
                explanation = f"Very safe area ({incidents} incidents)"
            elif score >= 6.0:
                explanation = f"Safe area ({incidents} incidents)"
            elif score >= 4.0:
                explanation = f"Moderate safety ({incidents} incidents)"
            else:
                explanation = f"Higher crime area ({incidents} incidents)"
            
            return score, explanation
            
        except Exception as e:
            logger.error(f"Error calculating safety score: {e}")
            return 5.0, "Unable to calculate safety score"
    
    def get_accessibility_score(self, zip_code: str) -> Tuple[float, str]:
        """Calculate accessibility score (0-10) and explanation."""
        try:
            if self.walkscore_data.empty:
                return 5.0, "Walkability data unavailable"
            
            # Find WalkScore data for ZIP
            zip_row = self.walkscore_data[self.walkscore_data['zip_code'] == float(zip_code)]
            if zip_row.empty:
                return 5.0, "Walkability data not found for ZIP"
            
            walk_score = zip_row['walk_score'].iloc[0]
            transit_score = zip_row['transit_score'].iloc[0]
            bike_score = zip_row['bike_score'].iloc[0]
            
            # Combine scores (walk score weighted most heavily)
            combined_score = (walk_score * 0.6) + (transit_score * 0.3) + (bike_score * 0.1)
            
            # Convert to 0-10 scale
            score = combined_score / 10.0
            
            # Create explanation
            walk_desc = zip_row['walk_description'].iloc[0] if 'walk_description' in zip_row.columns else "Unknown"
            explanation = f"{walk_desc} (Walk: {walk_score}, Transit: {transit_score})"
            
            return score, explanation
            
        except Exception as e:
            logger.error(f"Error calculating accessibility score: {e}")
            return 5.0, "Unable to calculate accessibility score"
    
    def get_neighborhood_score(self, zip_code: str) -> Tuple[float, str]:
        """Calculate neighborhood quality score (0-10) and explanation."""
        try:
            # Use walkability as proxy for neighborhood quality
            if self.walkscore_data.empty:
                return 5.0, "Neighborhood data unavailable"
            
            zip_row = self.walkscore_data[self.walkscore_data['zip_code'] == float(zip_code)]
            if zip_row.empty:
                return 5.0, "Neighborhood data not found for ZIP"
            
            walk_score = zip_row['walk_score'].iloc[0]
            
            # Convert walk score to neighborhood quality (0-10 scale)
            score = walk_score / 10.0
            
            # Create explanation based on walkability (proxy for amenities)
            if score >= 8.0:
                explanation = "Excellent amenities and walkability"
            elif score >= 6.0:
                explanation = "Good neighborhood amenities"
            elif score >= 4.0:
                explanation = "Moderate amenities nearby"
            else:
                explanation = "Limited neighborhood amenities"
            
            return score, explanation
            
        except Exception as e:
            logger.error(f"Error calculating neighborhood score: {e}")
            return 5.0, "Unable to calculate neighborhood score"
    
    def get_environment_score(self, zip_code: str) -> Tuple[float, str]:
        """Calculate environmental quality score (0-10) and explanation."""
        try:
            if self.zip_coords.empty:
                return 5.0, "Environmental data unavailable"
            
            # Find coordinates for ZIP
            zip_row = self.zip_coords[self.zip_coords['zip_code'] == float(zip_code)]
            if zip_row.empty:
                return 5.0, "ZIP coordinates not found"
            
            lat = zip_row['latitude'].iloc[0]
            lon = zip_row['longitude'].iloc[0]
            
            # Downtown Austin coordinates
            downtown_lat, downtown_lon = 30.2672, -97.7431
            
            # Calculate distance from downtown
            distance = ((lat - downtown_lat) ** 2 + (lon - downtown_lon) ** 2) ** 0.5
            
            # Convert distance to environmental score
            # Further from downtown = better environment (less pollution, noise)
            max_distance = 0.3  # Roughly 20 miles
            normalized_distance = min(distance / max_distance, 1.0)
            
            # Score: further = better environment
            score = 3.0 + (normalized_distance * 7.0)  # Range 3-10
            
            # Create explanation
            distance_miles = distance * 69  # Rough conversion to miles
            if score >= 8.0:
                explanation = f"Quiet suburban area ({distance_miles:.1f} mi from downtown)"
            elif score >= 6.0:
                explanation = f"Residential area ({distance_miles:.1f} mi from downtown)"
            elif score >= 4.0:
                explanation = f"Urban area ({distance_miles:.1f} mi from downtown)"
            else:
                explanation = f"Downtown area ({distance_miles:.1f} mi from center)"
            
            return score, explanation
            
        except Exception as e:
            logger.error(f"Error calculating environment score: {e}")
            return 5.0, "Unable to calculate environment score"
    
    def calculate_property_scores(self, property_data: Dict) -> Dict:
        """Calculate all scores for a property."""
        zip_code = str(property_data.get('zip_code', ''))
        rent = float(property_data.get('rent', 0))
        
        # Calculate individual scores
        affordability_score, affordability_explanation = self.get_affordability_score(rent, zip_code)
        safety_score, safety_explanation = self.get_safety_score(zip_code)
        accessibility_score, accessibility_explanation = self.get_accessibility_score(zip_code)
        neighborhood_score, neighborhood_explanation = self.get_neighborhood_score(zip_code)
        environment_score, environment_explanation = self.get_environment_score(zip_code)
        
        # Calculate weighted overall score
        overall_score = (
            affordability_score * self.weights['affordability'] +
            safety_score * self.weights['safety'] +
            accessibility_score * self.weights['accessibility'] +
            neighborhood_score * self.weights['neighborhood'] +
            environment_score * self.weights['environment']
        )
        
        return {
            'overall_score': round(overall_score, 1),
            'scores': {
                'affordability': {
                    'score': round(affordability_score, 1),
                    'explanation': affordability_explanation,
                    'weight': self.weights['affordability']
                },
                'safety': {
                    'score': round(safety_score, 1),
                    'explanation': safety_explanation,
                    'weight': self.weights['safety']
                },
                'accessibility': {
                    'score': round(accessibility_score, 1),
                    'explanation': accessibility_explanation,
                    'weight': self.weights['accessibility']
                },
                'neighborhood': {
                    'score': round(neighborhood_score, 1),
                    'explanation': neighborhood_explanation,
                    'weight': self.weights['neighborhood']
                },
                'environment': {
                    'score': round(environment_score, 1),
                    'explanation': environment_explanation,
                    'weight': self.weights['environment']
                }
            }
        }
    
    def get_zip_summary(self, zip_code: str) -> Dict:
        """Get summary statistics for a ZIP code."""
        try:
            # Calculate scores for the ZIP code
            dummy_property = {'zip_code': zip_code, 'rent': 1200}  # Use average rent for ZIP summary
            scores = self.calculate_property_scores(dummy_property)
            
            return {
                'zip_code': zip_code,
                'overall_score': scores['overall_score'],
                'safety_score': scores['scores']['safety']['score'],
                'accessibility_score': scores['scores']['accessibility']['score'],
                'neighborhood_score': scores['scores']['neighborhood']['score'],
                'environment_score': scores['scores']['environment']['score'],
                'safety_explanation': scores['scores']['safety']['explanation'],
                'accessibility_explanation': scores['scores']['accessibility']['explanation']
            }
            
        except Exception as e:
            logger.error(f"Error getting ZIP summary: {e}")
            return {
                'zip_code': zip_code,
                'overall_score': 5.0,
                'error': str(e)
            }
