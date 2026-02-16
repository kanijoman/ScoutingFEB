# Plan de Refactorización - ScoutingFEB

## Estado Actual: Testing Infrastructure Completada ✅

### Progreso Completado

#### 1. Infraestructura de Testing (100% ✅)

**Archivos Creados**:
- `requirements_dev.txt` - Dependencias de testing
- `pytest.ini` - Configuración de pytest
- `tests/conftest.py` - Fixtures compartidos
- `tests/fixtures/sample_data/` - Datos de muestra para tests

**Tests Implementados**:
- **Regresión End-to-End** (`tests/regression/test_full_pipeline.py`)
  - Test de pipeline completo ETL
  - Validación de creación de esquema
  - Manejo de MongoDB vacío
  - Verificación de integridad de datos

- **Tests de Integración** (`tests/integration/`)
  - `test_etl_sanity.py` - Validación de métricas en rangos válidos
  - `test_identity_matching.py` - Matching de identidades de jugadores
  - `test_potential_scoring.py` - Sistema de scoring de potencial

- **Tests de Humo** (`tests/smoke/`)
  - `test_ml_executes.py` - Modelos ML se ejecutan sin crash
  - `test_ui_loads.py` - Componentes UI se cargan correctamente

**Utilidades y Scripts**:
- `scripts/quick_validation.py` - Validación rápida (<30 seg)
- `scripts/run_regression_suite.py` - Suite completa con coverage
- `docs/TESTING_GUIDE.md` - Documentación completa de testing

#### 2. Utilidades Compartidas (100% ✅)

**Eliminación de Código Duplicado**:
- `src/utils/database_context.py` - Gestión centralizada de conexiones SQLite
  - Context managers para transacciones
  - Funciones helper para queries comunes
  - Clase DatabaseContext para operaciones batch
  
- `src/utils/season_utils.py` - Utilidades de parsing de temporadas
  - `parse_season()` - Conversión string → tupla años
  - `format_season()` - Conversión años → string
  - `get_previous_season()`, `get_next_season()`
  - `seasons_between()` - Generación de rangos
  - Funciones de comparación y validación
  
- `src/utils/progress_reporter.py` - Reporting de progreso consistente
  - Clase `ProgressReporter` con ETA y elapsed time
  - `BatchProgressReporter` para operaciones con commits
  - Funciones `report_section()`, `report_stats()`

---

## Próximos Pasos de Refactorización

### Fase 1: Refactorización Estructural (Prioridad Alta)

#### A. División de etl_processor.py (2,349 líneas → 5 módulos)

**Estado**: 🔄 Pendiente

**Módulos a Extraer**:

1. **`etl_extractor.py`** (~300 líneas)
   - Clase `MongoDBExtractor`
   - Método `extract_games_from_mongodb()`
   - Lógica de queries MongoDB
   - **Validación**: Ejecutar tests de regresión post-extracción

2. **`player_metrics_calculator.py`** (~400 líneas)
   - Clase `PlayerMetricsCalculator`
   - Método `compute_profile_metrics()` (líneas 824-1060)
   - Cálculo de 35+ métricas avanzadas
   - Per-36 stats, rolling windows, momentum index
   - **Validación**: Tests de sanidad para rangos de métricas

3. **`potential_scorer.py`** (~300 líneas)
   - Clase `PotentialScorer`
   - Métodos `calculate_profile_potential_scores()` (líneas 1158-1422)
   - `calculate_career_potential_scores()` (líneas 1505-1924)
   - Sistema de clasificación en tiers
   - **Validación**: Tests de potential scoring

4. **`etl_transformer.py`** (~400 líneas)
   - Clase `GameDataTransformer`
   - Método `transform_game_data()` (líneas 136-220)
   - `_transform_player_stats()` (líneas 220-482)
   - Lógica de pesos de partidos
   - **Validación**: Tests de transformación de datos

5. **`etl_loader.py`** (~400 líneas)
   - Clase `SQLiteLoader`
   - Métodos `load_game()`, `load_player()`, `load_team()`, `load_competition()`
   - `load_or_get_player_profile()` (líneas 482-570)
   - Operaciones de insert/update en SQLite
   - **Validación**: Tests de carga de datos

**Clase Orquestadora** (mantenida en `etl_processor.py`, ~500 líneas):
```python
class FEBDataETL:
    def __init__(self, ...):
        self.extractor = MongoDBExtractor(...)
        self.transformer = GameDataTransformer(...)
        self.loader = SQLiteLoader(...)
        self.metrics_calculator = PlayerMetricsCalculator(...)
        self.potential_scorer = PotentialScorer(...)
    
    def run_full_etl(self, ...):
        # Orquesta llamadas a componentes
        games = self.extractor.extract_games(...)
        for game in games:
            transformed = self.transformer.transform(game)
            self.loader.load(transformed)
        
        self.metrics_calculator.compute_all_metrics(...)
        self.potential_scorer.calculate_scores(...)
```

**Estrategia de Validación**:
1. Ejecutar `pytest -m regression` ANTES de dividir → baseline
2. Extraer un módulo a la vez
3. Actualizar imports en `etl_processor.py`
4. Ejecutar `pytest -m regression` → debe pasar 100%
5. Comparar resultados DB antes/después (opcional, golden master)
6. Repetir para siguiente módulo

---

#### B. División de Archivos UI Grandes

**`ui/data_admin.py`** (800 líneas) → 4 archivos:

1. **`ui/data_admin_main.py`** - Ventana principal y tabs
2. **`ui/widgets/scraping_widget.py`** - Tab de scraping
3. **`ui/widgets/etl_widget.py`** - Tab de ETL
4. **`ui/widgets/bio_widget.py`** - Tab de datos biográficos

**`ui/scouting_ui.py`** (600 líneas) → 3 archivos:

1. **`ui/scouting_main.py`** - Ventana principal
2. **`ui/widgets/roster_table.py`** - Tabla de roster
3. **`ui/widgets/chart_widgets.py`** - Gráficos y visualizaciones

**Validación**: Smoke tests UI (`pytest -m ui`)

---

#### C. División de xgboost_model.py (719 líneas)

**Dividir en**:
1. **`ml/model_trainer.py`** - Entrenamiento y feature engineering
2. **`ml/model_predictor.py`** - Predicciones y SHAP

**Validación**: Smoke tests ML + tests de predicción

---

### Fase 2: Estandarización de Lenguaje (Prioridad Media)

**Estado**: 🔄 Pendiente

**Archivos a Traducir** (docstrings, comments, variables a inglés):

**Orden de Prioridad**:
1. `src/ml/advanced_stats.py` (500 líneas)
   - Validación: Tests de sanidad post-traducción
2. `src/ml/etl_processor.py` (y módulos divididos)
3. `src/ml/normalization.py` (601 líneas)
4. `src/ml/identity_manager_cli.py` (463 líneas)
5. `src/ml/player_identity_matcher.py` (336 líneas)
6. `ui/scouting_ui.py` y `ui/data_admin.py`
   - **IMPORTANTE**: Mantener textos UI en español
7. `evaluate_team.py` (671 líneas)

**Proceso por Archivo**:
1. Ejecutar tests de regresión PRE-traducción
2. Traducir docstrings y comentarios
3. Renombrar variables/métodos (ej: `temporada` → `season`)
4. Actualizar imports si cambian nombres
5. Ejecutar `pytest tests/regression/` POST-traducción
6. Verificar que no hay cambios en lógica

**Herramientas**:
- Script automatizado para detectar strings en español
- Revisar con `ruff` y `mypy` tras cambios

---

### Fase 3: Mejoras de Modelos ML (Prioridad Media)

**Estado**: 🔄 Pendiente

#### Nuevas Features para xgboost_model.py

1. **Contexto de Oponente**
   - Fuerza del equipo oponente (avg team PER)
   - Nivel de competición del partido
   - Home/away splits

2. **Historial de Compañeros**
   - Avg PER de compañeros de equipo
   - Cambios de roster (new vs returning players)

3. **Momentum y Tendencias**
   - Performance trend últimos N partidos
   - Improvement rate (slope)

4. **Feature Engineering Avanzado**
   - Interacciones entre features (age × experience)
   - Polynomial features para métricas clave

#### Validación y Tuning

1. **Time-Series Cross-Validation**
   - Reemplazar split aleatorio por chronological
   - 5-fold time-series CV

2. **Hyperparameter Tuning**
   - Implementar Optuna para búsqueda
   - Guardar mejor configuración

3. **Ensemble Methods**
   - XGBoost + LightGBM
   - Voting/Stacking

4. **Monitoreo**
   - Logging de métricas (RMSE, R²) en metadata
   - Comparación con baseline models

**Validación**:
- Tests NO deben fallar por cambios en predicciones
- Tests deben validar: modelo entrena, predice valores válidos, SHAP funciona
- Métricas guardadas en metadata para comparación manual

---

### Fase 4: Completado de UI (Prioridad Media)

**Estado**: 🔄 Pendiente

#### Features Faltantes

1. **Tab "Análisis de Jugador"** (actualmente stub)
   - Gráfico de trayectoria de carrera
   - Gráfico game-by-game performance
   - Radar chart de fortalezas/debilidades
   - SHAP explanation para predicciones
   - Comparación con jugadores similares

2. **Funcionalidad de Export**
   - Export roster a CSV/Excel
   - Export gráficos como PNG
   - Generación de PDF reports

3. **Búsqueda Global**
   - Búsqueda de jugadores cross-team/season
   - Filtros avanzados (edad, posición, potential tier)
   - Guardado de filtros como presets

4. **Optimizaciones de Performance**
   - Cargar datos en QThread background
   - Caching de queries frecuentes
   - Paginación para tablas grandes

**Validación**:
- Smoke tests UI para nuevas funcionalidades
- Test manual de flujos de usuario

---

### Fase 5: Code Quality (Prioridad Baja)

**Estado**: 🔄 Pendiente

#### Linting y Type Hints

1. **Configurar ruff**
   - Crear `pyproject.toml` con reglas
   - Ejecutar `ruff check src/` y corregir

2. **Añadir Type Hints**
   - Prioridad: módulos ML y ETL
   - Ejecutar `mypy src/` progresivamente

3. **Pre-commit Hooks**
   - Instalar pre-commit
   - Configurar hooks: black, ruff, mypy

#### Documentación

1. **Docstrings faltantes**
   - `src/scraper/` (múltiples módulos)
   - Module-level docstrings con ejemplos

2. **Architecture Documentation**
   - Diagramas de flujo ETL
   - Diagramas de clases ML

---

## Uso de Utilidades Nuevas

### Reemplazar Código Duplicado

**Database Connections** (múltiples archivos):

ANTES:
```python
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
# ... operaciones ...
conn.commit()
conn.close()
```

DESPUÉS:
```python
from utils.database_context import get_db_connection

with get_db_connection(db_path) as conn:
    cursor = conn.cursor()
    # ... operaciones ...
    # Auto-commit y auto-close
```

**Season Parsing** (etl_processor.py, evaluate_team.py, etc.):

ANTES:
```python
start_year = int(temporada.split('-')[0])
end_year = int(temporada.split('-')[1])
```

DESPUÉS:
```python
from utils.season_utils import parse_season

start_year, end_year = parse_season(season)
```

**Progress Reporting** (etl_processor.py, scraper, etc.):

ANTES:
```python
for i, item in enumerate(items, 1):
    process(item)
    if i % 100 == 0:
        print(f"Progreso: {i}/{len(items)}")
        conn.commit()
```

DESPUÉS:
```python
from utils.progress_reporter import BatchProgressReporter

reporter = BatchProgressReporter(
    "Processing items",
    total=len(items),
    batch_size=100,
    on_batch=lambda: conn.commit()
)

for i, item in enumerate(items, 1):
    process(item)
    reporter.update(i)

reporter.complete()
```

---

## Criterios de Aceptación

### Por Cada Refactor

✅ **DEBE pasar**:
1. `pytest -m regression` - 100% pass
2. `pytest -m integration` - 100% pass
3. `pytest -m smoke` - 100% pass
4. Pipeline ETL completo ejecuta sin excepciones
5. Modelos ML entrenan y predicen sin crash
6. UI se carga sin errores

❌ **NO debe fallar por**:
- Cambios en valores exactos de predicciones ML
- Pequeñas diferencias en métricas calculadas (< 1%)
- Mejoras en algoritmos

🔴 **DEBE fallar si**:
- Pipeline lanza excepciones no manejadas
- Métricas generan NaN o valores imposibles
- Datos no se guardan en base de datos

---

## Timeline Estimado

| Fase | Tarea | Estimación | Prioridad |
|------|-------|-----------|-----------|
| 1A | Split etl_processor.py | 2-3 días | 🔴 Alta |
| 1B | Split UI files | 1 día | 🟡 Media |
| 1C | Split xgboost_model.py | 0.5 días | 🟡 Media |
| 2 | Estandarizar a inglés | 2-3 días | 🟡 Media |
| 3 | Mejoras ML | 2-3 días | 🟡 Media |
| 4 | Completar UI | 2-3 días | 🟡 Media |
| 5 | Code quality | 1-2 días | 🟢 Baja |

**Total**: 10-15 días desarrollo

---

## Comandos Útiles

### Testing
```bash
# Validación rápida (<30 seg)
python scripts/quick_validation.py

# Suite completa de regresión
python scripts/run_regression_suite.py

# Con coverage
python scripts/run_regression_suite.py --coverage

# Tests específicos
pytest tests/integration/test_etl_sanity.py -v
pytest -m smoke -v
pytest -m "not ui" -v  # Skip UI tests
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint
ruff check src/

# Type check
mypy src/

# Run all quality checks
pre-commit run --all-files
```

### Instalación
```bash
# Dependencias de desarrollo
pip install -r requirements_dev.txt

# Pre-commit hooks
pre-commit install
```

---

## Notas Importantes

1. **Tests de Regresión son Red de Seguridad**: Ejecutar SIEMPRE antes y después de cambios mayores

2. **Refactor Incremental**: Dividir archivos UNO a la vez, validar, luego siguiente

3. **ML Improvements Flexibles**: Tests ML validan funcionamiento, NO valores exactos

4. **Documentación en Español**: Mantener docs/ y textos UI en español, código en inglés

5. **Backup Before Major Changes**: Git commit frecuente, branches para features grandes

---

## Contacto y Recursos

- **Testing Guide**: `docs/TESTING_GUIDE.md`
- **Architecture**: `docs/ARCHITECTURE.md` (actualizar post-refactor)
- **ML System**: `docs/ML_SYSTEM.md` (actualizar con nuevas features)
