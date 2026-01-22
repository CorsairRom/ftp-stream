import os
import time
import subprocess
import glob
import sys
from datetime import datetime, timedelta

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
    """Logger simple con timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


# Validar configuración al inicio
if not os.path.exists(WATCH_DIR):
    log(f"ERROR: El directorio {WATCH_DIR} no existe", "ERROR")
    sys.exit(1)

if not RTMP_URL or RTMP_URL == "rtmp://a.rtmp.youtube.com/live2":
    log("ADVERTENCIA: URL RTMP incompleta. Configura RTMP_URL con tu clave de streaming", "WARN")
    log("Ejemplo: export RTMP_URL='rtmp://server:1935/app/stream_key'", "WARN")

log("Iniciando puente de video...")
log(f"Monitoreando: {WATCH_DIR}")
log(f"Destino RTMP: {RTMP_URL}")
log(f"Edad mínima archivo: {MIN_FILE_AGE}s")
log(f"Máximo reintentos: {MAX_RETRIES}")
log(f"Intervalo escaneo: {SCAN_INTERVAL}s")
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
        
        # PASO 2: Descartar el último archivo (siempre se está escribiendo)
        if len(files) >= 2:
            # Excluir el último (se está escribiendo)
            available_files = files[:-1]
            currently_writing = files[-1]
            log(f"📹 Archivo en escritura (ignorado): {os.path.basename(currently_writing)}")
        else:
            # Solo hay 1 archivo, debe estar escribiéndose
            log(f"Solo 1 archivo disponible (debe estar siendo escrito), esperando más archivos...")
            time.sleep(SCAN_INTERVAL)
            continue
        
        # PASO 3: De los archivos disponibles, tomar el MÁS VIEJO (para ir en orden secuencial)
        # Esto garantiza que vamos 10:30 → 10:31 → 10:32 (nunca hacia atrás)
        target = available_files[0]  # El más viejo disponible (ya ordenado)
        
        log(f"📂 Archivos disponibles: {len(available_files)}, Procesando el más antiguo: {os.path.basename(target)}")
        
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
            log(f"❌ Error en transmisión: {os.path.basename(target)}", "ERROR")
            if e.stderr:
                log(f"FFmpeg: {e.stderr.strip()}", "ERROR")
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