import os
import time
import subprocess
import glob

# RUTA DONDE LLEGAN LOS VIDEOS
WATCH_DIR = os.path.expanduser("~/camera_data")
# URL DE OVENMEDIAENGINE (RTMP)
RTMP_URL = "rtmp://dev.video360.heligrafics.net:1935/qforest/test_device_001"

def get_files():
    # Busca todos los mp4 en subcarpetas
    return glob.glob(os.path.join(WATCH_DIR, "**/*.mp4"), recursive=True)

print("[*] Iniciando puente de video...")
print(f"[*] Monitoreando: {WATCH_DIR}")

streamed_files = set()

while True:
    files = get_files()
    
    if len(files) >= 2:
        # Ordenar por fecha (el más viejo primero)
        files.sort(key=os.path.getmtime)
        
        # Tomamos el penúltimo (el último suele estar bloqueado por la cámara)
        target = files[-2]
        
        if target not in streamed_files:
            print(f"\n[+] Transmitiendo: {os.path.basename(target)}")
            
            # Comando FFmpeg: Lee el archivo y lo empuja a OME
            cmd = [
                "ffmpeg", "-re", "-i", target, 
                "-c", "copy", "-f", "flv", RTMP_URL
            ]
            
            try:
                # Ejecutar transmisión
                subprocess.run(cmd, check=True)
                streamed_files.add(target)
                
                # BORRADO: Limpiamos el archivo para no agotar el disco de la VM
                os.remove(target)
                print("[OK] Archivo procesado y eliminado.")
                
            except Exception as e:
                print(f"[!] Error: {e}")
    
    time.sleep(5)