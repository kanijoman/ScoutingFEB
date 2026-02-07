# CORRECCIÓN: Niveles de Competición en el ETL

## Problema Identificado

Al ejecutar el ETL, todos los partidos se asignaban a **Nivel 4** en lugar de sus niveles correctos:
- LF ENDESA debería ser Nivel 1 (primera división)
- LF CHALLENGE debería ser Nivel 2 (segunda división, desde 2021/22)
- L.F.-2 debería ser Nivel 2 (hasta 2020/21) o Nivel 3 (desde 2021/22)

## Causa Raíz

La función `initialize_competition_levels()` en [src/ml/normalization.py](src/ml/normalization.py) tenía 3 bugs:

1. **Nombres no coincidían**: El diccionario usaba `'LIGA FEMENINA'` pero la BD tiene `'LF ENDESA'`
2. **Formato de temporada incorrecto**: Usaba `season.split('-')` para temporadas con formato `'2001/2002'` (con `/`)
3. **Lógica de L.F.-2 incompleta**: No manejaba correctamente el cambio de nivel 2→3 en 2021/22

## Solución Implementada

### 1. Corrección en `src/ml/normalization.py` (líneas 488-591)

```python
# ANTES (incorrecto):
default_levels = {
    'LIGA FEMENINA': 1,      # ✗ No coincide con 'LF ENDESA'
    'LIGA FEMENINA 2': 2,    # ✗ No coincide con 'L.F.-2'
    'LIGA CHALLENGE': 2,     # ✗ No coincide con 'LF CHALLENGE'
}
season_year = int(season.split('-')[0])  # ✗ Falla con '2001/2002'

# DESPUÉS (correcto):
default_levels = {
    'LF ENDESA': 1,          # ✓ Nombre exacto de la BD
    'LF CHALLENGE': 2,       # ✓ Nombre exacto de la BD
    'L.F.-2': 2,            # ✓ Nombre exacto de la BD
}
season_year = int(season.split('/')[0])  # ✓ Parsea '2001/2002' correctamente

# Lógica especial para L.F.-2:
if comp_name == 'L.F.-2':
    if season_year >= 2021:
        level = 3  # Tercera división (desde reforma)
        weight = 1.0
    else:
        level = 2  # Segunda división (antes de reforma)
        weight = 1.25
```

### 2. Scripts Creados

- **[fix_competition_levels.py](fix_competition_levels.py)**: Corrige los niveles en la BD actual (ya ejecutado ✓)
- **[test_competition_levels_init.py](test_competition_levels_init.py)**: Verifica que la función corregida funciona (tests pasados ✓)

## Verificación

```bash
$ python test_competition_levels_init.py
✅ TODOS LOS TESTS PASARON

Niveles asignados:
  LF ENDESA    | Nivel 1 | 2001/2002 - 2025/2026 | 25 temporadas
  LF CHALLENGE | Nivel 2 | 2021/2022 - 2025/2026 | 5 temporadas
  L.F.-2       | Nivel 2 | 2001/2002 - 2020/2021 | 20 temporadas
  L.F.-2       | Nivel 3 | 2021/2022 - 2025/2026 | 5 temporadas
```

## Impacto

Los niveles de competición afectan a:
1. **Cálculo de Z-Scores**: Las estadísticas se normalizan dentro de cada nivel
2. **Modelo ML**: El nivel es una feature importante para predecir potencial
3. **Análisis comparativo**: Permite comparar jugadoras en contextos similares

## Próximos Pasos

⚠️ **IMPORTANTE**: Debes re-calcular los Z-Scores para que usen los niveles correctos:

```bash
cd src
python run_ml_pipeline.py --etl-only  # Re-procesa normalizaciones
```

O si solo quieres actualizar Z-Scores sin re-procesar todo:

```python
from ml.normalization import ZScoreNormalizer
normalizer = ZScoreNormalizer('scouting_feb.db')
normalizer.update_zscores_all()  # Re-calcula solo Z-Scores
```

## Estado Actual

- ✅ Niveles corregidos en `competition_levels` (tabla)
- ✅ Función `initialize_competition_levels()` corregida (código)
- ⚠️ Z-Scores pendientes de re-cálculo (se calcularon con niveles incorrectos)

En futuras ejecuciones del ETL desde cero, los niveles se asignarán automáticamente de forma correcta.
