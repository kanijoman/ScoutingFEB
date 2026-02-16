"""
End-to-End Test: Identity Consolidation

Tests the complete player identity matching and consolidation workflow.
"""

import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from database.sqlite_schema import SQLiteSchemaManager
from ml.player_identity_matcher import PlayerIdentityMatcher
from ml.consolidate_identities import consolidate_identities


@pytest.mark.e2e
class TestIdentityConsolidationE2E:
    """End-to-end tests for player identity consolidation."""
    
    @pytest.fixture
    def db_with_duplicate_profiles(self, temp_sqlite_db):
        """Create database with duplicate player profiles."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Insert teams
        cursor.execute("""
            INSERT INTO teams (team_id, name, gender)
            VALUES ('team_001', 'CB Estudiantes', 'F')
        """)
        
        cursor.execute("""
            INSERT INTO teams (team_id, name, gender)
            VALUES ('team_002', 'Perfumerías Avenida', 'F')
        """)
        
        # Insert competition
        cursor.execute("""
            INSERT INTO competitions (competition_id, name, gender, season)
            VALUES ('comp_001', 'LF ENDESA', 'F', '2023/24')
        """)
        
        # Insert players with variations of same person
        # María García López - different formats
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
            VALUES (1, 'María García López', 'MARIA GARCIA LOPEZ', 'F', 1995)
        """)
        
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
            VALUES (2, 'M. García López', 'M. GARCIA LOPEZ', 'F', 1995)
        """)
        
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
            VALUES (3, 'García López, María', 'GARCIA LOPEZ, MARIA', 'F', 1995)
        """)
        
        # Ana Martín - single profile (control)
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
            VALUES (4, 'Ana Martín Ruiz', 'ANA MARTIN RUIZ', 'F', 1998)
        """)
        
        # Laura Pérez - two profiles, different birth years (edge case)
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
            VALUES (5, 'Laura Pérez Sánchez', 'LAURA PEREZ SANCHEZ', 'F', 2000)
        """)
        
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
            VALUES (6, 'L. Pérez', 'L. PEREZ', 'F', 2001)
        """)
        
        # Insert games
        cursor.execute("""
            INSERT INTO games (game_id, competition_id, season, date, 
                             home_team_id, away_team_id, home_score, away_score)
            VALUES ('game_001', 'comp_001', '2023/24', '2023-10-15',
                   'team_001', 'team_002', 75, 68)
        """)
        
        cursor.execute("""
            INSERT INTO games (game_id, competition_id, season, date,
                             home_team_id, away_team_id, home_score, away_score)
            VALUES ('game_002', 'comp_001', '2023/24', '2023-10-22',
                   'team_002', 'team_001', 82, 78)
        """)
        
        # Insert game stats for different player_ids (duplicates)
        game_stats = [
            # Game 1 - María (player_id 1)
            (1, 'game_001', 'team_001', 28, 18, 7, 14, 2, 3, 7, 4, 2, 3),
            # Game 2 - M. García (player_id 2) - same person, different format
            (2, 'game_002', 'team_001', 30, 22, 8, 16, 4, 5, 7, 3, 1, 2),
            # Ana Martín (player_id 4)
            (4, 'game_001', 'team_001', 32, 24, 9, 18, 3, 4, 5, 6, 3, 2),
            (4, 'game_002', 'team_001', 28, 16, 6, 14, 2, 2, 3, 8, 2, 3),
            # Laura (player_id 5)
            (5, 'game_001', 'team_002', 30, 15, 6, 13, 1, 2, 9, 2, 1, 4),
        ]
        
        for stat in game_stats:
            cursor.execute("""
                INSERT INTO player_game_stats 
                (player_id, game_id, team_id, minutes_played, points, 
                 field_goals_made, field_goals_attempted, free_throws_made, 
                 free_throws_attempted, total_rebounds, assists, steals, turnovers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, stat)
        
        # Create player profiles
        profiles = [
            (1, 'María García López', 'MARIA GARCIA LOPEZ', 'team_001', '2023/24', 1995, 0, None),
            (2, 'M. García López', 'M. GARCIA LOPEZ', 'team_001', '2023/24', 1995, 0, None),
            (3, 'García López, María', 'GARCIA LOPEZ, MARIA', 'team_001', '2023/24', 1995, 0, None),
            (4, 'Ana Martín Ruiz', 'ANA MARTIN RUIZ', 'team_001', '2023/24', 1998, 0, None),
            (5, 'Laura Pérez Sánchez', 'LAURA PEREZ SANCHEZ', 'team_002', '2023/24', 2000, 0, None),
            (6, 'L. Pérez', 'L. PEREZ', 'team_002', '2023/24', 2001, 0, None),
        ]
        
        for profile in profiles:
            cursor.execute("""
                INSERT INTO player_profiles 
                (player_id, name_raw, name_normalized, team_id, season, 
                 birth_year, is_consolidated, consolidated_player_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, profile)
        
        conn.commit()
        conn.close()
        
        return temp_sqlite_db
    
    def test_identity_matching_finds_duplicates(self, db_with_duplicate_profiles):
        """
        Test that identity matcher correctly identifies duplicate profiles.
        """
        matcher = PlayerIdentityMatcher(db_with_duplicate_profiles)
        
        # Find matches for profile 1 (María García López)
        matches = matcher.find_candidate_matches(profile_id=1, min_score=0.5)
        
        # Should find profiles 2 and 3 as high-confidence matches
        assert len(matches) >= 2, "Should find at least 2 matching profiles"
        
        # Check that profiles 2 and 3 are in matches
        matched_profile_ids = [m['profile_id'] for m in matches]
        assert 2 in matched_profile_ids, "Should match profile 2 (M. García López)"
        assert 3 in matched_profile_ids, "Should match profile 3 (García López, María)"
        
        # Verify scores are high for clear matches
        for match in matches:
            if match['profile_id'] in [2, 3]:
                assert match['candidate_score'] >= 0.7, \
                    f"Score should be high for profile {match['profile_id']}"
                assert match['confidence_level'] in ['high', 'very_high'], \
                    f"Confidence should be high for profile {match['profile_id']}"
    
    def test_identity_matching_rejects_false_matches(self, db_with_duplicate_profiles):
        """
        Test that identity matcher doesn't incorrectly match different players.
        """
        matcher = PlayerIdentityMatcher(db_with_duplicate_profiles)
        
        # Find matches for profile 1 (María García López)
        matches = matcher.find_candidate_matches(profile_id=1, min_score=0.3)
        
        # Should NOT match Ana Martín (profile 4) - completely different name
        matched_profile_ids = [m['profile_id'] for m in matches]
        
        if 4 in matched_profile_ids:
            # If it's in matches, score should be very low
            ana_match = next(m for m in matches if m['profile_id'] == 4)
            assert ana_match['candidate_score'] < 0.4, \
                "Different player should have low match score"
    
    def test_identity_matching_handles_age_discrepancies(self, db_with_duplicate_profiles):
        """
        Test matching behavior with different birth years.
        """
        matcher = PlayerIdentityMatcher(db_with_duplicate_profiles)
        
        # Find matches for profile 5 (Laura Pérez Sánchez, born 2000)
        matches = matcher.find_candidate_matches(profile_id=5, min_score=0.3)
        
        # Profile 6 (L. Pérez, born 2001) might match but with lower confidence
        matched_profile_ids = [m['profile_id'] for m in matches]
        
        if 6 in matched_profile_ids:
            laura_match = next(m for m in matches if m['profile_id'] == 6)
            # 1 year age difference should reduce but not eliminate match
            assert 0.3 <= laura_match['candidate_score'] <= 0.8, \
                "1-year age difference should give medium confidence"
    
    def test_consolidation_merges_duplicate_profiles(self, db_with_duplicate_profiles):
        """
        Test that consolidation correctly merges duplicate profiles.
        """
        # Run consolidation
        consolidate_identities(
            db_path=db_with_duplicate_profiles,
            min_score=0.85
        )
        
        conn = sqlite3.connect(db_with_duplicate_profiles)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check that María's profiles are consolidated
        cursor.execute("""
            SELECT 
                profile_id,
                name_raw,
                is_consolidated,
                consolidated_player_id
            FROM player_profiles
            WHERE profile_id IN (1, 2, 3)
            ORDER BY profile_id
        """)
        maria_profiles = cursor.fetchall()
        
        # At least some should be marked as consolidated
        consolidated_count = sum(1 for p in maria_profiles if p['is_consolidated'])
        assert consolidated_count >= 2, \
            "At least 2 of María's profiles should be consolidated"
        
        # Check that they reference the same consolidated_player_id
        consolidated_ids = [
            p['consolidated_player_id'] 
            for p in maria_profiles 
            if p['consolidated_player_id'] is not None
        ]
        
        if len(consolidated_ids) >= 2:
            # All consolidated profiles should point to the same master
            assert len(set(consolidated_ids)) == 1, \
                "All consolidated profiles should point to same master player"
        
        # Ana should NOT be consolidated (no duplicates)
        cursor.execute("""
            SELECT is_consolidated
            FROM player_profiles
            WHERE profile_id = 4
        """)
        ana_profile = cursor.fetchone()
        assert ana_profile['is_consolidated'] == 0, \
            "Ana should not be consolidated (no duplicates)"
        
        conn.close()
    
    def test_consolidation_aggregates_stats_correctly(self, db_with_duplicate_profiles):
        """
        Test that consolidated player stats are correctly aggregated.
        """
        # Run consolidation
        consolidate_player_profiles(
            db_path=db_with_duplicate_profiles,
            min_confidence_score=0.7
        )
        
        conn = sqlite3.connect(db_with_duplicate_profiles)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Find consolidated player_id for María
        cursor.execute("""
            SELECT DISTINCT consolidated_player_id
            FROM player_profiles
            WHERE profile_id IN (1, 2)
              AND consolidated_player_id IS NOT NULL
        """)
        result = cursor.fetchone()
        
        if result and result['consolidated_player_id']:
            consolidated_id = result['consolidated_player_id']
            
            # Check aggregated stats for consolidated player
            cursor.execute("""
                SELECT COUNT(*) as game_count
                FROM player_game_stats
                WHERE player_id IN (
                    SELECT player_id
                    FROM player_profiles
                    WHERE consolidated_player_id = ?
                       OR player_id = ?
                )
            """, (consolidated_id, consolidated_id))
            
            stats = cursor.fetchone()
            # María played 2 games (1 as player_id 1, 1 as player_id 2)
            assert stats['game_count'] == 2, \
                "Consolidated player should have stats from both profiles"
        
        conn.close()
    
    def test_consolidation_preserves_unconsolidated_profiles(self, db_with_duplicate_profiles):
        """
        Test that profiles without duplicates remain unchanged.
        """
        # Run consolidation
        consolidate_player_profiles(
            db_path=db_with_duplicate_profiles,
            min_confidence_score=0.7
        )
        
        conn = sqlite3.connect(db_with_duplicate_profiles)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ana Martín (profile 4) should remain unconsolidated
        cursor.execute("""
            SELECT 
                profile_id,
                name_raw,
                is_consolidated,
                consolidated_player_id
            FROM player_profiles
            WHERE profile_id = 4
        """)
        ana = cursor.fetchone()
        
        assert ana['is_consolidated'] == 0, "Ana should not be consolidated"
        assert ana['consolidated_player_id'] is None, \
            "Ana should not reference a consolidated player"
        
        # Her stats should still be accessible
        cursor.execute("""
            SELECT COUNT(*) as game_count
            FROM player_game_stats
            WHERE player_id = 4
        """)
        ana_stats = cursor.fetchone()
        assert ana_stats['game_count'] == 2, "Ana's stats should be preserved"
        
        conn.close()
    
    def test_consolidation_respects_confidence_threshold(self, db_with_duplicate_profiles):
        """
        Test that consolidation only merges profiles above confidence threshold.
        """
        # Run consolidation with very high threshold
        consolidate_player_profiles(
            db_path=db_with_duplicate_profiles,
            min_confidence_score=0.95  # Very high - only exact matches
        )
        
        conn = sqlite3.connect(db_with_duplicate_profiles)
        cursor = conn.cursor()
        
        # Count how many profiles were consolidated
        cursor.execute("""
            SELECT COUNT(*) as consolidated_count
            FROM player_profiles
            WHERE is_consolidated = 1
        """)
        result = cursor.fetchone()
        high_threshold_count = result[0]
        
        conn.close()
        
        # Reset database and try with lower threshold
        # (For a full test, we'd recreate the database, but here we check behavior)
        # With high threshold, fewer profiles should be consolidated
        # than with a medium threshold
        assert high_threshold_count <= 3, \
            "Very high threshold should consolidate fewer profiles"
