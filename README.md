# ScoutingFEB

Sistema de scouting de baloncesto basado en IA para predecir el rendimiento futuro de jugadores usando datos estadísticos de la Federación Española de Baloncesto (FEB).

## 🎯 Características Principales

- **Scraping Automático**: Recopilación de datos de partidos desde la web de la FEB
- **Sistema Incremental**: Solo procesa encuentros nuevos (ahorro 97-98%)
- **Gestión de Identidades**: Sistema inteligente para resolver duplicados de jugadores
- **Consolidación de Carreras**: Rastrea jugadoras a través de 25+ temporadas
- **ETL Completo**: Pipeline de transformación MongoDB → SQLite
- **Machine Learning Avanzado**: Modelos XGBoost prediciendo promedios de temporada (R²=0.88)
- **Feature Engineering**: Per-36, rolling windows, team ratios, consistency metrics
- **Interpretabilidad**: Explicaciones SHAP de las predicciones
- **Base de Datos Dual**: MongoDB (raw) + SQLite (procesado)
- **Testing Robusto**: Suite completa de tests de regresión para garantizar estabilidad

## 🚀 Resultados del Sistema ML

**Últimas mejoras (Feb 2026):**
- **R² = 0.880** para predicción de puntos (mejora del 89% vs baseline)
- **R² = 0.886** para predicción de eficiencia (mejora del 124% vs baseline)
- **152,577 registros** de entrenamiento con 2,107 jugadoras únicas
- **6,725 identidades consolidadas** rastreando carreras completas

Ver detalles: [docs/ML_IMPROVEMENTS_RESULTS.md](docs/ML_IMPROVEMENTS_RESULTS.md)

## 🆕 Sistema de Gestión de Identidades

El sistema ahora incluye un **sofisticado sistema de perfiles de jugadores** que resuelve el problema de identificación única:

### Problema Resuelto
- ❌ Un mismo jugador puede tener múltiples IDs FEB entre temporadas
- ❌ Nombres en formatos inconsistentes ("J. PÉREZ", "JUAN PÉREZ", "PÉREZ, JUAN")
- ❌ Fechas de nacimiento no siempre disponibles

### Solución Implementada
- ✅ **Perfiles únicos**: Cada aparición (nombre+equipo+temporada) genera un perfil
- ✅ **Consolidación Automática**: 16,528 perfiles → 6,725 identidades únicas (score ≥0.95)
- ✅ **Candidate Matching**: Algoritmo de similitud automático con scoring (0.0-1.0)
- ✅ **Validación Humana**: El staff confirma identidades, el sistema aprende
- ✅ **Scoring de Potencial**: Identificación automática de jugadores prometedores
- ✅ **Tracking Multi-Temporada**: Rastrea carreras de hasta 19 temporadas

**Ver documentación completa:** [docs/PLAYER_IDENTITY_SYSTEM.md](docs/PLAYER_IDENTITY_SYSTEM.md)

## 🏆 Estado del Proyecto (Febrero 2026)

**✅ PRODUCTION-READY** - Código refactorizado y listo para producción

### Métricas de Calidad
- **Complejidad promedio**: A (4.86) - Excelente
- **Funciones críticas**: 0 (eliminadas 100%)
- **Puntuación**: 9.4/10 ⭐⭐⭐⭐⭐
- **Tests**: 284 tests, 100% passing
- **Cobertura**: Test-to-code ratio 1.36:1

Ver detalles: [docs/REFACTORING_FINAL_REPORT.md](docs/REFACTORING_FINAL_REPORT.md) | [docs/FINAL_COMPLEXITY_AUDIT.md](docs/FINAL_COMPLEXITY_AUDIT.md)

## Descripción

ScoutingFEB es un proyecto que combina web scraping, análisis de datos y inteligencia artificial para ayudar en el proceso de scouting de jugadores de baloncesto. El sistema recopila datos detallados de partidos de la FEB y los almacena en una base de datos MongoDB para su posterior análisis.

## Características

- ✅ **Scraping automático de datos FEB**: Obtiene todos los partidos de competiciones FEB
- ✅ **Sistema incremental**: Solo procesa encuentros nuevos, ahorrando tiempo y recursos
- ✅ **Múltiples temporadas y grupos**: Recopila datos históricos completos
- ✅ **Separación por género**: Almacenamiento separado para competiciones masculinas y femeninas
- ✅ **Base de datos MongoDB**: Almacenamiento eficiente y escalable
- ✅ **Datos detallados**: Incluye estadísticas de jugadores, play-by-play, y shot charts
- ✅ **Sistema de logging**: Seguimiento completo del proceso de scraping

## Estructura del Proyecto

```
ScoutingFEB/
├── ui/                                 # 🆕 Interfaz gráfica
│   ├── __init__.py
│   ├── scouting_ui.py                 # Ventana principal
│   └── data_admin.py                  # Widget de administración
│
├── src/
│   ├── __init__.py
│   ├── main.py                         # Scraper principal
│   ├── config.py                       # Configuración
│   ├── utils.py                        # Utilidades
│   ├── run_scraping.py                 # Script unificado de scraping
│   ├── examples_incremental.py         # Ejemplos sistema incremental
│   ├── test_incremental.py             # Tests
│   ├── run_ml_pipeline.py              # Pipeline completo ML
│   │
│   ├── scraper/                        # Módulo de scraping
│   │   ├── __init__.py
│   │   ├── api_client.py
│   │   ├── constants.py
│   │   ├── data_processor.py
│   │   ├── feb_scraper.py
│   │   ├── token_manager.py
│   │   └── web_client.py
│   │
│   ├── database/                       # Módulo de bases de datos
│   │   ├── __init__.py
│   │   ├── mongodb_client.py          # Cliente MongoDB
│   │   └── sqlite_schema.py           # Esquema SQLite
│   │
│   └── ml/                             # Módulo de Machine Learning
│       ├── __init__.py
│       ├── etl_processor.py           # ETL MongoDB → SQLite
│       ├── xgboost_model.py           # Modelos XGBoost + SHAP
│       ├── name_normalizer.py         # Normalización de nombres
│       ├── player_identity_matcher.py # Matching de identidades
│       └── identity_manager_cli.py    # CLI de gestión
│
├── docs/                               # 📚 Documentación
│   ├── UI_README.md                   # Guía de interfaz gráfica
│   ├── DATA_ADMIN_GUIDE.md            # Guía de administración de datos
│   ├── ARCHITECTURE.md                # Arquitectura completa
│   ├── ML_SYSTEM.md                   # Sistema ML
│   ├── ML_EXECUTIVE_SUMMARY.md        # Resumen ejecutivo ML
│   └── PLAYER_IDENTITY_SYSTEM.md      # Gestión de identidades
│
├── examples/                           # Scripts de ejemplo
│   └── identity_system_examples.py    # Ejemplos del sistema
│
├── models/                             # Modelos ML entrenados
│   ├── *.joblib                       # Modelos serializados
│   ├── *_metadata.json                # Metadata
│   └── *_shap_summary.png             # Gráficos SHAP
│
├── run_ui.py                          # 🆕 Lanzador de interfaz gráfica
├── evaluate_team.py                   # Script de evaluación de equipos
├── requirements.txt                   # Dependencias base
├── requirements_ui.txt                # 🆕 Dependencias UI (PyQt6)
├── README.md                          # Este archivo
├── QUICKSTART.md                      # Guía rápida
├── CHANGELOG.md                       # Historial de cambios
└── LICENSE
```

## Requisitos

### Software Necesario
- Python 3.8 o superior
- MongoDB 4.0 o superior (para datos raw)
- SQLite 3 (incluido con Python)
- Conexión a Internet para scraping

### Librerías Python
Ver `requirements.txt` para la lista completa. Principales:
- **Scraping**: requests, beautifulsoup4, pymongo
- **ML**: xgboost, shap, scikit-learn, pandas, numpy
- **Visualización**: matplotlib

## Instalación

1. **Clonar o descargar el repositorio**

2. **Instalar MongoDB** (si no lo tienes instalado)
   
   Windows:
   ```powershell
   # Descargar desde: https://www.mongodb.com/try/download/community
   # O usar Chocolatey:
   choco install mongodb
   ```

   Asegúrate de que MongoDB esté ejecutándose:
   ```powershell
   # Iniciar MongoDB como servicio
   net start MongoDB
   ```

3. **Instalar dependencias de Python**
   ```powershell
   cd ScoutingFEB
   pip install -r requirements.txt
   ```

## 🚀 Inicio Rápido

### Opción 1: Solo Scraping

```powershell
# 1. Asegurarte de que MongoDB esté ejecutándose
net start MongoDB

# 2. Ejecutar scraper
cd src
python main.py
```

### Opción 2: Pipeline Completo (Scraping + ETL + ML)

```powershell
# Ejecutar pipeline completo con sistema de perfiles
cd src
python run_ml_pipeline.py

# Opciones avanzadas:
python run_ml_pipeline.py --limit 100      # Prueba con 100 partidos
python run_ml_pipeline.py --skip-etl       # Saltar ETL (usar datos existentes)
python run_ml_pipeline.py --skip-training  # Saltar entrenamiento
```

Este comando ejecutará:
1. ✅ Creación de esquema SQLite (con tablas de perfiles)
2. ✅ Proceso ETL (MongoDB → SQLite) con gestión de identidades
3. ✅ Generación de candidatos de matching automático
4. ✅ Cálculo de scores de potencial
5. ✅ Entrenamiento de modelos XGBoost
6. ✅ Análisis SHAP de interpretabilidad
7. ✅ Predicciones de ejemplo

### Opción 3: Sistema de Gestión de Identidades

```powershell
# Ver candidatos de alta confianza
python src/ml/identity_manager_cli.py list-candidates --min-score 0.70

# Ver detalles de un perfil
python src/ml/identity_manager_cli.py profile 1234

# Validar un candidato
python src/ml/identity_manager_cli.py validate 123 confirmed

# Ver jugadores con alto potencial
python src/ml/identity_manager_cli.py potential --min-score 0.60

# Ver estadísticas de validación
python src/ml/identity_manager_cli.py stats

# Ejecutar ejemplos interactivos
python examples/identity_system_examples.py
```

**Ver guía completa:** [PLAYER_IDENTITY_SYSTEM.md](PLAYER_IDENTITY_SYSTEM.md)

## 📚 Documentación

### Guías de Usuario
- **[QUICKSTART.md](QUICKSTART.md)** - Guía rápida de inicio
- **[docs/UI_README.md](docs/UI_README.md)** - 🆕 Documentación de interfaz gráfica
- **[docs/DATA_ADMIN_GUIDE.md](docs/DATA_ADMIN_GUIDE.md)** - 🆕 Guía de administración de datos

### Documentación Técnica
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Arquitectura completa del sistema
- **[docs/PLAYER_IDENTITY_SYSTEM.md](docs/PLAYER_IDENTITY_SYSTEM.md)** - Sistema de gestión de identidades
- **[docs/ML_SYSTEM.md](docs/ML_SYSTEM.md)** - Sistema de Machine Learning con XGBoost + SHAP
- **[docs/ML_EXECUTIVE_SUMMARY.md](docs/ML_EXECUTIVE_SUMMARY.md)** - Resumen ejecutivo del sistema ML

### Implementación y Cambios
- **[IMPLEMENTATION_SUMMARY_IDENTITIES.md](IMPLEMENTATION_SUMMARY_IDENTITIES.md)** - 🆕 Resumen de implementación del sistema de identidades
- **[CHANGELOG.md](CHANGELOG.md)** - Historial de cambios y versiones

### Diagramas y Ejemplos
- **[INCREMENTAL_SYSTEM_DIAGRAM.md](INCREMENTAL_SYSTEM_DIAGRAM.md)** - Diagramas del sistema incremental
- **[examples/identity_system_examples.py](examples/identity_system_examples.py)** - 🆕 Ejemplos interactivos del sistema

## Uso

### Interfaz Gráfica (Recomendado) 🆕

La forma más fácil de usar ScoutingFEB es a través de la interfaz gráfica:

```powershell
# Instalar dependencias UI (solo primera vez)
pip install -r requirements_ui.txt

# Lanzar aplicación
python run_ui.py
```

**La interfaz gráfica incluye:**
- 🏀 **Evaluación de Equipos**: Visualiza plantillas con proyecciones ML
- ⚙️ **Administración de Datos**: Scraping, ETL, gestión biográfica
- 👤 **Análisis de Jugadoras**: (Próximamente)
- 📊 **Estadísticas**: (Próximamente)

**Guías detalladas:**
- [docs/UI_README.md](docs/UI_README.md) - Documentación completa de la interfaz
- [docs/DATA_ADMIN_GUIDE.md](docs/DATA_ADMIN_GUIDE.md) - Guía de administración de datos

### Sistema de Scraping Incremental

ScoutingFEB incluye un **sistema de scraping incremental** que reduce significativamente el costo de la recopilación de datos al procesar solo los encuentros nuevos.

📖 **[Ver documentación completa del sistema incremental](INCREMENTAL_SCRAPING.md)**

**Uso rápido con el script unificado:**
```powershell
# Ejecutar el script interactivo
python src/run_scraping.py

# Menú con opciones:
# 1. Listar competiciones
# 2. Scraping interactivo (incremental)
# 3. Scraping completo (re-scraping)
# 4. Múltiples competiciones
# 5-8. Consultas y administración
```

**Uso programático:**
```python
from src.main import FEBScoutingScraper

scraper = FEBScoutingScraper()

# Modo incremental (por defecto) - solo procesa encuentros nuevos
stats = scraper.scrape_competition_by_name("LF2", incremental=True)

# Modo completo - procesa todos los encuentros
stats = scraper.scrape_competition_by_name("LF2", incremental=False)

scraper.close()
```

### ⏰ Soporte para Partidos Antiguos (Pre-2019-20)

ScoutingFEB incluye **soporte automático para partidos de temporadas anteriores a 2019-20**, que utilizan un formato de datos diferente (HTML embebido en lugar de API JSON).

**Características:**
- ✅ **Detección automática**: El sistema detecta automáticamente si un partido es antiguo (API devuelve 404)
- ✅ **Fallback HTML**: Parsea automáticamente los datos del HTML de la página
- ✅ **Datos completos**: Extrae las mismas estadísticas que los partidos modernos:
  - Información del partido (equipos, marcador, temporada)
  - Estadísticas detalladas de jugadores (20+ métricas)
  - Parciales por cuarto
  - Metadatos (árbitros, fecha, hora)
- ✅ **Sin cambios de código**: Funciona transparentemente con la misma API

**Ejemplo:**
```python
from src.main import FEBScoutingScraper

scraper = FEBScoutingScraper()

# Funciona automáticamente para partidos antiguos
# Ejemplo: LF2 2019/2020 - SEGLE XXI 72-68 BARÇA CBS
data = scraper.scrape_match("2098897")

# Los datos incluyen un campo 'data_source' para identificar el origen
print(data.get('data_source'))  # 'html_legacy' para partidos antiguos
print(f"{data['home_team']} {data['home_score']}-{data['away_score']} {data['away_team']}")
print(f"Jugadores: {len(data['players'])}")

scraper.close()
```

**Notas técnicas:**
- El token de autenticación se obtiene del campo `_ctl0_token` en el HTML
- Los datos se extraen del panel estático (`id="EstaticoPanel"`)
- El campo `data_source` será `"html_legacy"` en lugar de `"api"` para identificar la fuente

Ver [CHANGELOG.md](CHANGELOG.md) v0.4.3 para más detalles técnicos.

---

### 1. Listar competiciones disponibles

Para ver todas las competiciones FEB disponibles:

```powershell
python src/run_scraping.py
# Selecciona opción 1
```

### 2. Scraping de una competición específica

Edita el archivo `main.py` y descomenta las líneas relevantes en la función `main()`:

**Opción A: Por nombre de competición**
```python
# Busca automáticamente la competición por nombre
scraper.scrape_competition_by_name("LF2")
```

**Opción B: Por URL directa**
```python
stats = scraper.scrape_competition(
    "https://baloncestoenvivo.feb.es/calendario/lf2/9/2024",
    "LF2 - Liga Femenina 2",
    "fem"  # 'masc' o 'fem'
)
```

Luego ejecuta:
```powershell
python main.py
```

### 3. Uso programático

También puedes usar el scraper en tu propio código:

```python
from main import FEBScoutingScraper

# Inicializar el scraper
scraper = FEBScoutingScraper(
    mongodb_uri="mongodb://localhost:27017/",
    database_name="scouting_feb"
)

# Listar competiciones
competitions = scraper.list_available_competitions()

# Scraping de una competición
stats = scraper.scrape_competition_by_name("LF2")

# Cerrar conexiones
scraper.close()
```

## Colecciones de MongoDB

Los datos se almacenan en múltiples colecciones:

### Colecciones de Partidos
- **all_feb_games_masc**: Partidos de competiciones masculinas
- **all_feb_games_fem**: Partidos de competiciones femeninas

### Colección de Estado (Sistema Incremental)
- **scraping_state**: Guarda el estado del scraping por competición/temporada/grupo para el procesamiento incremental

Cada documento de partido contiene:
- **HEADER**: Información del partido (equipos, resultado, fecha, lugar)
- **BOXSCORE**: Estadísticas detalladas de jugadores
- **PLAYBYPLAY**: Jugada a jugada del partido
- **SHOTCHART**: Información de todos los tiros
- Metadatos adicionales (competición, temporada, grupo, género)

## Configuración

### Cambiar la base de datos MongoDB

Por defecto, el sistema usa:
- URI: `mongodb://localhost:27017/`
- Base de datos: `scouting_feb`

Para cambiar esto, modifica los parámetros al inicializar `FEBScoutingScraper`:

```python
scraper = FEBScoutingScraper(
    mongodb_uri="mongodb://tu-servidor:27017/",
    database_name="tu_base_de_datos"
)
```

### Configurar logging

El sistema genera logs en:
- Consola (stdout)
- Archivo: `scouting_feb.log`

Puedes modificar el nivel de logging en `main.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Cambia a DEBUG para más detalle
    # ...
)
```

## Características del Scraping

- **Automático**: Detecta automáticamente todas las temporadas y grupos disponibles
- **Incremental**: Solo procesa encuentros nuevos (sistema de estado con MongoDB)
- **Configurable**: Puede forzarse un re-scraping completo si es necesario
- **Resiliente**: Maneja errores y continúa con el siguiente partido
- **Respetuoso**: Incluye delays entre peticiones (0.5 segundos)
- **Completo**: Obtiene boxscore, play-by-play y shot charts
- **Trazable**: Guarda el estado de cada scraping con timestamps

## Ejemplo de Salida

```
=== Available FEB Competitions ===

- LF2 - Liga Femenina 2 (fem) - https://...
- LEB ORO - Liga Masculina (masc) - https://...
...

=== Starting scraping process ===

2025-01-12 10:30:00 - INFO - Starting scrape for LF2 (fem)
2025-01-12 10:30:00 - INFO - Found 5 seasons
2025-01-12 10:30:01 - INFO - Processing season: 2024/25
2025-01-12 10:30:02 - INFO - Found 4 groups in season 2024/25
2025-01-12 10:30:03 - INFO - Found 132 matches in 2024/25 - Grupo A
...
```

## 🧪 Testing y Desarrollo

ScoutingFEB incluye una **suite completa de tests de regresión** para garantizar que la funcionalidad persiste tras refactorizaciones y mejoras.

### Instalación de Dependencias de Testing

```powershell
pip install -r requirements_dev.txt
```

### Ejecutar Tests

```powershell
# Validación rápida (< 30 seg) - recomendado durante desarrollo
python scripts/quick_validation.py

# Suite completa de regresión
python scripts/run_regression_suite.py

# Con reporte de cobertura
python scripts/run_regression_suite.py --coverage

# Tests específicos
pytest tests/integration/test_etl_sanity.py -v
pytest -m smoke -v                    # Solo smoke tests
pytest -m "not ui" -v                 # Excluir tests UI
```

### Tipos de Tests

- **Regresión (`@pytest.mark.regression`)**: Tests end-to-end que validan flujos completos
- **Integración (`@pytest.mark.integration`)**: Validación de métricas en rangos válidos, sin NaN/Inf
- **Humo (`@pytest.mark.smoke`)**: Tests rápidos de carga básica sin crash

### Filosofía de Testing

- ✅ **Objetivo**: Garantizar que el sistema funciona tras cambios, NO buscar 100% cobertura
- ✅ **Enfoque**: Tests funcionales que validan comportamiento razonable
- ✅ **ML Flexible**: Tests ML validan que funciona, NO valores exactos (permitiendo mejoras)
- ❌ **Evitar**: Over-testing de código trivial cubierto en tests funcionales

**Documentación completa:** [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)

### Plan de Refactorización

El proyecto está en proceso de refactorización para mejorar mantenibilidad:
- División de archivos grandes (etl_processor.py: 2,349 líneas → 5 módulos)
- Estandarización de código a inglés (manteniendo docs en español)
- Eliminación de código duplicado (utilidades compartidas)
- Mejoras en modelos ML (nuevas features, hyperparameter tuning)

**Ver plan completo:** [docs/REFACTORING_PLAN.md](docs/REFACTORING_PLAN.md)

## Próximos Pasos

Este proyecto está diseñado para ser la base de un sistema de scouting más completo. Los siguientes pasos incluirían:

1. ✅ **Análisis estadístico**: Procesamiento de datos para extraer métricas avanzadas (COMPLETADO)
2. ✅ **Modelos de IA**: Predicción de rendimiento futuro de jugadores (COMPLETADO - R²=0.88)
3. **API REST**: Exposición de datos y predicciones
4. **Dashboard web**: Visualización de datos y análisis
5. **Sistema de alertas**: Notificaciones sobre jugadores prometedores

## Solución de Problemas

### MongoDB no se conecta

Verifica que MongoDB esté ejecutándose:
```powershell
# Windows
net start MongoDB

# O comprueba el estado
sc query MongoDB
```

### Errores de scraping

- Verifica tu conexión a Internet
- La web de la FEB puede estar temporalmente no disponible
- Revisa el archivo `scouting_feb.log` para más detalles

### Dependencias faltantes

```powershell
pip install -r requirements.txt --upgrade
```

## 📚 Documentación

Toda la documentación técnica está organizada en la carpeta [docs/](docs/):

- **[docs/INDEX.md](docs/INDEX.md)** - Índice completo de documentación
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Arquitectura del sistema
- **[docs/REFACTORING_FINAL_REPORT.md](docs/REFACTORING_FINAL_REPORT.md)** - Informe de refactoring completo
- **[docs/TEST_COVERAGE_REPORT.md](docs/TEST_COVERAGE_REPORT.md)** - Reporte de tests
- **[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)** - Guía de testing
- **[docs/UI_README.md](docs/UI_README.md)** - Manual de interfaz de usuario

## Licencia

Este proyecto es de código abierto para fines educativos y de investigación.

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue o pull request.

## Contacto

Para preguntas o sugerencias, abre un issue en el repositorio.

---

**Nota**: Este proyecto no está afiliado con la Federación Española de Baloncesto. Los datos se obtienen de fuentes públicas para fines de análisis deportivo.
