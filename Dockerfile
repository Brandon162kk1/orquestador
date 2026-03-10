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

# agregar user1 al grupo docker
RUN usermod -aG root user1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Carpetas necesarias
RUN mkdir -p /app/sync /codigo_mapfre \
    && chown -R user1:user1 /app \
    && chmod 777 /codigo_mapfre

# 🔐 Volver a usuario sin privilegios
USER user1

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/Codigo