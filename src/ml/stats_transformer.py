"""
Stats Transformer Module

Extracted helper functions for transforming player statistics from raw
FEB API format to normalized format. Supports both legacy and modern data formats.
"""

from typing import Dict, Tuple, Optional
from datetime import datetime


class TypeConverter:
    """Helper class for safe type conversions."""
    
    @staticmethod
    def safe_int(value, default=0) -> int:
        """
        Safely convert value to integer.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
            
        Returns:
            Integer value or default
        """
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_float(value, default=0.0) -> float:
        """
        Safely convert value to float.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
            
        Returns:
            Float value or default
        """
        try:
            return float(value) if value else default
        except (ValueError, TypeError):
            return default


class MinutesParser:
    """Helper class for parsing playing time in different formats."""
    
    @staticmethod
    def parse_minutes(player: Dict) -> float:
        """
        Parse playing time from player data.
        
        Supports multiple formats:
        - "MM:SS" string
        - Seconds as integer/float
        - String with just number
        
        Args:
            player: Player data dictionary
            
        Returns:
            Minutes played as float
        """
        time_str = player.get("minFormatted", player.get("min", "0:00"))
        
        # If it's a number (seconds), convert to minutes
        if isinstance(time_str, (int, float)):
            return time_str / 60.0
        
        # If it's string with MM:SS format
        if isinstance(time_str, str) and ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 2:
                minutes = TypeConverter.safe_int(parts[0])
                seconds = TypeConverter.safe_int(parts[1])
                return minutes + seconds / 60.0
        
        # If it's string with just number
        if isinstance(time_str, str) and time_str.isdigit():
            return TypeConverter.safe_int(time_str) / 60.0
        
        return 0.0


class FormatDetector:
    """Helper class for detecting data format (legacy vs modern)."""
    
    @staticmethod
    def is_legacy_format(player: Dict) -> bool:
        """
        Check if player data is in legacy format.
        
        Legacy format uses English keys (playername, shirtnumber, etc.)
        Modern format uses FEB API keys (name, no, pts, etc.)
        
        Args:
            player: Player data dictionary
            
        Returns:
            True if legacy format, False if modern
        """
        return "playername" in player


class ShootingStatsExtractor:
    """Helper class for extracting shooting statistics."""
    
    @staticmethod
    def extract_shooting_stats(player: Dict, is_legacy: bool) -> Dict[str, int]:
        """
        Extract shooting statistics based on data format.
        
        Args:
            player: Player data dictionary
            is_legacy: True if legacy format, False if modern
            
        Returns:
            Dictionary with shooting stats (made/attempted for 2pt, 3pt, FT)
        """
        if is_legacy:
            # Legacy format: English keys
            three_made = TypeConverter.safe_int(player.get("three_points_made", 0))
            three_att = TypeConverter.safe_int(player.get("three_points_attempted", 0))
            two_made = TypeConverter.safe_int(player.get("two_points_made", 0))
            two_att = TypeConverter.safe_int(player.get("two_points_attempted", 0))
            field_goals_made = TypeConverter.safe_int(player.get("field_goals_made", 0))
            field_goals_att = TypeConverter.safe_int(player.get("field_goals_attempted", 0))
            ft_made = TypeConverter.safe_int(player.get("free_throws_made", 0))
            ft_att = TypeConverter.safe_int(player.get("free_throws_attempted", 0))
        else:
            # Modern format: FEB API keys (p1m/p1a, p2m/p2a, p3m/p3a)
            three_made = TypeConverter.safe_int(player.get("p3m", 0))
            three_att = TypeConverter.safe_int(player.get("p3a", 0))
            two_made = TypeConverter.safe_int(player.get("p2m", 0))
            two_att = TypeConverter.safe_int(player.get("p2a", 0))
            field_goals_made = two_made + three_made
            field_goals_att = two_att + three_att
            ft_made = TypeConverter.safe_int(player.get("p1m", 0))
            ft_att = TypeConverter.safe_int(player.get("p1a", 0))
        
        return {
            "three_made": three_made,
            "three_att": three_att,
            "two_made": two_made,
            "two_att": two_att,
            "field_goals_made": field_goals_made,
            "field_goals_att": field_goals_att,
            "ft_made": ft_made,
            "ft_att": ft_att
        }


class ShootingPercentageCalculator:
    """Helper class for calculating shooting percentages."""
    
    @staticmethod
    def calculate_percentages(shooting_stats: Dict[str, int]) -> Dict[str, float]:
        """
        Calculate shooting percentages from made/attempted stats.
        
        Args:
            shooting_stats: Dictionary with made/attempted stats
            
        Returns:
            Dictionary with percentage stats
        """
        three_pct = (
            (shooting_stats["three_made"] / shooting_stats["three_att"] * 100)
            if shooting_stats["three_att"] > 0 else 0.0
        )
        two_pct = (
            (shooting_stats["two_made"] / shooting_stats["two_att"] * 100)
            if shooting_stats["two_att"] > 0 else 0.0
        )
        field_goal_pct = (
            (shooting_stats["field_goals_made"] / shooting_stats["field_goals_att"] * 100)
            if shooting_stats["field_goals_att"] > 0 else 0.0
        )
        ft_pct = (
            (shooting_stats["ft_made"] / shooting_stats["ft_att"] * 100)
            if shooting_stats["ft_att"] > 0 else 0.0
        )
        
        return {
            "three_point_pct": three_pct,
            "two_point_pct": two_pct,
            "field_goal_pct": field_goal_pct,
            "free_throw_pct": ft_pct
        }


class AgeDateCalculator:
    """Helper class for calculating player age from birth year and game date."""
    
    @staticmethod
    def parse_game_year(game_date: str) -> Optional[int]:
        """
        Parse game year from date string in various formats.
        
        Supported formats:
        - ISO: "2025-10-04T19:00:00"
        - FEB: "04-10-2025 - 19:00" or "04-10-2025"
        - YYYY-MM-DD or DD-MM-YYYY
        
        Args:
            game_date: Date string
            
        Returns:
            Year as integer or None if parsing fails
        """
        if not game_date:
            return None
        
        try:
            # Format ISO: "2025-10-04T19:00:00"
            if 'T' in game_date or game_date.count('-') >= 2:
                try:
                    return datetime.fromisoformat(game_date.replace('Z', '+00:00')).year
                except:
                    pass
            
            # Format FEB: "04-10-2025 - 19:00" or "04-10-2025"
            date_part = game_date.split(' - ')[0].strip() if ' - ' in game_date else game_date.strip()
            parts = date_part.split('-')
            
            if len(parts) == 3:
                # Can be DD-MM-YYYY or YYYY-MM-DD
                if len(parts[0]) == 4:  # YYYY-MM-DD
                    return int(parts[0])
                else:  # DD-MM-YYYY
                    return int(parts[2])
        except (ValueError, IndexError):
            pass
        
        return None
    
    @staticmethod
    def validate_birth_year(birth_year_raw, player: Dict, game_year: Optional[int]) -> Optional[int]:
        """
        Validate and correct birth year if needed.
        
        Args:
            birth_year_raw: Raw birth year value
            player: Player data dictionary (may contain birth_date)
            game_year: Game year for validation
            
        Returns:
            Valid birth year or None
        """
        if not birth_year_raw:
            return None
        
        try:
            birth_year = int(birth_year_raw)
            
            # If we have game_year, check age reasonability (12-50 years)
            if game_year:
                age = game_year - birth_year
                if 12 <= age <= 50:
                    return birth_year
                
                # Try to parse from birth_date if available
                birth_date_str = player.get("birth_date", "")
                if birth_date_str and "/" in birth_date_str:
                    parts = birth_date_str.split("/")
                    if len(parts) == 3:
                        # Format DD/MM/YYYY
                        potential_year = TypeConverter.safe_int(parts[2])
                        if potential_year and 12 <= (game_year - potential_year) <= 50:
                            return potential_year
                
                return None  # Age not reasonable
            
            # No game_year - validate birth year is in reasonable range (1950-2020)
            if 1950 <= birth_year <= 2020:
                return birth_year
        except (ValueError, TypeError):
            pass
        
        return None
    
    @staticmethod
    def calculate_age(player: Dict, game_date: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
        """
        Calculate player age at game time.
        
        Args:
            player: Player data dictionary
            game_date: Game date string
            
        Returns:
            Tuple of (birth_year, age_at_game)
        """
        birth_year_raw = player.get("birth_year")
        game_year = AgeDateCalculator.parse_game_year(game_date) if game_date else None
        
        birth_year = AgeDateCalculator.validate_birth_year(birth_year_raw, player, game_year)
        
        if birth_year and game_year:
            age = game_year - birth_year
            if 12 <= age <= 50:
                return birth_year, age
        
        return birth_year, None


class GeneralStatsExtractor:
    """Helper class for extracting general statistics."""
    
    @staticmethod
    def extract_general_stats(player: Dict, is_legacy: bool) -> Dict:
        """
        Extract general statistics based on data format.
        
        Args:
            player: Player data dictionary
            is_legacy: True if legacy format, False if modern
            
        Returns:
            Dictionary with general stats
        """
        if is_legacy:
            # Legacy format: English keys
            return {
                "player_name": player.get("playername", "").strip(),
                "dorsal": player.get("shirtnumber", ""),
                "is_starter": player.get("is_starter", False),
                "points": TypeConverter.safe_int(player.get("points", 0)),
                "offensive_rebounds": TypeConverter.safe_int(player.get("offensive_rebounds", 0)),
                "defensive_rebounds": TypeConverter.safe_int(player.get("defensive_rebounds", 0)),
                "total_rebounds": TypeConverter.safe_int(player.get("total_rebounds", 0)),
                "assists": TypeConverter.safe_int(player.get("assists", 0)),
                "turnovers": TypeConverter.safe_int(player.get("turnovers", 0)),
                "steals": TypeConverter.safe_int(player.get("steals", 0)),
                "blocks": TypeConverter.safe_int(player.get("blocks", 0)),
                "blocks_received": TypeConverter.safe_int(player.get("blocks_received", 0)),
                "personal_fouls": TypeConverter.safe_int(player.get("personal_fouls", 0)),
                "fouls_received": TypeConverter.safe_int(player.get("fouls_received", 0)),
                "plus_minus": TypeConverter.safe_int(player.get("plus_minus", 0)),
                "efficiency": TypeConverter.safe_float(player.get("efficiency", 0))
            }
        else:
            # Modern format: FEB API keys
            return {
                "player_name": player.get("name", "").strip(),
                "dorsal": player.get("no", ""),
                "is_starter": player.get("inn", "0") == "1",
                "points": TypeConverter.safe_int(player.get("pts", 0)),
                "offensive_rebounds": TypeConverter.safe_int(player.get("ro", 0)),
                "defensive_rebounds": TypeConverter.safe_int(player.get("rd", 0)),
                "total_rebounds": TypeConverter.safe_int(player.get("rt", 0)),
                "assists": TypeConverter.safe_int(player.get("assist", 0)),
                "turnovers": TypeConverter.safe_int(player.get("to", 0)),
                "steals": TypeConverter.safe_int(player.get("st", 0)),
                "blocks": TypeConverter.safe_int(player.get("bs", 0)),
                "blocks_received": TypeConverter.safe_int(player.get("mt", 0)),
                "personal_fouls": TypeConverter.safe_int(player.get("pf", 0)),
                "fouls_received": TypeConverter.safe_int(player.get("rf", 0)),
                "plus_minus": TypeConverter.safe_int(player.get("pllss", 0)),
                "efficiency": TypeConverter.safe_float(player.get("val", 0))
            }


class StatsTransformer:
    """
    Main class for transforming player statistics.
    
    Orchestrates all helper classes to transform raw FEB API data into
    normalized format with calculated advanced metrics.
    """
    
    @staticmethod
    def transform_player_stats(
        player: Dict,
        is_home: bool,
        team_won: bool,
        game_date: Optional[str] = None,
        advanced_stats_calculator = None
    ) -> Dict:
        """
        Transform player statistics from raw format to normalized format.
        
        Args:
            player: Raw player data from FEB API
            is_home: Whether player's team is home team
            team_won: Whether player's team won
            game_date: Game date string for age calculation
            advanced_stats_calculator: Function to calculate advanced metrics
            
        Returns:
            Dictionary with normalized and calculated statistics
        """
        # Detect format
        is_legacy = FormatDetector.is_legacy_format(player)
        
        # Parse minutes
        minutes_played = MinutesParser.parse_minutes(player)
        
        # Extract shooting stats
        shooting_stats = ShootingStatsExtractor.extract_shooting_stats(player, is_legacy)
        
        # Calculate percentages
        percentages = ShootingPercentageCalculator.calculate_percentages(shooting_stats)
        
        # Calculate age
        birth_year, age_at_game = AgeDateCalculator.calculate_age(player, game_date)
        
        # Extract general stats
        general_stats = GeneralStatsExtractor.extract_general_stats(player, is_legacy)
        
        # Prepare data for advanced metrics calculation
        stats_for_advanced = {
            'pts': general_stats["points"],
            'fgm': shooting_stats["field_goals_made"],
            'fga': shooting_stats["field_goals_att"],
            'fg3m': shooting_stats["three_made"],
            'ftm': shooting_stats["ft_made"],
            'fta': shooting_stats["ft_att"],
            'orb': general_stats["offensive_rebounds"],
            'drb': general_stats["defensive_rebounds"],
            'reb': general_stats["total_rebounds"],
            'ast': general_stats["assists"],
            'tov': general_stats["turnovers"],
            'stl': general_stats["steals"],
            'blk': general_stats["blocks"],
            'minutes': minutes_played
        }
        
        # Calculate advanced metrics if calculator provided
        advanced_stats = {}
        if advanced_stats_calculator:
            advanced_stats = advanced_stats_calculator(stats_for_advanced)
        
        # Build normalized output
        return {
            "dorsal": general_stats["dorsal"],
            "name": general_stats["player_name"],
            "birth_year": birth_year,
            "age_at_game": age_at_game,
            "is_home": is_home,
            "is_starter": general_stats["is_starter"],
            "team_won": team_won,
            
            # Time
            "minutes_played": minutes_played,
            
            # Points
            "points": general_stats["points"],
            "field_goals_made": shooting_stats["field_goals_made"],
            "field_goals_attempted": shooting_stats["field_goals_att"],
            "field_goal_pct": percentages["field_goal_pct"],
            "three_points_made": shooting_stats["three_made"],
            "three_points_attempted": shooting_stats["three_att"],
            "three_point_pct": percentages["three_point_pct"],
            "two_points_made": shooting_stats["two_made"],
            "two_points_attempted": shooting_stats["two_att"],
            "two_point_pct": percentages["two_point_pct"],
            "free_throws_made": shooting_stats["ft_made"],
            "free_throws_attempted": shooting_stats["ft_att"],
            "free_throw_pct": percentages["free_throw_pct"],
            
            # Rebounds
            "offensive_rebounds": general_stats["offensive_rebounds"],
            "defensive_rebounds": general_stats["defensive_rebounds"],
            "total_rebounds": general_stats["total_rebounds"],
            
            # Passes and turnovers
            "assists": general_stats["assists"],
            "turnovers": general_stats["turnovers"],
            "steals": general_stats["steals"],
            
            # Defense
            "blocks": general_stats["blocks"],
            "blocks_received": general_stats["blocks_received"],
            "personal_fouls": general_stats["personal_fouls"],
            "fouls_received": general_stats["fouls_received"],
            
            # Legacy metrics
            "plus_minus": general_stats["plus_minus"],
            "efficiency_rating": general_stats["efficiency"],
            
            # Advanced metrics
            "true_shooting_pct": advanced_stats.get('true_shooting_pct'),
            "effective_fg_pct": advanced_stats.get('effective_fg_pct'),
            "offensive_rating": advanced_stats.get('offensive_rating'),
            "player_efficiency_rating": advanced_stats.get('player_efficiency_rating'),
            "turnover_pct": advanced_stats.get('turnover_pct'),
            "offensive_rebound_pct": advanced_stats.get('offensive_rebound_pct'),
            "defensive_rebound_pct": advanced_stats.get('defensive_rebound_pct'),
            "free_throw_rate": advanced_stats.get('free_throw_rate'),
            "assist_to_turnover_ratio": advanced_stats.get('assist_to_turnover_ratio'),
            "usage_rate": advanced_stats.get('usage_rate'),
            "win_shares": advanced_stats.get('win_shares'),
            "win_shares_per_36": advanced_stats.get('win_shares_per_36')
        }
