# Usar tu imagen base personalizada
FROM chromedriver:stable

# Volver a root solo para instalar docker-cli
USER root

RUN apt-get update && apt-get install -y \
    docker.io \
    curl \
    bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 🔹 Crear carpeta sync y asignar permisos correctamente
RUN mkdir -p /app/sync \
    && chown -R user1:user1 /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/Codigo

# Volver a usuario sin privilegios
#USER user1