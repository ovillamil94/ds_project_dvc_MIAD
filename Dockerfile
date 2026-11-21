# =============================================================================
# Dockerfile - API de fatalidad de siniestros (Taller 8)
# Se construye desde la carpeta raiz (donde estan este archivo y fatalidad-api/):
#   sudo docker build -t fatalidad-api:latest .
# Usa la MISMA version de Python con la que entreno el modelo (ver export_model.py):
#   sudo docker build --build-arg PYTHON_VERSION=3.11 -t fatalidad-api:latest .
# =============================================================================

# FROM: imagen base (Linux + Python). Debe coincidir con la version de Python del entrenamiento.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

# ENV: logs sin buffer (se ven en vivo en `docker run -it`) y puerto por defecto
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8001

# RUN: libgomp1 es la libreria OpenMP que usa HistGradientBoosting de scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# COPY (solo requirements primero): si el codigo cambia, esta capa se reutiliza desde la cache
COPY fatalidad-api/requirements.txt /tmp/api-requirements.txt
COPY fatalidad-api/model/requirements.txt /tmp/model-requirements.txt

# RUN: instala EXACTAMENTE las versiones con las que MLflow guardo el modelo (evita errores
# al deserializar). `mlflow-skinny` es la version liviana de mlflow: basta para cargar el modelo.
RUN sed -i 's/^mlflow==/mlflow-skinny==/' /tmp/model-requirements.txt \
    && pip install -r /tmp/model-requirements.txt -r /tmp/api-requirements.txt

# COPY: codigo de la API, el modelo exportado y run.sh
COPY fatalidad-api/ /app/

# RUN: quita finales de linea de Windows (CRLF) y da permiso de ejecucion a run.sh
RUN sed -i 's/\r$//' /app/run.sh && chmod +x /app/run.sh

# EXPOSE: documenta el puerto del contenedor (el mapeo real lo hace `docker run -p`)
EXPOSE 8001

# CMD: comando al lanzar el contenedor; run.sh lee la variable PORT
CMD ["./run.sh"]
