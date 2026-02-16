"""
Profile Metrics Computer Module

Extracted helper class for computing player profile metrics from game statistics.
Orchestrates the calculation of comprehensive player profile metrics.
"""

from typing import Dict, Optional, Tuple, Any
import sqlite3
import logging
from .profile_metrics_calculator import ProfileMetricsCalculator, ProfileQueryBuilder


class ProfileDataFetcher:
    """Helper class for fetching profile-related data from database."""
    
    @staticmethod
    def fetch_basic_stats(
        cursor: sqlite3.Cursor,
        profile_id: int
    ) -> Optional[Tuple]:
        """
        Fetch basic aggregated statistics for a profile.
        
        Args:
            cursor: Database cursor
            profile_id: Profile identifier
            
        Returns:
            Tuple of statistics or None
        """
        cursor.execute(
            ProfileQueryBuilder.get_basic_stats_query(),
            (profile_id, profile_id, profile_id, profile_id, profile_id)
        )
        return cursor.fetchone()
    
    @staticmethod
    def fetch_rolling_window_stats(
        cursor: sqlite3.Cursor,
        profile_id: int
    ) -> Optional[Tuple]:
        """
        Fetch rolling window statistics (last 5/10 games).
        
        Args:
            cursor: Database cursor
            profile_id: Profile identifier
            
        Returns:
            Tuple of rolling stats or None
        """
        cursor.execute(
            ProfileQueryBuilder.get_rolling_windows_query(),
            (profile_id,)
        )
        return cursor.fetchone()
    
    @staticmethod
    def fetch_trend_data(
        cursor: sqlite3.Cursor,
        profile_id: int
    ) -> Optional[Tuple]:
        """
        Fetch trend calculation data.
        
        Args:
            cursor: Database cursor
            profile_id: Profile identifier
            
        Returns:
            Tuple of trend data or None
        """
        cursor.execute(
            ProfileQueryBuilder.get_trend_query(),
            (profile_id,)
        )
        return cursor.fetchone()
    
    @staticmethod
    def fetch_team_context(
        cursor: sqlite3.Cursor,
        profile_id: int
    ) -> Optional[Tuple[int, str]]:
        """
        Fetch team and season context for profile.
        
        Args:
            cursor: Database cursor
            profile_id: Profile identifier
            
        Returns:
            Tuple of (team_id, season) or None
        """
        cursor.execute("""
            SELECT pp.team_id, pp.season
            FROM player_profiles pp
            WHERE pp.profile_id = ?
        """, (profile_id,))
        return cursor.fetchone()
    
    @staticmethod
    def fetch_team_totals(
        cursor: sqlite3.Cursor,
        team_id: int,
        season: str
    ) -> Optional[Tuple]:
        """
        Fetch team aggregate statistics.
        
        Args:
            cursor: Database cursor
            team_id: Team identifier
            season: Season string
            
        Returns:
            Tuple of team statistics or None
        """
        cursor.execute(
            ProfileQueryBuilder.get_team_totals_query(),
            (team_id, season)
        )
        return cursor.fetchone()
    
    @staticmethod
    def fetch_player_usage(
        cursor: sqlite3.Cursor,
        profile_id: int
    ) -> Optional[float]:
        """
        Fetch player's average usage rate.
        
        Args:
            cursor: Database cursor
            profile_id: Profile identifier
            
        Returns:
            Average usage rate or None
        """
        cursor.execute("""
            SELECT AVG(usage_rate)
            FROM player_game_stats
            WHERE player_id = ?
        """, (profile_id,))
        result = cursor.fetchone()
        return result[0] if result and result[0] else None


class ProfileMetricsComputer:
    """
    Orchestrates the computation of player profile metrics.
    
    Combines data fetching, calculation, and persistence operations.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize computer with optional logger."""
        self.logger = logger or logging.getLogger(__name__)
    
    def compute_all_profiles(
        self,
        conn: sqlite3.Connection
    ) -> int:
        """
        Compute metrics for all player profiles.
        
        Args:
            conn: SQLite database connection
            
        Returns:
            Number of profiles processed
        """
        cursor = conn.cursor()
        
        # Get all profiles
        cursor.execute("SELECT profile_id FROM player_profiles")
        profiles = cursor.fetchall()
        
        self.logger.info(f"Calculando métricas para {len(profiles)} perfiles...")
        
        for i, (profile_id,) in enumerate(profiles, 1):
            if i % 100 == 0:
                self.logger.info(f"  Progreso: {i}/{len(profiles)}")
            
            self._compute_single_profile(cursor, profile_id)
        
        conn.commit()
        self.logger.info(f"✓ Métricas calculadas para {len(profiles)} perfiles")
        
        return len(profiles)
    
    def _compute_single_profile(
        self,
        cursor: sqlite3.Cursor,
        profile_id: int
    ):
        """
        Compute metrics for a single profile.
        
        Args:
            cursor: Database cursor
            profile_id: Profile identifier
        """
        # Fetch basic stats
        stats = ProfileDataFetcher.fetch_basic_stats(cursor, profile_id)
        
        if not stats or stats[0] == 0:
            return
        
        # Extract core metrics
        core_metrics = self._extract_core_metrics(stats)
        
        # Calculate derived metrics
        variability_metrics = self._calculate_variability_metrics(stats, core_metrics)
        per_36_metrics = self._calculate_per_36_metrics(stats, core_metrics)
        rolling_metrics = self._calculate_rolling_metrics(cursor, profile_id)
        trend_metrics = self._calculate_trend_metrics(cursor, profile_id, rolling_metrics)
        team_ratio_metrics = self._calculate_team_ratios(cursor, profile_id, stats, core_metrics)
        
        # Determine performance tier
        tier = ProfileMetricsCalculator.determine_performance_tier(
            core_metrics['avg_z_oer']
        )
        
        # Persist metrics
        self._persist_metrics(
            cursor,
            profile_id,
            core_metrics,
            variability_metrics,
            per_36_metrics,
            rolling_metrics,
            trend_metrics,
            team_ratio_metrics,
            tier,
            stats
        )
    
    def _extract_core_metrics(self, stats: Tuple) -> Dict[str, Any]:
        """Extract core metrics from stats tuple."""
        return {
            'games': stats[0],
            'total_minutes': stats[1],
            'avg_minutes': stats[2],
            'avg_points': stats[3],
            'avg_z_oer': stats[7] if stats[7] is not None else 0
        }
    
    def _calculate_variability_metrics(
        self,
        stats: Tuple,
        core_metrics: Dict[str, Any]
    ) -> Dict[str, Optional[float]]:
        """Calculate variability and consistency metrics."""
        std_oer, cv_points, stability_index = (
            ProfileMetricsCalculator.calculate_variability_metrics(
                variance=stats[10],
                avg_value=core_metrics['avg_points'],
                num_games=core_metrics['games']
            )
        )
        
        std_points = (
            (stats[11] ** 0.5)
            if stats[11] is not None and stats[11] > 0
            else 0
        )
        
        return {
            'std_oer': std_oer,
            'std_points': std_points,
            'cv_points': cv_points,
            'stability_index': stability_index
        }
    
    def _calculate_per_36_metrics(
        self,
        stats: Tuple,
        core_metrics: Dict[str, Any]
    ) -> Dict[str, Optional[float]]:
        """Calculate per-36 minute statistics."""
        totals = {
            'pts': stats[12],
            'ast': stats[13],
            'reb': stats[14],
            'stl': stats[15],
            'blk': stats[16],
            'tov': stats[17],
            'fgm': stats[18],
            'fga': stats[19],
            'fg3m': stats[20]
        }
        
        return ProfileMetricsCalculator.calculate_per_36_stats(
            core_metrics['total_minutes'],
            totals
        )
    
    def _calculate_rolling_metrics(
        self,
        cursor: sqlite3.Cursor,
        profile_id: int
    ) -> Dict[str, Optional[float]]:
        """Calculate rolling window metrics."""
        rolling = ProfileDataFetcher.fetch_rolling_window_stats(cursor, profile_id)
        
        if not rolling:
            return {
                'last_5_pts': None,
                'last_5_oer': None,
                'last_10_pts': None,
                'last_10_oer': None
            }
        
        return {
            'last_5_pts': rolling[0] if rolling[0] else None,
            'last_5_oer': rolling[1] if rolling[1] else None,
            'last_10_pts': rolling[2] if rolling[2] else None,
            'last_10_oer': rolling[3] if rolling[3] else None
        }
    
    def _calculate_trend_metrics(
        self,
        cursor: sqlite3.Cursor,
        profile_id: int,
        rolling_metrics: Dict[str, Optional[float]]
    ) -> Dict[str, Optional[float]]:
        """Calculate trend and momentum metrics."""
        # Calculate momentum from rolling windows
        momentum_index = ProfileMetricsCalculator.calculate_momentum_index(
            rolling_metrics['last_5_pts'],
            rolling_metrics['last_10_pts']
        )
        
        # Calculate trend from regression
        trend_data = ProfileDataFetcher.fetch_trend_data(cursor, profile_id)
        trend_points = ProfileMetricsCalculator.calculate_trend_slope(
            covariance_xy=trend_data[0] if trend_data else None,
            variance_x=trend_data[1] if trend_data else None
        )
        
        return {
            'momentum_index': momentum_index,
            'trend_points': trend_points
        }
    
    def _calculate_team_ratios(
        self,
        cursor: sqlite3.Cursor,
        profile_id: int,
        stats: Tuple,
        core_metrics: Dict[str, Any]
    ) -> Dict[str, Optional[float]]:
        """Calculate player-to-team ratio metrics."""
        # Get team context
        team_context = ProfileDataFetcher.fetch_team_context(cursor, profile_id)
        
        if not team_context:
            return {
                'player_pts_share': None,
                'minutes_share': None,
                'efficiency_vs_team_avg': None,
                'player_usage_share': None
            }
        
        team_id, season = team_context
        
        # Get team totals
        team_stats = ProfileDataFetcher.fetch_team_totals(cursor, team_id, season)
        
        # Get player usage
        player_usage = ProfileDataFetcher.fetch_player_usage(cursor, profile_id)
        
        # Build totals dicts
        player_totals = {
            'points': stats[12],
            'minutes': core_metrics['total_minutes'],
            'avg_ts': stats[6],
            'avg_usage': player_usage
        }
        
        team_totals = {
            'points': team_stats[0] if team_stats else None,
            'minutes': team_stats[1] if team_stats else None,
            'avg_ts': team_stats[2] if team_stats else None,
            'avg_usage': team_stats[3] if team_stats else None
        }
        
        return ProfileMetricsCalculator.calculate_player_team_ratios(
            player_totals,
            team_totals
        )
    
    def _persist_metrics(
        self,
        cursor: sqlite3.Cursor,
        profile_id: int,
        core_metrics: Dict[str, Any],
        variability_metrics: Dict[str, Optional[float]],
        per_36_metrics: Dict[str, Optional[float]],
        rolling_metrics: Dict[str, Optional[float]],
        trend_metrics: Dict[str, Optional[float]],
        team_ratio_metrics: Dict[str, Optional[float]],
        tier: str,
        stats: Tuple
    ):
        """Persist calculated metrics to database."""
        cursor.execute("""
            INSERT OR REPLACE INTO player_profile_metrics (
                profile_id, games_played, total_minutes, avg_minutes, avg_points,
                avg_offensive_rating, avg_player_efficiency_rating,
                avg_true_shooting_pct, avg_z_offensive_rating,
                avg_z_player_efficiency_rating, avg_z_minutes,
                std_offensive_rating, std_points, performance_tier,
                pts_per_36, ast_per_36, reb_per_36, stl_per_36, blk_per_36,
                tov_per_36, fgm_per_36, fga_per_36, fg3m_per_36,
                cv_points, stability_index,
                last_5_games_pts, last_5_games_oer, last_10_games_pts, last_10_games_oer,
                trend_points, momentum_index,
                player_pts_share, player_usage_share, efficiency_vs_team_avg, minutes_share
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            profile_id,
            core_metrics['games'],
            core_metrics['total_minutes'],
            core_metrics['avg_minutes'],
            core_metrics['avg_points'],
            stats[4], stats[5], stats[6], stats[7], stats[8], stats[9],
            variability_metrics['std_oer'],
            variability_metrics['std_points'],
            tier,
            per_36_metrics.get('pts_per_36'),
            per_36_metrics.get('ast_per_36'),
            per_36_metrics.get('reb_per_36'),
            per_36_metrics.get('stl_per_36'),
            per_36_metrics.get('blk_per_36'),
            per_36_metrics.get('tov_per_36'),
            per_36_metrics.get('fgm_per_36'),
            per_36_metrics.get('fga_per_36'),
            per_36_metrics.get('fg3m_per_36'),
            variability_metrics['cv_points'],
            variability_metrics['stability_index'],
            rolling_metrics['last_5_pts'],
            rolling_metrics['last_5_oer'],
            rolling_metrics['last_10_pts'],
            rolling_metrics['last_10_oer'],
            trend_metrics['trend_points'],
            trend_metrics['momentum_index'],
            team_ratio_metrics['player_pts_share'],
            team_ratio_metrics['player_usage_share'],
            team_ratio_metrics['efficiency_vs_team_avg'],
            team_ratio_metrics['minutes_share']
        ))
