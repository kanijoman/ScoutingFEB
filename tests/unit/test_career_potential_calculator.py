"""
Tests for CareerPotentialCalculator module.

Basic tests to validate the extracted helper functions work correctly.
"""

import pytest
from src.ml.career_potential_calculator import CareerPotentialCalculator


class TestBasicFunctionality:
    """Test basic functionality of career potential calculator."""
    
    def test_aggregate_seasons_with_team_factors(self):
        """Aggregate seasons requires team_factors parameter."""
        season_data = [
            ('2023/2024', 1, 100, 20, 600, 30.0, 0.8, 0.85, 0.9, True, 105, 18, 3)
        ]
        team_factors = {(100, '2023/2024'): 1.05}
        result = CareerPotentialCalculator.aggregate_seasons_by_performance(
            season_data, team_factors
        )
        assert isinstance(result, dict)
        assert '2023/2024' in result
    
    def test_career_average_returns_numeric(self):
        """Career average should return a number."""
        seasons = [{'score': 0.85, 'minutes': 600, 'season': '2023/2024'}]
        avg = CareerPotentialCalculator.calculate_career_average(seasons)
        assert isinstance(avg, (int, float))
        assert 0 <= avg <= 1.0
        assert avg == 0.85
    
    def test_recent_performance_with_single_season(self):
        """Recent performance with one season."""
        seasons = [{'score': 0.85, 'minutes': 600, 'season': '2023/2024'}]
        recent = CareerPotentialCalculator.calculate_recent_performance(
            seasons, career_avg=0.80, num_recent=2
        )
        assert isinstance(recent, (int, float))
        assert recent == 0.85
    
    def test_trajectory_with_multiple_seasons(self):
        """Trajectory calculation with multiple seasons."""
        seasons = [
            {'score': 0.90, 'season': '2023/2024', 'minutes': 600},
            {'score': 0.80, 'season': '2022/2023', 'minutes': 580},
            {'score': 0.70, 'season': '2021/2022', 'minutes': 550}
        ]
        trajectory = CareerPotentialCalculator.calculate_trajectory(seasons)
        assert isinstance(trajectory, (int, float))
        assert 0 <= trajectory <= 1
    
    def test_consistency_returns_score(self):
        """Consistency should return 0-1 score."""
        seasons = [
            {'score': 0.80, 'minutes': 600},
            {'score': 0.82, 'minutes': 590},
            {'score': 0.78, 'minutes': 610}
        ]
        consistency = CareerPotentialCalculator.calculate_consistency(seasons)
        assert isinstance(consistency, (int, float))
        assert 0 <= consistency <= 1
    
    def test_age_score_young_player(self):
        """Young players get high score."""
        score = CareerPotentialCalculator.calculate_age_score(20)
        assert score >= 0.8
    
    def test_age_score_older_player(self):
        """Older players get lower score."""
        score = CareerPotentialCalculator.calculate_age_score(32)
        assert score <= 0.3
    
    def test_age_score_handles_none(self):
        """None age returns neutral score."""
        score = CareerPotentialCalculator.calculate_age_score(None)
        assert 0.4 <= score <= 0.6
    
    def test_confidence_score_returns_valid_range(self):
        """Confidence score should be between 0 and 1."""
        confidence = CareerPotentialCalculator.calculate_confidence_score(
            seasons_count=3,
            total_games=40
        )
        assert 0 <= confidence <= 1
        assert confidence >= 0.90  # Should be high with 3 seasons, 40 games
    
    def test_determine_tier_returns_valid_tier(self):
        """Tier determination returns valid tier name."""
        tier = CareerPotentialCalculator.determine_tier(0.75)
        assert tier in ['elite', 'very_high', 'high', 'medium', 'low']
        assert tier == 'elite'  # 0.75 >= 0.70 = elite
    
    def test_calculate_special_flags_returns_tuple(self):
        """Special flags returns tuple of booleans."""
        result = CareerPotentialCalculator.calculate_special_flags(
            seasons_count=3,
            current_age=22,
            recent_performance=0.75,
            career_avg_performance=0.70,
            career_trajectory=0.60,
            career_consistency=0.75
        )
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert all(isinstance(flag, bool) for flag in result)
        # Young player improving -> should be rising star
        is_rising_star, is_established, is_peak = result
        assert is_rising_star is True


class TestAdvancedFunctionality:
    """Test advanced scenarios and edge cases."""
    
    def test_trajectory_with_improving_player(self):
        """Test trajectory calculation for improving player."""
        seasons = [
            {'score': 0.85, 'season': '2023/2024', 'minutes': 600},
            {'score': 0.75, 'season': '2022/2023', 'minutes': 580},
            {'score': 0.65, 'season': '2021/2022', 'minutes': 550}
        ]
        trajectory = CareerPotentialCalculator.calculate_trajectory(seasons)
        # Improving player should have trajectory > 0.5
        assert trajectory > 0.5
    
    def test_trajectory_with_declining_player(self):
        """Test trajectory calculation for declining player."""
        seasons = [
            {'score': 0.60, 'season': '2023/2024', 'minutes': 600},
            {'score': 0.70, 'season': '2022/2023', 'minutes': 580},
            {'score': 0.80, 'season': '2021/2022', 'minutes': 550}
        ]
        trajectory = CareerPotentialCalculator.calculate_trajectory(seasons)
        # Declining player should have trajectory < 0.5
        assert trajectory < 0.5
    
    def test_recent_performance_with_multiple_seasons(self):
        """Test recent performance calculation prioritizes recent data."""
        seasons = [
            {'score': 0.90, 'season': '2023/2024', 'minutes': 600},
            {'score': 0.85, 'season': '2022/2023', 'minutes': 580},
            {'score': 0.60, 'season': '2021/2022', 'minutes': 550}
        ]
        recent = CareerPotentialCalculator.calculate_recent_performance(
            seasons, career_avg=0.78, num_recent=2
        )
        # Should be closer to recent values (0.90, 0.85) than career avg
        assert recent > 0.85
    
    def test_confidence_score_with_many_games(self):
        """High game count gives high confidence."""
        confidence = CareerPotentialCalculator.calculate_confidence_score(
            seasons_count=4,
            total_games=60
        )
        assert confidence == 1.0
    
    def test_confidence_score_with_few_games(self):
        """Low game count gives lower confidence."""
        confidence = CareerPotentialCalculator.calculate_confidence_score(
            seasons_count=1,
            total_games=8
        )
        assert confidence == 0.60
    
    def test_level_jump_bonus_with_improvement(self):
        """Test bonus calculation when player moves up levels."""
        seasons = [
            {'max_level': 3, 'season': '2023/2024', 'minutes': 600, 'score': 0.80},
            {'max_level': 3, 'season': '2022/2023', 'minutes': 580, 'score': 0.75},
            {'max_level': 2, 'season': '2021/2022', 'minutes': 550, 'score': 0.70}
        ]
        bonus = CareerPotentialCalculator.calculate_level_jump_bonus(seasons)
        # Should get bonus for moving from level 2 to 3
        assert bonus > 0
        assert bonus == 0.08  # 1 level jump
    
    def test_tier_boundaries(self):
        """Test all tier boundaries."""
        assert CareerPotentialCalculator.determine_tier(0.75) == 'elite'
        assert CareerPotentialCalculator.determine_tier(0.65) == 'very_high'
        assert CareerPotentialCalculator.determine_tier(0.55) == 'high'
        assert CareerPotentialCalculator.determine_tier(0.45) == 'medium'
        assert CareerPotentialCalculator.determine_tier(0.35) == 'low'
    
    def test_special_flags_established_talent(self):
        """Test established talent flag."""
        is_rising, is_established, is_peak = CareerPotentialCalculator.calculate_special_flags(
            seasons_count=5,
            current_age=28,
            recent_performance=0.55,
            career_avg_performance=0.55,
            career_trajectory=0.50,
            career_consistency=0.75
        )
        # 5 seasons, good avg, consistent -> established
        assert is_established is True
    
    def test_special_flags_peak_performer(self):
        """Test peak performer flag."""
        is_rising, is_established, is_peak = CareerPotentialCalculator.calculate_special_flags(
            seasons_count=4,
            current_age=26,
            recent_performance=0.70,
            career_avg_performance=0.60,
            career_trajectory=0.55,
            career_consistency=0.70
        )
        # Prime age, recent better than avg -> peak
        assert is_peak is True
    
    def test_consistency_with_stable_performance(self):
        """Consistent performance gives high consistency score."""
        seasons = [
            {'score': 0.80, 'minutes': 600},
            {'score': 0.81, 'minutes': 590},
            {'score': 0.79, 'minutes': 610},
            {'score': 0.80, 'minutes': 600}
        ]
        consistency = CareerPotentialCalculator.calculate_consistency(seasons)
        # Very stable -> high consistency
        assert consistency > 0.9
    
    def test_consistency_with_variable_performance(self):
        """Variable performance gives lower consistency score."""
        seasons = [
            {'score': 0.95, 'minutes': 600},
            {'score': 0.40, 'minutes': 590},
            {'score': 0.90, 'minutes': 610},
            {'score': 0.35, 'minutes': 600}
        ]
        consistency = CareerPotentialCalculator.calculate_consistency(seasons)
        # High variance -> lower consistency (more extreme values)
        assert consistency < 0.6
    
    def test_age_score_progression(self):
        """Test age score decreases with age."""
        score_20 = CareerPotentialCalculator.calculate_age_score(20)
        score_25 = CareerPotentialCalculator.calculate_age_score(25)
        score_30 = CareerPotentialCalculator.calculate_age_score(30)
        
        # Should decrease with age
        assert score_20 > score_25 > score_30
    
    def test_career_average_weighted_by_minutes(self):
        """Career average should weight by minutes played."""
        seasons = [
            {'score': 0.90, 'minutes': 100},  # Less minutes
            {'score': 0.60, 'minutes': 900}   # More minutes
        ]
        avg = CareerPotentialCalculator.calculate_career_average(seasons)
        # Should be closer to 0.60 (more minutes)
        assert 0.60 < avg < 0.70
