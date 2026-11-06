# Ejecutar el proyecto en AWS EC2 

Reemplace `IP` por la IP pública de la instancia y `llave.pem` por su llave.
Las rutas de Windows con espacios van entre comillas.

## 1. Desde su computador: subir el proyecto y los datos
Ejecute desde la carpeta raíz del proyecto (NO suba `.venv`, `.git` ni `mlruns`).

```powershell
ssh -i llave.pem ubuntu@IP "mkdir -p ~/ds_project/data/processed"
scp -i llave.pem -r src tests configs config.yml requirements.txt ubuntu@IP:~/ds_project/
scp -i llave.pem data\processed\siniestros.parquet ubuntu@IP:~/ds_project/data/processed/
```
(Si no tiene carpeta `configs`, quítela del primer comando.)

## 2. En la instancia (pasos 3-9 de la guía, más las librerías del proyecto)
```bash
ssh -i llave.pem ubuntu@IP
sudo apt update
sudo apt install -y python3-pip python3-venv
cd ~/ds_project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mlflow --version          
```

## 3. Terminal 1: servidor MLflow 
```bash
cd ~/ds_project && source .venv/bin/activate
mlflow server -h 0.0.0.0 -p 8050 \
  --backend-store-uri sqlite:///mlflow.db \
  --allowed-hosts "localhost:8050,IP:8050" \
  --cors-allowed-origins "http://IP:8050"
```
Deje esta terminal abierta (o use `nohup ... &` / `tmux`).
Abra el puerto 8050 en el grupo de seguridad (Inbound rule, TCP 8050).
Use como origen "My IP" en lugar de 0.0.0.0/0 para no exponer MLflow a todo internet.
Si detiene y reinicia la instancia, la IP pública cambia: actualice `IP` en el comando.

## 4. Terminal 2: entrenar (paso 15 de la guía)
Nueva conexión SSH a la instancia:
```bash
cd ~/ds_project && source .venv/bin/activate
python -m src.train --data data/processed/siniestros.parquet --all \
  --tracking-uri http://localhost:8050 --experiment fatalidad_aws_v1
```
Use `localhost` (no `127.0.0.1`), porque `--allowed-hosts` solo lista `localhost:8050` y `IP:8050`.
Interfaz web: `http://IP:8050` desde su navegador.

## 5. Variar parámetros 
Edite `config.yml` con nano (`nano config.yml`; CTRL+X, Y, ENTER) y vuelva a ejecutar el paso 4
con otro `--experiment`, o agregue corridas con nombre propio en la sección `experiments:`:
```yaml
  - {model: hgb, features: evento, name: hgb_evento_d2, params: {max_depth: 2}}
  - {model: hgb, features: evento, name: hgb_evento_d8, params: {max_depth: 8}}
```
Para comparar en la interfaz: marque las corridas y pulse **Compare** (gráfica de `val_pr_auc` / `test_pr_auc`).

## 6. Traer resultados a su computador
```powershell
scp -i llave.pem ubuntu@IP:~/ds_project/resultados_experimentos.csv .
```
