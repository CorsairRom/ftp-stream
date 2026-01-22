import os
import time
import subprocess
import glob
import sys
from datetime import datetime, timedelta
import logging

# CONFIGURACIÓN (puedes sobreescribir con variables de entorno)
WATCH_DIR = os.getenv("WATCH_DIR", os.path.expanduser("~/camera_data"))
RTMP_URL = os.getenv("RTMP_URL", "rtmp://dev.video360.heligrafics.net:1935/qforest/test_device_001")

# Tiempo mínimo que debe tener un archivo antes de procesarlo (en segundos)
# Esto evita procesar archivos que aún se están escribiendo
MIN_FILE_AGE = int(os.getenv("MIN_FILE_AGE", "30"))

# Número máximo de reintentos por archivo
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Intervalo de escaneo (en segundos)
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "5"))

# Configurar logging dual (consola + archivo)
LOG_FILE = os.path.expanduser("~/ftp-stream.log")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def get_files():
    """Busca todos los mp4 en subcarpetas que sean lo suficientemente viejos."""
    all_files = glob.glob(os.path.join(WATCH_DIR, "**/*.mp4"), recursive=True)
    
    # Filtrar archivos que sean lo suficientemente viejos
    now = time.time()
    valid_files = []
    for f in all_files:
        try:
            file_age = now - os.path.getmtime(f)
            if file_age >= MIN_FILE_AGE:
                valid_files.append(f)
            else:
                remaining = int(MIN_FILE_AGE - file_age)
                print(f"[~] Esperando archivo: {os.path.basename(f)} (faltan {remaining}s)")
        except OSError:
            continue
    
    return valid_files


def validate_video_file(filepath):
    """Valida que el archivo de video esté completo usando ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=10,
            check=True
        )
        return result.stdout.strip() != ""
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False

def log(message, level="INFO"):
    """Logger con timestamp a consola y archivo."""
    level_map = {
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "SUCCESS": logging.INFO,
        "DEBUG": logging.DEBUG
    }
    logger.log(level_map.get(level, logging.INFO), message)


def test_rtmp_connection():
    """Prueba la conectividad al servidor RTMP."""
    import socket
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(RTMP_URL)
        host = parsed.hostname
        port = parsed.port or 1935
        
        log(f"Probando conexión a {host}:{port}...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            log(f"✅ Puerto {port} abierto en {host}", "SUCCESS")
            return True
        else:
            log(f"❌ No se puede conectar a {host}:{port}", "ERROR")
            log(f"Verifica: 1) Servidor encendido, 2) Puerto correcto, 3) Firewall", "ERROR")
            return False
    except Exception as e:
        log(f"❌ Error probando conexión: {e}", "ERROR")
        return False


# Validar configuración al inicio
if not os.path.exists(WATCH_DIR):
    log(f"ERROR: El directorio {WATCH_DIR} no existe", "ERROR")
    sys.exit(1)

if not RTMP_URL or RTMP_URL == "rtmp://a.rtmp.youtube.com/live2":
    log("ADVERTENCIA: URL RTMP incompleta. Configura RTMP_URL con tu clave de streaming", "WARN")
    log("Ejemplo: export RTMP_URL='rtmp://server:1935/app/stream_key'", "WARN")

log("Iniciando puente de video...")
log(f"Archivo de logs: {LOG_FILE}")
log(f"Monitoreando: {WATCH_DIR}")
log(f"Destino RTMP: {RTMP_URL}")
log(f"Edad mínima archivo: {MIN_FILE_AGE}s")
log(f"Máximo reintentos: {MAX_RETRIES}")
log(f"Intervalo escaneo: {SCAN_INTERVAL}s")
log("-" * 60)

# Probar conectividad al servidor RTMP
if not test_rtmp_connection():
    log("⚠️  ADVERTENCIA: No se puede conectar al servidor RTMP", "WARN")
    log("El servicio continuará, pero las transmisiones fallarán", "WARN")
    log("-" * 60)
else:
    log("-" * 60)

# Tracking del último archivo procesado (por timestamp de modificación)
last_processed_mtime = 0
failed_files = {}  # {filepath: {'count': int, 'last_attempt': timestamp}}

while True:
    try:
        files = get_files()
        
        if len(files) == 0:
            log("No hay archivos para procesar")
            time.sleep(SCAN_INTERVAL)
            continue
        
        # Ordenar por fecha de modificación (el más viejo primero)
        files.sort(key=os.path.getmtime)
        
        log(f"📋 Total archivos encontrados (>={MIN_FILE_AGE}s edad): {len(files)}")
        for idx, f in enumerate(files, 1):
            age = int(time.time() - os.path.getmtime(f))
            log(f"   {idx}. {os.path.basename(f)} (edad: {age}s)")
        
        # PASO 1: Limpiar archivos viejos (anteriores al último procesado)
        # Esto evita volver atrás en el tiempo
        old_files = []
        for f in files:
            f_mtime = os.path.getmtime(f)
            if f_mtime <= last_processed_mtime:
                old_files.append(f)
        
        if old_files:
            log(f"⚠️  Encontrados {len(old_files)} archivos VIEJOS (anteriores al último procesado)")
            for old_file in old_files:
                try:
                    log(f"🗑️  Descartando archivo viejo: {os.path.basename(old_file)}")
                    os.remove(old_file)
                    # Limpiar del registro de fallos
                    if old_file in failed_files:
                        del failed_files[old_file]
                except Exception as e:
                    log(f"Error al borrar archivo viejo: {e}", "ERROR")
            
            # Refrescar lista sin archivos viejos
            files = [f for f in files if f not in old_files]
            if len(files) == 0:
                log("No quedan archivos por procesar después de limpiar viejos")
                time.sleep(SCAN_INTERVAL)
                continue
        
        # PASO 2: Identificar el archivo que AÚN SE ESTÁ ESCRIBIENDO
        # Un archivo se considera "en escritura" si:
        # 1. Fue modificado recientemente (< MIN_FILE_AGE segundos)
        # 2. O es el último por fecha de modificación Y tiene < 5 minutos
        
        now = time.time()
        writing_files = []
        available_files = []
        
        for f in files:
            f_mtime = os.path.getmtime(f)
            age = now - f_mtime
            
            # Si el archivo fue modificado hace menos de 60 segundos, probablemente se está escribiendo
            if age < 60:
                writing_files.append(f)
                log(f"✏️  Archivo RECIENTE (ignorado, edad: {int(age)}s): {os.path.basename(f)}")
            else:
                available_files.append(f)
        
        if not available_files:
            log(f"No hay archivos listos (todos son muy recientes), esperando...")
            time.sleep(SCAN_INTERVAL)
            continue
        
        log(f"📋 Archivos disponibles para streaming: {len(available_files)}")
        for idx, f in enumerate(available_files, 1):
            age = int(now - os.path.getmtime(f))
            log(f"   {idx}. {os.path.basename(f)} (edad: {age}s)")
        
        # PASO 3: De los archivos disponibles, tomar el MÁS VIEJO (para ir en orden secuencial)
        # Esto garantiza que vamos 10:30 → 10:31 → 10:32 (nunca hacia atrás)
        target = available_files[0]  # El más viejo disponible (ya ordenado)
        
        log(f"🎯 Seleccionado para transmitir: {os.path.basename(target)}")
        
        # PASO 4: Verificar intentos previos
        file_info = failed_files.get(target, {'count': 0, 'last_attempt': 0})
        retry_count = file_info['count']
        last_attempt = file_info['last_attempt']
        
        # Verificar si ya falló demasiadas veces RECIENTEMENTE
        time_since_last_attempt = time.time() - last_attempt
        if retry_count >= MAX_RETRIES and time_since_last_attempt < 300:
            log(f"⏭️  Saltando temporalmente (intentos: {retry_count}, se reintentará en {int(300 - time_since_last_attempt)}s): {os.path.basename(target)}")
            time.sleep(SCAN_INTERVAL)
            continue
        
        # Resetear contador si ha pasado suficiente tiempo
        if time_since_last_attempt >= 300:
            retry_count = 0
        
        attempt = retry_count + 1
        log(f"🔄 Procesando ({attempt}/{MAX_RETRIES}): {os.path.basename(target)}")
        
        # PASO 5: Validar que el archivo esté completo
        if not validate_video_file(target):
            log(f"⚠️  Archivo corrupto o incompleto: {os.path.basename(target)}", "WARN")
            failed_files[target] = {'count': attempt, 'last_attempt': time.time()}
            
            if attempt >= MAX_RETRIES:
                log(f"❌ Archivo no válido tras {MAX_RETRIES} intentos, se descartará: {os.path.basename(target)}", "ERROR")
                try:
                    os.remove(target)
                    log(f"🗑️  Archivo corrupto eliminado: {os.path.basename(target)}")
                    if target in failed_files:
                        del failed_files[target]
                except Exception as e:
                    log(f"Error al eliminar archivo corrupto: {e}", "ERROR")
            
            time.sleep(SCAN_INTERVAL)
            continue
        
        # PASO 6: Transmitir el archivo
        log(f"📡 Transmitiendo: {os.path.basename(target)}")
        
        cmd = [
            "ffmpeg", "-re", "-i", target,
            "-c", "copy", "-f", "flv",
            "-rtmp_buffer", "1000",
            "-loglevel", "error",
            RTMP_URL
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                check=True,
                capture_output=True,
                text=True,
                timeout=3600
            )
            
            # ÉXITO: actualizar timestamp y eliminar archivo
            last_processed_mtime = os.path.getmtime(target)
            os.remove(target)
            log(f"✅ Transmitido y eliminado: {os.path.basename(target)}", "SUCCESS")
            
            # Limpiar del registro de fallos
            if target in failed_files:
                del failed_files[target]
            
        except subprocess.TimeoutExpired:
            log(f"⏱️  Timeout transmitiendo: {os.path.basename(target)}", "ERROR")
            failed_files[target] = {'count': attempt, 'last_attempt': time.time()}
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else ""
            
            # Detectar error específico de Broken Pipe (servidor rechaza conexión)
            if "Broken pipe" in error_msg or "Connection refused" in error_msg:
                log(f"❌ Error en transmisión: {os.path.basename(target)}", "ERROR")
                log(f"🔌 PROBLEMA DE CONEXIÓN RTMP:", "ERROR")
                log(f"   • El servidor rechazó o cerró la conexión", "ERROR")
                log(f"   • Verifica que el servidor RTMP esté corriendo", "ERROR")
                log(f"   • Verifica que la URL/clave sean correctas", "ERROR")
                log(f"   • URL: {RTMP_URL}", "ERROR")
            else:
                log(f"❌ Error en transmisión: {os.path.basename(target)}", "ERROR")
                if error_msg:
                    log(f"FFmpeg: {error_msg}", "ERROR")
            
            failed_files[target] = {'count': attempt, 'last_attempt': time.time()}
            
        except Exception as e:
            log(f"❌ Error inesperado: {e}", "ERROR")
            failed_files[target] = {'count': attempt, 'last_attempt': time.time()}
        
    except KeyboardInterrupt:
        log("\n⏹️  Interrumpido por el usuario", "INFO")
        log(f"📊 Archivos fallidos pendientes: {len(failed_files)}", "INFO")
        sys.exit(0)
    
    except Exception as e:
        log(f"❌ Error en loop principal: {e}", "ERROR")
    
    time.sleep(SCAN_INTERVAL)