# Guía de Re-Scraping Completo

## 1. Limpiar Base de Datos MongoDB (Opcional)

Si quieres empezar completamente desde cero:

```powershell
python clean_database.py
```

Esto eliminará:
- `all_feb_games_fem` - Partidos femeninos
- `all_feb_games_masc` - Partidos masculinos  
- `scraping_state` - Estados de scraping incremental

## 2. Ejecutar Scraping

### Scraping Interactivo (Recomendado)

```powershell
python src/run_scraping.py
```

Menú interactivo para seleccionar:
- Competiciones específicas
- Modo incremental vs completo
- Género (femenino/masculino)

### Scraping Automático de Todas las Competiciones

```python
from src.main import FEBScoutingScraper

scraper = FEBScoutingScraper()

# Scraping incremental (solo partidos nuevos)
scraper.scrape_all_available_competitions(
    gender='fem',  # o 'masc' o None para ambos
    incremental=True
)

scraper.close()
```

## 3. Verificar Datos

### MongoDB

```python
from src.database.mongodb_client import MongoDBClient

db = MongoDBClient()

# Contar partidos femeninos
fem_count = db.get_collection("all_feb_games_fem").count_documents({})
print(f"Partidos femeninos: {fem_count}")

# Contar partidos masculinos
masc_count = db.get_collection("all_feb_games_masc").count_documents({})
print(f"Partidos masculinos: {masc_count}")

# Ver temporadas disponibles
seasons = db.get_collection("all_feb_games_fem").distinct("HEADER.season")
print(f"Temporadas: {sorted(seasons)}")
```

## 4. Ejecutar Pipeline ML

Una vez tengas datos scrapeados:

```powershell
python src/run_ml_pipeline.py
```

Esto:
1. Extrae datos de MongoDB
2. Los transforma (ETL) con normalización Z-score y pesos de partidos
3. Los carga en SQLite (`scouting_feb.db`)
4. Entrena modelos XGBoost
5. Genera predicciones

## 5. Sistema de Ponderación de Partidos

El sistema automáticamente asigna pesos a los partidos según su importancia:

| Tipo | Peso | Aplicación |
|------|------|------------|
| 🏆 Final | 1.5x | Partidos definitivos |
| ⭐ Play-offs | 1.4x | Eliminatorias |
| 🏅 Copa | 1.3x | Torneos de copa |
| 🎖️ Supercopa | 1.2x | Supercopa |
| 📊 Liga Regular | 1.0x | Temporada regular |

Los pesos se calculan automáticamente basándose en el campo `group_name` de cada partido.

## 6. Estructura de Datos

### MongoDB (Raw Data)
```json
{
  "HEADER": {
    "game_code": 2479683,
    "season": "2025/2026",
    "competition_name": "LF ENDESA",
    "group": "Liga Regular \"A\"",
    "gender": "fem",
    "starttime": "2025-10-05T18:00:00",
    "TEAM": [...]
  },
  "BOXSCORE": {
    "PLAYER": [...]
  }
}
```

### SQLite (Processed Data)
- `games` - Información de partidos con `match_weight`
- `players` - Catálogo de jugadores
- `player_game_stats` - Estadísticas por partido/jugador
- `competitions`, `teams` - Dimensiones

## 7. Troubleshooting

### Problema: "No token available"
- El token manager se refresca automáticamente
- Si persiste, verifica conectividad con baloncestoenvivo.feb.es

### Problema: "API returned 404"
- El sistema automáticamente usa el legacy parser para partidos antiguos (pre-2019)
- Normal para partidos históricos

### Problema: Partidos duplicados
- El sistema incremental evita duplicados automáticamente
- Usa `game_code` como clave única

### Problema: Partidos futuros sin datos
- Normal - los partidos futuros no tienen estadísticas todavía
- El scraper los saltará automáticamente

## 8. Logs

Los logs se guardan en:
- `scouting_feb.log` - Log principal del scraping
- Consola - Output en tiempo real

## 9. Rendimiento

- **Incremental**: ~97-98% más rápido (solo partidos nuevos)
- **Completo**: Puede tardar varias horas dependiendo de competiciones
- **Recomendación**: Usar modo incremental para actualizaciones

## 10. Monitoreo

Durante el scraping verás:
```
Processing season: 2024/2025
Found 240 matches in regular calendar
Found 2 series/phases for season 2024/2025
  - Play-Offs (ID: 44123)
  - Copa de la Reina (ID: 44124)
Total unique matches for season 2024/2025: 267
Incremental mode: 245 matches already processed, 22 new matches to process
```

Esto indica:
- Temporada actual
- Partidos encontrados
- Series/fases adicionales (Play-offs, Copa, etc.)
- Partidos ya procesados vs nuevos
