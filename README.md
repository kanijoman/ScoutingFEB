# ScoutingFEB

Sistema de scouting de baloncesto basado en IA para predecir el rendimiento futuro de jugadores usando datos estadísticos de la Federación Española de Baloncesto (FEB).

## 🎯 Características Principales

- **Scraping Automático**: Recopilación de datos de partidos desde la web de la FEB
- **Sistema Incremental**: Solo procesa encuentros nuevos (ahorro 97-98%)
- **ETL Completo**: Pipeline de transformación MongoDB → SQLite
- **Machine Learning**: Modelos XGBoost para predicción de rendimiento
- **Interpretabilidad**: Explicaciones SHAP de las predicciones
- **Base de Datos Dual**: MongoDB (raw) + SQLite (procesado)

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
├── src/
│   ├── __init__.py
│   ├── main.py                         # Scraper principal
│   ├── config.py                       # Configuración
│   ├── utils.py                        # Utilidades
│   ├── examples.py                     # Ejemplos de uso
│   ├── examples_incremental.py         # Ejemplos sistema incremental
│   ├── test_incremental.py             # Tests
│   ├── run_ml_pipeline.py              # 🆕 Pipeline completo ML
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
│   │   └── sqlite_schema.py           # 🆕 Esquema SQLite
│   │
│   └── ml/                             # 🆕 Módulo de Machine Learning
│       ├── __init__.py
│       ├── etl_processor.py           # ETL MongoDB → SQLite
│       └── xgboost_model.py           # Modelos XGBoost + SHAP
│
├── models/                             # 🆕 Modelos ML entrenados
│   ├── *.joblib                       # Modelos serializados
│   ├── *_metadata.json                # Metadata
│   └── *_shap_summary.png             # Gráficos SHAP
│
├── requirements.txt                    # Dependencias
├── README.md                          # Este archivo
├── QUICKSTART.md                      # Guía rápida
├── CHANGELOG.md                       # Historial de cambios
├── LICENSE
│
├── INCREMENTAL_SCRAPING.md            # 📚 Doc: Sistema incremental
├── INCREMENTAL_SYSTEM_DIAGRAM.md      # 📚 Doc: Diagramas
├── ML_SYSTEM.md                       # 📚 Doc: Sistema ML
└── ARCHITECTURE.md                    # 📚 Doc: Arquitectura completa
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
# Ejecutar pipeline completo
cd src
python run_ml_pipeline.py

# Opciones avanzadas:
python run_ml_pipeline.py --limit 100      # Prueba con 100 partidos
python run_ml_pipeline.py --skip-etl       # Saltar ETL (usar datos existentes)
python run_ml_pipeline.py --skip-training  # Saltar entrenamiento
```

Este comando ejecutará:
1. ✅ Creación de esquema SQLite
2. ✅ Proceso ETL (MongoDB → SQLite)
3. ✅ Entrenamiento de modelos XGBoost
4. ✅ Análisis SHAP de interpretabilidad
5. ✅ Predicciones de ejemplo

## 📚 Documentación

### Guías Principales
- **[QUICKSTART.md](QUICKSTART.md)** - Guía rápida de inicio
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Arquitectura completa del sistema
- **[ML_SYSTEM.md](ML_SYSTEM.md)** - Sistema de Machine Learning con XGBoost + SHAP
- **[INCREMENTAL_SCRAPING.md](INCREMENTAL_SCRAPING.md)** - Sistema de scraping incremental

### Diagramas y Ejemplos
- **[INCREMENTAL_SYSTEM_DIAGRAM.md](INCREMENTAL_SYSTEM_DIAGRAM.md)** - Diagramas del sistema incremental
- **[CHANGELOG.md](CHANGELOG.md)** - Historial de cambios y versiones

## Uso

### Sistema de Scraping Incremental

ScoutingFEB incluye un **sistema de scraping incremental** que reduce significativamente el costo de la recopilación de datos al procesar solo los encuentros nuevos.

📖 **[Ver documentación completa del sistema incremental](INCREMENTAL_SCRAPING.md)**

**Uso rápido:**
```python
from src.main import FEBScoutingScraper

scraper = FEBScoutingScraper()

# Modo incremental (por defecto) - solo procesa encuentros nuevos
stats = scraper.scrape_competition_by_name("LF2", incremental=True)

# Modo completo - procesa todos los encuentros
stats = scraper.scrape_competition_by_name("LF2", incremental=False)

scraper.close()
```

**Ejemplos interactivos:**
```powershell
python src/examples_incremental.py
```

### 1. Listar competiciones disponibles

Para ver todas las competiciones FEB disponibles:

```powershell
cd src
python main.py
```

Esto mostrará una lista de todas las competiciones con su género detectado automáticamente.

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

## Próximos Pasos

Este proyecto está diseñado para ser la base de un sistema de scouting más completo. Los siguientes pasos incluirían:

1. **Análisis estadístico**: Procesamiento de datos para extraer métricas avanzadas
2. **Modelos de IA**: Predicción de rendimiento futuro de jugadores
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

## Licencia

Este proyecto es de código abierto para fines educativos y de investigación.

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue o pull request.

## Contacto

Para preguntas o sugerencias, abre un issue en el repositorio.

---

**Nota**: Este proyecto no está afiliado con la Federación Española de Baloncesto. Los datos se obtienen de fuentes públicas para fines de análisis deportivo.
