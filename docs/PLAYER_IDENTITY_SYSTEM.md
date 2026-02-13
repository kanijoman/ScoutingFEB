# Sistema de Gestión de Identidades de Jugadores

## 📋 Visión General

El sistema de gestión de identidades resuelve el problema crítico de identificación de jugadores en datos de la FEB:

### ❌ Problema
- **IDs FEB no únicos**: Un jugador puede tener múltiples IDs entre temporadas
- **Nombres inconsistentes**: "J. PÉREZ", "JUAN PÉREZ", "PÉREZ, JUAN"
- **Fechas de nacimiento ausentes**: No siempre disponibles

### ✅ Solución
- **Sistema de perfiles**: Cada aparición única (nombre+equipo+temporada) = 1 perfil
- **Candidate matching**: Algoritmo de similitud para sugerir perfiles del mismo jugador
- **Validación humana**: El staff confirma identidades, el sistema aprende

## 🏗️ Arquitectura

### Tablas Principales

#### 1. `player_profiles`
Almacena cada aparición única de un jugador:
```sql
profile_id          -- ID único del perfil
feb_id              -- ID FEB (puede cambiar)
name_raw            -- Nombre original
name_normalized     -- Nombre normalizado para matching
team_id             -- Equipo
season              -- Temporada
competition_id      -- Competición
birth_year          -- Año de nacimiento (si disponible)
first_game_date     -- Primera aparición
last_game_date      -- Última aparición
total_games         -- Partidos jugados con este perfil
is_consolidated     -- Si está confirmado como perfil único
consolidated_player_id  -- Referencia al jugador consolidado
```

#### 2. `player_identity_candidates`
Candidatos de merge entre perfiles:
```sql
candidate_id        -- ID único del candidato
profile_id_1        -- Primer perfil
profile_id_2        -- Segundo perfil
name_match_score    -- Similitud de nombres (0-1)
age_match_score     -- Similitud de edad (0-1)
team_overlap_score  -- Solapamiento de equipos (0-1)
timeline_fit_score  -- Continuidad temporal (0-1)
candidate_score     -- Score total combinado
validation_status   -- pending/confirmed/rejected/unsure
confidence_level    -- very_high/high/medium/low
```

#### 3. `player_profile_metrics`
Métricas agregadas por perfil:
```sql
profile_id          -- Referencia al perfil
games_played        -- Partidos jugados
avg_points          -- Puntos promedio
avg_offensive_rating -- OER promedio
avg_z_offensive_rating -- OER normalizado
performance_tier    -- elite/very_good/above_average/average/below_average
```

#### 4. `player_profile_potential`
Score de potencial para scouting:
```sql
profile_id              -- Referencia al perfil
age_projection_score    -- Score basado en edad (0-1)
performance_trend_score -- Score basado en tendencia (0-1)
consistency_score       -- Score de consistencia (0-1)
advanced_metrics_score  -- Score de métricas avanzadas (0-1)
potential_score         -- Score total de potencial (0-1)
potential_tier          -- very_high/high/medium/low/very_low
is_young_talent         -- Flag: < 23 años con buen rendimiento
is_breakout_candidate   -- Flag: tendencia muy positiva
is_consistent_performer -- Flag: bajo std, alto rendimiento
```

## 🎯 Algoritmo de Candidate Score

### Fórmula
```
candidate_score = 0.40 × name_match +
                 0.30 × age_match +
                 0.20 × team_overlap +
                 0.10 × timeline_fit
```

### Componentes

#### 1. Name Match (40%)
- **Estrategia**: Comparación inteligente de componentes
  - Coincidencia exacta de apellidos: 0.60
  - Tokens de apellidos (Jaccard): 0.60 × similarity
  - Coincidencia de iniciales: 0.20
  - Coincidencia de nombre completo: 0.20

**Ejemplos:**
- "JUAN PÉREZ" vs "J. PÉREZ" → 0.80 (apellidos + inicial)
- "PÉREZ, JUAN" vs "JUAN PÉREZ" → 1.00 (match completo)
- "J.M. GARCÍA" vs "JOSÉ MARÍA GARCÍA" → 0.70 (apellidos + inicial parcial)

#### 2. Age Match (30%)
- **Diferencia 0 años**: 1.0
- **Diferencia 1 año**: 0.7 (puede ser error en datos)
- **Diferencia 2 años**: 0.3
- **Diferencia > 2 años**: 0.0
- **Sin información**: 0.5 (neutral)

#### 3. Team Overlap (20%)
- **Mismo equipo**: 1.0
- **Equipos diferentes**: 0.2
- **Sin información**: 0.3

#### 4. Timeline Fit (10%)
- **Misma temporada**: 0.8 (fichaje)
- **Temporadas consecutivas**: 1.0
- **Gap de 1 año**: 0.6
- **Gap de 2-4 años**: 0.3
- **Gap > 4 años**: 0.1

### Clasificación de Confianza
- **very_high**: score ≥ 0.85
- **high**: score ≥ 0.70
- **medium**: score ≥ 0.50
- **low**: score < 0.50

## 🎯 Score de Potencial

### Fórmula
```
potential_score = 0.30 × age_projection +
                 0.40 × performance +
                 0.20 × consistency +
                 0.10 × advanced_metrics
```

### Componentes

#### 1. Age Projection (30%)
- **≤ 21 años**: 1.0 (muy joven, alto potencial)
- **22-24 años**: 0.8
- **25-27 años**: 0.5
- **28-30 años**: 0.3
- **> 30 años**: 0.1

#### 2. Performance (40%)
- Basado en z-scores de OER y PER
- Normalizado a rango 0-1

#### 3. Consistency (20%)
- Basado en desviación estándar de OER
- std bajo = score alto

#### 4. Advanced Metrics (10%)
- Basado en TS% (True Shooting %)
- TS% > 55% es muy bueno

### Clasificación
- **very_high**: ≥ 0.75
- **high**: ≥ 0.60
- **medium**: ≥ 0.45
- **low**: ≥ 0.30
- **very_low**: < 0.30

## 🚀 Uso del Sistema

### 1. Ejecutar ETL con Perfiles

```bash
# ETL completo con sistema de perfiles (por defecto)
python src/ml/etl_processor.py

# ETL con opciones
python src/ml/etl_processor.py --limit 100 --masc-only

# ETL sin generar candidatos automáticamente
python src/ml/etl_processor.py --no-candidates

# ETL con threshold personalizado
python src/ml/etl_processor.py --candidate-threshold 0.60

# ETL en modo legacy (jugadores únicos, sin perfiles)
python src/ml/etl_processor.py --legacy-mode
```

### 2. Gestionar Identidades (CLI)

#### Listar candidatos de alta confianza
```bash
python src/ml/identity_manager_cli.py list-candidates

# Con threshold personalizado
python src/ml/identity_manager_cli.py list-candidates --min-score 0.80 --limit 20
```

**Output:**
```
==================================================================================================
CANDIDATOS DE ALTA CONFIANZA (Score >= 0.70)
==================================================================================================
Total encontrados: 45

1. [Score: 0.893] ID: 123
   Perfil 1: J. PÉREZ | Equipo: 101 | Temporada: 2023/24 | Edad: 2001
   Perfil 2: JUAN PÉREZ | Equipo: 101 | Temporada: 2024/25 | Edad: 2001
   Componentes: Nombre=0.80, Edad=1.00, Equipo=1.00, Timeline=1.00
   Confianza: VERY_HIGH
```

#### Ver detalles de un perfil
```bash
python src/ml/identity_manager_cli.py profile 1234
```

**Output:**
```
================================================================================
PERFIL ID: 1234
================================================================================
Nombre: JUAN PÉREZ GARCÍA
Nombre normalizado: JUAN PEREZ GARCIA
FEB ID: 12345
Equipo: CB Barcelona
Temporada: 2024/25
Competición: Liga Endesa Masculina
Año nacimiento: 2001
Dorsal: 23

Estadísticas:
  Partidos: 28
  Minutos promedio: 24.5
  Puntos promedio: 12.3
  OER promedio: 105.7
  Performance tier: very_good

Potencial:
  Score: 0.782
  Tier: very_high
  Joven talento: Sí
```

#### Validar candidato
```bash
# Confirmar que son el mismo jugador
python src/ml/identity_manager_cli.py validate 123 confirmed --notes "Mismo jugador, verificado en vídeo"

# Rechazar (diferentes jugadores)
python src/ml/identity_manager_cli.py validate 124 rejected --notes "Homónimos, diferentes edades"

# Marcar como incierto
python src/ml/identity_manager_cli.py validate 125 unsure
```

#### Ver estadísticas de validación
```bash
python src/ml/identity_manager_cli.py stats
```

**Output:**
```
================================================================================
ESTADÍSTICAS DE VALIDACIÓN
================================================================================
PENDING: 342
CONFIRMED: 87
REJECTED: 23
UNSURE: 12

TOTAL: 464
```

#### Listar perfiles con alto potencial
```bash
python src/ml/identity_manager_cli.py potential

# Con threshold personalizado
python src/ml/identity_manager_cli.py potential --min-score 0.70 --limit 30
```

**Output:**
```
========================================================================================================================
PERFILES CON ALTO POTENCIAL (Score >= 0.60)
========================================================================================================================
Total encontrados: 142

1. [0.856] MARÍA GARCÍA LÓPEZ 🌟 JOVEN 🎯 CONSISTENTE
   ID: 2341 | CB Avenida | 2024/25 | Edad: 21
   Stats: 15.8 pts, OER=112.4 | Tier: elite | Potencial: very_high

2. [0.782] JUAN PÉREZ GARCÍA 🌟 JOVEN
   ID: 1234 | CB Barcelona | 2024/25 | Edad: 23
   Stats: 12.3 pts, OER=105.7 | Tier: very_good | Potencial: very_high
```

### 3. Uso Programático

```python
from ml.player_identity_matcher import PlayerIdentityMatcher
from ml.name_normalizer import NameNormalizer

# Normalización de nombres
normalizer = NameNormalizer()
name_norm = normalizer.normalize_name("J. PÉREZ")
# Output: "J PEREZ"

similarity = normalizer.calculate_name_similarity("J. PÉREZ", "JUAN PÉREZ")
# Output: 0.80

# Matching de identidades
matcher = PlayerIdentityMatcher("scouting_feb.db")

# Buscar candidatos para un perfil
candidates = matcher.find_candidate_matches(profile_id=1234, min_score=0.50)

# Generar todos los candidatos
count = matcher.generate_all_candidates(min_score=0.50)

# Obtener candidatos de alta confianza
high_conf = matcher.get_high_confidence_candidates(min_score=0.70)

# Validar candidato
success = matcher.validate_candidate(
    candidate_id=123,
    status="confirmed",
    validated_by="staff_user",
    notes="Verificado en vídeo"
)
```

## 🔄 Flujo de Trabajo Recomendado

### Fase 1: Carga Inicial
1. Ejecutar ETL con sistema de perfiles
2. Sistema genera automáticamente candidatos (threshold 0.50)
3. Calcular métricas y potential scores

### Fase 2: Revisión de Alta Confianza
1. Listar candidatos con score ≥ 0.80
2. Revisar y validar manualmente
3. Para cada candidato:
   - Ver detalles de ambos perfiles
   - Verificar estadísticas, equipos, temporadas
   - Validar como `confirmed`, `rejected` o `unsure`

### Fase 3: Revisión de Media Confianza
1. Listar candidatos con score 0.60-0.80
2. Análisis más detallado
3. Considerar contexto adicional (vídeos, equipos vinculados)

### Fase 4: Consolidación
1. Para candidatos confirmados, crear registros consolidados
2. Actualizar `consolidated_player_id` en perfiles
3. Marcar perfiles como `is_consolidated = 1`

### Fase 5: Scouting
1. Listar perfiles con alto potencial
2. Filtrar por criterios:
   - `is_young_talent`: Menores de 23 años
   - `potential_tier`: very_high, high
   - `performance_tier`: elite, very_good
3. Generar informes de candidatos para el staff

## 📊 Consultas SQL Útiles

### Perfiles sin validar con alta similitud
```sql
SELECT 
    c.candidate_id,
    c.candidate_score,
    p1.name_raw as name_1,
    p2.name_raw as name_2,
    p1.season as season_1,
    p2.season as season_2
FROM player_identity_candidates c
JOIN player_profiles p1 ON c.profile_id_1 = p1.profile_id
JOIN player_profiles p2 ON c.profile_id_2 = p2.profile_id
WHERE c.validation_status = 'pending'
    AND c.candidate_score >= 0.75
ORDER BY c.candidate_score DESC;
```

### Top jugadores jóvenes con potencial
```sql
SELECT 
    pp.profile_id,
    pp.name_raw,
    pp.birth_year,
    t.team_name,
    ppm.avg_points,
    ppm.avg_offensive_rating,
    ppp.potential_score
FROM player_profiles pp
JOIN player_profile_potential ppp ON pp.profile_id = ppp.profile_id
JOIN player_profile_metrics ppm ON pp.profile_id = ppm.profile_id
JOIN teams t ON pp.team_id = t.team_id
WHERE ppp.is_young_talent = 1
    AND ppp.potential_score >= 0.70
ORDER BY ppp.potential_score DESC
LIMIT 50;
```

### Perfiles consolidados de un jugador
```sql
SELECT 
    pp.*,
    t.team_name,
    ppm.avg_points,
    ppm.performance_tier
FROM player_profiles pp
LEFT JOIN teams t ON pp.team_id = t.team_id
LEFT JOIN player_profile_metrics ppm ON pp.profile_id = ppm.profile_id
WHERE pp.consolidated_player_id = 123
ORDER BY pp.season;
```

## 🎯 Mejoras Futuras

### Corto Plazo
- [ ] UI web para revisión de candidatos
- [ ] Export de informes en PDF/Excel
- [ ] Integración con vídeos de partidos

### Medio Plazo
- [ ] Aprendizaje automático del matching (feedback loop)
- [ ] Detección de equipos vinculados
- [ ] Análisis de progresión multi-temporada

### Largo Plazo
- [ ] Sistema de recomendación automática
- [ ] Predicción de rendimiento futuro
- [ ] Integración con otros sistemas de datos

## 📖 Referencias

- [Enlace al análisis original](https://chatgpt.com/share/69765935-87d4-8013-af91-cd4d97b13e4c)
- Documentación de métricas avanzadas: [ML_SYSTEM.md](ML_SYSTEM.md)
- Normalización Z-Score: [ZSCORE_NORMALIZATION.md](ZSCORE_NORMALIZATION.md)
