# ScoutingFEB - Interfaz Gráfica

Interfaz de escritorio moderna para el sistema de análisis de baloncesto femenino.

## 🎨 Características

### Pantalla Principal: Evaluación de Equipos
- **Selección intuitiva**: Filtro por competición y equipo
- **Búsqueda rápida**: Encuentra equipos por nombre
- **Tabla de jugadoras**: 
  - Estadísticas actuales (PTS, EFF)
  - Proyecciones 2026/2027 (→PTS, →EFF)
  - Potencial de desarrollo (POT)
  - Alertas de predicciones conservadoras (⚠)
- **Panel de resumen**:
  - Estadísticas del equipo
  - Gráfico de distribución de potencial
  - Comparación actual vs proyectado

### Funcionalidades Integradas
- ✅ **Entrenamiento automático de modelos**: Detecta si faltan modelos y los entrena
- ✅ **Tema oscuro moderno**: Diseño profesional y cómodo para la vista
- ✅ **Actualización en tiempo real**: Cambios instantáneos al seleccionar equipos
- ✅ **Código de colores**: Identificación visual rápida del potencial (Elite = dorado, etc.)
- ✅ **Administración de datos**: Scraping de nuevos partidos, ETL, gestión biográfica

## 📦 Instalación

```bash
# 1. Instalar dependencias de UI
pip install -r requirements_ui.txt

# 2. Ejecutar aplicación
python scouting_ui.py
```

## 🚀 Uso

### Primera Ejecución
1. Lanza la aplicación: `python scouting_ui.py`
2. Si no hay modelos entrenados, te preguntará si deseas entrenarlos (acepta)
3. Espera 1-2 minutos mientras entrena
4. ¡Listo! Ya puedes usar la aplicación

### Evaluación de Equipos
1. **Selecciona competición** del dropdown (ej: "LF1 FEMENINA")
2. **Selecciona equipo** del segundo dropdown
3. **Visualiza**:
   - Plantilla completa con proyecciones
   - Estadísticas agregadas del equipo
   - Gráfico de distribución de potencial

### Búsqueda Rápida
- Escribe en "Búsqueda rápida" para filtrar equipos por nombre
- Mínimo 3 caracteres

## 🎯 Interpretación de Datos

### Columnas de la Tabla

| Columna | Descripción |
|---------|-------------|
| **Jugadora** | Nombre de la jugadora |
| **Edad** | Años actuales (o N/D si no disponible) |
| **PJ** | Partidos jugados en 2025/2026 |
| **PTS** | Promedio de puntos actuales |
| **EFF** | Promedio de eficiencia actual |
| **→PTS** | Proyección puntos 2026/2027 (Modelo ML) |
| **→EFF** | Proyección eficiencia 2026/2027 (Modelo ML) |
| **POT** | Potencial de desarrollo |
| **⚠** | Alerta: Modelo conservador vs potencial alto |

### Categorías de Potencial (POT)

| Código | Significado | % | Color |
|--------|-------------|---|-------|
| **ELI** | Elite | Top 0.3% (15 jugadoras) | 🟡 Dorado |
| **VER** | Very High | Top 1.2% (54 jugadoras) | 🔵 Azul cielo |
| **HIG** | High | Top 4.5% (208 jugadoras) | 🟢 Verde claro |
| **MED** | Medium | Top 8% (357 jugadoras) | ⚪ Blanco |
| **LOW** | Low | Resto (3,739 jugadoras) | ⚪ Blanco |

### Símbolo ⚠ (Alerta)

Aparece cuando:
- Jugadora tiene potencial **Elite/Very High/High**
- PERO el modelo ML predice **descenso** en rendimiento

**Interpretación**: El modelo es conservador y predice regresión a la media, pero la jugadora puede estar en fase de crecimiento. El potencial alto sugiere que puede superar la predicción conservadora.

## 🔧 Arquitectura Técnica

### Stack Tecnológico
- **UI Framework**: PyQt6
- **Gráficos**: PyQt6-Charts
- **Backend**: SQLite + XGBoost
- **Threading**: QThread para operaciones pesadas

### Componentes Principales

```
scouting_ui.py
├── MainWindow: Ventana principal con tabs
├── TeamEvaluationWidget: Evaluación de equipos
│   ├── Controles de selección (competición/equipo)
│   ├── Tabla de roster
│   ├── Panel de estadísticas
│   └── Gráfico de potencial
├── DataAdminWidget: Administración de datos
│   ├── ScrapingThread: Scraping de nuevos partidos (MongoDB)
│   ├── ETLThread: Procesamiento ETL (MongoDB → SQLite)
│   └── Biographical Editor: Edición manual de datos biográficos
└── ModelTrainingThread: Entrenamiento en background
```

### Flujo de Datos

```
DB (SQLite) → TeamEvaluator → UI Components
                ↓
        XGBoost Models (predicciones)
```

## 📊 Próximas Funcionalidades (Roadmap)

### ~~Fase 1: Administración de Datos~~ ✅ COMPLETADA
- [x] Scraping de nuevos partidos desde FEB
- [x] Procesamiento ETL (MongoDB → SQLite)
- [x] Editor de datos biográficos manual
- [x] Importación CSV de datos biográficos

### Fase 2: Análisis de Jugadoras
- [ ] Vista de perfil individual de jugadora
- [ ] Histórico de rendimiento (gráfico temporal)
- [ ] Comparación entre jugadoras
- [ ] Exportación de informes

### Fase 3: Estadísticas Avanzadas
- [ ] Rankings de competiciones
- [ ] Top jugadoras por categoría
- [ ] Análisis de tendencias temporales
- [ ] Predicciones de MVP

### Fase 4: Mejoras de UX
- [ ] Temas personalizables (claro/oscuro)
- [ ] Exportación a PDF/Excel
- [ ] Filtros avanzados
- [ ] Dashboard configurable

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'PyQt6'"
```bash
pip install -r requirements_ui.txt
```

### Error: "No se encontró scouting_feb.db"
Asegúrate de estar en el directorio correcto donde está la base de datos.

### La aplicación se congela durante el entrenamiento
Es normal. El entrenamiento de modelos tarda 1-2 minutos. La UI se desbloqueará automáticamente.

### Las proyecciones no aparecen
1. Verifica que los modelos estén entrenados (carpeta `models/`)
2. Re-entrena borrando la carpeta `models/` y reiniciando la app

## 💡 Tips de Uso

1. **Performance**: La primera carga de un equipo puede tardar unos segundos
2. **Datos actualizados**: Para refrescar datos, cierra y reabre la aplicación
3. **Modelos**: Re-entrena modelos cuando actualices la base de datos con nuevos partidos

## 📝 Licencia

Ver archivo LICENSE en la raíz del proyecto.
