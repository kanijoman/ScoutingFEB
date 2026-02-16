"""
Player Stats Aggregator Module

Extracted helper functions for aggregating player statistics.
Breaks down complex aggregation logic into testable, reusable components.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import logging


class StatsExtractor:
    """Helper class for extracting stats from database rows into numpy arrays."""
    
    @staticmethod
    def extract_basic_stats(stats: List[Dict[str, Any]]) -> Dict[str, np.ndarray]:
        """
        Extract basic stats from game stats list into numpy arrays.
        
        Args:
            stats: List of game stats dictionaries
            
        Returns:
            Dictionary with numpy arrays for each stat
        """
        return {
            'minutes': np.array([s["minutes_played"] for s in stats]),
            'points': np.array([s["points"] for s in stats]),
            'efficiency': np.array([s["efficiency_rating"] for s in stats]),
            'fg_pct': np.array([s["field_goal_pct"] for s in stats]),
            'three_pct': np.array([s["three_point_pct"] for s in stats]),
            'ft_pct': np.array([s["free_throw_pct"] for s in stats]),
            'rebounds': np.array([s["total_rebounds"] for s in stats]),
            'assists': np.array([s["assists"] for s in stats]),
            'wins': np.array([s["team_won"] for s in stats])
        }
    
    @staticmethod
    def extract_advanced_stats(stats: List[Dict[str, Any]]) -> Dict[str, np.ndarray]:
        """
        Extract advanced metrics from game stats list into numpy arrays.
        
        Handles None values by replacing with 0.
        
        Args:
            stats: List of game stats dictionaries
            
        Returns:
            Dictionary with numpy arrays for each advanced stat
        """
        return {
            'ts_pct': np.array([s["true_shooting_pct"] if s["true_shooting_pct"] is not None else 0 for s in stats]),
            'efg_pct': np.array([s["effective_fg_pct"] if s["effective_fg_pct"] is not None else 0 for s in stats]),
            'oer': np.array([s["offensive_rating"] if s["offensive_rating"] is not None else 0 for s in stats]),
            'per': np.array([s["player_efficiency_rating"] if s["player_efficiency_rating"] is not None else 0 for s in stats]),
            'tov_pct': np.array([s["turnover_pct"] if s["turnover_pct"] is not None else 0 for s in stats]),
            'orb_pct': np.array([s["offensive_rebound_pct"] if s["offensive_rebound_pct"] is not None else 0 for s in stats]),
            'drb_pct': np.array([s["defensive_rebound_pct"] if s["defensive_rebound_pct"] is not None else 0 for s in stats]),
            'ws': np.array([s["win_shares"] if s["win_shares"] is not None else 0 for s in stats]),
            'ws_36': np.array([s["win_shares_per_36"] if s["win_shares_per_36"] is not None else 0 for s in stats])
        }


class StatsAggregator:
    """Helper class for calculating aggregated statistics."""
    
    @staticmethod
    def calculate_basic_averages(basic_stats: Dict[str, np.ndarray]) -> Dict[str, float]:
        """
        Calculate averages for basic statistics.
        
        For percentage stats (fg_pct, three_pct, ft_pct), only averages
        values > 0 to avoid including games with no attempts.
        
        Args:
            basic_stats: Dictionary of numpy arrays with basic stats
            
        Returns:
            Dictionary with average values
        """
        fg_pct = basic_stats['fg_pct']
        three_pct = basic_stats['three_pct']
        ft_pct = basic_stats['ft_pct']
        
        return {
            'avg_minutes': float(np.mean(basic_stats['minutes'])),
            'avg_points': float(np.mean(basic_stats['points'])),
            'avg_efficiency': float(np.mean(basic_stats['efficiency'])),
            'avg_fg_pct': float(np.mean(fg_pct[fg_pct > 0])) if np.any(fg_pct > 0) else 0.0,
            'avg_three_pct': float(np.mean(three_pct[three_pct > 0])) if np.any(three_pct > 0) else 0.0,
            'avg_ft_pct': float(np.mean(ft_pct[ft_pct > 0])) if np.any(ft_pct > 0) else 0.0,
            'avg_rebounds': float(np.mean(basic_stats['rebounds'])),
            'avg_assists': float(np.mean(basic_stats['assists']))
        }
    
    @staticmethod
    def calculate_advanced_averages(advanced_stats: Dict[str, np.ndarray]) -> Dict[str, Optional[float]]:
        """
        Calculate averages for advanced metrics.
        
        Returns None for metrics with no valid values (all zeros).
        Uses > 0 filter for most metrics, != 0 for PER (can be negative).
        
        Args:
            advanced_stats: Dictionary of numpy arrays with advanced stats
            
        Returns:
            Dictionary with average values (can contain None)
        """
        ts_pct = advanced_stats['ts_pct']
        efg_pct = advanced_stats['efg_pct']
        oer = advanced_stats['oer']
        per = advanced_stats['per']
        tov_pct = advanced_stats['tov_pct']
        orb_pct = advanced_stats['orb_pct']
        drb_pct = advanced_stats['drb_pct']
        ws_36 = advanced_stats['ws_36']
        
        return {
            'avg_ts_pct': float(np.mean(ts_pct[ts_pct > 0])) if np.any(ts_pct > 0) else None,
            'avg_efg_pct': float(np.mean(efg_pct[efg_pct > 0])) if np.any(efg_pct > 0) else None,
            'avg_oer': float(np.mean(oer[oer > 0])) if np.any(oer > 0) else None,
            'avg_per': float(np.mean(per[per != 0])) if np.any(per != 0) else None,
            'avg_tov_pct': float(np.mean(tov_pct[tov_pct > 0])) if np.any(tov_pct > 0) else None,
            'avg_orb_pct': float(np.mean(orb_pct[orb_pct > 0])) if np.any(orb_pct > 0) else None,
            'avg_drb_pct': float(np.mean(drb_pct[drb_pct > 0])) if np.any(drb_pct > 0) else None,
            'avg_ws_36': float(np.mean(ws_36[ws_36 > 0])) if np.any(ws_36 > 0) else None
        }
    
    @staticmethod
    def calculate_totals(basic_stats: Dict[str, np.ndarray]) -> Dict[str, int]:
        """
        Calculate total sums for counting stats.
        
        Args:
            basic_stats: Dictionary of numpy arrays with basic stats
            
        Returns:
            Dictionary with total values
        """
        return {
            'total_points': int(np.sum(basic_stats['points'])),
            'total_rebounds': int(np.sum(basic_stats['rebounds'])),
            'total_assists': int(np.sum(basic_stats['assists']))
        }
    
    @staticmethod
    def calculate_std_deviations(basic_stats: Dict[str, np.ndarray]) -> Dict[str, float]:
        """
        Calculate standard deviations for variability metrics.
        
        Args:
            basic_stats: Dictionary of numpy arrays with basic stats
            
        Returns:
            Dictionary with standard deviation values
        """
        return {
            'std_points': float(np.std(basic_stats['points'])),
            'std_efficiency': float(np.std(basic_stats['efficiency']))
        }
    
    @staticmethod
    def calculate_trends(
        basic_stats: Dict[str, np.ndarray],
        games_played: int,
        min_games: int = 3
    ) -> Dict[str, float]:
        """
        Calculate linear regression trends for performance metrics.
        
        Uses simple linear regression (polyfit) to detect improvement/decline.
        Requires minimum number of games for meaningful trend.
        
        Args:
            basic_stats: Dictionary of numpy arrays with basic stats
            games_played: Number of games played
            min_games: Minimum games required for trend calculation
            
        Returns:
            Dictionary with trend slopes (0.0 if insufficient games)
        """
        if games_played >= min_games:
            x = np.arange(games_played)
            trend_points = float(np.polyfit(x, basic_stats['points'], 1)[0])
            trend_efficiency = float(np.polyfit(x, basic_stats['efficiency'], 1)[0])
        else:
            trend_points = 0.0
            trend_efficiency = 0.0
        
        return {
            'trend_points': trend_points,
            'trend_efficiency': trend_efficiency
        }
    
    @staticmethod
    def calculate_win_percentage(basic_stats: Dict[str, np.ndarray]) -> float:
        """
        Calculate team win percentage when player participated.
        
        Args:
            basic_stats: Dictionary of numpy arrays with basic stats
            
        Returns:
            Win percentage (0-100)
        """
        return float(np.mean(basic_stats['wins']) * 100)
    
    @staticmethod
    def calculate_total_win_shares(advanced_stats: Dict[str, np.ndarray]) -> float:
        """
        Calculate total win shares accumulated.
        
        Args:
            advanced_stats: Dictionary of numpy arrays with advanced stats
            
        Returns:
            Total win shares
        """
        return float(np.sum(advanced_stats['ws']))
    
    @staticmethod
    def extract_date_range(stats: List[Dict[str, Any]]) -> Tuple[str, str]:
        """
        Extract first and last game dates from stats list.
        
        Args:
            stats: List of game stats dictionaries (must be sorted by date)
            
        Returns:
            Tuple of (date_from, date_to)
        """
        return stats[0]["game_date"], stats[-1]["game_date"]
    
    @staticmethod
    def calculate_average_age(stats: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate average age across all games.
        
        Args:
            stats: List of game stats dictionaries or sqlite3.Row objects
            
        Returns:
            Average age or None if age not available
        """
        ages = []
        for s in stats:
            try:
                # Try dict access first, then attribute access for Row objects
                age = s.get("age") if hasattr(s, 'get') else s["age"] if "age" in s.keys() else None
                if age is not None:
                    ages.append(age)
            except (KeyError, IndexError):
                continue
        
        return float(np.mean(ages)) if ages else None


class AggregationQueryBuilder:
    """Helper class for building aggregation queries."""
    
    @staticmethod
    def get_player_season_stats_query() -> str:
        """
        Get SQL query for fetching all game stats for a player/season/competition.
        
        Returns:
            SQL query string
        """
        return """
            SELECT 
                pgs.*,
                g.game_date
            FROM player_game_stats pgs
            JOIN games g ON pgs.game_id = g.game_id
            WHERE pgs.player_id = ?
                AND g.season = ?
                AND g.competition_id = ?
            ORDER BY g.game_date
        """
    
    @staticmethod
    def get_insert_aggregates_query() -> str:
        """
        Get SQL query for inserting aggregated stats.
        
        Only inserts core calculated fields. Z-scores, percentiles, and tiers
        are calculated separately via normalization step.
        
        Returns:
            SQL query string
        """
        return """
            INSERT OR REPLACE INTO player_aggregated_stats (
                player_id, season, competition_id, games_played,
                date_from, date_to, avg_age,
                avg_minutes, avg_points, avg_field_goal_pct,
                avg_three_point_pct, avg_free_throw_pct,
                avg_total_rebounds, avg_assists, avg_efficiency,
                total_points, total_rebounds, total_assists,
                std_points, std_efficiency,
                trend_points, trend_efficiency,
                avg_true_shooting_pct, avg_effective_fg_pct, avg_offensive_rating,
                avg_player_efficiency_rating, avg_turnover_pct,
                avg_offensive_rebound_pct, avg_defensive_rebound_pct,
                avg_win_shares_per_36,
                win_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
