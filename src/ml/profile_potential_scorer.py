"""
Profile Potential Scorer Module

Extracted helper functions for calculating player profile potential scores.
Breaks down complex scoring logic into testable, reusable components.
"""

from typing import Dict, Optional, Tuple, List
import logging


class EligibilityChecker:
    """Helper class for checking player eligibility for potential scoring."""
    
    # Eligibility thresholds
    MIN_GAMES_FOR_POTENTIAL = 8
    MIN_TOTAL_MINUTES = 80
    MIN_AVG_MINUTES = 8
    
    @staticmethod
    def check_eligibility(
        games_played: int,
        total_minutes: Optional[float],
        avg_minutes: Optional[float]
    ) -> Tuple[bool, List[str]]:
        """
        Check if a player profile meets eligibility criteria for potential scoring.
        
        Args:
            games_played: Number of games played
            total_minutes: Total minutes played
            avg_minutes: Average minutes per game
            
        Returns:
            Tuple of (meets_eligibility, eligibility_notes)
        """
        meets_eligibility = True
        eligibility_notes = []
        
        if games_played < EligibilityChecker.MIN_GAMES_FOR_POTENTIAL:
            meets_eligibility = False
            eligibility_notes.append(
                f"Pocos partidos ({games_played}<{EligibilityChecker.MIN_GAMES_FOR_POTENTIAL})"
            )
        
        if total_minutes is None or total_minutes < EligibilityChecker.MIN_TOTAL_MINUTES:
            meets_eligibility = False
            total_min_str = f"{total_minutes:.0f}" if total_minutes else "0"
            eligibility_notes.append(
                f"Pocos minutos totales ({total_min_str}<{EligibilityChecker.MIN_TOTAL_MINUTES})"
            )
        
        if avg_minutes is None or avg_minutes < EligibilityChecker.MIN_AVG_MINUTES:
            meets_eligibility = False
            avg_min_str = f"{avg_minutes:.1f}" if avg_minutes else "0"
            eligibility_notes.append(
                f"Rol marginal ({avg_min_str}<{EligibilityChecker.MIN_AVG_MINUTES} min/partido)"
            )
        
        return meets_eligibility, eligibility_notes


class PotentialScoreCalculator:
    """
    Helper class for calculating various components of player potential scores.
    
    All scores are normalized to 0.0-1.0 range.
    """
    
    @staticmethod
    def calculate_age_projection_score(age: Optional[int]) -> float:
        """
        Calculate age-based projection score.
        
        Younger players have higher potential for development.
        
        Args:
            age: Player's age
            
        Returns:
            Score from 0.0 to 1.0
        """
        if age is None:
            return 0.5  # Neutral if age unknown
        
        if age <= 21:
            return 1.0  # Very young, high potential
        elif age <= 24:
            return 0.8
        elif age <= 27:
            return 0.5
        elif age <= 30:
            return 0.3
        else:
            return 0.1
    
    @staticmethod
    def calculate_performance_score(
        avg_z_oer: Optional[float],
        avg_z_per: Optional[float],
        competition_level: Optional[int]
    ) -> float:
        """
        Calculate performance score from z-scores with competition adjustment.
        
        Args:
            avg_z_oer: Average z-score for offensive rating
            avg_z_per: Average z-score for player efficiency rating
            competition_level: Level of competition (1=highest, 3=lowest)
            
        Returns:
            Score from 0.0 to 1.0
        """
        if avg_z_oer is None or avg_z_per is None:
            return 0.5
        
        # Normalize z-scores to 0-1 range (assuming -3 to +3)
        base_perf_score = ((avg_z_oer + avg_z_per) / 2 + 3) / 6
        base_perf_score = max(0.0, min(1.0, base_perf_score))
        
        # Adjust for competition level
        competition_bonus = 0.0
        if competition_level == 1:
            competition_bonus = 0.10  # Top level: +10%
        elif competition_level == 3:
            competition_bonus = -0.05  # Lower level: -5%
        
        perf_score = min(1.0, base_perf_score * (1.0 + competition_bonus))
        return perf_score
    
    @staticmethod
    def calculate_consistency_score(
        cv_points: Optional[float],
        std_oer: Optional[float]
    ) -> float:
        """
        Calculate consistency score from coefficient of variation.
        
        Lower CV means more consistent performance.
        
        Args:
            cv_points: Coefficient of variation for points
            std_oer: Standard deviation of offensive rating (fallback)
            
        Returns:
            Score from 0.0 to 1.0
        """
        if cv_points is not None and cv_points >= 0:
            # CV < 0.3 = very consistent, CV > 0.8 = very inconsistent
            return max(0.0, min(1.0, 1.0 - (cv_points / 0.8)))
        elif std_oer is not None and std_oer > 0:
            # Fallback to older method
            return max(0.0, 1.0 - (std_oer / 50.0))
        else:
            return 0.5
    
    @staticmethod
    def calculate_advanced_metrics_score(
        avg_ts_pct: Optional[float],
        efficiency_vs_team_avg: Optional[float]
    ) -> float:
        """
        Calculate score from advanced metrics (TS%, efficiency vs team).
        
        Args:
            avg_ts_pct: Average true shooting percentage
            efficiency_vs_team_avg: Player efficiency relative to team average
            
        Returns:
            Score from 0.0 to 1.0
        """
        if avg_ts_pct is None:
            return 0.5
        
        # TS% > 55% is very good
        base_ts_score = min(1.0, avg_ts_pct / 65.0)
        
        # Adjust by team efficiency if available
        if efficiency_vs_team_avg is not None:
            # > 1.0 = better than team, < 1.0 = worse than team
            team_adj = min(1.2, max(0.8, efficiency_vs_team_avg))
            return base_ts_score * team_adj
        else:
            return base_ts_score
    
    @staticmethod
    def calculate_momentum_score(
        momentum_index: Optional[float],
        trend_points: Optional[float]
    ) -> float:
        """
        Calculate momentum/trend score for breakout detection.
        
        Positive momentum indicates improving performance.
        
        Args:
            momentum_index: Difference between last 5 and last 10 games average
            trend_points: Linear trend slope
            
        Returns:
            Score from 0.0 to 1.0
        """
        if momentum_index is not None:
            # momentum_index = avg(last5) - avg(last10)
            # Positive = improving, negative = declining
            # Normalize between -5 and +5 points difference
            normalized_momentum = (momentum_index + 5) / 10
            return max(0.0, min(1.0, normalized_momentum))
        elif trend_points is not None:
            # Trend as fallback
            normalized_trend = (trend_points + 2) / 4
            return max(0.0, min(1.0, normalized_trend))
        else:
            return 0.5  # Neutral default
    
    @staticmethod
    def calculate_production_score(
        pts_per_36: Optional[float],
        player_pts_share: Optional[float]
    ) -> float:
        """
        Calculate production score normalized by playing time.
        
        Args:
            pts_per_36: Points per 36 minutes
            player_pts_share: Player's share of team points
            
        Returns:
            Score from 0.0 to 1.0
        """
        if pts_per_36 is None:
            return 0.5
        
        # pts_per_36 > 15 = excellent, < 5 = very low
        production_score = min(1.0, pts_per_36 / 20.0)
        
        # Adjust by team share if available
        if player_pts_share is not None:
            # > 0.15 = offensive leader, < 0.05 = secondary role
            share_bonus = min(0.2, player_pts_share * 1.0)
            production_score = min(1.0, production_score + share_bonus)
        
        return production_score
    
    @staticmethod
    def calculate_composite_potential_score(
        age_score: float,
        perf_score: float,
        production_score: float,
        consistency_score: float,
        adv_metrics_score: float,
        momentum_score: float
    ) -> float:
        """
        Calculate composite potential score from all components.
        
        Weighting:
        - 20% Age (temporal projection)
        - 30% Performance (z-scores adjusted by competition)
        - 15% Production per-36 (normalized production)
        - 15% Consistency (CV points, stability)
        - 10% Advanced metrics (TS%, efficiency vs team)
        - 10% Momentum (breakout detection)
        
        Args:
            age_score: Age projection score
            perf_score: Performance score
            production_score: Production score
            consistency_score: Consistency score
            adv_metrics_score: Advanced metrics score
            momentum_score: Momentum score
            
        Returns:
            Composite score from 0.0 to 1.0
        """
        return (
            0.20 * age_score +
            0.30 * perf_score +
            0.15 * production_score +
            0.15 * consistency_score +
            0.10 * adv_metrics_score +
            0.10 * momentum_score
        )
    
    @staticmethod
    def calculate_temporal_weight(season: str, current_year: int = 2026) -> float:
        """
        Calculate temporal weight for season recency.
        
        More recent seasons get higher weight.
        
        Args:
            season: Season string (e.g., "2024/2025")
            current_year: Current year for comparison
            
        Returns:
            Weight from 0.5 to 1.0
        """
        try:
            season_year = int(season.split('/')[0])
            years_ago = current_year - season_year
            # 2025/2026 = 1.0, 2024/2025 = 0.95, 2023/2024 = 0.90, etc.
            return max(0.5, 1.0 - (years_ago * 0.05))
        except:
            return 1.0
    
    @staticmethod
    def calculate_age_from_season(
        season: str,
        birth_year: Optional[int]
    ) -> Optional[int]:
        """
        Calculate player age for a given season.
        
        Args:
            season: Season string (e.g., "2024/2025")
            birth_year: Player's birth year
            
        Returns:
            Calculated age or None
        """
        if birth_year is None:
            return None
        
        try:
            season_year = int(season.split('/')[0])
            return season_year - birth_year
        except:
            return None
    
    @staticmethod
    def apply_temporal_adjustment(
        base_score: float,
        temporal_weight: float
    ) -> float:
        """
        Apply temporal weight adjustment to score.
        
        Recent data gets 100% weight, older data gets reduced weight.
        
        Args:
            base_score: Base potential score
            temporal_weight: Temporal weight (0.5-1.0)
            
        Returns:
            Adjusted score
        """
        return base_score * (0.85 + 0.15 * temporal_weight)
    
    @staticmethod
    def determine_potential_tier(potential_score: float) -> str:
        """
        Determine potential tier from final score.
        
        Args:
            potential_score: Final potential score
            
        Returns:
            Tier string
        """
        if potential_score >= 0.75:
            return 'very_high'
        elif potential_score >= 0.60:
            return 'high'
        elif potential_score >= 0.45:
            return 'medium'
        elif potential_score >= 0.30:
            return 'low'
        else:
            return 'very_low'
    
    @staticmethod
    def calculate_special_flags(
        age: Optional[int],
        perf_score: float,
        consistency_score: float,
        meets_eligibility: bool
    ) -> Tuple[bool, bool]:
        """
        Calculate special flags for talent identification.
        
        Args:
            age: Player's age
            perf_score: Performance score
            consistency_score: Consistency score
            meets_eligibility: Whether player meets eligibility criteria
            
        Returns:
            Tuple of (is_young_talent, is_consistent_performer)
        """
        is_young_talent = (
            age is not None and 
            age < 23 and 
            perf_score >= 0.6 and 
            meets_eligibility
        )
        
        is_consistent = (
            consistency_score >= 0.7 and 
            perf_score >= 0.6 and 
            meets_eligibility
        )
        
        return is_young_talent, is_consistent
