# Arquitectura Completa del Sistema ScoutingFEB

## Visión General del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CAPA DE DATOS RAW                          │
└─────────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐
    │   Web FEB       │  ← Scraping de calendario y partidos
    │  (baloncesto    │
    │   envivo.feb.es)│
    └────────┬────────┘
             │
             │ feb_scraper.py
             │ + api_client.py
             ▼
    ┌─────────────────┐
    │   MongoDB       │  ← Almacenamiento raw (NoSQL)
    │   scouting_feb  │     • HEADER
    │                 │     • BOXSCORE
    │   Collections:  │     • PLAYBYPLAY
    │   - masc        │     • SHOTCHART
    │   - fem         │
    │   - state       │  ← Sistema incremental
    └────────┬────────┘
             │
             │
┌────────────────────────────────────────────────────────────────────┐
│                       CAPA DE PROCESAMIENTO                        │
└────────────────────────────────────────────────────────────────────┘
             │
             │ etl_processor.py
             │ • Extract: MongoDB
             │ • Transform: Normalizar, calcular features
             │ • Load: SQLite
             ▼
    ┌─────────────────┐
    │    SQLite       │  ← Base de datos procesada (SQL)
    │ scouting_feb.db │
    │                 │
    │ Tablas:         │
    │ ├ players       │  ← Dimensión jugadores
    │ ├ teams         │  ← Dimensión equipos
    │ ├ competitions  │  ← Dimensión competiciones
    │ ├ games         │  ← Hechos: partidos
    │ ├ player_game_  │  ← Hechos: stats por partido
    │ │  stats        │
    │ ├ player_agg_   │  ← Features agregadas
    │ │  stats        │     (promedios, tendencias)
    │ ├ player_targets│  ← Variables objetivo ML
    │ └ ...           │
    └────────┬────────┘
             │
             │
┌────────────────────────────────────────────────────────────────────┐
│                    CAPA DE MACHINE LEARNING                        │
└────────────────────────────────────────────────────────────────────┘
             │
             │ xgboost_model.py
             │ • Feature engineering
             │ • Training
             │ • Evaluation
             ▼
    ┌─────────────────┐
    │  XGBoost Models │  ← Modelos entrenados
    │                 │
    │ • points_       │  ← Predictor de puntos
    │   predictor     │
    │                 │
    │ • efficiency_   │  ← Predictor de valoración
    │   predictor     │
    │                 │
    │ Guardados:      │
    │ ├ *.joblib      │  ← Modelos serializados
    │ └ *_metadata.   │  ← Configuración
    │   json          │
    └────────┬────────┘
             │
             │
┌────────────────────────────────────────────────────────────────────┐
│                  CAPA DE INTERPRETABILIDAD                         │
└────────────────────────────────────────────────────────────────────┘
             │
             │ SHAP (SHapley Additive exPlanations)
             │ • Feature importance
             │ • Individual predictions
             │ • Global explanations
             ▼
    ┌─────────────────┐
    │  Explicaciones  │  ← Interpretabilidad
    │                 │
    │ • Summary plots │  ← Gráficos de importancia
    │ • Force plots   │  ← Explicaciones individuales
    │ • Dependence    │  ← Relaciones entre features
    │   plots         │
    └────────┬────────┘
             │
             │
┌────────────────────────────────────────────────────────────────────┐
│                      CAPA DE APLICACIÓN                            │
└────────────────────────────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  Predicciones   │  ← API / Scripts
    │  y Análisis     │
    │                 │
    │ • Predicción    │  ← Rendimiento futuro
    │   individual    │
    │                 │
    │ • Análisis de   │  ← Identificar talento
    │   jugadores     │
    │                 │
    │ • Comparativas  │  ← Benchmarking
    │                 │
    │ • Dashboards    │  ← Visualización
    └─────────────────┘
```

## Flujo de Datos Detallado

### 1. Scraping (Web → MongoDB)

```
┌────────────┐
│ Web FEB    │
└──────┬─────┘
       │
       │ HTTP GET/POST
       ▼
┌──────────────────────────────────────┐
│ feb_scraper.py                       │
│ ├ get_seasons()                      │
│ ├ get_groups()                       │
│ └ get_matches()                      │
└──────┬───────────────────────────────┘
       │
       │ Match codes
       ▼
┌──────────────────────────────────────┐
│ api_client.py                        │
│ └ fetch_boxscore(match_code)         │
└──────┬───────────────────────────────┘
       │
       │ JSON data
       ▼
┌──────────────────────────────────────┐
│ mongodb_client.py                    │
│ └ insert_game(game_data)             │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────┐
│ MongoDB      │
│ {            │
│   HEADER: {..│
│   BOXSCORE:{ │
│   ...        │
│ }            │
└──────────────┘
```

### 2. ETL (MongoDB → SQLite)

```
┌──────────────┐
│ MongoDB      │
│ (Raw JSON)   │
└──────┬───────┘
       │
       │ Extract
       ▼
┌─────────────────────────────────┐
│ etl_processor.py                │
│                                 │
│ extract_games_from_mongodb()    │
│   ├ Leer documentos             │
│   └ Iterar partidos             │
└──────┬──────────────────────────┘
       │
       │ Transform
       ▼
┌─────────────────────────────────┐
│ transform_game_data()           │
│   ├ Normalizar estructura       │
│   ├ Extraer equipos             │
│   ├ Parsear estadísticas        │
│   ├ Calcular porcentajes        │
│   └ Crear registros             │
└──────┬──────────────────────────┘
       │
       │ Load
       ▼
┌─────────────────────────────────┐
│ load_game()                     │
│   ├ load_competition()          │
│   ├ load_team()                 │
│   ├ load_player()               │
│   └ INSERT player_game_stats    │
└──────┬──────────────────────────┘
       │
       │ Aggregate
       ▼
┌─────────────────────────────────┐
│ compute_player_aggregates()     │
│   ├ GROUP BY player/season      │
│   ├ AVG(points, efficiency...)  │
│   ├ STD(points...)              │
│   ├ TREND (linear regression)   │
│   └ INSERT player_agg_stats     │
└──────┬──────────────────────────┘
       │
       ▼
┌──────────────┐
│ SQLite       │
│ (Relational) │
└──────────────┘
```

### 3. Machine Learning (SQLite → Modelos)

```
┌──────────────┐
│ SQLite       │
└──────┬───────┘
       │
       │ SQL Query
       ▼
┌─────────────────────────────────┐
│ prepare_training_data()         │
│   ├ SELECT features + targets   │
│   ├ JOIN múltiples tablas       │
│   ├ Compute targets             │
│   │   (next game values)        │
│   └ Encode categoricals         │
└──────┬──────────────────────────┘
       │
       │ X (features), y (target)
       ▼
┌─────────────────────────────────┐
│ train_model()                   │
│   ├ train_test_split()          │
│   ├ XGBRegressor.fit()          │
│   ├ early_stopping              │
│   └ evaluate(RMSE, R², MAE)     │
└──────┬──────────────────────────┘
       │
       │ Trained model
       ▼
┌─────────────────────────────────┐
│ TreeExplainer (SHAP)            │
│   ├ Compute SHAP values         │
│   ├ Feature importance          │
│   └ Generate plots              │
└──────┬──────────────────────────┘
       │
       │ Save
       ▼
┌──────────────┐
│ models/      │
│ *.joblib     │
│ *.json       │
│ *.png        │
└──────────────┘
```

### 4. Predicción (Modelos → Insights)

```
┌──────────────┐
│ New Player   │
│ Data         │
└──────┬───────┘
       │
       │ player_id
       ▼
┌─────────────────────────────────┐
│ predict_player_performance()    │
│   ├ Load latest player data     │
│   ├ Prepare features            │
│   └ model.predict(X)            │
└──────┬──────────────────────────┘
       │
       │ Prediction value
       ▼
┌─────────────────────────────────┐
│ SHAP Explanation                │
│   ├ explainer.shap_values(X)    │
│   ├ Identify top features       │
│   └ Compute impacts             │
└──────┬──────────────────────────┘
       │
       │ Explained prediction
       ▼
┌──────────────┐
│ Output       │
│ {            │
│  prediction: │
│  features: [ │
│    impact:+  │
│    value:... │
│  ]           │
│ }            │
└──────────────┘
```

## Stack Tecnológico

### Backend de Datos
- **MongoDB**: Almacenamiento NoSQL para datos raw
  - Flexible para estructura JSON compleja
  - Incremental scraping con colección `scraping_state`

- **SQLite**: Base de datos relacional para datos procesados
  - Estructura normalizada
  - Optimizada para queries ML
  - Portabilidad (archivo único)

### Machine Learning
- **XGBoost**: Gradient boosting de alto rendimiento
  - Regularización incorporada
  - Manejo de missing values
  - Feature importance nativa

- **SHAP**: Interpretabilidad del modelo
  - Valores de Shapley para explicar predicciones
  - Gráficos de importancia
  - Análisis de interacciones

- **scikit-learn**: Utilidades ML
  - Train/test split
  - Métricas de evaluación
  - Preprocessing

### Desarrollo
- **Python 3.8+**: Lenguaje principal
- **pandas/numpy**: Manipulación de datos
- **matplotlib**: Visualización

## Arquitectura de Features

### Feature Engineering Pipeline

```
Raw Stats → Engineered Features
│
├─ Básicas (directas)
│  ├─ points
│  ├─ minutes_played
│  ├─ field_goal_pct
│  └─ ...
│
├─ Agregadas (calculadas)
│  ├─ avg_points (temporada)
│  ├─ std_points (consistencia)
│  ├─ trend_points (pendiente)
│  └─ win_percentage
│
├─ Contextuales
│  ├─ is_home
│  ├─ is_starter
│  ├─ team_streak
│  └─ days_since_last_game
│
└─ Categóricas (encoded)
   ├─ position → [0,1,2,3,4]
   ├─ gender → [0,1]
   └─ level → [0,1,2,...]
```

## Métricas y Monitoreo

### Métricas del Pipeline

1. **ETL**
   - Partidos procesados
   - Jugadores únicos
   - Tiempo de procesamiento
   - Errores/omisiones

2. **Modelos**
   - RMSE (error cuadrático medio)
   - MAE (error absoluto medio)
   - R² (coeficiente de determinación)
   - Training time

3. **Predicciones**
   - Latencia de predicción
   - Confianza del modelo
   - Feature coverage

## Escalabilidad

### Limitaciones Actuales
- SQLite: ~1-10M registros (adecuado para proyecto)
- Single-machine training
- Batch predictions

### Opciones de Escalado
1. **Datos**: Migrar a PostgreSQL/MySQL
2. **Training**: Usar Dask o Ray para paralelización
3. **Serving**: API REST con FastAPI + Redis cache
4. **Monitoreo**: MLflow + Prometheus

## Seguridad y Privacidad

- ✓ Datos públicos de FEB
- ✓ Sin información personal identificable
- ✓ Modelos locales (no cloud)
- ✓ Compliance con términos de uso FEB
