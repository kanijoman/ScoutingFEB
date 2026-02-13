# Sistema de Machine Learning - XGBoost + SHAP

## Descripción

Sistema completo de Machine Learning para predecir el rendimiento futuro de jugadores de baloncesto, utilizando:

- **XGBoost**: Algoritmo de gradient boosting para predicciones precisas
- **SHAP**: Interpretabilidad del modelo con SHAP values
- **SQLite**: Base de datos procesada con features optimizados para ML
- **ETL**: Pipeline completo desde MongoDB raw hasta modelos entrenados

## Arquitectura del Sistema

```
┌─────────────────┐
│   MongoDB       │  ← Datos raw de partidos FEB
│   (Raw Data)    │
└────────┬────────┘
         │
         │ ETL Process
         ▼
┌─────────────────┐
│    SQLite       │  ← Datos procesados y agregados
│  (Processed)    │     • Estadísticas por partido
│                 │     • Agregados por temporada
│                 │     • Features para ML
└────────┬────────┘
         │
         │ Feature Engineering
         ▼
┌─────────────────┐
│  XGBoost Models │  ← Modelos de predicción
│                 │     • Puntos próximo partido
│                 │     • Eficiencia próxima
│                 │     • Rendimiento futuro
└────────┬────────┘
         │
         │ SHAP Analysis
         ▼
┌─────────────────┐
│  Explicabilidad │  ← Interpretación de predicciones
│  + Predicciones │     • Importancia de features
│                 │     • Análisis de decisiones
└─────────────────┘
```

## Estructura de Tablas SQLite

### Tablas Principales

#### **players** - Dimensión de jugadores
```sql
- player_id (PK)
- name
- position
- height_cm
- birth_year (para calcular edad)
- dorsal (opcional, no usado en ML)
- years_experience
- total_games
- first_seen_date / last_seen_date
```

#### **teams** - Dimensión de equipos
```sql
- team_id (PK)
- team_code
- team_name
```

#### **games** - Hechos de partidos
```sql
- game_id (PK) 
- competition_id
- season, group_name, game_date
- home_team_id, away_team_id
- home_score, away_score, score_diff
```

#### **player_game_stats** - Estadísticas granulares
```sql
- stat_id (PK)
- game_id, player_id, team_id
- age_at_game (edad en este partido)
- games_played_season (experiencia en temporada)
- minutes_played, points, efficiency_rating
- field_goals_made/attempted, fg_pct
- three_points_made/attempted, three_pct
- offensive/defensive/total_rebounds
- assists, turnovers, steals, blocks
- personal_fouls, plus_minus
- team_won (boolean)
```

#### **player_aggregated_stats** - Features agregadas
```sql
- player_id, season, competition_id
- avg_minutes, avg_points, avg_efficiency
- avg_field_goal_pct, avg_three_point_pct
- std_points, std_efficiency (consistencia)
- trend_points, trend_efficiency (tendencias)
- win_percentage
- games_played
```

#### **player_targets** - Variables objetivo para ML
```sql
- player_id, game_id
- next_game_points
- next_game_efficiency
- next5_avg_points (promedio próximos 5)
- performance_level (categoría)
- will_exceed_avg_points (booleano)
```

### Vistas para ML

#### **ml_features_view** - Todas las features
Une todas las tablas relevantes en un solo dataset listo para ML.

#### **ml_training_dataset** - Dataset completo
Incluye features + targets para entrenamiento directo.

## Proceso ETL

### 1. Extracción (MongoDB)

```python
from ml.etl_processor import FEBDataETL

etl = FEBDataETL(
    mongodb_uri="mongodb://localhost:27017/",
    mongodb_db="scouting_feb",
    sqlite_path="scouting_feb.db"
)

# Extraer partidos de MongoDB
etl.run_full_etl()
```

### 2. Transformación

El ETL transforma:
- **Datos raw** → Estructura relacional
- **Boxscore MongoDB** → player_game_stats
- **Cálculo de agregados** → player_aggregated_stats
- **Features de contexto** → team_game_context

### 3. Carga (SQLite)

Todos los datos se cargan en SQLite con:
- Integridad referencial
- Índices optimizados
- Vistas pre-computadas

## Entrenamiento de Modelos

### Uso Básico

```python
from ml.xgboost_model import PlayerPerformanceModel

# Crear instancia del modelo
model = PlayerPerformanceModel(db_path="scouting_feb.db")

# Entrenar todos los modelos
results = model.train_all_models(min_games=5)

# Ver métricas
for model_name, result in results.items():
    print(f"\n{model_name}:")
    print(f"  RMSE: {result['metrics']['test']['rmse']:.2f}")
    print(f"  R²: {result['metrics']['test']['r2']:.3f}")
```

### Modelos Disponibles

1. **points_predictor**: Predice puntos en el próximo partido
2. **efficiency_predictor**: Predice valoración (efficiency rating) próximo partido

Puedes extender fácilmente con:
- Predicción de rebotes
- Predicción de asistencias
- Clasificación de rendimiento (bajo/medio/alto)

## Interpretabilidad con SHAP

### Importancia de Características

```python
# Obtener importancia de features
importance_df = model.get_feature_importance("points_predictor")
print(importance_df.head(10))
```

Output:
```
                    feature  xgboost_importance  shap_importance
0              avg_points                 0.234           0.456
1           avg_efficiency                0.189           0.321
2          minutes_played                0.145           0.287
3      avg_field_goal_pct                0.098           0.198
4              trend_points                0.076           0.154
```

### Gráficos SHAP

```python
# Generar gráfico resumen de SHAP
model.plot_shap_summary(
    "points_predictor",
    num_samples=200,
    save_path="shap_summary.png"
)
```

### Explicar Predicción Individual

```python
# Predecir y explicar para un jugador específico
prediction = model.predict_player_performance(
    player_id=123,
    model_name="points_predictor"
)

print(f"Jugador: {prediction['player_name']}")
print(f"Predicción próximo partido: {prediction['prediction']:.1f} puntos")
print(f"Promedio actual: {prediction['current_avg']:.1f} puntos")

print("\nFactores más influyentes:")
for feature in prediction['top_features']:
    print(f"  • {feature['feature']}: {feature['value']:.2f} "
          f"(impacto: {feature['impact']})")
```

### Features del Modelo

### Features Básicas (Partido Actual)
- **Información del jugador**: Edad, años de experiencia
- Minutos jugados
- Puntos, valoración
- Porcentajes de tiro (FG%, 3P%, FT%)
- Rebotes, asistencias, robos, tapones
- Pérdidas, faltas
- Plus/minus
- Titular o suplente
- Local o visitante

### Features Agregadas (Histórico)
- **Edad promedio** durante la temporada
- Promedios de temporada (puntos, valoración, etc.)
- Consistencia (desviación estándar)
- Tendencias (regresión lineal últimos partidos)
- Porcentaje de victorias
- Número de partidos jugados
- Años de experiencia

### Features Contextuales
- Racha del equipo
- Días desde último partido
- Rendimiento reciente del equipo
- Importancia del partido (playoff, derby)

## Hiperparámetros XGBoost

Parámetros por defecto optimizados:

```python
params = {
    'objective': 'reg:squarederror',
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 200,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'random_state': 42
}
```

Puedes personalizarlos:

```python
custom_params = {
    'max_depth': 8,
    'learning_rate': 0.05,
    'n_estimators': 500
}

result = model.train_model(X, y, params=custom_params)
```

## Métricas de Evaluación

El sistema calcula automáticamente:

- **RMSE** (Root Mean Squared Error): Error promedio de predicción
- **MAE** (Mean Absolute Error): Error absoluto promedio
- **R²** (R-squared): Porcentaje de varianza explicada (0-1)

Ejemplo de output:
```
✓ Modelo entrenado
  Test RMSE: 4.23
  Test R²: 0.756
```

Esto significa que el modelo explica el 75.6% de la variabilidad en los puntos, con un error promedio de ~4 puntos.

## Casos de Uso

### 1. Scouting de Jugadores

Identificar jugadores con tendencia ascendente:

```python
# Filtrar jugadores con trend_points positivo alto
conn = model.get_connection()
query = """
SELECT p.name, pas.avg_points, pas.trend_points, pas.games_played
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
WHERE pas.trend_points > 2.0
  AND pas.games_played >= 10
ORDER BY pas.trend_points DESC
LIMIT 20
"""
rising_stars = pd.read_sql_query(query, conn)
```

### 2. Predicción Pre-Partido

Predecir rendimiento antes de cada partido:

```python
# Predecir para todo un equipo
team_players = [101, 102, 103, 104, 105]  # IDs de jugadores

for player_id in team_players:
    pred = model.predict_player_performance(player_id)
    print(f"{pred['player_name']}: {pred['prediction']:.1f} puntos esperados")
```

### 3. Análisis de Consistencia

Identificar jugadores consistentes vs inconsistentes:

```python
query = """
SELECT p.name, 
       pas.avg_points, 
       pas.std_points,
       (pas.std_points / pas.avg_points) as cv_points
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
WHERE pas.avg_points > 10
ORDER BY cv_points
LIMIT 10
```

### 4. Análisis What-If

Simular cambios en características:

```python
# ¿Qué pasaría si el jugador jugara más minutos?
X_modified = X.copy()
X_modified['minutes_played'] = 30  # Aumentar minutos

prediction_new = model.models['points_predictor'].predict(X_modified)
```

## Optimización y Tuning

### Grid Search de Hiperparámetros

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'max_depth': [4, 6, 8],
    'learning_rate': [0.01, 0.1, 0.2],
    'n_estimators': [100, 200, 500]
}

xgb_model = xgb.XGBRegressor()
grid_search = GridSearchCV(xgb_model, param_grid, cv=5, scoring='neg_mean_squared_error')
grid_search.fit(X_train, y_train)

print(f"Mejores parámetros: {grid_search.best_params_}")
```

### Feature Selection

```python
from sklearn.feature_selection import SelectKBest, f_regression

# Seleccionar top K features
selector = SelectKBest(f_regression, k=20)
X_selected = selector.fit_transform(X, y)

# Ver features seleccionadas
selected_features = [self.feature_names[i] 
                    for i in selector.get_support(indices=True)]
```

## Monitoreo de Modelos

### Guardar Métricas Históricas

```python
# Guardar métricas en cada entrenamiento
metrics_log = {
    'timestamp': datetime.now().isoformat(),
    'model_name': 'points_predictor',
    'test_rmse': result['metrics']['test']['rmse'],
    'test_r2': result['metrics']['test']['r2'],
    'n_samples': len(X),
    'n_features': X.shape[1]
}

# Guardar en JSON o base de datos
with open('models/metrics_log.json', 'a') as f:
    f.write(json.dumps(metrics_log) + '\n')
```

### Detección de Drift

Monitorear si las predicciones degradan con el tiempo debido a cambios en los datos.

## Requisitos

### Librerías Python

```bash
pip install xgboost shap scikit-learn matplotlib pandas numpy joblib
```

### Versiones Recomendadas
- Python >= 3.8
- xgboost >= 1.7.0
- shap >= 0.41.0
- scikit-learn >= 1.0.0

## Troubleshooting

### "Modelo no encontrado"
Asegúrate de entrenar primero: `model.train_all_models()`

### "No se encontraron datos"
Ejecuta el ETL primero: `etl.run_full_etl()`

### SHAP es lento
Reduce `num_samples` en `plot_shap_summary()` o `explain_model()`

### Memoria insuficiente
- Reduce batch size en el ETL con parámetro `limit`
- Entrena con menos features usando feature selection

## Próximas Mejoras

- [ ] Cross-validation temporal (respetando orden cronológico)
- [ ] Modelos de clasificación (rendimiento alto/medio/bajo)
- [ ] Ensemble de múltiples modelos
- [ ] API REST para predicciones en tiempo real
- [ ] Dashboard interactivo con Streamlit
- [ ] Reentrenamiento automático periódico
- [ ] A/B testing de modelos
- [ ] Tracking de experimentos con MLflow
