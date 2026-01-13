# Sistema de Scraping Incremental

## Descripción

El sistema de scraping incremental permite añadir nuevos encuentros sin tener que recorrer cada vez toda la lista de encuentros, reduciendo significativamente el costo de la recopilación de datos.

## Cómo Funciona

### 1. **Colección de Estado** (`scraping_state`)

El sistema mantiene una colección en MongoDB llamada `scraping_state` que guarda el estado de cada scraping por:
- Competición
- Temporada
- Grupo

Cada documento de estado contiene:
```json
{
  "_id": "all_feb_games_masc_LF2_2024-2025_Grupo A",
  "competition_name": "LF2",
  "season": "2024-2025",
  "group": "Grupo A",
  "collection_name": "all_feb_games_masc",
  "last_match_code": "123456",
  "total_matches": 132,
  "last_update": "2026-01-12T10:30:00.000Z"
}
```

### 2. **Procesamiento Incremental**

Cuando se ejecuta un scraping en modo incremental (activado por defecto):

1. El sistema obtiene la lista completa de encuentros de la web de la FEB
2. Consulta la base de datos para ver qué encuentros ya están procesados
3. **Solo procesa los encuentros nuevos** que no están en la base de datos
4. Actualiza el estado después de procesar cada grupo

### 3. **Ventajas**

- ⚡ **Más rápido**: Solo procesa encuentros nuevos
- 💰 **Más económico**: Reduce el número de peticiones a la API
- 🔄 **Actualizable**: Puedes ejecutar el scraping regularmente para añadir nuevos encuentros
- 📊 **Trazable**: Sabes exactamente cuándo se procesó cada grupo por última vez

## Uso

### Modo Incremental (por defecto)

```python
from src.main import FEBScoutingScraper

scraper = FEBScoutingScraper()

# Solo procesa encuentros nuevos
stats = scraper.scrape_competition_by_name("LF2", incremental=True)
```

### Modo Completo (re-scraping total)

Si necesitas volver a procesar todos los encuentros:

```python
# Procesa TODOS los encuentros, incluso los ya existentes
stats = scraper.scrape_competition_by_name("LF2", incremental=False)
```

### Configuración en `config.py`

```python
SCRAPING_CONFIG = {
    "incremental_mode": True,  # Activa el modo incremental
    "force_full_rescrape": False  # Si es True, ignora el modo incremental
}
```

## Métodos Añadidos

### MongoDBClient

#### `get_scraping_state(competition_name, season, group, collection_name)`
Obtiene el estado del scraping para un grupo específico.

#### `update_scraping_state(competition_name, season, group, collection_name, last_match_code, total_matches, timestamp)`
Actualiza el estado después de procesar un grupo.

#### `get_all_processed_matches(competition_name, season, group, collection_name)`
Obtiene la lista de códigos de encuentros ya procesados para un grupo.

## Ejemplo de Uso Completo

```python
from src.main import FEBScoutingScraper

# Inicializar scraper
scraper = FEBScoutingScraper()

try:
    # Primera ejecución: procesa todos los encuentros
    print("Primera ejecución - procesando todos los encuentros...")
    stats1 = scraper.scrape_competition_by_name("LF2")
    print(f"Procesados: {stats1['total_matches_scraped']}")
    
    # Segunda ejecución (días después): solo procesa encuentros nuevos
    print("\nSegunda ejecución - solo encuentros nuevos...")
    stats2 = scraper.scrape_competition_by_name("LF2")
    print(f"Nuevos encuentros: {stats2['total_matches_scraped']}")
    print(f"Encuentros omitidos: {stats2['total_matches_skipped']}")
    
finally:
    scraper.close()
```

## Estadísticas Mejoradas

El método `scrape_competition()` ahora devuelve estadísticas más detalladas:

```python
{
    "competition": "LF2",
    "gender": "fem",
    "collection": "all_feb_games_fem",
    "total_seasons": 3,
    "total_groups": 8,
    "total_matches_found": 240,  # Total en la web
    "total_matches_scraped": 45,  # Nuevos procesados
    "total_matches_skipped": 195,  # Ya estaban en BD
    "total_matches_failed": 0
}
```

## Notas Importantes

1. **Seguridad Concurrente**: El sistema incluye una doble verificación antes de insertar para evitar duplicados en caso de ejecuciones concurrentes.

2. **Orden de Procesamiento**: Los encuentros se procesan en el orden que aparecen en la web de la FEB.

3. **Estado por Grupo**: El estado se guarda a nivel de grupo, no de competición completa, para mayor granularidad.

4. **Metadatos**: Cada encuentro incluye metadatos de `competition_name`, `season`, `group` y `gender` para facilitar las consultas.

## Consultas Útiles

### Ver el estado del scraping

```python
from src.database import MongoDBClient

db = MongoDBClient()
state_collection = db.get_collection("scraping_state")

# Ver todos los estados
for state in state_collection.find():
    print(f"{state['competition_name']} - {state['season']} - {state['group']}: "
          f"{state['total_matches']} encuentros (último: {state['last_update']})")
```

### Resetear el estado para re-scraping

```python
# Eliminar estado de una competición específica
state_collection.delete_many({"competition_name": "LF2"})

# O eliminar todo el estado
state_collection.delete_many({})
```

## Troubleshooting

### El sistema sigue procesando todos los encuentros

- Verifica que `incremental=True` en la llamada al método
- Verifica que los metadatos (`competition_name`, `season`, `group`) coincidan exactamente

### Encuentros duplicados

- El sistema usa el `game_code` como `_id`, por lo que MongoDB previene duplicados automáticamente
- Si ves duplicados, puede ser que los `game_code` sean diferentes

### Rendimiento

- El filtrado de encuentros ya procesados es muy eficiente (usa índices MongoDB)
- Para grandes volúmenes, considera añadir índices adicionales en los campos de metadatos
