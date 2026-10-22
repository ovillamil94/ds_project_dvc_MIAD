# Siniestros viales Bogotá 2019-2025 · Proyecto con Git + DVC

Este repositorio versiona el **código** con Git y los **datos** con DVC.

- **Git / GitHub** guarda el código, los notebooks y unos archivos pequeños de texto (`.dvc`) que apuntan a la versión exacta de los datos.
- **DVC** guarda los datos reales (archivos xlsx) en un **remote**: una carpeta compartida de Google Drive.
- Los datos **no están en GitHub**. Después de clonar, hay que traerlos con `dvc pull`.

## Estructura del proyecto

```
ds_project_dvc_MIAD/
├── .dvc/              # configuración de DVC (sin credenciales ni rutas personales)
├── data/
│   ├── raw/           # xlsx originales (los descarga DVC, no están en Git)
│   ├── raw.dvc        # puntero a la versión de los datos (sí está en Git)
│   └── processed/     # datos limpios generados por código (los versiona DVC)
├── notebooks/         # notebooks (.ipynb) de exploración y reportes
│   └── template_carga_datos.ipynb   # plantilla para cargar los xlsx (punto de partida)
├── src/               # scripts (.py) reutilizables, p. ej. prepare.py
└── README.md
```

| Carpeta | Qué va ahí |
|---|---|
| `notebooks/` | Exploración interactiva y reportes (`.ipynb`), incluida la plantilla de carga de datos |
| `src/` | Código final que se ejecuta solo y que DVC puede usar en un pipeline (`.py`) |

Flujo recomendado: se explora en `notebooks/`, y cuando la lógica de limpieza funciona se pasa a `src/` para que DVC la ejecute con `dvc repro`. Git no guarda carpetas vacías: `notebooks/` y `src/` aparecen en el repositorio cuando contienen su primer archivo.

## 1. Requisitos previos

| Requisito | Para qué |
|---|---|
| [Git](https://git-scm.com/downloads) | Control de versiones del código |
| Python 3.9 o superior | Ejecutar DVC, Jupyter y los scripts |
| [Google Drive para escritorio](https://www.google.com/drive/download/) | Ver la carpeta compartida como una carpeta local |
| Acceso al repositorio de GitHub | Pedirlo al propietario (Settings → Collaborators) |
| Acceso a la carpeta `dvcstore` en Google Drive | Pedirlo al propietario (compartida como Editor) |
| Token personal de GitHub | Contraseña para `git push` (ver sección 10) |

## 2. Configuración inicial (una sola vez)

### 2.1 Clonar el repositorio

Clónalo en una carpeta **fuera de OneDrive y de Google Drive** (la sincronización puede dañar la carpeta `.git`). Usa una ruta corta, por ejemplo `D:\Projects`.

```powershell
cd D:\Projects
git clone https://github.com/ovillamil94/ds_project_dvc_MIAD.git
cd ds_project_dvc_MIAD
```

### 2.2 Crear el entorno e instalar las dependencias

```powershell
python -m venv .venv
.venv\Scripts\activate          # en Linux/macOS: source .venv/bin/activate
pip install --upgrade pip
pip install dvc pandas openpyxl jupyter ipykernel
python -m ipykernel install --user --name ds-project-dvc --display-name "Python (ds-project-dvc)"
```

El último comando registra el entorno como kernel de Jupyter, para que los notebooks usen las librerías instaladas. Si usas un remote en S3, instala `pip install "dvc[s3]"`. Con la carpeta de Google Drive sincronizada basta con `dvc`.

### 2.3 Acceder a la carpeta compartida de Google Drive

1. El propietario comparte la carpeta `dvcstore` con tu correo (permiso **Editor** si vas a hacer `dvc push`; **Lector** si solo vas a descargar).
2. Abre el enlace que te llegó y elige **Organizar → Agregar acceso directo a Mi unidad**.
3. En Google Drive para escritorio, marca la carpeta como disponible sin conexión (clic derecho → **Acceso sin conexión → Disponible sin conexión**), para que los archivos estén realmente en tu PC.
4. Espera a que termine la sincronización y localiza la ruta en el Explorador de archivos, por ejemplo `G:\My Drive\dvcstore`.

### 2.4 Conectar DVC con tu carpeta

Cada persona tiene una ruta distinta, por eso se configura con `--local`: la ruta se guarda en `.dvc/config.local`, que Git ignora.

```powershell
dvc remote add -d gdrive-local --local "G:\My Drive\dvcstore"
```

Cambia la ruta por la tuya y mantén las comillas. Si ya existe un remote con ese nombre y quieres corregir la ruta:

```powershell
dvc remote modify gdrive-local url "G:\My Drive\dvcstore" --local
```

### 2.5 Descargar los datos

```powershell
dvc pull
dir data\raw
```

Deben aparecer los archivos xlsx en `data\raw`.

## 3. Rutina diaria

Antes de empezar a trabajar, actualiza código y datos:

```powershell
git pull
dvc pull
```

## 4. Leer los datos en scripts y notebooks

Los datos se leen **siempre desde `data/raw`** dentro del proyecto, nunca desde la carpeta de Drive ni desde la carpeta original de OneDrive.

```
Drive (dvcstore)  ──dvc pull──►  data/raw  ──script o notebook──►  data/processed
```

- La carpeta `dvcstore` es el almacenamiento interno de DVC: guarda los archivos con nombres de hash (`files/md5/3a/f81c...`), no con sus nombres originales. Solo `dvc push` y `dvc pull` deben tocarla.
- Una ruta relativa como `data/raw` funciona igual en el equipo de todos. Una ruta como `G:\My Drive\...` solo funciona en el tuyo.
- Si cambias de versión de los datos (`git checkout` + `dvc checkout`), tu código lee automáticamente esa versión.

### 4.1 Punto de partida: notebook template

El repositorio incluye la plantilla `notebooks/template_carga_datos.ipynb`. Úsala como punto de partida para cargar los archivos, sobre todo porque **la primera hoja de cada xlsx no siempre comparte el mismo esquema**.

| Sección | Qué hace |
|---|---|
| 0. Configuración | Define las rutas `ROOT`, `RAW` y `PROCESSED` (relativas al proyecto) |
| 1. Archivos y hojas | Lista cada xlsx con un índice y los nombres de sus hojas |
| 2. **Opción A** | Carga **un solo archivo**: eliges archivo (por índice o nombre), hoja y fila del encabezado (`HEADER`) |
| 3. **Opción B** | Carga **todos los archivos** en un diccionario `{archivo: DataFrame}` con `cargar_todos(hoja=0)`, sin unirlos |
| 3. Comparar esquemas | Muestra las columnas comunes y las adicionales de cada archivo |
| 4. Unión opcional | Une los archivos tras renombrar columnas (`RENOMBRAR`) y elegir si se conservan solo las comunes (`SOLO_COMUNES`) |
| 5. Guardar | Escribe el resultado en `data/processed`, nunca en `data/raw` |

**Cómo usarla:**

1. Ejecuta `git pull` y `dvc pull` para tener la plantilla y los datos.
2. **Haz una copia** de la plantilla con tu nombre, por ejemplo `notebooks/exploracion_nombre.ipynb`, y trabaja en la copia. Así no modificas el original ni generas conflictos en Git.
3. Empieza por la opción A para revisar un archivo; usa la opción B cuando quieras comparar todos.

```powershell
copy notebooks\template_carga_datos.ipynb notebooks\exploracion_nombre.ipynb
```

Si guardas el notebook en la raíz del proyecto en lugar de `notebooks/`, cambia `ROOT = Path.cwd().parent` por `ROOT = Path.cwd()`.

### 4.2 Desde un notebook (sin la plantilla)

Abre Jupyter desde la raíz del proyecto y guarda los notebooks en `notebooks/`:

```powershell
cd D:\Projects\ds_project_dvc_MIAD
.venv\Scripts\activate
jupyter notebook
```

Elige el kernel **Python (ds-project-dvc)**. Un notebook resuelve las rutas relativas desde su propia carpeta, así que desde `notebooks/` la raíz del proyecto es la carpeta superior:

```python
from pathlib import Path
import pandas as pd

ROOT = Path.cwd().parent          # raíz del proyecto
RAW = ROOT / "data" / "raw"
print(RAW.exists(), len(list(RAW.glob("*.xlsx"))))   # debe imprimir True y el número de xlsx

frames = []
for f in sorted(RAW.glob("*.xlsx")):
    df = pd.read_excel(f)
    df["source_file"] = f.name
    frames.append(df)

data = pd.concat(frames, ignore_index=True)
data.head()
```

Guarda cada archivo en una lista y concaténalos al final: si asignas `df` dentro del bucle sin guardarlo, solo conservas el último archivo. Revisa también que las columnas coincidan entre años (`data.columns`); si no, renómbralas antes de concatenar.

### 4.3 Desde un script

Ejecuta los scripts desde la raíz del proyecto, para que la ruta relativa funcione:

```python
# src/prepare.py
import pandas as pd
from pathlib import Path

frames = []
for f in sorted(Path("data/raw").glob("*.xlsx")):
    df = pd.read_excel(f)
    df["source_file"] = f.name
    frames.append(df)

data = pd.concat(frames, ignore_index=True)
Path("data/processed").mkdir(parents=True, exist_ok=True)
data.to_csv("data/processed/siniestros.csv", index=False)
```

```powershell
python src/prepare.py
```

## 5. Cambiar el código o los notebooks

Nunca trabajes directamente en `main`. Usa una rama y un pull request.

```powershell
git switch -c nombre-de-tu-rama
# ... edita archivos ...
git add src/prepare.py notebooks/exploracion.ipynb
git commit -m "Describe el cambio"
git push -u origin nombre-de-tu-rama
```

Luego abre el **Pull Request** en GitHub (botón *Compare & pull request*) y pide revisión. Si `main` tiene una regla de protección, el PR es la única forma de integrar cambios.

Los `.ipynb` son archivos JSON grandes y difíciles de revisar en un PR. Antes de hacer commit, conviene limpiar las salidas (Kernel → Restart & Clear Output) y mover la lógica estable a `src/`.

## 6. Cambiar o agregar datos

Esto pasa cuando se actualizan los xlsx, por ejemplo con un año nuevo.

```powershell
# 1. Copia o reemplaza los archivos en data\raw
# 2. Registra la nueva versión en DVC
dvc add data/raw

# 3. Versiona el puntero en Git
git switch -c datos-nueva-version
git add data/raw.dvc data/.gitignore
git commit -m "Agrega datos 2026"

# 4. Sube los datos al remote y el puntero a GitHub
dvc push
git push -u origin datos-nueva-version
```

Después abre el PR. **Haz siempre ambos pushes**: `dvc push` sube los datos y `git push` sube el puntero. Si solo haces uno, tus compañeros no podrán reproducir la versión.

## 7. Volver a una versión anterior de los datos

```powershell
git log --oneline -- data/raw.dvc      # busca el commit deseado
git checkout <commit> -- data/raw.dvc  # restaura el puntero de esa versión
dvc checkout                           # restaura los datos que corresponden
```

Para volver a la versión actual: `git checkout main -- data/raw.dvc` y `dvc checkout`.

## 8. Pipeline de preparación (opcional)

Los xlsx de `data/raw` son los originales: **no se editan nunca**. Toda limpieza va en un script de `src/` que DVC puede volver a ejecutar:

```powershell
dvc stage add -n prepare -d src/prepare.py -d data/raw -o data/processed python src/prepare.py
dvc repro
git add dvc.yaml dvc.lock .gitignore
git commit -m "Agrega etapa prepare"
dvc push
git push
```

Cuando cambian los datos o el script, `dvc repro` vuelve a ejecutar solo lo necesario. DVC ejecuta scripts, no notebooks, por eso la lógica final debe estar en `src/`.

## 9. Acceso a Google Drive desde otros entornos

Si trabajas en Colab o en un servidor, el remote se configura igual, apuntando a la ruta de Drive en ese entorno (en Colab: `drive.mount('/content/drive')` y luego `dvc remote add -d gdrive-local --local "/content/drive/MyDrive/dvcstore"`). Esas sesiones son temporales: repite la configuración y haz `dvc pull` cada vez.

## 10. Token de GitHub

GitHub no acepta contraseñas para `git push` por HTTPS. Genera un token:

1. GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)**.
2. **Generate new token (classic)**, elige una duración y marca el permiso `repo`.
3. Copia el token y úsalo como contraseña cuando Git la pida (el usuario es tu nombre de usuario de GitHub).

No compartas el token ni lo subas al repositorio.

## 11. Comandos de referencia

| Acción | Comando |
|---|---|
| Ver estado del código | `git status` |
| Ver estado de los datos | `dvc status` |
| Ver si el remote está al día | `dvc status -c` |
| Traer cambios de código | `git pull` |
| Traer datos | `dvc pull` |
| Registrar cambios en datos | `dvc add data/raw` |
| Subir datos | `dvc push` |
| Subir código | `git push` |
| Ver remotes de DVC | `dvc remote list` |
| Ejecutar el pipeline | `dvc repro` |
| Restaurar datos tras cambiar de rama | `git switch <rama>` y luego `dvc checkout` |

## 12. Problemas frecuentes

| Problema | Causa y solución |
|---|---|
| `dvc pull` dice que faltan archivos | El propietario no hizo `dvc push`, o Drive aún sincroniza. Espera o pídele que ejecute `dvc push`. |
| `dvc pull` no encuentra el remote | No configuraste el paso 2.4. Ejecuta `dvc remote add -d gdrive-local --local "<tu ruta>"`. |
| `data/raw` aparece vacía | Falta `dvc pull`. Los datos no vienen con `git clone`. |
| Los archivos tienen columnas distintas entre años | Usa la plantilla `template_carga_datos.ipynb`: carga un archivo a la vez (opción A) o compara esquemas (opción B) antes de unirlos. |
| El notebook no encuentra `data/raw` (lista vacía) | Se ejecuta desde otra carpeta. Imprime `Path.cwd()` y ajusta `ROOT`, o abre Jupyter desde la raíz del proyecto. |
| `ModuleNotFoundError` en el notebook | El kernel no es el del entorno del proyecto. Elige **Python (ds-project-dvc)** o instala `ipykernel` (paso 2.2). |
| Error al leer xlsx (`openpyxl`) | Instala el lector con `pip install openpyxl` en el mismo entorno del kernel. |
| Archivos de 0 KB en la carpeta de Drive | La carpeta no está disponible sin conexión. Actívalo en Google Drive para escritorio. |
| `git push` rechazado (`non-fast-forward`) | Hay cambios remotos que no tienes. Ejecuta `git pull` y vuelve a intentar. No uses `--force`. |
| `git push` rechazado por regla `GH013` | `main` está protegida. Sube tu rama y abre un Pull Request. |
| `Permission denied` o error 403 al hacer push | Usaste la contraseña en lugar del token, el token no tiene el permiso `repo`, o no eres colaborador. |
| Conflictos de sincronización en `dvcstore` | Dos personas hicieron `dvc push` a la vez. Acordad quién sube y esperad a que Drive termine de sincronizar. |
| Rutas largas fallan en Windows | Usa una ruta corta para el proyecto, por ejemplo `D:\Projects\...`. |

## 13. Buenas prácticas

- No edites los archivos de `data/raw`. Cualquier corrección va en un script de `src/` o en un notebook, y el resultado se guarda en `data/processed`.
- Lee los datos desde `data/raw` con rutas relativas. No uses rutas absolutas ni leas desde `dvcstore` u OneDrive.
- No subas credenciales, tokens ni rutas personales. Para eso existe `--local`.
- No guardes el proyecto dentro de OneDrive ni de Google Drive. Solo el remote `dvcstore` vive en Drive.
- Haz siempre `git pull` y `dvc pull` antes de empezar a trabajar.
- Si los datos contienen información personal, confirma que pueden compartirse antes de subirlos al remote.
- El remote en Drive no es una copia de seguridad completa. Si alguien borra `dvcstore`, los punteros de Git no sirven. Mantén una copia adicional de los datos originales.
