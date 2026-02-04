# Directorio para modelos ML entrenados

Este directorio almacena los modelos entrenados generados por el pipeline:

- `*_predictor.joblib` - Modelos XGBoost serializados
- `*_metadata.json` - Metadata de los modelos (features, métricas)
- `*_shap_summary.png` - Gráficos de importancia de features (SHAP)

**Nota:** Los archivos de modelos NO se suben al repositorio (ver .gitignore)
ya que son pesados y se regeneran con `python src/run_ml_pipeline.py`
