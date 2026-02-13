"""
Script para evaluar equipos y proyectar rendimiento de jugadoras a próxima temporada.

PREDICCIONES:
- →PTS: Proyección de puntos promedio por partido en la temporada 2026/2027
- →EFF: Proyección de valoración promedio por partido en la temporada 2026/2027
- Basado en modelos XGBoost entrenados con datos históricos 2001-2024

POTENCIAL (POT):
- ELI (Elite): Top 0.3% - Futuras estrellas absolutas
- VER (Very High): Top 1.2% - Potencial muy alto
- HIG (High): Top 4.5% - Alto potencial de crecimiento  
- MED (Medium): Top 8% - Potencial medio-alto
- LOW (Low): Resto - Desarrollo estándar

Uso:
    python evaluate_team.py
    python evaluate_team.py --team "CAMPUS PROMETE"
    python evaluate_team.py --competition "LF1 FEMENINA"
"""

import sqlite3
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional
import joblib
import pandas as pd
import numpy as np

# Ajustar path para imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ml.xgboost_model import PlayerPerformanceModel


def train_models_if_needed(db_path: str = "scouting_feb.db", model_dir: str = "models") -> bool:
    """
    Entrenar modelos automáticamente si no existen o fallan.
    
    Returns:
        True si los modelos están listos, False si falló
    """
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    import json
    
    try:
        import xgboost as xgb
    except ImportError:
        print("⚠ Error: XGBoost no está instalado. Ejecuta: pip install xgboost scikit-learn")
        return False
    
    model_dir_path = Path(model_dir)
    points_model = model_dir_path / "points_predictor.joblib"
    eff_model = model_dir_path / "efficiency_predictor.joblib"
    
    # Verificar si modelos existen
    if points_model.exists() and eff_model.exists():
        return True
    
    print("\n" + "="*70)
    print("⚠ MODELOS ML NO ENCONTRADOS")
    print("="*70)
    print("Los modelos de predicción no existen. Se entrenarán automáticamente.")
    print("Esto puede tardar 1-2 minutos...")
    
    response = input("\n¿Continuar con el entrenamiento? [S/n]: ").strip().lower()
    if response and response not in ['s', 'si', 'sí', 'y', 'yes']:
        print("❌ Entrenamiento cancelado. No habrá proyecciones disponibles.")
        return False
    
    print("\n" + "="*70)
    print("ENTRENAMIENTO AUTOMÁTICO DE MODELOS")
    print("="*70)
    
    # Función de entrenamiento
    def get_training_data(target_col, min_games=5):
        conn = sqlite3.connect(db_path)
        query = f"""
        WITH player_season_stats AS (
            SELECT 
                player_name, season,
                AVG(points) as avg_points,
                AVG(efficiency_rating) as avg_efficiency,
                COUNT(*) as games_played
            FROM ml_features_view
            WHERE season != '2025/2026'
            GROUP BY player_name, season
            HAVING COUNT(*) >= {min_games}
        ),
        next_season_targets AS (
            SELECT 
                curr.player_name, curr.season,
                next.avg_points as next_season_points,
                next.avg_efficiency as next_season_efficiency
            FROM player_season_stats curr
            JOIN player_season_stats next ON 
                curr.player_name = next.player_name AND
                CAST(SUBSTR(next.season, 1, 4) AS INTEGER) = CAST(SUBSTR(curr.season, 1, 4) AS INTEGER) + 1
        )
        SELECT f.*, nst.next_season_points, nst.next_season_efficiency
        FROM ml_features_view f
        JOIN next_season_targets nst ON 
            f.player_name = nst.player_name AND f.season = nst.season
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            raise ValueError("No se obtuvieron datos de entrenamiento")
        
        exclude_cols = [
            'stat_id', 'game_id', 'player_id', 'player_name', 'game_date',
            'season', 'position', 'height_cm', 'birth_year', 'years_experience',
            'next_season_points', 'next_season_efficiency', 'opponent_team_id', 'team_id',
            'competition_id', 'competition_name', 'gender', 'level', 'competition_level',
            'performance_tier'
        ]
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        X = df[feature_cols].copy().fillna(0)
        
        bool_cols = X.select_dtypes(include=['bool']).columns
        X[bool_cols] = X[bool_cols].astype(int)
        
        object_cols = X.select_dtypes(include=['object']).columns.tolist()
        if object_cols:
            X = X.drop(columns=object_cols)
            feature_cols = [f for f in feature_cols if f not in object_cols]
        
        y = df['next_season_points' if 'points' in target_col else 'next_season_efficiency'].copy()
        return X, y, feature_cols
    
    def train_model(X, y, feature_names, model_name):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        model = xgb.XGBRegressor(
            objective='reg:squarederror', max_depth=6, learning_rate=0.1,
            n_estimators=200, subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=-1
        )
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        
        test_pred = model.predict(X_test)
        metrics = {
            'test': {
                'rmse': float(np.sqrt(mean_squared_error(y_test, test_pred))),
                'r2': float(r2_score(y_test, test_pred))
            }
        }
        
        model_dir_path.mkdir(exist_ok=True)
        joblib.dump(model, model_dir_path / f"{model_name}.joblib")
        
        with open(model_dir_path / f"{model_name}_metadata.json", 'w') as f:
            json.dump({
                'feature_names': feature_names,
                'target': target_col,
                'metrics': metrics
            }, f, indent=2)
        
        return metrics
    
    try:
        # Entrenar puntos
        print("\n[1/2] Entrenando modelo de puntos...")
        X_pts, y_pts, features_pts = get_training_data("next_season_points")
        metrics_pts = train_model(X_pts, y_pts, features_pts, "points_predictor")
        print(f"✓ Points predictor: R²={metrics_pts['test']['r2']:.3f}")
        
        # Entrenar eficiencia
        print("\n[2/2] Entrenando modelo de eficiencia...")
        X_eff, y_eff, features_eff = get_training_data("next_season_efficiency")
        metrics_eff = train_model(X_eff, y_eff, features_eff, "efficiency_predictor")
        print(f"✓ Efficiency predictor: R²={metrics_eff['test']['r2']:.3f}")
        
        print("\n" + "="*70)
        print("✓ MODELOS ENTRENADOS EXITOSAMENTE")
        print("="*70 + "\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante el entrenamiento: {e}")
        return False


class TeamEvaluator:
    """Evaluador de equipos con proyecciones ML."""
    
    def __init__(self, db_path: str = "scouting_feb.db"):
        """
        Inicializar evaluador.
        
        Args:
            db_path: Ruta a la base de datos SQLite
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.model = None
        
        # Intentar entrenar modelos automáticamente si no existen
        models_ready = train_models_if_needed(db_path)
        
        if not models_ready:
            print("⚠ Continuando sin modelos ML. No habrá proyecciones disponibles.")
            return
        
        # Intentar cargar modelos
        try:
            self.model = PlayerPerformanceModel(db_path=db_path)
            self.model.load_model("points_predictor")
            self.model.load_model("efficiency_predictor")
            print("✓ Modelos ML cargados exitosamente")
        except Exception as e:
            print(f"⚠ Error al cargar modelos: {e}")
            print("  Las proyecciones no estarán disponibles.")
            self.model = None
    
    def list_competitions(self) -> List[tuple]:
        """Listar competiciones disponibles en temporada actual."""
        cursor = self.conn.cursor()
        
        query = """
        SELECT DISTINCT c.competition_id, c.competition_name, c.level, COUNT(DISTINCT t.team_id) as teams
        FROM competitions c
        JOIN games g ON c.competition_id = g.competition_id
        JOIN teams t ON g.home_team_id = t.team_id OR g.away_team_id = t.team_id
        WHERE g.season = '2025/2026'
        GROUP BY c.competition_id
        ORDER BY c.level DESC, teams DESC
        """
        
        cursor.execute(query)
        return cursor.fetchall()
    
    def list_teams(self, competition_id: Optional[int] = None, 
                   competition_name: Optional[str] = None) -> List[tuple]:
        """
        Listar equipos disponibles.
        
        Args:
            competition_id: Filtrar por ID de competición
            competition_name: Filtrar por nombre de competición (búsqueda parcial)
            
        Returns:
            Lista de (team_id, team_name, competition_name, players)
        """
        cursor = self.conn.cursor()
        
        query = """
        SELECT DISTINCT 
            t.team_id,
            t.team_name,
            c.competition_name,
            COUNT(DISTINCT pp.profile_id) as players
        FROM teams t
        JOIN games g ON t.team_id = g.home_team_id OR t.team_id = g.away_team_id
        JOIN competitions c ON g.competition_id = c.competition_id
        JOIN player_game_stats pgs ON g.game_id = pgs.game_id
        JOIN player_profiles pp ON pgs.player_id = pp.profile_id
        WHERE g.season = '2025/2026'
          AND pp.season = '2025/2026'
          AND (t.team_id = pgs.team_id OR EXISTS (
              SELECT 1 FROM player_profiles pp2 
              WHERE pp2.profile_id = pp.profile_id AND pp2.team_id = t.team_id
          ))
        """
        
        params = []
        if competition_id:
            query += " AND c.competition_id = ?"
            params.append(competition_id)
        elif competition_name:
            query += " AND c.competition_name LIKE ?"
            params.append(f"%{competition_name}%")
        
        query += """
        GROUP BY t.team_id
        HAVING players >= 5
        ORDER BY competition_name, team_name
        """
        
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def get_team_roster(self, team_id: int, season: str = "2025/2026") -> List[Dict]:
        """
        Obtener roster actual de un equipo con estadísticas.
        
        Args:
            team_id: ID del equipo
            season: Temporada (default: 2025/2026)
            
        Returns:
            Lista de diccionarios con datos de jugadoras
        """
        cursor = self.conn.cursor()
        
        query = """
        SELECT 
            pp.profile_id,
            pp.consolidated_player_id,
            pp.name_normalized,
            pp.birth_year,
            CASE WHEN pp.birth_year IS NOT NULL THEN 2026 - pp.birth_year ELSE NULL END as age,
            COUNT(DISTINCT pgs.game_id) as games_played,
            AVG(pgs.minutes_played) as avg_minutes,
            AVG(pgs.points) as avg_points,
            AVG(pgs.efficiency_rating) as avg_efficiency,
            AVG(pgs.total_rebounds) as avg_rebounds,
            AVG(pgs.assists) as avg_assists,
            ppm.pts_per_36,
            ppm.last_10_games_pts,
            ppm.momentum_index,
            ppm.cv_points,
            ppm.player_pts_share,
            pcp.unified_potential_score,
            pcp.potential_tier
        FROM player_profiles pp
        JOIN player_game_stats pgs ON pp.profile_id = pgs.player_id
        LEFT JOIN player_profile_metrics ppm ON pp.profile_id = ppm.profile_id
        LEFT JOIN player_career_potential pcp ON pp.name_normalized = pcp.player_name
        WHERE pp.team_id = ?
          AND pp.season = ?
          AND pgs.team_id = ?
        GROUP BY pp.profile_id
        HAVING games_played >= 3
        ORDER BY avg_points DESC
        """
        
        cursor.execute(query, (team_id, season, team_id))
        rows = cursor.fetchall()
        
        roster = []
        for row in rows:
            player = {
                'profile_id': row[0],
                'consolidated_id': row[1],
                'name': row[2],
                'birth_year': row[3],
                'age': row[4],
                'games_played': row[5],
                'avg_minutes': row[6] or 0,
                'avg_points': row[7] or 0,
                'avg_efficiency': row[8] or 0,
                'avg_rebounds': row[9] or 0,
                'avg_assists': row[10] or 0,
                'pts_per_36': row[11],
                'last_10_games_pts': row[12],
                'momentum_index': row[13],
                'cv_points': row[14],
                'player_pts_share': row[15],
                'potential_score': row[16],
                'potential_category': row[17]
            }
            
            # Predecir próxima temporada si hay modelos
            if self.model and self.model.models:
                try:
                    # Predecir puntos
                    pred_points = self._predict_next_season(player['profile_id'], 'points_predictor')
                    player['predicted_points'] = pred_points
                    
                    # Predecir eficiencia
                    pred_efficiency = self._predict_next_season(player['profile_id'], 'efficiency_predictor')
                    player['predicted_efficiency'] = pred_efficiency
                except Exception as e:
                    # Debug: mostrar primer error
                    if not hasattr(self, '_prediction_error_shown'):
                        print(f"\n⚠ Error en predicción (jugadora {player['name']}): {str(e)[:100]}")
                        self._prediction_error_shown = True
                    player['predicted_points'] = None
                    player['predicted_efficiency'] = None
            else:
                player['predicted_points'] = None
                player['predicted_efficiency'] = None
            
            roster.append(player)
        
        return roster
    
    def _predict_next_season(self, profile_id: int, model_name: str) -> Optional[float]:
        """
        Predecir rendimiento de próxima temporada para un profile.
        
        Args:
            profile_id: ID del perfil de jugadora
            model_name: Nombre del modelo ('points_predictor' o 'efficiency_predictor')
            
        Returns:
            Predicción o None si falla
        """
        try:
            result = self.model.predict_player_performance(profile_id, model_name)
            # Debug: mostrar qué está retornando
            if not hasattr(self, '_prediction_debug_shown'):
                if not result:
                    print(f"\n⚠ Debug: predict_player_performance retornó vacío para profile_id {profile_id}")
                elif 'prediction' not in result:
                    print(f"\n⚠ Debug: result no tiene 'prediction'. Keys: {list(result.keys())}")
                else:
                    print(f"\n✓ Debug: Predicción exitosa. Prediction: {result['prediction']}")
                self._prediction_debug_shown = True
            
            if result and 'prediction' in result:
                return result['prediction']
        except Exception as e:
            if not hasattr(self, '_prediction_exception_shown'):
                print(f"\n⚠ Debug: Excepción en _predict_next_season: {str(e)[:150]}")
                self._prediction_exception_shown = True
        return None
    
    def print_team_evaluation(self, team_id: int, team_name: str):
        """Imprimir evaluación completa del equipo."""
        print("\n" + "="*100)
        print(f"EVALUACIÓN DE EQUIPO: {team_name}")
        print("="*100)
        
        roster = self.get_team_roster(team_id)
        
        if not roster:
            print("⚠ No se encontraron jugadoras para este equipo en la temporada actual")
            return
        
        print(f"\nPlantilla actual: {len(roster)} jugadoras (≥3 partidos)")
        print("\n" + "-"*100)
        
        # Tabla de roster
        header = f"{'JUGADORA':<30} {'Edad':>4} {'PJ':>3} {'MIN':>5} {'PTS':>5} {'EFF':>5} {'→PTS':>6} {'→EFF':>6} {'POT':>6}"
        print(header)
        print("-"*100)
        print("Leyenda: →PTS/→EFF = Proyección promedio próxima temporada | POT: ELI(Elite) VER(Very High) HIG(High) MED(Medium) LOW(Low)")
        print("         ⚠ = Predicción conservadora (modelo ML vs. potencial alto - puede subestimar jugadoras en ascenso)")
        print("-"*100)
        
        total_predicted_points = 0
        total_predicted_efficiency = 0
        players_with_predictions = 0
        
        for player in roster:
            name = player['name'][:28] if len(player['name']) > 28 else player['name']
            age = player['age'] if player['age'] is not None else 'N/D'
            games = player['games_played']
            minutes = player['avg_minutes']
            points = player['avg_points']
            efficiency = player['avg_efficiency']
            
            # Potencial (definir primero para usarlo después)
            pot_score = player['potential_score']
            pot_cat = player['potential_category']
            
            # Proyecciones
            pred_pts = player['predicted_points']
            pred_eff = player['predicted_efficiency']
            
            # Detectar inconsistencias: alto potencial pero predicción a la baja
            is_high_potential = pot_cat and pot_cat.lower() in ['elite', 'very_high', 'high']
            predicts_decline = (pred_pts is not None and pred_pts < points * 0.9) or \
                               (pred_eff is not None and pred_eff < efficiency * 0.9)
            
            if pred_pts is not None:
                # Añadir indicador si hay potencial alto pero predicción conservadora
                if is_high_potential and pred_pts < points:
                    pred_pts_str = f"{pred_pts:>5.1f}⚠"  # Alerta: modelo conservador
                else:
                    pred_pts_str = f"{pred_pts:>6.1f}"
                total_predicted_points += pred_pts
                players_with_predictions += 1
            else:
                pred_pts_str = f"{'--':>6}"
            
            if pred_eff is not None:
                if is_high_potential and pred_eff < efficiency:
                    pred_eff_str = f"{pred_eff:>5.1f}⚠"
                else:
                    pred_eff_str = f"{pred_eff:>6.1f}"
                total_predicted_efficiency += pred_eff
            else:
                pred_eff_str = f"{'--':>6}"
            
            # Formatear potencial
            if pot_score and pot_cat:
                # Mapear categorías de potencial a abreviaturas
                pot_lower = pot_cat.lower()
                if 'elite' in pot_lower:
                    pot_str = "ELI"  # Elite (top 0.3%)
                elif 'very_high' in pot_lower or 'very high' in pot_lower:
                    pot_str = "VER"  # Very High (top 1.2%)
                elif 'high' in pot_lower:
                    pot_str = "HIG"  # High (top 4.5%)
                elif 'medium' in pot_lower or 'medio' in pot_lower:
                    pot_str = "MED"  # Medium (top 8%)
                elif 'low' in pot_lower or 'bajo' in pot_lower:
                    pot_str = "LOW"  # Low
                else:
                    pot_str = pot_cat[:3].upper()
            else:
                pot_str = "---"
            
            print(f"{name:<30} {age:>4} {games:>3} {minutes:>5.1f} {points:>5.1f} {efficiency:>5.1f} {pred_pts_str} {pred_eff_str} {pot_str:>6}")
        
        # Resumen
        print("-"*100)
        if players_with_predictions > 0:
            avg_pred_pts = total_predicted_points / players_with_predictions
            avg_pred_eff = total_predicted_efficiency / players_with_predictions
            
            print(f"\n📊 PROYECCIÓN EQUIPO 2026/2027:")
            print(f"  • Promedio puntos proyectado: {avg_pred_pts:.1f} pts/jugadora")
            print(f"  • Promedio eficiencia proyectado: {avg_pred_eff:.1f} OER/jugadora")
            print(f"  • Jugadoras con proyección válida: {players_with_predictions}/{len(roster)}")
            
            # Categorías de potencial
            def is_elite(cat):
                return cat and 'elite' in cat.lower()
            
            def is_very_high(cat):
                return cat and 'very_high' in cat.lower()
            
            def is_high(cat):
                return cat and ('high' in cat.lower() and 'very' not in cat.lower())
            
            def is_medium(cat):
                return cat and ('medium' in cat.lower() or 'medio' in cat.lower())
            
            elite = sum(1 for p in roster if is_elite(p.get('potential_category')))
            very_high = sum(1 for p in roster if is_very_high(p.get('potential_category')))
            high = sum(1 for p in roster if is_high(p.get('potential_category')))
            medium = sum(1 for p in roster if is_medium(p.get('potential_category')))
            
            if elite + very_high + high + medium > 0:
                print(f"\n🌟 DISTRIBUCIÓN DE POTENCIAL:")
                if elite > 0:
                    print(f"  • Elite (ELI): {elite} jugadoras")
                if very_high > 0:
                    print(f"  • Very High (VER): {very_high} jugadoras")
                if high > 0:
                    print(f"  • High (HIG): {high} jugadoras")
                if medium > 0:
                    print(f"  • Medium (MED): {medium} jugadoras")
        else:
            print("\n⚠ No hay proyecciones disponibles")
            print("  Los modelos ML no están cargados. El entrenamiento automático falló o fue cancelado.")
        
        print("\n" + "="*100)
    
    def interactive_mode(self):
        """Modo interactivo para seleccionar equipo."""
        print("""
╔════════════════════════════════════════════════════════════════════╗
║            ScoutingFEB - Evaluación de Equipos                     ║
║         Proyección de Rendimiento a Próxima Temporada              ║
╚════════════════════════════════════════════════════════════════════╝
        """)
        
        # Listar competiciones
        competitions = self.list_competitions()
        
        if not competitions:
            print("✗ No hay competiciones en la temporada 2025/2026")
            return
        
        print("\nCOMPETICIONES DISPONIBLES:")
        print("-" * 70)
        print(f"{'#':<4} {'NOMBRE':<40} {'NIVEL':<10} {'EQUIPOS':>8}")
        print("-" * 70)
        
        for i, (comp_id, name, level, teams) in enumerate(competitions, 1):
            print(f"{i:<4} {name[:38]:<40} {level or 'N/A':<10} {teams:>8}")
        
        print(f"{0:<4} {'TODOS LOS EQUIPOS':<40} {'':<10} {'':<8}")
        print("-" * 70)
        
        # Seleccionar competición
        try:
            choice = input("\nSelecciona competición (número, 0 para todos): ").strip()
            choice_num = int(choice)
            
            if choice_num < 0 or choice_num > len(competitions):
                print("✗ Selección inválida")
                return
            
            comp_filter = competitions[choice_num - 1][0] if choice_num > 0 else None
        except (ValueError, IndexError):
            print("✗ Entrada inválida")
            return
        
        # Listar equipos
        teams = self.list_teams(competition_id=comp_filter)
        
        if not teams:
            print("✗ No hay equipos disponibles")
            return
        
        print(f"\nEQUIPOS DISPONIBLES ({len(teams)}):")
        print("-" * 90)
        print(f"{'#':<4} {'NOMBRE':<40} {'COMPETICIÓN':<30} {'JUGADORAS':>10}")
        print("-" * 90)
        
        for i, (team_id, team_name, comp_name, players) in enumerate(teams, 1):
            print(f"{i:<4} {team_name[:38]:<40} {comp_name[:28]:<30} {players:>10}")
        
        print("-" * 90)
        
        # Seleccionar equipo
        try:
            choice = input(f"\nSelecciona equipo (1-{len(teams)}): ").strip()
            choice_num = int(choice)
            
            if choice_num < 1 or choice_num > len(teams):
                print("✗ Selección inválida")
                return
            
            team_id, team_name, comp_name, _ = teams[choice_num - 1]
        except (ValueError, IndexError):
            print("✗ Entrada inválida")
            return
        
        # Evaluar equipo
        self.print_team_evaluation(team_id, team_name)
    
    def close(self):
        """Cerrar conexión a base de datos."""
        if self.conn:
            self.conn.close()


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Evaluar equipos y proyectar rendimiento a próxima temporada"
    )
    parser.add_argument('--team', type=str, help='Nombre del equipo (búsqueda parcial)')
    parser.add_argument('--competition', type=str, help='Nombre de competición (búsqueda parcial)')
    parser.add_argument('--db', default='scouting_feb.db', help='Ruta a base de datos')
    
    args = parser.parse_args()
    
    evaluator = TeamEvaluator(db_path=args.db)
    
    try:
        if args.team:
            # Buscar equipo por nombre
            teams = evaluator.list_teams()
            matching_teams = [t for t in teams if args.team.upper() in t[1].upper()]
            
            if not matching_teams:
                print(f"✗ No se encontró equipo con '{args.team}'")
                return
            
            if len(matching_teams) > 1:
                print(f"⚠ Se encontraron {len(matching_teams)} equipos:")
                for t in matching_teams:
                    print(f"  - {t[1]} ({t[2]})")
                print("\nEspecifica más el nombre o usa modo interactivo")
                return
            
            team_id, team_name, _, _ = matching_teams[0]
            evaluator.print_team_evaluation(team_id, team_name)
        else:
            # Modo interactivo
            evaluator.interactive_mode()
    
    finally:
        evaluator.close()


if __name__ == "__main__":
    main()
