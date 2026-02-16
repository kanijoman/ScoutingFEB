"""
Machine Learning module with XGBoost and SHAP for player performance prediction.

This module includes:
- Feature preparation from SQLite
- XGBoost model training
- Interpretability with SHAP
- Future player performance prediction
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from pathlib import Path
import json
import joblib
from datetime import datetime

# ML libraries
try:
    import xgboost as xgb
    import shap
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    import matplotlib.pyplot as plt
except ImportError:
    raise ImportError(
        "ML libraries required. Install with: "
        "pip install xgboost shap scikit-learn matplotlib"
    )


class PlayerPerformanceModel:
    """ML model for predicting player performance."""
    
    def __init__(self, db_path: str = "scouting_feb.db", 
                 model_dir: str = "models"):
        """
        Initialize model.
        
        Args:
            db_path: Path to SQLite database
            model_dir: Directory to save models
        """
        self.db_path = db_path
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
        # Trained models
        self.models = {}
        self.scalers = {}
        self.feature_names = []
        self.target_name = None
        
        # SHAP explainers
        self.explainers = {}
    
    def get_connection(self) -> sqlite3.Connection:
        """Get SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # DATA PREPARATION
    # =========================================================================
    
    def prepare_training_data(self, target: str = "next_game_points",
                             min_games: int = 5) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data from SQLite.
        
        Args:
            target: Target variable ('next_game_points', 'next_game_efficiency', etc.)
            min_games: Minimum games played to include player
            
        Returns:
            Tuple (features_df, target_series)
        """
        self.logger.info(f"Preparing training data for target: {target}")
        self.target_name = target
        
        conn = self.get_connection()
        
        # Query to get features and targets
        query = """
        SELECT 
            pgs.player_id,
            pgs.game_id,
            pp.consolidated_player_id,

            -- Current game features
            pgs.age_at_game,
            pgs.minutes_played,
            pgs.points,
            pgs.efficiency_rating,
            pgs.field_goal_pct,
            pgs.three_point_pct,
            pgs.free_throw_pct,
            pgs.total_rebounds,
            pgs.assists,
            pgs.turnovers,
            pgs.steals,
            pgs.blocks,
            pgs.personal_fouls,
            pgs.plus_minus,
            pgs.is_starter,
            pgs.is_home,
            pgs.team_won,
            
            -- Normalized Z-Scores (CRITICAL for comparing eras/leagues)
            pgs.z_offensive_rating,
            pgs.z_player_efficiency_rating,
            pgs.z_true_shooting_pct,
            pgs.z_usage_rate,
            pgs.z_minutes,
            
            -- Aggregated player features
            pas.avg_age,
            pas.avg_minutes,
            pas.avg_points,
            pas.avg_efficiency,
            pas.avg_field_goal_pct,
            pas.avg_three_point_pct,
            pas.avg_total_rebounds,
            pas.avg_assists,
            pas.std_points,
            pas.std_efficiency,
            pas.trend_points,
            pas.trend_efficiency,
            pas.win_percentage,
            pas.games_played as season_games_played,
            
            -- Aggregated Z-Scores and percentiles
            pas.z_avg_offensive_rating,
            pas.z_avg_player_efficiency_rating,
            pas.z_avg_true_shooting_pct,
            pas.z_avg_win_shares_per_36,
            pas.percentile_offensive_rating,
            pas.percentile_player_efficiency_rating,
            
            -- ✨ NEW FEATURES: Per-36 minutes normalization
            ppm.pts_per_36,
            ppm.ast_per_36,
            ppm.reb_per_36,
            ppm.stl_per_36,
            ppm.blk_per_36,
            ppm.tov_per_36,
            
            -- ✨ NUEVAS FEATURES: Rolling windows y momentum
            ppm.last_5_games_pts,
            ppm.last_5_games_oer,
            ppm.last_10_games_pts,
            ppm.last_10_games_oer,
            ppm.momentum_index,
            ppm.trend_points as ppm_trend_points,
            
            -- ✨ NUEVAS FEATURES: Consistencia mejorada
            ppm.cv_points,
            ppm.stability_index,
            
            -- ✨ NUEVAS FEATURES: Ratios jugadora/equipo
            ppm.player_pts_share,
            ppm.player_usage_share,
            ppm.efficiency_vs_team_avg,
            ppm.minutes_share,
            
            -- Features del partido
            g.score_diff,
            c.gender,
            c.level,
            
            -- Features del equipo (si disponibles)
            tgc.team_streak,
            tgc.days_since_last_game,
            tgc.team_last5_wins,
            
            -- Identificar la temporada actual
            g.season
            
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.game_id
        JOIN competitions c ON g.competition_id = c.competition_id
        JOIN player_profiles pp ON pgs.player_id = pp.profile_id
        LEFT JOIN player_aggregated_stats pas 
            ON pgs.player_id = pas.player_id 
            AND g.season = pas.season
            AND g.competition_id = pas.competition_id
        LEFT JOIN player_profile_metrics ppm 
            ON pgs.player_id = ppm.profile_id
        LEFT JOIN team_game_context tgc 
            ON pgs.game_id = tgc.game_id 
            AND pgs.team_id = tgc.team_id
        WHERE pgs.player_id IN (
            -- Filtrar jugadores/perfiles con suficientes partidos
            SELECT player_id 
            FROM player_game_stats 
            GROUP BY player_id 
            HAVING COUNT(*) >= ?
        )
        AND pgs.minutes_played > 0
        ORDER BY pgs.player_id, g.game_date
        """
        
        df = pd.read_sql_query(query, conn, params=(min_games,))
        conn.close()
        
        self.logger.info(f"Datos cargados: {len(df)} registros, {df['player_id'].nunique()} jugadores")
        
        # Calcular targets (próximo partido)
        df = self._compute_targets(df)
        
        # Eliminar registros sin target (último partido de cada jugador)
        df = df.dropna(subset=[target])
        
        self.logger.info(f"Datos con target: {len(df)} registros")
        
        # Separar features y target
        target_cols = ['next_season_avg_points', 'next_season_avg_efficiency']
        feature_cols = [col for col in df.columns 
                       if col not in target_cols + ['player_id', 'game_id', 'season', 
                                                     'next_season', 'season_avg_points', 
                                                     'season_avg_efficiency', 'season_total_minutes',
                                                     'next_season_total_minutes', 'consolidated_player_id']]
        
        X = df[feature_cols].copy()
        y = df[target]
        
        # Encoding de variables categóricas
        categorical_cols = ['position', 'gender', 'level']
        for col in categorical_cols:
            if col in X.columns:
                X[col] = X[col].fillna('unknown')
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col])
        
        # Rellenar NaN con 0 (para features opcionales)
        X = X.fillna(0).infer_objects(copy=False)
        
        self.feature_names = list(X.columns)
        
        return X, y
    
    def _compute_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcular targets (promedios de la próxima temporada) para cada jugador.
        
        Args:
            df: DataFrame con datos ordenados por jugador y fecha
            
        Returns:
            DataFrame con columnas de target añadidas
        """
        self.logger.info("Calculando targets (promedios próxima temporada)...")
        
        # Filtrar solo perfiles consolidados
        df = df[df['consolidated_player_id'].notna()].copy()
        self.logger.info(f"Registros con identidad consolidada: {len(df)}")
        self.logger.info(f"Identidades únicas: {df['consolidated_player_id'].nunique()}")
        
        # Agrupar por identidad consolidada y temporada para calcular promedios
        season_stats = df.groupby(['consolidated_player_id', 'season']).agg({
            'points': 'mean',
            'efficiency_rating': 'mean',
            'minutes_played': ['sum', 'count']
        }).reset_index()
        
        season_stats.columns = ['consolidated_player_id', 'season', 'season_avg_points', 
                                'season_avg_efficiency', 'season_total_minutes', 'games_in_season']
        
        # Calcular temporada siguiente
        def next_season(season_str):
            try:
                years = str(season_str).split('/')
                return f"{int(years[0])+1}/{int(years[1])+1}"
            except:
                return None
        
        season_stats['next_season'] = season_stats['season'].apply(next_season)
        
        # Self-join: cada temporada se conecta con sus stats de la siguiente
        next_stats = season_stats[['consolidated_player_id', 'season', 'season_avg_points', 
                                   'season_avg_efficiency', 'season_total_minutes']].copy()
        next_stats.columns = ['consolidated_player_id', 'prev_season', 'next_season_avg_points', 
                             'next_season_avg_efficiency', 'next_season_total_minutes']
        
        # Merge: la temporada N se une con la N+1
        season_stats = season_stats.merge(
            next_stats,
            left_on=['consolidated_player_id', 'next_season'],
            right_on=['consolidated_player_id', 'prev_season'],
            how='inner'
        )
        
        print(f"DEBUG: Después del merge: {len(season_stats)} registros")
        print(f"DEBUG: Columnas después del merge: {season_stats.columns.tolist()}")
        
        # Filtrar solo jugadores que tuvieron actividad suficiente en la siguiente temporada (>=200 min)
        season_stats = season_stats[season_stats['next_season_total_minutes'] >= 200].copy()
        
        self.logger.info(f"Temporadas con siguiente temporada disponible: {len(season_stats)}")
        self.logger.info(f"Jugadores únicos: {season_stats['consolidated_player_id'].nunique()}")
        
        # Merge con el dataframe original (cada partido se etiqueta con el promedio de la SIGUIENTE temporada)
        df = df.merge(
            season_stats[['consolidated_player_id', 'season', 'next_season_avg_points', 'next_season_avg_efficiency']],
            on=['consolidated_player_id', 'season'],
            how='inner'
        )
        
        return df
    
    # =========================================================================
    # ENTRENAMIENTO DE MODELOS
    # =========================================================================
    
    def train_model(self, X: pd.DataFrame, y: pd.Series, 
                   model_name: str = "points_predictor",
                   params: Optional[Dict] = None) -> Dict:
        """
        Entrenar modelo XGBoost.
        
        Args:
            X: Features
            y: Target
            model_name: Nombre del modelo
            params: Hiperparámetros de XGBoost (opcional)
            
        Returns:
            Diccionario con métricas y modelo
        """
        self.logger.info(f"Entrenando modelo: {model_name}")
        self.logger.info(f"Features: {X.shape[1]}, Samples: {len(X)}")
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Parámetros por defecto de XGBoost
        if params is None:
            params = {
                'objective': 'reg:squarederror',
                'max_depth': 6,
                'learning_rate': 0.1,
                'n_estimators': 200,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42,
                'n_jobs': -1
            }
        
        # Entrenar modelo
        self.logger.info("Entrenando XGBoost...")
        model = xgb.XGBRegressor(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        
        # Predicciones
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)
        
        # Métricas
        metrics = {
            'train': {
                'mse': mean_squared_error(y_train, y_pred_train),
                'mae': mean_absolute_error(y_train, y_pred_train),
                'r2': r2_score(y_train, y_pred_train),
                'rmse': np.sqrt(mean_squared_error(y_train, y_pred_train))
            },
            'test': {
                'mse': mean_squared_error(y_test, y_pred_test),
                'mae': mean_absolute_error(y_test, y_pred_test),
                'r2': r2_score(y_test, y_pred_test),
                'rmse': np.sqrt(mean_squared_error(y_test, y_pred_test))
            }
        }
        
        self.logger.info(f"✓ Modelo entrenado")
        self.logger.info(f"  Test RMSE: {metrics['test']['rmse']:.2f}")
        self.logger.info(f"  Test R²: {metrics['test']['r2']:.3f}")
        
        # Guardar modelo
        self.models[model_name] = model
        
        # Crear SHAP explainer
        self.logger.info("Creando SHAP explainer...")
        explainer = shap.TreeExplainer(model)
        self.explainers[model_name] = explainer
        
        return {
            'model': model,
            'metrics': metrics,
            'explainer': explainer,
            'X_test': X_test,
            'y_test': y_test,
            'y_pred': y_pred_test
        }
    
    def train_all_models(self, min_games: int = 5):
        """
        Entrenar modelos para diferentes targets.
        
        Args:
            min_games: Mínimo de partidos para incluir jugadores
        """
        self.logger.info("="*70)
        self.logger.info("ENTRENAMIENTO DE MODELOS XGBOOST")
        self.logger.info("="*70)
        
        targets = {
            'points_predictor': 'next_season_avg_points',
            'efficiency_predictor': 'next_season_avg_efficiency'
        }
        
        results = {}
        
        for model_name, target in targets.items():
            self.logger.info(f"\n--- {model_name} ---")
            
            # Preparar datos
            X, y = self.prepare_training_data(target=target, min_games=min_games)
            
            # Entrenar
            result = self.train_model(X, y, model_name=model_name)
            results[model_name] = result
            
            # Guardar modelo
            self.save_model(model_name)
        
        self.logger.info("\n" + "="*70)
        self.logger.info("ENTRENAMIENTO COMPLETADO")
        self.logger.info("="*70)
        
        return results
    
    # =========================================================================
    # INTERPRETABILIDAD CON SHAP
    # =========================================================================
    
    def explain_model(self, model_name: str, num_samples: int = 100):
        """
        Generar explicaciones SHAP para un modelo.
        
        Args:
            model_name: Nombre del modelo
            num_samples: Número de muestras para SHAP
            
        Returns:
            Valores SHAP
        """
        if model_name not in self.explainers:
            self.logger.error(f"Modelo {model_name} no encontrado")
            return None
        
        self.logger.info(f"Generando explicaciones SHAP para {model_name}...")
        
        # Obtener datos de test
        X, y = self.prepare_training_data(target=self.target_name)
        X_sample = X.sample(min(num_samples, len(X)), random_state=42)
        
        # Calcular SHAP values
        explainer = self.explainers[model_name]
        shap_values = explainer.shap_values(X_sample)
        
        return shap_values, X_sample
    
    def plot_shap_summary(self, model_name: str, num_samples: int = 100,
                         save_path: Optional[str] = None):
        """
        Crear gráfico resumen de SHAP.
        
        Args:
            model_name: Nombre del modelo
            num_samples: Número de muestras
            save_path: Ruta para guardar imagen
        """
        shap_values, X_sample = self.explain_model(model_name, num_samples)
        
        if shap_values is None:
            return
        
        plt.figure(figsize=(10, 8))
        shap.summary_plot(shap_values, X_sample, show=False)
        
        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
            self.logger.info(f"✓ Gráfico SHAP guardado: {save_path}")
        else:
            plt.show()
        
        plt.close()
    
    def get_feature_importance(self, model_name: str) -> pd.DataFrame:
        """
        Obtener importancia de características.
        
        Args:
            model_name: Nombre del modelo
            
        Returns:
            DataFrame con importancia de features
        """
        if model_name not in self.models:
            self.logger.error(f"Modelo {model_name} no encontrado")
            return pd.DataFrame()
        
        model = self.models[model_name]
        
        # Importancia de XGBoost
        importance = model.feature_importances_
        
        # Importancia SHAP (promedio de valores absolutos)
        shap_values, X_sample = self.explain_model(model_name, num_samples=200)
        shap_importance = np.abs(shap_values).mean(axis=0)
        
        df = pd.DataFrame({
            'feature': self.feature_names,
            'xgboost_importance': importance,
            'shap_importance': shap_importance
        })
        
        df = df.sort_values('shap_importance', ascending=False)
        
        return df
    
    # =========================================================================
    # PREDICCIÓN
    # =========================================================================
    
    def predict_player_performance(self, player_id: int, 
                                   model_name: str = "points_predictor") -> Dict:
        """
        Predecir rendimiento futuro de un jugador.
        
        Args:
            player_id: ID del jugador
            model_name: Nombre del modelo a usar
            
        Returns:
            Diccionario con predicciones y explicaciones
        """
        if model_name not in self.models:
            self.logger.error(f"Modelo {model_name} no encontrado")
            return {}
        
        conn = self.get_connection()
        
        # Obtener últimas features del jugador
        query = """
        SELECT * FROM ml_features_view
        WHERE player_id = ?
        ORDER BY game_date DESC
        LIMIT 1
        """
        
        df = pd.read_sql_query(query, conn, params=(player_id,))
        conn.close()
        
        if df.empty:
            self.logger.warning(f"No se encontraron datos para jugador {player_id}")
            return {}
        
        # Preparar features
        # Solo usar features que existen tanto en df como en el modelo
        feature_cols = [col for col in self.feature_names if col in df.columns]
        X = df[feature_cols].copy()
        
        # Encoding categórico (simplificado)
        categorical_cols = ['position', 'gender', 'level']
        for col in categorical_cols:
            if col in X.columns:
                X[col] = X[col].fillna('unknown')
                # Usar un encoding simple numérico
                X[col] = pd.Categorical(X[col]).codes
        
        X = X.fillna(0).infer_objects(copy=False)
        
        # Predicción
        model = self.models[model_name]
        prediction = model.predict(X)[0]
        
        # Explicación SHAP
        explainer = self.explainers[model_name]
        shap_values = explainer.shap_values(X)
        
        # Top features que influyen en la predicción
        shap_abs = np.abs(shap_values[0])
        top_indices = np.argsort(shap_abs)[-5:][::-1]
        
        top_features = []
        for idx in top_indices:
            top_features.append({
                'feature': self.feature_names[idx],
                'value': float(X.iloc[0, idx]),
                'shap_value': float(shap_values[0][idx]),
                'impact': 'positive' if shap_values[0][idx] > 0 else 'negative'
            })
        
        return {
            'player_id': player_id,
            'player_name': df['player_name'].iloc[0],
            'prediction': float(prediction),
            'target': self.target_name,
            'top_features': top_features,
            'current_avg': float(df['avg_points'].iloc[0]) if 'avg_points' in df.columns else None
        }
    
    # =========================================================================
    # PERSISTENCIA
    # =========================================================================
    
    def save_model(self, model_name: str):
        """
        Guardar modelo entrenado.
        
        Args:
            model_name: Nombre del modelo
        """
        if model_name not in self.models:
            self.logger.error(f"Modelo {model_name} no encontrado")
            return
        
        model_path = self.model_dir / f"{model_name}.joblib"
        metadata_path = self.model_dir / f"{model_name}_metadata.json"
        
        # Guardar modelo
        joblib.dump(self.models[model_name], model_path)
        
        # Guardar metadata
        metadata = {
            'model_name': model_name,
            'target': self.target_name,
            'feature_names': self.feature_names,
            'trained_at': datetime.now().isoformat()
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"✓ Modelo guardado: {model_path}")
    
    def load_model(self, model_name: str):
        """
        Cargar modelo guardado.
        
        Args:
            model_name: Nombre del modelo
        """
        model_path = self.model_dir / f"{model_name}.joblib"
        metadata_path = self.model_dir / f"{model_name}_metadata.json"
        
        if not model_path.exists():
            self.logger.error(f"Modelo no encontrado: {model_path}")
            return
        
        # Cargar modelo
        self.models[model_name] = joblib.load(model_path)
        
        # Cargar metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        self.feature_names = metadata['feature_names']
        self.target_name = metadata['target']
        
        # Crear explainer
        self.explainers[model_name] = shap.TreeExplainer(self.models[model_name])
        
        self.logger.info(f"✓ Modelo cargado: {model_name}")


def main():
    """Ejemplo de uso."""
    logging.basicConfig(level=logging.INFO)
    
    # Crear y entrenar modelos
    model = PlayerPerformanceModel()
    results = model.train_all_models(min_games=5)
    
    # Mostrar resumen de resultados
    print("\n" + "="*70)
    print("RESULTADOS DEL ENTRENAMIENTO")
    print("="*70 + "\n")
    
    for model_name, result in results.items():
        metrics = result['metrics']
        print(f"{model_name.upper().replace('_', ' ')}")
        print(f"  Train RMSE: {metrics['train']['rmse']:.2f}")
        print(f"  Train R²:   {metrics['train']['r2']:.3f}")
        print(f"  Test RMSE:  {metrics['test']['rmse']:.2f}")
        print(f"  Test R²:    {metrics['test']['r2']:.3f}")
        print(f"  Test MAE:   {metrics['test']['mae']:.2f}")
        print()
    
    # Ver importancia de características
    for model_name in results.keys():
        print(f"\n=== Importancia de características: {model_name} ===")
        importance_df = model.get_feature_importance(model_name)
        print(importance_df.head(10))
        
        # Guardar gráfico SHAP
        model.plot_shap_summary(
            model_name,
            save_path=f"models/{model_name}_shap_summary.png"
        )


if __name__ == "__main__":
    main()
