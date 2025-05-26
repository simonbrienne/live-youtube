import os
from flask import Flask, render_template, jsonify
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import logging
from dotenv import load_dotenv
import subprocess
import threading
import time

# Désactiver les logs de discovery cache
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

app = Flask(__name__)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales pour le streaming
streaming_process = None
should_stop_stream = False

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
        # Récupérer le nombre d'abonnés initial
        subscribers = get_channel_subscribers()
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
    """Mettre à jour l'overlay du stream avec le nombre d'abonnés"""
    global streaming_process, should_stop_stream
    
    while streaming_process and streaming_process.poll() is None and not should_stop_stream:
        try:
            subscribers = get_channel_subscribers()
            if subscribers and not should_stop_stream:
                logger.info(f"Abonnés actuels: {subscribers}")
                
                # Redémarrer FFmpeg avec le nouveau nombre d'abonnés
                if streaming_process and not should_stop_stream:
                    streaming_process.terminate()
                    streaming_process.wait()
                    
                    # Vérifier à nouveau si on doit arrêter avant de redémarrer
                    if not should_stop_stream:
                        generate_video_with_counter()
                
            time.sleep(30)  # Mise à jour toutes les 30 secondes
            
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
    """API endpoint pour récupérer le nombre d'abonnés"""
    subscribers = get_channel_subscribers()
    if subscribers is not None:
        return jsonify({"subscribers": subscribers})
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
        logger.info(f"Test RTMP vers {rtmp_url}/{stream_key[:8]}...")
        
        # Test simple de 5 secondes avec des paramètres minimaux
        test_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", 
            "-i", "testsrc=duration=5:size=320x240:rate=10",
            "-f", "lavfi", 
            "-i", "sine=frequency=440:duration=5",
            "-c:v", "libx264", 
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", "300k", 
            "-pix_fmt", "yuv420p",
            "-g", "10",
            "-c:a", "aac", 
            "-b:a", "64k",
            "-ac", "2",
            "-ar", "44100",
            "-t", "5", 
            "-f", "flv",
            f"{rtmp_url}/{stream_key}"
        ]
        
        logger.info("Exécution du test RTMP...")
        result = subprocess.run(
            test_cmd,
            capture_output=True,
            text=True,
            timeout=20
        )
        
        logger.info(f"Test terminé avec le code: {result.returncode}")
        
        if result.returncode == 0:
            return jsonify({"message": "Test RTMP réussi!", "status": "success"})
        else:
            logger.error(f"STDERR: {result.stderr}")
            return jsonify({
                "error": "Test RTMP échoué",
                "details": result.stderr[-500:],  # Dernières 500 caractères
                "returncode": result.returncode
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout: Test RTMP trop long"}), 500
    except Exception as e:
        logger.error(f"Erreur test RTMP: {e}")
        return jsonify({"error": f"Erreur test RTMP: {str(e)}"}), 500

@app.route("/api/audio-status")
def audio_status():
    """Vérifier les fichiers audio disponibles"""
    audio_files = []
    possible_files = ["audio.mp3", "background.mp3", "music.mp3", "stream_audio.mp3"]
    
    for filename in possible_files:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            audio_files.append({
                "filename": filename,
                "size": f"{size / 1024 / 1024:.2f} MB"
            })
    
    return jsonify({
        "audio_files": audio_files,
        "has_audio": len(audio_files) > 0
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

