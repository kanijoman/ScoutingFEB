"""
Profile Metrics Calculator Module

Extracted helper functions for calculating player profile metrics.
Breaks down complex aggregation logic into testable, reusable components.
"""

from typing import Dict, Optional, Tuple
import logging


class ProfileMetricsCalculator:
    """
    Helper class for calculating player profile metrics.
    
    Provides static methods for computing various performance metrics
    from raw game statistics.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize calculator with optional logger."""
        self.logger = logger or logging.getLogger(__name__)
    
    @staticmethod
    def calculate_per_36_stats(
        total_minutes: Optional[float],
        totals: Dict[str, Optional[float]]
    ) -> Dict[str, Optional[float]]:
        """
        Calculate per-36 minute statistics.
        
        Normalizes counting stats to a 36-minute game for comparison
        across players with different playing time.
        
        Args:
            total_minutes: Total minutes played
            totals: Dictionary of total stats (points, assists, rebounds, etc.)
            
        Returns:
            Dictionary with per-36 versions of all stats
        """
        per_36 = {}
        
        if total_minutes and total_minutes > 0:
            factor_36 = 36.0 / total_minutes
            
            for stat_name, total_value in totals.items():
                per_36_name = f"{stat_name}_per_36"
                per_36[per_36_name] = (total_value * factor_36) if total_value else 0
        else:
            # Set all to None if no minutes
            for stat_name in totals.keys():
                per_36[f"{stat_name}_per_36"] = None
        
        return per_36
    
    @staticmethod
    def calculate_variability_metrics(
        variance: Optional[float],
        avg_value: Optional[float],
        num_games: int
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate variability and consistency metrics.
        
        Args:
            variance: Variance of the stat
            avg_value: Average value of the stat
            num_games: Number of games
            
        Returns:
            Tuple of (std_dev, coefficient_of_variation, stability_index)
        """
        # Standard deviation
        std_dev = (variance ** 0.5) if (variance is not None and variance > 0) else 0
        
        # Coefficient of variation (CV)
        cv = None
        if avg_value and avg_value > 0 and std_dev > 0:
            cv = std_dev / avg_value
        
        # Stability index (lower is more stable)
        stability_index = None
        if num_games > 0 and std_dev is not None:
            stability_index = std_dev / (num_games ** 0.5)
        
        return std_dev, cv, stability_index
    
    @staticmethod
    def calculate_momentum_index(
        last_5_avg: Optional[float],
        last_10_avg: Optional[float]
    ) -> Optional[float]:
        """
        Calculate momentum index (recent vs slightly older performance).
        
        Positive values indicate improving performance, negative indicate decline.
        
        Args:
            last_5_avg: Average from last 5 games
            last_10_avg: Average from last 10 games
            
        Returns:
            Momentum index (difference between recent and older average)
        """
        if last_5_avg is not None and last_10_avg is not None:
            return last_5_avg - last_10_avg
        return None
    
    @staticmethod
    def calculate_trend_slope(
        covariance_xy: Optional[float],
        variance_x: Optional[float]
    ) -> Optional[float]:
        """
        Calculate linear trend slope.
        
        Used to determine if performance is trending up or down over time.
        
        Args:
            covariance_xy: Covariance between game number and performance
            variance_x: Variance of game numbers
            
        Returns:
            Slope of the trend line (positive = improving)
        """
        if covariance_xy is not None and variance_x and variance_x != 0:
            return covariance_xy / variance_x
        return None
    
    @staticmethod
    def calculate_player_team_ratios(
        player_totals: Dict[str, Optional[float]],
        team_totals: Dict[str, Optional[float]]
    ) -> Dict[str, Optional[float]]:
        """
        Calculate player contribution ratios relative to team.
        
        Args:
            player_totals: Player's total stats
            team_totals: Team's total stats
            
        Returns:
            Dictionary with ratio metrics (pts_share, minutes_share, etc.)
        """
        ratios = {}
        
        # Points share
        if team_totals.get('points') and player_totals.get('points'):
            ratios['player_pts_share'] = player_totals['points'] / team_totals['points']
        else:
            ratios['player_pts_share'] = None
        
        # Minutes share
        if team_totals.get('minutes') and player_totals.get('minutes'):
            ratios['minutes_share'] = player_totals['minutes'] / team_totals['minutes']
        else:
            ratios['minutes_share'] = None
        
        # Efficiency vs team average
        if team_totals.get('avg_ts') and player_totals.get('avg_ts'):
            ratios['efficiency_vs_team_avg'] = player_totals['avg_ts'] / team_totals['avg_ts']
        else:
            ratios['efficiency_vs_team_avg'] = None
        
        # Usage share
        if team_totals.get('avg_usage') and player_totals.get('avg_usage'):
            ratios['player_usage_share'] = player_totals['avg_usage'] / team_totals['avg_usage']
        else:
            ratios['player_usage_share'] = None
        
        return ratios
    
    @staticmethod
    def determine_performance_tier(avg_z_score: Optional[float]) -> str:
        """
        Determine performance tier from z-score.
        
        Args:
            avg_z_score: Average z-score (typically of offensive rating)
            
        Returns:
            Tier string: 'elite', 'very_good', 'above_average', 'average', or 'below_average'
        """
        if avg_z_score is None:
            return 'average'
        
        if avg_z_score > 1.5:
            return 'elite'
        elif avg_z_score > 0.5:
            return 'very_good'
        elif avg_z_score > -0.5:
            return 'above_average'
        elif avg_z_score > -1.5:
            return 'average'
        else:
            return 'below_average'
    
    @staticmethod
    def normalize_stat_value(
        value: Optional[float],
        min_val: float = 0.0,
        max_val: float = 1.0
    ) -> Optional[float]:
        """
        Normalize a stat value to a given range.
        
        Args:
            value: Value to normalize
            min_val: Minimum of target range
            max_val: Maximum of target range
            
        Returns:
            Normalized value, or None if input is None
        """
        if value is None:
            return None
        
        # Simple clipping for now (could be extended with percentile-based normalization)
        if value < min_val:
            return min_val
        elif value > max_val:
            return max_val
        else:
            return value
    
    @staticmethod
    def calculate_composite_score(
        components: Dict[str, Tuple[float, float]]
    ) -> float:
        """
        Calculate weighted composite score from multiple components.
        
        Args:
            components: Dict mapping component name to (value, weight) tuples
            
        Returns:
            Weighted average score
        """
        total_weight = sum(weight for _, weight in components.values())
        
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(value * weight for value, weight in components.values())
        return weighted_sum / total_weight
    
    @staticmethod
    def detect_outlier_games(
        game_values: list,
        threshold_std: float = 2.5
    ) -> list:
        """
        Detect outlier games (unusually good or bad performances).
        
        Args:
            game_values: List of performance values across games
            threshold_std: Number of standard deviations to consider outlier
            
        Returns:
            List of indices of outlier games
        """
        if not game_values or len(game_values) < 3:
            return []
        
        import numpy as np
        
        values = np.array(game_values)
        mean = np.mean(values)
        std = np.std(values)
        
        if std == 0:
            return []
        
        z_scores = np.abs((values - mean) / std)
        outlier_indices = [i for i, z in enumerate(z_scores) if z > threshold_std]
        
        return outlier_indices


class ProfileQueryBuilder:
    """
    Helper class for building SQL queries for profile metrics.
    
    Centralizes query construction to maintain consistency and reduce duplication.
    """
    
    @staticmethod
    def get_basic_stats_query() -> str:
        """Get query for basic aggregated stats."""
        return """
            SELECT 
                COUNT(*) as games_played,
                SUM(minutes_played) as total_minutes,
                AVG(minutes_played) as avg_minutes,
                AVG(points) as avg_points,
                AVG(offensive_rating) as avg_offensive_rating,
                AVG(player_efficiency_rating) as avg_per,
                AVG(true_shooting_pct) as avg_ts_pct,
                AVG(z_offensive_rating) as avg_z_oer,
                AVG(z_player_efficiency_rating) as avg_z_per,
                AVG(z_minutes) as avg_z_minutes,
                AVG((offensive_rating - (SELECT AVG(offensive_rating) FROM player_game_stats WHERE player_id = ?)) * 
                    (offensive_rating - (SELECT AVG(offensive_rating) FROM player_game_stats WHERE player_id = ?))) as var_oer,
                AVG((points - (SELECT AVG(points) FROM player_game_stats WHERE player_id = ?)) * 
                    (points - (SELECT AVG(points) FROM player_game_stats WHERE player_id = ?))) as var_points,
                SUM(points) as total_points,
                SUM(assists) as total_assists,
                SUM(total_rebounds) as total_rebounds,
                SUM(steals) as total_steals,
                SUM(blocks) as total_blocks,
                SUM(turnovers) as total_turnovers,
                SUM(field_goals_made) as total_fgm,
                SUM(field_goals_attempted) as total_fga,
                SUM(three_points_made) as total_3pm
            FROM player_game_stats
            WHERE player_id = ?
        """
    
    @staticmethod
    def get_rolling_windows_query() -> str:
        """Get query for rolling window statistics."""
        return """
            WITH recent_games AS (
                SELECT pgs.points, pgs.offensive_rating, g.game_date,
                       ROW_NUMBER() OVER (ORDER BY g.game_date DESC) as rn
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.game_id
                WHERE pgs.player_id = ?
            )
            SELECT 
                AVG(CASE WHEN rn <= 5 THEN points END) as last_5_pts,
                AVG(CASE WHEN rn <= 5 THEN offensive_rating END) as last_5_oer,
                AVG(CASE WHEN rn <= 10 THEN points END) as last_10_pts,
                AVG(CASE WHEN rn <= 10 THEN offensive_rating END) as last_10_oer
            FROM recent_games
        """
    
    @staticmethod
    def get_trend_query() -> str:
        """Get query for trend calculation."""
        return """
            WITH recent_trend AS (
                SELECT pgs.points, g.game_date,
                       ROW_NUMBER() OVER (ORDER BY g.game_date DESC) as rn
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.game_id
                WHERE pgs.player_id = ?
                LIMIT 10
            )
            SELECT AVG(points * rn) - AVG(points) * AVG(rn),
                   AVG(rn * rn) - AVG(rn) * AVG(rn)
            FROM recent_trend
        """
    
    @staticmethod
    def get_team_totals_query() -> str:
        """Get query for team aggregate stats."""
        return """
            SELECT 
                SUM(pgs.points) as team_total_pts,
                SUM(pgs.minutes_played) as team_total_minutes,
                AVG(pgs.true_shooting_pct) as team_avg_ts,
                AVG(pgs.usage_rate) as team_avg_usage
            FROM player_game_stats pgs
            JOIN player_profiles pp ON pgs.player_id = pp.profile_id
            WHERE pp.team_id = ? AND pp.season = ?
        """
