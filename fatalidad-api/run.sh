#!/bin/sh
# Lanza la API. El puerto viene de la variable de entorno PORT (docker run -e PORT=8001).
set -e
: "${PORT:?Defina la variable de entorno PORT, por ejemplo: -e PORT=8001}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
