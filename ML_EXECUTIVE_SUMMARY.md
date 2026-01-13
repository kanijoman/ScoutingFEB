# ScoutingFEB - Resumen Ejecutivo: Sistema de ML

## 🎯 Visión General

**ScoutingFEB** es un sistema completo de análisis y predicción de rendimiento de jugadores de baloncesto que combina:

1. **Scraping Automático** de datos de la FEB
2. **Pipeline ETL** (Extract, Transform, Load)
3. **Normalización Z-Score** para comparaciones históricas ⭐ NUEVO
4. **Machine Learning** con XGBoost
5. **Interpretabilidad** con SHAP

## 📊 Propuesta Implementada

### 1. Base de Datos SQLite - Esquema Optimizado para ML

#### Diseño de Tablas

**Tablas Dimensionales:**
- `players` - Catálogo de jugadores (con `birth_year`, `years_experience`)
- `teams` - Catálogo de equipos
- `competitions` - Catálogo de competiciones
- `competition_levels` - Niveles dinámicos por temporada ⭐ NUEVO

**Tablas de Hechos:**
- `games` - Información de partidos
- `player_game_stats` - Estadísticas granulares + Z-Scores ⭐ ACTUALIZADO

**Tablas de Features:**
- `player_aggregated_stats` - Stats agregadas + Percentiles ⭐ ACTUALIZADO
- `player_targets` - Variables objetivo para ML
- `team_game_context` - Contexto del equipo
- `game_context` - Contexto del partido

**Vistas Precomputadas:**
- `ml_features_view` - Todas las features + Z-Scores
- `ml_training_dataset` - Dataset completo para entrenamiento

#### Features CRÍTICAS para Predicción

| Feature | Importancia | Justificación |
|---------|-------------|---------------|
| **age_at_game** | 🔴 CRÍTICA | Edad predice prime deportivo (25-29), potencial (juveniles), declive (>32) |
| **z_efficiency** | 🔴 CRÍTICA | Eficiencia normalizada (comparable entre épocas/ligas) |
| **z_points** | 🔴 CRÍTICA | Puntos normalizados (elimina efecto época/liga) |
| **percentile_efficiency** | 🟠 ALTA | Comunicación clara para scouts (top X%) |
| **avg_minutes** | 🟠 ALTA | Rol en equipo y confianza de entrenador |
| **years_experience** | 🟠 ALTA | Madurez deportiva |
| **z_rebounds**, **z_assists** | 🟡 MEDIA | Rol específico del jugador |
| dorsal | ⚪ IRRELEVANTE | Sin valor predictivo |

#### Ventajas del Diseño

✅ **Normalización**: Evita redundancia de datos
✅ **Indexado**: Queries optimizados para ML
✅ **Portabilidad**: Archivo único SQLite
✅ **Performance**: Agregados pre-calculados
✅ **Escalabilidad**: Diseño preparado para millones de registros
✅ **Comparabilidad**: Z-Scores permiten comparar épocas y ligas ⭐ NUEVO

### 2. Pipeline ETL (MongoDB → SQLite)

#### Proceso Implementado

**EXTRACT**
```python
- Leer documentos de MongoDB (all_feb_games_masc/fem)
- Iterar por todos los partidos disponibles
- Extraer HEADER, BOXSCORE, PLAYBYPLAY, SHOTCHART
```

**TRANSFORM**
```python
- Normalizar estructura de datos
- Parsear estadísticas de jugadores
- Calcular porcentajes de tiro
- Calcular edad a partir de birth_year y game_date ⭐ NUEVO
- Extraer equipos y competiciones
- Convertir formatos de tiempo
```

**LOAD**
```python
- Insertar dimensiones (players, teams, competitions)
- Cargar hechos (games, player_game_stats)
- Calcular agregados (player_aggregated_stats)
- Normalizar con Z-Scores por contexto ⭐ NUEVO
- Calcular percentiles ⭐ NUEVO
- Crear índices y vistas
```

#### Características del ETL

✅ **Robusto**: Manejo de errores por partido
✅ **Incremental**: Solo procesa datos nuevos
✅ **Transaccional**: Commits periódicos
✅ **Logging**: Seguimiento completo del proceso
✅ **Configurable**: Límites y filtros opcionales
✅ **Contextual**: Z-Scores por nivel+temporada ⭐ NUEVO

#### Métricas Típicas del ETL

```
Entrada:  MongoDB con ~500 partidos
Salida:   SQLite con:
          - 500 partidos en tabla games
          - ~1,000 jugadores en tabla players
          - ~10,000 estadísticas en player_game_stats
          - ~1,000 agregados en player_aggregated_stats
          - Z-Scores y percentiles calculados ⭐ NUEVO

Tiempo:   ~3-7 minutos (incluye normalización)
```

### 3. Normalización Z-Score (Comparaciones Históricas) ⭐ NUEVO

#### ¿Por qué Z-Score?

**Problema**: 10 pts en 2005 ≠ 10 pts en 2025, ACB ≠ EBA

**Solución**: Z-Score mide cuántas desviaciones estándar está un valor de la media de su **contexto**

$$Z = \frac{x - \mu}{\sigma}$$

**Contexto** = nivel_competición + temporada

#### Interpretación

| Z-Score | Significado | Percentil |
|---------|-------------|-----------|
| 0 | Promedio | 50% |
| +1.0 | Muy bueno | ~84% |
| +2.0 | Élite | ~97% |
| +2.5 | Dominante | ~99% |

#### Ventajas

✅ **Para ML**: Escala homogénea, mejor convergencia XGBoost
✅ **Para Scouts**: Identificar jugadores dominantes en ligas inferiores
✅ **Para Comparaciones**: 2005 vs 2025 son comparables

Ver [ZSCORE_NORMALIZATION.md](ZSCORE_NORMALIZATION.md) para detalles completos.

### 4. Modelo de Machine Learning: XGBoost + SHAP

#### Arquitectura del Modelo

**Algoritmo:** XGBoost (eXtreme Gradient Boosting)
- Gradient boosting optimizado
- Regularización incorporada (L1/L2)
- Manejo nativo de missing values
- Feature importance nativa

**Hiperparámetros:**
```python
{
    'objective': 'reg:squarederror',  # Regresión
    'max_depth': 6,                   # Profundidad árboles
    'learning_rate': 0.1,             # Tasa de aprendizaje
    'n_estimators': 200,              # Número de árboles
    'subsample': 0.8,                 # Submuestreo
    'colsample_bytree': 0.8           # Submuestreo de features
}
```

#### Modelos Implementados

**1. Points Predictor**
- **Objetivo**: Predecir puntos en el próximo partido
- **Target**: `next_game_points`
- **Uso**: Scouting pre-partido, análisis de rendimiento

**2. Efficiency Predictor**
- **Objetivo**: Predecir valoración (efficiency rating) en próximo partido
- **Target**: `next_game_efficiency`
- **Uso**: Evaluación integral de rendimiento

#### Features del Modelo (60+ características)

**Features Básicas (20+):**
- **Edad del jugador** (age_at_game) - CRÍTICO
- **Años de experiencia** (years_experience)
- Minutos jugados, puntos, valoración
- Porcentajes de tiro (FG%, 3P%, 2P%, FT%)
- Rebotes (ofensivos, defensivos, totales)
- Asistencias, pérdidas, robos, tapones
- Faltas, plus/minus
- Contexto: titular/suplente, local/visitante

**Features Agregadas (20+):**
- **Edad promedio de la temporada** (avg_age)
- Promedios de temporada
- Desviación estándar (consistencia)
- Tendencias (regresión lineal últimos N juegos)
- Porcentaje de victorias
- Número de partidos jugados

**Features Contextuales (10+):**
- Racha del equipo
- Días desde último partido
- Rendimiento reciente del equipo
- Importancia del partido
- Posición en clasificación

**Features Categóricas:**
- Posición del jugador
- Género de la competición
- Nivel de competición

#### Métricas de Rendimiento Esperadas

Para **Points Predictor** (ejemplo con datos típicos):
```
RMSE:  4-6 puntos
MAE:   3-5 puntos
R²:    0.65-0.80 (65-80% de varianza explicada)
```

Para **Efficiency Predictor**:
```
RMSE:  3-5 puntos de valoración
MAE:   2-4 puntos de valoración
R²:    0.60-0.75
```

**Interpretación:**
- El modelo predice con un error promedio de ~4 puntos
- Explica ~70% de la variabilidad en el rendimiento
- Útil para identificar patrones y tendencias

### 4. Interpretabilidad: SHAP (SHapley Additive exPlanations)

#### ¿Qué es SHAP?

SHAP es un método basado en teoría de juegos (valores de Shapley) que explica:
- **Importancia global**: Qué features son más importantes en general
- **Impacto individual**: Cómo cada feature afecta una predicción específica
- **Interacciones**: Relaciones entre features

#### Visualizaciones Generadas

**1. Summary Plot**
- Muestra top N features más importantes
- Color indica valor de la feature (alto/bajo)
- Posición horizontal indica impacto en predicción
- Guardado como: `models/*_shap_summary.png`

**2. Feature Importance**
- Lista ordenada de features por importancia SHAP
- Comparación con importancia XGBoost nativa
- Exportable a DataFrame

**3. Force Plot (individual)**
- Explicación detallada de una predicción
- Muestra qué features aumentan/disminuyen predicción
- Valores base vs valor predicho

#### Ejemplo de Output SHAP

```python
Top Features (SHAP Importance):
1. avg_points              0.456  ← Promedio histórico
2. avg_efficiency          0.321  ← Valoración histórica
3. minutes_played          0.287  ← Minutos en último partido
4. avg_field_goal_pct      0.198  ← Efectividad de tiro
5. trend_points            0.154  ← Tendencia reciente
```

**Interpretación:**
- El promedio histórico de puntos es el predictor más fuerte
- La forma actual (tendencia) también es muy relevante
- Minutos jugados indica confianza del entrenador

## 🎬 Flujo de Trabajo Completo

### Caso de Uso: Analizar Nueva Temporada

```powershell
# 1. Scraping de partidos nuevos (incremental)
cd src
python main.py
# → Actualiza MongoDB con partidos nuevos

# 2. ETL: Procesar nuevos datos
python -m ml.etl_processor
# → Transforma y carga en SQLite

# 3. Reentrenar modelo (opcional)
python -m ml.xgboost_model
# → Entrena con datos actualizados

# 4. Hacer predicciones
python
>>> from ml.xgboost_model import PlayerPerformanceModel
>>> model = PlayerPerformanceModel()
>>> model.load_model("points_predictor")
>>> pred = model.predict_player_performance(player_id=123)
>>> print(f"Predicción: {pred['prediction']:.1f} puntos")
```

### Pipeline Automatizado

```powershell
# Todo en uno
python src/run_ml_pipeline.py

# Salida:
# ✓ ETL completado: 500 partidos, 1000 jugadores
# ✓ Modelos entrenados: RMSE=4.2, R²=0.76
# ✓ Análisis SHAP generado
# ✓ Predicciones de ejemplo realizadas
```

## 📈 Casos de Uso Avanzados

### 1. Identificar Jugadores en Ascenso

```python
# Jugadores con tendencia positiva significativa
query = """
SELECT p.name, pas.avg_points, pas.trend_points
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
WHERE pas.trend_points > 2.0  -- Mejorando >2 puntos/partido
  AND pas.games_played >= 10
ORDER BY pas.trend_points DESC
"""
```

### 2. Scouting Pre-Partido

```python
# Predecir rendimiento de equipo completo
team_predictions = []
for player_id in team_roster:
    pred = model.predict_player_performance(player_id)
    team_predictions.append(pred)

total_expected = sum(p['prediction'] for p in team_predictions)
print(f"Puntos esperados del equipo: {total_expected}")
```

### 3. Análisis de Consistencia

```python
# Jugadores más/menos consistentes
query = """
SELECT p.name, 
       pas.avg_points,
       pas.std_points,
       (pas.std_points / pas.avg_points) as coef_variation
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
ORDER BY coef_variation
```

### 4. What-If Analysis

```python
# ¿Qué pasaría si jugara más minutos?
X_original['minutes_played'] = 20  # Actual
prediction_20min = model.predict(X_original)

X_modified['minutes_played'] = 30  # Simulación
prediction_30min = model.predict(X_modified)

impact = prediction_30min - prediction_20min
print(f"Impacto de 10 minutos extra: +{impact:.1f} puntos")
```

## 🔧 Extensibilidad

### Añadir Nuevos Modelos

```python
# En xgboost_model.py
def train_rebounds_predictor(self):
    X, y = self.prepare_training_data(target='next_game_rebounds')
    return self.train_model(X, y, model_name='rebounds_predictor')
```

### Añadir Nuevas Features

```sql
-- En sqlite_schema.py, añadir columna
ALTER TABLE player_aggregated_stats
ADD COLUMN avg_usage_rate REAL;

-- Calcular en ETL
UPDATE player_aggregated_stats
SET avg_usage_rate = (
    SELECT AVG(usage_rate) FROM player_game_stats
    WHERE player_id = player_aggregated_stats.player_id
);
```

### Añadir Nuevos Targets

```python
# Clasificación de rendimiento
def add_performance_class(row):
    if row['efficiency'] > 20: return 'excellent'
    elif row['efficiency'] > 10: return 'good'
    elif row['efficiency'] > 5: return 'average'
    else: return 'poor'

# Entrenar clasificador
from xgboost import XGBClassifier
model = XGBClassifier()
model.fit(X, y_class)
```

## 🚀 Próximos Pasos y Mejoras

### Corto Plazo
- [ ] Cross-validation temporal (time-series aware)
- [ ] Más modelos (rebotes, asistencias, etc.)
- [ ] Hyperparameter tuning con GridSearch
- [ ] Feature selection automático

### Medio Plazo
- [ ] API REST (FastAPI) para predicciones
- [ ] Dashboard interactivo (Streamlit/Dash)
- [ ] Sistema de alertas (jugadores prometedores)
- [ ] Exportación de reportes PDF

### Largo Plazo
- [ ] Ensemble de modelos (bagging/stacking)
- [ ] Deep Learning (LSTM para series temporales)
- [ ] Análisis de video (computer vision)
- [ ] Marketplace de modelos entrenados

## 📊 KPIs del Sistema

### Métricas de Datos
- **Cobertura**: % de partidos con datos completos
- **Actualización**: Frecuencia de scraping (diario/semanal)
- **Completitud**: % de jugadores con >N partidos

### Métricas de Modelo
- **Accuracy**: RMSE, MAE, R² en test set
- **Drift**: Degradación de rendimiento con el tiempo
- **Latencia**: Tiempo de predicción (<100ms objetivo)

### Métricas de Negocio
- **Adoption**: % de recomendaciones seguidas
- **ROI**: Valor generado por decisiones basadas en IA
- **Satisfacción**: Feedback de usuarios (scouts/entrenadores)

## 🎓 Conclusión

El sistema implementado proporciona:

✅ **Pipeline completo** desde scraping hasta predicciones
✅ **Arquitectura escalable** con separación de responsabilidades
✅ **Interpretabilidad** mediante SHAP para confianza en decisiones
✅ **Extensibilidad** para añadir nuevos modelos y features
✅ **Documentación completa** para mantenimiento y mejoras

**Tecnologías clave:**
- MongoDB (datos raw) + SQLite (datos procesados)
- XGBoost (predicción) + SHAP (explicabilidad)
- Python ecosystem (pandas, numpy, scikit-learn)

**Valor generado:**
- Predicciones objetivas basadas en datos
- Identificación de talento emergente
- Optimización de estrategias de juego
- Toma de decisiones informada para scouts y entrenadores
