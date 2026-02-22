# Dockerfile SIMAGRI_V3
# Permet de lancer l'application directement depuis le dossier SIMAGRI_V3

FROM iridl/simagridssat:latest

ENV PYTHONIOENCODING=utf-8 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    SIMAGRI_ENV=docker \
    SIMAGRI_HOST=0.0.0.0 \
    SIMAGRI_DEBUG=True \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependances systeme minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    zlib1g \
    zlib1g-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN python3 --version && pip3 --version

# Dependances Python
COPY requirements.txt /app/requirements.txt
RUN pip3 install --upgrade pip \
    && pip3 install -r /app/requirements.txt \
    && pip3 install "itsdangerous<2.1" "flask<2.3"

# Code SIMAGRI_V3
COPY *.py /app/
COPY domain/ /app/domain/
COPY ui/ /app/ui/
COPY assets/ /app/assets/
COPY data/ /app/data/
COPY dssat/ /app/dssat/

# Dossiers de travail DSSAT
RUN mkdir -p /app/dssat/exp /app/dssat/snx /app/dssat/outputs \
    && chmod -R 755 /app

EXPOSE 8050

CMD ["python3", "/app/app.py"]
