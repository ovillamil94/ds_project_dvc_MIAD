# Modelado y experimentos (MLflow)

Objetivo: predecir si un siniestro con víctimas tendrá muertos (`fatal=1`) vs. solo heridos.
Split temporal: entrenamiento ≤2023, validación 2024 (se elige el umbral), prueba 2025.

## Ejecutar
```bash
pip install -r requirements.txt
python -m src.train --data data/processed/<archivo_siniestros>.parquet --all
mlflow ui --backend-store-uri sqlite:///mlflow.db     # http://127.0.0.1:5000
pytest -q tests                                       # prueba con datos sintéticos
```
Un solo experimento: `--model hgb --features evento`. Para registrar modelos: `--register`.

## Qué se compara (11 corridas)
- Líneas base: prevalencia; tabla de letalidad suavizada por franja×localidad.
- Modelos: `logreg`, `hgb`, `hgb_balanced`.
- Conjuntos de variables: `llamada` (hora, día, localidad, coordenadas), `evento` (+ tipo de siniestro), `completo` (+ banderas post-hoc, solo hasta 2024).

Métricas por corrida (val_* y test_*): PR-AUC, ROC-AUC, recall y precisión en el umbral que logra recall ≥ 0,80 en validación, tasa de alertas y recall al priorizar el 10 % / 20 % de siniestros. Se guardan parámetros, hash MD5 del parquet, importancia por permutación y el modelo con firma.

## Nota
Las corridas con datos sintéticos solo verifican el código; no son resultados del proyecto.
Ajustar nombres de columnas en `src/data.py` si el parquet real difiere (`gravedad`, `dia_semana`, `con_*`).
