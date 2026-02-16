"""
Unit tests for profile_potential_scorer module.
Tests the extracted helper functions for calculating player profile potential scores.
"""

import pytest
from src.ml.profile_potential_scorer import EligibilityChecker, PotentialScoreCalculator


class TestEligibilityChecker:
    """Test player eligibility checking."""
    
    def test_check_eligibility_meets_all_criteria(self):
        """Test player that meets all eligibility criteria."""
        meets, notes = EligibilityChecker.check_eligibility(
            games_played=10,
            total_minutes=100.0,
            avg_minutes=10.0
        )
        
        assert meets is True
        assert len(notes) == 0
    
    def test_check_eligibility_insufficient_games(self):
        """Test player with insufficient games."""
        meets, notes = EligibilityChecker.check_eligibility(
            games_played=5,
            total_minutes=100.0,
            avg_minutes=10.0
        )
        
        assert meets is False
        assert any("Pocos partidos" in note for note in notes)
    
    def test_check_eligibility_insufficient_total_minutes(self):
        """Test player with insufficient total minutes."""
        meets, notes = EligibilityChecker.check_eligibility(
            games_played=10,
            total_minutes=50.0,
            avg_minutes=10.0
        )
        
        assert meets is False
        assert any("Pocos minutos totales" in note for note in notes)
    
    def test_check_eligibility_insufficient_avg_minutes(self):
        """Test player with insufficient average minutes."""
        meets, notes = EligibilityChecker.check_eligibility(
            games_played=10,
            total_minutes=100.0,
            avg_minutes=5.0
        )
        
        assert meets is False
        assert any("Rol marginal" in note for note in notes)
    
    def test_check_eligibility_multiple_failures(self):
        """Test player failing multiple criteria."""
        meets, notes = EligibilityChecker.check_eligibility(
            games_played=3,
            total_minutes=20.0,
            avg_minutes=3.0
        )
        
        assert meets is False
        assert len(notes) == 3  # All three checks should fail
    
    def test_check_eligibility_none_values(self):
        """Test with None values for minutes."""
        meets, notes = EligibilityChecker.check_eligibility(
            games_played=10,
            total_minutes=None,
            avg_minutes=None
        )
        
        assert meets is False
        assert len(notes) == 2


class TestAgeProjectionScore:
    """Test age-based projection score calculation."""
    
    def test_very_young_player(self):
        """Test score for very young player (<=21)."""
        score = PotentialScoreCalculator.calculate_age_projection_score(20)
        assert score == 1.0
    
    def test_young_player(self):
        """Test score for young player (22-24)."""
        score = PotentialScoreCalculator.calculate_age_projection_score(23)
        assert score == 0.8
    
    def test_prime_age_player(self):
        """Test score for prime age player (25-27)."""
        score = PotentialScoreCalculator.calculate_age_projection_score(26)
        assert score == 0.5
    
    def test_veteran_player(self):
        """Test score for veteran player (28-30)."""
        score = PotentialScoreCalculator.calculate_age_projection_score(29)
        assert score == 0.3
    
    def test_old_player(self):
        """Test score for older player (>30)."""
        score = PotentialScoreCalculator.calculate_age_projection_score(33)
        assert score == 0.1
    
    def test_none_age(self):
        """Test that None age returns neutral score."""
        score = PotentialScoreCalculator.calculate_age_projection_score(None)
        assert score == 0.5


class TestPerformanceScore:
    """Test performance score calculation with z-scores."""
    
    def test_calculate_performance_score_top_level(self):
        """Test performance score at top competition level."""
        score = PotentialScoreCalculator.calculate_performance_score(
            avg_z_oer=1.5,
            avg_z_per=1.5,
            competition_level=1
        )
        
        # Base score = ((1.5+1.5)/2 + 3) / 6 = 0.75
        # With 10% bonus = 0.75 * 1.1 = 0.825
        assert score == pytest.approx(0.825, rel=1e-2)
    
    def test_calculate_performance_score_low_level(self):
        """Test performance score at lower competition level."""
        score = PotentialScoreCalculator.calculate_performance_score(
            avg_z_oer=1.0,
            avg_z_per=1.0,
            competition_level=3
        )
        
        # Base score = ((1.0+1.0)/2 + 3) / 6 = 0.667
        # With -5% penalty = 0.667 * 0.95 = 0.633
        assert score == pytest.approx(0.633, rel=1e-2)
    
    def test_calculate_performance_score_mid_level(self):
        """Test performance score at mid-level competition."""
        score = PotentialScoreCalculator.calculate_performance_score(
            avg_z_oer=0.0,
            avg_z_per=0.0,
            competition_level=2
        )
        
        # Base score = ((0+0)/2 + 3) / 6 = 0.5
        # No adjustment for level 2
        assert score == pytest.approx(0.5, rel=1e-2)
    
    def test_calculate_performance_score_none_values(self):
        """Test with None z-scores returns neutral score."""
        score = PotentialScoreCalculator.calculate_performance_score(
            avg_z_oer=None,
            avg_z_per=None,
            competition_level=1
        )
        
        assert score == 0.5
    
    def test_calculate_performance_score_caps_at_1(self):
        """Test that score is capped at 1.0."""
        score = PotentialScoreCalculator.calculate_performance_score(
            avg_z_oer=3.0,
            avg_z_per=3.0,
            competition_level=1
        )
        
        assert score <= 1.0


class TestConsistencyScore:
    """Test consistency score calculation."""
    
    def test_calculate_consistency_very_consistent(self):
        """Test score for very consistent player (low CV)."""
        score = PotentialScoreCalculator.calculate_consistency_score(
            cv_points=0.2,
            std_oer=None
        )
        
        # 1.0 - (0.2 / 0.8) = 0.75
        assert score == pytest.approx(0.75, rel=1e-2)
    
    def test_calculate_consistency_very_inconsistent(self):
        """Test score for very inconsistent player (high CV)."""
        score = PotentialScoreCalculator.calculate_consistency_score(
            cv_points=0.9,
            std_oer=None
        )
        
        # 1.0 - (0.9 / 0.8) = clamped to 0.0
        assert score == 0.0
    
    def test_calculate_consistency_fallback_to_std_oer(self):
        """Test fallback to std_oer when CV not available."""
        score = PotentialScoreCalculator.calculate_consistency_score(
            cv_points=None,
            std_oer=25.0
        )
        
        # 1.0 - (25.0 / 50.0) = 0.5
        assert score == pytest.approx(0.5, rel=1e-2)
    
    def test_calculate_consistency_no_data(self):
        """Test with no consistency data returns neutral score."""
        score = PotentialScoreCalculator.calculate_consistency_score(
            cv_points=None,
            std_oer=None
        )
        
        assert score == 0.5


class TestAdvancedMetricsScore:
    """Test advanced metrics score calculation."""
    
    def test_calculate_advanced_metrics_excellent_ts(self):
        """Test with excellent true shooting percentage."""
        score = PotentialScoreCalculator.calculate_advanced_metrics_score(
            avg_ts_pct=60.0,  # TS% as percentage, not decimal
            efficiency_vs_team_avg=None
        )
        
        # 60.0 / 65.0 = 0.923
        assert score == pytest.approx(0.923, rel=1e-2)
    
    def test_calculate_advanced_metrics_with_team_adjustment(self):
        """Test with team efficiency adjustment."""
        score = PotentialScoreCalculator.calculate_advanced_metrics_score(
            avg_ts_pct=50.0,  # TS% as percentage
            efficiency_vs_team_avg=1.1  # 10% better than team
        )
        
        # (50.0 / 65.0) * 1.1 = 0.846
        assert score == pytest.approx(0.846, rel=1e-2)
    
    def test_calculate_advanced_metrics_none_ts(self):
        """Test with None TS% returns neutral score."""
        score = PotentialScoreCalculator.calculate_advanced_metrics_score(
            avg_ts_pct=None,
            efficiency_vs_team_avg=1.1
        )
        
        assert score == 0.5


class TestMomentumScore:
    """Test momentum and trend score calculation."""
    
    def test_calculate_momentum_positive(self):
        """Test positive momentum (improving)."""
        score = PotentialScoreCalculator.calculate_momentum_score(
            momentum_index=3.0,
            trend_points=None
        )
        
        # (3.0 + 5) / 10 = 0.8
        assert score == pytest.approx(0.8, rel=1e-2)
    
    def test_calculate_momentum_negative(self):
        """Test negative momentum (declining)."""
        score = PotentialScoreCalculator.calculate_momentum_score(
            momentum_index=-3.0,
            trend_points=None
        )
        
        # (-3.0 + 5) / 10 = 0.2
        assert score == pytest.approx(0.2, rel=1e-2)
    
    def test_calculate_momentum_fallback_to_trend(self):
        """Test fallback to trend_points when momentum not available."""
        score = PotentialScoreCalculator.calculate_momentum_score(
            momentum_index=None,
            trend_points=1.0
        )
        
        # (1.0 + 2) / 4 = 0.75
        assert score == pytest.approx(0.75, rel=1e-2)
    
    def test_calculate_momentum_no_data(self):
        """Test with no momentum data returns neutral score."""
        score = PotentialScoreCalculator.calculate_momentum_score(
            momentum_index=None,
            trend_points=None
        )
        
        assert score == 0.5


class TestProductionScore:
    """Test production score calculation."""
    
    def test_calculate_production_excellent(self):
        """Test with excellent production."""
        score = PotentialScoreCalculator.calculate_production_score(
            pts_per_36=16.0,
            player_pts_share=None
        )
        
        # 16.0 / 20.0 = 0.8
        assert score == pytest.approx(0.8, rel=1e-2)
    
    def test_calculate_production_with_team_share_bonus(self):
        """Test with team share bonus."""
        score = PotentialScoreCalculator.calculate_production_score(
            pts_per_36=12.0,
            player_pts_share=0.15  # Offensive leader
        )
        
        # (12.0 / 20.0) + (0.15 * 1.0) = 0.75
        assert score == pytest.approx(0.75, rel=1e-2)
    
    def test_calculate_production_none_pts_per_36(self):
        """Test with None pts_per_36 returns neutral score."""
        score = PotentialScoreCalculator.calculate_production_score(
            pts_per_36=None,
            player_pts_share=0.15
        )
        
        assert score == 0.5


class TestCompositeScore:
    """Test composite potential score calculation."""
    
    def test_calculate_composite_all_high(self):
        """Test composite with all high component scores."""
        score = PotentialScoreCalculator.calculate_composite_potential_score(
            age_score=1.0,
            perf_score=0.9,
            production_score=0.8,
            consistency_score=0.8,
            adv_metrics_score=0.7,
            momentum_score=0.7
        )
        
        # 0.20*1.0 + 0.30*0.9 + 0.15*0.8 + 0.15*0.8 + 0.10*0.7 + 0.10*0.7
        # = 0.20 + 0.27 + 0.12 + 0.12 + 0.07 + 0.07 = 0.85
        assert score == pytest.approx(0.85, rel=1e-2)
    
    def test_calculate_composite_all_average(self):
        """Test composite with all average scores."""
        score = PotentialScoreCalculator.calculate_composite_potential_score(
            age_score=0.5,
            perf_score=0.5,
            production_score=0.5,
            consistency_score=0.5,
            adv_metrics_score=0.5,
            momentum_score=0.5
        )
        
        assert score == pytest.approx(0.5, rel=1e-2)
    
    def test_calculate_composite_mixed_scores(self):
        """Test composite with mixed scores."""
        score = PotentialScoreCalculator.calculate_composite_potential_score(
            age_score=1.0,  # Very young
            perf_score=0.3,  # Below average performance
            production_score=0.4,
            consistency_score=0.6,
            adv_metrics_score=0.5,
            momentum_score=0.8  # Good momentum
        )
        
        # 0.20*1.0 + 0.30*0.3 + 0.15*0.4 + 0.15*0.6 + 0.10*0.5 + 0.10*0.8
        # = 0.20 + 0.09 + 0.06 + 0.09 + 0.05 + 0.08 = 0.57
        assert score == pytest.approx(0.57, rel=1e-2)


class TestTemporalWeight:
    """Test temporal weight calculation for season recency."""
    
    def test_calculate_temporal_weight_current_season(self):
        """Test weight for current season."""
        weight = PotentialScoreCalculator.calculate_temporal_weight("2026/2027", 2026)
        
        assert weight == 1.0
    
    def test_calculate_temporal_weight_one_year_ago(self):
        """Test weight for one year ago."""
        weight = PotentialScoreCalculator.calculate_temporal_weight("2025/2026", 2026)
        
        assert weight == pytest.approx(0.95, rel=1e-2)
    
    def test_calculate_temporal_weight_two_years_ago(self):
        """Test weight for two years ago."""
        weight = PotentialScoreCalculator.calculate_temporal_weight("2024/2025", 2026)
        
        assert weight == pytest.approx(0.90, rel=1e-2)
    
    def test_calculate_temporal_weight_floors_at_half(self):
        """Test that weight floors at 0.5."""
        weight = PotentialScoreCalculator.calculate_temporal_weight("2010/2011", 2026)
        
        assert weight == 0.5
    
    def test_calculate_temporal_weight_invalid_format(self):
        """Test with invalid season format returns 1.0."""
        weight = PotentialScoreCalculator.calculate_temporal_weight("invalid", 2026)
        
        assert weight == 1.0


class TestAgeCalculation:
    """Test age calculation from season and birth year."""
    
    def test_calculate_age_from_season_valid(self):
        """Test valid age calculation."""
        age = PotentialScoreCalculator.calculate_age_from_season("2024/2025", 2000)
        
        assert age == 24
    
    def test_calculate_age_from_season_none_birth_year(self):
        """Test with None birth year returns None."""
        age = PotentialScoreCalculator.calculate_age_from_season("2024/2025", None)
        
        assert age is None
    
    def test_calculate_age_from_season_invalid_format(self):
        """Test with invalid season format returns None."""
        age = PotentialScoreCalculator.calculate_age_from_season("invalid", 2000)
        
        assert age is None


class TestTemporalAdjustment:
    """Test temporal adjustment application."""
    
    def test_apply_temporal_adjustment_current_season(self):
        """Test adjustment for current season (weight=1.0)."""
        adjusted = PotentialScoreCalculator.apply_temporal_adjustment(0.8, 1.0)
        
        # 0.8 * (0.85 + 0.15*1.0) = 0.8 * 1.0 = 0.8
        assert adjusted == pytest.approx(0.8, rel=1e-2)
    
    def test_apply_temporal_adjustment_old_season(self):
        """Test adjustment for older season (weight=0.5)."""
        adjusted = PotentialScoreCalculator.apply_temporal_adjustment(0.8, 0.5)
        
        # 0.8 * (0.85 + 0.15*0.5) = 0.8 * 0.925 = 0.74
        assert adjusted == pytest.approx(0.74, rel=1e-2)


class TestPotentialTier:
    """Test potential tier determination."""
    
    def test_determine_potential_tier_very_high(self):
        """Test very high potential tier."""
        tier = PotentialScoreCalculator.determine_potential_tier(0.80)
        assert tier == 'very_high'
    
    def test_determine_potential_tier_high(self):
        """Test high potential tier."""
        tier = PotentialScoreCalculator.determine_potential_tier(0.65)
        assert tier == 'high'
    
    def test_determine_potential_tier_medium(self):
        """Test medium potential tier."""
        tier = PotentialScoreCalculator.determine_potential_tier(0.50)
        assert tier == 'medium'
    
    def test_determine_potential_tier_low(self):
        """Test low potential tier."""
        tier = PotentialScoreCalculator.determine_potential_tier(0.35)
        assert tier == 'low'
    
    def test_determine_potential_tier_very_low(self):
        """Test very low potential tier."""
        tier = PotentialScoreCalculator.determine_potential_tier(0.20)
        assert tier == 'very_low'
    
    def test_determine_potential_tier_boundary_values(self):
        """Test boundary values."""
        assert PotentialScoreCalculator.determine_potential_tier(0.75) == 'very_high'
        assert PotentialScoreCalculator.determine_potential_tier(0.60) == 'high'
        assert PotentialScoreCalculator.determine_potential_tier(0.45) == 'medium'
        assert PotentialScoreCalculator.determine_potential_tier(0.30) == 'low'


class TestSpecialFlags:
    """Test special flags calculation."""
    
    def test_calculate_special_flags_young_talent(self):
        """Test young talent flag."""
        is_young, is_consistent = PotentialScoreCalculator.calculate_special_flags(
            age=21,
            perf_score=0.7,
            consistency_score=0.5,
            meets_eligibility=True
        )
        
        assert is_young is True
        assert is_consistent is False
    
    def test_calculate_special_flags_consistent_performer(self):
        """Test consistent performer flag."""
        is_young, is_consistent = PotentialScoreCalculator.calculate_special_flags(
            age=26,
            perf_score=0.7,
            consistency_score=0.75,
            meets_eligibility=True
        )
        
        assert is_young is False
        assert is_consistent is True
    
    def test_calculate_special_flags_both(self):
        """Test both flags active."""
        is_young, is_consistent = PotentialScoreCalculator.calculate_special_flags(
            age=21,
            perf_score=0.7,
            consistency_score=0.75,
            meets_eligibility=True
        )
        
        assert is_young is True
        assert is_consistent is True
    
    def test_calculate_special_flags_none(self):
        """Test neither flag active."""
        is_young, is_consistent = PotentialScoreCalculator.calculate_special_flags(
            age=26,
            perf_score=0.5,
            consistency_score=0.5,
            meets_eligibility=True
        )
        
        assert is_young is False
        assert is_consistent is False
    
    def test_calculate_special_flags_not_eligible(self):
        """Test that flags are False when not eligible."""
        is_young, is_consistent = PotentialScoreCalculator.calculate_special_flags(
            age=21,
            perf_score=0.7,
            consistency_score=0.75,
            meets_eligibility=False
        )
        
        assert is_young is False
        assert is_consistent is False


class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_complete_potential_scoring_workflow(self):
        """Test complete potential scoring workflow."""
        # Check eligibility
        meets, notes = EligibilityChecker.check_eligibility(
            games_played=15,
            total_minutes=300.0,
            avg_minutes=20.0
        )
        assert meets is True
        
        # Calculate component scores
        age_score = PotentialScoreCalculator.calculate_age_projection_score(22)
        perf_score = PotentialScoreCalculator.calculate_performance_score(1.0, 1.0, 1)
        prod_score = PotentialScoreCalculator.calculate_production_score(14.0, 0.12)
        cons_score = PotentialScoreCalculator.calculate_consistency_score(0.3, None)
        adv_score = PotentialScoreCalculator.calculate_advanced_metrics_score(58.0, 1.05)  # TS% as percentage
        mom_score = PotentialScoreCalculator.calculate_momentum_score(2.0, None)
        
        # Calculate composite
        composite = PotentialScoreCalculator.calculate_composite_potential_score(
            age_score, perf_score, prod_score, cons_score, adv_score, mom_score
        )
        
        # Apply temporal adjustment
        temporal_weight = PotentialScoreCalculator.calculate_temporal_weight("2026/2027", 2026)
        adjusted_score = PotentialScoreCalculator.apply_temporal_adjustment(composite, temporal_weight)
        
        # Determine tier
        tier = PotentialScoreCalculator.determine_potential_tier(adjusted_score)
        
        # Calculate flags
        is_young, is_consistent = PotentialScoreCalculator.calculate_special_flags(
            22, perf_score, cons_score, meets
        )
        
        # Verify results
        assert composite > 0.6
        assert tier in ['high', 'very_high']
        assert is_young is True
    
    def test_low_potential_player_workflow(self):
        """Test workflow for low potential player."""
        # Fails eligibility
        meets, notes = EligibilityChecker.check_eligibility(
            games_played=4,
            total_minutes=30.0,
            avg_minutes=5.0
        )
        assert meets is False
        
        # Old with poor performance
        age_score = PotentialScoreCalculator.calculate_age_projection_score(32)
        perf_score = PotentialScoreCalculator.calculate_performance_score(-1.0, -1.0, 3)
        
        composite = PotentialScoreCalculator.calculate_composite_potential_score(
            age_score, perf_score, 0.3, 0.4, 0.4, 0.4
        )
        
        tier = PotentialScoreCalculator.determine_potential_tier(composite)
        
        assert composite < 0.4
        assert tier in ['low', 'very_low']
