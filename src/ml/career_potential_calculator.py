"""
Career Potential Calculation Module

Extracted helper functions for calculating player career potential scores.
These functions support the ETL processor by breaking down complex logic
into manageable, testable components.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import logging


class CareerPotentialCalculator:
    """
    Helper class for calculating career potential scores.
    
    Breaks down the complex career potential calculation into logical,
    testable components with clear responsibilities.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize calculator with optional logger."""
        self.logger = logger or logging.getLogger(__name__)
    
    @staticmethod
    def aggregate_seasons_by_performance(
        season_data: List[Tuple],
        team_factors: Dict[Tuple[int, str], float]
    ) -> Dict[str, Dict]:
        """
        Aggregate player performance data by season.
        
        When a player has multiple profiles in the same season (played for
        multiple teams/competitions), aggregates by summing games/minutes and
        averaging scores weighted by minutes and competition level.
        
        Args:
            season_data: List of tuples with season performance data
            team_factors: Team strength adjustment factors by (team_id, season)
            
        Returns:
            Dictionary mapping season to aggregated metrics
        """
        seasons_aggregated = {}
        
        for s in season_data:
            (season, profile_id, team_id, games, minutes, avg_min, base_score,
             pot_score, conf, eligible, off_rat, per, comp_level) = s
            
            # Only consider eligible profiles with valid data
            if not eligible or pot_score is None or minutes is None or minutes == 0:
                continue
            
            # Get team context factor
            team_factor = team_factors.get((team_id, season), 1.0)
            
            # Competition level multiplier
            level_multiplier = CareerPotentialCalculator._get_level_multiplier(comp_level)
            
            # Adjust score by level and team context
            team_adjusted_score = pot_score * (1.0 + 0.5 * (team_factor - 1.0))
            adjusted_score = team_adjusted_score * level_multiplier
            
            if season not in seasons_aggregated:
                seasons_aggregated[season] = {
                    'games': games or 0,
                    'minutes': minutes,
                    'weighted_score_sum': adjusted_score * minutes,
                    'profiles': 1,
                    'max_level': comp_level
                }
            else:
                # Aggregate: sum games, minutes, and weighted scores
                seasons_aggregated[season]['games'] += (games or 0)
                seasons_aggregated[season]['minutes'] += minutes
                seasons_aggregated[season]['weighted_score_sum'] += (adjusted_score * minutes)
                seasons_aggregated[season]['profiles'] += 1
                seasons_aggregated[season]['max_level'] = max(
                    seasons_aggregated[season]['max_level'],
                    comp_level
                )
        
        return seasons_aggregated
    
    @staticmethod
    def _get_level_multiplier(comp_level: int) -> float:
        """
        Get competition level multiplier for score adjustment.
        
        Args:
            comp_level: Competition level (0-3)
            
        Returns:
            Multiplier in range [0.80, 1.00]
        """
        if comp_level == 3:
            return 1.0  # LF ENDESA (top tier)
        elif comp_level == 2:
            return 0.90  # Regional first division
        elif comp_level == 1:
            return 0.85  # LF CHALLENGE (second national tier)
        else:
            return 0.80  # Unknown or lower levels
    
    @staticmethod
    def build_eligible_seasons(
        seasons_aggregated: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Build list of eligible seasons with computed average scores.
        
        Args:
            seasons_aggregated: Dictionary of aggregated season data
            
        Returns:
            List of season dictionaries sorted by season (newest first)
        """
        eligible_seasons = []
        for season, data in sorted(seasons_aggregated.items(), reverse=True):
            avg_score = data['weighted_score_sum'] / data['minutes']
            eligible_seasons.append({
                'season': season,
                'games': data['games'],
                'minutes': data['minutes'],
                'score': avg_score,
                'profiles': data['profiles'],
                'max_level': data['max_level']
            })
        return eligible_seasons
    
    @staticmethod
    def calculate_career_average(eligible_seasons: List[Dict]) -> float:
        """
        Calculate career average performance weighted by minutes.
        
        Args:
            eligible_seasons: List of season data dictionaries
            
        Returns:
            Career average performance score (0.0-1.0)
        """
        total_weighted_score = sum(s['score'] * s['minutes'] for s in eligible_seasons)
        total_minutes = sum(s['minutes'] for s in eligible_seasons)
        return total_weighted_score / total_minutes if total_minutes > 0 else 0.5
    
    @staticmethod
    def calculate_recent_performance(
        eligible_seasons: List[Dict],
        career_avg: float,
        num_recent: int = 2
    ) -> float:
        """
        Calculate recent performance (last N seasons).
        
        Args:
            eligible_seasons: List of season data (newest first)
            career_avg: Career average as fallback
            num_recent: Number of recent seasons to consider
            
        Returns:
            Recent performance score (0.0-1.0)
        """
        recent_limit = min(num_recent, len(eligible_seasons))
        recent_seasons = eligible_seasons[:recent_limit]
        recent_weighted_score = sum(s['score'] * s['minutes'] for s in recent_seasons)
        recent_minutes = sum(s['minutes'] for s in recent_seasons)
        return recent_weighted_score / recent_minutes if recent_minutes > 0 else career_avg
    
    @staticmethod
    def calculate_trajectory(eligible_seasons: List[Dict]) -> float:
        """
        Calculate career trajectory (improvement trend).
        
        Optimized for detecting explosive growth:
        - Compares recent performance vs historical average
        - Uses linear regression for trend
        - Combines both approaches with 70/30 weighting
        
        Args:
            eligible_seasons: List of season data (newest first)
            
        Returns:
            Trajectory score (0.0-1.0)
        """
        valid_perf_scores = [s['score'] for s in eligible_seasons[::-1]]  # Chronological order
        
        if len(valid_perf_scores) >= 3:
            # Compare recent 2 seasons vs all previous
            recent_avg = np.mean(valid_perf_scores[-2:])
            older_avg = np.mean(valid_perf_scores[:-2])
            improvement = recent_avg - older_avg
            
            # Traditional linear regression
            x = np.arange(len(valid_perf_scores))
            y = np.array(valid_perf_scores)
            slope = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0
            trajectory_from_slope = (slope / 0.15) * 0.5 + 0.5
            trajectory_from_slope = max(0.0, min(1.0, trajectory_from_slope))
            
            # Direct comparison (more sensitive to jumps)
            if improvement > 0.10:  # Explosive jump (>10%)
                trajectory_from_improvement = 0.95
            elif improvement > 0.05:  # Significant jump (>5%)
                trajectory_from_improvement = 0.80
            elif improvement > 0.02:  # Moderate improvement
                trajectory_from_improvement = 0.65
            elif improvement > -0.02:  # Stable
                trajectory_from_improvement = 0.50
            else:  # Declining
                trajectory_from_improvement = 0.30
            
            # Combine (70% direct comparison, 30% regression)
            return 0.70 * trajectory_from_improvement + 0.30 * trajectory_from_slope
                
        elif len(valid_perf_scores) == 2:
            # Only 2 seasons: direct comparison with more granularity
            improvement = valid_perf_scores[-1] - valid_perf_scores[0]
            if improvement > 0.10:
                return 0.90
            elif improvement > 0.05:
                return 0.75
            elif improvement > 0.02:
                return 0.65
            elif improvement > -0.02:
                return 0.50
            elif improvement > -0.05:
                return 0.35
            else:
                return 0.20
        else:
            return 0.50  # Insufficient history
    
    @staticmethod
    def adjust_trajectory_for_performance(
        trajectory: float,
        recent_performance: float,
        min_performance_threshold: float = 0.40
    ) -> float:
        """
        Adjust trajectory if recent performance is poor.
        
        Args:
            trajectory: Calculated trajectory score
            recent_performance: Recent performance score
            min_performance_threshold: Minimum acceptable performance
            
        Returns:
            Adjusted trajectory score
        """
        if recent_performance < min_performance_threshold:
            return min(trajectory, 0.40)
        return trajectory
    
    @staticmethod
    def calculate_consistency(eligible_seasons: List[Dict]) -> float:
        """
        Calculate career consistency (low variance is good).
        
        Args:
            eligible_seasons: List of season data
            
        Returns:
            Consistency score (0.0-1.0)
        """
        valid_perf_scores = [s['score'] for s in eligible_seasons]
        
        if len(valid_perf_scores) >= 2:
            std_career = np.std(valid_perf_scores)
            return max(0.0, 1.0 - (std_career / 0.5))
        else:
            return 0.5
    
    @staticmethod
    def calculate_age_score(current_age: Optional[int]) -> float:
        """
        Calculate age projection score.
        
        Younger players have more potential for growth.
        
        Args:
            current_age: Player's current age (None if unknown)
            
        Returns:
            Age score (0.0-1.0)
        """
        if not current_age:
            return 0.5
        
        if current_age <= 21:
            return 1.0
        elif current_age <= 24:
            return 0.8
        elif current_age <= 27:
            return 0.5
        elif current_age <= 30:
            return 0.3
        else:
            return 0.1
    
    @staticmethod
    def calculate_confidence_score(
        seasons_count: int,
        total_games: int
    ) -> float:
        """
        Calculate confidence score based on data quantity.
        
        More seasons and games = more confidence in assessment.
        
        Args:
            seasons_count: Number of seasons played
            total_games: Total games played
            
        Returns:
            Confidence score (0.0-1.0)
        """
        if seasons_count >= 4 and total_games >= 50:
            return 1.0
        elif seasons_count >= 3 and total_games >= 30:
            return 0.95
        elif seasons_count >= 2 and total_games >= 20:
            return 0.90
        elif seasons_count >= 2 and total_games >= 10:
            return 0.85
        elif seasons_count >= 1 and total_games >= 15:
            return 0.75
        else:
            return 0.60
    
    @staticmethod
    def calculate_level_jump_bonus(eligible_seasons: List[Dict]) -> float:
        """
        Calculate bonus for jumping competition levels.
        
        Moving up competition tiers indicates explosive potential.
        
        Args:
            eligible_seasons: List of season data (newest first)
            
        Returns:
            Bonus value (0.0-0.15)
        """
        if len(eligible_seasons) < 2:
            return 0.0
        
        # Compare max level of recent 2 seasons vs past seasons
        recent_max_level = max([s['max_level'] for s in eligible_seasons[:2]])
        
        if len(eligible_seasons) > 2:
            past_max_level = max([s['max_level'] for s in eligible_seasons[2:]])
            level_jump = recent_max_level - past_max_level
            
            if level_jump >= 2:
                return 0.15  # Significant bonus for 2+ level jump
            elif level_jump >= 1:
                return 0.08
        
        return 0.0
    
    @staticmethod
    def calculate_unified_score(
        recent_performance: float,
        career_trajectory: float,
        career_avg_performance: float,
        age_score: float,
        career_consistency: float,
        career_confidence: float,
        level_jump_bonus: float
    ) -> float:
        """
        Calculate unified potential score from components.
        
        Weighting optimized for explosive growth detection:
        - 50% Recent performance (current ability)
        - 25% Trajectory (momentum)
        - 5% Historical average (past is less relevant)
        - 10% Age projection (room for growth)
        - 5% Consistency
        - 5% Data confidence
        + Level jump bonus
        
        Args:
            All component scores (0.0-1.0)
            level_jump_bonus: Bonus for competition level jumps (0.0-0.15)
            
        Returns:
            Unified score capped at 1.0
        """
        base_score = (
            0.50 * recent_performance +
            0.25 * career_trajectory +
            0.05 * career_avg_performance +
            0.10 * age_score +
            0.05 * career_consistency +
            0.05 * career_confidence
        )
        
        return min(1.0, base_score + level_jump_bonus)
    
    @staticmethod
    def apply_inactivity_penalty(
        score: float,
        last_season: str,
        current_year: int = 2026,
        logger: Optional[logging.Logger] = None,
        player_name: str = ""
    ) -> float:
        """
        Apply penalty for player inactivity.
        
        Args:
            score: Base unified score
            last_season: Last season played (format: "YYYY/YYYY")
            current_year: Current year for comparison
            logger: Optional logger for warnings
            player_name: Player name for logging
            
        Returns:
            Score with inactivity penalty applied
        """
        try:
            # Use end year of season (2025/2026 -> played until 2026)
            last_season_end_year = int(last_season.split('/')[1])
            seasons_inactive = current_year - last_season_end_year
            
            if seasons_inactive >= 1:
                # Progressive penalty:
                # 1 season: -15% (injury/academic break)
                # 2 seasons: -35% (concerning)
                # 3+ seasons: -60% (likely retired or left FEB)
                if seasons_inactive == 1:
                    inactivity_penalty = 0.15
                elif seasons_inactive == 2:
                    inactivity_penalty = 0.35
                else:
                    inactivity_penalty = 0.60
                
                adjusted_score = score * (1.0 - inactivity_penalty)
                
                # Log if relevant
                if logger and adjusted_score >= 0.50:
                    logger.info(
                        f"⚠️  {player_name}: {seasons_inactive} seasons inactive "
                        f"(last: {last_season}). Penalty: -{inactivity_penalty*100:.0f}%. "
                        f"Adjusted score: {adjusted_score:.3f}"
                    )
                
                return adjusted_score
        except:
            pass  # If season parsing fails, no penalty
        
        return score
    
    @staticmethod
    def determine_tier(score: float) -> str:
        """
        Determine potential tier from unified score.
        
        Args:
            score: Unified potential score (0.0-1.0)
            
        Returns:
            Tier string: 'elite', 'very_high', 'high', 'medium', or 'low'
        """
        if score >= 0.70:
            return 'elite'
        elif score >= 0.60:
            return 'very_high'
        elif score >= 0.50:
            return 'high'
        elif score >= 0.40:
            return 'medium'
        else:
            return 'low'
    
    @staticmethod
    def calculate_special_flags(
        seasons_count: int,
        current_age: Optional[int],
        recent_performance: float,
        career_avg_performance: float,
        career_trajectory: float,
        career_consistency: float
    ) -> Tuple[bool, bool, bool]:
        """
        Calculate special player flags.
        
        Returns:
            Tuple of (is_rising_star, is_established_talent, is_peak_performer)
        """
        # Rising Star: Young player improving
        is_rising_star = (
            seasons_count >= 2 and
            current_age and current_age <= 24 and
            recent_performance > career_avg_performance + 0.02 and
            career_trajectory >= 0.55 and
            recent_performance >= 0.45
        )
        
        # Established Talent: Consistent veteran
        is_established_talent = (
            seasons_count >= 3 and
            career_avg_performance >= 0.50 and
            career_consistency >= 0.7 and
            recent_performance >= 0.45
        )
        
        # Peak Performer: Player at their best
        is_peak_performer = (
            recent_performance >= 0.55 and
            (recent_performance > career_avg_performance * 1.05 or
             recent_performance >= 0.65) and
            current_age and 22 <= current_age <= 29
        )
        
        return is_rising_star, is_established_talent, is_peak_performer
