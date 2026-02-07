"""
Script completo de ejemplo: Pipeline ETL + ML con XGBoost + SHAP

Este script demuestra el flujo completo desde datos raw en MongoDB
hasta predicciones interpretables con SHAP.
"""

import sys
import os
import logging
from pathlib import Path

# Añadir ruta del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.etl_processor import FEBDataETL
from ml.xgboost_model import PlayerPerformanceModel
from database.sqlite_schema import SQLiteSchemaManager


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def paso_1_crear_esquema():
    """Paso 1: Crear esquema de base de datos SQLite."""
    print("\n" + "="*70)
    print("PASO 1: CREACIÓN DE ESQUEMA SQLITE")
    print("="*70)
    
    # Ruta relativa desde src/ hacia raíz del proyecto
    db_path = os.path.join(os.path.dirname(__file__), '..', 'scouting_feb.db')
    schema_manager = SQLiteSchemaManager(db_path)
    success = schema_manager.create_database()
    
    if success:
        print("✓ Esquema creado exitosamente")
        schema_manager.print_schema_summary()
    else:
        print("✗ Error creando esquema")
        return False
    
    return True


def paso_2_ejecutar_etl(limit=None, use_profiles=True, generate_candidates=True, 
                        candidate_threshold=0.50, consolidate_identities=True):
    """Paso 2: Ejecutar proceso ETL de MongoDB a SQLite."""
    print("\n" + "="*70)
    print("PASO 2: PROCESO ETL (MongoDB → SQLite)")
    print("="*70)
    print(f"Modo: {'PERFILES' if use_profiles else 'JUGADORES ÚNICOS'}")
    if use_profiles:
        print(f"Generación de candidatos: {'Sí' if generate_candidates else 'No'}")
        if generate_candidates:
            print(f"Threshold de candidatos: {candidate_threshold}")
        print(f"Consolidación de identidades: {'Sí' if consolidate_identities else 'No'}")
    
    try:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'scouting_feb.db')
        etl = FEBDataETL(
            mongodb_uri="mongodb://localhost:27017/",
            mongodb_db="scouting_feb",
            sqlite_path=db_path,
            use_profiles=use_profiles
        )
        
        # Ejecutar ETL completo
        etl.run_full_etl(
            limit=limit,
            generate_candidates=generate_candidates,
            candidate_min_score=candidate_threshold
        )
        
        # Consolidar identidades si está habilitado
        if consolidate_identities and use_profiles:
            print("\n" + "="*70)
            print("CONSOLIDACIÓN DE IDENTIDADES")
            print("="*70)
            
            from ml.consolidate_identities import consolidate_identities as consolidate_func
            consolidate_func(db_path, min_score=0.95)
        
        print("\n✓ ETL completado exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"Error en ETL: {e}", exc_info=True)
        return False


def paso_3_entrenar_modelos():
    """Paso 3: Entrenar modelos de Machine Learning."""
    print("\n" + "="*70)
    print("PASO 3: ENTRENAMIENTO DE MODELOS XGBOOST")
    print("="*70)
    
    try:
        # Crear directorio para modelos
        Path("models").mkdir(exist_ok=True)
        
        db_path = os.path.join(os.path.dirname(__file__), '..', 'scouting_feb.db')
        model = PlayerPerformanceModel(
            db_path=db_path,
            model_dir="models"
        )
        
        # Entrenar todos los modelos
        results = model.train_all_models(min_games=5)
        
        print("\n" + "-"*70)
        print("RESULTADOS DEL ENTRENAMIENTO")
        print("-"*70)
        
        for model_name, result in results.items():
            metrics = result['metrics']
            print(f"\n{model_name.upper()}")
            print(f"  Train RMSE: {metrics['train']['rmse']:.2f}")
            print(f"  Train R²:   {metrics['train']['r2']:.3f}")
            print(f"  Test RMSE:  {metrics['test']['rmse']:.2f}")
            print(f"  Test R²:    {metrics['test']['r2']:.3f}")
            print(f"  Test MAE:   {metrics['test']['mae']:.2f}")
        
        return model, results
        
    except Exception as e:
        logger.error(f"Error entrenando modelos: {e}", exc_info=True)
        return None, None


def paso_4_analisis_shap(model):
    """Paso 4: Análisis de interpretabilidad con SHAP."""
    print("\n" + "="*70)
    print("PASO 4: ANÁLISIS DE INTERPRETABILIDAD (SHAP)")
    print("="*70)
    
    try:
        for model_name in model.models.keys():
            print(f"\n--- {model_name} ---")
            
            # Obtener importancia de características
            importance_df = model.get_feature_importance(model_name)
            
            print("\nTop 10 características más importantes (SHAP):")
            print(importance_df[['feature', 'shap_importance']].head(10).to_string(index=False))
            
            # Generar gráfico SHAP
            output_path = f"models/{model_name}_shap_summary.png"
            print(f"\nGenerando gráfico SHAP: {output_path}")
            model.plot_shap_summary(model_name, num_samples=100, save_path=output_path)
            print(f"✓ Gráfico guardado")
        
        return True
        
    except Exception as e:
        logger.error(f"Error en análisis SHAP: {e}", exc_info=True)
        return False


def paso_5_hacer_predicciones(model):
    """Paso 5: Hacer predicciones de ejemplo."""
    print("\n" + "="*70)
    print("PASO 5: PREDICCIONES DE EJEMPLO")
    print("="*70)
    
    try:
        import sqlite3
        
        db_path = os.path.join(os.path.dirname(__file__), '..', 'scouting_feb.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Obtener algunos jugadores de ejemplo (con más partidos)
        # Contar partidos directamente desde player_game_stats
        # Filtrar jugadores sin nombre (datos corruptos en MongoDB)
        cursor.execute("""
            SELECT 
                pgs.player_id,
                COALESCE(pp.name_raw, p.name) as name,
                COUNT(DISTINCT pgs.game_id) as total_games
            FROM player_game_stats pgs
            LEFT JOIN player_profiles pp ON pgs.player_id = pp.profile_id
            LEFT JOIN players p ON pgs.player_id = p.player_id
            WHERE COALESCE(pp.name_raw, p.name, '') != ''
            GROUP BY pgs.player_id
            HAVING COUNT(DISTINCT pgs.game_id) >= 10
            ORDER BY total_games DESC
            LIMIT 5
        """)
        
        players = cursor.fetchall()
        conn.close()
        
        if not players:
            print("⚠ No hay suficientes jugadores con >= 10 partidos para predicciones")
            return True
        
        print(f"\nPredicciones para {len(players)} jugadores:")
        print("-"*70)
        
        for player_id, player_name, total_games in players:
            print(f"\n{player_name} (ID: {player_id}, {total_games} partidos)")
            
            # Predicción de puntos
            pred_points = model.predict_player_performance(
                player_id, 
                model_name="points_predictor"
            )
            
            if pred_points:
                print(f"  📊 Predicción próximo partido: {pred_points['prediction']:.1f} puntos")
                
                if pred_points.get('current_avg'):
                    print(f"  📈 Promedio actual: {pred_points['current_avg']:.1f} puntos")
                
                print(f"  🔍 Factores más influyentes:")
                for i, feature in enumerate(pred_points['top_features'][:3], 1):
                    impact_symbol = "↑" if feature['impact'] == 'positive' else "↓"
                    print(f"     {i}. {feature['feature']}: {feature['value']:.2f} {impact_symbol}")
            else:
                print(f"  ⚠ No se pudo generar predicción")
        
        return True
        
    except Exception as e:
        logger.error(f"Error haciendo predicciones: {e}", exc_info=True)
        return False


def main():
    """Función principal - ejecuta todo el pipeline."""
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║         ScoutingFEB - Pipeline Completo: ETL + ML + SHAP          ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    Este script ejecuta:
    1. Creación del esquema SQLite (con tablas de perfiles)
    2. Proceso ETL (MongoDB → SQLite) con gestión de identidades
    3. Generación de candidatos de matching automático
    4. Entrenamiento de modelos XGBoost
    5. Análisis de interpretabilidad con SHAP
    6. Predicciones de ejemplo
    """)
    
    import argparse
    parser = argparse.ArgumentParser(description='Pipeline completo ETL + ML')
    parser.add_argument('--skip-etl', action='store_true', 
                       help='Saltar ETL (usar datos existentes)')
    parser.add_argument('--etl-only', action='store_true',
                       help='Solo ejecutar ETL (sin entrenamiento ni predicciones)')
    parser.add_argument('--skip-training', action='store_true',
                       help='Saltar entrenamiento (cargar modelos existentes)')
    parser.add_argument('--limit', type=int,
                       help='Limitar partidos en ETL para pruebas rápidas')
    parser.add_argument('--legacy-mode', action='store_true',
                       help='Usar sistema legacy (jugadores únicos) sin perfiles')
    parser.add_argument('--no-candidates', action='store_true',
                       help='No generar candidatos de matching automático')
    parser.add_argument('--candidate-threshold', type=float, default=0.50,
                       help='Score mínimo para generar candidatos (default: 0.50)')
    parser.add_argument('--no-consolidate', action='store_true',
                       help='No consolidar identidades automáticamente después del ETL')
    
    args = parser.parse_args()
    
    # Verificar que existe MongoDB
    if not args.skip_etl:
        from pymongo import MongoClient
        try:
            client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
            client.server_info()
            logger.info("✓ Conexión a MongoDB exitosa")
            client.close()
        except Exception as e:
            logger.error(f"✗ No se puede conectar a MongoDB: {e}")
            logger.error("Por favor, asegúrate de que MongoDB esté ejecutándose")
            logger.error("Puedes usar --skip-etl si ya tienes scouting_feb.db")
            return
    
    # Paso 1: Crear esquema
    if not paso_1_crear_esquema():
        logger.error("✗ Error en Paso 1")
        return
    
    # Paso 2: ETL
    if not args.skip_etl:
        if not paso_2_ejecutar_etl(
            limit=args.limit,
            use_profiles=not args.legacy_mode,
            generate_candidates=not args.no_candidates,
            candidate_threshold=args.candidate_threshold,
            consolidate_identities=not args.no_consolidate
        ):
            logger.error("✗ Error en Paso 2 (ETL)")
            return
    else:
        logger.info("⊗ Saltando ETL (usando datos existentes)")
    
    # Si solo queremos ETL, terminar aquí
    if args.etl_only:
        print("\n" + "="*70)
        print("✓ ETL COMPLETADO EXITOSAMENTE")
        print("="*70)
        print(f"""
Archivo generado:
  • scouting_feb.db              - Base de datos SQLite actualizada
  • consolidated_player_id       - Identidades consolidadas para ML

Próximos pasos:
  • Verificar birth_year corregidos:
      python check_birth_year_sqlite.py
  • Entrenar modelos ML:
      python src/run_ml_pipeline.py --skip-etl
  • Revisar candidatos de identidades:
      python src/ml/identity_manager_cli.py list-candidates
        """)
        return
    
    # Paso 3: Entrenar modelos
    if not args.skip_training:
        model, results = paso_3_entrenar_modelos()
        if model is None:
            logger.error("✗ Error en Paso 3 (Entrenamiento)")
            return
    else:
        logger.info("⊗ Saltando entrenamiento (cargando modelos existentes)")
        db_path = os.path.join(os.path.dirname(__file__), '..', 'scouting_feb.db')
        model = PlayerPerformanceModel(db_path=db_path)
        try:
            model.load_model("points_predictor")
            model.load_model("efficiency_predictor")
        except Exception as e:
            logger.error(f"✗ Error cargando modelos: {e}")
            logger.error("Ejecuta sin --skip-training primero")
            return
    
    # Paso 4: Análisis SHAP
    if not paso_4_analisis_shap(model):
        logger.warning("⚠ Advertencia en Paso 4 (SHAP)")
    
    # Paso 5: Predicciones
    if not paso_5_hacer_predicciones(model):
        logger.warning("⚠ Advertencia en Paso 5 (Predicciones)")
    
    print("\n" + "="*70)
    print("✓ PIPELINE COMPLETADO EXITOSAMENTE")
    print("="*70)
    print(f"""
Archivos generados:
  • scouting_feb.db              - Base de datos SQLite
  • models/*.joblib              - Modelos XGBoost entrenados
  • models/*_metadata.json       - Metadata de modelos
  • Revisar candidatos de identidades (si usaste perfiles):
      python src/ml/identity_manager_cli.py list-candidates
  • Ver jugadores con alto potencial (si usaste perfiles):
      python src/ml/identity_manager_cli.py potential
  • Usar modelos para predicciones en producción
  • Reentrenar periódicamente con nuevos datos

Documentación del sistema de identidades:
  • PLAYER_IDENTITY_SYSTEM.md
Próximos pasos:
  • Analizar gráficos SHAP en models/
  • Explorar base de datos SQLite con herramientas SQL
  • Usar modelos para predicciones en producción
  • Reentrenar periódicamente con nuevos datos
    """)


if __name__ == "__main__":
    main()
