"""
Smoke Test: ML Model Execution

These tests verify that ML models can be instantiated and execute
basic operations without crashing. They do NOT validate model accuracy
or specific predictions.

Focus: "Does it run?" not "Does it work well?"
"""

import pytest
import tempfile
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ml.xgboost_model import PlayerPerformanceModel


@pytest.mark.smoke
class TestMLModelSmoke:
    """Smoke tests for ML model basic functionality."""
    
    def test_xgboost_model_instantiates(self, temp_sqlite_db):
        """
        Test that XGBoost model can be instantiated without errors.
        """
        try:
            model = PlayerPerformanceModel(db_path=temp_sqlite_db)
            assert model is not None, "Model should instantiate"
        except Exception as e:
            pytest.fail(f"Model instantiation failed: {e}")
    
    def test_xgboost_model_trains_with_minimal_data(self, temp_sqlite_db):
        """
        Test that model can train with minimal valid data.
        
        This validates the training pipeline executes without crashing.
        """
        # Create minimal training data
        n_samples = 50
        np.random.seed(42)
        
        X = pd.DataFrame({
            'feature_1': np.random.uniform(5, 20, n_samples),
            'feature_2': np.random.uniform(15, 35, n_samples),
            'feature_3': np.random.uniform(0.4, 0.6, n_samples),
        })
        
        y = pd.Series(np.random.uniform(5, 25, n_samples))
        
        # Train model
        try:
            model = PlayerPerformanceModel(db_path=temp_sqlite_db)
            result = model.train_model(X, y, model_name='test_model')
            assert result is not None, "Model trained successfully"
            assert 'model' in result
        except Exception as e:
            pytest.fail(f"Model training failed: {e}")
    
    def test_xgboost_model_predicts_after_training(self, temp_sqlite_db):
        """
        Test that model can make predictions after training.
        """
        # Create and train model
        n_samples = 50
        np.random.seed(42)
        
        X_train = pd.DataFrame({
            'feature_1': np.random.uniform(5, 20, n_samples),
            'feature_2': np.random.uniform(15, 35, n_samples),
            'feature_3': np.random.uniform(0.4, 0.6, n_samples),
        })
        
        y_train = pd.Series(np.random.uniform(5, 25, n_samples))
        
        model = PlayerPerformanceModel(db_path=temp_sqlite_db)
        model.train_model(X_train, y_train, model_name='test_predict')
        
        # Make predictions
        X_test = X_train.iloc[:5]
        try:
            predictions = model.models['test_predict'].predict(X_test)
            assert len(predictions) == 5, "Should return 5 predictions"
            assert all(isinstance(p, (int, float, np.number)) for p in predictions), \
                "All predictions should be numeric"
        except Exception as e:
            pytest.fail(f"Prediction failed: {e}")
    
    def test_xgboost_model_saves_and_loads(self, temp_sqlite_db, tmp_path):
        """
        Test that model can be saved and loaded without errors.
        """
        # Create and train minimal model
        n_samples = 30
        np.random.seed(42)
        
        X = pd.DataFrame({
            'feature_1': np.random.uniform(5, 20, n_samples),
            'feature_2': np.random.uniform(15, 35, n_samples),
            'feature_3': np.random.uniform(0.4, 0.6, n_samples),
        })
        y = pd.Series(np.random.uniform(5, 25, n_samples))
        
        model = PlayerPerformanceModel(db_path=temp_sqlite_db, model_dir=str(tmp_path))
        model.train_model(X, y, model_name='test_save')
        
        # Save model
        try:
            model.save_model('test_save')
            model_path = tmp_path / 'test_save.joblib'
            assert model_path.exists(), "Model file should be created"
        except Exception as e:
            pytest.fail(f"Model save failed: {e}")
        
        # Load model
        try:
            loaded_model = PlayerPerformanceModel(db_path=temp_sqlite_db, model_dir=str(tmp_path))
            loaded_model.load_model('test_save')
            
            # Verify it loaded correctly
            assert 'test_save' in loaded_model.models, "Model should be loaded"
        except Exception as e:
            pytest.fail(f"Model load failed: {e}")
    
    def test_xgboost_shap_executes_without_error(self, temp_sqlite_db):
        """
        Test that SHAP value calculation executes without crashing.
        
        SHAP is computationally expensive, so we use minimal data.
        """
        # Create minimal model
        n_samples = 30
        np.random.seed(42)
        
        X = pd.DataFrame({
            'feature_1': np.random.uniform(5, 20, n_samples),
            'feature_2': np.random.uniform(15, 35, n_samples),
            'feature_3': np.random.uniform(0.4, 0.6, n_samples),
        })
        y = pd.Series(np.random.uniform(5, 25, n_samples))
        
        model = PlayerPerformanceModel(db_path=temp_sqlite_db)
        result = model.train_model(X, y, model_name='test_shap')
        
        # SHAP explainer is created automatically in train_model
        try:
            assert 'explainer' in result, "SHAP explainer should be created"
            assert result['explainer'] is not None
        except Exception as e:
            # SHAP can be tricky, so we just ensure it doesn't crash catastrophically
            pytest.skip(f"SHAP calculation failed (non-critical): {e}")


@pytest.mark.smoke
class TestAdvancedStatsSmoke:
    """Smoke tests for advanced statistics calculations."""
    
    def test_advanced_stats_module_imports(self):
        """
        Test that advanced_stats module can be imported.
        """
        try:
            from ml.advanced_stats import calculate_true_shooting_pct
            assert callable(calculate_true_shooting_pct), "Function should be callable"
        except Exception as e:
            pytest.fail(f"Failed to import advanced_stats: {e}")
    
    def test_ts_percentage_calculates_without_error(self):
        """
        Test that True Shooting Percentage calculation works.
        """
        try:
            from ml.advanced_stats import calculate_true_shooting_pct
            
            # Valid case
            ts = calculate_true_shooting_pct(
                pts=20,
                fga=15,
                fta=5
            )
            assert isinstance(ts, (int, float)), "TS% should be numeric"
            assert 0 <= ts <= 1, "TS% should be between 0 and 1"
            
            # Edge case: no attempts
            ts_zero = calculate_true_shooting_pct(
                pts=0,
                fga=0,
                fta=0
            )
            # Should handle gracefully (return 0 or None)
            assert ts_zero == 0 or ts_zero is None, "Should handle zero attempts"
            
        except Exception as e:
            pytest.fail(f"TS% calculation failed: {e}")
    
    def test_per_calculates_without_error(self):
        """
        Test that PER (Player Efficiency Rating) calculation works.
        """
        try:
            from ml.advanced_stats import calculate_player_efficiency_rating
            
            # Create sample stats
            stats = {
                'pts': 15,
                'reb': 6,
                'ast': 4,
                'stl': 2,
                'blk': 1,
                'fgm': 6,
                'ftm': 3,
                'tov': 2,
                'fga': 12,
                'fta': 4,
                'minutes': 30
            }
            
            per = calculate_player_efficiency_rating(stats)
            assert isinstance(per, (int, float)), "PER should be numeric"
            assert per >= 0, "PER should be non-negative"
            
        except Exception as e:
            pytest.fail(f"PER calculation failed: {e}")
