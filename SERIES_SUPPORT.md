# Soporte para Series/Fases en el Scraper de FEB

## Problema Identificado

El scraper original solo capturaba partidos del **calendario regular** (Liga Regular), pero no capturaba partidos de otras fases importantes como:

- **Play-offs**
- **Copa de la Reina / Copa SM Reina**
- **Supercopa**
- Otras fases especiales

Estos partidos están disponibles en la web de FEB pero **NO en el dropdown de grupos**, sino en enlaces separados del tipo:
```html
<a href="Series.aspx?f=43123#">Supercopa</a>
```

## Solución Implementada

### 1. Nuevos Métodos en `feb_scraper.py`

**`get_series_links(soup)`**
- Extrae enlaces a series/fases de la página de competición
- Retorna lista de diccionarios con: `name`, `url`, `fase_id`
- Identifica fases como Play-offs, Copa, Supercopa, etc.

**`get_matches_from_series(series_url)`**
- Carga la página de una serie específica (Series.aspx?f=xxxxx)
- Extrae todos los códigos de partidos de esa serie
- Evita duplicados

### 2. Modificaciones en `main.py`

El flujo de scraping ahora:

1. **Selecciona la temporada**
2. **Extrae partidos del calendario regular** (como antes)
3. **Busca enlaces a series/fases** en esa temporada
4. **Para cada serie encontrada**, extrae sus partidos
5. **Combina todos los partidos**, eliminando duplicados
6. **Asigna el grupo correcto**:
   - Partidos de series → nombre de la serie (ej: "Play-Offs")
   - Partidos del calendario → campo `round` del API

### 3. Ejemplo de Resultados

**Temporada 2018/2019 de LF ENDESA:**

Antes (solo calendario):
- 182 partidos

Ahora (con series):
- Liga Regular: 182 partidos
- Play-Offs: 16 partidos
- Copa de la Reina: 7 partidos
- **Total: 205 partidos** ✓

**Temporada 2025/2026 de LF ENDESA:**
- Liga Regular: ~128 partidos
- Supercopa: 3 partidos
- **Total: 131 partidos** ✓

## Archivos Modificados

1. **src/scraper/feb_scraper.py**
   - Añadidos métodos `get_series_links()` y `get_matches_from_series()`

2. **src/main.py**
   - Modificado `scrape_competition()` para procesar series además del calendario
   - Lógica de deduplicación de partidos
   - Asignación correcta de grupo según origen (serie o calendario)

## Uso

El scraping funciona igual que antes, pero ahora captura automáticamente todos los partidos:

```python
from main import FEBScoutingScraper

scraper = FEBScoutingScraper()
stats = scraper.scrape_competition_by_name("LF ENDESA", incremental=True)
scraper.close()
```

O usando el script interactivo:
```bash
cd src
python run_scraping.py
# Selecciona opción 2 (Scraping interactivo)
# Ingresa: LF ENDESA
```

## Beneficios

✅ **Captura completa**: Todos los partidos oficiales (Liga + Play-offs + Copas)  
✅ **Automático**: Detecta automáticamente qué series/fases existen en cada temporada  
✅ **Retrocompatible**: Funciona con temporadas antiguas y nuevas  
✅ **Incremental**: Modo incremental evita re-procesar partidos existentes  
✅ **Sin duplicados**: Elimina automáticamente partidos que aparecen en múltiples lugares  

## Testing

Scripts de prueba creados:
- `analyze_series_links.py` - Analiza enlaces de series en la web
- `analyze_old_seasons_phases.py` - Verifica fases en temporadas antiguas  
- `test_series_scraper.py` - Test unitario de funcionalidad
- `scrape_2018_test.py` - Scraping completo de temporada de prueba

## Próximos Pasos

Para obtener los datos históricos completos:

1. Ejecutar scraping incremental de LF ENDESA (capturará las fases faltantes)
2. El sistema detectará automáticamente todas las series de cada temporada
3. Los partidos se almacenarán con su fase/grupo correcto
