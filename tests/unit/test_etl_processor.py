"""
Unit Tests: ETL Processor Core Functionality

Tests the ETL processor's core methods including:
- Initialization and database connections
- Incremental mode with get_processed_game_ids
- Type conversion between MongoDB (strings) and SQLite (integers)
- Game extraction with exclusion lists
"""

import pytest
import sqlite3
from pathlib import Path
import sys
from unittest.mock import Mock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ml.etl_processor import FEBDataETL


@pytest.mark.unit
class TestETLProcessorInitialization:
    """Test ETL processor initialization and database connections."""
    
    def test_initialization_creates_mongo_db_attribute(self):
        """Test that ETL processor has mongo_db attribute after initialization."""
        with patch('ml.etl_processor.MongoDBClient') as mock_mongo_client:
            # Setup mock
            mock_client_instance = Mock()
            mock_db = Mock()
            mock_client_instance.db = mock_db
            mock_mongo_client.return_value = mock_client_instance
            
            # Create ETL instance
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="test_db",
                sqlite_path=":memory:",
                use_profiles=True
            )
            
            # Verify mongo_db attribute exists and equals client.db
            assert hasattr(etl, 'mongo_db'), "ETL must have mongo_db attribute"
            assert etl.mongo_db == mock_db, "mongo_db should reference client.db"
    
    def test_mongo_client_has_db_attribute(self):
        """Test that mongo_client.db exists (regression test for attribute error)."""
        with patch('ml.etl_processor.MongoDBClient') as mock_mongo_client:
            mock_client_instance = Mock()
            mock_client_instance.db = Mock()
            mock_mongo_client.return_value = mock_client_instance
            
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="test_db",
                sqlite_path=":memory:",
                use_profiles=True
            )
            
            # Should not raise AttributeError
            assert etl.mongo_client.db is not None


@pytest.mark.unit
class TestETLIncrementalMode:
    """Test ETL incremental mode functionality."""
    
    @pytest.fixture
    def mock_etl(self):
        """Create ETL instance with mocked dependencies."""
        with patch('ml.etl_processor.MongoDBClient') as mock_mongo:
            mock_client = Mock()
            mock_client.db = Mock()
            mock_mongo.return_value = mock_client
            
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="test_db",
                sqlite_path=":memory:",
                use_profiles=True
            )
            
            yield etl
    
    def test_get_processed_game_ids_returns_list_of_integers(self, mock_etl):
        """Test that get_processed_game_ids returns list of integers."""
        # Create in-memory SQLite database with test data
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        # Create games table with integer game_id
        cursor.execute("""
            CREATE TABLE games (
                game_id INTEGER PRIMARY KEY,
                competition TEXT,
                season TEXT
            )
        """)
        
        # Insert test data
        test_game_ids = [2479443, 2479444, 2479445, 1234567]
        for game_id in test_game_ids:
            cursor.execute(
                "INSERT INTO games (game_id, competition, season) VALUES (?, ?, ?)",
                (game_id, "LF ENDESA", "2024-2025")
            )
        conn.commit()
        
        # Call method with connection
        result = mock_etl.get_processed_game_ids(conn)
        
        # Verify results
        assert isinstance(result, set), "Should return a set"
        assert len(result) == 4, "Should return all 4 game IDs"
        assert all(isinstance(gid, int) for gid in result), "All IDs should be integers"
        assert result == set(test_game_ids), "Should return exact game IDs"
        
        conn.close()
    
    def test_get_processed_game_ids_handles_empty_table(self, mock_etl):
        """Test that get_processed_game_ids handles empty games table."""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE games (
                game_id INTEGER PRIMARY KEY,
                competition TEXT
            )
        """)
        conn.commit()
        
        result = mock_etl.get_processed_game_ids(conn)
        
        assert isinstance(result, set), "Should return a set"
        assert len(result) == 0, "Should return empty set for empty table"
        
        conn.close()
    
    def test_get_processed_game_ids_handles_missing_table(self, mock_etl):
        """Test that get_processed_game_ids handles missing games table gracefully."""
        conn = sqlite3.connect(":memory:")
        
        # Should handle gracefully (return empty set or raise clear error)
        try:
            result = mock_etl.get_processed_game_ids(conn)
            # If no exception, should return empty set
            assert result == set(), "Should return empty set if table doesn't exist"
        except Exception as e:
            # If exception raised, should be clear and informative
            assert "games" in str(e).lower(), f"Error should mention 'games' table: {e}"
        
        conn.close()


@pytest.mark.unit
class TestETLTypeConversion:
    """Test type conversion between MongoDB strings and SQLite integers."""
    
    @pytest.fixture
    def mock_etl_with_mongo(self):
        """Create ETL with mocked MongoDB connection."""
        with patch('ml.etl_processor.MongoDBClient') as mock_mongo:
            mock_client = Mock()
            mock_db = Mock()
            mock_collection = Mock()
            
            mock_client.db = mock_db
            mock_db.__getitem__ = Mock(return_value=mock_collection)
            mock_mongo.return_value = mock_client
            
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="test_db",
                sqlite_path=":memory:",
                use_profiles=True
            )
            
            # Store mock collection for testing
            etl._test_collection = mock_collection
            
            yield etl
    
    def test_extract_games_converts_integer_ids_to_strings(self, mock_etl_with_mongo):
        """Test that extract_games_from_mongodb filters games in Python with string conversion."""
        # Setup: game_ids as integers (from SQLite)
        exclude_game_ids = {2479443, 2479444, 2479445}
        
        # Mock MongoDB collection to return mixed games
        mock_collection = mock_etl_with_mongo._test_collection
        mock_games = [
            {"HEADER": {"game_code": "2479443"}},  # Should be excluded
            {"HEADER": {"game_code": "2479444"}},  # Should be excluded
            {"HEADER": {"game_code": "2479999"}},  # Should be kept (new)
            {"HEADER": {"game_code": "2480000"}},  # Should be kept (new)
        ]
        mock_collection.find.return_value = mock_games
        
        # Replace mongo_db collection access
        mock_etl_with_mongo.mongo_db = {'all_feb_games_fem': mock_collection}
        
        # Call extract method with integer IDs
        result = mock_etl_with_mongo.extract_games_from_mongodb(
            collection_name='all_feb_games_fem',
            exclude_game_ids=exclude_game_ids
        )
        
        # Verify find was called WITHOUT $nin query (extracts all, filters in Python)
        assert mock_collection.find.called, "MongoDB find should be called"
        call_args = mock_collection.find.call_args
        query = call_args[0][0] if call_args[0] else {}
        assert query == {}, "Query should be empty (no $nin), filtering done in Python"
        
        # Verify filtering worked correctly
        assert len(result) == 2, "Should return only 2 new games (filtered in Python)"
        returned_codes = {g["HEADER"]["game_code"] for g in result}
        assert returned_codes == {"2479999", "2480000"}, "Should return only non-excluded games"
    
    def test_type_mismatch_between_mongodb_and_sqlite(self):
        """Test that documents the type mismatch issue between databases."""
        # This test documents the issue:
        # - SQLite stores game_id as INTEGER
        # - MongoDB stores game_code as STRING
        # - Direct comparison fails: 2479443 != '2479443'
        
        # Simulate SQLite integer
        sqlite_game_id = 2479443
        assert isinstance(sqlite_game_id, int), "SQLite stores as integer"
        
        # Simulate MongoDB string
        mongo_game_code = '2479443'
        assert isinstance(mongo_game_code, str), "MongoDB stores as string"
        
        # Direct comparison fails
        assert sqlite_game_id != mongo_game_code, "Integer != String (type mismatch)"
        
        # Set membership fails
        sqlite_ids = {2479443, 2479444, 2479445}
        assert mongo_game_code not in sqlite_ids, "String not found in integer set"
        
        # Solution: convert to strings
        sqlite_ids_str = {str(gid) for gid in sqlite_ids}
        assert mongo_game_code in sqlite_ids_str, "String found in string set (correct)"
    
    def test_incremental_mode_with_type_conversion(self, mock_etl_with_mongo):
        """Integration test: incremental mode must convert types correctly and filter in Python."""
        # Create SQLite table with integer IDs
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE games (
                game_id INTEGER PRIMARY KEY,
                competition TEXT
            )
        """)
        
        # Insert games with INTEGER IDs
        existing_ids = [2479443, 2479444, 2479445]
        for gid in existing_ids:
            cursor.execute(
                "INSERT INTO games (game_id, competition) VALUES (?, ?)",
                (gid, "LF ENDESA")
            )
        conn.commit()
        
        # Mock MongoDB to return string game_codes
        mock_collection = Mock()
        mock_games = [
            {"HEADER": {"game_code": "2479443"}},  # Existing (as string)
            {"HEADER": {"game_code": "2479444"}},  # Existing (as string)  
            {"HEADER": {"game_code": "2479999"}},  # New game (as string)
        ]
        mock_collection.find.return_value = mock_games
        mock_etl_with_mongo.mongo_db = {'all_feb_games_fem': mock_collection}
        
        # Get processed IDs (integers from SQLite)
        processed_ids = mock_etl_with_mongo.get_processed_game_ids(conn)
        assert all(isinstance(gid, int) for gid in processed_ids), "SQLite returns integers"
        
        # Call extract with exclusion (should filter in Python after converting to strings)
        result = mock_etl_with_mongo.extract_games_from_mongodb(
            collection_name='all_feb_games_fem',
            exclude_game_ids=processed_ids
        )
        
        # Verify query does NOT use $nin (filters in Python instead)
        call_args = mock_collection.find.call_args
        query = call_args[0][0] if call_args[0] else {}
        assert query == {}, "Query should be empty, filtering done in Python"
        
        # Verify filtering worked (only new game returned)
        assert len(result) == 1, "Incremental mode should return only 1 new game"
        assert result[0]["HEADER"]["game_code"] == "2479999", "Should return the new game"
        
        conn.close()


@pytest.mark.unit
class TestETLExtractionWithExclusion:
    """Test game extraction with exclusion lists."""
    
    def test_extract_without_exclusion_list(self):
        """Test that extract works when no exclusion list is provided."""
        with patch('ml.etl_processor.MongoDBClient') as mock_mongo:
            mock_client = Mock()
            mock_db = Mock()
            mock_collection = Mock()
            
            mock_client.db = mock_db
            mock_db.__getitem__ = Mock(return_value=mock_collection)
            mock_mongo.return_value = mock_client
            
            # Return empty list from MongoDB
            mock_collection.find.return_value = []
            
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="test_db",
                sqlite_path=":memory:",
                use_profiles=True
            )
            
            # Call without exclusion
            etl.extract_games_from_mongodb(
                collection_name='all_feb_games_fem',
                exclude_game_ids=None
            )
            
            # Verify find was called
            assert mock_collection.find.called
            
            # Verify query is empty (no filtering)
            call_args = mock_collection.find.call_args
            query = call_args[0][0] if call_args[0] else {}
            
            # Should have empty query when no exclusion
            assert query == {}, "Query should be empty when no exclusion list provided"
    
    def test_extract_with_empty_exclusion_list(self):
        """Test that extract handles empty exclusion list correctly."""
        with patch('ml.etl_processor.MongoDBClient') as mock_mongo:
            mock_client = Mock()
            mock_db = Mock()
            mock_collection = Mock()
            
            mock_client.db = mock_db
            mock_db.__getitem__ = Mock(return_value=mock_collection)
            mock_mongo.return_value = mock_client
            
            mock_collection.find.return_value = []
            
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="test_db",
                sqlite_path=":memory:",
                use_profiles=True
            )
            
            # Call with empty list
            etl.extract_games_from_mongodb(
                collection_name='all_feb_games_fem',
                exclude_game_ids=[]
            )
            
            # Should work without errors
            assert mock_collection.find.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
