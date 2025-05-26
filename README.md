# Live Compteur Abonnés YouTube 🚀

Application Flask qui génère automatiquement un live stream YouTube avec un compteur d'abonnés en temps réel.

## 🎯 Fonctionnalités

- **Compteur d'abonnés en temps réel** : Affichage automatique du nombre d'abonnés YouTube
- **Streaming automatique** : Génération de flux vidéo avec FFmpeg vers YouTube Live
- **Interface web** : Contrôles pour démarrer/arrêter le stream
- **Support audio** : Possibilité d'ajouter un fichier MP3 en arrière-plan
- **Test de connectivité** : Vérification RTMP avant le streaming
- **Déploiement Cloud** : Prêt pour Google Cloud Run

## 🛠️ Technologies utilisées

- **Backend** : Flask (Python)
- **Streaming** : FFmpeg
- **API** : YouTube Data API v3
- **Authentification** : OAuth2
- **Conteneurisation** : Docker
- **Déploiement** : Google Cloud Run

## 📋 Prérequis

1. **Compte Google Cloud** avec YouTube Data API activée
2. **Credentials OAuth2** pour YouTube
3. **Docker** (pour le déploiement)
4. **Fichier audio MP3** (optionnel)

## ⚙️ Configuration

### 1. Créer les credentials YouTube

1. Aller sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créer un nouveau projet ou sélectionner un projet existant
3. Activer l'API YouTube Data API v3
4. Créer des credentials OAuth2 (Application de bureau)
5. Télécharger le fichier `client_secrets.json`

### 2. Générer le refresh token

```bash
# Installer les dépendances
pip install google-auth-oauthlib

# Exécuter le script de génération
python generate_refresh_token.py
```

### 3. Configurer les variables d'environnement

Copier `.env.example` vers `.env` et remplir :

```env
# Configuration YouTube API
YTB_CLIENT_ID="votre_client_id"
YTB_CLIENT_SECRET="votre_client_secret"
YTB_REFRESH_TOKEN="votre_refresh_token"

# Configuration Live Stream
YTB_STREAM_KEY="votre_clé_de_flux_youtube"
YTB_RTMP_PRIMARY="rtmp://a.rtmp.youtube.com/live2"
YTB_RTMP_BACKUP="rtmp://b.rtmp.youtube.com/live2?backup=1"

# Configuration Flask
FLASK_ENV=production
PORT=5000
```

### 4. Ajouter un fichier audio (optionnel)

Placer un fichier MP3 dans le dossier avec l'un de ces noms :
- `audio.mp3`
- `background.mp3`
- `music.mp3`
- `stream_audio.mp3`

## 🚀 Démarrage

### Développement local

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python app.py
```

### Avec Docker

```bash
# Construire l'image
docker build -t youtube-live-counter .

# Lancer le conteneur
docker run -p 5000:5000 youtube-live-counter
```

### Déploiement sur Google Cloud Run

```bash
# Construire et pousser l'image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/youtube-live-counter

# Déployer sur Cloud Run
gcloud run deploy youtube-live-counter \
  --image gcr.io/YOUR_PROJECT_ID/youtube-live-counter \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated
```

## 📱 Utilisation

1. **Accéder à l'interface** : Ouvrir `http://localhost:5000`
2. **Créer un live YouTube** : Aller sur YouTube Studio > Live
3. **Récupérer la clé de flux** : Copier dans la configuration YouTube Studio
4. **Tester la connectivité** : Cliquer sur "Tester RTMP"
5. **Démarrer le stream** : Cliquer sur "Démarrer le Live"

## 🎨 Interface

L'interface affiche :
- **Compteur d'abonnés** en temps réel
- **Boutons de contrôle** pour le streaming
- **Statut du stream** (En cours / Arrêté)
- **Statut audio** (Fichier détecté ou silencieux)

## 🔧 API Endpoints

- `GET /` : Interface principale
- `GET /api/subscribers` : Nombre d'abonnés
- `GET /api/start-stream` : Démarrer le stream
- `GET /api/stop-stream` : Arrêter le stream
- `GET /api/stream-status` : Statut du stream
- `GET /api/test-rtmp` : Test de connectivité
- `GET /api/audio-status` : Statut des fichiers audio

## 📁 Structure du projet

```
LIVE_247/
├── app.py                    # Application Flask principale
├── generate_refresh_token.py # Script pour générer le refresh token
├── requirements.txt          # Dépendances Python
├── Dockerfile               # Configuration Docker
├── .env                     # Variables d'environnement
├── .gitignore              # Fichiers à ignorer
├── README.md               # Documentation
├── templates/
│   └── index.html          # Interface web
├── static/
│   └── style.css           # Styles CSS
└── audio.mp3               # Fichier audio (optionnel)
```

## 🐛 Dépannage

### Erreurs courantes

**Erreur API YouTube** :
- Vérifier que l'API YouTube Data v3 est activée
- Vérifier les credentials OAuth2
- Régénérer le refresh token si nécessaire

**Erreur RTMP** :
- Vérifier que la clé de flux est correcte
- Tester avec le bouton "Tester RTMP"
- Vérifier que le live YouTube est créé et en attente

**FFmpeg ne démarre pas** :
- Vérifier que FFmpeg est installé
- Vérifier les logs pour les erreurs spécifiques

### Logs utiles

```bash
# Voir les logs de l'application
docker logs container_name

# Logs en temps réel
docker logs -f container_name
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit les changements (`git commit -am 'Ajouter nouvelle fonctionnalité'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

## 🆘 Support

Pour toute question ou problème :
1. Vérifier la section dépannage ci-dessus
2. Consulter les logs de l'application
3. Créer une issue sur GitHub avec les détails de l'erreur

## 🎉 Remerciements

- YouTube Data API v3
- FFmpeg pour le streaming
- Flask pour le framework web
- Google Cloud Run pour l'hébergement
# live-youtube
