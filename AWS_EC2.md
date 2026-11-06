# Fatalidad de siniestros viales en Bogotá: experimentos con MLflow

Predice si un siniestro con víctimas tendrá muertos (`fatal = 1`) o solo heridos, comparando
dos líneas base y tres modelos (`logreg`, `hgb`, `hgb_balanced`) sobre tres conjuntos de variables
(`llamada`, `evento`, `completo`). Cada ejecución queda registrada en MLflow (parámetros, métricas,
importancia por permutación y modelo).

Todos los parámetros están en `config.yml`; no hay valores fijos en el código.

**Vocabulario de MLflow**

| Término | Qué es | Dónde se define |
|---|---|---|
| Experimento | Un grupo de corridas | `experiment.name` en `config.yml` (o `--experiment`) |
| Corrida (run) | Un entrenamiento individual (ej. `hgb__evento`) | Lista `experiments:` en `config.yml` |

---

## 1. Inventario de archivos

```
ds_project_dvc_MIAD/
├── README.md                    # este documento
├── config.yml                   # TODOS los parámetros (con comentarios)
├── configs/                     # opcional: variantes de config.yml (ej. depth2.yml)
├── requirements.txt             # dependencias de Python
├── .gitignore                   # archivos que no se suben a Git
├── .dvc/                        # configuración de DVC
├── src/
│   ├── __init__.py              # vacío; necesario para `python -m src.train`
│   ├── config.py                # carga y valida config.yml
│   ├── data.py                  # carga del parquet, universo, variable objetivo, split temporal, conjuntos de variables
│   └── train.py                 # entrena los modelos y registra todo en MLflow
├── tests/
│   ├── __init__.py              # vacío; necesario para las importaciones
│   ├── make_synthetic_data.py   # genera un parquet SINTÉTICO para probar el código
│   └── test_pipeline.py         # pruebas con pytest
└── data/                        # administrado por DVC, NO está en Git
    ├── raw/                     # archivos originales
    └── processed/
        └── siniestros.parquet   # único archivo que lee train.py
```

| Archivo | Descripción |
|---|---|
| `config.yml` | Años del split, listas de variables, conjuntos de variables, hiperparámetros, lista de corridas, nombre del experimento y servidor MLflow. |
| `src/config.py` | Lee el yml y valida (años en orden, nombres de corrida únicos, modelos y conjuntos existentes). |
| `src/data.py` | Prepara los datos: filtra siniestros con víctimas, crea `fatal`, deriva variables (franja, fin de semana, madrugada), elimina duplicados y separa train/val/test por año. |
| `src/train.py` | Construye los pipelines, elige el umbral en validación para el recall objetivo, calcula métricas y las registra en MLflow. |
| `tests/test_pipeline.py` | Verifica el universo, el split temporal, el registro en MLflow y los nombres/parámetros por corrida. |
| `tests/make_synthetic_data.py` | Datos falsos con el esquema real; solo para probar el código. |
| `requirements.txt` | mlflow, scikit-learn, pandas, numpy, pyarrow, matplotlib, cloudpickle, pyyaml, pytest. |

**Qué va en cada sistema**

| Sistema | Contenido |
|---|---|
| Git | `src/`, `tests/`, `config.yml`, `configs/`, `requirements.txt`, `README.md`, archivos `.dvc` |
| DVC | `data/` (el parquet no está en Git: hay que subirlo a la instancia, ver 4.5) |
| Ninguno (ignorar) | `.venv/`, `mlflow.db`, `mlruns/`, `mlartifacts/`, `__pycache__/`, `.pytest_cache/`, `resultados_experimentos.csv`, `*.log`, `*.pem` |

`.gitignore` sugerido:

```
.venv/
__pycache__/
.pytest_cache/
mlflow.db
mlruns/
mlartifacts/
resultados_experimentos.csv
*.log
*.pem
```

---

## 2. Parámetros (`config.yml`)

| Sección | Qué controla |
|---|---|
| `experiment` | Nombre del experimento, servidor MLflow (`tracking_uri`), semilla, recall objetivo, fuente de gravedad, CSV de salida |
| `split` | Años de entrenamiento (`train_max`), validación (`val_year`) y prueba (`test_year`) |
| `features` | Grupos de variables (`cat_*` son categóricos; los demás, numéricos) |
| `feature_sets` | Qué grupos usa cada conjunto: `llamada`, `evento`, `completo` |
| `preprocessing` | `min_frequency`: categorías raras se agrupan en una sola |
| `baselines` | `rate_table_k`: suavizado de la tabla de letalidad |
| `models` | Hiperparámetros por defecto de `logreg`, `hgb`, `hgb_balanced` |
| `experiments` | Las corridas: `model`, `features`, y opcionalmente `name` y `params` |

Ejemplo de corrida con nombre e hiperparámetros propios:

```yaml
experiments:
  - {model: hgb, features: evento, name: hgb_evento_d2, params: {max_depth: 2}}
```

**Prioridad:** lo que se escribe en la línea de comandos (`--experiment`, `--tracking-uri`, `--gravedad-source`, `--out`)
anula lo que dice el yml.

---

## 3. Ejecución local (Windows, PowerShell)

Todos los comandos se ejecutan desde la carpeta raíz del proyecto.

```powershell
python -m venv .venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser   # solo si PowerShell bloquea Activate.ps1
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

pytest -q tests                                                        # prueba con datos sintéticos
python -m src.train --data data/processed/siniestros.parquet --all     # las 11 corridas
mlflow ui --backend-store-uri sqlite:///mlflow.db                      # http://127.0.0.1:5000
```

Una sola corrida: `python -m src.train --data data/processed/siniestros.parquet --model hgb --features evento`

---

## 4. Ejecución en AWS EC2

Funciona con cualquier instancia nueva siguiendo estos pasos en orden.

### 4.0 Qué se ejecuta dónde

| Dónde | Qué | Prompt que verá |
|---|---|---|
| **Su computador** (PowerShell de Windows) | `ssh` para conectarse y `scp` para subir y bajar archivos | `PS C:\...>` |
| **La instancia** (sesión SSH) | Instalar, iniciar el servidor, entrenar | `ubuntu@ip-172-31-...:~$` |

Error frecuente: `scp` solo funciona desde su computador. Dentro de la sesión SSH no existen sus carpetas `C:\` ni `D:\`.

Se necesitan **dos sesiones SSH** a la instancia: una para el servidor MLflow y otra para entrenar
(o una sola, si el servidor se inicia con `nohup`, como se muestra abajo).

### 4.1 Requisitos previos

- El código con `config.yml` ya subido a GitHub (`git push`).
- El archivo `siniestros.parquet` en su computador (no está en Git).
- La llave `.pem` de la instancia.

### 4.2 Lanzar la instancia

En la consola de AWS EC2, **Launch instance**:

| Campo | Valor |
|---|---|
| Sistema operativo | Ubuntu Server 24.04 |
| Tipo | `t2.medium` (2 vCPU, 4 GB RAM) |
| Disco | 20 GB |
| Key pair | Cree o elija uno y descargue el `.pem` |
| Security group | Ver 4.3 |

### 4.3 Configuración de red (Security group)

Reglas de entrada (**Inbound rules**) necesarias:

| Tipo | Protocolo | Puerto | Origen recomendado | Para qué |
|---|---|---|---|---|
| SSH | TCP | 22 | My IP | Conectarse por `ssh` y subir archivos con `scp` |
| Custom TCP | TCP | 8050 | My IP | Abrir la interfaz web de MLflow desde el navegador |

Para editarlas: EC2, Instances, seleccione la instancia, pestaña **Security**, clic en el security group,
**Edit inbound rules**.

Notas de seguridad y red:

- Con origen `0.0.0.0/0` cualquiera en internet puede abrir su MLflow, que no tiene contraseña. Úselo solo si su red cambia con frecuencia y retírelo al terminar.
- Con "My IP", si cambia de red (otra WiFi, VPN, datos móviles), edite la regla.
- La **IP pública cambia** cada vez que detiene y vuelve a iniciar la instancia (salvo con Elastic IP). Tome siempre la actual de la columna *Public IPv4 address* de la consola.
- Use la IP **pública** (no la privada 172.x), en `http://` (no `https://`).

### 4.4 Conectarse (desde su computador)

Defina las variables una vez por ventana de PowerShell:

```powershell
$KEY = "C:\ruta\a\mi_llave.pem"      # ruta completa a su llave
$IP  = "54.91.93.27"                 # IP pública actual de la instancia
```

Si no recuerda dónde está la llave:

```powershell
Get-ChildItem "D:\Documents" -Recurse -Filter *.pem -ErrorAction SilentlyContinue | Select-Object FullName
```

Conéctese:

```powershell
ssh -i "$KEY" ubuntu@$IP
```

La primera vez pregunta si confía en el servidor: responda `yes`.

Si aparece `UNPROTECTED PRIVATE KEY FILE`:

```powershell
icacls "$KEY" /inheritance:r
icacls "$KEY" /grant:r "$($env:USERNAME):(R)"
```

### 4.5 Preparar el entorno (en la instancia)

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git

git clone https://github.com/<su_usuario>/ds_project_dvc_MIAD.git ds_project
cd ds_project

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mlflow --version          

mkdir -p data/processed
```

Si el repositorio es privado, GitHub pide su usuario y un *personal access token* (no la contraseña).
Si trabaja en otra rama, agregue `-b <rama>` al `git clone`.

Verifique que la instancia tiene el código nuevo:

```bash
ls config.yml src/config.py
grep -c "load_config" src/train.py     # debe imprimir un número mayor que 0
```

Si falla, falta hacer `git push` desde su computador y luego `git pull` en la instancia.

### 4.6 Subir los datos (desde su computador)

`git clone` **no trae** el parquet (lo administra DVC) y `dvc pull` no funciona desde EC2 si su
remoto es una carpeta de Google Drive de su PC. Súbalo con `scp` desde PowerShell, en la
carpeta raíz del proyecto:

```powershell
cd "D:\Documents\Courses\Data Analytics\Python\8. Python DataCamp\18.Web Scraping\Repository\ds_project_dvc_MIAD"
scp -i "$KEY" data\processed\siniestros.parquet ubuntu@${IP}:~/ds_project/data/processed/
```

Escriba `${IP}` con llaves: PowerShell interpreta `$IP:` como el nombre de una variable con ámbito.

Verifique en la instancia:

```bash
ls -lh ~/ds_project/data/processed/siniestros.parquet
```

Opcional, para confirmar que es el mismo archivo (el entrenamiento guarda su MD5 en la etiqueta `data_md5`):

```powershell
Get-FileHash data\processed\siniestros.parquet -Algorithm MD5     # en su computador
```
```bash
md5sum ~/ds_project/data/processed/siniestros.parquet             # en la instancia
```

### 4.7 Iniciar el servidor MLflow (en la instancia)

```bash
cd ~/ds_project && source .venv/bin/activate
IP=$(curl -s checkip.amazonaws.com)
echo "$IP"                      # debe coincidir con la IP pública de la consola; si no, escríbala a mano en $IP

nohup mlflow server -h 0.0.0.0 -p 8050 \
  --backend-store-uri sqlite:///mlflow.db \
  --allowed-hosts "localhost:8050,$IP:8050" \
  --cors-allowed-origins "http://$IP:8050" > server.log 2>&1 &

sleep 30
tail -5 server.log
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: $IP:8050" http://localhost:8050/health
```

Debe ver `Uvicorn running on http://0.0.0.0:8050` en el log y `200` en el `curl`. El primer arranque
tarda porque crea la base de datos.

Cada vez que reinicie la instancia hay que repetir este paso, porque el servidor no arranca solo y la IP cambió.
No escriba `<public IPv4>` literalmente: es un marcador que debe reemplazar.

### 4.8 Entrenar (en la instancia)

```bash
cd ~/ds_project && source .venv/bin/activate
nohup python -u -m src.train --data data/processed/siniestros.parquet --all \
  --tracking-uri http://localhost:8050 > train.log 2>&1 &
tail -f train.log
```

- El experimento toma el nombre de `experiment.name` en `config.yml`. Solo agregue `--experiment <nombre>` si quiere anularlo.
- Use `localhost` en `--tracking-uri`: `--allowed-hosts` del paso 4.7 lo permite.
- `train.log` muestra el avance (`[3/11] logreg__llamada`) y, al final, la tabla resumen. Ctrl+C solo deja de mostrar el log; el trabajo continúa.
- Las 11 corridas tardan unos minutos.

### 4.9 Ver los resultados (en su navegador)

```
http://<IP pública>:8050
```

Los enlaces que imprime MLflow dicen `localhost:8050`: no abren desde su computador; cambie `localhost` por la IP pública.
Para comparar: abra el experimento, marque las corridas y pulse **Compare**. Las métricas principales son
`val_pr_auc` y `test_pr_auc`; las demás están descritas en la sección 5.

### 4.10 Cambiar parámetros y repetir

Opción A, editar en la instancia:

```bash
cd ~/ds_project
nano config.yml           # CTRL+X, Y, ENTER para guardar
```

Opción B, editar en su computador, `git push` y en la instancia `git pull` (elija una sola para evitar conflictos).

Para que las corridas nuevas no se mezclen con las anteriores, cambie `experiment.name` o use `--experiment <nombre_nuevo>`.
Si deja el mismo nombre, MLflow agrega las corridas al experimento existente.

### 4.11 Traer los resultados a su computador

```powershell
scp -i "$KEY" ubuntu@${IP}:~/ds_project/resultados_experimentos.csv .
scp -i "$KEY" ubuntu@${IP}:~/ds_project/mlflow.db .
```

### 4.12 Detener, reanudar y terminar

| Acción | Efecto |
|---|---|
| **Stop** | Conserva disco, datos y `mlflow.db`; la IP pública cambia; el servidor no arranca solo (repita 4.7 con la IP nueva). |
| **Terminate** | Borra todo. Antes, baje `mlflow.db` y el CSV (4.11). |

Detenga la instancia cuando termine para evitar cargos y exposición.

### 4.13 Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `Connection refused` en `localhost:8050` | El servidor MLflow no está corriendo | Ejecute 4.7 y espere el `200` antes de entrenar |
| `FileNotFoundError: data/processed/siniestros.parquet` | El parquet no está en la instancia | Súbalo con `scp` (4.6) |
| `Permission denied (publickey)` | Llave equivocada o `scp` ejecutado desde dentro de la instancia | Ejecute `scp`/`ssh` en PowerShell de Windows con la ruta correcta de la `.pem` |
| `Identity file ... not accessible` | Ruta de la llave incorrecta | Búsquela con el comando de 4.4 |
| `No such file or directory` al subir | Falta la carpeta de destino | `mkdir -p ~/ds_project/data/processed` en la instancia |
| La interfaz no abre en el navegador | Puerto 8050 cerrado, IP cambiada o `https` | Revise 4.3, use la IP actual y `http://` |
| Página con "Invalid Host header" o error 403 | `--allowed-hosts` no incluye la IP usada | Reinicie el servidor con la IP real (4.7) |
| El traceback muestra `train.py` con `main()` de 174 líneas | La instancia tiene el código viejo | `git push` desde su computador y `git pull` en la instancia |
| `ConvergenceWarning` en `logreg` | No convergió | Suba `models.logreg.max_iter` en `config.yml` |
| `ValueError: Split vacío` | Años del split sin datos o `gravedad_source: tradicional` | Revise `split` y use `30d` |

---

## 5. Cómo leer las métricas

| Métrica | Uso |
|---|---|
| `val_pr_auc`, `test_pr_auc` | Principal; el azar rinde aproximadamente la `prevalence`. Importa la mejora sobre ese valor |
| `*_roc_auc` | Complementaria; se ve optimista con clases desbalanceadas |
| `*_recall`, `*_precision` | En el umbral elegido en validación para alcanzar `recall_target`; se aplica igual a prueba |
| `*_alert_rate` | Proporción de siniestros que se marcan; es el costo operativo |
| `*_recall_top10`, `*_recall_top20` | Fracción de fatales capturada si solo se prioriza el 10 % o el 20 % con mayor puntaje |
| `cobertura_posthoc_*` | Solo en conjuntos con banderas post-hoc. Si `test` es menor que 1, faltan banderas en el año de prueba y ese resultado no es comparable |

Orden sugerido: superar las líneas base, comparar conjuntos de variables, revisar la brecha entre validación y prueba,
comparar el costo (`alert_rate`) a recall similar y abrir la importancia por permutación de la mejor corrida.
Elija parámetros con las métricas `val_*` y use `test_*` solo para confirmar.

---

## 6. Pruebas

```bash
pytest -q tests
```

Usan datos sintéticos; verifican el código, no son resultados del proyecto.