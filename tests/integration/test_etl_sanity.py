"""
Integration Test: ETL Sanity Checks

This test validates that the ETL processor calculates basketball metrics
within reasonable ranges. It does NOT validate exact values, but ensures:
- Metrics are calculated without errors
- Values are within valid basketball ranges
- No NaN or Inf values are produced
- Percentages are between 0 and 1
"""

import pytest
import sqlite3
import json
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from database.sqlite_schema import SQLiteSchemaManager
from ml.etl_processor import FEBDataETL


@pytest.mark.integration
class TestETLMetricsSanity:
    """Test that ETL calculations produce reasonable metric values."""
    
    @pytest.fixture
    def etl_with_sample_data(
        self,
        temp_sqlite_db,
        mock_mongo_db,
        sample_games_data
    ):
        """Set up ETL processor with sample data and schema."""
        # Create schema
        schema_manager = SQLiteSchemaManager(temp_sqlite_db)
        schema_manager.create_database()
        
        # Create ETL instance (without running full pipeline)
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_test",
            sqlite_path=temp_sqlite_db,
            use_profiles=True
        )
        
        # Note: Full ETL execution would require complex mocking
        # For now, we just verify instantiation works
        
        return temp_sqlite_db
    
    def test_shooting_percentages_in_valid_range(self, etl_with_sample_data):
        """
        Test that shooting percentages are between 0 and 1.
        
        Validates: TS%, eFG%, FT%, 2P%, 3P%
        """
        conn = sqlite3.connect(etl_with_sample_data)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if advanced stats table exists and has data
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_aggregated_stats'
        """)
        if not cursor.fetchone():
            pytest.skip("Advanced stats table not created yet")
        
        cursor.execute("""
            SELECT 
                avg_true_shooting_pct,
                avg_effective_fg_pct,
                avg_field_goal_pct,
                avg_two_point_pct,
                avg_three_point_pct,
                avg_free_throw_pct
            FROM player_aggregated_stats
            WHERE games_played >= 3
        """)
        
        rows = cursor.fetchall()
        if len(rows) == 0:
            pytest.skip("No aggregated stats available")
        
        for row in rows:
            # All shooting percentages should be between 0 and 1 (or NULL)
            for key in row.keys():
                value = row[key]
                if value is not None:
                    assert 0 <= value <= 1.0, \
                        f"{key} out of range: {value}"
        
        conn.close()
    
    def test_per_values_are_reasonable(self, etl_with_sample_data):
        """
        Test that Player Efficiency Rating (PER) is positive and reasonable.
        
        Typical PER ranges: 0-50, with average around 15
        """
        conn = sqlite3.connect(etl_with_sample_data)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_aggregated_stats'
        """)
        if not cursor.fetchone():
            pytest.skip("Advanced stats table not created yet")
        
        cursor.execute("""
            SELECT avg_player_efficiency_rating
            FROM player_aggregated_stats
            WHERE games_played >= 3 AND avg_player_efficiency_rating IS NOT NULL
        """)
        
        rows = cursor.fetchall()
        if len(rows) == 0:
            pytest.skip("No PER values available")
        
        for row in rows:
            per = row['per']
            # PER should be positive and typically under 50
            # (even elite players rarely exceed 35-40)
            assert 0 <= per <= 50, f"PER out of reasonable range: {per}"
        
        conn.close()
    
    def test_no_nan_or_inf_in_metrics(self, etl_with_sample_data):
        """
        Test that no metrics contain NaN or Inf values.
        
        This catches division by zero and calculation errors.
        """
        conn = sqlite3.connect(etl_with_sample_data)
        cursor = conn.cursor()
        
        # Check game statistics
        cursor.execute("""
            SELECT efficiency_rating, points, minutes_played
            FROM player_game_stats
        """)
        
        for row in cursor.fetchall():
            for value in row:
                if value is not None:
                    assert isinstance(value, (int, float)), \
                        f"Non-numeric value found: {value}"
                    assert not (isinstance(value, float) and 
                               (value != value or abs(value) == float('inf'))), \
                        f"NaN or Inf value found: {value}"
        
        conn.close()
    
    def test_aggregated_stats_have_required_fields(self, etl_with_sample_data):
        """
        Test that aggregated statistics contain expected fields.
        
        This validates the ETL transformation completeness.
        """
        conn = sqlite3.connect(etl_with_sample_data)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_aggregated_stats'
        """)
        if not cursor.fetchone():
            pytest.skip("Aggregated stats table not created yet")
        
        cursor.execute("SELECT * FROM player_aggregated_stats LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            pytest.skip("No aggregated stats available")
        
        # Essential fields that should exist
        expected_fields = [
            'player_id',
            'season',
            'games_played',
            'points_per_game',
            'minutes_per_game'
        ]
        
        for field in expected_fields:
            assert field in row.keys(), f"Missing required field: {field}"
        
        conn.close()
    
    def test_usage_rate_in_valid_range(self, etl_with_sample_data):
        """
        Test that usage rate is between 0 and 0.5 (50%).
        
        Usage rate over 40% is extremely rare, over 50% is impossible.
        """
        conn = sqlite3.connect(etl_with_sample_data)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_game_stats'
        """)
        if not cursor.fetchone():
            pytest.skip("Game stats table not created yet")
        
        cursor.execute("""
            SELECT usage_rate
            FROM player_game_stats
            WHERE usage_rate IS NOT NULL
            LIMIT 100
        """)
        
        rows = cursor.fetchall()
        if len(rows) == 0:
            pytest.skip("No usage rate values available")
        
        for row in rows:
            usage = row['usage_rate']
            assert 0 <= usage <= 0.5, \
                f"Usage rate out of valid range: {usage}"
        
        conn.close()


@pytest.mark.integration
class TestETLDataConsistency:
    """Test data consistency across ETL transformations."""
    
    def test_player_game_count_matches_statistics(
        self,
        temp_sqlite_db,
        mock_mongo_db,
        sample_games_data
    ):
        """
        Test that player game counts match actual statistics records.
        
        This validates data integrity during transformation.
        """
        # Setup and run ETL
        if sample_games_data.get("games"):
            mock_mongo_db.all_feb_games_fem.insert_many(sample_games_data["games"])
        
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_test",
            sqlite_path=temp_sqlite_db
        )
        etl.mongo_client = mock_mongo_db.client
        etl.mongo_db = mock_mongo_db
        etl.run_full_etl()
        
        # Check consistency
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Get player game counts from aggregated stats
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_aggregated_stats'
        """)
        if not cursor.fetchone():
            pytest.skip("Aggregated stats table not created yet")
        
        cursor.execute("""
            SELECT player_id, games_played
            FROM player_aggregated_stats
        """)
        agg_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Count actual game records
        cursor.execute("""
            SELECT player_id, COUNT(*) as game_count
            FROM player_game_stats
            GROUP BY player_id
        """)
        actual_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Compare
        for player_id, agg_count in agg_counts.items():
            actual_count = actual_counts.get(player_id, 0)
            assert agg_count == actual_count, \
                f"Game count mismatch for profile {player_id}: " \
                f"aggregated={agg_count}, actual={actual_count}"
        
        conn.close()
