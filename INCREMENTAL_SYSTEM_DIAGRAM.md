# Sistema Incremental de Scraping - Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────────────────┐
│                  INICIO: Scraping Incremental                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. Obtener lista COMPLETA de encuentros de la web FEB             │
│     (Por competición, temporada y grupo)                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. Consultar MongoDB: ¿Qué encuentros ya están procesados?        │
│     - Consulta: colección de partidos con metadatos                │
│     - Retorna: lista de game_codes ya en BD                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. Filtrar: Encuentros_Web - Encuentros_BD = Encuentros_Nuevos    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────┴─────────┐
                    │ ¿Hay encuentros   │
                    │ nuevos?           │
                    └─────────┬─────────┘
                              │
                 ┌────────────┴────────────┐
                 │ NO                      │ SÍ
                 ▼                         ▼
    ┌──────────────────────┐   ┌──────────────────────────┐
    │ Log: Todos           │   │ 4. Procesar solo         │
    │ procesados           │   │    encuentros nuevos     │
    │ Actualizar timestamp │   │    (uno por uno)         │
    └──────────────────────┘   └──────────────────────────┘
                 │                         │
                 │                         ▼
                 │              ┌──────────────────────────┐
                 │              │ 5. Por cada encuentro:   │
                 │              │    - Fetch API           │
                 │              │    - Añadir metadatos    │
                 │              │    - Insert MongoDB      │
                 │              │    - Delay 0.5s          │
                 │              └──────────────────────────┘
                 │                         │
                 │                         ▼
                 │              ┌──────────────────────────┐
                 │              │ 6. Actualizar estado:    │
                 │              │    - Último encuentro    │
                 │              │    - Total encuentros    │
                 │              │    - Timestamp           │
                 │              └──────────────────────────┘
                 │                         │
                 └────────────┬────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FIN: Retornar estadísticas                                         │
│  - Total encontrados                                                │
│  - Nuevos procesados                                                │
│  - Omitidos (ya en BD)                                              │
│  - Fallidos                                                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Ventajas del Sistema Incremental

### 🚀 Eficiencia

| Escenario | Sin Incremental | Con Incremental | Mejora |
|-----------|----------------|-----------------|--------|
| Primera ejecución (200 encuentros) | ~100 min | ~100 min | - |
| Segunda ejecución (5 nuevos) | ~100 min | ~2.5 min | **97.5% más rápido** |
| Ejecución diaria (promedio 3 nuevos) | ~100 min | ~1.5 min | **98.5% más rápido** |

*Asumiendo ~30 segundos por encuentro (API + delay)*

### 💰 Ahorro de Costos

```
Competición típica:
- Temporadas: 3
- Grupos por temporada: 4
- Encuentros por grupo: ~40
- Total encuentros: ~480

Primera ejecución:
- Peticiones API: 480
- Tiempo: ~4 horas

Actualizaciones semanales (promedio 10 nuevos):
SIN incremental:
- Peticiones API: 480 (cada vez)
- Tiempo: ~4 horas (cada vez)
- Peticiones/mes: 1,920

CON incremental:
- Peticiones API: 10 (solo nuevos)
- Tiempo: ~5 minutos
- Peticiones/mes: 40

AHORRO: 98% menos peticiones y tiempo
```

### 🎯 Casos de Uso

1. **Actualización Diaria Automática**
   ```python
   # Cron job diario
   scraper.scrape_competition_by_name("LF2", incremental=True)
   # Solo procesa los partidos de ayer
   ```

2. **Múltiples Competiciones**
   ```python
   for comp in ["LF2", "LF", "LEB ORO", "ACB"]:
       scraper.scrape_competition_by_name(comp, incremental=True)
   # Eficiente incluso con muchas competiciones
   ```

3. **Recuperación de Errores**
   ```python
   # Si un scraping falla, la próxima ejecución continúa
   # desde donde quedó sin repetir todo
   ```

## Colección scraping_state

### Estructura de Documento

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

### Índices Recomendados

```python
db.scraping_state.createIndex({"competition_name": 1, "season": 1, "group": 1})
db.scraping_state.createIndex({"last_update": -1})
db.scraping_state.createIndex({"collection_name": 1})
```

## Comparación: Antes vs Después

### ANTES (sin sistema incremental)
```
Ejecución 1 (día 1):
✓ Procesa 200 encuentros (100 minutos)

Ejecución 2 (día 2 - hay 3 nuevos):
✓ Revisa 203 encuentros
✓ Salta 200 que ya existen (verificación una por una)
✓ Procesa 3 nuevos
⏱️ Tiempo: ~100 minutos (revisó todos)
```

### DESPUÉS (con sistema incremental)
```
Ejecución 1 (día 1):
✓ Procesa 200 encuentros (100 minutos)
✓ Guarda estado: último=200, total=200

Ejecución 2 (día 2 - hay 3 nuevos):
✓ Lee estado: ya procesados 200
✓ Obtiene lista nueva: 203 encuentros
✓ Filtra: 203 - 200 = 3 nuevos
✓ Procesa solo 3
⏱️ Tiempo: ~1.5 minutos (solo nuevos)
```

## Monitoreo y Mantenimiento

### Ver Estado Actual
```python
python src/examples_incremental.py
# Opción 4: Ver estado del scraping
```

### Resetear Estado (forzar re-scraping)
```python
# Resetear una competición específica
python src/examples_incremental.py
# Opción 5: Resetear estado

# O manualmente en MongoDB
db.scraping_state.deleteMany({"competition_name": "LF2"})
```

### Query útil: Últimas Actualizaciones
```javascript
// MongoDB Shell
db.scraping_state.find().sort({"last_update": -1}).limit(10)

// Competiciones no actualizadas en 7 días
db.scraping_state.find({
  "last_update": {
    $lt: new Date(Date.now() - 7*24*60*60*1000)
  }
})
```
