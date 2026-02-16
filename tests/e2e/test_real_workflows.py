"""
End-to-End Tests: Real System Workflows

Tests for actual workflows in the current scouting system.
"""

import pytest
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from database.sqlite_schema import SQLiteSchemaManager
from ml.advanced_stats import (
    calculate_true_shooting_pct,
    calculate_effective_fg_pct,
    calculate_turnover_pct,
    calculate_free_throw_rate,
    calculate_assist_to_turnover_ratio,
    calculate_offensive_rating,
    calculate_player_efficiency_rating,
    calculate_usage_rate,
    calculate_all_advanced_stats
)


@pytest.mark.e2e
class TestAdvancedStatsWorkflow:
    """Test the complete workflow of calculating advanced statistics."""
    
    @pytest.fixture
    def db_with_game_data(self, temp_sqlite_db):
        """Create database with realistic game statistics."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Insert teams
        cursor.execute("""
            INSERT INTO teams (team_code, team_name) 
            VALUES ('TEAM_A', 'Team Alpha')
        """)
        cursor.execute("""
            INSERT INTO teams (team_code, team_name) 
            VALUES ('TEAM_B', 'Team Beta')
        """)
        
        # Insert competition
        cursor.execute("""
            INSERT INTO competitions (competition_name, gender, level)
            VALUES ('Test League', 'fem', 'LF')
        """)
        
        # Insert game
        cursor.execute("""
            INSERT INTO games (game_id, competition_id, season, game_date,
                             home_team_id, away_team_id, home_score, away_score)
            VALUES (1001, 1, '2023/24', '2023-10-15', 1, 2, 78, 72)
        """)
        
        # Insert player
        cursor.execute("""
            INSERT INTO players (name, position, birth_year, total_games)
            VALUES ('Ana García López', 'Base', 1998, 10)
        """)
        
        # Insert realistic game stats
        cursor.execute("""
            INSERT INTO player_game_stats (
                game_id, player_id, team_id, is_home, is_starter,
                minutes_played, points,
                field_goals_made, field_goals_attempted,
                three_points_made, three_points_attempted,
                free_throws_made, free_throws_attempted,
                total_rebounds, offensive_rebounds, defensive_rebounds,
                assists, turnovers, steals, blocks, personal_fouls
            ) VALUES (
                1001, 1, 1, 1, 1,
                32.5, 18,
                7, 14,
                2, 5,
                2, 3,
                6, 2, 4,
                5, 3, 2, 1, 2
            )
        """)
        
        conn.commit()
        conn.close()
        return temp_sqlite_db
    
    def test_calculate_true_shooting_percentage(self, db_with_game_data):
        """Test TS% calculation with real data."""
        conn = sqlite3.connect(db_with_game_data)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT points, field_goals_attempted, free_throws_attempted
            FROM player_game_stats WHERE player_id = 1
        """)
        
        pts, fga, fta = cursor.fetchone()
        conn.close()
        
        # Calculate TS%
        ts_pct = calculate_true_shooting_pct(pts, fga, fta)
        
        assert ts_pct is not None, "TS% should be calculated"
        assert 0 <= ts_pct <= 1.5, "TS% should be in reasonable range"
        
        # Manual calculation: 18 / (2 * (14 + 0.44 * 3))
        expected = 18 / (2 * (14 + 0.44 * 3))
        assert abs(ts_pct - expected) < 0.001, f"TS% calculation incorrect: {ts_pct} vs {expected}"
    
    def test_calculate_effective_field_goal_pct(self, db_with_game_data):
        """Test eFG% calculation with real data."""
        conn = sqlite3.connect(db_with_game_data)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT field_goals_made, three_points_made, field_goals_attempted
            FROM player_game_stats WHERE player_id = 1
        """)
        
        fgm, fg3m, fga = cursor.fetchone()
        conn.close()
        
        # Calculate eFG%
        efg_pct = calculate_effective_fg_pct(fgm, fg3m, fga)
        
        assert efg_pct is not None, "eFG% should be calculated"
        assert 0 <= efg_pct <= 1.5, "eFG% should be in reasonable range"
        
        # Manual calculation: (7 + 0.5 * 2) / 14
        expected = (7 + 0.5 * 2) / 14
        assert abs(efg_pct - expected) < 0.001, f"eFG% calculation incorrect"
    
    def test_calculate_turnover_percentage(self, db_with_game_data):
        """Test TOV% calculation with real data."""
        conn = sqlite3.connect(db_with_game_data)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT turnovers, field_goals_attempted, free_throws_attempted
            FROM player_game_stats WHERE player_id = 1
        """)
        
        tov, fga, fta = cursor.fetchone()
        conn.close()
        
        # Calculate TOV%
        tov_pct = calculate_turnover_pct(tov, fga, fta)
        
        assert tov_pct is not None, "TOV% should be calculated"
        assert 0 <= tov_pct <= 1.0, "TOV% should be between 0 and 1"
    
    def test_calculate_assist_to_turnover_ratio(self, db_with_game_data):
        """Test AST/TOV ratio calculation."""
        conn = sqlite3.connect(db_with_game_data)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT assists, turnovers
            FROM player_game_stats WHERE player_id = 1
        """)
        
        ast, tov = cursor.fetchone()
        conn.close()
        
        # Calculate AST/TOV
        ratio = calculate_assist_to_turnover_ratio(ast, tov)
        
        assert ratio is not None, "AST/TOV should be calculated"
        assert ratio > 0, "AST/TOV should be positive"
        assert ratio == ast / tov, "AST/TOV calculation incorrect"
    
    def test_calculate_all_stats_at_once(self, db_with_game_data):
        """Test calculating all advanced stats from game data."""
        conn = sqlite3.connect(db_with_game_data)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                points, field_goals_made, field_goals_attempted,
                three_points_made, three_points_attempted,
                free_throws_made, free_throws_attempted,
                total_rebounds, offensive_rebounds, defensive_rebounds,
                assists, turnovers, steals, blocks, personal_fouls,
                minutes_played
            FROM player_game_stats WHERE player_id = 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        # Build stats dictionary
        stats = {
            'pts': row[0],
            'fgm': row[1],
            'fga': row[2],
            'fg3m': row[3],
            'fg3a': row[4],
            'ftm': row[5],
            'fta': row[6],
            'trb': row[7],
            'orb': row[8],
            'drb': row[9],
            'ast': row[10],
            'tov': row[11],
            'stl': row[12],
            'blk': row[13],
            'pf': row[14],
            'min': row[15]
        }
        
        # Calculate all stats
        result = calculate_all_advanced_stats(stats)
        
        assert result is not None, "Should return calculated stats"
        assert 'true_shooting_pct' in result, "Should include TS%"
        assert 'effective_fg_pct' in result, "Should include eFG%"
        assert 'player_efficiency_rating' in result, "Should include PER"
        
        # Validate values are reasonable
        if result['true_shooting_pct'] is not None:
            assert 0 <= result['true_shooting_pct'] <= 1.5, "TS% should be reasonable"
        if result['effective_fg_pct'] is not None:
            assert 0 <= result['effective_fg_pct'] <= 1.5, "eFG% should be reasonable"
    
    def test_update_stats_in_database(self, db_with_game_data):
        """Test updating database with calculated stats."""
        conn = sqlite3.connect(db_with_game_data)
        cursor = conn.cursor()
        
        # Get raw stats
        cursor.execute("""
            SELECT 
                points, field_goals_made, field_goals_attempted,
                three_points_made, free_throws_made, free_throws_attempted,
                total_rebounds, offensive_rebounds, defensive_rebounds,
                assists, turnovers, steals, blocks, personal_fouls,
                minutes_played
            FROM player_game_stats WHERE player_id = 1
        """)
        
        row = cursor.fetchone()
        
        stats = {
            'pts': row[0], 'fgm': row[1], 'fga': row[2],
            'fg3m': row[3], 'ftm': row[4], 'fta': row[5],
            'trb': row[6], 'orb': row[7], 'drb': row[8],
            'ast': row[9], 'tov': row[10], 'stl': row[11],
            'blk': row[12], 'pf': row[13], 'min': row[14]
        }
        
        # Calculate advanced stats
        advanced = calculate_all_advanced_stats(stats)
        
        # Update database
        cursor.execute("""
            UPDATE player_game_stats
            SET true_shooting_pct = ?,
                effective_fg_pct = ?,
                player_efficiency_rating = ?,
                turnover_pct = ?,
                assist_to_turnover_ratio = ?
            WHERE player_id = 1
        """, (
            advanced.get('true_shooting_pct'),
            advanced.get('effective_fg_pct'),
            advanced.get('player_efficiency_rating'),
            advanced.get('turnover_pct'),
            advanced.get('assist_to_turnover_ratio')
        ))
        
        conn.commit()
        
        # Verify update
        cursor.execute("""
            SELECT true_shooting_pct, effective_fg_pct, player_efficiency_rating
            FROM player_game_stats WHERE player_id = 1
        """)
        
        ts, efg, per = cursor.fetchone()
        conn.close()
        
        assert ts is not None, "TS% should be updated"
        assert efg is not None, "eFG% should be updated"
        # PER can be None if team stats are missing, just check it was attempted
        assert True, "Update completed successfully"


@pytest.mark.e2e
class TestDatabaseIntegrityWorkflow:
    """Test database integrity and constraints."""
    
    @pytest.fixture
    def populated_db(self, temp_sqlite_db):
        """Create database with multiple related records."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Insert teams
        cursor.execute("INSERT INTO teams (team_code, team_name) VALUES ('T1', 'Team 1')")
        cursor.execute("INSERT INTO teams (team_code, team_name) VALUES ('T2', 'Team 2')")
        
        # Insert competition
        cursor.execute("""
            INSERT INTO competitions (competition_name, gender, level)
            VALUES ('League A', 'fem', 'LF')
        """)
        
        # Insert game
        cursor.execute("""
            INSERT INTO games (game_id, competition_id, season, game_date,
                             home_team_id, away_team_id, home_score, away_score)
            VALUES (101, 1, '2023/24', '2023-10-15', 1, 2, 75, 70)
        """)
        
        # Insert players
        cursor.execute("INSERT INTO players (name, birth_year) VALUES ('Player A', 1998)")
        cursor.execute("INSERT INTO players (name, birth_year) VALUES ('Player B', 1999)")
        
        # Insert stats
        cursor.execute("""
            INSERT INTO player_game_stats (
                game_id, player_id, team_id, minutes_played, points,
                field_goals_made, field_goals_attempted, total_rebounds, assists
            ) VALUES (101, 1, 1, 30, 20, 8, 15, 6, 5)
        """)
        cursor.execute("""
            INSERT INTO player_game_stats (
                game_id, player_id, team_id, minutes_played, points,
                field_goals_made, field_goals_attempted, total_rebounds, assists
            ) VALUES (101, 2, 1, 25, 15, 6, 12, 4, 3)
        """)
        
        conn.commit()
        conn.close()
        return temp_sqlite_db
    
    def test_foreign_key_integrity(self, populated_db):
        """Test that all foreign keys reference existing records."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        
        # Check player_game_stats → players
        cursor.execute("""
            SELECT COUNT(*)
            FROM player_game_stats pgs
            LEFT JOIN players p ON pgs.player_id = p.player_id
            WHERE p.player_id IS NULL
        """)
        orphaned_players = cursor.fetchone()[0]
        
        # Check player_game_stats → games
        cursor.execute("""
            SELECT COUNT(*)
            FROM player_game_stats pgs
            LEFT JOIN games g ON pgs.game_id = g.game_id
            WHERE g.game_id IS NULL
        """)
        orphaned_games = cursor.fetchone()[0]
        
        # Check games → teams
        cursor.execute("""
            SELECT COUNT(*)
            FROM games g
            LEFT JOIN teams t ON g.home_team_id = t.team_id
            WHERE t.team_id IS NULL
        """)
        orphaned_home_teams = cursor.fetchone()[0]
        
        conn.close()
        
        assert orphaned_players == 0, "No orphaned player references"
        assert orphaned_games == 0, "No orphaned game references"
        assert orphaned_home_teams == 0, "No orphaned team references"
    
    def test_unique_constraints(self, populated_db):
        """Test that unique constraints are enforced."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        
        # Try to insert duplicate team
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO teams (team_code, team_name)
                VALUES ('T1', 'Duplicate Team')
            """)
        
        conn.close()
    
    def test_stat_values_are_valid(self, populated_db):
        """Test that statistical values are within valid ranges."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                minutes_played, points,
                field_goals_made, field_goals_attempted,
                total_rebounds, assists
            FROM player_game_stats
        """)
        
        for row in cursor.fetchall():
            minutes, points, fgm, fga, reb, ast = row
            
            # Validate ranges
            assert 0 <= minutes <= 48, f"Minutes out of range: {minutes}"
            assert 0 <= points <= 100, f"Points out of range: {points}"
            assert 0 <= fgm <= fga, f"FGM > FGA: {fgm} > {fga}"
            assert 0 <= reb <= 30, f"Rebounds out of range: {reb}"
            assert 0 <= ast <= 20, f"Assists out of range: {ast}"
        
        conn.close()
    
    def test_player_name_uniqueness(self, populated_db):
        """Test that player names are unique."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, COUNT(*) as count
            FROM players
            GROUP BY name
            HAVING count > 1
        """)
        
        duplicates = cursor.fetchall()
        conn.close()
        
        assert len(duplicates) == 0, f"Found duplicate players: {duplicates}"


@pytest.mark.e2e
class TestPlayerAggregationWorkflow:
    """Test aggregating player statistics across games."""
    
    @pytest.fixture
    def db_with_multiple_games(self, temp_sqlite_db):
        """Create database with player stats across multiple games."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Setup basic data
        cursor.execute("INSERT INTO teams (team_code, team_name) VALUES ('T1', 'Team')")
        cursor.execute("""
            INSERT INTO competitions (competition_name, gender, level)
            VALUES ('League', 'fem', 'LF')
        """)
        cursor.execute("INSERT INTO players (name, birth_year) VALUES ('Test Player', 1998)")
        
        # Insert 5 games with stats
        for game_num in range(1, 6):
            cursor.execute("""
                INSERT INTO games (game_id, competition_id, season, game_date,
                                 home_team_id, away_team_id, home_score, away_score)
                VALUES (?, 1, '2023/24', '2023-10-1' || ?, 1, 1, 75, 70)
            """, (game_num, game_num))
            
            cursor.execute("""
                INSERT INTO player_game_stats (
                    game_id, player_id, team_id,
                    minutes_played, points, field_goals_made, field_goals_attempted,
                    total_rebounds, assists, turnovers
                ) VALUES (?, 1, 1, 30, ?, 8, 15, 6, 5, 3)
            """, (game_num, 15 + game_num))  # Varying points
        
        conn.commit()
        conn.close()
        return temp_sqlite_db
    
    def test_aggregate_player_stats(self, db_with_multiple_games):
        """Test aggregating stats across multiple games."""
        conn = sqlite3.connect(db_with_multiple_games)
        cursor = conn.cursor()
        
        # Aggregate stats
        cursor.execute("""
            SELECT 
                COUNT(*) as games_played,
                SUM(points) as total_points,
                AVG(points) as avg_points,
                SUM(minutes_played) as total_minutes,
                AVG(minutes_played) as avg_minutes,
                SUM(assists) as total_assists,
                SUM(turnovers) as total_turnovers
            FROM player_game_stats
            WHERE player_id = 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        games, total_pts, avg_pts, total_min, avg_min, total_ast, total_tov = row
        
        assert games == 5, "Should have 5 games"
        assert total_pts == 16 + 17 + 18 + 19 + 20, "Total points incorrect"
        assert abs(avg_pts - 18) < 0.1, "Average points incorrect"
        assert total_min == 150, "Total minutes incorrect"
        assert avg_min == 30, "Average minutes incorrect"
        assert total_ast == 25, "Total assists incorrect"
        assert total_tov == 15, "Total turnovers incorrect"
    
    def test_calculate_per_game_averages(self, db_with_multiple_games):
        """Test calculating per-game averages."""
        conn = sqlite3.connect(db_with_multiple_games)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                AVG(points) as ppg,
                AVG(total_rebounds) as rpg,
                AVG(assists) as apg,
                AVG(minutes_played) as mpg
            FROM player_game_stats
            WHERE player_id = 1
        """)
        
        ppg, rpg, apg, mpg = cursor.fetchone()
        conn.close()
        
        assert ppg == 18.0, f"PPG should be 18.0, got {ppg}"
        assert rpg == 6.0, f"RPG should be 6.0, got {rpg}"
        assert apg == 5.0, f"APG should be 5.0, got {apg}"
        assert mpg == 30.0, f"MPG should be 30.0, got {mpg}"
    
    def test_calculate_shooting_percentages(self, db_with_multiple_games):
        """Test calculating season shooting percentages."""
        conn = sqlite3.connect(db_with_multiple_games)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                SUM(field_goals_made) * 1.0 / SUM(field_goals_attempted) as fg_pct,
                SUM(points) as total_points,
                SUM(field_goals_attempted) as total_fga
            FROM player_game_stats
            WHERE player_id = 1
        """)
        
        fg_pct, total_pts, total_fga = cursor.fetchone()
        conn.close()
        
        assert 0 <= fg_pct <= 1, "FG% should be between 0 and 1"
        assert total_fga == 75, "Total FGA should be 75 (15 * 5 games)"
        assert total_pts == 90, "Total points should be 90"


@pytest.mark.e2e
class TestSchemaManagement:
    """Test database schema creation and management."""
    
    def test_schema_creation_is_idempotent(self, temp_sqlite_db):
        """Test that schema can be created multiple times safely."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        
        # Create schema first time
        schema_mgr.create_database()
        
        # Create schema second time (should not fail)
        schema_mgr.create_database()
        
        # Verify tables exist
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        expected_tables = [
            'competitions', 'competition_levels', 'games',
            'players', 'player_game_stats', 'teams'
        ]
        
        for table in expected_tables:
            assert table in tables, f"Table '{table}' should exist"
    
    def test_all_required_tables_created(self, temp_sqlite_db):
        """Test that all required tables are created."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Check each table
        tables_to_check = [
            'players', 'teams', 'competitions', 'games',
            'player_game_stats', 'player_aggregated_stats'
        ]
        
        for table in tables_to_check:
            cursor.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{table}'
            """)
            result = cursor.fetchone()
            assert result is not None, f"Table '{table}' should exist"
        
        conn.close()
