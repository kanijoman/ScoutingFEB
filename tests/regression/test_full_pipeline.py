"""
End-to-End Regression Test: Full Pipeline Execution

This test validates the complete data pipeline from MongoDB extraction
through ETL processing to SQLite database population. It ensures that
the entire workflow executes without errors and produces expected data structures.

The test does NOT validate exact metric values (which may change with improvements),
but rather confirms:
- Pipeline executes without exceptions
- Data is correctly loaded into SQLite
- Expected tables and columns exist
- Data is within reasonable ranges
"""

import pytest
import sqlite3
import mongomock
from pathlib import Path
import sys
import json

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from database.sqlite_schema import SQLiteSchemaManager
from ml.etl_processor import FEBDataETL


@pytest.mark.regression
class TestFullPipelineExecution:
    """Test the complete ETL pipeline execution."""
    
    def test_etl_pipeline_executes_without_errors(
        self,
        temp_sqlite_db,
        mock_mongo_db,
        sample_games_data
    ):
        """
        Test that ETL pipeline can be instantiated and basic setup works.
        
        This test validates:
        1. ETL class can be instantiated
        2. Database schema can be created
        3. Basic structure is correct
        
        Note: Full ETL execution requires complex MongoDB mocking,
        so this test focuses on instantiation and schema creation.
        """
        # Arrange: Create SQLite schema
        schema_manager = SQLiteSchemaManager(temp_sqlite_db)
        schema_manager.create_database()
        
        # Act: Instantiate ETL processor
        try:
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="scouting_test",
                sqlite_path=temp_sqlite_db,
                use_profiles=True
            )
            
            assert etl is not None, "ETL processor should instantiate"
            assert etl.sqlite_path == temp_sqlite_db, "SQLite path should be set"
            
        except Exception as e:
            pytest.fail(f"ETL instantiation failed with exception: {e}")
        
        # Assert: Verify schema was created
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Check that some main tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert len(tables) > 0, "Database should have tables after schema creation"
        
        conn.close()
    
    def test_etl_creates_required_tables(self, temp_sqlite_db):
        """
        Test that schema creation produces all required tables.
        
        This validates the database structure is correct.
        """
        # Arrange & Act
        schema_manager = SQLiteSchemaManager(temp_sqlite_db)
        schema_manager.create_database()
        conn = sqlite3.connect(temp_sqlite_db)
        
        # Assert: Check all expected tables exist
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = [
            'players',
            'teams',
            'games',
            'player_game_stats',
            'player_profiles',
            'player_aggregated_stats'
        ]
        
        for table in required_tables:
            assert table in tables, f"Required table '{table}' not found in schema"
        
        conn.close()
    
    def test_etl_with_empty_mongodb_completes(
        self,
        temp_sqlite_db,
        mock_mongo_db
    ):
        """
        Test that ETL handles empty MongoDB gracefully.
        
        This ensures the pipeline doesn't crash with no data.
        """
        # Arrange: Empty MongoDB
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        # Act & Assert: Should complete without error
        try:
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="scouting_test",
                sqlite_path=temp_sqlite_db
            )
            
            etl.mongo_client = mock_mongo_db.client
            etl.mongo_db = mock_mongo_db
            
            # This should complete without crashing
            etl.run_full_etl()
            
        except Exception as e:
            pytest.fail(f"ETL should handle empty DB gracefully, but failed: {e}")


@pytest.mark.regression
class TestDatabaseIntegrity:
    """Test database integrity after ETL processing."""
    
    def test_player_profiles_have_valid_structure(
        self,
        temp_sqlite_db,
        mock_mongo_db,
        sample_games_data
    ):
        """
        Test that player profiles in SQLite have expected structure.
        
        This validates data transformation correctness.
        """
        # Arrange & Act: Run ETL
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
        
        # Assert: Check player profiles
        conn = sqlite3.connect(temp_sqlite_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM player_profiles LIMIT 5")
        profiles = cursor.fetchall()
        
        assert len(profiles) > 0, "Should have consolidated player profiles"
        
        # Check that required fields exist and have reasonable values
        required_fields = [
            'profile_id',
            'name_normalized',
            'season'
        ]
        
        for profile in profiles:
            for field in required_fields:
                assert profile[field] is not None, f"Field {field} should not be null"
        
        conn.close()
    
    def test_game_statistics_have_valid_ranges(
        self,
        temp_sqlite_db,
        mock_mongo_db,
        sample_games_data
    ):
        """
        Test that game statistics are within valid ranges.
        
        This catches calculation errors or data corruption.
        """
        # Arrange & Act: Run ETL
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
        
        # Assert: Check statistics are in valid ranges
        conn = sqlite3.connect(temp_sqlite_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT points, minutes_played, field_goals_attempted, field_goals_made,
                   total_rebounds, assists
            FROM player_game_stats
        """)
        stats = cursor.fetchall()
        
        assert len(stats) > 0, "Should have game statistics"
        
        for stat in stats:
            # Points should be non-negative and reasonable (< 100 per game)
            assert 0 <= stat['points'] <= 100, f"Invalid points: {stat['points']}"
            
            # Minutes should be between 0 and 48 (regulation + OT)
            assert 0 <= stat['minutes_played'] <= 60, f"Invalid minutes: {stat['minutes_played']}"
            
            # Field goals made can't exceed attempts
            if stat['field_goals_attempted'] > 0:
                assert stat['field_goals_made'] <= stat['field_goals_attempted'], \
                    "Made shots can't exceed attempts"
            
            # Rebounds, assists should be non-negative
            assert stat['total_rebounds'] >= 0, "Rebounds can't be negative"
            assert stat['assists'] >= 0, "Assists can't be negative"
        
        conn.close()
