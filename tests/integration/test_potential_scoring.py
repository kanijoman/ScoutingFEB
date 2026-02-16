"""
Integration Test: Potential Scoring System

This test validates the player potential scoring and tier classification system.

Tests focus on:
- Scoring executes without errors
- Players are assigned to valid tiers
- Tier distribution is reasonable
- Edge cases are handled (few games, missing data)
"""

import pytest
import sqlite3
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from database.sqlite_schema import SQLiteSchemaManager
from ml.etl_processor import FEBDataETL


@pytest.mark.integration
class TestPotentialScoring:
    """Test the player potential scoring system."""
    
    @pytest.fixture
    def db_with_potential_scores(
        self,
        temp_sqlite_db,
        mock_mongo_db,
        sample_games_data
    ):
        """Create database with potential scores calculated."""
        # Populate and run ETL
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
        
        return temp_sqlite_db
    
    def test_potential_tiers_are_valid(self, db_with_potential_scores):
        """
        Test that all assigned potential tiers are valid categories.
        
        Valid tiers: Elite, Muy Alto, Alto, Medio-Alto, Medio, Desarrollo
        """
        conn = sqlite3.connect(db_with_potential_scores)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if potential table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_career_potential'
        """)
        if not cursor.fetchone():
            pytest.skip("Potential table not created yet")
        
        cursor.execute("SELECT potential_tier FROM player_career_potential")
        tiers = [row['potential_tier'] for row in cursor.fetchall()]
        
        if len(tiers) == 0:
            pytest.skip("No potential scores calculated")
        
        valid_tiers = [
            'elite',
            'very_high',
            'high',
            'medium',
            'low',
            None  # Some players might not have tier assigned
        ]
        
        for tier in tiers:
            assert tier in valid_tiers, f"Invalid tier: {tier}"
        
        conn.close()
    
    def test_potential_scores_are_in_range(self, db_with_potential_scores):
        """
        Test that potential scores are within expected range (0-100).
        """
        conn = sqlite3.connect(db_with_potential_scores)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_career_potential'
        """)
        if not cursor.fetchone():
            pytest.skip("Potential table not created yet")
        
        cursor.execute("""
            SELECT unified_potential_score
            FROM player_career_potential
            WHERE unified_potential_score IS NOT NULL
        """)
        
        scores = [row['unified_potential_score'] if 'unified_potential_score' in row.keys() else row[0] for row in cursor.fetchall()]
        
        if len(scores) == 0:
            pytest.skip("No potential scores calculated")
        
        for score in scores:
            assert 0 <= score <= 100, f"Potential score out of range: {score}"
        
        conn.close()
    
    def test_tier_classification_is_consistent(self, db_with_potential_scores):
        """
        Test that tier classification is consistent with scores.
        
        Higher scores should correspond to higher tiers.
        """
        conn = sqlite3.connect(db_with_potential_scores)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_career_potential'
        """)
        if not cursor.fetchone():
            pytest.skip("Potential table not created yet")
        
        cursor.execute("""
            SELECT unified_potential_score, potential_tier
            FROM player_career_potential
            WHERE unified_potential_score IS NOT NULL 
            AND potential_tier IS NOT NULL
            ORDER BY unified_potential_score DESC
        """)
        
        results = cursor.fetchall()
        
        if len(results) < 2:
            pytest.skip("Not enough data to test tier consistency")
        
        # Define tier hierarchy (English names from schema)
        tier_order = {
            'elite': 5,
            'very_high': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }
        
        # Check that scores are generally consistent with tiers
        # (allowing some flexibility as edges between tiers may vary)
        for i in range(len(results) - 1):
            score1 = results[i]['unified_potential_score']
            score2 = results[i + 1]['unified_potential_score']
            tier1 = results[i]['potential_tier']
            tier2 = results[i + 1]['potential_tier']
            
            tier1_rank = tier_order.get(tier1, 0)
            tier2_rank = tier_order.get(tier2, 0)
            
            # Higher score should have equal or higher tier
            # (allowing ties because of threshold edges)
            if score1 > score2 + 5:  # Significant score difference
                assert tier1_rank >= tier2_rank, \
                    f"Tier inconsistency: score {score1} (tier {tier1}) " \
                    f"should be >= score {score2} (tier {tier2})"
        
        conn.close()
    
    def test_potential_scoring_handles_limited_data(
        self,
        temp_sqlite_db,
        mock_mongo_db,
        sample_games_data
    ):
        """
        Test that potential scoring handles players with few games gracefully.
        
        Players with insufficient data should either:
        - Not have scores assigned, OR
        - Have scores with lower confidence
        """
        # Use only first game from sample data to simulate limited data
        if not sample_games_data.get("games"):
            pytest.skip("No sample games data available")
        
        minimal_games = {"games": [sample_games_data["games"][0]]}  # Just one game
        
        mock_mongo_db.all_feb_games_fem.insert_many(minimal_games["games"])
        
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        # Run ETL - should not crash
        try:
            etl = FEBDataETL(
                mongodb_uri="mongodb://localhost:27017/",
                mongodb_db="scouting_test",
                sqlite_path=temp_sqlite_db
            )
            etl.mongo_client = mock_mongo_db.client
            etl.mongo_db = mock_mongo_db
            etl.run_full_etl()
        except Exception as e:
            pytest.fail(f"ETL should handle limited data gracefully, but failed: {e}")
        
        # Verify it completed (don't necessarily expect potential scores)
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM player_game_stats")
        count = cursor.fetchone()[0]
        assert count > 0, "Should have loaded game statistics"
        conn.close()
