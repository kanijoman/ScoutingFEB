# Guía de Instalación Completa - ScoutingFEB

## Requisitos Previos

### 1. Python
- Python 3.8 o superior
- pip (gestor de paquetes)

Verificar instalación:
```powershell
python --version
pip --version
```

### 2. MongoDB
- MongoDB 4.0 o superior
- MongoDB debe estar ejecutándose como servicio

#### Instalación de MongoDB en Windows:

**Opción A: Instalador oficial**
1. Descargar desde: https://www.mongodb.com/try/download/community
2. Ejecutar instalador
3. Seleccionar "Install MongoDB as a Service"

**Opción B: Chocolatey**
```powershell
choco install mongodb
```

**Verificar instalación:**
```powershell
# Iniciar servicio
net start MongoDB

# Verificar que esté corriendo
sc query MongoDB

# Conectar con cliente
mongo --version
```

### 3. SQLite
SQLite viene incluido con Python, no requiere instalación adicional.

## Instalación del Proyecto

### Paso 1: Clonar/Descargar el Proyecto

```powershell
# Si usas git
git clone <url-del-repositorio>
cd ScoutingFEB

# O descargar ZIP y extraer
cd ScoutingFEB
```

### Paso 2: Crear Entorno Virtual (Recomendado)

```powershell
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Si hay error de permisos, ejecutar:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Paso 3: Instalar Dependencias

```powershell
# Actualizar pip
python -m pip install --upgrade pip

# Instalar todas las dependencias
pip install -r requirements.txt
```

**Nota**: La instalación de las librerías ML puede tardar 5-10 minutos.

#### Dependencias que se instalarán:

**Core:**
- requests>=2.31.0
- beautifulsoup4>=4.12.0
- pymongo>=4.6.0

**Machine Learning:**
- xgboost>=1.7.0
- shap>=0.41.0
- scikit-learn>=1.0.0
- pandas>=1.5.0
- numpy>=1.23.0

**Visualización:**
- matplotlib>=3.5.0
- joblib>=1.2.0

### Paso 4: Verificar Instalación

```powershell
# Verificar imports Python
python -c "import xgboost; import shap; import sklearn; print('✓ ML libraries OK')"

# Verificar conexión MongoDB
python -c "from pymongo import MongoClient; client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=2000); client.server_info(); print('✓ MongoDB OK')"
```

## Configuración Inicial

### 1. Verificar Estructura de Directorios

El proyecto debería tener esta estructura:
```
ScoutingFEB/
├── src/
│   ├── database/
│   ├── scraper/
│   ├── ml/
│   └── ...
├── requirements.txt
└── README.md
```

### 2. Configuración de MongoDB

Editar `src/config.py` si es necesario:

```python
MONGODB_CONFIG = {
    "uri": "mongodb://localhost:27017/",  # Cambiar si MongoDB está en otro host
    "database": "scouting_feb",
    "collections": {
        "masculine": "all_feb_games_masc",
        "feminine": "all_feb_games_fem"
    }
}
```

## Prueba de Instalación

### Opción 1: Prueba Rápida (Sin Scraping)

```powershell
cd src

# Crear esquema SQLite
python -c "from database.sqlite_schema import SQLiteSchemaManager; m = SQLiteSchemaManager(); m.create_database(); m.print_schema_summary()"

# Si muestra el esquema sin errores, ¡instalación exitosa!
```

### Opción 2: Prueba con Datos Sintéticos

```powershell
cd src

# Ejecutar tests
python test_incremental.py

# Debería mostrar:
# ✓ PASS - Conexión MongoDB
# ✓ PASS - Métodos de estado
# etc.
```

### Opción 3: Pipeline Completo (Requiere datos)

```powershell
cd src

# Si ya tienes datos en MongoDB, ejecutar:
python run_ml_pipeline.py --limit 10

# Procesa solo 10 partidos como prueba
```

## Troubleshooting

### Error: "No module named 'xgboost'"

**Solución:**
```powershell
pip install xgboost shap scikit-learn
```

### Error: "Cannot connect to MongoDB"

**Solución:**
```powershell
# Verificar que MongoDB esté corriendo
net start MongoDB

# Si falla, verificar servicio
sc query MongoDB

# Si no existe el servicio, iniciar manualmente
mongod --dbpath "C:\data\db"
```

### Error: "SSL module not available"

**Solución:**
Reinstalar Python con soporte SSL desde python.org

### Error: "Permission denied" al activar venv

**Solución:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Error: "Microsoft Visual C++ required"

**Solución:**
Algunas librerías requieren Visual C++:
1. Descargar: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Instalar "Desktop development with C++"
3. Reinstalar paquetes: `pip install --force-reinstall xgboost`

### Instalación Lenta de Dependencias

**Solución:**
```powershell
# Usar mirror más rápido
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# O instalar paquetes precompilados
pip install --only-binary :all: xgboost shap scikit-learn
```

## Verificación Final

Ejecutar este script de verificación completa:

```powershell
python
```

```python
# En el intérprete Python:
print("Verificando instalación...")

# 1. Imports básicos
import requests
import bs4
import pymongo
print("✓ Librerías básicas OK")

# 2. Imports ML
import xgboost
import shap
import sklearn
import pandas
import numpy
print("✓ Librerías ML OK")

# 3. MongoDB
from pymongo import MongoClient
client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
client.server_info()
print("✓ MongoDB OK")

# 4. SQLite
import sqlite3
conn = sqlite3.connect(":memory:")
conn.close()
print("✓ SQLite OK")

print("\n🎉 ¡Instalación completa y funcional!")
```

Si todos los checks pasan, ¡estás listo para usar ScoutingFEB!

## Próximos Pasos

1. **Scraping inicial:**
   ```powershell
   cd src
   python main.py
   ```

2. **ETL y ML:**
   ```powershell
   python run_ml_pipeline.py
   ```

3. **Explorar documentación:**
   - [README.md](../README.md) - Visión general
   - [QUICKSTART.md](../QUICKSTART.md) - Guía rápida
   - [ML_SYSTEM.md](../ML_SYSTEM.md) - Sistema ML
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Arquitectura

## Soporte

Si encuentras problemas:
1. Revisar [TROUBLESHOOTING](#troubleshooting) arriba
2. Verificar logs en `scouting_feb.log`
3. Consultar documentación en archivos `.md`
4. Abrir issue en el repositorio (si aplica)

## Versiones Recomendadas (Probadas)

- Python: 3.10.x o 3.11.x
- MongoDB: 6.0.x o 7.0.x
- xgboost: 2.0.x
- shap: 0.43.x
- scikit-learn: 1.3.x

## Recursos Adicionales

- Python: https://www.python.org/downloads/
- MongoDB: https://www.mongodb.com/try/download/community
- XGBoost Docs: https://xgboost.readthedocs.io/
- SHAP Docs: https://shap.readthedocs.io/
