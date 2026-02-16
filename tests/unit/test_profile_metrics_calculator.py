"""
Unit tests for profile_metrics_calculator module.
Tests the extracted helper functions for calculating player profile metrics.
"""

import pytest
import numpy as np
from src.ml.profile_metrics_calculator import ProfileMetricsCalculator, ProfileQueryBuilder


class TestPer36Stats:
    """Test per-36 minute statistics calculation."""
    
    def test_calculate_per_36_with_valid_minutes(self):
        """Test per-36 calculation with valid playing time."""
        total_minutes = 200.0
        totals = {
            'points': 100.0,
            'assists': 50.0,
            'rebounds': 80.0
        }
        
        result = ProfileMetricsCalculator.calculate_per_36_stats(total_minutes, totals)
        
        assert result['points_per_36'] == pytest.approx(18.0, rel=1e-2)  # 100 * 36 / 200
        assert result['assists_per_36'] == pytest.approx(9.0, rel=1e-2)  # 50 * 36 / 200
        assert result['rebounds_per_36'] == pytest.approx(14.4, rel=1e-2)  # 80 * 36 / 200
    
    def test_calculate_per_36_with_zero_minutes(self):
        """Test that zero minutes returns None for all stats."""
        total_minutes = 0.0
        totals = {'points': 100.0, 'assists': 50.0}
        
        result = ProfileMetricsCalculator.calculate_per_36_stats(total_minutes, totals)
        
        assert result['points_per_36'] is None
        assert result['assists_per_36'] is None
    
    def test_calculate_per_36_with_none_minutes(self):
        """Test that None minutes returns None for all stats."""
        total_minutes = None
        totals = {'points': 100.0, 'assists': 50.0}
        
        result = ProfileMetricsCalculator.calculate_per_36_stats(total_minutes, totals)
        
        assert result['points_per_36'] is None
        assert result['assists_per_36'] is None
    
    def test_calculate_per_36_with_none_values(self):
        """Test that None stat values result in 0."""
        total_minutes = 100.0
        totals = {
            'points': None,
            'assists': 20.0
        }
        
        result = ProfileMetricsCalculator.calculate_per_36_stats(total_minutes, totals)
        
        assert result['points_per_36'] == 0
        assert result['assists_per_36'] == pytest.approx(7.2, rel=1e-2)


class TestVariabilityMetrics:
    """Test variability and consistency metrics calculation."""
    
    def test_calculate_variability_with_valid_inputs(self):
        """Test variability calculation with valid inputs."""
        variance = 16.0  # std_dev = 4.0
        avg_value = 20.0
        num_games = 10
        
        std_dev, cv, stability_index = ProfileMetricsCalculator.calculate_variability_metrics(
            variance, avg_value, num_games
        )
        
        assert std_dev == pytest.approx(4.0, rel=1e-2)
        assert cv == pytest.approx(0.2, rel=1e-2)  # 4.0 / 20.0
        assert stability_index == pytest.approx(1.265, rel=1e-2)  # 4.0 / sqrt(10)
    
    def test_calculate_variability_with_zero_variance(self):
        """Test with zero variance (perfectly consistent)."""
        variance = 0.0
        avg_value = 20.0
        num_games = 10
        
        std_dev, cv, stability_index = ProfileMetricsCalculator.calculate_variability_metrics(
            variance, avg_value, num_games
        )
        
        assert std_dev == 0
        assert cv is None  # Cannot calculate CV with zero std_dev
        assert stability_index == 0
    
    def test_calculate_variability_with_none_variance(self):
        """Test with None variance."""
        variance = None
        avg_value = 20.0
        num_games = 10
        
        std_dev, cv, stability_index = ProfileMetricsCalculator.calculate_variability_metrics(
            variance, avg_value, num_games
        )
        
        assert std_dev == 0
        assert cv is None
        assert stability_index == 0
    
    def test_calculate_variability_with_zero_average(self):
        """Test with zero average value."""
        variance = 16.0
        avg_value = 0.0
        num_games = 10
        
        std_dev, cv, stability_index = ProfileMetricsCalculator.calculate_variability_metrics(
            variance, avg_value, num_games
        )
        
        assert std_dev == pytest.approx(4.0, rel=1e-2)
        assert cv is None  # Cannot divide by zero average
        assert stability_index == pytest.approx(1.265, rel=1e-2)


class TestMomentumIndex:
    """Test momentum index calculation."""
    
    def test_calculate_momentum_positive(self):
        """Test positive momentum (recent performance better)."""
        last_5_avg = 25.0
        last_10_avg = 20.0
        
        result = ProfileMetricsCalculator.calculate_momentum_index(last_5_avg, last_10_avg)
        
        assert result == pytest.approx(5.0, rel=1e-2)
    
    def test_calculate_momentum_negative(self):
        """Test negative momentum (declining performance)."""
        last_5_avg = 15.0
        last_10_avg = 20.0
        
        result = ProfileMetricsCalculator.calculate_momentum_index(last_5_avg, last_10_avg)
        
        assert result == pytest.approx(-5.0, rel=1e-2)
    
    def test_calculate_momentum_with_none_values(self):
        """Test that None values return None."""
        assert ProfileMetricsCalculator.calculate_momentum_index(None, 20.0) is None
        assert ProfileMetricsCalculator.calculate_momentum_index(25.0, None) is None
        assert ProfileMetricsCalculator.calculate_momentum_index(None, None) is None


class TestTrendSlope:
    """Test linear trend slope calculation."""
    
    def test_calculate_trend_slope_positive(self):
        """Test positive trend slope (improving)."""
        covariance_xy = 5.0
        variance_x = 2.0
        
        result = ProfileMetricsCalculator.calculate_trend_slope(covariance_xy, variance_x)
        
        assert result == pytest.approx(2.5, rel=1e-2)
    
    def test_calculate_trend_slope_negative(self):
        """Test negative trend slope (declining)."""
        covariance_xy = -3.0
        variance_x = 1.5
        
        result = ProfileMetricsCalculator.calculate_trend_slope(covariance_xy, variance_x)
        
        assert result == pytest.approx(-2.0, rel=1e-2)
    
    def test_calculate_trend_slope_with_zero_variance(self):
        """Test with zero variance returns None."""
        result = ProfileMetricsCalculator.calculate_trend_slope(5.0, 0.0)
        
        assert result is None
    
    def test_calculate_trend_slope_with_none_values(self):
        """Test with None values returns None."""
        assert ProfileMetricsCalculator.calculate_trend_slope(None, 2.0) is None
        assert ProfileMetricsCalculator.calculate_trend_slope(5.0, None) is None


class TestPlayerTeamRatios:
    """Test player-to-team ratio calculations."""
    
    def test_calculate_ratios_all_valid(self):
        """Test ratio calculation with all valid values."""
        player_totals = {
            'points': 500.0,
            'minutes': 600.0,
            'avg_ts': 0.60,
            'avg_usage': 25.0
        }
        team_totals = {
            'points': 2000.0,
            'minutes': 2400.0,
            'avg_ts': 0.55,
            'avg_usage': 100.0
        }
        
        result = ProfileMetricsCalculator.calculate_player_team_ratios(
            player_totals, team_totals
        )
        
        assert result['player_pts_share'] == pytest.approx(0.25, rel=1e-2)
        assert result['minutes_share'] == pytest.approx(0.25, rel=1e-2)
        assert result['efficiency_vs_team_avg'] == pytest.approx(1.091, rel=1e-2)
        assert result['player_usage_share'] == pytest.approx(0.25, rel=1e-2)
    
    def test_calculate_ratios_with_none_values(self):
        """Test that None values result in None ratios."""
        player_totals = {'points': None, 'minutes': 600.0}
        team_totals = {'points': 2000.0, 'minutes': None}
        
        result = ProfileMetricsCalculator.calculate_player_team_ratios(
            player_totals, team_totals
        )
        
        assert result['player_pts_share'] is None
        assert result['minutes_share'] is None
    
    def test_calculate_ratios_with_missing_keys(self):
        """Test with missing dictionary keys."""
        player_totals = {'points': 500.0}
        team_totals = {'points': 2000.0}
        
        result = ProfileMetricsCalculator.calculate_player_team_ratios(
            player_totals, team_totals
        )
        
        assert result['player_pts_share'] == pytest.approx(0.25, rel=1e-2)
        assert result['minutes_share'] is None
        assert result['efficiency_vs_team_avg'] is None
        assert result['player_usage_share'] is None


class TestPerformanceTier:
    """Test performance tier determination from z-scores."""
    
    def test_elite_tier(self):
        """Test elite tier classification."""
        assert ProfileMetricsCalculator.determine_performance_tier(2.0) == 'elite'
        assert ProfileMetricsCalculator.determine_performance_tier(1.6) == 'elite'
    
    def test_very_good_tier(self):
        """Test very good tier classification."""
        assert ProfileMetricsCalculator.determine_performance_tier(1.0) == 'very_good'
        assert ProfileMetricsCalculator.determine_performance_tier(0.6) == 'very_good'
    
    def test_above_average_tier(self):
        """Test above average tier classification."""
        assert ProfileMetricsCalculator.determine_performance_tier(0.2) == 'above_average'
        assert ProfileMetricsCalculator.determine_performance_tier(-0.3) == 'above_average'
    
    def test_average_tier(self):
        """Test average tier classification."""
        assert ProfileMetricsCalculator.determine_performance_tier(-0.8) == 'average'
        assert ProfileMetricsCalculator.determine_performance_tier(-1.2) == 'average'
    
    def test_below_average_tier(self):
        """Test below average tier classification."""
        assert ProfileMetricsCalculator.determine_performance_tier(-2.0) == 'below_average'
        assert ProfileMetricsCalculator.determine_performance_tier(-1.6) == 'below_average'
    
    def test_none_z_score(self):
        """Test that None returns average tier."""
        assert ProfileMetricsCalculator.determine_performance_tier(None) == 'average'


class TestNormalization:
    """Test stat value normalization."""
    
    def test_normalize_within_range(self):
        """Test normalization of value within range."""
        result = ProfileMetricsCalculator.normalize_stat_value(0.5, 0.0, 1.0)
        
        assert result == 0.5
    
    def test_normalize_below_minimum(self):
        """Test clipping to minimum value."""
        result = ProfileMetricsCalculator.normalize_stat_value(-0.5, 0.0, 1.0)
        
        assert result == 0.0
    
    def test_normalize_above_maximum(self):
        """Test clipping to maximum value."""
        result = ProfileMetricsCalculator.normalize_stat_value(1.5, 0.0, 1.0)
        
        assert result == 1.0
    
    def test_normalize_none_value(self):
        """Test that None values return None."""
        result = ProfileMetricsCalculator.normalize_stat_value(None, 0.0, 1.0)
        
        assert result is None


class TestCompositeScore:
    """Test composite score calculation."""
    
    def test_calculate_composite_equal_weights(self):
        """Test composite score with equal weights."""
        components = {
            'metric1': (80.0, 1.0),
            'metric2': (90.0, 1.0),
            'metric3': (70.0, 1.0)
        }
        
        result = ProfileMetricsCalculator.calculate_composite_score(components)
        
        assert result == pytest.approx(80.0, rel=1e-2)  # (80 + 90 + 70) / 3
    
    def test_calculate_composite_different_weights(self):
        """Test composite score with different weights."""
        components = {
            'metric1': (80.0, 2.0),
            'metric2': (90.0, 1.0),
            'metric3': (70.0, 1.0)
        }
        
        result = ProfileMetricsCalculator.calculate_composite_score(components)
        
        assert result == pytest.approx(80.0, rel=1e-2)  # (80*2 + 90*1 + 70*1) / 4
    
    def test_calculate_composite_zero_weights(self):
        """Test with all zero weights returns 0."""
        components = {
            'metric1': (80.0, 0.0),
            'metric2': (90.0, 0.0)
        }
        
        result = ProfileMetricsCalculator.calculate_composite_score(components)
        
        assert result == 0.0
    
    def test_calculate_composite_empty_dict(self):
        """Test with empty components dict."""
        components = {}
        
        result = ProfileMetricsCalculator.calculate_composite_score(components)
        
        assert result == 0.0


class TestOutlierDetection:
    """Test outlier game detection."""
    
    def test_detect_outliers_with_outliers(self):
        """Test detection of clear outliers."""
        game_values = [10, 12, 11, 10, 50, 11, 10, 12]  # 50 is outlier
        
        result = ProfileMetricsCalculator.detect_outlier_games(game_values, threshold_std=2.0)
        
        assert 4 in result  # Index of value 50
    
    def test_detect_outliers_without_outliers(self):
        """Test with no outliers present."""
        game_values = [10, 12, 11, 10, 13, 11, 10, 12]
        
        result = ProfileMetricsCalculator.detect_outlier_games(game_values, threshold_std=2.0)
        
        assert len(result) == 0
    
    def test_detect_outliers_insufficient_games(self):
        """Test with too few games returns empty list."""
        game_values = [10, 12]
        
        result = ProfileMetricsCalculator.detect_outlier_games(game_values)
        
        assert len(result) == 0
    
    def test_detect_outliers_empty_list(self):
        """Test with empty list returns empty list."""
        game_values = []
        
        result = ProfileMetricsCalculator.detect_outlier_games(game_values)
        
        assert len(result) == 0
    
    def test_detect_outliers_all_same_values(self):
        """Test with all identical values (zero std dev)."""
        game_values = [10, 10, 10, 10, 10]
        
        result = ProfileMetricsCalculator.detect_outlier_games(game_values)
        
        assert len(result) == 0


class TestProfileQueryBuilder:
    """Test SQL query builder for profile metrics."""
    
    def test_get_basic_stats_query(self):
        """Test basic stats query generation."""
        query = ProfileQueryBuilder.get_basic_stats_query()
        
        assert "SELECT" in query
        assert "COUNT(*) as games_played" in query
        assert "AVG(minutes_played)" in query
        assert "AVG(points)" in query
        assert "AVG(offensive_rating)" in query
        assert "player_game_stats" in query
        assert "WHERE player_id = ?" in query
    
    def test_get_rolling_windows_query(self):
        """Test rolling windows query generation."""
        query = ProfileQueryBuilder.get_rolling_windows_query()
        
        assert "WITH recent_games AS" in query
        assert "ROW_NUMBER() OVER" in query
        assert "CASE WHEN rn <= 5" in query
        assert "CASE WHEN rn <= 10" in query
        assert "last_5_pts" in query
        assert "last_10_pts" in query
    
    def test_get_trend_query(self):
        """Test trend calculation query generation."""
        query = ProfileQueryBuilder.get_trend_query()
        
        assert "WITH recent_trend AS" in query
        assert "ROW_NUMBER() OVER" in query
        assert "LIMIT 10" in query
        assert "AVG(points * rn)" in query
    
    def test_get_team_totals_query(self):
        """Test team totals query generation."""
        query = ProfileQueryBuilder.get_team_totals_query()
        
        assert "SELECT" in query
        assert "SUM(pgs.points) as team_total_pts" in query
        assert "AVG(pgs.true_shooting_pct) as team_avg_ts" in query
        assert "player_profiles pp ON" in query
        assert "WHERE pp.team_id = ?" in query


class TestIntegration:
    """Integration tests combining multiple calculations."""
    
    def test_complete_profile_metrics_calculation(self):
        """Test complete profile metrics workflow."""
        # Simulate player data
        total_minutes = 300.0
        totals = {'points': 150.0, 'assists': 60.0, 'rebounds': 90.0}
        
        # Calculate per-36 stats
        per_36 = ProfileMetricsCalculator.calculate_per_36_stats(total_minutes, totals)
        
        # Calculate variability
        variance = 25.0
        avg_value = 15.0
        num_games = 10
        std_dev, cv, stability = ProfileMetricsCalculator.calculate_variability_metrics(
            variance, avg_value, num_games
        )
        
        # Calculate momentum
        momentum = ProfileMetricsCalculator.calculate_momentum_index(18.0, 15.0)
        
        # Determine tier
        tier = ProfileMetricsCalculator.determine_performance_tier(1.2)
        
        # Verify all calculations completed
        assert per_36['points_per_36'] == pytest.approx(18.0, rel=1e-2)
        assert std_dev == pytest.approx(5.0, rel=1e-2)
        assert cv == pytest.approx(0.333, rel=1e-2)
        assert momentum == pytest.approx(3.0, rel=1e-2)
        assert tier == 'very_good'
    
    def test_edge_case_minimal_data(self):
        """Test with minimal/invalid data."""
        # Zero minutes
        per_36 = ProfileMetricsCalculator.calculate_per_36_stats(0, {'points': 10.0})
        assert per_36['points_per_36'] is None
        
        # No variance
        std_dev, cv, stability = ProfileMetricsCalculator.calculate_variability_metrics(0, 15.0, 5)
        assert std_dev == 0
        assert cv is None
        
        # None values
        momentum = ProfileMetricsCalculator.calculate_momentum_index(None, 15.0)
        assert momentum is None
