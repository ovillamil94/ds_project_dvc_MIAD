# Imagen base: Linux mínimo con Python
FROM python:3.11-slim

# Logs sin buffer (se ven en vivo en `docker run -it`) y sin .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Primero solo las dependencias: Docker reutiliza esta capa si el código cambia pero ellas no
COPY fatalidad-api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Código de la API y modelo (main.py, run.sh, model/)
COPY fatalidad-api/ /app/

# Quita finales de línea de Windows (CRLF) que romperían run.sh en Linux
RUN sed -i 's/\r$//' /app/run.sh && chmod +x /app/run.sh

# Puerto que escucha la API (el puerto real lo fija -e PORT al ejecutar)
EXPOSE 8001

CMD ["./run.sh"]
