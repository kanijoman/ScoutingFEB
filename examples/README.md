# Ejemplos de Uso - ScoutingFEB

Esta carpeta contiene scripts de ejemplo que demuestran cómo usar las diferentes funcionalidades del sistema ScoutingFEB.

## 📋 Scripts Disponibles

### Análisis de Potencial de Jugadores

#### `analyze_career_potential.py`
Analiza el potencial de carrera de jugadores usando el sistema de scoring.

**Uso**:
```bash
python examples/analyze_career_potential.py
```

**Funcionalidad**:
- Calcula scores de potencial de carrera para jugadores
- Identifica jugadores con mayor proyección
- Analiza trayectorias ascendentes/descendentes

---

#### `analyze_potential_with_filters.py`
Análisis de potencial con filtros personalizados (edad, nivel, posición).

**Uso**:
```bash
python examples/analyze_potential_with_filters.py
```

**Funcionalidad**:
- Filtra jugadores por edad, nivel de competición, o posición
- Genera rankings personalizados
- Compara potencial entre diferentes grupos

---

#### `analyze_team_potential.py`
Analiza el potencial agregado de equipos completos.

**Uso**:
```bash
python examples/analyze_team_potential.py
```

**Funcionalidad**:
- Evalúa el roster completo de un equipo
- Calcula potencial promedio del equipo
- Identifica fortalezas y debilidades

---

#### `analyze_team_potential_v2.py`
Versión mejorada del análisis de equipos con métricas adicionales.

**Uso**:
```bash
python examples/analyze_team_potential_v2.py
```

**Funcionalidad**:
- Análisis más detallado de equipos
- Distribución de potencial por posición
- Proyecciones de rendimiento futuro

---

### Evaluación de Equipos

#### `evaluate_team.py`
Evaluación integral de equipos con comparativas.

**Uso**:
```bash
python examples/evaluate_team.py
```

**Funcionalidad**:
- Compara estadísticas entre equipos
- Genera reportes de evaluación
- Visualiza métricas clave

---

### Análisis de Resultados ETL

#### `analyze_etl_results.py`
Verifica y analiza los resultados del proceso ETL.

**Uso**:
```bash
python examples/analyze_etl_results.py
```

**Funcionalidad**:
- Cuenta registros procesados
- Muestra distribución por temporada
- Verifica integridad de datos

---

### Sistema de Identidades

#### `identity_system_examples.py`
Ejemplos de uso del sistema de gestión de identidades de jugadores.

**Uso**:
```bash
python examples/identity_system_examples.py
```

**Funcionalidad**:
- Busca candidatos de consolidación
- Muestra perfiles de jugadores
- Valida identidades

**Ver documentación completa**: [../docs/PLAYER_IDENTITY_SYSTEM.md](../docs/PLAYER_IDENTITY_SYSTEM.md)

---

## 🔧 Requisitos

Todos los scripts requieren:
- Base de datos SQLite (`scouting_feb.db`) con datos procesados
- Dependencias instaladas: `pip install -r requirements.txt`

## 📝 Notas

- Ejecutar los scripts desde el directorio raíz del proyecto
- Algunos scripts pueden tardar varios minutos en ejecutarse con datasets grandes
- Los resultados se muestran en consola, algunos scripts generan visualizaciones

## 🚀 Flujo de Trabajo Recomendado

1. **Primero**: Ejecutar el ETL completo
   ```bash
   python src/main.py --etl
   ```

2. **Verificar datos**: Ejecutar `analyze_etl_results.py`
   ```bash
   python examples/analyze_etl_results.py
   ```

3. **Análisis de jugadores**: Ejecutar scripts de potencial
   ```bash
   python examples/analyze_career_potential.py
   python examples/analyze_potential_with_filters.py
   ```

4. **Análisis de equipos**: Ejecutar scripts de evaluación
   ```bash
   python examples/evaluate_team.py
   python examples/analyze_team_potential_v2.py
   ```

---

## 💡 Personalizando los Scripts

Todos los scripts son plantillas que puedes modificar. Ejemplo:

```python
# En analyze_potential_with_filters.py
# Cambiar filtros:
min_age = 18
max_age = 25
min_games = 10
competition_level = 'LF'

# Ejecutar análisis personalizado
results = analyze_players_with_filters(
    min_age=min_age, 
    max_age=max_age,
    min_games=min_games,
    level=competition_level
)
```

---

**Última actualización**: Febrero 16, 2026
