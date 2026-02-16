# 🎯 Plan de Mejoras al Modelo de Scouting

Basado en análisis de mejores prácticas y recomendaciones de expertos en ML para baloncesto.

## 📋 Resumen Ejecutivo

**Origen**: Análisis de conversation sobre features importantes en ML para baloncesto  
**Fecha**: 6 de febrero de 2026  
**Estado actual**: Sistema funcional pero con oportunidades de mejora significativas

---

## ✅ Fortalezas Actuales

### Métricas Avanzadas (Ya implementadas)
- ✅ True Shooting % (TS%)
- ✅ Usage Rate
- ✅ Effective FG%
- ✅ Offensive Rating
- ✅ Player Efficiency Rating (PER)
- ✅ Win Shares per 36
- ✅ Team Strength Factors
- ✅ Career Trajectory (multi-season trends)
- ✅ Competition Level weighting
- ✅ Temporal weighting (recency bias)
- ✅ Inactivity penalties

### Arquitectura de Datos
- ✅ MongoDB para datos raw
- ✅ SQLite para analytics
- ✅ ETL robusto con player identity matching
- ✅ Separación player_profile_potential vs player_career_potential

---

## ⚠️ Oportunidades de Mejora (Priorizadas)

### 🔴 PRIORIDAD 1: Normalización per-36 minutos

**Problema**: Usamos promedios simples (avg_points) que sesgan hacia jugadoras con más minutos.

**Solución**:
```python
# Agregar a player_profile_metrics:
pts_per_36 = (total_points / total_minutes) * 36
ast_per_36 = (total_assists / total_minutes) * 36
reb_per_36 = (total_rebounds / total_minutes) * 36
fgm_per_36 = (total_fgm / total_minutes) * 36
```

**Impacto esperado**:
- Jugadoras de rol/bench serán comparables con titulares
- Elimina sesgo de "minutos = puntos = potencial"
- Detección de talento en suplentes

**Esfuerzo**: 2-3 horas (agregar columnas, recalcular métricas)

---

### 🔴 PRIORIDAD 2: Ventanas temporales (Rolling Windows)

**Problema**: Solo tenemos promedios de temporada completa, perdemos tendencias intra-temporada.

**Solución**:
```python
# Calcular para cada jugadora en cada ventana:
last_5_games_stats = {
    'avg_pts': ...,
    'avg_minutes': ...,
    'ts_pct': ...
}

last_10_games_stats = {...}

# Features derivadas:
trend_points = slope(points_last_15_games)
momentum_index = avg(last_5) - avg(last_10)
delta_pts_recent_vs_season = last_5_avg - season_avg
```

**Impacto esperado**:
- Detectar breakouts (jugadoras en racha ascendente)
- Detectar declive temprano
- Mejorar predicción de próxima temporada
- Rising stars más precisas

**Esfuerzo**: 6-8 horas (nueva tabla, sliding windows, features)

---

### 🟡 PRIORIDAD 3: Ratios Jugadora/Equipo

**Problema**: No sabemos si una jugadora anota 15 pts porque es buena o porque su equipo es ofensivo.

**Solución**:
```python
# Agregar a player_profile_metrics:
player_pts_share = player_total_pts / team_total_pts
player_usage_share = player_usage_rate / team_avg_usage
efficiency_vs_team = player_ts_pct / team_ts_pct

# Contexto normalizado:
context_adjusted_score = pts_per_36 * efficiency_vs_team / team_off_rating
```

**Impacto esperado**:
- Eliminar sesgo de "equipo ofensivo inflates stats"
- Detectar jugadoras que cargan el equipo (alta pts_share)
- Comparación más justa entre competiciones

**Esfuerzo**: 4-5 horas (calcular team totals, ratios)

---

### 🟡 PRIORIDAD 4: Volatilidad/Consistency mejorada

**Problema**: Usamos std_points directamente, no consideramos sample size.

**Solución**:
```python
# Coeficiente de variación (mejor que std)
cv_points = std_points / avg_points

# Índice de estabilidad ajustado por partidos
stability_index = std_points / sqrt(games_played)

# Consistency score normalizado
consistency_score = 1 - min(1.0, cv_points / 0.5)
```

**Impacto esperado**:
- Penalizar menos a jugadoras con pocas games (sample size)
- Valorar consistencia relativa, no absoluta

**Esfuerzo**: 2 horas (fórmulas simples)

---

### 🟢 PRIORIDAD 5: Breakout Detection Score

**Problema**: No tenemos métrica compuesta para "explosión de talento".

**Solución**:
```python
breakout_score = (
    trend_points *           # ¿Está mejorando?
    (ts_pct / usage_rate) *  # ¿Eficiencia vs uso?
    minutes_trend            # ¿Le dan más confianza?
)

# Flags:
is_breakout_candidate = (
    breakout_score > threshold AND
    age <= 25 AND
    seasons_played <= 3
)
```

**Impacto esperado**:
- Detectar rising stars antes que sean obvias
- Componente "scout eye" automatizado

**Esfuerzo**: 3 horas (calcular trends, combinar)

---

### 🟢 PRIORIDAD 6: On/Off Court Rating

**Problema**: No sabemos si el equipo juega mejor con ella en cancha.

**⚠️ LIMITACIÓN**: Requiere datos de lineup que FEB puede no proporcionar en box scores.

**Solución (si hay datos)**:
```python
on_court_rating = team_rating_when_player_on_floor
off_court_rating = team_rating_when_player_off_floor
on_off_net_rating = on_court_rating - off_court_rating
```

**Esfuerzo**: 
- Si hay datos: 6-8 horas (parsear lineups, calcular por posesión)
- Si NO hay datos: **SKIP** por ahora

---

## 🚫 Features a EVITAR (Anti-patterns detectados)

❌ **Puntos absolutos como feature principal**  
✅ Usar pts_per_36 o pts_share

❌ **Promedios de temporada entera sin contexto**  
✅ Usar rolling windows + season avg

❌ **Eficiencia sin normalizar por uso**  
✅ Usar ts_pct / usage_rate

❌ **Minutos como proxy de talento**  
✅ Controlar por minutos (per-36), no premiarlo

❌ **Stats totales sin normalizar**  
✅ Todo per-36, per-possession, o per-100-possessions

---

## 📅 Roadmap de Implementación

### Fase 1: Quick Wins (1 semana)
1. ✅ Normalización per-36 (P1)
2. ✅ Consistency mejorada (P4)
3. ✅ Ratios jugadora/equipo básicos (P3 parcial)

### Fase 2: Core Improvements (2-3 semanas)
4. ✅ Ventanas temporales (P2)
5. ✅ Breakout detection (P5)
6. ✅ Ratios avanzados jugadora/equipo (P3 completo)

### Fase 3: Advanced (si hay datos)
7. ⚠️ On/Off ratings (P6) - **Evaluar viabilidad primero**
8. 📊 Dashboard de explicabilidad (SHAP values)

---

## 🧪 Testing y Validación

### Después de cada mejora:
1. **Sanity check**: ¿Los top 20 tienen sentido?
2. **Comparación A/B**: Modelo anterior vs nuevo
3. **Feature importance**: ¿Las nuevas features son relevantes?
4. **Casos extremos**: Revisar jugadoras muy jóvenes, veteranas, lesionadas

### Métricas de éxito:
- ✅ Detección temprana de rising stars (antes que sean obvias)
- ✅ Menos jugadoras inactivas en top 20
- ✅ Menos sesgo por minutos jugados
- ✅ Rising stars reales (explosión de rendimiento) vs jóvenes mediocres

---

## 💡 Insights del Análisis Original

### Qué funciona en modelos de producción:

1. **Separar modelos por objetivo**:
   - Modelo A: Continuidad (¿seguirá en el equipo?)
   - Modelo B: Proyección (¿mejorará?)
   - Modelo C: Eficiencia (¿qué tan bien juega?)

2. **Features críticas** (por orden de importancia en otros sistemas):
   - `pts_per_36` (producción normalizada)
   - `std_points` / `cv_points` (consistencia)
   - `efficiency` (TS%, eFG%)
   - `trend_points` (momentum)
   - `usage_rate` (rol ofensivo)
   - `minutes_share` (confianza del coach)

3. **Features que NO funcionan**:
   - Puntos absolutos (sesgo de minutos)
   - Totales de temporada (no normalizado)
   - Ratings opacos sin definición
   - Stats del futuro (data leakage)

---

## 🎯 Objetivo Final

**Sistema de scouting que detecta**:
- 🌟 Rising stars tempranas (breakout antes de que sea obvio)
- 🔥 Jugadoras en pico de rendimiento
- 👑 Talento consolidado y estable
- 📈 Tendencias ascendentes/descendentes
- 🎯 Eficiencia real (no inflada por minutos/equipo)

**Y evita**:
- ❌ Sesgo por minutos jugados
- ❌ Inflación por equipo ofensivo
- ❌ Premiar inconsistencia
- ❌ Jugadoras inactivas en top rankings

---

## 📚 Referencias

- Conversación original: https://chatgpt.com/share/6985fa11-4330-8013-acfc-888f75fd7441
- Implementación actual: `src/ml/etl_processor.py`, `src/ml/advanced_stats.py`
- Documentación sistema: `ML_SYSTEM.md`, `PLAYER_IDENTITY_SYSTEM.md`
