"""
Tests for StatsTransformer module.

Validates the extracted helper functions for transforming player statistics
from raw FEB API format to normalized format.
"""

import pytest
from src.ml.stats_transformer import (
    TypeConverter,
    MinutesParser,
    FormatDetector,
    ShootingStatsExtractor,
    ShootingPercentageCalculator,
    AgeDateCalculator,
    GeneralStatsExtractor,
    StatsTransformer
)


class TestTypeConverter:
    """Test safe type conversion functions."""
    
    def test_safe_int_with_valid_int(self):
        """Convert valid integer."""
        assert TypeConverter.safe_int("42") == 42
        assert TypeConverter.safe_int(42) == 42
    
    def test_safe_int_with_invalid(self):
        """Invalid values return default."""
        assert TypeConverter.safe_int("abc", default=0) == 0
        assert TypeConverter.safe_int(None, default=0) == 0
        assert TypeConverter.safe_int("", default=5) == 5
    
    def test_safe_float_with_valid_float(self):
        """Convert valid float."""
        assert TypeConverter.safe_float("3.14") == 3.14
        assert TypeConverter.safe_float(3.14) == 3.14
    
    def test_safe_float_with_invalid(self):
        """Invalid values return default."""
        assert TypeConverter.safe_float("abc", default=0.0) == 0.0
        assert TypeConverter.safe_float(None, default=1.5) == 1.5


class TestMinutesParser:
    """Test playing time parsing."""
    
    def test_parse_minutes_from_mm_ss_format(self):
        """Parse MM:SS format."""
        player = {"minFormatted": "25:30"}
        minutes = MinutesParser.parse_minutes(player)
        assert minutes == 25.5
    
    def test_parse_minutes_from_seconds(self):
        """Parse seconds as number."""
        player = {"min": 1500}  # 25 minutes
        minutes = MinutesParser.parse_minutes(player)
        assert minutes == 25.0
    
    def test_parse_minutes_from_string_number(self):
        """Parse string with just number."""
        player = {"min": "1500"}
        minutes = MinutesParser.parse_minutes(player)
        assert minutes == 25.0
    
    def test_parse_minutes_with_zero(self):
        """Handle zero minutes."""
        player = {"min": "0:00"}
        minutes = MinutesParser.parse_minutes(player)
        assert minutes == 0.0
    
    def test_parse_minutes_missing_data(self):
        """Handle missing data."""
        player = {}
        minutes = MinutesParser.parse_minutes(player)
        assert minutes == 0.0


class TestFormatDetector:
    """Test format detection."""
    
    def test_detect_legacy_format(self):
        """Detect legacy format with playername key."""
        player = {"playername": "John Doe", "shirtnumber": "5"}
        assert FormatDetector.is_legacy_format(player) is True
    
    def test_detect_modern_format(self):
        """Detect modern format without playername key."""
        player = {"name": "John Doe", "no": "5"}
        assert FormatDetector.is_legacy_format(player) is False


class TestShootingStatsExtractor:
    """Test shooting statistics extraction."""
    
    def test_extract_shooting_stats_modern_format(self):
        """Extract from modern FEB API format."""
        player = {
            "p3m": 2, "p3a": 5,
            "p2m": 8, "p2a": 12,
            "p1m": 3, "p1a": 4
        }
        stats = ShootingStatsExtractor.extract_shooting_stats(player, is_legacy=False)
        
        assert stats["three_made"] == 2
        assert stats["three_att"] == 5
        assert stats["two_made"] == 8
        assert stats["two_att"] == 12
        assert stats["field_goals_made"] == 10  # 2+8
        assert stats["field_goals_att"] == 17   # 5+12
        assert stats["ft_made"] == 3
        assert stats["ft_att"] == 4
    
    def test_extract_shooting_stats_legacy_format(self):
        """Extract from legacy format."""
        player = {
            "three_points_made": 2,
            "three_points_attempted": 5,
            "two_points_made": 8,
            "two_points_attempted": 12,
            "field_goals_made": 10,
            "field_goals_attempted": 17,
            "free_throws_made": 3,
            "free_throws_attempted": 4
        }
        stats = ShootingStatsExtractor.extract_shooting_stats(player, is_legacy=True)
        
        assert stats["three_made"] == 2
        assert stats["field_goals_made"] == 10


class TestShootingPercentageCalculator:
    """Test percentage calculations."""
    
    def test_calculate_percentages_perfect_shooting(self):
        """Calculate with 100% shooting."""
        shooting_stats = {
            "three_made": 5, "three_att": 5,
            "two_made": 10, "two_att": 10,
            "field_goals_made": 15, "field_goals_att": 15,
            "ft_made": 8, "ft_att": 8
        }
        pct = ShootingPercentageCalculator.calculate_percentages(shooting_stats)
        
        assert pct["three_point_pct"] == 100.0
        assert pct["two_point_pct"] == 100.0
        assert pct["field_goal_pct"] == 100.0
        assert pct["free_throw_pct"] == 100.0
    
    def test_calculate_percentages_no_attempts(self):
        """Handle zero attempts."""
        shooting_stats = {
            "three_made": 0, "three_att": 0,
            "two_made": 0, "two_att": 0,
            "field_goals_made": 0, "field_goals_att": 0,
            "ft_made": 0, "ft_att": 0
        }
        pct = ShootingPercentageCalculator.calculate_percentages(shooting_stats)
        
        assert pct["three_point_pct"] == 0.0
        assert pct["two_point_pct"] == 0.0
    
    def test_calculate_percentages_realistic(self):
        """Calculate with realistic values."""
        shooting_stats = {
            "three_made": 2, "three_att": 6,
            "two_made": 5, "two_att": 10,
            "field_goals_made": 7, "field_goals_att": 16,
            "ft_made": 6, "ft_att": 8
        }
        pct = ShootingPercentageCalculator.calculate_percentages(shooting_stats)
        
        assert abs(pct["three_point_pct"] - 33.33) < 0.1
        assert pct["two_point_pct"] == 50.0
        assert abs(pct["field_goal_pct"] - 43.75) < 0.1
        assert pct["free_throw_pct"] == 75.0


class TestAgeDateCalculator:
    """Test age calculation logic."""
    
    def test_parse_game_year_iso_format(self):
        """Parse ISO date format."""
        year = AgeDateCalculator.parse_game_year("2024-10-15T19:00:00")
        assert year == 2024
    
    def test_parse_game_year_feb_format(self):
        """Parse FEB date format."""
        year = AgeDateCalculator.parse_game_year("15-10-2024 - 19:00")
        assert year == 2024
        
        year = AgeDateCalculator.parse_game_year("15-10-2024")
        assert year == 2024
    
    def test_parse_game_year_invalid(self):
        """Handle invalid dates."""
        year = AgeDateCalculator.parse_game_year("invalid")
        assert year is None
        
        year = AgeDateCalculator.parse_game_year(None)
        assert year is None
    
    def test_validate_birth_year_reasonable_age(self):
        """Validate reasonable birth year."""
        player = {}
        birth_year = AgeDateCalculator.validate_birth_year(1998, player, 2024)
        assert birth_year == 1998  # Age 26 is reasonable
    
    def test_validate_birth_year_too_young(self):
        """Reject unreasonably young age."""
        player = {}
        birth_year = AgeDateCalculator.validate_birth_year(2015, player, 2024)
        assert birth_year is None  # Age 9 is too young
    
    def test_validate_birth_year_too_old(self):
        """Reject unreasonably old age."""
        player = {}
        birth_year = AgeDateCalculator.validate_birth_year(1960, player, 2024)
        assert birth_year is None  # Age 64 is too old
    
    def test_calculate_age_with_valid_data(self):
        """Calculate age with valid birth year and game date."""
        player = {"birth_year": 1998}
        birth_year, age = AgeDateCalculator.calculate_age(player, "2024-10-15T19:00:00")
        
        assert birth_year == 1998
        assert age == 26
    
    def test_calculate_age_with_birth_date_fallback(self):
        """Use birth_date as fallback."""
        player = {"birth_year": 2015, "birth_date": "15/03/1998"}
        birth_year, age = AgeDateCalculator.calculate_age(player, "2024-10-15")
        
        assert birth_year == 1998
        assert age == 26
    
    def test_calculate_age_missing_data(self):
        """Handle missing data gracefully."""
        player = {}
        birth_year, age = AgeDateCalculator.calculate_age(player, None)
        
        assert birth_year is None
        assert age is None


class TestGeneralStatsExtractor:
    """Test general statistics extraction."""
    
    def test_extract_general_stats_modern_format(self):
        """Extract from modern format."""
        player = {
            "name": "John Doe",
            "no": "7",
            "inn": "1",
            "pts": 25,
            "ro": 2, "rd": 5, "rt": 7,
            "assist": 8,
            "to": 3,
            "st": 2,
            "bs": 1, "mt": 0,
            "pf": 3, "rf": 4,
            "pllss": 15,
            "val": 28.5
        }
        stats = GeneralStatsExtractor.extract_general_stats(player, is_legacy=False)
        
        assert stats["player_name"] == "John Doe"
        assert stats["dorsal"] == "7"
        assert stats["is_starter"] is True
        assert stats["points"] == 25
        assert stats["assists"] == 8
        assert stats["turnovers"] == 3
    
    def test_extract_general_stats_legacy_format(self):
        """Extract from legacy format."""
        player = {
            "playername": "Jane Smith",
            "shirtnumber": "10",
            "is_starter": True,
            "points": 18,
            "assists": 5,
            "turnovers": 2
        }
        stats = GeneralStatsExtractor.extract_general_stats(player, is_legacy=True)
        
        assert stats["player_name"] == "Jane Smith"
        assert stats["dorsal"] == "10"
        assert stats["is_starter"] is True


class TestStatsTransformer:
    """Test main transformer orchestrator."""
    
    def test_transform_player_stats_complete_modern(self):
        """Transform complete modern format player data."""
        player = {
            "name": "Test Player",
            "no": "23",
            "inn": "1",
            "minFormatted": "30:00",
            "pts": 22,
            "p3m": 3, "p3a": 8,
            "p2m": 7, "p2a": 12,
            "p1m": 2, "p1a": 3,
            "ro": 2, "rd": 6, "rt": 8,
            "assist": 5,
            "to": 2,
            "st": 3,
            "bs": 1, "mt": 0,
            "pf": 2, "rf": 3,
            "pllss": 12,
            "val": 25.0,
            "birth_year": 2000
        }
        
        result = StatsTransformer.transform_player_stats(
            player=player,
            is_home=True,
            team_won=True,
            game_date="2024-10-15T19:00:00"
        )
        
        assert result["name"] == "Test Player"
        assert result["dorsal"] == "23"
        assert result["is_starter"] is True
        assert result["is_home"] is True
        assert result["team_won"] is True
        assert result["minutes_played"] == 30.0
        assert result["points"] == 22
        assert result["three_points_made"] == 3
        assert result["field_goals_made"] == 10  # 3+7
        assert result["assists"] == 5
        assert result["birth_year"] == 2000
        assert result["age_at_game"] == 24
    
    def test_transform_player_stats_with_advanced_calculator(self):
        """Transform with advanced stats calculator."""
        player = {
            "name": "Advanced Player",
            "no": "10",
            "inn": "0",
            "minFormatted": "20:00",
            "pts": 15,
            "p3m": 2, "p3a": 5,
            "p2m": 5, "p2a": 8,
            "p1m": 1, "p1a": 2,
            "ro": 1, "rd": 4, "rt": 5,
            "assist": 3,
            "to": 1,
            "st": 2,
            "bs": 0, "mt": 0,
            "pf": 1, "rf": 2,
            "pllss": 8,
            "val": 18.0
        }
        
        def mock_advanced_calculator(stats):
            return {
                'true_shooting_pct': 55.5,
                'effective_fg_pct': 50.0,
                'player_efficiency_rating': 18.0
            }
        
        result = StatsTransformer.transform_player_stats(
            player=player,
            is_home=False,
            team_won=False,
            game_date="2024-10-15",
            advanced_stats_calculator=mock_advanced_calculator
        )
        
        assert result["true_shooting_pct"] == 55.5
        assert result["effective_fg_pct"] == 50.0
        assert result["player_efficiency_rating"] == 18.0
    
    def test_transform_player_stats_minimal_data(self):
        """Transform with minimal required data."""
        player = {
            "name": "Minimal Player",
            "no": "1",
            "inn": "0"
        }
        
        result = StatsTransformer.transform_player_stats(
            player=player,
            is_home=True,
            team_won=False
        )
        
        assert result["name"] == "Minimal Player"
        assert result["minutes_played"] == 0.0
        assert result["points"] == 0
        assert result["birth_year"] is None
        assert result["age_at_game"] is None
