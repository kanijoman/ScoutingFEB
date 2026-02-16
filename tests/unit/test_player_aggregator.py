"""
Unit tests for player_aggregator module.
Tests the extracted helper functions for aggregating player statistics.
"""

import pytest
import numpy as np
from src.ml.player_aggregator import StatsExtractor, StatsAggregator, AggregationQueryBuilder


class TestStatsExtractor:
    """Test StatsExtractor helper class."""
    
    def test_extract_basic_stats(self):
        """Test basic stats extraction from dictionary list."""
        stats = [
            {
                "minutes_played": 30, "points": 15, "efficiency_rating": 20.5,
                "field_goal_pct": 0.45, "three_point_pct": 0.33, "free_throw_pct": 0.80,
                "total_rebounds": 8, "assists": 5, "team_won": 1
            },
            {
                "minutes_played": 25, "points": 12, "efficiency_rating": 18.0,
                "field_goal_pct": 0.50, "three_point_pct": 0.40, "free_throw_pct": 0.75,
                "total_rebounds": 6, "assists": 4, "team_won": 0
            },
            {
                "minutes_played": 28, "points": 18, "efficiency_rating": 22.0,
                "field_goal_pct": 0.48, "three_point_pct": 0.35, "free_throw_pct": 0.85,
                "total_rebounds": 7, "assists": 6, "team_won": 1
            }
        ]
        
        result = StatsExtractor.extract_basic_stats(stats)
        
        assert 'minutes' in result
        assert 'points' in result
        assert 'efficiency' in result
        assert len(result['minutes']) == 3
        assert result['points'][0] == 15
        assert result['minutes'][1] == 25
        assert result['wins'][2] == 1
        
    def test_extract_basic_stats_empty(self):
        """Test extraction with empty stats."""
        stats = []
        
        result = StatsExtractor.extract_basic_stats(stats)
        
        assert isinstance(result, dict)
        assert len(result['minutes']) == 0
    
    def test_extract_advanced_stats(self):
        """Test advanced stats extraction with None handling."""
        stats = [
            {
                "true_shooting_pct": 0.58, "effective_fg_pct": 0.52,
                "offensive_rating": 110.0, "player_efficiency_rating": 18.5,
                "turnover_pct": 12.0, "offensive_rebound_pct": 8.0,
                "defensive_rebound_pct": 22.0, "win_shares": 0.15,
                "win_shares_per_36": 0.18
            },
            {
                "true_shooting_pct": None, "effective_fg_pct": None,
                "offensive_rating": None, "player_efficiency_rating": None,
                "turnover_pct": None, "offensive_rebound_pct": None,
                "defensive_rebound_pct": None, "win_shares": None,
                "win_shares_per_36": None
            }
        ]
        
        result = StatsExtractor.extract_advanced_stats(stats)
        
        assert result['ts_pct'][0] == 0.58
        assert result['ts_pct'][1] == 0  # None replaced with 0
        assert result['per'][0] == 18.5
        assert result['ws'][0] == 0.15
        assert result['ws'][1] == 0  # None replaced with 0


class TestStatsAggregator:
    """Test StatsAggregator helper class."""
    
    def test_calculate_basic_averages(self):
        """Test basic averages calculation."""
        basic_stats = {
            'minutes': np.array([30, 25, 28]),
            'points': np.array([15, 12, 18]),
            'efficiency': np.array([20.5, 18.0, 22.0]),
            'fg_pct': np.array([0.45, 0.50, 0.48]),
            'three_pct': np.array([0.33, 0.40, 0.35]),
            'ft_pct': np.array([0.80, 0.75, 0.85]),
            'rebounds': np.array([8, 6, 7]),
            'assists': np.array([5, 4, 6]),
            'wins': np.array([1, 0, 1])
        }
        
        result = StatsAggregator.calculate_basic_averages(basic_stats)
        
        assert result['avg_minutes'] == pytest.approx(27.67, rel=1e-2)
        assert result['avg_points'] == pytest.approx(15.0, rel=1e-2)
        assert result['avg_efficiency'] == pytest.approx(20.17, rel=1e-2)
        assert result['avg_fg_pct'] == pytest.approx(0.477, rel=1e-2)
        assert result['avg_rebounds'] == pytest.approx(7.0, rel=1e-2)
        assert result['avg_assists'] == pytest.approx(5.0, rel=1e-2)
    
    def test_calculate_basic_averages_with_zero_percentages(self):
        """Test that zero percentages are excluded from averages."""
        basic_stats = {
            'minutes': np.array([30, 25]),
            'points': np.array([15, 12]),
            'efficiency': np.array([20.5, 18.0]),
            'fg_pct': np.array([0.45, 0.0]),  # One zero
            'three_pct': np.array([0.33, 0.0]),
            'ft_pct': np.array([0.80, 0.0]),
            'rebounds': np.array([8, 6]),
            'assists': np.array([5, 4]),
            'wins': np.array([1, 0])
        }
        
        result = StatsAggregator.calculate_basic_averages(basic_stats)
        
        # Should only average non-zero percentages
        assert result['avg_fg_pct'] == 0.45
        assert result['avg_three_pct'] == 0.33
        assert result['avg_ft_pct'] == 0.80
    
    def test_calculate_advanced_averages(self):
        """Test advanced metrics averages calculation."""
        advanced_stats = {
            'ts_pct': np.array([0.58, 0.55, 0.60]),
            'efg_pct': np.array([0.52, 0.48, 0.54]),
            'oer': np.array([110.0, 108.0, 112.0]),
            'per': np.array([18.5, 17.0, 19.2]),
            'tov_pct': np.array([12.0, 11.5, 13.0]),
            'orb_pct': np.array([8.0, 7.5, 8.5]),
            'drb_pct': np.array([22.0, 21.0, 23.0]),
            'ws': np.array([0.15, 0.12, 0.18]),
            'ws_36': np.array([0.18, 0.15, 0.20])
        }
        
        result = StatsAggregator.calculate_advanced_averages(advanced_stats)
        
        assert result['avg_ts_pct'] == pytest.approx(0.577, rel=1e-2)
        assert result['avg_efg_pct'] == pytest.approx(0.513, rel=1e-2)
        assert result['avg_oer'] == pytest.approx(110.0, rel=1e-2)
        assert result['avg_per'] == pytest.approx(18.23, rel=1e-2)
        assert result['avg_ws_36'] == pytest.approx(0.177, rel=1e-2)
    
    def test_calculate_advanced_averages_with_zeros(self):
        """Test that zeros are handled correctly in advanced metrics."""
        advanced_stats = {
            'ts_pct': np.array([0.58, 0.0, 0.60]),  # One zero
            'efg_pct': np.array([0.0, 0.0, 0.0]),  # All zeros
            'oer': np.array([110.0, 0.0, 112.0]),
            'per': np.array([18.5, -2.0, 19.2]),  # One negative (PER can be negative)
            'tov_pct': np.array([12.0, 0.0, 13.0]),
            'orb_pct': np.array([8.0, 0.0, 8.5]),
            'drb_pct': np.array([22.0, 0.0, 23.0]),
            'ws': np.array([0.15, 0.0, 0.18]),
            'ws_36': np.array([0.18, 0.0, 0.20])
        }
        
        result = StatsAggregator.calculate_advanced_averages(advanced_stats)
        
        # Should average non-zero values
        assert result['avg_ts_pct'] == pytest.approx(0.59, rel=1e-2)
        # Should return None when all zeros
        assert result['avg_efg_pct'] is None
        # PER can be negative, so should include all non-zero
        assert result['avg_per'] == pytest.approx(11.9, rel=1e-2)
    
    def test_calculate_totals(self):
        """Test totals calculation."""
        basic_stats = {
            'points': np.array([15, 12, 18]),
            'rebounds': np.array([8, 6, 7]),
            'assists': np.array([5, 4, 6])
        }
        
        result = StatsAggregator.calculate_totals(basic_stats)
        
        assert result['total_points'] == 45
        assert result['total_rebounds'] == 21
        assert result['total_assists'] == 15
    
    def test_calculate_std_deviations(self):
        """Test standard deviations calculation."""
        basic_stats = {
            'points': np.array([15, 12, 18, 20, 10]),
            'efficiency': np.array([20.5, 18.0, 22.0, 24.5, 17.0])
        }
        
        result = StatsAggregator.calculate_std_deviations(basic_stats)
        
        assert 'std_points' in result
        assert 'std_efficiency' in result
        assert result['std_points'] > 0
        assert result['std_efficiency'] > 0
    
    def test_calculate_trends_sufficient_games(self):
        """Test trend calculation with sufficient games."""
        basic_stats = {
            'points': np.array([10, 12, 14, 16, 18]),  # Increasing trend
            'efficiency': np.array([15, 16, 17, 18, 19])  # Increasing trend
        }
        
        result = StatsAggregator.calculate_trends(basic_stats, games_played=5)
        
        assert result['trend_points'] == pytest.approx(2.0, rel=1e-2)
        assert result['trend_efficiency'] == pytest.approx(1.0, rel=1e-2)
    
    def test_calculate_trends_insufficient_games(self):
        """Test trend calculation with insufficient games."""
        basic_stats = {
            'points': np.array([10, 12]),
            'efficiency': np.array([15, 16])
        }
        
        result = StatsAggregator.calculate_trends(basic_stats, games_played=2, min_games=3)
        
        assert result['trend_points'] == 0.0
        assert result['trend_efficiency'] == 0.0
    
    def test_calculate_win_percentage(self):
        """Test win percentage calculation."""
        basic_stats = {
            'wins': np.array([1, 0, 1, 1, 0])  # 3 wins out of 5
        }
        
        result = StatsAggregator.calculate_win_percentage(basic_stats)
        
        assert result == 60.0
    
    def test_calculate_total_win_shares(self):
        """Test total win shares calculation."""
        advanced_stats = {
            'ws': np.array([0.15, 0.12, 0.18, 0.20, 0.10])
        }
        
        result = StatsAggregator.calculate_total_win_shares(advanced_stats)
        
        assert result == pytest.approx(0.75, rel=1e-2)
    
    def test_extract_date_range(self):
        """Test date range extraction."""
        stats = [
            {"game_date": "2023-10-15"},
            {"game_date": "2023-10-20"},
            {"game_date": "2023-10-25"}
        ]
        
        date_from, date_to = StatsAggregator.extract_date_range(stats)
        
        assert date_from == "2023-10-15"
        assert date_to == "2023-10-25"


class TestAggregationQueryBuilder:
    """Test AggregationQueryBuilder helper class."""
    
    def test_get_player_season_stats_query(self):
        """Test SQL query generation for fetching stats."""
        query = AggregationQueryBuilder.get_player_season_stats_query()
        
        assert "SELECT" in query
        assert "player_game_stats" in query
        assert "games" in query
        assert "player_id = ?" in query
        assert "season = ?" in query
        assert "competition_id = ?" in query
        assert "ORDER BY g.game_date" in query
    
    def test_get_insert_aggregates_query(self):
        """Test SQL query generation for inserting aggregates."""
        query = AggregationQueryBuilder.get_insert_aggregates_query()
        
        assert "INSERT OR REPLACE" in query
        assert "player_aggregated_stats" in query
        assert "player_id" in query
        assert "avg_minutes" in query
        assert "total_points" in query
        assert "VALUES" in query


class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_full_aggregation_pipeline(self):
        """Test complete aggregation workflow."""
        # Sample game stats
        stats = [
            {
                "minutes_played": 30, "points": 15, "efficiency_rating": 20.5,
                "field_goal_pct": 0.45, "three_point_pct": 0.33, "free_throw_pct": 0.80,
                "total_rebounds": 8, "assists": 5, "team_won": 1,
                "true_shooting_pct": 0.58, "effective_fg_pct": 0.52,
                "offensive_rating": 110.0, "player_efficiency_rating": 18.5,
                "turnover_pct": 12.0, "offensive_rebound_pct": 8.0,
                "defensive_rebound_pct": 22.0, "win_shares": 0.15,
                "win_shares_per_36": 0.18, "game_date": "2023-10-15"
            },
            {
                "minutes_played": 25, "points": 12, "efficiency_rating": 18.0,
                "field_goal_pct": 0.50, "three_point_pct": 0.40, "free_throw_pct": 0.75,
                "total_rebounds": 6, "assists": 4, "team_won": 0,
                "true_shooting_pct": 0.55, "effective_fg_pct": 0.48,
                "offensive_rating": 108.0, "player_efficiency_rating": 17.0,
                "turnover_pct": 11.5, "offensive_rebound_pct": 7.5,
                "defensive_rebound_pct": 21.0, "win_shares": 0.12,
                "win_shares_per_36": 0.15, "game_date": "2023-10-20"
            },
            {
                "minutes_played": 28, "points": 18, "efficiency_rating": 22.0,
                "field_goal_pct": 0.48, "three_point_pct": 0.35, "free_throw_pct": 0.85,
                "total_rebounds": 7, "assists": 6, "team_won": 1,
                "true_shooting_pct": 0.60, "effective_fg_pct": 0.54,
                "offensive_rating": 112.0, "player_efficiency_rating": 19.2,
                "turnover_pct": 13.0, "offensive_rebound_pct": 8.5,
                "defensive_rebound_pct": 23.0, "win_shares": 0.18,
                "win_shares_per_36": 0.20, "game_date": "2023-10-25"
            }
        ]
        
        # Extract stats
        basic_stats = StatsExtractor.extract_basic_stats(stats)
        advanced_stats = StatsExtractor.extract_advanced_stats(stats)
        
        # Calculate aggregations
        basic_averages = StatsAggregator.calculate_basic_averages(basic_stats)
        advanced_averages = StatsAggregator.calculate_advanced_averages(advanced_stats)
        totals = StatsAggregator.calculate_totals(basic_stats)
        std_devs = StatsAggregator.calculate_std_deviations(basic_stats)
        trends = StatsAggregator.calculate_trends(basic_stats, games_played=3)
        win_pct = StatsAggregator.calculate_win_percentage(basic_stats)
        total_ws = StatsAggregator.calculate_total_win_shares(advanced_stats)
        date_from, date_to = StatsAggregator.extract_date_range(stats)
        
        # Verify results
        assert basic_averages['avg_points'] == pytest.approx(15.0, rel=1e-2)
        assert totals['total_points'] == 45
        assert win_pct == pytest.approx(66.67, rel=1e-2)
        assert total_ws == pytest.approx(0.45, rel=1e-2)
        assert date_from == "2023-10-15"
        assert date_to == "2023-10-25"
        assert trends['trend_points'] > 0  # Positive trend


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_single_game_stats(self):
        """Test aggregation with only one game."""
        stats = [
            {
                "minutes_played": 30, "points": 15, "efficiency_rating": 20.5,
                "field_goal_pct": 0.45, "three_point_pct": 0.33, "free_throw_pct": 0.80,
                "total_rebounds": 8, "assists": 5, "team_won": 1
            }
        ]
        
        basic_stats = StatsExtractor.extract_basic_stats(stats)
        result = StatsAggregator.calculate_basic_averages(basic_stats)
        
        # Averages should equal single values
        assert result['avg_points'] == 15
        assert result['avg_minutes'] == 30
    
    def test_all_losses(self):
        """Test win percentage with all losses."""
        basic_stats = {
            'wins': np.array([0, 0, 0, 0, 0])
        }
        
        result = StatsAggregator.calculate_win_percentage(basic_stats)
        
        assert result == 0.0
    
    def test_all_wins(self):
        """Test win percentage with all wins."""
        basic_stats = {
            'wins': np.array([1, 1, 1, 1, 1])
        }
        
        result = StatsAggregator.calculate_win_percentage(basic_stats)
        
        assert result == 100.0
    
    def test_negative_per_values(self):
        """Test handling of negative PER values."""
        advanced_stats = {
            'ts_pct': np.array([0.58, 0.55]),
            'efg_pct': np.array([0.52, 0.48]),
            'oer': np.array([110.0, 108.0]),
            'per': np.array([-5.0, -3.0]),  # Negative PER values
            'tov_pct': np.array([12.0, 11.5]),
            'orb_pct': np.array([8.0, 7.5]),
            'drb_pct': np.array([22.0, 21.0]),
            'ws': np.array([0.15, 0.12]),
            'ws_36': np.array([0.18, 0.15])
        }
        
        result = StatsAggregator.calculate_advanced_averages(advanced_stats)
        
        # Should average negative values (PER uses != 0 filter, not > 0)
        assert result['avg_per'] == pytest.approx(-4.0, rel=1e-2)
