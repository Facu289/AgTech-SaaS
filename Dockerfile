# Receta de la "imagen" de AgroApp: un Linux chiquito con Python, las librerías y el código.
# La misma imagen sirve para los dos servicios de docker-compose.yml (api y bot).
# La base y los backups NO van adentro: viven en la carpeta datos/ del NAS (un "volumen").

FROM python:3.14-slim

# PYTHONUNBUFFERED: los print() salen enseguida en "docker compose logs".
# PYTHONDONTWRITEBYTECODE: no crea carpetas __pycache__ dentro del contenedor.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# tzdata trae las zonas horarias: sin ella, TZ=America/Argentina/Buenos_Aires no tendría efecto
# y las fechas (backups, vencimientos, partos) saldrían en hora UTC.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Primero solo requirements.txt: si el código cambia pero las librerías no,
# Docker reutiliza este paso (ya hecho) y la imagen se arma mucho más rápido.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Después el código (lo que no hay que copiar está en .dockerignore: .env, datos/, .venv/...).
COPY . .

EXPOSE 8000

# Por defecto arranca la API. El bot usa la misma imagen con otro comando (ver docker-compose.yml).
# Sin --reload (eso es solo para programar) y con un solo proceso: SQLite y lo que queda
# pendiente de confirmar por Telegram viven en un único proceso.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
