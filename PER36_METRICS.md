# Métricas Per-36: Normalización por Minutos Jugados

## 🎯 Problema

En baloncesto, comparar estadísticas absolutas (puntos, rebotes, asistencias) tiene un **sesgo fundamental**: **los minutos jugados**.

### Ejemplo Real

| Jugador | Puntos | Minutos | Rol |
|---------|--------|---------|-----|
| A | 20 | 35 | Titular |
| B | 12 | 18 | Suplente |

**Pregunta**: ¿Quién es más productivo?

**Respuesta intuitiva incorrecta**: Jugador A (más puntos)

**Respuesta correcta** (normalizada):
- Jugador A: 20/35 × 36 = **20.6 pts/36min**
- Jugador B: 12/18 × 36 = **24.0 pts/36min** ⭐

El **Jugador B es más productivo**, pero juega menos minutos.

## 📊 ¿Qué son las Métricas Per-36?

Las métricas **per-36** normalizan las estadísticas a **36 minutos** (duración estándar de un partido de baloncesto).

### Fórmula

$$\text{Stat\_per\_36} = \frac{\text{Stat}}{\text{Minutos}} \times 36$$

### ¿Por qué 36 minutos?

- Duración reglamentaria: **4 cuartos × 10 min = 40 min** (FIBA) o **4 cuartos × 12 min = 48 min** (NBA)
- **36 minutos**: Estándar histórico en basketball analytics
- Permite comparación directa entre jugadores independientemente de minutos

## 🔍 Casos de Uso

### 1. Comparar Titulares vs Suplentes

```sql
SELECT 
    name,
    avg_minutes,
    avg_points,
    avg_points_per_36,
    CASE 
        WHEN avg_minutes >= 25 THEN 'Titular'
        ELSE 'Suplente'
    END as rol
FROM player_aggregated_stats
WHERE avg_minutes >= 10
ORDER BY avg_points_per_36 DESC;
```

### 2. Identificar Suplentes Infrautilizados

Jugadores con alta productividad pero pocos minutos:

```sql
SELECT name, avg_minutes, avg_points_per_36, z_points_per_36
FROM player_aggregated_stats
WHERE avg_minutes BETWEEN 10 AND 20  -- Suplentes
    AND z_points_per_36 >= 1.5  -- Top 93% en productividad
ORDER BY z_points_per_36 DESC;
```

**Interpretación**: Estos jugadores deberían tener más minutos

### 3. Detectar Jugadores "Vacíos"

Titulares con muchos minutos pero baja productividad:

```sql
SELECT name, avg_minutes, avg_points, avg_points_per_36
FROM player_aggregated_stats
WHERE avg_minutes >= 30  -- Titulares con muchos minutos
    AND avg_points_per_36 < 10  -- Baja productividad
ORDER BY avg_minutes DESC;
```

### 4. Proyectar Rendimiento con Más Minutos

Si un suplente pasara a ser titular:

```python
# Jugador actual: 12 pts en 18 min (24 pts/36)
# Si pasa a jugar 30 minutos:
projected_points = (24 / 36) * 30  # = 20 puntos

# Nota: Asume que mantiene la productividad (no siempre cierto)
```

## ⚠️ Limitaciones y Consideraciones

### 1. **No Linealidad**

La productividad NO siempre escala linealmente:
- **Fatiga**: Jugador puede rendir menos con más minutos
- **Rol**: Suplente puede enfrentar defensas más relajadas
- **Ritmo**: Starters enfrentan mejores defensores

**Solución**: Usar per-36 CON contexto (minutos mínimos, calidad de oponentes)

### 2. **Muestra Mínima**

Jugador con 3 min y 4 pts → 48 pts/36 (no representativo)

**Recomendación**: Filtrar por `minutes_played >= 10` o `avg_minutes >= 15`

### 3. **Contexto de Equipo**

Suplente en equipo débil puede tener stats infladas

**Solución**: Combinar per-36 con Z-Scores (contexto de liga+temporada)

## 🧮 Implementación en el Sistema

### Cálculo en ETL

```python
# En _transform_player_stats()
minutes_played = 18.5  # Minutos jugados en el partido
points = 12

# Calcular per-36
points_per_36 = (points / minutes_played) * 36 if minutes_played > 0 else 0
# = (12 / 18.5) * 36 = 23.35 pts/36
```

### Almacenamiento

**Tabla `player_game_stats`** (por partido):
```sql
CREATE TABLE player_game_stats (
    ...
    minutes_played REAL,
    points INTEGER,
    points_per_36 REAL,  -- Calculado automáticamente
    rebounds_per_36 REAL,
    assists_per_36 REAL,
    efficiency_per_36 REAL,
    ...
);
```

**Tabla `player_aggregated_stats`** (por temporada):
```sql
CREATE TABLE player_aggregated_stats (
    ...
    avg_minutes REAL,
    avg_points REAL,
    avg_points_per_36 REAL,  -- Promedio de per-36 de todos los partidos
    z_points_per_36 REAL,  -- Z-Score contextual
    ...
);
```

### Normalización con Z-Score

Combinar per-36 con Z-Score para máxima comparabilidad:

```python
# Jugador A (2010, EBA): 24 pts/36
# Media EBA 2010: 18 pts/36, σ = 5
z_A = (24 - 18) / 5 = +1.2

# Jugador B (2023, EBA): 22 pts/36
# Media EBA 2023: 16 pts/36, σ = 4
z_B = (22 - 16) / 4 = +1.5

# Jugador B es más dominante en su contexto
```

## 📈 Uso en Machine Learning

### Features Críticas

| Feature | Importancia | Razón |
|---------|-------------|-------|
| `z_points_per_36` | 🔴 MUY ALTA | Productividad normalizada y contextual |
| `z_efficiency_per_36` | 🔴 MUY ALTA | Eficiencia real independiente de minutos |
| `avg_minutes` | 🟠 ALTA | Rol en equipo (titular vs suplente) |
| `avg_points_per_36` | 🟡 MEDIA | Productividad raw sin contexto |

### Interacciones

XGBoost puede detectar interacciones:
- `avg_minutes × points_per_36`: Titulares productivos vs suplentes productivos
- `age × efficiency_per_36`: Veteranos eficientes en poco tiempo
- `z_points_per_36 × competition_level`: Dominancia en liga inferior

### Ejemplo de Predicción

**Target**: ¿Rendirá bien en liga superior?

```python
# Features importantes:
features = [
    'z_points_per_36',  # Productividad contextual
    'z_efficiency_per_36',  # Eficiencia contextual
    'avg_minutes',  # Rol actual
    'age_at_game',  # Madurez
    'years_experience'  # Experiencia
]

# Si z_points_per_36 > 2.0 en liga inferior:
# → Alta probabilidad de éxito en liga superior
```

## 🎯 Comparación: Per-36 vs Absolutos vs Z-Score

| Métrica | Elimina Sesgo Minutos | Elimina Sesgo Época/Liga | Uso Principal |
|---------|:---------------------:|:------------------------:|---------------|
| **Absolutos** (pts) | ❌ | ❌ | Estadísticas básicas |
| **Per-36** (pts/36) | ✅ | ❌ | Comparar roles (titular vs suplente) |
| **Z-Score** (z_pts) | ❌ | ✅ | Comparar épocas y ligas |
| **Z-Score Per-36** (z_pts/36) | ✅ | ✅ | **ÓPTIMO**: Comparación total |

**Conclusión**: **`z_points_per_36`** es la métrica más completa para scouting.

## 📊 Ejemplo Completo

### Datos Raw

| Jugador | Temporada | Liga | Min | Pts | Pts/36 |
|---------|-----------|------|-----|-----|--------|
| García | 2010 | EBA | 18 | 14 | 28.0 |
| López | 2023 | EBA | 32 | 18 | 20.3 |
| Martín | 2023 | LEB Oro | 25 | 16 | 23.0 |

### Con Normalización

| Jugador | Liga | Pts/36 | Media | Std | Z-Score | Interpretación |
|---------|------|--------|-------|-----|---------|----------------|
| García | EBA | 28.0 | 18.0 | 5.0 | **+2.0** | Élite (top 97%) |
| López | EBA | 20.3 | 16.0 | 4.0 | **+1.1** | Muy bueno (top 86%) |
| Martín | LEB Oro | 23.0 | 22.0 | 6.0 | **+0.2** | Promedio (top 58%) |

**Insight**: García es el más dominante a pesar de jugar menos minutos.

## 🚀 Queries Útiles

### Top 10 Jugadores Más Productivos (Independiente de Minutos)

```sql
SELECT 
    p.name,
    c.competition_name,
    pas.season,
    pas.avg_minutes,
    ROUND(pas.avg_points_per_36, 1) as pts_per_36,
    ROUND(pas.z_points_per_36, 2) as z_score,
    pas.percentile_points as percentile
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
JOIN competitions c ON pas.competition_id = c.competition_id
WHERE pas.avg_minutes >= 15  -- Mínimo representativo
    AND pas.games_played >= 10
ORDER BY pas.z_points_per_36 DESC
LIMIT 10;
```

### Suplentes con Potencial de Ser Titulares

```sql
SELECT 
    p.name,
    pas.avg_minutes as min_actuales,
    ROUND(pas.avg_points_per_36, 1) as productividad,
    ROUND(pas.z_points_per_36, 2) as z_score,
    CASE 
        WHEN pas.z_points_per_36 >= 2.0 THEN 'Elite'
        WHEN pas.z_points_per_36 >= 1.0 THEN 'Muy bueno'
        ELSE 'Bueno'
    END as nivel
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
WHERE pas.avg_minutes BETWEEN 12 AND 22  -- Suplentes
    AND pas.z_points_per_36 >= 1.0  -- Alta productividad
    AND pas.games_played >= 15
ORDER BY pas.z_points_per_36 DESC;
```

### Comparar Dos Jugadores (Diferentes Minutos)

```sql
-- Jugador A vs Jugador B
SELECT 
    p.name,
    pas.avg_minutes,
    pas.avg_points,
    ROUND(pas.avg_points_per_36, 1) as pts_36,
    ROUND(pas.z_points_per_36, 2) as z_pts_36,
    ROUND(pas.avg_efficiency_per_36, 1) as eff_36,
    ROUND(pas.z_efficiency_per_36, 2) as z_eff_36
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
WHERE p.name IN ('García Martínez', 'López Rodríguez')
    AND pas.season = '2023-2024';
```

## 💡 Tips para Scouting

### 1. **Buscar Suplentes Infrautilizados**
```sql
WHERE avg_minutes < 20 AND z_points_per_36 >= 1.5
```

### 2. **Validar Titulares "Vacíos"**
```sql
WHERE avg_minutes >= 30 AND z_efficiency_per_36 < 0
```

### 3. **Proyectar Potencial**
```python
# Si suplente (18 min) pasa a titular (30 min):
# NO asumir linealidad completa
projected = current_per_36 * (new_minutes / 36) * 0.9  # Factor corrección 90%
```

### 4. **Combinar con Edad**
```sql
-- Jóvenes productivos con pocos minutos = alta prioridad
WHERE age_at_game <= 23 
    AND avg_minutes < 20 
    AND z_points_per_36 >= 1.5
```

## 📚 Referencias

- **Basketball Reference**: Usa per-36 como métrica estándar
- **NBA Advanced Stats**: Todas las métricas pace-adjusted
- **FiveThirtyEight**: RAPTOR usa per-100 possessions (similar concepto)
- **Dean Oliver**: "Basketball on Paper" (pionero en pace-adjusted stats)

## ⚙️ Mantenimiento

### Recalcular Per-36

Las métricas per-36 se calculan automáticamente en el ETL:

```python
# En etl_processor.py
etl = FEBDataETL()
etl.run_full_etl(collections=["all_feb_games_masc"])
# Per-36 se calculan en _transform_player_stats()
```

### Verificar Datos

```sql
-- Verificar que per-36 se calcularon correctamente
SELECT 
    COUNT(*) as total,
    COUNT(points_per_36) as con_per36,
    AVG(points_per_36) as avg_per36
FROM player_game_stats
WHERE minutes_played > 0;

-- Debe mostrar: total = con_per36 (100% cobertura)
```

## 🎓 Conclusión

Las métricas **per-36** son **esenciales** para:

1. **Comparar jugadores** con diferentes minutos
2. **Identificar suplentes** productivos infrautilizados
3. **Proyectar rendimiento** si aumentan minutos
4. **Detectar eficiencia** real independiente de rol

Combinadas con **Z-Scores**, permiten comparaciones completas entre:
- Titulares vs suplentes
- Diferentes épocas
- Diferentes ligas

**Resultado**: Sistema de scouting que identifica talento real, no solo volumen de estadísticas.
