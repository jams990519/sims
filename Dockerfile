FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_RUTA=/app/datos/simpareja.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY simpareja ./simpareja

# La base de datos vive en /app/datos: monta ahí un volumen para no perder las partidas
# (docker run -v ... o un Volume de Railway con ese mount path).
CMD ["python", "-m", "simpareja"]
