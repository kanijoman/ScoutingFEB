# Modelos de Machine Learning

Este directorio contiene los modelos de Machine Learning entrenados para el sistema de scouting.

## ⚠️ Modelos No Incluidos en el Repositorio

Los modelos entrenados **NO están incluidos** en el repositorio porque son artefactos generados (no código fuente). Deben ser entrenados localmente después de configurar el sistema.

## 📋 Modelos del Sistema

El sistema entrena dos modelos XGBoost:

1. **Points Predictor** (`points_predictor.joblib`)
   - Predice: Puntos por partido del jugador
   - Metadata: `points_predictor_metadata.json`
   - Visualización SHAP: `points_predictor_shap_summary.png`

2. **Efficiency Predictor** (`efficiency_predictor.joblib`)
   - Predice: Efficiency (valoración) por partido
   - Metadata: `efficiency_predictor_metadata.json`
   - Visualización SHAP: `efficiency_predictor_shap_summary.png`

## 🚀 Cómo Generar los Modelos

### Prerequisitos
1. Haber ejecutado el scraping de datos (ver [INSTALLATION.md](../INSTALLATION.md))
2. Tener la base de datos `scouting_feb.db` poblada con datos
3. Tener todas las dependencias instaladas (`pip install -r requirements.txt`)

### Entrenamiento

```bash
# Desde la raíz del proyecto
python src/run_ml_pipeline.py
```

Este comando:
1. ✅ Carga datos desde `scouting_feb.db`
2. ✅ Prepara features para ML
3. ✅ Entrena modelos XGBoost con validación cruzada
4. ✅ Genera explicaciones SHAP
5. ✅ Guarda modelos en este directorio

### Tiempo Estimado
- Con ~1000 jugadores: 2-5 minutos
- Con ~10000 jugadores: 10-20 minutos

## 📊 Estructura de Archivos Generados

Después de ejecutar el pipeline, este directorio contendrá:

```
models/
├── README.md  (este archivo)
├── points_predictor.joblib
├── points_predictor_metadata.json
├── points_predictor_shap_summary.png
├── efficiency_predictor.joblib
├── efficiency_predictor_metadata.json
└── efficiency_predictor_shap_summary.png
```

## 🔍 Metadata de Modelos

Los archivos `*_metadata.json` contienen información sobre el entrenamiento:

```json
{
  "model_type": "XGBRegressor",
  "target": "avg_points",
  "features_used": [...],
  "train_samples": 1234,
  "test_samples": 309,
  "cv_score_mean": 0.85,
  "cv_score_std": 0.03,
  "test_mae": 2.34,
  "test_rmse": 3.12,
  "test_r2": 0.82,
  "trained_at": "2026-02-04T12:34:56",
  "hyperparameters": {...}
}
```

## 📈 Validación de Modelos

Para validar que los modelos se entrenaron correctamente:

```python
import joblib

# Cargar modelo
model = joblib.load('models/points_predictor.joblib')

# Verificar
print(f"Features: {model.feature_names_in_}")
print(f"N features: {model.n_features_in_}")
```

## ⚙️ Reentrenamiento

Los modelos deben ser reentrenados cuando:
- ✅ Se agregan nuevas temporadas de datos
- ✅ Se modifican features o preprocesamiento
- ✅ Se actualizan hiperparámetros
- ✅ Se mejora la calidad de datos

Simplemente ejecuta de nuevo:
```bash
python src/run_ml_pipeline.py
```

Los modelos antiguos serán sobrescritos automáticamente.

## 🔒 Seguridad

Los modelos `.joblib` pueden contener código ejecutable. Solo carga modelos de fuentes confiables o que hayas entrenado tú mismo.

## 📚 Referencias

- **Documentación completa**: Ver [ML_SYSTEM.md](../ML_SYSTEM.md)
- **Resumen ejecutivo**: Ver [ML_EXECUTIVE_SUMMARY.md](../ML_EXECUTIVE_SUMMARY.md)
- **Código de entrenamiento**: `src/run_ml_pipeline.py`
- **Modelo XGBoost**: `src/ml/xgboost_model.py`
