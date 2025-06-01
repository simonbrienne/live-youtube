FROM python:3.11-slim

# Installer FFmpeg et les dépendances système
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

ARG YTB_CLIENT_ID
ARG YTB_CLIENT_SECRET
ARG YTB_REFRESH_TOKEN
ARG YTB_STREAM_KEY
ARG YTB_RTMP_PRIMARY
ARG YTB_RTMP_BACKUP

ENV YTB_CLIENT_ID=$YTB_CLIENT_ID
ENV YTB_CLIENT_SECRET=$YTB_CLIENT_SECRET
ENV YTB_REFRESH_TOKEN=$YTB_REFRESH_TOKEN
ENV YTB_STREAM_KEY=$YTB_STREAM_KEY
ENV YTB_RTMP_PRIMARY=$YTB_RTMP_PRIMARY
ENV YTB_RTMP_BACKUP=$YTB_RTMP_BACKUP
ENV FLASK_ENV=production

# Copier le fichier requirements.txt dans le conteneur
COPY requirements.txt /app/

# Installer les dépendances de l'application
RUN pip install --no-cache-dir -r requirements.txt

# se servir du .env pour définir les variables d'environnement
COPY app.py /app/app.py
COPY static /app/static
COPY templates /app/templates
COPY audio.mp3 /app/audio.mp3

# Exposer le port défini par la variable d'environnement PORT
EXPOSE 5000

# Définir la commande par défaut pour exécuter l'application
CMD ["python", "app.py"]