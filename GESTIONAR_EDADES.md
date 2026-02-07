# Sistema de Gestión de Edades de Jugadoras

Este sistema te permite añadir edades manualmente, detectar duplicados y exportar listados.

## Uso básico

### 1. Modo interactivo (recomendado)
```bash
python manage_player_ages.py
```

Te muestra las 30 jugadoras sin edad con mayor potencial y opciones interactivas:
- **Opción 1**: Seleccionar jugadora por número para añadir edad
- **Opción 2**: Buscar duplicados de una jugadora
- **Opción 3**: Exportar lista completa a CSV
- **Opción 4**: Salir

### 2. Procesar una jugadora específica
```bash
python manage_player_ages.py "A. POCEK"
```

Muestra:
- Detalles completos de la jugadora
- Equipos por temporada
- Posibles duplicados (similitud > 75%)
- URL de búsqueda en la FEB
- Opciones para añadir edad

### 3. Buscar duplicados
```bash
python manage_player_ages.py --find "GARCIA"
```

Lista todas las jugadoras con nombres similares a "GARCIA"

### 4. Exportar a CSV
```bash
python manage_player_ages.py --export
```

Genera `players_without_age.csv` con todas las jugadoras sin edad

### 5. Actualización en lote desde CSV
```bash
python manage_player_ages.py --csv edades_actualizadas.csv
```

El CSV debe tener estas columnas:
- `player_name`: Nombre exacto (ej: "A. POCEK")
- `birth_year`: Año de nacimiento (ej: 1995)

Ejemplo de CSV:
```csv
player_name,birth_year
A. POCEK,1995
M. COULIBALY,1997
A. TRAORE,1995
```

## Ejemplos de uso

### Ejemplo 1: Añadir edad a una jugadora
```bash
$ python manage_player_ages.py "A. POCEK"

====================================================================================================
JUGADORA: A. POCEK
====================================================================================================

Datos actuales:
  • Score: 0.552 (high)
  • Temporadas: 3 (2020/2021 - 2022/2023)
  • Partidos: 670
  • Birth year: NO DISPONIBLE

Equipos:
  • 2022/2023: ARASKI AES
  • 2021/2022: ARASKI AES
  • 2020/2021: LOINTEK GERNIKA BIZKAIA

----------------------------------------------------------------------------------------------------
Buscando posibles duplicados...
✓ No se encontraron duplicados

🔗 URL de búsqueda en FEB:
   https://www.feb.es/Resultados/Competiciones/buscador_jugadores.aspx?nombre=A%20POCEK

----------------------------------------------------------------------------------------------------
OPCIONES:
  1. Añadir año de nacimiento
  2. Ver duplicados en detalle
  3. Copiar URL de la FEB
  0. Volver al menú principal
----------------------------------------------------------------------------------------------------

Seleccionar opción: 1
Año de nacimiento (ej: 2000): 1995

✓ Actualizado: 1 en career_potential, 3 en profiles
  • Edad actual: 30 años
```

### Ejemplo 2: Detectar duplicados
```bash
$ python manage_player_ages.py --find "L. GARCIA ANDRES"

Buscando duplicados de: L. GARCIA ANDRES

Encontrados 2 posibles duplicados:
#    Nombre                              Año    Simil    Temp   Score
--------------------------------------------------------------------------------
1    L. GARCIA ANDRES                    1998   100.0%   1      0.431
2    L. GARCIA ANDRES                    2002   100.0%   4      0.440
```

Como vemos, son hermanas con el mismo nombre normalizado pero diferentes años de nacimiento (correcto).

### Ejemplo 3: Proceso completo con CSV

1. **Exportar lista**:
```bash
python manage_player_ages.py --export
```

2. **Editar CSV** (Excel, LibreOffice, etc.):
- Abre `players_without_age.csv`
- Busca información en FEB o fuentes externas
- Añade columna `birth_year` con años de nacimiento
- Guarda como `edades_actualizadas.csv`

3. **Importar actualizaciones**:
```bash
python manage_player_ages.py --csv edades_actualizadas.csv
```

## Detección de duplicados

El sistema usa similitud de texto (algoritmo SequenceMatcher) para detectar:
- **Similitud > 85%**: Probables duplicados
- **Similitud 70-85%**: Posibles variantes del nombre
- **Similitud < 70%**: No relacionados

Casos detectados:
- Mismo nombre, diferentes años: **NO es duplicado** (ej: hermanas)
- Variantes ortográficas: **Posible duplicado** (ej: "A. MARTIN" vs "ANA MARTIN")
- Abreviaturas diferentes: **Verificar manualmente**

## Fusión de perfiles (avanzado)

⚠️ **CUIDADO**: La fusión de perfiles es irreversible. Solo usar cuando estés 100% seguro de que son la misma persona.

La fusión debe hacerse manualmente editando el código. No hay interfaz automática por seguridad.

## Fuentes de información

### 1. FEB (Federación Española de Baloncesto)
El script genera automáticamente URLs de búsqueda:
```
https://www.feb.es/Resultados/Competiciones/buscador_jugadores.aspx?nombre=NOMBRE
```

### 2. Otras fuentes
- Páginas web de equipos
- Redes sociales de equipos
- Basketball-reference (internacional)
- Eurobasket.com
- FIBA.basketball

## Estadísticas

Jugadoras sin edad en la base de datos: **460** (~27% del total)

Top prioridades (alto potencial sin edad):
- A. POCEK: 0.552 (high)
- M. COULIBALY: 0.500 (high)
- A. TRAORE: 0.459 (medium)

## Notas técnicas

- Los cambios afectan a `player_career_potential` y `player_profiles`
- Después de añadir edades, ejecutar ETL completo para recalcular edad actual
- O usar: `UPDATE player_career_potential SET current_age = 2025 - birth_year WHERE birth_year IS NOT NULL`
- Las edades se mantienen después de ejecutar ETL (no se sobreescriben)

## Troubleshooting

**Problema**: "No se encontró la jugadora"
- Verificar que el nombre esté exactamente como en la BD (usa mayúsculas y normalización)
- Probar con modo interactivo para ver lista exacta

**Problema**: "Error al actualizar"
- Verificar permisos de escritura en la BD
- Comprobar que no hay otro proceso usando la BD

**Problema**: "Duplicados no detectados"
- Ajustar threshold en `find_potential_duplicates()` (default: 0.85)
- Threshold más bajo = más resultados pero más falsos positivos
