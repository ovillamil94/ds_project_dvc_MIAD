# Resultados de modelado (v1, v2, v3)

Evidencia de los experimentos de Erica Quintero (ramas `modelos-v2-erica`), ejecutados en Google Colab con MLflow (sqlite) y los datos de `data/processed/siniestros.parquet` (DVC).

| Archivo | Contenido |
|---|---|
| `resultados_v1.csv` | v1: líneas base y modelos con niveles llamada, evento y completo (11 corridas) |
| `resultados_v2.csv` | v2: variables derivadas (hora cíclica, festivo, quincena, celda geográfica) e hiperparámetros (10 corridas) |
| `resultados_v3.csv` | v3: se añade `con_carga` (3 corridas) |
| `comparacion_modelos.csv` | Las 24 corridas con IC 95 % de la PR-AUC, tasa de alerta y Brier |

## Cómo reproducirlo (p. ej. en EC2)

```
pip install -r requirements.txt
dvc pull
python -m src.train --data data/processed/siniestros.parquet --all --out resultados_v1.csv
python -m src.train --data data/processed/siniestros.parquet --all --config configs/v2.yml --out resultados_v2.csv
python -m src.train --data data/processed/siniestros.parquet --all --config configs/v3.yml --out resultados_v3.csv
python -m src.register --tracking-uri sqlite:///mlflow.db --experiment fatalidad_siniestros_bogota --llamada-run hgb__evento --escena-run hgb__completo --version-label v1
python -m src.register --tracking-uri sqlite:///mlflow.db --experiment fatalidad_siniestros_bogota_v3 --escena-run hgb__evento_carga --solo escena --version-label v3

pip install mlflow

mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000

```

Ejecutar el registro **una sola vez** (cada ejecución crea versiones nuevas).

## Cifras de control (PR-AUC en validación 2024)

| Corrida | PR-AUC val | PR-AUC test |
|---|---|---|
| hgb__evento (v1) | 0,1160 | 0,1281 |
| hgb__completo (v1, solo comparable en 2024) | 0,2058 | 0,1707 |
| hgb__evento_carga (v3, campeón) | 0,1631 | 0,1688 |

Si en EC2 salen estos valores, el experimento es reproducible.

## Resultado del registro (Model Registry)

- `fatalidad_llamada`: v1 (alias `champion`, `modelo_v1`).
- `fatalidad_escena`: v1 = hgb__completo (`modelo_v1`); v2 = hgb__evento_carga (`modelo_v3`, `champion`).
