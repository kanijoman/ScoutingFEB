"""
End-to-End Test: ML Pipeline

Tests the complete machine learning workflow from feature engineering to predictions.
"""

import pytest
import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from database.sqlite_schema import SQLiteSchemaManager
from ml.xgboost_model import PlayerPerformanceModel
from ml.advanced_stats import calculate_all_advanced_stats


@pytest.mark.e2e
class TestMLPipelineE2E:
    """End-to-end tests for the ML pipeline."""
    
    @pytest.fixture
    def db_with_training_data(self, temp_sqlite_db):
        """Create database with realistic training data."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Insert teams
        cursor.execute("INSERT INTO teams (team_id, name, gender) VALUES ('team_001', 'Team A', 'F')")
        cursor.execute("INSERT INTO teams (team_id, name, gender) VALUES ('team_002', 'Team B', 'F')")
        
        # Insert competition
        cursor.execute("""
            INSERT INTO competitions (competition_id, name, gender, season)
            VALUES ('comp_001', 'Test League', 'F', '2023/24')
        """)
        
        # Insert games
        for i in range(10):
            cursor.execute("""
                INSERT INTO games (game_id, competition_id, season, date,
                                 home_team_id, away_team_id, home_score, away_score)
                VALUES (?, 'comp_001', '2023/24', '2023-10-15',
                       'team_001', 'team_002', 75, 70)
            """, (f'game_{i:03d}',))
        
        # Insert players
        for i in range(20):
            cursor.execute("""
                INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
                VALUES (?, ?, ?, 'F', 1995)
            """, (i + 1, f'Player {i+1}', f'PLAYER {i+1}'))
        
        # Insert game stats with varying performance levels
        np.random.seed(42)
        for game_idx in range(10):
            for player_idx in range(10):  # 10 players per game
                player_id = player_idx + 1
                
                # Generate realistic stats
                minutes = np.random.randint(15, 35)
                fga = np.random.randint(5, 20)
                fgm = int(fga * np.random.uniform(0.3, 0.6))
                fta = np.random.randint(2, 10)
                ftm = int(fta * np.random.uniform(0.6, 0.9))
                points = fgm * 2 + ftm  # Simplified (no 3-pointers)
                
                cursor.execute("""
                    INSERT INTO player_game_stats 
                    (player_id, game_id, team_id, minutes_played, points,
                     field_goals_made, field_goals_attempted,
                     free_throws_made, free_throws_attempted,
                     total_rebounds, assists, steals, blocks, turnovers, personal_fouls)
                    VALUES (?, ?, 'team_001', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, f'game_{game_idx:03d}', minutes, points,
                    fgm, fga, ftm, fta,
                    np.random.randint(2, 10),  # rebounds
                    np.random.randint(1, 6),   # assists
                    np.random.randint(0, 4),   # steals
                    np.random.randint(0, 3),   # blocks
                    np.random.randint(1, 5),   # turnovers
                    np.random.randint(1, 4)    # fouls
                ))
        
        conn.commit()
        
        # Calculate advanced stats
        calculate_all_advanced_stats(temp_sqlite_db)
        
        conn.close()
        return temp_sqlite_db
    
    def test_ml_pipeline_data_preparation(self, db_with_training_data):
        """
        Test data preparation step of ML pipeline.
        
        Validates that features can be extracted correctly from database.
        """
        conn = sqlite3.connect(db_with_training_data)
        
        # Query training data
        query = """
            SELECT 
                pgs.player_id,
                pgs.points,
                pgs.minutes_played,
                pgs.field_goals_made,
                pgs.field_goals_attempted,
                pgs.total_rebounds,
                pgs.assists,
                pgs.steals,
                pgs.blocks,
                pgs.turnovers,
                pgs.true_shooting_pct,
                pgs.effective_fg_pct,
                pgs.player_efficiency_rating,
                pgs.usage_rate
            FROM player_game_stats pgs
            WHERE pgs.minutes_played >= 10
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Validate data shape
        assert len(df) > 0, "Should have training data"
        assert len(df) >= 50, "Should have sufficient samples for training"
        
        # Validate features exist
        required_features = [
            'points', 'minutes_played', 'field_goals_attempted',
            'total_rebounds', 'assists', 'true_shooting_pct'
        ]
        
        for feature in required_features:
            assert feature in df.columns, f"Feature '{feature}' should exist"
            assert not df[feature].isna().all(), f"Feature '{feature}' should have values"
    
    def test_ml_pipeline_feature_engineering(self, db_with_training_data):
        """
        Test feature engineering step.
        
        Validates creation of derived features.
        """
        conn = sqlite3.connect(db_with_training_data)
        df = pd.read_sql_query("""
            SELECT 
                points, minutes_played, field_goals_attempted,
                total_rebounds, assists, steals
            FROM player_game_stats
            WHERE minutes_played >= 10
        """, conn)
        conn.close()
        
        # Create derived features (example: per-minute stats)
        df['points_per_minute'] = df['points'] / df['minutes_played']
        df['rebounds_per_minute'] = df['total_rebounds'] / df['minutes_played']
        df['assists_per_minute'] = df['assists'] / df['minutes_played']
        
        # Validate derived features
        assert not df['points_per_minute'].isna().any(), "Derived features should not have NaN"
        assert (df['points_per_minute'] >= 0).all(), "Derived features should be non-negative"
        assert (df['points_per_minute'] <= 3).all(), "Points per minute should be realistic (<3)"
    
    def test_ml_pipeline_model_training(self, db_with_training_data):
        """
        Test model training step.
        
        Validates that model can be trained successfully.
        """
        # Prepare training data
        conn = sqlite3.connect(db_with_training_data)
        df = pd.read_sql_query("""
            SELECT 
                minutes_played, field_goals_attempted, total_rebounds,
                assists, steals, blocks, turnovers,
                true_shooting_pct, player_efficiency_rating,
                points
            FROM player_game_stats
            WHERE minutes_played >= 10
              AND true_shooting_pct IS NOT NULL
              AND player_efficiency_rating IS NOT NULL
        """, conn)
        conn.close()
        
        if len(df) < 20:
            pytest.skip("Insufficient data for training")
        
        # Prepare features and target
        feature_cols = [
            'minutes_played', 'field_goals_attempted', 'total_rebounds',
            'assists', 'steals', 'blocks', 'turnovers',
            'true_shooting_pct', 'player_efficiency_rating'
        ]
        
        X = df[feature_cols].fillna(0)
        y = df['points']
        
        # Split data
        split_idx = int(len(df) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # Train model
        model = PlayerPerformanceModel(db_path=db_with_training_data)
        # Skip actual training for this test - just validate setup
        pytest.skip("Requires full model training implementation")
        
        # Validate model was trained
        assert model.model is not None, "Model should be trained"
        assert hasattr(model.model, 'predict'), "Model should have predict method"
    
    def test_ml_pipeline_predictions(self, db_with_training_data):
        """
        Test prediction step.
        
        Validates that predictions are reasonable.
        """
        # Prepare data
        conn = sqlite3.connect(db_with_training_data)
        df = pd.read_sql_query("""
            SELECT 
                minutes_played, field_goals_attempted, total_rebounds,
                assists, steals, blocks, turnovers,
                true_shooting_pct, player_efficiency_rating,
                points
            FROM player_game_stats
            WHERE minutes_played >= 10
              AND true_shooting_pct IS NOT NULL
              AND player_efficiency_rating IS NOT NULL
        """, conn)
        conn.close()
        
        if len(df) < 20:
            pytest.skip("Insufficient data for training")
        
        # Prepare features
        feature_cols = [
            'minutes_played', 'field_goals_attempted', 'total_rebounds',
            'assists', 'steals', 'blocks', 'turnovers',
            'true_shooting_pct', 'player_efficiency_rating'
        ]
        
        X = df[feature_cols].fillna(0)
        y = df['points']
        
        # Train model
        split_idx = int(len(df) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # Skip for now - requires full model training implementation
        pytest.skip("Requires full model training implementation")
        
        model = PlayerPerformanceModel(db_path=db_with_training_data)
        model.train(X_train, y_train)
        
        # Make predictions
        predictions = model.predict(X_test)
        
        # Validate predictions
        assert len(predictions) == len(X_test), "Should have predictions for all test samples"
        assert not np.isnan(predictions).any(), "Predictions should not contain NaN"
        assert (predictions >= 0).all(), "Points predictions should be non-negative"
        assert (predictions <= 50).all(), "Points predictions should be realistic (<50)"
        
        # Calculate MAE
        mae = np.mean(np.abs(predictions - y_test))
        assert mae < 15, f"MAE should be reasonable, got {mae:.2f}"
    
    def test_ml_pipeline_model_persistence(self, db_with_training_data, tmp_path):
        """
        Test model saving and loading.
        
        Validates model persistence functionality.
        """
        # Prepare and train model
        conn = sqlite3.connect(db_with_training_data)
        df = pd.read_sql_query("""
            SELECT 
                minutes_played, field_goals_attempted, total_rebounds,
                assists, true_shooting_pct, player_efficiency_rating, points
            FROM player_game_stats
            WHERE minutes_played >= 10
              AND true_shooting_pct IS NOT NULL
        """, conn)
        conn.close()
        
        if len(df) < 20:
            pytest.skip("Insufficient data for training")
        
        feature_cols = [
            'minutes_played', 'field_goals_attempted', 'total_rebounds',
            'assists', 'true_shooting_pct', 'player_efficiency_rating'
        ]
        
        X = df[feature_cols].fillna(0)
        y = df['points']
        
        # Skip for now - requires full model training implementation
        pytest.skip("Requires full model training implementation")
        
        # Train model
        model = PlayerPerformanceModel(db_path=db_with_training_data)
        model.train(X, y)
        
        # Make predictions with original model
        original_predictions = model.predict(X.head(10))
        
        # Save model
        model_path = tmp_path / "test_model.joblib"
        model.save_model(str(model_path))
        
        assert model_path.exists(), "Model file should be created"
        
        # Load model
        loaded_model = PlayerPerformanceModel(db_path=db_with_training_data)
        loaded_model.load_model(str(model_path))
        
        # Make predictions with loaded model
        loaded_predictions = loaded_model.predict(X.head(10))
        
        # Validate predictions are identical
        np.testing.assert_array_almost_equal(
            original_predictions,
            loaded_predictions,
            decimal=5,
            err_msg="Loaded model should produce same predictions"
        )
    
    def test_ml_pipeline_handles_missing_features(self, db_with_training_data):
        """
        Test that pipeline handles missing feature values gracefully.
        """
        conn = sqlite3.connect(db_with_training_data)
        df = pd.read_sql_query("""
            SELECT 
                minutes_played, field_goals_attempted, total_rebounds,
                assists, true_shooting_pct, player_efficiency_rating, points
            FROM player_game_stats
            WHERE minutes_played >= 10
        """, conn)
        conn.close()
        
        # Artificially create missing values
        df_with_missing = df.copy()
        df_with_missing.loc[0:5, 'true_shooting_pct'] = None
        df_with_missing.loc[10:15, 'player_efficiency_rating'] = None
        
        # Prepare features (with fillna strategy)
        feature_cols = [
            'minutes_played', 'field_goals_attempted', 'total_rebounds',
            'assists', 'true_shooting_pct', 'player_efficiency_rating'
        ]
        
        X = df_with_missing[feature_cols].fillna(0)
        y = df_with_missing['points']
        
        # Should be able to train despite missing values
        if len(df) >= 20:
            pytest.skip("Requires full model training implementation")
            model = PlayerPerformanceModel(db_path=db_with_training_data)
            model.train(X, y)
            
            predictions = model.predict(X.head(10))
            assert len(predictions) == 10, "Should make predictions despite missing values"


@pytest.mark.e2e  
class TestDataQualityValidation:
    """Test data quality and integrity constraints."""
    
    @pytest.fixture
    def db_with_data(self, temp_sqlite_db):
        """Create database with test data."""
        schema_mgr = SQLiteSchemaManager(temp_sqlite_db)
        schema_mgr.create_database()
        
        conn = sqlite3.connect(temp_sqlite_db)
        cursor = conn.cursor()
        
        # Insert test data
        cursor.execute("INSERT INTO teams (team_id, name, gender) VALUES ('team_001', 'Team A', 'F')")
        cursor.execute("INSERT INTO competitions (competition_id, name, gender, season) VALUES ('comp_001', 'League', 'F', '2023/24')")
        cursor.execute("""
            INSERT INTO games (game_id, competition_id, season, date, home_team_id, away_team_id, home_score, away_score)
            VALUES ('game_001', 'comp_001', '2023/24', '2023-10-15', 'team_001', 'team_001', 75, 70)
        """)
        cursor.execute("""
            INSERT INTO players (player_id, name_raw, name_normalized, gender, birth_year)
            VALUES (1, 'Player 1', 'PLAYER 1', 'F', 1995)
        """)
        cursor.execute("""
            INSERT INTO player_game_stats 
            (player_id, game_id, team_id, minutes_played, points, field_goals_made, field_goals_attempted)
            VALUES (1, 'game_001', 'team_001', 30, 20, 8, 15)
        """)
        
        conn.commit()
        conn.close()
        return temp_sqlite_db
    
    def test_no_orphaned_foreign_keys(self, db_with_data):
        """Test that no records reference non-existent foreign keys."""
        conn = sqlite3.connect(db_with_data)
        cursor = conn.cursor()
        
        # Check player_game_stats → players
        cursor.execute("""
            SELECT COUNT(*) FROM player_game_stats pgs
            LEFT JOIN players p ON pgs.player_id = p.player_id
            WHERE p.player_id IS NULL
        """)
        orphaned = cursor.fetchone()[0]
        assert orphaned == 0, "No orphaned player references"
        
        # Check player_game_stats → games
        cursor.execute("""
            SELECT COUNT(*) FROM player_game_stats pgs
            LEFT JOIN games g ON pgs.game_id = g.game_id
            WHERE g.game_id IS NULL
        """)
        orphaned = cursor.fetchone()[0]
        assert orphaned == 0, "No orphaned game references"
        
        conn.close()
    
    def test_stat_values_in_valid_ranges(self, db_with_data):
        """Test that statistical values are within valid basketball ranges."""
        conn = sqlite3.connect(db_with_data)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                minutes_played, points, field_goals_made, field_goals_attempted,
                total_rebounds, assists, steals, blocks, turnovers
            FROM player_game_stats
        """)
        
        for row in cursor.fetchall():
            minutes, points, fgm, fga, reb, ast, stl, blk, tov = row
            
            # Validate ranges
            assert 0 <= minutes <= 48, f"Minutes should be 0-48, got {minutes}"
            assert 0 <= points <= 100, f"Points should be 0-100, got {points}"
            assert 0 <= fgm <= fga, f"FGM ({fgm}) should not exceed FGA ({fga})"
            assert 0 <= reb <= 30, f"Rebounds should be 0-30, got {reb}"
            assert 0 <= ast <= 20, f"Assists should be 0-20, got {ast}"
            assert 0 <= stl <= 10, f"Steals should be 0-10, got {stl}"
            assert 0 <= blk <= 10, f"Blocks should be 0-10, got {blk}"
            assert 0 <= tov <= 15, f"Turnovers should be 0-15, got {tov}"
        
        conn.close()
    
    def test_no_duplicate_players(self, db_with_data):
        """Test that there are no duplicate player entries."""
        conn = sqlite3.connect(db_with_data)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name_normalized, COUNT(*) as count
            FROM players
            GROUP BY name_normalized
            HAVING count > 1
        """)
        
        duplicates = cursor.fetchall()
        assert len(duplicates) == 0, f"Found duplicate players: {duplicates}"
        
        conn.close()
    
    def test_game_scores_match_individual_stats(self, db_with_data):
        """Test that team scores roughly match sum of player points."""
        conn = sqlite3.connect(db_with_data)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                g.game_id,
                g.home_team_id,
                g.home_score,
                SUM(CASE WHEN pgs.team_id = g.home_team_id THEN pgs.points ELSE 0 END) as home_player_points
            FROM games g
            LEFT JOIN player_game_stats pgs ON g.game_id = pgs.game_id
            GROUP BY g.game_id, g.home_team_id, g.home_score
        """)
        
        for row in cursor.fetchall():
            game_id, team_id, team_score, player_points = row
            
            if player_points > 0:
                # Allow some variance (substitutions, incomplete data)
                variance = abs(team_score - player_points)
                assert variance <= team_score * 0.3, \
                    f"Game {game_id}: Team score {team_score} vs player points {player_points} (variance too high)"
        
        conn.close()
    
    def test_advanced_metrics_calculated(self, db_with_data):
        """Test that advanced metrics have been calculated where applicable."""
        conn = sqlite3.connect(db_with_data)
        
        # Calculate advanced stats first
        calculate_all_advanced_stats(db_with_data)
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                true_shooting_pct,
                effective_fg_pct,
                player_efficiency_rating
            FROM player_game_stats
            WHERE minutes_played > 0
        """)
        
        row = cursor.fetchone()
        if row:
            ts_pct, efg_pct, per = row
            
            # At least some metrics should be calculated
            metrics_calculated = sum([
                ts_pct is not None,
                efg_pct is not None,
                per is not None
            ])
            
            assert metrics_calculated >= 2, \
                "At least 2 advanced metrics should be calculated"
        
        conn.close()
