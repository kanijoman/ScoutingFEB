# Reorganización de Estructura del Proyecto

## 📁 Cambios Realizados

### Nueva Estructura de Carpetas

Se ha reorganizado el proyecto para mejorar la mantenibilidad y claridad:

```
ScoutingFEB/
├── ui/                      # 🆕 Componentes de interfaz gráfica
│   ├── __init__.py
│   ├── scouting_ui.py      # Ventana principal (antes en raíz)
│   └── data_admin.py       # Widget de administración (antes ui_data_admin.py)
│
├── docs/                    # 🆕 Documentación técnica
│   ├── UI_README.md        # Guía de interfaz gráfica
│   ├── DATA_ADMIN_GUIDE.md # Guía de administración
│   ├── ARCHITECTURE.md     # Arquitectura del sistema
│   ├── ML_SYSTEM.md        # Sistema ML
│   ├── ML_EXECUTIVE_SUMMARY.md
│   └── PLAYER_IDENTITY_SYSTEM.md
│
├── src/                     # Código fuente principal
│   ├── scraper/            # Módulo de scraping
│   ├── database/           # Clientes de BD
│   └── ml/                 # Machine Learning
│
├── examples/                # Scripts de ejemplo
├── models/                  # Modelos ML entrenados
│
├── run_ui.py               # 🆕 Lanzador de interfaz gráfica
├── evaluate_team.py        # Script CLI de evaluación
├── requirements.txt        # Dependencias base
├── requirements_ui.txt     # Dependencias UI (PyQt6)
├── README.md              # Documentación principal
└── QUICKSTART.md          # Guía rápida
```

## 🔄 Archivos Movidos

### UI Components → ui/
- `scouting_ui.py` → `ui/scouting_ui.py`
- `ui_data_admin.py` → `ui/data_admin.py`

### Documentación → docs/
- `UI_README.md` → `docs/UI_README.md`
- `DATA_ADMIN_GUIDE.md` → `docs/DATA_ADMIN_GUIDE.md`
- `ARCHITECTURE.md` → `docs/ARCHITECTURE.md`
- `ML_SYSTEM.md` → `docs/ML_SYSTEM.md`
- `ML_EXECUTIVE_SUMMARY.md` → `docs/ML_EXECUTIVE_SUMMARY.md`
- `PLAYER_IDENTITY_SYSTEM.md` → `docs/PLAYER_IDENTITY_SYSTEM.md`

## ✏️ Actualizaciones de Código

### ui/scouting_ui.py
- Actualizado `sys.path` para apuntar a `parent.parent / "src"`
- Import de `data_admin` cambiado a `from ui.data_admin import DataAdminWidget`
- DB path actualizado con `Path(__file__).parent.parent / "scouting_feb.db"`

### ui/data_admin.py
- Actualizado `sys.path` para apuntar a `parent.parent / "src"`
- DB path actualizado en función `search_players()`

### run_ui.py (NUEVO)
- Punto de entrada único para lanzar la interfaz gráfica
- Maneja paths correctamente desde la raíz del proyecto
- Imports: `from ui.scouting_ui import main`

## 📝 Documentación Actualizada

### README.md
- Sección de estructura actualizada con carpetas `ui/` y `docs/`
- Nueva sección "Uso" destacando la interfaz gráfica
- Referencias actualizadas a documentación en `docs/`

### QUICKSTART.md
- Opción 1 ahora es la interfaz gráfica (`python run_ui.py`)
- Instrucciones de instalación incluyen `requirements_ui.txt`
- Referencias a documentación en `docs/`

## 🚀 Cómo Usar Después de la Reorganización

### Interfaz Gráfica (Recomendado)

```powershell
# Primera vez: instalar dependencias UI
pip install -r requirements_ui.txt

# Lanzar aplicación
python run_ui.py
```

### Scripts CLI

```powershell
# Evaluación de equipos
python evaluate_team.py

# Scraping
python src/run_scraping.py

# Pipeline ML
python src/run_ml_pipeline.py
```

### Documentación

Toda la documentación técnica ahora está en `docs/`:

```powershell
# Ver documentación de UI
cat docs/UI_README.md

# Ver guía de administración de datos
cat docs/DATA_ADMIN_GUIDE.md

# Ver arquitectura del sistema
cat docs/ARCHITECTURE.md
```

## ✅ Verificación

Para verificar que todo funciona correctamente:

1. **Instalar dependencias UI**:
   ```powershell
   pip install -r requirements_ui.txt
   ```

2. **Lanzar interfaz gráfica**:
   ```powershell
   python run_ui.py
   ```
   
   Deberías ver la ventana principal con 4 tabs:
   - 🏀 Evaluación de Equipos
   - 👤 Análisis de Jugadoras
   - 📊 Estadísticas
   - ⚙️ Administración

3. **Probar funcionalidad básica**:
   - Navegar entre tabs
   - Seleccionar una competición y equipo
   - Ver datos de administración

## 🔧 Solución de Problemas

### Error: "ModuleNotFoundError: No module named 'PyQt6'"

**Solución**:
```powershell
pip install -r requirements_ui.txt
```

### Error: "ModuleNotFoundError: No module named 'ui'"

**Solución**: Asegúrate de ejecutar desde la raíz del proyecto:
```powershell
cd d:\ScoutingFEB
python run_ui.py
```

### Error: "No such file or directory: scouting_feb.db"

**Solución**: La UI buscará la BD en la raíz del proyecto. Si no existe:
```powershell
# Ejecutar pipeline ETL para crear la BD
python src/run_ml_pipeline.py
```

## 📌 Beneficios de la Nueva Estructura

1. **Separación de Concerns**:
   - UI en `ui/`
   - Documentación en `docs/`
   - Código fuente en `src/`

2. **Más Limpio**:
   - Raíz del proyecto con solo archivos esenciales
   - Documentación organizada en un lugar

3. **Escalabilidad**:
   - Fácil añadir nuevos widgets en `ui/`
   - Fácil añadir nueva documentación en `docs/`

4. **Mejor Developer Experience**:
   - `run_ui.py` como punto de entrada único
   - Paths relativos manejados correctamente
   - Imports más claros

## 🎯 Próximos Pasos

La estructura ahora está lista para:
- Añadir más widgets de UI en `ui/`
- Crear sub-módulos dentro de `ui/` si crece (ej: `ui/widgets/`, `ui/dialogs/`)
- Añadir tests en `tests/`
- Documentación adicional en `docs/`

---

**Fecha de reorganización**: 11 de febrero de 2026  
**Versión**: 2.0
