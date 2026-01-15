# Sistema de Ponderación de Partidos (Match Weighting)

## Descripción General

El sistema de ponderación asigna diferentes pesos a los partidos según su importancia competitiva. Esto permite que el modelo de Machine Learning valore mejor el rendimiento de los jugadores en momentos clave (finales, play-offs, copas) frente a partidos regulares de temporada.

## Motivación

Un jugador que mantiene o mejora su rendimiento en partidos de alta presión (finales, eliminatorias) demuestra capacidades mentales y técnicas superiores. Por el contrario, un jugador que baja su nivel en estos momentos muestra vulnerabilidad bajo presión. El sistema de ponderación captura esta diferencia.

## Tabla de Pesos

| Tipo de Partido | Peso | Descripción |
|----------------|------|-------------|
| **Liga Regular** | 1.0x | Partidos de temporada regular (baseline) |
| **Supercopa** | 1.2x | Torneo de apertura de temporada |
| **Copa** | 1.3x | Copa del Rey / Copa de la Reina |
| **Play-offs** | 1.4x | Eliminatorias directas (cuartos, semifinales, octavos) |
| **Final** | 1.5x | Partidos de final de competición |

## Implementación Técnica

### 1. Base de Datos

Se añadió el campo `match_weight` a la tabla `games`:

```sql
CREATE TABLE games (
    ...
    match_weight REAL DEFAULT 1.0,  -- Peso del partido según importancia
    ...
);
```

### 2. Cálculo de Pesos

La función `calculate_match_weight()` en `src/ml/etl_processor.py` determina el peso basándose en el campo `group_name`:

```python
def calculate_match_weight(self, group_name: str) -> float:
    """Calcular peso del partido según su fase/importancia."""
    if not group_name:
        return 1.0
    
    group_lower = group_name.lower()
    
    # Orden importante: términos más específicos primero
    if "supercopa" in group_lower:
        return 1.2
    if "final" in group_lower and not any(prefix in group_lower 
                                          for prefix in ["semifinal", "cuartos"]):
        return 1.5
    if any(keyword in group_lower 
           for keyword in ["play", "playoff", "semifinal", "cuartos"]):
        return 1.4
    if "copa" in group_lower:
        return 1.3
    
    return 1.0  # Liga regular
```

### 3. Proceso ETL

El peso se calcula automáticamente durante la transformación:

```python
def transform_game_data(self, mongo_game: Dict) -> Dict:
    group_name = header.get("group", "")
    
    game_data = {
        ...
        "group_name": group_name,
        "match_weight": self.calculate_match_weight(group_name),
        ...
    }
```

## Aplicaciones en Machine Learning

### 1. Agregados Ponderados

En lugar de promedios simples, usar promedios ponderados:

```python
# Media simple (anterior)
avg_points = sum(points) / len(games)

# Media ponderada (nuevo)
weighted_avg = sum(p * w for p, w in zip(points, weights)) / sum(weights)
```

### 2. Identificación de Jugadores "Clutch"

Comparar rendimiento en partidos importantes vs regulares:

```python
# Rendimiento en finales/play-offs
important_games = games[games['match_weight'] > 1.3]
clutch_rating = important_games['points'].mean() / regular_games['points'].mean()

# clutch_rating > 1.0 → Mejora en momentos clave
# clutch_rating < 1.0 → Baja en momentos de presión
```

### 3. Features para XGBoost

Crear features específicas:

```python
features = {
    'avg_points_regular': stats_regular['points'].mean(),
    'avg_points_playoffs': stats_playoffs['points'].mean(),
    'clutch_factor': avg_playoffs / avg_regular,
    'finals_experience': len(stats_finals),
    'weighted_avg_points': weighted_average(stats['points'], stats['match_weight'])
}
```

### 4. Ajuste de Predicciones

Ajustar predicciones según contexto:

```python
# Predicción base
base_prediction = model.predict(features)

# Ajuste según importancia del partido
if match_weight > 1.3:  # Partido importante
    adjustment = player_clutch_factor * match_weight
    final_prediction = base_prediction * adjustment
```

## Ejemplos Prácticos

### Ejemplo 1: Comparación de Dos Jugadores

**Jugador A (Consistente)**
- Liga Regular: 15.2 pts/partido (peso 1.0)
- Play-offs: 15.8 pts/partido (peso 1.4)
- Finales: 16.1 pts/partido (peso 1.5)
- → **Jugador clutch**, mejora en momentos clave

**Jugador B (Volátil)**
- Liga Regular: 18.5 pts/partido (peso 1.0)
- Play-offs: 14.2 pts/partido (peso 1.4)
- Finales: 12.8 pts/partido (peso 1.5)
- → **Baja bajo presión**, rendimiento inconsistente

### Ejemplo 2: Valoración Ponderada

Un jugador con las siguientes actuaciones:

| Partido | Puntos | Peso | Valor Ponderado |
|---------|--------|------|-----------------|
| Liga Regular | 10 | 1.0 | 10.0 |
| Liga Regular | 12 | 1.0 | 12.0 |
| Semifinal | 18 | 1.4 | 25.2 |
| Final | 20 | 1.5 | 30.0 |

```python
# Media simple (sin pesos)
simple_avg = (10 + 12 + 18 + 20) / 4 = 15.0 pts

# Media ponderada
weighted_avg = (10*1.0 + 12*1.0 + 18*1.4 + 20*1.5) / (1.0 + 1.0 + 1.4 + 1.5)
             = 77.2 / 4.9 = 15.76 pts
```

## Migración de Bases de Datos Existentes

Si ya tienes una base de datos SQLite creada, ejecuta el script de migración:

```bash
python migrate_add_weights.py
```

Esto:
1. Añade el campo `match_weight` (si no existe)
2. Recalcula los pesos para todos los partidos existentes
3. Muestra estadísticas de la migración

## Pruebas

Ejecuta el script de pruebas para verificar el funcionamiento:

```bash
python test_match_weights.py
```

Las pruebas verifican:
- ✓ Cálculo correcto de pesos para diferentes tipos de partidos
- ✓ Análisis de pesos en datos reales de MongoDB
- ✓ Integración con el proceso ETL
- ✓ Transformación correcta de datos

## Consideraciones

### Ajuste de Pesos

Los pesos actuales (1.2x, 1.3x, 1.4x, 1.5x) son valores iniciales razonables. Puedes ajustarlos según:
- Análisis de varianza de rendimiento
- Feedback del modelo de ML
- Preferencias del sistema de scouting

### Extensiones Futuras

El sistema se puede extender para considerar:
- **Importancia del partido en la clasificación** (derbi, partido decisivo)
- **Rivalidad histórica** (clásicos, rivalidades regionales)
- **Fase de temporada** (partidos de final de temporada más importantes)
- **Diferencia de nivel** (partidos contra equipos de mayor nivel)

### Limitaciones

- El sistema actual solo considera el tipo de fase, no otros factores contextuales
- No diferencia dentro de play-offs (ej: cuartos vs semifinales)
- Asume que todos los partidos de la misma fase tienen igual importancia

## Referencias

- Código fuente: `src/ml/etl_processor.py` (líneas 87-128)
- Schema: `src/database/sqlite_schema.py` (línea 83)
- Pruebas: `test_match_weights.py`
- Migración: `migrate_add_weights.py`
