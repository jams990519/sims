FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_RUTA=/app/datos/simpareja.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY simpareja ./simpareja

# Aquí vive la base de datos: monta un volumen para no perder las partidas.
VOLUME ["/app/datos"]

CMD ["python", "-m", "simpareja"]
