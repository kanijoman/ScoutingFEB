"""
Unit Tests: ETL Aggregation and Load Operations

Tests the ETL processor's aggregation calculation and database insertion:
- Player aggregates calculation
- Column count matching with database schema
- calculate_average_age() with sqlite3.Row objects
- INSERT query parameter count validation
"""

import pytest
import sqlite3
import numpy as np
from pathlib import Path
import sys
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ml.player_aggregator import StatsAggregator, AggregationQueryBuilder


@pytest.mark.unit
class TestStatsAggregatorAverageAge:
    """Test average age calculation with different input types."""
    
    def test_calculate_average_age_with_dict_list(self):
        """Test calculate_average_age with list of dictionaries."""
        stats = [
            {"age": 25.5},
            {"age": 26.0},
            {"age": 24.8}
        ]
        
        avg_age = StatsAggregator.calculate_average_age(stats)
        
        assert avg_age is not None, "Should return average age"
        assert abs(avg_age - 25.433) < 0.01, "Average should be ~25.43"
    
    def test_calculate_average_age_with_sqlite_row_objects(self):
        """Test calculate_average_age with sqlite3.Row objects (regression test)."""
        # Create in-memory database with age column
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("CREATE TABLE test_stats (age REAL, points REAL)")
        cursor.execute("INSERT INTO test_stats VALUES (25.5, 10)")
        cursor.execute("INSERT INTO test_stats VALUES (26.0, 12)")
        cursor.execute("INSERT INTO test_stats VALUES (24.8, 11)")
        
        cursor.execute("SELECT * FROM test_stats")
        stats = cursor.fetchall()
        
        # Verify they are Row objects
        assert isinstance(stats[0], sqlite3.Row), "Should be sqlite3.Row objects"
        
        # Should handle Row objects without .get() method
        avg_age = StatsAggregator.calculate_average_age(stats)
        
        assert avg_age is not None, "Should return average age from Row objects"
        assert abs(avg_age - 25.433) < 0.01, "Average should be ~25.43"
        
        conn.close()
    
    def test_calculate_average_age_with_missing_ages(self):
        """Test calculate_average_age with some missing age values."""
        stats = [
            {"age": 25.5},
            {"age": None},
            {"points": 10},  # No age key
            {"age": 26.0}
        ]
        
        avg_age = StatsAggregator.calculate_average_age(stats)
        
        assert avg_age is not None, "Should calculate from available ages"
        assert abs(avg_age - 25.75) < 0.01, "Should average only non-None values"
    
    def test_calculate_average_age_with_all_missing(self):
        """Test calculate_average_age when all ages are missing."""
        stats = [
            {"points": 10},
            {"points": 12},
            {"age": None}
        ]
        
        avg_age = StatsAggregator.calculate_average_age(stats)
        
        assert avg_age is None, "Should return None when no valid ages"
    
    def test_calculate_average_age_with_empty_list(self):
        """Test calculate_average_age with empty stats list."""
        stats = []
        
        avg_age = StatsAggregator.calculate_average_age(stats)
        
        assert avg_age is None, "Should return None for empty list"


@pytest.mark.unit
class TestAggregationQueryBuilder:
    """Test SQL query builders for aggregation."""
    
    def test_insert_aggregates_query_structure(self):
        """Test that INSERT query has correct structure."""
        query = AggregationQueryBuilder.get_insert_aggregates_query()
        
        assert "INSERT OR REPLACE INTO player_aggregated_stats" in query
        assert "VALUES" in query
        
        # Extract column names and placeholders
        columns_part = query.split("(")[1].split(")")[0]
        values_part = query.split("VALUES")[1].strip()
        
        # Count columns
        columns = [c.strip() for c in columns_part.split(",")]
        
        # Count placeholders
        placeholders = values_part.count("?")
        
        assert len(columns) > 0, "Should have column names"
        assert placeholders > 0, "Should have placeholders"
        assert len(columns) == placeholders, \
            f"Column count ({len(columns)}) must match placeholder count ({placeholders})"
    
    def test_insert_query_matches_database_schema(self):
        """Test that INSERT query columns match database schema."""
        # Create in-memory database with actual schema
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        # Create player_aggregated_stats table (simplified version with key columns)
        cursor.execute("""
            CREATE TABLE player_aggregated_stats (
                agg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                season TEXT NOT NULL,
                competition_id INTEGER,
                games_played INTEGER,
                date_from TEXT,
                date_to TEXT,
                avg_age REAL,
                avg_minutes REAL,
                avg_points REAL,
                avg_field_goal_pct REAL,
                avg_three_point_pct REAL,
                avg_free_throw_pct REAL,
                avg_total_rebounds REAL,
                avg_assists REAL,
                avg_efficiency REAL,
                total_points INTEGER,
                total_rebounds INTEGER,
                total_assists INTEGER,
                std_points REAL,
                std_efficiency REAL,
                trend_points REAL,
                trend_efficiency REAL,
                avg_true_shooting_pct REAL,
                avg_effective_fg_pct REAL,
                avg_offensive_rating REAL,
                avg_player_efficiency_rating REAL,
                avg_turnover_pct REAL,
                avg_offensive_rebound_pct REAL,
                avg_defensive_rebound_pct REAL,
                avg_win_shares_per_36 REAL,
                win_percentage REAL
            )
        """)
        
        # Get column count (excluding AUTOINCREMENT)
        cursor.execute("PRAGMA table_info(player_aggregated_stats)")
        table_columns = cursor.fetchall()
        non_auto_columns = [col for col in table_columns if col[1] != 'agg_id']
        
        # Get INSERT query
        query = AggregationQueryBuilder.get_insert_aggregates_query()
        
        # Count placeholders in query
        values_part = query.split("VALUES")[1].strip()
        placeholder_count = values_part.count("?")
        
        # Should match (this specific test uses simplified schema)
        # In real schema there are more columns, but INSERT should only insert core columns
        assert placeholder_count == len(non_auto_columns), \
            f"Placeholder count ({placeholder_count}) should match insertable columns ({len(non_auto_columns)})"
        
        # Try to execute with correct number of parameters
        try:
            test_values = tuple([1] * placeholder_count)
            cursor.execute(query, test_values)
            conn.commit()
            success = True
        except sqlite3.OperationalError as e:
            success = False
            error_msg = str(e)
        
        assert success, f"INSERT should execute without column count mismatch"
        
        conn.close()
    
    def test_insert_query_includes_avg_age_column(self):
        """Test that INSERT query includes avg_age column (regression test)."""
        query = AggregationQueryBuilder.get_insert_aggregates_query()
        
        # Should include avg_age in column list
        columns_part = query.split("(")[1].split(")")[0].lower()
        
        assert "avg_age" in columns_part, \
            "INSERT query must include avg_age column (was causing 29/30 column mismatch)"


@pytest.mark.unit  
class TestETLAggregationIntegration:
    """Integration tests for aggregation calculation."""
    
    def test_aggregate_calculation_with_real_data(self):
        """Test that aggregation calculation produces valid output."""
        # Create mock stats data
        stats_data = [
            {
                "game_date": "2024-01-01",
                "age": 25.0,
                "minutes": 30.0,
                "points": 15.0,
                "field_goal_pct": 0.45,
                "three_point_pct": 0.35,
                "free_throw_pct": 0.80,
                "total_rebounds": 8.0,
                "assists": 4.0,
                "efficiency": 18.0,
                "team_won": 1,
                "true_shooting_pct": 0.55,
                "effective_fg_pct": 0.50,
                "offensive_rating": 110.0,
                "player_efficiency_rating": 20.0,
                "turnover_pct": 0.12,
                "offensive_rebound_pct": 0.08,
                "defensive_rebound_pct": 0.15,
                "win_shares_per_36": 0.15
            },
            {
                "game_date": "2024-01-05",
                "age": 25.1,
                "minutes": 32.0,
                "points": 18.0,
                "field_goal_pct": 0.50,
                "three_point_pct": 0.40,
                "free_throw_pct": 0.85,
                "total_rebounds": 10.0,
                "assists": 5.0,
                "efficiency": 22.0,
                "team_won": 1,
                "true_shooting_pct": 0.60,
                "effective_fg_pct": 0.55,
                "offensive_rating": 115.0,
                "player_efficiency_rating": 23.0,
                "turnover_pct": 0.10,
                "offensive_rebound_pct": 0.10,
                "defensive_rebound_pct": 0.18,
                "win_shares_per_36": 0.18
            }
        ]
        
        # Convert to numpy arrays (as StatsExtractor would do)
        basic_stats = {
            'minutes': np.array([s['minutes'] for s in stats_data]),
            'points': np.array([s['points'] for s in stats_data]),
            'rebounds': np.array([s['total_rebounds'] for s in stats_data]),
            'assists': np.array([s['assists'] for s in stats_data]),
            'efficiency': np.array([s['efficiency'] for s in stats_data]),
            'fg_pct': np.array([s['field_goal_pct'] for s in stats_data]),
            'three_pct': np.array([s['three_point_pct'] for s in stats_data]),
            'ft_pct': np.array([s['free_throw_pct'] for s in stats_data]),
            'wins': np.array([s['team_won'] for s in stats_data])
        }
        
        # Test basic averages
        basic_avgs = StatsAggregator.calculate_basic_averages(basic_stats)
        
        assert 'avg_points' in basic_avgs
        assert basic_avgs['avg_points'] == 16.5, "Should average 15 and 18"
        assert basic_avgs['avg_minutes'] == 31.0, "Should average 30 and 32"
        
        # Test standard deviations
        std_devs = StatsAggregator.calculate_std_deviations(basic_stats)
        
        assert 'std_points' in std_devs
        assert std_devs['std_points'] > 0, "Should have non-zero std deviation"
        
        # Test trends
        trends = StatsAggregator.calculate_trends(basic_stats, games_played=2, min_games=2)
        
        assert 'trend_points' in trends
        # Points went from 15 to 18, so trend should be positive (with min_games=2)
        assert trends['trend_points'] > 0, "Points increased, trend should be positive"
        
        # Test win percentage
        win_pct = StatsAggregator.calculate_win_percentage(basic_stats)
        
        assert win_pct == 100.0, "Both games won, should be 100%"
        
        # Test date range
        date_from, date_to = StatsAggregator.extract_date_range(stats_data)
        
        assert date_from == "2024-01-01"
        assert date_to == "2024-01-05"
        
        # Test average age
        avg_age = StatsAggregator.calculate_average_age(stats_data)
        
        assert avg_age is not None
        assert abs(avg_age - 25.05) < 0.01, "Should average 25.0 and 25.1"


@pytest.mark.unit
class TestETLColumnMismatchPrevention:
    """Tests to prevent column count mismatches (regression tests for prod bugs)."""
    
    def test_insert_query_parameter_count_documented(self):
        """Document expected parameter count for INSERT query."""
        query = AggregationQueryBuilder.get_insert_aggregates_query()
        
        values_part = query.split("VALUES")[1].strip()
        placeholder_count = values_part.count("?")
        
        # Document the expected count (update this when schema changes)
        EXPECTED_PARAM_COUNT = 31  # Based on current implementation
        
        assert placeholder_count == EXPECTED_PARAM_COUNT, \
            f"INSERT query should have {EXPECTED_PARAM_COUNT} placeholders. " \
            f"Found {placeholder_count}. If this is intentional, update EXPECTED_PARAM_COUNT."
    
    def test_required_columns_present_in_insert(self):
        """Test that all required columns are in INSERT statement."""
        query = AggregationQueryBuilder.get_insert_aggregates_query()
        query_lower = query.lower()
        
        required_columns = [
            'player_id',
            'season',
            'competition_id',
            'games_played',
            'date_from',
            'date_to',
            'avg_age',  # Was missing, caused bug
            'avg_minutes',
            'avg_points',
            'win_percentage'
        ]
        
        for column in required_columns:
            assert column in query_lower, \
                f"Required column '{column}' missing from INSERT query"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
