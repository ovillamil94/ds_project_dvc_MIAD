#!/bin/sh
# El puerto llega por la variable de entorno PORT (docker run -e PORT=8001 ...)
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:?Defina PORT con -e PORT=8001}"
