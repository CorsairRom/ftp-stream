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

streamed_files = set()
failed_files = {}  # {filepath: {'count': int, 'last_attempt': timestamp}}

while True:
    try:
        files = get_files()
        
        if len(files) >= 2:
            # Ordenar por fecha (el más viejo primero)
            files.sort(key=os.path.getmtime)
            
            # IMPORTANTE: Tomamos el PENÚLTIMO (files[-2])
            # El último (files[-1]) siempre está siendo escrito por la cámara
            target = files[-2]
            
            # Verificar si ya fue procesado exitosamente
            if target in streamed_files:
                pass  # Ya procesado exitosamente, esperar a que haya más archivos
            else:
                # Obtener info de intentos previos
                file_info = failed_files.get(target, {'count': 0, 'last_attempt': 0})
                retry_count = file_info['count']
                last_attempt = file_info['last_attempt']
                
                # Verificar si ya falló demasiadas veces RECIENTEMENTE
                # Permitir reintentar después de 5 minutos (300 segundos)
                time_since_last_attempt = time.time() - last_attempt
                if retry_count >= MAX_RETRIES and time_since_last_attempt < 300:
                    # Saltarlo por ahora, puede estar siendo escrito aún
                    log(f"Saltando archivo (intentos previos: {retry_count}, esperando antes de reintentar): {os.path.basename(target)}")
                else:
                    # Resetear contador si ha pasado suficiente tiempo
                    if time_since_last_attempt >= 300:
                        retry_count = 0
                    
                    attempt = retry_count + 1
                    
                    log(f"Procesando ({attempt}/{MAX_RETRIES}): {os.path.basename(target)}")
                    
                    # Validar que el archivo esté completo
                    if not validate_video_file(target):
                        log(f"Archivo corrupto o incompleto (puede estar escribiéndose): {os.path.basename(target)}", "WARN")
                        failed_files[target] = {'count': attempt, 'last_attempt': time.time()}
                        
                        if attempt >= MAX_RETRIES:
                            log(f"Archivo no válido tras {MAX_RETRIES} intentos, se saltará temporalmente: {os.path.basename(target)}", "WARN")
                            log(f"Se reintentará automáticamente en 5 minutos si sigue ahí", "INFO")
                        continue
                
                log(f"Transmitiendo: {os.path.basename(target)}")
                
                # Comando FFmpeg: Lee el archivo y lo empuja al servidor RTMP
                cmd = [
                    "ffmpeg", "-re", "-i", target,
                    "-c", "copy", "-f", "flv",
                    "-rtmp_buffer", "1000",  # Buffer para conexiones inestables
                    "-loglevel", "error",    # Solo mostrar errores
                    RTMP_URL
                ]
                
                try:
                    # Ejecutar transmisión
                    result = subprocess.run(
                        cmd, 
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=3600  # Timeout de 1 hora
                    )
                    
                    # Éxito: marcar como procesado y eliminar
                    streamed_files.add(target)
                    os.remove(target)
                    log(f"✓ Transmitido y eliminado: {os.path.basename(target)}", "SUCCESS")
                    
                    # Limpiar del registro de fallos si estaba ahí
                    if target in failed_files:
                        del failed_files[target]
                    
                except subprocess.TimeoutExpired:
                    log(f"Timeout transmitiendo: {os.path.basename(target)}", "ERROR")
                    failed_files[target] = {'count': attempt, 'last_attempt': time.time()}
                    
                except subprocess.CalledProcessError as e:
                    log(f"Error en transmisión: {os.path.basename(target)}", "ERROR")
                    if e.stderr:
                        log(f"FFmpeg error: {e.stderr.strip()}", "ERROR")
                    failed_files[target] = {'count': attempt, 'last_attempt': time.time()}
                    
                except Exception as e:
                    log(f"Error inesperado: {e}", "ERROR")
                    failed_files[target] = {'count': attempt, 'last_attempt': time.time()}
        
        elif len(files) == 1:
            log(f"Solo 1 archivo encontrado (puede estar siendo escrito), esperando...")
        else:
            log(f"No hay archivos para procesar")
        
    except KeyboardInterrupt:
        log("\nInterrumpido por el usuario", "INFO")
        log(f"Archivos procesados: {len(streamed_files)}", "INFO")
        log(f"Archivos fallidos: {len(failed_files)}", "INFO")
        sys.exit(0)
    
    except Exception as e:
        log(f"Error en loop principal: {e}", "ERROR")
    
    time.sleep(SCAN_INTERVAL)