"""
Unit tests for advanced basketball statistics calculations.

Tests all functions in ml.advanced_stats module with various scenarios
including edge cases, valid inputs, and integration tests.
"""

import pytest
from src.ml.advanced_stats import (
    calculate_true_shooting_pct,
    calculate_effective_fg_pct,
    calculate_turnover_pct,
    calculate_free_throw_rate,
    calculate_assist_to_turnover_ratio,
    calculate_offensive_rating,
    calculate_player_efficiency_rating,
    calculate_usage_rate,
    calculate_rebound_percentages,
    calculate_win_shares,
    calculate_all_advanced_stats
)


@pytest.mark.unit
class TestShootingEfficiencyMetrics:
    """Test shooting efficiency calculations."""
    
    def test_true_shooting_pct_normal_case(self):
        """Test TS% with typical stats."""
        # Player scores 20 points on 15 FGA and 5 FTA
        ts = calculate_true_shooting_pct(pts=20, fga=15, fta=5)
        
        assert ts is not None
        assert isinstance(ts, float)
        assert 0 <= ts <= 1.5  # Can exceed 1.0 for very efficient scorers
        # Expected: 20 / (2 * (15 + 0.44*5)) = 20 / 34.4 ≈ 0.581
        assert 0.55 < ts < 0.62
    
    def test_true_shooting_pct_zero_attempts(self):
        """Test TS% when player has no attempts."""
        ts = calculate_true_shooting_pct(pts=0, fga=0, fta=0)
        assert ts is None or ts == 0
    
    def test_true_shooting_pct_only_free_throws(self):
        """Test TS% when player only shoots free throws."""
        ts = calculate_true_shooting_pct(pts=10, fga=0, fta=10)
        assert ts is not None
        # 10 / (2 * (0 + 0.44*10)) = 10 / 8.8 ≈ 1.136
        assert ts > 1.0  # Should be very efficient
    
    def test_effective_fg_pct_normal_case(self):
        """Test eFG% with typical stats."""
        # 6 FGM, 2 3PM out of 12 FGA
        efg = calculate_effective_fg_pct(fgm=6, fg3m=2, fga=12)
        
        assert efg is not None
        assert isinstance(efg, float)
        # Expected: (6 + 0.5*2) / 12 = 7 / 12 ≈ 0.583
        assert 0.58 < efg < 0.59
    
    def test_effective_fg_pct_zero_attempts(self):
        """Test eFG% with no field goal attempts."""
        efg = calculate_effective_fg_pct(fgm=0, fg3m=0, fga=0)
        assert efg is None
    
    def test_effective_fg_pct_all_threes(self):
        """Test eFG% when all makes are three-pointers."""
        # 5 3PM out of 10 FGA (no 2P)
        efg = calculate_effective_fg_pct(fgm=5, fg3m=5, fga=10)
        
        # Expected: (5 + 0.5*5) / 10 = 7.5 / 10 = 0.75
        assert efg == 0.75


@pytest.mark.unit
class TestBallHandlingMetrics:
    """Test ball handling and possession metrics."""
    
    def test_turnover_pct_normal_case(self):
        """Test TOV% with typical stats."""
        tov_pct = calculate_turnover_pct(tov=3, fga=15, fta=4)
        
        assert tov_pct is not None
        assert 0 <= tov_pct <= 1
        # Expected: 3 / (15 + 0.44*4 + 3) = 3 / 19.76 ≈ 0.152
        assert 0.14 < tov_pct < 0.16
    
    def test_turnover_pct_zero_possessions(self):
        """Test TOV% with no possessions."""
        tov_pct = calculate_turnover_pct(tov=0, fga=0, fta=0)
        assert tov_pct is None
    
    def test_turnover_pct_high_turnovers(self):
        """Test TOV% with high turnover rate."""
        # 10 turnovers, 10 FGA, 2 FTA
        tov_pct = calculate_turnover_pct(tov=10, fga=10, fta=2)
        
        assert tov_pct is not None
        # Should be relatively high (> 0.4)
        assert tov_pct > 0.4
    
    def test_free_throw_rate_normal_case(self):
        """Test FTr with typical stats."""
        ftr = calculate_free_throw_rate(fta=8, fga=15)
        
        assert ftr is not None
        # Expected: 8 / 15 ≈ 0.533
        assert 0.53 < ftr < 0.54
    
    def test_free_throw_rate_zero_fga(self):
        """Test FTr with no field goal attempts."""
        ftr = calculate_free_throw_rate(fta=5, fga=0)
        assert ftr is None
    
    def test_assist_to_turnover_ratio_normal_case(self):
        """Test AST/TOV with typical stats."""
        ratio = calculate_assist_to_turnover_ratio(ast=6, tov=2)
        
        assert ratio is not None
        assert ratio == 3.0
    
    def test_assist_to_turnover_ratio_zero_turnovers(self):
        """Test AST/TOV when player has no turnovers."""
        ratio = calculate_assist_to_turnover_ratio(ast=5, tov=0)
        
        # Should return the assist value (or None, depending on implementation)
        assert ratio is None or ratio == 5.0
    
    def test_assist_to_turnover_ratio_zero_assists(self):
        """Test AST/TOV when player has no assists."""
        ratio = calculate_assist_to_turnover_ratio(ast=0, tov=3)
        
        assert ratio is not None
        assert ratio == 0.0


@pytest.mark.unit
class TestRatingMetrics:
    """Test offensive rating and PER calculations."""
    
    def test_offensive_rating_normal_case(self):
        """Test OER with typical stats."""
        oer = calculate_offensive_rating(
            pts=20, fga=15, fta=4, tov=2
        )
        
        assert oer is not None
        assert oer > 0
        # Expected possessions: 15 + 0.44*4 + 2 = 18.76
        # OER: (20 / 18.76) * 100 ≈ 106.6
        assert 100 < oer < 115
    
    def test_offensive_rating_zero_possessions(self):
        """Test OER with no possessions."""
        oer = calculate_offensive_rating(
            pts=0, fga=0, fta=0, tov=0
        )
        assert oer is None
    
    def test_offensive_rating_efficient_scorer(self):
        """Test OER for highly efficient scorer."""
        # 30 points on 12 FGA, 6 FTA, 1 TOV
        oer = calculate_offensive_rating(
            pts=30, fga=12, fta=6, tov=1
        )
        
        assert oer is not None
        # Should be > 120 for very efficient scorer
        assert oer > 120
    
    def test_per_normal_case(self):
        """Test PER with typical stats."""
        stats = {
            'pts': 15,
            'reb': 6,
            'ast': 4,
            'stl': 2,
            'blk': 1,
            'fgm': 6,
            'fga': 12,
            'ftm': 3,
            'fta': 4,
            'tov': 2,
            'minutes': 30
        }
        
        per = calculate_player_efficiency_rating(stats)
        
        assert per is not None
        assert per > 0
        # PER typically ranges from 0-30+ (15 is league average)
        assert 0 < per < 50
    
    def test_per_zero_minutes(self):
        """Test PER when player has 0 minutes."""
        stats = {
            'pts': 10,
            'reb': 5,
            'minutes': 0
        }
        
        per = calculate_player_efficiency_rating(stats)
        assert per is None
    
    def test_per_negative_contributors(self):
        """Test PER with player who has more negatives than positives."""
        stats = {
            'pts': 2,
            'reb': 1,
            'ast': 0,
            'stl': 0,
            'blk': 0,
            'fgm': 1,
            'fga': 10,  # Many misses
            'ftm': 0,
            'fta': 4,   # Many missed FTs
            'tov': 5,   # Many turnovers
            'minutes': 20
        }
        
        per = calculate_player_efficiency_rating(stats)
        
        assert per is not None
        # Should be low or negative (scaled)
        assert per < 5


@pytest.mark.unit
class TestAdvancedMetrics:
    """Test usage rate, rebound percentages, and win shares."""
    
    def test_usage_rate_without_team_stats(self):
        """Test USG% using simplified formula."""
        usg = calculate_usage_rate(
            fga=15, fta=5, tov=3, minutes=30.0
        )
        
        assert usg is not None
        assert usg > 0
        # Simplified: (15 + 0.44*5 + 3) / 30 * 100
        # = 20.2 / 30 * 100 ≈ 67.3
        assert 60 < usg < 75
    
    def test_usage_rate_with_team_stats(self):
        """Test USG% with full team statistics."""
        usg = calculate_usage_rate(
            fga=15, fta=5, tov=3, minutes=30.0,
            team_fga=80, team_fta=20, team_tov=12, team_minutes=200.0
        )
        
        assert usg is not None
        assert usg > 0
        # Should be percentage (typically 15-35%)
        assert 10 < usg < 40
    
    def test_usage_rate_zero_minutes(self):
        """Test USG% with zero minutes."""
        usg = calculate_usage_rate(
            fga=10, fta=5, tov=2, minutes=0
        )
        assert usg is None
    
    def test_rebound_percentages_without_team_stats(self):
        """Test rebound % without team/opponent data."""
        reb_pcts = calculate_rebound_percentages(
            player_orb=3, player_drb=5
        )
        
        assert 'orb_pct' in reb_pcts
        assert 'drb_pct' in reb_pcts
        # Without team stats, should return None
        assert reb_pcts['orb_pct'] is None
        assert reb_pcts['drb_pct'] is None
    
    def test_rebound_percentages_with_team_stats(self):
        """Test rebound % with complete data."""
        reb_pcts = calculate_rebound_percentages(
            player_orb=3, player_drb=7,
            team_orb=15, team_drb=30,
            opponent_orb=12, opponent_drb=28,
            minutes=30.0, team_minutes=200.0
        )
        
        assert reb_pcts['orb_pct'] is not None
        assert reb_pcts['drb_pct'] is not None
        assert 0 <= reb_pcts['orb_pct'] <= 1
        assert 0 <= reb_pcts['drb_pct'] <= 1
    
    def test_win_shares_normal_case(self):
        """Test Win Shares calculation."""
        stats = {
            'pts': 18,
            'reb': 7,
            'ast': 5,
            'stl': 2,
            'blk': 1,
            'fgm': 7,
            'fga': 14,
            'ftm': 4,
            'fta': 5,
            'tov': 2,
            'minutes': 32
        }
        
        ws = calculate_win_shares(stats)
        
        assert ws is not None
        assert ws >= 0
        # WS should be relatively small for single game
        assert ws < 5
    
    def test_win_shares_zero_minutes(self):
        """Test Win Shares with zero minutes."""
        stats = {
            'pts': 10,
            'minutes': 0
        }
        
        ws = calculate_win_shares(stats)
        assert ws is None


@pytest.mark.unit
class TestIntegrationAllStats:
    """Test the comprehensive calculate_all_advanced_stats function."""
    
    def test_all_stats_basic_player(self):
        """Test calculating all stats for a basic player."""
        stats = {
            'pts': 15,
            'fgm': 6,
            'fga': 12,
            'fg3m': 2,
            'ftm': 3,
            'fta': 4,
            'reb': 6,
            'orb': 2,
            'drb': 4,
            'ast': 4,
            'stl': 2,
            'blk': 1,
            'tov': 2,
            'minutes': 30.0
        }
        
        result = calculate_all_advanced_stats(stats)
        
        # Check all expected keys exist
        expected_keys = [
            'true_shooting_pct', 'effective_fg_pct',
            'turnover_pct', 'free_throw_rate',
            'assist_to_turnover_ratio',
            'offensive_rating', 'player_efficiency_rating',
            'usage_rate',
            'offensive_rebound_pct', 'defensive_rebound_pct',
            'win_shares', 'win_shares_per_36'
        ]
        
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"
        
        # Check that numeric values are present (not all None)
        numeric_values = [v for v in result.values() if v is not None]
        assert len(numeric_values) > 5, "Should calculate multiple metrics"
    
    def test_all_stats_with_team_data(self):
        """Test calculating all stats with team and opponent data."""
        stats = {
            'pts': 20,
            'fgm': 8,
            'fga': 15,
            'fg3m': 2,
            'ftm': 4,
            'fta': 5,
            'reb': 8,
            'orb': 3,
            'drb': 5,
            'ast': 6,
            'stl': 2,
            'blk': 1,
            'tov': 3,
            'minutes': 32.0
        }
        
        team_stats = {
            'fga': 80,
            'fta': 20,
            'tov': 12,
            'orb': 15,
            'drb': 30,
            'minutes': 200.0,
            'possessions': 100
        }
        
        opponent_stats = {
            'orb': 12,
            'drb': 28
        }
        
        result = calculate_all_advanced_stats(stats, team_stats, opponent_stats)
        
        # With team data, more metrics should be calculated
        # Usage rate should be more accurate
        assert result['usage_rate'] is not None
        
        # Rebound percentages should be calculated
        assert result['offensive_rebound_pct'] is not None
        assert result['defensive_rebound_pct'] is not None
    
    def test_all_stats_minimal_data(self):
        """Test calculating stats with minimal data."""
        stats = {
            'pts': 5,
            'fga': 3,
            'fta': 0,
            'minutes': 10.0
        }
        
        result = calculate_all_advanced_stats(stats)
        
        # Should handle gracefully, some metrics will be None
        assert isinstance(result, dict)
        assert len(result) > 0
        
        # At minimum, should calculate some shooting metrics
        assert 'true_shooting_pct' in result
        assert 'effective_fg_pct' in result
    
    def test_all_stats_edge_case_zero_minutes(self):
        """Test all stats calculation with zero minutes."""
        stats = {
            'pts': 10,
            'fga': 5,
            'fta': 2,
            'minutes': 0
        }
        
        result = calculate_all_advanced_stats(stats)
        
        # Metrics requiring minutes should be None
        assert result['player_efficiency_rating'] is None
        assert result['usage_rate'] is None
        assert result['win_shares'] is None
        
        # But some metrics should still calculate
        assert result['true_shooting_pct'] is not None


@pytest.mark.unit
class TestEdgeCasesAndValidation:
    """Test edge cases and input validation."""
    
    def test_negative_values_handled(self):
        """Test that negative values don't cause crashes."""
        # Negative values shouldn't occur, but test robustness
        ts = calculate_true_shooting_pct(pts=-5, fga=10, fta=2)
        # Should return a value (even if nonsensical) or None
        assert ts is None or isinstance(ts, float)
    
    def test_very_large_values(self):
        """Test handling of unrealistically large values."""
        stats = {
            'pts': 100,
            'fga': 50,
            'fta': 30,
            'reb': 30,
            'ast': 20,
            'minutes': 48.0
        }
        
        result = calculate_all_advanced_stats(stats)
        
        # Should not crash
        assert isinstance(result, dict)
        
        # Values might be extreme but should be numeric
        for key, value in result.items():
            if value is not None:
                assert isinstance(value, (int, float))
    
    def test_missing_optional_stats(self):
        """Test that missing optional stats are handled."""
        stats = {
            'pts': 15,
            'fga': 12,
            'fta': 3,
            'minutes': 28.0
            # Missing many stats like reb, ast, etc.
        }
        
        result = calculate_all_advanced_stats(stats)
        
        # Should not crash, use defaults (0)
        assert isinstance(result, dict)
        assert result['true_shooting_pct'] is not None
