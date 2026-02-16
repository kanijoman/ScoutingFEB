"""
Error Handling Tests

Tests error handling and recovery across all components.
"""

import pytest
import sqlite3
import mongomock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from database.sqlite_schema import SQLiteSchemaManager
from ml.etl_processor import FEBDataETL
from ml.advanced_stats import (
    calculate_true_shooting_pct,
    calculate_player_efficiency_rating,
    calculate_usage_rate
)
from ml.name_normalizer import NameNormalizer
from ml.player_identity_matcher import PlayerIdentityMatcher


@pytest.mark.e2e
class TestErrorHandling:
    """Test error handling across components."""
    
    def test_etl_handles_missing_mongodb_connection(self, temp_sqlite_db):
        """Test ETL gracefully handles MongoDB connection failures."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        # Try to create ETL with invalid MongoDB URI
        with pytest.raises(Exception):  # Should raise connection error
            etl = FEBDataETL(
                mongodb_uri="mongodb://invalid_host:99999/",
                mongodb_db="nonexistent",
                sqlite_path=temp_sqlite_db
            )
            # Attempting to use it should fail
            etl.run_full_etl()
    
    def test_etl_handles_corrupted_game_data(self, temp_sqlite_db):
        """Test ETL handles malformed game data gracefully."""
        mongo_client = mongomock.MongoClient()
        mongo_db = mongo_client['scouting_test']
        
        # Insert corrupted game data (missing required fields)
        mongo_db['games'].insert_one({
            '_id': 'game_bad',
            'competition_id': 'comp_001',
            # Missing: season, date, teams, scores
            'game_stats': []
        })
        
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_test",
            sqlite_path=temp_sqlite_db
        )
        etl.mongo_client = mongo_client
        etl.mongo_db = mongo_db
        
        # Should complete without crashing (skip bad data or use defaults)
        try:
            etl.run_full_etl()
        except Exception as e:
            # If it raises, should be a specific, handled error
            assert "connection" not in str(e).lower(), \
                "Should not be a connection error"
    
    def test_etl_handles_duplicate_player_names(self, temp_sqlite_db):
        """Test ETL handles duplicate player insertions correctly."""
        mongo_client = mongomock.MongoClient()
        mongo_db = mongo_client['scouting_test']
        
        # Insert teams and competition
        mongo_db['teams'].insert_one({
            '_id': 'team_001',
            'name': 'Test Team',
            'gender': 'F'
        })
        
        mongo_db['competitions'].insert_one({
            '_id': 'comp_001',
            'name': 'Test League',
            'gender': 'F',
            'season': '2023/24'
        })
        
        # Insert same player in two games
        mongo_db['games'].insert_many([
            {
                '_id': 'game_001',
                'competition_id': 'comp_001',
                'season': '2023/24',
                'date': '2023-10-15',
                'home_team_id': 'team_001',
                'away_team_id': 'team_001',
                'home_score': 70,
                'away_score': 65,
                'game_stats': [
                    {
                        'player_name': 'María García',
                        'team_id': 'team_001',
                        'minutes_played': 30,
                        'points': 20,
                        'field_goals_made': 8,
                        'field_goals_attempted': 15,
                        'free_throws_made': 4,
                        'free_throws_attempted': 5,
                        'total_rebounds': 5,
                        'assists': 3,
                        'steals': 2,
                        'turnovers': 2,
                        'efficiency_rating': 18
                    }
                ]
            },
            {
                '_id': 'game_002',
                'competition_id': 'comp_001',
                'season': '2023/24',
                'date': '2023-10-22',
                'home_team_id': 'team_001',
                'away_team_id': 'team_001',
                'home_score': 75,
                'away_score': 70,
                'game_stats': [
                    {
                        'player_name': 'María García',  # Same name
                        'team_id': 'team_001',
                        'minutes_played': 28,
                        'points': 18,
                        'field_goals_made': 7,
                        'field_goals_attempted': 14,
                        'free_throws_made': 4,
                        'free_throws_attempted': 4,
                        'total_rebounds': 6,
                        'assists': 4,
                        'steals': 1,
                        'turnovers': 3,
                        'efficiency_rating': 16
                    }
                ]
            }
        ])
        
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_test",
            sqlite_path=temp_sqlite_db
        )
        etl.mongo_client = mongo_client
        etl.mongo_db = mongo_db
        
        # Should complete without errors
        etl.run_full_etl()
        
        # Verify: Should have ONE player entry
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM players WHERE name_raw = 'María García'")
        player_count = cursor.fetchone()[0]
        
        assert player_count == 1, "Should not create duplicate player entries"
        
        # But TWO game stat entries
        cursor.execute("""
            SELECT COUNT(*) FROM player_game_stats pgs
            JOIN players p ON pgs.player_id = p.player_id
            WHERE p.name_raw = 'María García'
        """)
        stats_count = cursor.fetchone()[0]
        
        assert stats_count == 2, "Should have 2 game stat entries for same player"
        
        conn.close()


@pytest.mark.e2e
class TestAdvancedStatsErrorHandling:
    """Test error handling in advanced stats calculations."""
    
    def test_true_shooting_handles_zero_attempts(self):
        """Test TS% calculation with zero shot attempts."""
        # Edge case: 0 points, 0 attempts
        ts_pct = calculate_true_shooting_pct(
            points=0,
            field_goals_attempted=0,
            free_throws_attempted=0
        )
        assert ts_pct == 0.0, "TS% should be 0 when no attempts"
        
        # Edge case: Points but 0 attempts (defensive stats only)
        ts_pct = calculate_true_shooting_pct(
            points=5,  # Shouldn't happen in real data
            field_goals_attempted=0,
            free_throws_attempted=0
        )
        # Should handle gracefully (return 0 or None)
        assert ts_pct is not None, "Should not crash with invalid data"
    
    def test_per_handles_zero_minutes(self):
        """Test PER calculation with zero minutes played."""
        per = calculate_player_efficiency_rating(
            points=10,
            field_goals_made=4,
            field_goals_attempted=8,
            free_throws_made=2,
            free_throws_attempted=2,
            offensive_rebounds=1,
            defensive_rebounds=3,
            total_rebounds=4,
            assists=2,
            steals=1,
            blocks=0,
            turnovers=1,
            personal_fouls=2,
            minutes_played=0  # Zero minutes
        )
        
        assert per == 0, "PER should be 0 when minutes_played is 0"
    
    def test_per_handles_negative_stats(self):
        """Test PER calculation with negative contributions."""
        # Player with bad efficiency (lots of turnovers, fouls)
        per = calculate_player_efficiency_rating(
            points=2,
            field_goals_made=1,
            field_goals_attempted=10,  # 10% shooting
            free_throws_made=0,
            free_throws_attempted=3,
            offensive_rebounds=0,
            defensive_rebounds=1,
            total_rebounds=1,
            assists=0,
            steals=0,
            blocks=0,
            turnovers=7,  # Many turnovers
            personal_fouls=5,  # Many fouls
            minutes_played=20
        )
        
        # Should handle negative PER gracefully
        assert per is not None, "Should calculate even for bad performance"
        assert per < 5, "PER should be low for poor performance"
    
    def test_usage_rate_handles_missing_team_stats(self):
        """Test usage rate when team stats are unavailable."""
        usage = calculate_usage_rate(
            field_goals_attempted=10,
            free_throws_attempted=5,
            turnovers=2,
            minutes_played=25,
            team_minutes=None,  # Missing team stats
            team_field_goals_attempted=None,
            team_free_throws_attempted=None,
            team_turnovers=None
        )
        
        assert usage is not None, "Should return a value even without team stats"
        # Default implementation might return 0 or estimate
        assert 0 <= usage <= 100, "Usage rate should be in valid range"


@pytest.mark.e2e
class TestNameNormalizerErrorHandling:
    """Test error handling in name normalization."""
    
    def test_normalize_handles_none(self):
        """Test name normalization with None input."""
        normalizer = NameNormalizer()
        result = normalizer.normalize_name(None)
        
        assert result == "", "Should return empty string for None"
    
    def test_normalize_handles_empty_string(self):
        """Test name normalization with empty string."""
        normalizer = NameNormalizer()
        result = normalizer.normalize_name("")
        
        assert result == "", "Should return empty string for empty input"
    
    def test_normalize_handles_special_characters(self):
        """Test name normalization with unusual characters."""
        normalizer = NameNormalizer()
        
        # Unicode characters
        result = normalizer.normalize_name("María José Ñoño Müller")
        assert result is not None, "Should handle unicode characters"
        assert "MARIA" in result, "Should normalize María to MARIA"
        
        # Emojis and symbols
        result = normalizer.normalize_name("Player 😊 #10")
        assert result is not None, "Should handle emojis without crashing"
    
    def test_similarity_handles_empty_names(self):
        """Test name similarity with empty inputs."""
        normalizer = NameNormalizer()
        
        score = normalizer.calculate_name_similarity("", "")
        assert score == 0.0, "Two empty names should have 0 similarity"
        
        score = normalizer.calculate_name_similarity("John Doe", "")
        assert score == 0.0, "Name vs empty should have 0 similarity"
    
    def test_levenshtein_handles_empty_strings(self):
        """Test Levenshtein distance with empty strings."""
        normalizer = NameNormalizer()
        
        distance = normalizer.calculate_levenshtein_distance("", "")
        assert distance == 0, "Empty strings should have 0 distance"
        
        distance = normalizer.calculate_levenshtein_distance("test", "")
        assert distance == 4, "Distance should equal string length"


@pytest.mark.e2e
class TestIdentityMatcherErrorHandling:
    """Test error handling in identity matching."""
    
    @pytest.fixture
    def db_with_minimal_data(self, temp_sqlite_db):
        """Create database with minimal data for testing."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Insert minimal player profile
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender)
            VALUES (1, 'Test Player', 'TEST PLAYER', 'F')
        """)
        
        cursor.execute("""
            INSERT INTO player_profiles 
            (player_id, name_raw, name_normalized, season, is_consolidated)
            VALUES (1, 'Test Player', 'TEST PLAYER', '2023/24', 0)
        """)
        
        conn.commit()
        conn.close()
        
        return temp_sqlite_db
    
    def test_matcher_handles_nonexistent_profile(self, db_with_minimal_data):
        """Test matcher with non-existent profile ID."""
        matcher = PlayerIdentityMatcher(db_with_minimal_data)
        
        # Try to find matches for non-existent profile
        try:
            matches = matcher.find_candidate_matches(profile_id=999, min_score=0.5)
            # Should either return empty list or raise handled error
            assert isinstance(matches, list), "Should return a list"
        except Exception as e:
            # If it raises, should be a specific handled error
            assert "not found" in str(e).lower() or "does not exist" in str(e).lower(), \
                "Should have meaningful error message"
    
    def test_matcher_handles_missing_birth_year(self, db_with_minimal_data):
        """Test matcher when birth year is missing."""
        conn = sqlite3.connect(db_with_minimal_data)
        cursor = conn.cursor()
        
        # Add profile without birth year
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
            VALUES (2, 'Another Player', 'ANOTHER PLAYER', 'F', NULL)
        """)
        
        cursor.execute("""
            INSERT INTO player_profiles 
            (player_id, name_raw, name_normalized, season, birth_year, is_consolidated)
            VALUES (2, 'Another Player', 'ANOTHER PLAYER', '2023/24', NULL, 0)
        """)
        
        conn.commit()
        conn.close()
        
        matcher = PlayerIdentityMatcher(db_with_minimal_data)
        
        # Should handle missing birth year gracefully
        matches = matcher.find_candidate_matches(profile_id=1, min_score=0.3)
        
        assert isinstance(matches, list), "Should return list even with missing data"
    
    def test_calculate_score_handles_incomplete_profiles(self):
        """Test score calculation with incomplete profile data."""
        matcher = PlayerIdentityMatcher(":memory:")
        
        # Profiles with minimal data
        profile1 = {
            'name_raw': 'María García',
            'birth_year': None,  # Missing
            'team_id': None,  # Missing
            'season': '2023/24'
        }
        
        profile2 = {
            'name_raw': 'M. García',
            'birth_year': None,  # Missing
            'team_id': None,  # Missing
            'season': '2023/24'
        }
        
        # Should calculate score based on available data only
        score, components = matcher.calculate_candidate_score(profile1, profile2)
        
        assert 0.0 <= score <= 1.0, "Score should be in valid range"
        assert 'name_match_score' in components, "Should have name component"
        assert components['name_match_score'] > 0, "Names are similar, should have positive score"


@pytest.mark.e2e
class TestDatabaseErrorHandling:
    """Test database-related error handling."""
    
    def test_schema_creation_idempotent(self, temp_sqlite_db):
        """Test that creating schema multiple times doesn't cause errors."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        
        # Create schema first time
        schema_mgr.create_database()
        
        # Create schema second time - should not crash
        try:
            schema_mgr.create_database()
        except Exception as e:
            pytest.fail(f"Schema creation should be idempotent, but failed: {e}")
    
    def test_handles_database_locked(self, temp_sqlite_db):
        """Test handling of database lock situations."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        # Open connection and start transaction
        conn1 = sqlite3.connect(temp_sqlite_db)
        cursor1 = conn1.cursor()
        cursor1.execute("BEGIN EXCLUSIVE")
        
        # Try to access from another connection
        conn2 = sqlite3.connect(temp_sqlite_db, timeout=1.0)
        cursor2 = conn2.cursor()
        
        try:
            # This should timeout or wait
            cursor2.execute("INSERT INTO players (player_id, name_raw, name_normalized, gender) VALUES (999, 'Test', 'TEST', 'F')")
            conn2.commit()
        except sqlite3.OperationalError as e:
            # Expected: database is locked
            assert "locked" in str(e).lower() or "busy" in str(e).lower()
        finally:
            conn1.rollback()
            conn1.close()
            conn2.close()
    
    def test_handles_constraint_violations(self, temp_sqlite_db):
        """Test handling of database constraint violations."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Insert player
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender)
            VALUES (1, 'Test Player', 'TEST PLAYER', 'F')
        """)
        conn.commit()
        
        # Try to insert same player_id again (primary key violation)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO players (player_id, name_raw, name_normalized, gender)
                VALUES (1, 'Another Player', 'ANOTHER PLAYER', 'F')
            """)
        
        conn.close()
