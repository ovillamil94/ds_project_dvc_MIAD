# Siniestros viales Bogotá 2019-2025 · Proyecto con Git + DVC

Este repositorio versiona el **código** con Git y los **datos** con DVC.

- **Git / GitHub** guarda el código y unos archivos pequeños de texto (`.dvc`) que apuntan a la versión exacta de los datos.
- **DVC** guarda los datos reales (archivos xlsx) en un **remote**: una carpeta compartida de Google Drive.
- Los datos **no están en GitHub**. Después de clonar, hay que traerlos con `dvc pull`.

```
ds_project_dvc_MIAD/
├── .dvc/              # configuración de DVC (sin credenciales ni rutas personales)
├── data/
│   ├── raw/           # xlsx originales (los descarga DVC, no están en Git)
│   ├── raw.dvc        # puntero a la versión de los datos (sí está en Git)
│   └── processed/     # datos limpios generados por código (opcional)
├── src/               # scripts de preparación y análisis
└── README.md
```

## 1. Requisitos previos

| Requisito | Para qué |
|---|---|
| [Git](https://git-scm.com/downloads) | Control de versiones del código |
| Python 3.9 o superior | Ejecutar DVC y los scripts |
| [Google Drive para escritorio](https://www.google.com/drive/download/) | Ver la carpeta compartida como una carpeta local |
| Acceso al repositorio de GitHub | Pedirlo al propietario (Settings → Collaborators) |
| Acceso a la carpeta `dvcstore` en Google Drive | Pedirlo al propietario (compartida como Editor) |
| Token personal de GitHub | Contraseña para `git push` (ver sección 8) |

## 2. Configuración inicial (una sola vez)

### 2.1 Clonar el repositorio

Clónalo en una carpeta **fuera de OneDrive y de Google Drive** (la sincronización puede dañar la carpeta `.git`). Usa una ruta corta, por ejemplo `D:\Projects`.

```powershell
cd D:\Projects
git clone https://github.com/ovillamil94/ds_project_dvc_MIAD.git
cd ds_project_dvc_MIAD
```

### 2.2 Crear el entorno e instalar DVC

```powershell
python -m venv .venv
.venv\Scripts\activate          # en Linux/macOS: source .venv/bin/activate
pip install --upgrade pip
pip install dvc pandas openpyxl
```

Para trabajar con un remote en S3 usa `pip install "dvc[s3]"`. Con la carpeta de Google Drive sincronizada basta con `dvc`.

### 2.3 Acceder a la carpeta compartida de Google Drive

1. El propietario comparte la carpeta `dvcstore` con tu correo (permiso **Editor** si vas a hacer `dvc push`; **Lector** si solo vas a descargar).
2. Abre el enlace que te llegó y elige **Organizar → Agregar acceso directo a Mi unidad**.
3. Abre Google Drive para escritorio y marca la carpeta como disponible sin conexión (clic derecho → **Acceso sin conexión → Disponible sin conexión**), para que los archivos estén realmente en tu PC.
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

## 4. Cambiar el código

Nunca trabajes directamente en `main`. Usa una rama y un pull request.

```powershell
git switch -c nombre-de-tu-rama
# ... edita archivos ...
git add src/mi_script.py
git commit -m "Describe el cambio"
git push -u origin nombre-de-tu-rama
```

Luego abre el **Pull Request** en GitHub (botón *Compare & pull request*) y pide revisión. Si `main` tiene una regla de protección, el PR es la única forma de integrar cambios.

## 5. Cambiar o agregar datos

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

## 6. Volver a una versión anterior de los datos

```powershell
git log --oneline -- data/raw.dvc      # busca el commit deseado
git checkout <commit> -- data/raw.dvc  # restaura el puntero de esa versión
dvc checkout                           # restaura los datos que corresponden
```

Para volver a la versión actual: `git checkout main -- data/raw.dvc` y `dvc checkout`.

## 7. Pipeline de preparación (opcional)

Los xlsx de `data/raw` son los originales: **no se editan nunca**. Toda limpieza va en un script que DVC puede volver a ejecutar:

```powershell
dvc stage add -n prepare -d src/prepare.py -d data/raw -o data/processed python src/prepare.py
dvc repro
git add dvc.yaml dvc.lock .gitignore
git commit -m "Agrega etapa prepare"
dvc push
git push
```

Cuando cambian los datos o el script, `dvc repro` vuelve a ejecutar solo lo necesario.

## 8. Token de GitHub

GitHub no acepta contraseñas para `git push` por HTTPS. Genera un token:

1. GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)**.
2. **Generate new token (classic)**, elige una duración y marca el permiso `repo`.
3. Copia el token y úsalo como contraseña cuando Git la pida (el usuario es tu nombre de usuario de GitHub).

No compartas el token ni lo subas al repositorio.

## 9. Comandos de referencia

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
| Restaurar datos tras cambiar de rama | `git switch <rama>` y luego `dvc checkout` |

## 10. Problemas frecuentes

| Problema | Causa y solución |
|---|---|
| `dvc pull` dice que faltan archivos | El propietario no hizo `dvc push`, o Drive aún sincroniza. Espera o pídele que ejecute `dvc push`. |
| `dvc pull` no encuentra el remote | No configuraste el paso 2.4. Ejecuta `dvc remote add -d gdrive-local --local "<tu ruta>"`. |
| `data/raw` aparece vacía | Falta `dvc pull`. Los datos no vienen con `git clone`. |
| Archivos de 0 KB en la carpeta de Drive | La carpeta no está disponible sin conexión. Actívalo en Google Drive para escritorio. |
| `git push` rechazado (`non-fast-forward`) | Hay cambios remotos que no tienes. Ejecuta `git pull` y vuelve a intentar. No uses `--force`. |
| `git push` rechazado por regla `GH013` | `main` está protegida. Sube tu rama y abre un Pull Request. |
| `Permission denied` o error 403 al hacer push | Usaste la contraseña en lugar del token, o el token no tiene el permiso `repo`, o no eres colaborador. |
| Conflictos de sincronización en `dvcstore` | Dos personas hicieron `dvc push` a la vez. Acordad quién sube y esperad a que Drive termine de sincronizar. |
| Rutas largas fallan en Windows | Usa una ruta corta para el proyecto, por ejemplo `D:\Projects\...`. |

## 11. Buenas prácticas

- No edites los archivos de `data/raw`. Cualquier corrección va en un script.
- No subas credenciales, tokens ni rutas personales. Para eso existe `--local`.
- No guardes el proyecto dentro de OneDrive ni de Google Drive. Solo el remote `dvcstore` vive en Drive.
- Haz siempre `git pull` y `dvc pull` antes de empezar a trabajar.
- Si los datos contienen información personal, confirma que pueden compartirse antes de subirlos al remote.
- El remote en Drive no es una copia de seguridad completa. Si alguien borra `dvcstore`, los punteros de Git no sirven. Mantén una copia adicional de los datos originales.
