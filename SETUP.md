# Guía de Setup Inicial

Esta guía explica cómo generar los datos calculados (modelos ML y base de datos) después de clonar el repositorio.

---

## ⚠️ Archivos No Incluidos en el Repositorio

Los siguientes archivos **NO están en Git** porque son datos generados (no código fuente):

### 1. Base de Datos
- `scouting_feb.db` (~45 MB con datos completos)

### 2. Modelos ML (directorio `models/`)
- `points_predictor.joblib`
- `points_predictor_metadata.json`
- `points_predictor_shap_summary.png`
- `efficiency_predictor.joblib`
- `efficiency_predictor_metadata.json`
- `efficiency_predictor_shap_summary.png`

---

## 🚀 Setup Completo

### Paso 1: Clonar Repositorio

```bash
git clone <URL_del_repositorio>
cd ScoutingFEB
```

### Paso 2: Instalar Dependencias

```bash
# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### Paso 3: Configurar MongoDB

El sistema requiere MongoDB para el scraping inicial:

```bash
# Instalar MongoDB (si no está instalado)
# Ver: https://www.mongodb.com/docs/manual/installation/

# Iniciar servicio MongoDB
# Windows: net start MongoDB
# Linux/Mac: sudo systemctl start mongod
```

### Paso 4: Generar Base de Datos

#### 4.1 Scraping de Datos (Primera Vez)

```bash
python src/run_scraping.py
```

**Tiempo estimado**: 
- Temporada actual: 10-30 minutos
- Múltiples temporadas: 1-3 horas

**Qué hace**:
- Descarga datos de partidos desde web de la FEB
- Almacena en MongoDB (colecciones separadas por género)
- Sistema incremental (solo descarga nuevos partidos)

#### 4.2 ETL y Procesamiento

```bash
python src/main.py
```

**Tiempo estimado**: 5-15 minutos

**Qué hace**:
- Lee datos de MongoDB
- Procesa y normaliza estadísticas
- Calcula z-scores y métricas avanzadas
- Genera `scouting_feb.db` (SQLite)
- Resuelve identidades de jugadores
- Calcula potencial de carrera

**Resultado**: Base de datos `scouting_feb.db` lista para uso

### Paso 5: Entrenar Modelos ML

```bash
python src/run_ml_pipeline.py
```

**Tiempo estimado**: 5-10 minutos

**Qué hace**:
- Carga datos desde `scouting_feb.db`
- Prepara features para ML
- Entrena modelos XGBoost
- Genera explicaciones SHAP
- Guarda modelos en `models/`

**Resultado**: 6 archivos en directorio `models/`

---

## ✅ Verificación

Después del setup, deberías tener:

```
ScoutingFEB/
├── scouting_feb.db          ✓ Generada (40-50 MB)
├── models/
│   ├── README.md            ✓ En Git
│   ├── *_predictor.joblib   ✓ Generados (2 archivos)
│   ├── *_metadata.json      ✓ Generados (2 archivos)
│   └── *_shap_summary.png   ✓ Generados (2 archivos)
└── (resto de archivos)      ✓ En Git
```

### Comando de Verificación

```bash
# Verificar base de datos
ls -lh scouting_feb.db

# Verificar modelos
ls -lh models/
```

---

## 🔄 Actualización de Datos

### Actualizar con Nuevos Partidos

```bash
# 1. Scraping incremental (solo descarga nuevos partidos)
python src/run_scraping.py

# 2. Procesar nuevos datos
python src/main.py

# 3. Reentrenar modelos (opcional, si hay cambios significativos)
python src/run_ml_pipeline.py
```

### Borrar y Regenerar Todo

```bash
# Eliminar datos existentes
rm scouting_feb.db
rm models/*.joblib models/*.json models/*.png

# Regenerar desde cero
python src/run_scraping.py      # Scraping completo
python src/main.py              # ETL completo
python src/run_ml_pipeline.py   # Entrenar modelos
```

---

## 📊 Uso del Sistema

Una vez completado el setup, puedes usar el sistema:

### Ejemplos Básicos

```bash
# Analizar potencial de carrera
python examples/analyze_career_potential.py

# Buscar jugadores con filtros
python examples/analyze_potential_with_filters.py

# Gestión de identidades
python examples/identity_system_examples.py
```

### Acceso Directo a Datos

```python
import sqlite3

# Conectar a base de datos
conn = sqlite3.connect('scouting_feb.db')
cur = conn.cursor()

# Query de ejemplo
cur.execute("""
    SELECT player_name, unified_potential_score
    FROM player_career_potential
    ORDER BY unified_potential_score DESC
    LIMIT 10
""")

for row in cur.fetchall():
    print(f"{row[0]}: {row[1]:.3f}")

conn.close()
```

---

## 🐛 Troubleshooting

### Error: MongoDB no conecta
```bash
# Verificar que MongoDB esté corriendo
mongo --eval "db.version()"

# Iniciar servicio
# Windows: net start MongoDB
# Linux: sudo systemctl start mongod
```

### Error: Falta scouting_feb.db
```bash
# Regenerar base de datos
python src/run_scraping.py
python src/main.py
```

### Error: No hay modelos
```bash
# Entrenar modelos
python src/run_ml_pipeline.py
```

### Base de datos vacía
```bash
# Verificar que el scraping funcionó
python -c "from src.database.mongodb_client import MongoDBClient; \
client = MongoDBClient(); \
print(f'Partidos: {client.games_collection.count_documents({})}')
```

---

## 📚 Documentación Adicional

- **Instalación completa**: [INSTALLATION.md](INSTALLATION.md)
- **Inicio rápido**: [QUICKSTART.md](QUICKSTART.md)
- **Sistema ML**: [ML_SYSTEM.md](ML_SYSTEM.md)
- **Arquitectura**: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 💡 Notas Importantes

1. **MongoDB es temporal**: Solo se usa para scraping inicial. Después del ETL, todo está en SQLite.

2. **Modelos no versionados**: Los modelos ML se entrenan localmente porque:
   - Son archivos binarios grandes (5-10 MB)
   - Dependen de los datos específicos de cada instalación
   - Se regeneran fácilmente

3. **Base de datos no versionada**: La DB SQLite no se versiona porque:
   - Es grande (40-50 MB)
   - Contiene datos en constante cambio
   - Se regenera fácilmente con scraping

4. **Setup una sola vez**: Después del setup inicial, solo necesitas actualizar datos incrementalmente.

---

**Tiempo total de setup**: ~30-60 minutos (dependiendo de cantidad de datos a descargar)
