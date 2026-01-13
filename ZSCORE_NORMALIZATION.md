# Normalización con Z-Score para Comparaciones Históricas

## 🎯 Problema

En baloncesto, comparar estadísticas entre diferentes épocas y ligas es extremadamente difícil:

- **Efecto época**: 10 puntos en 2005 ≠ 10 puntos en 2025 (ritmo de juego, reglas)
- **Efecto liga**: ACB ≠ LEB Oro ≠ EBA (nivel competitivo diferente)
- **Cambios jerárquicos**: LF2 era nivel 2 hasta 2020 → nivel 3 con Liga Challenge

**Pregunta clave**: ¿Cómo sabemos si un jugador con 14 pts en EBA 2010 es mejor que uno con 11 pts en EBA 2023?

## 📊 Solución: Z-Score Normalization

### ¿Qué es el Z-Score?

El Z-Score mide **cuántas desviaciones estándar** se aleja un valor de la media de su grupo:

$$Z = \frac{x - \mu}{\sigma}$$

Donde:
- $x$ = valor del jugador (ej: puntos)
- $\mu$ = media del grupo (nivel competitivo + temporada)
- $\sigma$ = desviación estándar del grupo

### Interpretación Práctica

| Z-Score | Significado | Percentil |
|---------|-------------|-----------|
| 0 | Promedio del grupo | 50% |
| +1.0 | Una desviación por encima | ~84% (mejor que 84%) |
| +1.5 | Muy bueno | ~93% |
| +2.0 | Élite | ~97% |
| +2.5 | Dominante | ~99% |
| -1.0 | Por debajo del promedio | ~16% |

## 🔍 Ejemplo Real

### Jugador A - Temporada 2010
- **Competición**: EBA (nivel 4)
- **Puntos por partido**: 14
- **Media EBA 2010**: 9 puntos
- **Desviación estándar**: 2

```python
Z = (14 - 9) / 2 = +2.5
Percentil = 99%
```

**Interpretación**: Dominante para su contexto (top 1%)

### Jugador B - Temporada 2023
- **Competición**: EBA (nivel 4)
- **Puntos por partido**: 11
- **Media EBA 2023**: 7.5 puntos
- **Desviación estándar**: 1.8

```python
Z = (11 - 7.5) / 1.8 = +1.94
Percentil = 97%
```

**Interpretación**: Élite en su contexto (top 3%)

### Conclusión

Aunque el Jugador A tiene más puntos absolutos (14 vs 11), el Jugador B es ligeramente más dominante en su contexto (Z=+1.94 vs Z=+2.5). **Ahora son comparables**.

## 🏗️ Implementación en el Sistema

### 1. Tabla `competition_levels`

Modela cómo cambian las competiciones con el tiempo:

```sql
CREATE TABLE competition_levels (
    level_id INTEGER PRIMARY KEY,
    competition_id INTEGER NOT NULL,
    season TEXT NOT NULL,
    competition_level INTEGER NOT NULL,  -- 1=máximo, 2, 3...
    weight REAL DEFAULT 1.0,
    UNIQUE(competition_id, season)
);
```

**Ejemplo de configuración**:
```sql
-- LF2 era nivel 2 hasta 2019-2020
INSERT INTO competition_levels VALUES (1, 'LF2', '2019-2020', 2, 1.0);

-- LF2 pasó a nivel 3 con la Liga Challenge (2020-2021+)
INSERT INTO competition_levels VALUES (2, 'LF2', '2020-2021', 3, 1.0);
INSERT INTO competition_levels VALUES (3, 'Liga Challenge', '2020-2021', 2, 1.0);
```

### 2. Z-Scores en `player_game_stats`

Cada partido de cada jugador tiene Z-Scores calculados:

```sql
ALTER TABLE player_game_stats ADD COLUMN z_points REAL;
ALTER TABLE player_game_stats ADD COLUMN z_efficiency REAL;
ALTER TABLE player_game_stats ADD COLUMN z_rebounds REAL;
ALTER TABLE player_game_stats ADD COLUMN z_assists REAL;
ALTER TABLE player_game_stats ADD COLUMN z_usage REAL;
```

### 3. Z-Scores y Percentiles Agregados

En `player_aggregated_stats` (por temporada):

```sql
ALTER TABLE player_aggregated_stats ADD COLUMN z_avg_points REAL;
ALTER TABLE player_aggregated_stats ADD COLUMN z_avg_efficiency REAL;
ALTER TABLE player_aggregated_stats ADD COLUMN percentile_points INTEGER;
ALTER TABLE player_aggregated_stats ADD COLUMN percentile_efficiency INTEGER;
ALTER TABLE player_aggregated_stats ADD COLUMN performance_tier TEXT;
```

**Performance Tiers**:
- `elite`: Percentil 95+ (top 5%)
- `very_good`: Percentil 80-95
- `above_average`: Percentil 60-80
- `average`: Percentil 40-60
- `below_average`: Percentil <40

## 🔧 Uso en el Código

### Calcular Z-Scores

```python
from src.ml.normalization import ZScoreNormalizer

# Inicializar
normalizer = ZScoreNormalizer("scouting_feb.db")

# Calcular para un contexto (nivel + temporada)
normalizer.update_game_stats_zscores(competition_level=4, season="2023-2024")

# Calcular percentiles para jugadores
normalizer.update_aggregated_stats_normalized(player_id=123, season="2023-2024")
```

### Consultar Jugadores Elite

```sql
-- Top 10 jugadores por eficiencia (comparables entre ligas/épocas)
SELECT 
    p.name,
    c.competition_name,
    pas.season,
    pas.avg_efficiency,
    pas.z_avg_efficiency,
    pas.percentile_efficiency,
    pas.performance_tier
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
JOIN competitions c ON pas.competition_id = c.competition_id
WHERE pas.games_played >= 10
ORDER BY pas.z_avg_efficiency DESC
LIMIT 10;
```

### Identificar Prospectos

```python
# Jugadores jóvenes (<23 años) con rendimiento élite
query = """
SELECT 
    p.name,
    p.age_at_game,
    pas.percentile_efficiency,
    pas.z_avg_points
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
WHERE p.age_at_game < 23
    AND pas.percentile_efficiency >= 80  -- Top 20%
    AND pas.games_played >= 15
ORDER BY pas.z_avg_efficiency DESC
"""
```

## 📈 Ventajas del Z-Score

### ✅ Para Machine Learning

1. **Escala homogénea**: Todas las features en rango similar
2. **No dominancia artificial**: Una feature no domina por magnitud
3. **Facilita interacciones**: XGBoost encuentra patrones más fácilmente
4. **Comparabilidad**: Datos de 2005 y 2025 en mismo "idioma"

### ✅ Para Scouting

1. **Comunicación clara**: "Este jugador está en el percentil 95 de su liga"
2. **Identificación de outliers**: Z > +2 = jugador excepcional
3. **Comparación justa**: No penaliza por jugar en liga inferior
4. **Detección de tendencias**: ¿El jugador mejora su Z-Score con el tiempo?

## 🎯 Qué Variables Normalizar

### ✅ Ideal para Z-Score

- **Volumen**: Puntos, rebotes, asistencias, tiros
- **Uso**: % de posesiones, minutos
- **Ritmo**: Posesiones por partido
- **Impacto**: Valoración, plus/minus

### ⚠️ Con cuidado

- **Porcentajes de tiro**: TS%, eFG%, FT%
  - Rango limitado (0-100%)
  - Distribución estrecha
  - Mejor usar: `x - media` (sin dividir por std)

### ❌ NO normalizar

- **Variables categóricas**: Posición, género, equipo
- **IDs**: player_id, game_id
- **Fechas**: game_date, season
- **Booleanos**: is_starter, is_home

## 🚀 Proceso ETL con Z-Scores

### Paso 1: Cargar datos raw

```bash
python src/run_ml_pipeline.py --step etl
```

### Paso 2: Inicializar niveles de competición

```python
from src.ml.normalization import initialize_competition_levels

initialize_competition_levels("scouting_feb.db")
```

### Paso 3: Calcular Z-Scores

```python
etl = FEBDataETL()
etl.normalize_all_stats(conn, collections=["all_feb_games_masc"])
```

### Paso 4: Verificar resultados

```sql
-- Verificar distribución de Z-Scores (debe ser ~N(0,1))
SELECT 
    AVG(z_efficiency) as mean_z,      -- Debe ser ~0
    STDEV(z_efficiency) as std_z,     -- Debe ser ~1
    MIN(z_efficiency) as min_z,
    MAX(z_efficiency) as max_z,
    COUNT(*) as n
FROM player_game_stats
WHERE z_efficiency IS NOT NULL;
```

## 📊 SHAP Feature Importance con Z-Scores

Los Z-Scores mejoran la interpretabilidad de SHAP:

```python
# Z-Scores en top features
import shap

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)

# Features más importantes (típicamente)
# 1. z_efficiency (rendimiento relativo)
# 2. z_points (anotación relativa)
# 3. age_at_game (edad)
# 4. percentile_efficiency (posición en distribución)
# 5. z_avg_rebounds (rebotes históricos relativos)
```

## 🔄 Mantenimiento

### Añadir nueva temporada

```python
# Los Z-Scores se recalculan automáticamente en ETL
etl = FEBDataETL()
etl.run_full_etl(collections=["all_feb_games_masc"], limit=None)

# Los niveles de competición se actualizan automáticamente
# basados en la tabla competition_levels
```

### Ajustar niveles de competición

```sql
-- Si una competición cambia de nivel
UPDATE competition_levels
SET competition_level = 3,
    notes = 'Bajó de nivel 2 a nivel 3 por creación de Liga Challenge'
WHERE competition_id = (SELECT competition_id FROM competitions WHERE competition_name = 'LF2')
    AND season >= '2020-2021';
```

## 📚 Referencias

- **Z-Score**: [Wikipedia - Standard Score](https://en.wikipedia.org/wiki/Standard_score)
- **Basketball Analytics**: [Basketball Reference - Advanced Stats](https://www.basketball-reference.com/)
- **Percentiles**: [Función de distribución acumulativa normal](https://en.wikipedia.org/wiki/Normal_distribution)

## 💡 Tips de Uso

### Para Scouts

```sql
-- Encontrar jugadores que sobresalen en ligas inferiores (buenos prospectos)
SELECT 
    p.name,
    c.competition_name,
    cl.competition_level,
    pas.avg_points,
    pas.z_avg_points,
    pas.percentile_points
FROM player_aggregated_stats pas
JOIN players p ON pas.player_id = p.player_id
JOIN competitions c ON pas.competition_id = c.competition_id
JOIN competition_levels cl ON c.competition_id = cl.competition_id 
    AND pas.season = cl.season
WHERE cl.competition_level >= 3  -- Ligas inferiores
    AND pas.z_avg_points >= 2.0  -- Élite en su contexto
    AND p.age_at_game <= 25       -- Jóvenes
ORDER BY pas.z_avg_points DESC;
```

### Para Análisis

```python
# Comparar rendimiento de un jugador en diferentes temporadas
import matplotlib.pyplot as plt

query = """
SELECT season, z_avg_efficiency, percentile_efficiency
FROM player_aggregated_stats
WHERE player_id = ?
ORDER BY season
"""

df = pd.read_sql(query, conn, params=(player_id,))

plt.figure(figsize=(10, 6))
plt.plot(df['season'], df['z_avg_efficiency'], marker='o')
plt.axhline(0, color='red', linestyle='--', label='Media')
plt.axhline(2, color='green', linestyle='--', label='Élite (Z=+2)')
plt.title(f"Evolución Z-Score: {player_name}")
plt.xlabel("Temporada")
plt.ylabel("Z-Score Eficiencia")
plt.legend()
plt.grid(True)
plt.show()
```

## ⚠️ Limitaciones

1. **Muestra pequeña**: Si una competición/temporada tiene <30 jugadores, los Z-Scores pueden ser inestables
2. **Datos incompletos**: Si faltan datos de minutos jugados, los Z-Scores pueden estar sesgados
3. **Outliers extremos**: Jugadores con Z > 4 o Z < -4 pueden indicar errores en los datos
4. **Cambios de reglas**: Cambios drásticos en reglas del juego pueden afectar comparaciones

## 🎓 Conclusión

El Z-Score es el **idioma común** para comparar jugadores de:
- Diferentes épocas (2005 vs 2025)
- Diferentes ligas (ACB vs EBA)
- Diferentes géneros (masculino vs femenino)

**Resultado**: Sistema de scouting que identifica talento real, no solo estadísticas infladas por contexto favorable.
