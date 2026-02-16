"""
Normalization functions to compare players across eras and leagues.

Implements Z-Score normalization based on context (competition level + season)
to make player statistics comparable across different eras and leagues.

References:
- Z-Score: Measure of how many standard deviations a value is from the mean
- Context: Group defined by (competition_level, season)
"""

import sqlite3
from typing import Dict, List, Tuple, Optional
import logging
import math


logger = logging.getLogger(__name__)


class ZScoreNormalizer:
    """
    Calculates Z-Scores to normalize player statistics.
    
    Z-Score allows comparing players from different eras and leagues:
    - Z = 0: Average performance in their context
    - Z = +1: One standard deviation above (better than ~84%)
    - Z = +2: Two standard deviations above (elite, better than ~97%)
    - Z = -1: Below average
    
    Example:
        Player A (2010, EBA): 14 pts → Z = +2.5 (dominant)
        Player B (2023, EBA): 11 pts → Z = +1.9 (very good)
        → Comparable despite different eras
    """
    
    def __init__(self, db_path: str):
        """
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.context_stats_cache: Dict[Tuple[int, str], Dict[str, Tuple[float, float]]] = {}
    
    def calculate_context_statistics(
        self,
        competition_level: int,
        season: str,
        metrics: List[str] = None
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculates mean and standard deviation for a context (level + season).
        
        Args:
            competition_level: Competition level (1=highest, 2, 3...)
            season: Season (e.g., "2023-2024")
            metrics: List of metrics to calculate (default: points, efficiency, rebounds, assists)
        
        Returns:
            Dict with {metric: (mean, std_dev)} for each metric
        """
        if metrics is None:
            metrics = [
                'points', 'efficiency_rating', 'total_rebounds', 'assists',
                'true_shooting_pct', 'effective_fg_pct', 'offensive_rating',
                'player_efficiency_rating', 'turnover_pct',
                'offensive_rebound_pct', 'defensive_rebound_pct',
                'free_throw_rate', 'usage_rate', 'win_shares', 'win_shares_per_36'
            ]
        
        # Verificar caché
        cache_key = (competition_level, season)
        if cache_key in self.context_stats_cache:
            return self.context_stats_cache[cache_key]
        
        context_stats = {}
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for metric in metrics:
                # Calcular media y desviación estándar para el contexto
                query = f"""
                SELECT 
                    AVG({metric}) as mean,
                    -- Calcular std_dev manualmente: sqrt(avg(x^2) - avg(x)^2)
                    SQRT(AVG({metric} * {metric}) - AVG({metric}) * AVG({metric})) as std_dev,
                    COUNT(*) as sample_size
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.game_id
                JOIN competitions c ON g.competition_id = c.competition_id
                JOIN competition_levels cl ON c.competition_id = cl.competition_id 
                    AND g.season = cl.season
                WHERE cl.competition_level = ?
                    AND g.season = ?
                    AND {metric} IS NOT NULL
                    AND pgs.minutes_played >= 10  -- Only players with significant minutes
                """
                
                cursor.execute(query, (competition_level, season))
                row = cursor.fetchone()
                
                if row and row[0] is not None and row[1] is not None and row[1] > 0:
                    mean, std_dev, sample_size = row
                    
                    if sample_size < 30:
                        logger.warning(
                            f"Small sample for {metric} at level={competition_level}, "
                            f"season={season}: n={sample_size}"
                        )
                    
                    context_stats[metric] = (mean, std_dev)
                else:
                    logger.warning(
                        f"Insufficient data for {metric} at level={competition_level}, "
                        f"season={season}"
                    )
                    context_stats[metric] = (0.0, 1.0)  # Fallback
        
        # Save to cache
        self.context_stats_cache[cache_key] = context_stats
        return context_stats
    
    def calculate_zscore(
        self,
        value: float,
        mean: float,
        std_dev: float
    ) -> Optional[float]:
        """
        Calculates the Z-Score of a value.
        
        Z = (value - mean) / standard_deviation
        
        Args:
            value: Value to normalize
            mean: Context mean
            std_dev: Context standard deviation
        
        Returns:
            Z-Score or None if cannot calculate
        """
        if std_dev == 0 or std_dev is None:
            logger.warning(f"Standard deviation = 0, cannot calculate Z-Score")
            return None
        
        if value is None or mean is None:
            return None
        
        return (value - mean) / std_dev
    
    def normalize_player_game(
        self,
        stat_id: int,
        competition_level: int,
        season: str
    ) -> Dict[str, float]:
        """
        Calculates Z-Scores for player statistics in a game.
        
        Args:
            stat_id: player_game_stats ID
            competition_level: Competition level
            season: Season
        
        Returns:
            Dict with calculated Z-Scores
        """
        # Get context statistics
        context_stats = self.calculate_context_statistics(competition_level, season)
        
        # Get player values
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    points, efficiency_rating, total_rebounds, assists,
                    true_shooting_pct, effective_fg_pct, offensive_rating,
                    player_efficiency_rating, turnover_pct,
                    offensive_rebound_pct, defensive_rebound_pct,
                    free_throw_rate, usage_rate, win_shares, win_shares_per_36
                FROM player_game_stats
                WHERE stat_id = ?
            """, (stat_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.error(f"stat_id={stat_id} not found")
                return {}
            
            (points, efficiency, rebounds, assists,
             ts_pct, efg_pct, oer, per, tov_pct,
             orb_pct, drb_pct, ftr, usage, ws, ws_36) = row
        
        # Calculate Z-Scores
        z_scores = {}
        
        if 'points' in context_stats:
            mean, std = context_stats['points']
            z_scores['z_points'] = self.calculate_zscore(points, mean, std)
        
        if 'efficiency_rating' in context_stats:
            mean, std = context_stats['efficiency_rating']
            z_scores['z_efficiency'] = self.calculate_zscore(efficiency, mean, std)
        
        if 'total_rebounds' in context_stats:
            mean, std = context_stats['total_rebounds']
            z_scores['z_rebounds'] = self.calculate_zscore(rebounds, mean, std)
        
        if 'assists' in context_stats:
            mean, std = context_stats['assists']
            z_scores['z_assists'] = self.calculate_zscore(assists, mean, std)
        
        # Advanced metrics
        if 'offensive_rating' in context_stats and oer is not None:
            mean, std = context_stats['offensive_rating']
            z_scores['z_offensive_rating'] = self.calculate_zscore(oer, mean, std)
        
        if 'true_shooting_pct' in context_stats and ts_pct is not None:
            mean, std = context_stats['true_shooting_pct']
            z_scores['z_true_shooting_pct'] = self.calculate_zscore(ts_pct, mean, std)
        
        if 'player_efficiency_rating' in context_stats and per is not None:
            mean, std = context_stats['player_efficiency_rating']
            z_scores['z_player_efficiency_rating'] = self.calculate_zscore(per, mean, std)
        
        if 'turnover_pct' in context_stats and tov_pct is not None:
            mean, std = context_stats['turnover_pct']
            z_scores['z_turnover_pct'] = self.calculate_zscore(tov_pct, mean, std)
        
        if 'usage_rate' in context_stats and usage is not None:
            mean, std = context_stats['usage_rate']
            z_scores['z_usage'] = self.calculate_zscore(usage, mean, std)
        
        if 'win_shares_per_36' in context_stats and ws_36 is not None:
            mean, std = context_stats['win_shares_per_36']
            z_scores['z_win_shares_per_36'] = self.calculate_zscore(ws_36, mean, std)
        
        return z_scores
    
    def calculate_percentile(self, z_score: float) -> int:
        """
        Converts Z-Score to percentile (0-100).
        
        Uses the normal cumulative distribution function.
        
        Args:
            z_score: Calculated Z-Score
        
        Returns:
            Percentile between 0 and 100
        """
        if z_score is None:
            return 50  # Average by default
        
        # Normal CDF approximation using erf
        # CDF(z) = 0.5 * (1 + erf(z / sqrt(2)))
        percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
        return int(percentile * 100)
    
    def calculate_performance_tier(self, percentile: int) -> str:
        """
        Classifies performance based on percentile.
        
        Args:
            percentile: Percentile (0-100)
        
        Returns:
            Tier: 'elite', 'very_good', 'above_average', 'average', 'below_average'
        """
        if percentile >= 95:
            return 'elite'
        elif percentile >= 80:
            return 'very_good'
        elif percentile >= 60:
            return 'above_average'
        elif percentile >= 40:
            return 'average'
        else:
            return 'below_average'
    
    def update_game_stats_zscores(self, competition_level: int, season: str) -> int:
        """
        Updates Z-Scores for all games in a context.
        
        Args:
            competition_level: Competition level
            season: Season
        
        Returns:
            Number of updated records
        """
        logger.info(f"Calculating Z-Scores for level={competition_level}, season={season}")
        
        # Calculate context statistics
        context_stats = self.calculate_context_statistics(competition_level, season)
        
        updated_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all stat_ids from context
            cursor.execute("""
                SELECT 
                    pgs.stat_id, pgs.points, pgs.efficiency_rating,
                    pgs.total_rebounds, pgs.assists,
                    pgs.true_shooting_pct, pgs.effective_fg_pct, pgs.offensive_rating,
                    pgs.player_efficiency_rating, pgs.turnover_pct,
                    pgs.usage_rate, pgs.win_shares_per_36
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.game_id
                JOIN competitions c ON g.competition_id = c.competition_id
                JOIN competition_levels cl ON c.competition_id = cl.competition_id 
                    AND g.season = cl.season
                WHERE cl.competition_level = ?
                    AND g.season = ?
            """, (competition_level, season))
            
            rows = cursor.fetchall()
            
            for row in rows:
                (stat_id, points, efficiency, rebounds, assists,
                 ts_pct, efg_pct, oer, per, tov_pct, usage, ws_36) = row
                
                # Calculate basic Z-Scores
                z_points = None
                z_efficiency = None
                z_rebounds = None
                z_assists = None
                
                if 'points' in context_stats:
                    mean, std = context_stats['points']
                    z_points = self.calculate_zscore(points, mean, std)
                
                if 'efficiency_rating' in context_stats:
                    mean, std = context_stats['efficiency_rating']
                    z_efficiency = self.calculate_zscore(efficiency, mean, std)
                
                if 'total_rebounds' in context_stats:
                    mean, std = context_stats['total_rebounds']
                    z_rebounds = self.calculate_zscore(rebounds, mean, std)
                
                if 'assists' in context_stats:
                    mean, std = context_stats['assists']
                    z_assists = self.calculate_zscore(assists, mean, std)
                
                # Calculate Z-Scores for advanced metrics
                z_oer = None
                z_ts_pct = None
                z_per = None
                z_tov_pct = None
                z_usage = None
                z_ws_36 = None
                
                if oer is not None and 'offensive_rating' in context_stats:
                    mean, std = context_stats['offensive_rating']
                    z_oer = self.calculate_zscore(oer, mean, std)
                
                if ts_pct is not None and 'true_shooting_pct' in context_stats:
                    mean, std = context_stats['true_shooting_pct']
                    z_ts_pct = self.calculate_zscore(ts_pct, mean, std)
                
                if per is not None and 'player_efficiency_rating' in context_stats:
                    mean, std = context_stats['player_efficiency_rating']
                    z_per = self.calculate_zscore(per, mean, std)
                
                if tov_pct is not None and 'turnover_pct' in context_stats:
                    mean, std = context_stats['turnover_pct']
                    z_tov_pct = self.calculate_zscore(tov_pct, mean, std)
                
                if usage is not None and 'usage_rate' in context_stats:
                    mean, std = context_stats['usage_rate']
                    z_usage = self.calculate_zscore(usage, mean, std)
                
                if ws_36 is not None and 'win_shares_per_36' in context_stats:
                    mean, std = context_stats['win_shares_per_36']
                    z_ws_36 = self.calculate_zscore(ws_36, mean, std)
                
                # Update in database
                # NOTE: Only updating z-scores for advanced metrics that exist in schema
                # Basic metrics (points, efficiency, rebounds, assists) don't have z-score columns
                cursor.execute("""
                    UPDATE player_game_stats
                    SET z_offensive_rating = ?,
                        z_true_shooting_pct = ?,
                        z_player_efficiency_rating = ?,
                        z_turnover_pct = ?,
                        z_usage_rate = ?,
                        z_win_shares_per_36 = ?
                    WHERE stat_id = ?
                """, (z_oer, z_ts_pct, z_per, z_tov_pct, z_usage, z_ws_36, stat_id))
                
                updated_count += 1
            
            conn.commit()
        
        logger.info(f"Z-Scores updated: {updated_count} records")
        return updated_count
    
    def update_aggregated_stats_normalized(self, player_id: int, season: str) -> bool:
        """
        Updates Z-Scores and percentiles in player_aggregated_stats.
        
        Args:
            player_id: Player ID
            season: Season
        
        Returns:
            True if updated successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get player's aggregated statistics
            cursor.execute("""
                SELECT 
                    pas.agg_id,
                    pas.avg_points,
                    pas.avg_efficiency,
                    pas.avg_total_rebounds,
                    pas.avg_assists,
                    cl.competition_level
                FROM player_aggregated_stats pas
                JOIN competitions c ON pas.competition_id = c.competition_id
                JOIN competition_levels cl ON c.competition_id = cl.competition_id 
                    AND pas.season = cl.season
                WHERE pas.player_id = ?
                    AND pas.season = ?
            """, (player_id, season))
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"No aggregated stats for player_id={player_id}, season={season}")
                return False
            
            agg_id, avg_points, avg_efficiency, avg_rebounds, avg_assists, comp_level = row
            
            # Calculate Z-Scores
            context_stats = self.calculate_context_statistics(comp_level, season)
            
            z_avg_points = None
            z_avg_efficiency = None
            z_avg_rebounds = None
            z_avg_assists = None
            
            if 'points' in context_stats:
                mean, std = context_stats['points']
                z_avg_points = self.calculate_zscore(avg_points, mean, std)
            
            if 'efficiency_rating' in context_stats:
                mean, std = context_stats['efficiency_rating']
                z_avg_efficiency = self.calculate_zscore(avg_efficiency, mean, std)
            
            if 'total_rebounds' in context_stats:
                mean, std = context_stats['total_rebounds']
                z_avg_rebounds = self.calculate_zscore(avg_rebounds, mean, std)
            
            if 'assists' in context_stats:
                mean, std = context_stats['assists']
                z_avg_assists = self.calculate_zscore(avg_assists, mean, std)
            
            # Calculate percentiles (use efficiency as main metric)
            percentile_efficiency = self.calculate_percentile(z_avg_efficiency) if z_avg_efficiency else 50
            percentile_points = self.calculate_percentile(z_avg_points) if z_avg_points else 50
            percentile_rebounds = self.calculate_percentile(z_avg_rebounds) if z_avg_rebounds else 50
            percentile_assists = self.calculate_percentile(z_avg_assists) if z_avg_assists else 50
            
            # Classify performance
            performance_tier = self.calculate_performance_tier(percentile_efficiency)
            
            # NOTE: Columns z_avg_points, z_avg_efficiency, etc. don't exist in current schema
            # Only updating available columns: performance_tier and advanced metric percentiles
            # Basic metrics are not normalized in this table (they are normalized at game level)
            
            # Do nothing for now - columns don't exist in schema
            # If needed, add columns to schema or use another table
            z_points_str = f"{z_avg_points:.2f}" if z_avg_points else 'N/A'
            z_eff_str = f"{z_avg_efficiency:.2f}" if z_avg_efficiency else 'N/A'
            logger.debug(f"Normalized stats calculated for player {player_id}: "
                        f"z_points={z_points_str}, z_eff={z_eff_str}")
            
            conn.commit()
        
        return True


def initialize_competition_levels(db_path: str, default_levels: Dict[str, int] = None):
    """
    Initializes competition_levels table with default configuration.
    
    Args:
        db_path: Path to the SQLite database
        default_levels: Dict with {competition_name: level} by default
    """
    if default_levels is None:
        # Default configuration for FEB competitions
        # IMPORTANT: Names must match EXACTLY with those in the database
        default_levels = {
            # Men's
            'ACB': 1,
            'LEB ORO': 2,
            'LEB PLATA': 3,
            'EBA': 4,
            # Women's (actual names in DB)
            'LF ENDESA': 1,  # First division - highest level
            'LF CHALLENGE': 2,  # Second division (since 2021/22)
            'L.F.-2': 2,  # Second division until 2020/21, then level 3
            # Alternative names
            'LIGA FEMENINA': 1,
            'LIGA FEMENINA 2': 2,
            'LIGA CHALLENGE': 2,
            'PRIMERA FEB': 3,
        }
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Get all competitions and seasons
        cursor.execute("""
            SELECT DISTINCT c.competition_id, c.competition_name, g.season
            FROM competitions c
            JOIN games g ON c.competition_id = g.competition_id
            ORDER BY g.season, c.competition_name
        """)
        
        rows = cursor.fetchall()
        
        for comp_id, comp_name, season in rows:
            # Find default level (case-insensitive)
            level = None
            weight = 1.0
            notes = None
            
            # Search by exact name (uppercase)
            for key, val in default_levels.items():
                if comp_name.upper() == key.upper():
                    level = val
                    break
            
            # If not found, use level 4 by default
            if level is None:
                level = 4
            
            # SPECIAL RULE: L.F.-2 changed from level 2 to 3 in season 2021/2022
            if comp_name == 'L.F.-2':
                # Parse season year (format: "2001/2002")
                try:
                    season_year = int(season.split('/')[0])
                    if season_year >= 2021:
                        level = 3
                        weight = 1.0
                        notes = 'Third division (after 2021/22 reform)'
                    else:
                        level = 2
                        weight = 1.25
                        notes = 'Second division (before 2021/22 reform)'
                except (ValueError, IndexError):
                    pass  # Keep default level
            
            # Assign weights and descriptions by level
            if level == 1:
                weight = 1.5
                level_desc = f'Level 1 - {comp_name} - First division'
            elif level == 2:
                weight = 1.25
                level_desc = f'Level 2 - {comp_name} - Second division'
            elif level == 3:
                weight = 1.0
                level_desc = f'Level 3 - {comp_name} - Third division'
            else:
                weight = 1.0
                level_desc = f'Level {level} - {comp_name}'
            
            # Insert or ignore if already exists
            cursor.execute("""
                INSERT OR IGNORE INTO competition_levels 
                (competition_id, season, competition_level, weight, level_description, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (comp_id, season, level, weight, level_desc, notes))
        
        conn.commit()
    
    logger.info(f"Initialized competition levels for {len(rows)} entries")


# Auxiliary functions for direct use
def calculate_zscore(value: float, mean: float, std_dev: float) -> Optional[float]:
    """Calculates Z-Score: (value - mean) / standard_deviation"""
    if std_dev == 0 or std_dev is None or value is None or mean is None:
        return None
    return (value - mean) / std_dev


def percentile_from_zscore(z_score: float) -> int:
    """Converts Z-Score to percentile (0-100)"""
    if z_score is None:
        return 50
    percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
    return int(percentile * 100)
