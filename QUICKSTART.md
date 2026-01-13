# Guía de Inicio Rápido - ScoutingFEB

Esta guía te ayudará a poner en marcha el proyecto ScoutingFEB en pocos minutos.

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener:

- ✅ Python 3.8 o superior instalado
- ✅ MongoDB 4.0 o superior instalado y ejecutándose
- ✅ Conexión a Internet

## 🚀 Instalación Rápida

### Paso 1: Navegar al directorio del proyecto

```powershell
cd d:\ScoutingFEB
```

### Paso 2: Ejecutar el script de instalación

```powershell
.\install.ps1
```

Este script automáticamente:
- Verifica que Python y pip estén instalados
- Verifica que MongoDB esté instalado y ejecutándose
- Instala todas las dependencias de Python necesarias

### Paso 3: (Alternativa) Instalación manual

Si prefieres instalar manualmente:

```powershell
# Instalar dependencias
pip install -r requirements.txt

# Verificar que MongoDB esté ejecutándose
net start MongoDB
```

## 🎯 Uso Básico

### Opción 1: Usar el script de ejemplos (Recomendado)

```powershell
cd src
python examples.py
```

Esto te mostrará un menú interactivo con diferentes opciones:
1. Listar todas las competiciones disponibles
2. Scraping de una competición por nombre
3. Scraping de una competición por URL
4. Configuración personalizada de base de datos
5. Consultar partidos existentes en la base de datos

### Opción 2: Listar competiciones disponibles

```powershell
cd src
python main.py
```

Esto mostrará todas las competiciones FEB disponibles con su género detectado automáticamente.

### Opción 3: Scraping de una competición específica

Edita `src/main.py` y descomenta las líneas relevantes:

**Por nombre de competición:**
```python
scraper.scrape_competition_by_name("LF2")
```

**Por URL directa:**
```python
stats = scraper.scrape_competition(
    "https://baloncestoenvivo.feb.es/calendario/lf2/9/2024",
    "LF2 - Liga Femenina 2",
    "fem"
)
```

Luego ejecuta:
```powershell
python main.py
```

## 📊 Acceder a los Datos

### Usando MongoDB Compass (GUI)

1. Descarga MongoDB Compass: https://www.mongodb.com/products/compass
2. Conecta a: `mongodb://localhost:27017`
3. Selecciona la base de datos: `scouting_feb`
4. Explora las colecciones:
   - `all_feb_games_masc` - Partidos masculinos
   - `all_feb_games_fem` - Partidos femeninos

### Usando el código Python

```python
from main import FEBScoutingScraper

scraper = FEBScoutingScraper()

# Contar partidos
masc_count = scraper.db_client.count_games("all_feb_games_masc")
fem_count = scraper.db_client.count_games("all_feb_games_fem")
print(f"Total partidos: {masc_count + fem_count}")

# Obtener un partido específico
game = scraper.db_client.get_game("2477341", "all_feb_games_fem")
print(game)

scraper.close()
```

### Usando MongoDB Shell

```powershell
mongosh
use scouting_feb
db.all_feb_games_fem.countDocuments()
db.all_feb_games_fem.findOne()
```

## 📁 Estructura de Datos

Cada documento de partido contiene:

```json
{
  "_id": 2477341,
  "HEADER": {
    "game_code": 2477341,
    "competition": "L.F.-2",
    "competition_name": "LF2 - Liga Femenina 2",
    "season": "2024/25",
    "group": "Grupo A",
    "gender": "fem",
    "starttime": "05-10-2025 - 12:30",
    "TEAM": [
      {
        "name": "Equipo Local",
        "pts": "74",
        "id": "982047"
      },
      {
        "name": "Equipo Visitante",
        "pts": "56",
        "id": "981204"
      }
    ]
  },
  "BOXSCORE": { /* Estadísticas detalladas de jugadores */ },
  "PLAYBYPLAY": { /* Jugada a jugada */ },
  "SHOTCHART": [ /* Información de tiros */ ]
}
```

## 🎬 Ejemplos de Competiciones

Algunas competiciones populares que puedes scrapear:

- **LF2**: Liga Femenina 2
- **LF**: Liga Femenina
- **LEB ORO**: Liga LEB Oro (masculina)
- **EBA**: Liga EBA
- Y muchas más...

Para ver la lista completa, ejecuta `python main.py` o `python examples.py` (opción 1).

## 🔧 Configuración Avanzada

### Cambiar la base de datos

Edita `src/config.py`:

```python
MONGODB_CONFIG = {
    "uri": "mongodb://tu-servidor:27017/",
    "database": "tu_base_datos",
    # ...
}
```

### Ajustar el delay entre peticiones

Edita `src/config.py`:

```python
SCRAPING_CONFIG = {
    "delay_between_matches": 1.0,  # Aumentar a 1 segundo
    # ...
}
```

### Cambiar el nivel de logging

Edita `src/config.py`:

```python
LOGGING_CONFIG = {
    "level": "DEBUG",  # Más detallado
    # ...
}
```

## 🐛 Solución de Problemas

### Error: "MongoDB no está ejecutándose"

```powershell
# Iniciar MongoDB
net start MongoDB

# Verificar estado
sc query MongoDB
```

### Error: "No module named 'pymongo'"

```powershell
pip install -r requirements.txt
```

### Error: "Connection refused" al conectar a MongoDB

1. Verifica que MongoDB esté instalado
2. Verifica que el servicio esté ejecutándose
3. Verifica que el puerto 27017 no esté bloqueado

### Los logs no se generan

Verifica que tienes permisos de escritura en el directorio `src/`.

## 📚 Recursos Adicionales

- **README.md**: Documentación completa del proyecto
- **CHANGELOG.md**: Historial de cambios
- **examples.py**: Más ejemplos de uso
- **Logs**: Revisa `scouting_feb.log` para diagnóstico

## 🎓 Próximos Pasos

1. ✅ Instalar y ejecutar el scraper
2. ✅ Recopilar datos de competiciones
3. 🔜 Analizar datos con Python/Pandas
4. 🔜 Crear modelos de IA para predicción
5. 🔜 Desarrollar dashboard de visualización

## 💡 Consejos

- **Empieza pequeño**: Prueba primero con una sola competición
- **Revisa los logs**: Siempre consulta `scouting_feb.log` si algo falla
- **Usa MongoDB Compass**: Facilita la exploración de datos
- **Scraping incremental**: El sistema automáticamente omite partidos ya descargados

## 📞 ¿Necesitas Ayuda?

- Revisa el archivo `README.md` para más detalles
- Consulta los ejemplos en `examples.py`
- Revisa los logs en `scouting_feb.log`

---

¡Feliz scouting! 🏀
