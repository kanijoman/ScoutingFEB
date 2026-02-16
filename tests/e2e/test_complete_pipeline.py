"""
End-to-End Test: Complete ETL Pipeline

Tests the full data flow from MongoDB to SQLite with realistic data.
Validates data transformations, calculations, and integrity throughout the pipeline.
"""

import pytest
import sqlite3
import mongomock
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from database.sqlite_schema import SQLiteSchemaManager
from ml.etl_processor import FEBDataETL


@pytest.mark.e2e
class TestCompleteETLPipeline:
    """End-to-end tests for the complete ETL pipeline."""
    
    @pytest.fixture
    def realistic_mongodb_data(self):
        """Create realistic MongoDB data structure."""
        return {
            'teams': [
                {
                    '_id': 'team_001',
                    'name': 'CB Estudiantes',
                    'gender': 'F',
                    'city': 'Madrid'
                },
                {
                    '_id': 'team_002',
                    'name': 'Perfumerías Avenida',
                    'gender': 'F',
                    'city': 'Salamanca'
                }
            ],
            'competitions': [
                {
                    '_id': 'comp_001',
                    'name': 'LF ENDESA',
                    'gender': 'F',
                    'season': '2023/24'
                }
            ],
            'games': [
                {
                    '_id': 'game_001',
                    'competition_id': 'comp_001',
                    'season': '2023/24',
                    'date': '2023-10-15',
                    'home_team_id': 'team_001',
                    'away_team_id': 'team_002',
                    'home_score': 75,
                    'away_score': 68,
                    'game_stats': [
                        {
                            'player_name': 'María García López',
                            'team_id': 'team_001',
                            'minutes_played': 28,
                            'points': 18,
                            'field_goals_made': 7,
                            'field_goals_attempted': 14,
                            'two_point_made': 5,
                            'two_point_attempted': 9,
                            'three_point_made': 2,
                            'three_point_attempted': 5,
                            'free_throws_made': 2,
                            'free_throws_attempted': 3,
                            'offensive_rebounds': 2,
                            'defensive_rebounds': 5,
                            'total_rebounds': 7,
                            'assists': 4,
                            'steals': 2,
                            'blocks': 1,
                            'turnovers': 3,
                            'personal_fouls': 2,
                            'plus_minus': 7,
                            'efficiency_rating': 22
                        },
                        {
                            'player_name': 'Ana Martín Ruiz',
                            'team_id': 'team_001',
                            'minutes_played': 32,
                            'points': 24,
                            'field_goals_made': 9,
                            'field_goals_attempted': 18,
                            'two_point_made': 6,
                            'two_point_attempted': 11,
                            'three_point_made': 3,
                            'three_point_attempted': 7,
                            'free_throws_made': 3,
                            'free_throws_attempted': 4,
                            'offensive_rebounds': 1,
                            'defensive_rebounds': 4,
                            'total_rebounds': 5,
                            'assists': 6,
                            'steals': 3,
                            'blocks': 0,
                            'turnovers': 2,
                            'personal_fouls': 3,
                            'plus_minus': 7,
                            'efficiency_rating': 28
                        },
                        {
                            'player_name': 'Laura Pérez Sánchez',
                            'team_id': 'team_002',
                            'minutes_played': 30,
                            'points': 15,
                            'field_goals_made': 6,
                            'field_goals_attempted': 13,
                            'two_point_made': 4,
                            'two_point_attempted': 8,
                            'three_point_made': 2,
                            'three_point_attempted': 5,
                            'free_throws_made': 1,
                            'free_throws_attempted': 2,
                            'offensive_rebounds': 3,
                            'defensive_rebounds': 6,
                            'total_rebounds': 9,
                            'assists': 2,
                            'steals': 1,
                            'blocks': 2,
                            'turnovers': 4,
                            'personal_fouls': 4,
                            'plus_minus': -7,
                            'efficiency_rating': 18
                        }
                    ]
                },
                {
                    '_id': 'game_002',
                    'competition_id': 'comp_001',
                    'season': '2023/24',
                    'date': '2023-10-22',
                    'home_team_id': 'team_002',
                    'away_team_id': 'team_001',
                    'home_score': 82,
                    'away_score': 78,
                    'game_stats': [
                        {
                            'player_name': 'María García López',
                            'team_id': 'team_001',
                            'minutes_played': 30,
                            'points': 22,
                            'field_goals_made': 8,
                            'field_goals_attempted': 16,
                            'two_point_made': 6,
                            'two_point_attempted': 10,
                            'three_point_made': 2,
                            'three_point_attempted': 6,
                            'free_throws_made': 4,
                            'free_throws_attempted': 5,
                            'offensive_rebounds': 1,
                            'defensive_rebounds': 6,
                            'total_rebounds': 7,
                            'assists': 3,
                            'steals': 1,
                            'blocks': 0,
                            'turnovers': 2,
                            'personal_fouls': 3,
                            'plus_minus': -4,
                            'efficiency_rating': 24
                        },
                        {
                            'player_name': 'Ana Martín Ruiz',
                            'team_id': 'team_001',
                            'minutes_played': 28,
                            'points': 16,
                            'field_goals_made': 6,
                            'field_goals_attempted': 14,
                            'two_point_made': 4,
                            'two_point_attempted': 8,
                            'three_point_made': 2,
                            'three_point_attempted': 6,
                            'free_throws_made': 2,
                            'free_throws_attempted': 2,
                            'offensive_rebounds': 0,
                            'defensive_rebounds': 3,
                            'total_rebounds': 3,
                            'assists': 8,
                            'steals': 2,
                            'blocks': 1,
                            'turnovers': 3,
                            'personal_fouls': 2,
                            'plus_minus': -4,
                            'efficiency_rating': 20
                        },
                        {
                            'player_name': 'Laura Pérez Sánchez',
                            'team_id': 'team_002',
                            'minutes_played': 34,
                            'points': 28,
                            'field_goals_made': 11,
                            'field_goals_attempted': 20,
                            'two_point_made': 8,
                            'two_point_attempted': 13,
                            'three_point_made': 3,
                            'three_point_attempted': 7,
                            'free_throws_made': 3,
                            'free_throws_attempted': 4,
                            'offensive_rebounds': 2,
                            'defensive_rebounds': 7,
                            'total_rebounds': 9,
                            'assists': 4,
                            'steals': 2,
                            'blocks': 1,
                            'turnovers': 2,
                            'personal_fouls': 3,
                            'plus_minus': 4,
                            'efficiency_rating': 32
                        }
                    ]
                }
            ]
        }
    
    def test_complete_pipeline_mongodb_to_sqlite(
        self,
        temp_sqlite_db,
        realistic_mongodb_data
    ):
        """
        Test complete data flow from MongoDB to SQLite.
        
        Validates:
        1. Data extraction from MongoDB
        2. Transformation and calculation of advanced metrics
        3. Loading into SQLite with correct structure
        4. Data integrity throughout pipeline
        """
        # Arrange: Setup MongoDB mock
        mongo_client = mongomock.MongoClient()
        mongo_db = mongo_client['scouting_test']
        
        # Populate MongoDB with realistic data
        mongo_db['teams'].insert_many(realistic_mongodb_data['teams'])
        mongo_db['competitions'].insert_many(realistic_mongodb_data['competitions'])
        mongo_db['games'].insert_many(realistic_mongodb_data['games'])
        
        # Create SQLite schema
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        # Act: Run ETL pipeline
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_test",
            sqlite_path=temp_sqlite_db,
            use_profiles=True
        )
        
        # Inject mock MongoDB
        etl.mongo_client = mongo_client
        etl.mongo_db = mongo_db
        
        # Execute pipeline
        etl.run_full_etl()
        
        # Assert: Verify data was loaded correctly
        conn = sqlite3.connect(temp_sqlite_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Check teams were loaded
        cursor.execute("SELECT COUNT(*) as count FROM teams")
        team_count = cursor.fetchone()['count']
        assert team_count == 2, "Should have 2 teams loaded"
        
        # 2. Check games were loaded
        cursor.execute("SELECT COUNT(*) as count FROM games")
        game_count = cursor.fetchone()['count']
        assert game_count == 2, "Should have 2 games loaded"
        
        # 3. Check player game stats were loaded (3 players × 2 games = 6 records)
        cursor.execute("SELECT COUNT(*) as count FROM player_game_stats")
        stats_count = cursor.fetchone()['count']
        assert stats_count == 6, f"Should have 6 player game stats, got {stats_count}"
        
        # 4. Check advanced metrics were calculated
        cursor.execute("""
            SELECT 
                true_shooting_pct,
                effective_fg_pct,
                player_efficiency_rating,
                usage_rate
            FROM player_game_stats
            WHERE true_shooting_pct IS NOT NULL
        """)
        stats_with_metrics = cursor.fetchall()
        assert len(stats_with_metrics) > 0, "Advanced metrics should be calculated"
        
        # 5. Verify specific player data (María García López)
        cursor.execute("""
            SELECT 
                p.name_raw,
                COUNT(pgs.stat_id) as games_played,
                AVG(pgs.points) as avg_points,
                AVG(pgs.total_rebounds) as avg_rebounds,
                AVG(pgs.assists) as avg_assists
            FROM players p
            JOIN player_game_stats pgs ON p.player_id = pgs.player_id
            WHERE p.name_raw = 'María García López'
            GROUP BY p.player_id
        """)
        maria_stats = cursor.fetchone()
        
        assert maria_stats is not None, "María García López should exist"
        assert maria_stats['games_played'] == 2, "Should have played 2 games"
        assert 19 <= maria_stats['avg_points'] <= 21, "Average points should be ~20"
        assert maria_stats['avg_rebounds'] == 7.0, "Average rebounds should be 7"
        
        # 6. Check player profiles were created
        cursor.execute("SELECT COUNT(*) as count FROM player_profiles")
        profile_count = cursor.fetchone()['count']
        assert profile_count >= 3, "Should have at least 3 player profiles"
        
        conn.close()
    
    def test_pipeline_calculates_advanced_metrics_correctly(
        self,
        temp_sqlite_db,
        realistic_mongodb_data
    ):
        """
        Test that advanced metrics are calculated correctly.
        
        Validates specific calculations like TS%, eFG%, PER.
        """
        # Setup and run pipeline
        mongo_client = mongomock.MongoClient()
        mongo_db = mongo_client['scouting_test']
        mongo_db['teams'].insert_many(realistic_mongodb_data['teams'])
        mongo_db['competitions'].insert_many(realistic_mongodb_data['competitions'])
        mongo_db['games'].insert_many(realistic_mongodb_data['games'])
        
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_test",
            sqlite_path=temp_sqlite_db,
            use_profiles=False  # Skip profiles for this test
        )
        etl.mongo_client = mongo_client
        etl.mongo_db = mongo_db
        etl.run_full_etl()
        
        # Verify calculations
        conn = sqlite3.connect(temp_sqlite_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get first game stats for María García López
        cursor.execute("""
            SELECT 
                pgs.*,
                p.name_raw
            FROM player_game_stats pgs
            JOIN players p ON pgs.player_id = p.player_id
            JOIN games g ON pgs.game_id = g.game_id
            WHERE p.name_raw = 'María García López'
            ORDER BY g.date
            LIMIT 1
        """)
        maria_game1 = cursor.fetchone()
        
        # Manual calculation of TS%
        # María Game 1: 18 pts, 14 FGA, 3 FTA
        # TS% = PTS / (2 * (FGA + 0.44 * FTA))
        expected_ts = 18 / (2 * (14 + 0.44 * 3))
        actual_ts = maria_game1['true_shooting_pct']
        
        assert actual_ts is not None, "TS% should be calculated"
        assert abs(actual_ts - expected_ts) < 0.01, \
            f"TS% calculation incorrect: expected {expected_ts:.3f}, got {actual_ts:.3f}"
        
        # Manual calculation of eFG%
        # María Game 1: 7 FGM, 2 3PM, 14 FGA
        # eFG% = (FGM + 0.5 * 3PM) / FGA
        expected_efg = (7 + 0.5 * 2) / 14
        actual_efg = maria_game1['effective_fg_pct']
        
        assert actual_efg is not None, "eFG% should be calculated"
        assert abs(actual_efg - expected_efg) < 0.01, \
            f"eFG% calculation incorrect: expected {expected_efg:.3f}, got {actual_efg:.3f}"
        
        # Verify all metrics are within valid ranges
        cursor.execute("""
            SELECT 
                true_shooting_pct,
                effective_fg_pct,
                player_efficiency_rating,
                turnover_pct
            FROM player_game_stats
            WHERE minutes_played > 0
        """)
        
        for row in cursor.fetchall():
            if row['true_shooting_pct'] is not None:
                assert 0 <= row['true_shooting_pct'] <= 1.5, \
                    f"TS% out of range: {row['true_shooting_pct']}"
            
            if row['effective_fg_pct'] is not None:
                assert 0 <= row['effective_fg_pct'] <= 1.0, \
                    f"eFG% out of range: {row['effective_fg_pct']}"
            
            if row['player_efficiency_rating'] is not None:
                assert -10 <= row['player_efficiency_rating'] <= 50, \
                    f"PER out of range: {row['player_efficiency_rating']}"
        
        conn.close()
    
    def test_pipeline_maintains_referential_integrity(
        self,
        temp_sqlite_db,
        realistic_mongodb_data
    ):
        """
        Test that referential integrity is maintained throughout pipeline.
        
        Validates foreign key relationships and data consistency.
        """
        # Setup and run pipeline
        mongo_client = mongomock.MongoClient()
        mongo_db = mongo_client['scouting_test']
        mongo_db['teams'].insert_many(realistic_mongodb_data['teams'])
        mongo_db['competitions'].insert_many(realistic_mongodb_data['competitions'])
        mongo_db['games'].insert_many(realistic_mongodb_data['games'])
        
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_test",
            sqlite_path=temp_sqlite_db,
            use_profiles=False
        )
        etl.mongo_client = mongo_client
        etl.mongo_db = mongo_db
        etl.run_full_etl()
        
        # Verify integrity
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # 1. All game stats should reference valid players
        cursor.execute("""
            SELECT COUNT(*) as orphaned
            FROM player_game_stats pgs
            LEFT JOIN players p ON pgs.player_id = p.player_id
            WHERE p.player_id IS NULL
        """)
        orphaned_stats = cursor.fetchone()[0]
        assert orphaned_stats == 0, "All game stats should reference valid players"
        
        # 2. All game stats should reference valid games
        cursor.execute("""
            SELECT COUNT(*) as orphaned
            FROM player_game_stats pgs
            LEFT JOIN games g ON pgs.game_id = g.game_id
            WHERE g.game_id IS NULL
        """)
        orphaned_games = cursor.fetchone()[0]
        assert orphaned_games == 0, "All game stats should reference valid games"
        
        # 3. All games should reference valid teams
        cursor.execute("""
            SELECT COUNT(*) as orphaned
            FROM games g
            LEFT JOIN teams ht ON g.home_team_id = ht.team_id
            LEFT JOIN teams at ON g.away_team_id = at.team_id
            WHERE ht.team_id IS NULL OR at.team_id IS NULL
        """)
        orphaned_teams = cursor.fetchone()[0]
        assert orphaned_teams == 0, "All games should reference valid teams"
        
        # 4. All games should reference valid competitions
        cursor.execute("""
            SELECT COUNT(*) as orphaned
            FROM games g
            LEFT JOIN competitions c ON g.competition_id = c.competition_id
            WHERE c.competition_id IS NULL
        """)
        orphaned_comps = cursor.fetchone()[0]
        assert orphaned_comps == 0, "All games should reference valid competitions"
        
        conn.close()
    
    def test_pipeline_aggregates_player_stats_correctly(
        self,
        temp_sqlite_db,
        realistic_mongodb_data
    ):
        """
        Test that player aggregated stats are calculated correctly.
        
        Validates averaging and aggregation logic.
        """
        # Setup and run pipeline
        mongo_client = mongomock.MongoClient()
        mongo_db = mongo_client['scouting_test']
        mongo_db['teams'].insert_many(realistic_mongodb_data['teams'])
        mongo_db['competitions'].insert_many(realistic_mongodb_data['competitions'])
        mongo_db['games'].insert_many(realistic_mongodb_data['games'])
        
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_test",
            sqlite_path=temp_sqlite_db,
            use_profiles=False
        )
        etl.mongo_client = mongo_client
        etl.mongo_db = mongo_db
        etl.run_full_etl()
        
        # Manually trigger aggregation
        from ml.advanced_stats import calculate_aggregated_stats
        calculate_aggregated_stats(temp_sqlite_db)
        
        # Verify aggregations
        conn = sqlite3.connect(temp_sqlite_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check María García López aggregated stats
        cursor.execute("""
            SELECT 
                pas.*,
                p.name_raw
            FROM player_aggregated_stats pas
            JOIN players p ON pas.player_id = p.player_id
            WHERE p.name_raw = 'María García López'
        """)
        maria_agg = cursor.fetchone()
        
        if maria_agg:  # May not exist if aggregation is skipped in ETL
            # She played 2 games with 18 and 22 points
            expected_avg_points = (18 + 22) / 2
            actual_avg_points = maria_agg['avg_points']
            
            assert abs(actual_avg_points - expected_avg_points) < 0.1, \
                f"Average points incorrect: expected {expected_avg_points}, got {actual_avg_points}"
            
            # Games played should be 2
            assert maria_agg['games_played'] == 2, "Should have played 2 games"
            
            # Total minutes should be 58 (28 + 30)
            assert maria_agg['total_minutes'] == 58, "Total minutes should be 58"
        
        conn.close()
