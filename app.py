import os
from flask import Flask, render_template, jsonify
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import logging
import subprocess
import threading
import time

# Désactiver les logs de discovery cache
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

app = Flask(__name__)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales pour le streaming
streaming_process = None
should_stop_stream = False

# Cache global pour les données YouTube (OPTIMISATION)
cached_subscribers = None
cache_last_update = 0
cache_update_interval = 10  # Mise à jour toutes les 10 secondes (8 640 crédits/jour)
cache_thread = None
should_stop_cache = False

def get_youtube_client():
    """Créer et retourner un client YouTube authentifié"""
    try:
        # Récupérer les infos depuis les variables d'environnement
        client_id = os.environ.get("YTB_CLIENT_ID")
        client_secret = os.environ.get("YTB_CLIENT_SECRET")
        refresh_token = os.environ.get("YTB_REFRESH_TOKEN")
        
        if not all([client_id, client_secret, refresh_token]):
            raise ValueError("Variables d'environnement manquantes")

        # Créer les credentials OAuth2 sans interaction
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]
        )

        # Construire le client YouTube avec cache désactivé
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        return youtube
    
    except Exception as e:
        logger.error(f"Erreur lors de la création du client YouTube: {e}")
        return None

def get_channel_subscribers():
    """Récupérer le nombre d'abonnés de la chaîne"""
    try:
        youtube = get_youtube_client()
        if not youtube:
            return None
            
        request = youtube.channels().list(
            part="statistics",
            mine=True
        )
        response = request.execute()
        
        if response['items']:
            subscribers = int(response['items'][0]['statistics']['subscriberCount'])
            return subscribers
        return None
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des abonnés: {e}")
        return None

def update_subscriber_cache():
    """Thread dédié pour mettre à jour le cache des abonnés (OPTIMISATION)"""
    global cached_subscribers, cache_last_update, should_stop_cache
    
    logger.info("Thread de cache des abonnés démarré")
    
    while not should_stop_cache:
        try:
            subscribers = get_channel_subscribers()
            if subscribers is not None:
                cached_subscribers = subscribers
                cache_last_update = time.time()
                logger.info(f"Cache mis à jour: {subscribers} abonnés")
            else:
                logger.warning("Échec de la mise à jour du cache des abonnés")
                
            # Attendre avant la prochaine mise à jour
            for _ in range(cache_update_interval):
                if should_stop_cache:
                    break
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Erreur dans le thread de cache: {e}")
            if not should_stop_cache:
                time.sleep(10)
    
    logger.info("Thread de cache des abonnés arrêté")

def get_cached_subscribers():
    """Récupérer les abonnés depuis le cache (OPTIMISATION)"""
    global cached_subscribers, cache_last_update
    
    # Si pas de cache ou cache trop ancien (plus de 30 secondes)
    if cached_subscribers is None or (time.time() - cache_last_update) > 30:
        # Faire un appel direct seulement si vraiment nécessaire
        subscribers = get_channel_subscribers()
        if subscribers is not None:
            cached_subscribers = subscribers
            cache_last_update = time.time()
        return cached_subscribers
    
    return cached_subscribers

def start_cache_thread():
    """Démarrer le thread de cache s'il n'est pas déjà actif"""
    global cache_thread, should_stop_cache
    
    if cache_thread is None or not cache_thread.is_alive():
        should_stop_cache = False
        cache_thread = threading.Thread(target=update_subscriber_cache)
        cache_thread.daemon = True
        cache_thread.start()
        logger.info("Thread de cache démarré")

def stop_cache_thread():
    """Arrêter le thread de cache"""
    global should_stop_cache
    should_stop_cache = True
    logger.info("Signal d'arrêt envoyé au thread de cache")

def generate_video_with_counter():
    """Générer un flux vidéo avec le compteur d'abonnés"""
    global streaming_process
    
    # Récupérer les infos de streaming depuis les variables d'environnement
    stream_key = os.environ.get("YTB_STREAM_KEY")
    rtmp_url = os.environ.get("YTB_RTMP_PRIMARY", "rtmp://a.rtmp.youtube.com/live2/")
    
    if not stream_key or stream_key == "your_stream_key_here":
        logger.error("YTB_STREAM_KEY manquante ou non configurée dans les variables d'environnement")
        return False
        
    # Vérifier si un fichier audio existe
    audio_file = None
    possible_audio_files = ["audio.mp3", "background.mp3", "music.mp3", "stream_audio.mp3"]
    
    for filename in possible_audio_files:
        if os.path.exists(filename):
            audio_file = filename
            logger.info(f"Fichier audio trouvé: {filename}")
            break
    
    try:
        # Récupérer le nombre d'abonnés depuis le cache (OPTIMISATION)
        subscribers = get_cached_subscribers()
        if not subscribers:
            subscribers = "Erreur"
            
        logger.info(f"Démarrage du streaming vers {rtmp_url} avec {subscribers} abonnés")
        logger.info(f"Stream key length: {len(stream_key)}")
        
        # Construire la commande FFmpeg selon la disponibilité de l'audio
        if audio_file:
            logger.info(f"Utilisation du fichier audio: {audio_file}")
            ffmpeg_cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", "color=c=#1a1a1a:s=1920x1080:r=30",  # Source vidéo
                "-stream_loop", "-1",  # Boucler l'audio
                "-i", audio_file,  # Fichier audio MP3
                "-vf", f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Abonnés YouTube':fontcolor=white:fontsize=80:x=(w-text_w)/2:y=300,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{subscribers}':fontcolor=#FF0000:fontsize=180:x=(w-text_w)/2:y=500",
                "-c:v", "libx264",
                "-preset", "fast",
                "-tune", "zerolatency",
                "-b:v", "2000k",
                "-maxrate", "2500k",
                "-bufsize", "3000k",
                "-pix_fmt", "yuv420p",
                "-g", "60",
                "-keyint_min", "60",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "44100",
                "-shortest",  # Arrêter quand la vidéo se termine
                "-f", "flv",
                f"{rtmp_url}/{stream_key}"
            ]
        else:
            logger.info("Aucun fichier audio trouvé, utilisation d'audio silencieux")
            ffmpeg_cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", "color=c=#1a1a1a:s=1920x1080:r=30",
                "-f", "lavfi", 
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-vf", f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Abonnés YouTube':fontcolor=white:fontsize=80:x=(w-text_w)/2:y=300,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{subscribers}':fontcolor=#FF0000:fontsize=180:x=(w-text_w)/2:y=500",
                "-c:v", "libx264",
                "-preset", "fast",
                "-tune", "zerolatency",
                "-b:v", "2000k",
                "-maxrate", "2500k",
                "-bufsize", "3000k",
                "-pix_fmt", "yuv420p",
                "-g", "60",
                "-keyint_min", "60",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "44100",
                "-f", "flv",
                f"{rtmp_url}/{stream_key}"
            ]
        
        logger.info("Démarrage du stream principal...")
        
        streaming_process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1
        )
        
        # Vérifier si le processus a démarré correctement
        time.sleep(3)
        if streaming_process.poll() is not None:
            stdout, stderr = streaming_process.communicate()
            logger.error(f"FFmpeg s'est arrêté. Code: {streaming_process.returncode}")
            logger.error(f"STDERR: {stderr.decode()}")
            return False
        
        logger.info("Streaming démarré avec succès!")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du streaming: {e}")
        return False

def update_stream_overlay():
    """Mettre à jour l'overlay du stream avec le nombre d'abonnés (OPTIMISÉ)"""
    global streaming_process, should_stop_stream
    
    while streaming_process and streaming_process.poll() is None and not should_stop_stream:
        try:
            # Utiliser le cache au lieu d'un appel API direct (OPTIMISATION)
            subscribers = get_cached_subscribers()
            if subscribers and not should_stop_stream:
                logger.info(f"Abonnés actuels (depuis cache): {subscribers}")
                
                # Redémarrer FFmpeg avec le nouveau nombre d'abonnés
                if streaming_process and not should_stop_stream:
                    streaming_process.terminate()
                    streaming_process.wait()
                    
                    # Vérifier à nouveau si on doit arrêter avant de redémarrer
                    if not should_stop_stream:
                        generate_video_with_counter()
                
            time.sleep(10)  # Mise à jour toutes les 10 secondes pour synchroniser avec le cache
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'overlay: {e}")
            if not should_stop_stream:
                time.sleep(10)
            else:
                break
    
    logger.info("Thread de mise à jour arrêté")

@app.route("/")
def index():
    """Page principale"""
    return render_template("index.html")

@app.route("/api/subscribers")
def api_subscribers():
    """API endpoint pour récupérer le nombre d'abonnés (OPTIMISÉ)"""
    # Utiliser le cache au lieu d'un appel API direct (OPTIMISATION)
    subscribers = get_cached_subscribers()
    if subscribers is not None:
        return jsonify({
            "subscribers": subscribers,
            "cached": True,
            "last_update": cache_last_update
        })
    else:
        return jsonify({"error": "Impossible de récupérer les abonnés"}), 500

@app.route("/api/start-stream")
def start_stream():
    """Démarrer le live stream"""
    global streaming_process, should_stop_stream
    
    if streaming_process and streaming_process.poll() is None:
        return jsonify({"error": "Stream déjà en cours"}), 400
    
    # Vérifier que les variables d'environnement sont présentes
    stream_key = os.environ.get("YTB_STREAM_KEY")
    if not stream_key:
        return jsonify({"error": "YTB_STREAM_KEY manquante dans la configuration"}), 500
    
    # Réinitialiser le flag d'arrêt
    should_stop_stream = False
    
    # Démarrer le thread de cache si pas déjà actif (OPTIMISATION)
    start_cache_thread()
        
    # Démarrer le streaming FFmpeg
    if generate_video_with_counter():
        # Démarrer la mise à jour de l'overlay en arrière-plan
        overlay_thread = threading.Thread(target=update_stream_overlay)
        overlay_thread.daemon = True
        overlay_thread.start()
        
        return jsonify({
            "message": "Stream démarré avec succès",
            "rtmp_url": os.environ.get("YTB_RTMP_PRIMARY"),
            "stream_key": stream_key[:10] + "..."  # Masquer une partie de la clé
        })
    else:
        return jsonify({"error": "Impossible de démarrer le streaming"}), 500

@app.route("/api/stop-stream")
def stop_stream():
    """Arrêter le live stream"""
    global streaming_process, should_stop_stream
    
    try:
        # Signal pour arrêter le thread de mise à jour
        should_stop_stream = True
        logger.info("Signal d'arrêt envoyé au thread de mise à jour")
        
        if streaming_process:
            logger.info("Arrêt du streaming en cours...")
            
            # Essayer d'abord un arrêt propre
            streaming_process.terminate()
            
            # Attendre un peu pour que le processus se termine proprement
            try:
                streaming_process.wait(timeout=5)
                logger.info("Processus FFmpeg arrêté proprement")
            except subprocess.TimeoutExpired:
                # Si le processus ne s'arrête pas, forcer l'arrêt
                logger.warning("Processus FFmpeg ne répond pas, arrêt forcé")
                streaming_process.kill()
                streaming_process.wait()
                logger.info("Processus FFmpeg forcé à s'arrêter")
            
            streaming_process = None
            return jsonify({"message": "Stream arrêté avec succès"})
        else:
            return jsonify({"message": "Aucun stream en cours"})
        
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du stream: {e}")
        # S'assurer que les variables globales sont réinitialisées même en cas d'erreur
        streaming_process = None
        should_stop_stream = True
        return jsonify({"error": f"Erreur lors de l'arrêt du stream: {str(e)}"}), 500

@app.route("/api/stream-status")
def stream_status():
    """Vérifier le statut du stream"""
    global streaming_process
    
    is_running = streaming_process and streaming_process.poll() is None
    
    return jsonify({
        "is_running": is_running,
        "rtmp_url": os.environ.get("YTB_RTMP_PRIMARY"),
        "has_stream_key": bool(os.environ.get("YTB_STREAM_KEY"))
    })

@app.route("/api/stream-config")
def stream_config():
    """Récupérer la configuration de streaming"""
    return jsonify({
        "rtmp_primary": os.environ.get("YTB_RTMP_PRIMARY"),
        "rtmp_backup": os.environ.get("YTB_RTMP_BACKUP"),
        "has_stream_key": bool(os.environ.get("YTB_STREAM_KEY"))
    })

@app.route("/api/test-rtmp")
def test_rtmp():
    """Tester la connectivité RTMP"""
    stream_key = os.environ.get("YTB_STREAM_KEY")
    rtmp_url = os.environ.get("YTB_RTMP_PRIMARY", "rtmp://a.rtmp.youtube.com/live2/")
    
    if not stream_key:
        return jsonify({"error": "YTB_STREAM_KEY manquante"}), 500
    
    try:
        logger.info(f"Test RTMP vers {rtmp_url} avec la clé {stream_key}")
        
        # Utiliser FFmpeg pour tester la connexion RTMP
        ffmpeg_cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", "10",  # Durée de 10 secondes pour le test
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-f", "flv",
            f"{rtmp_url}/{stream_key}"
        ]
        
        # Lancer FFmpeg en mode subprocess
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Attendre la fin du processus
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            logger.info("Test RTMP réussi")
            return jsonify({"message": "Test RTMP réussi"})
        else:
            logger.error(f"Test RTMP échoué. Code: {process.returncode}")
            logger.error(f"STDERR: {stderr.decode()}")
            return jsonify({"error": "Test RTMP échoué"}), 500
    
    except Exception as e:
        logger.error(f"Erreur lors du test RTMP: {e}")
        return jsonify({"error": f"Erreur lors du test RTMP: {str(e)}"}), 500

if __name__ == "__main__":
    # Démarrer le thread de cache au démarrage de l'application (OPTIMISATION)
    start_cache_thread()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

