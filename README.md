# FTP Stream - Servicio de Streaming de Video

Servicio automático que monitorea un directorio de videos FTP y los transmite a un servidor RTMP (YouTube Live, OvenMediaEngine, etc.).

## 🚀 Inicio Rápido

```bash
# 1. Clonar el repositorio
git clone <tu-repo>
cd ftp-stream

# 2. Instalar uv (si no lo tienes)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Configurar el proyecto
make setup

# 4. Ejecutar el servicio
make run
```

## 📋 Requisitos

- Python 3.8+
- `ffmpeg` instalado en el sistema
- `uv` (gestor de paquetes Python)

### Instalar FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**CentOS/RHEL:**
```bash
sudo yum install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## ⚙️ Configuración

### Variables de Entorno

Copia el archivo de ejemplo y edítalo:

```bash
cp .env.example .env
nano .env  # o tu editor favorito
```

Variables disponibles:

- **`WATCH_DIR`**: Directorio donde llegan los videos (default: `~/camera_data`)
- **`RTMP_URL`**: URL completa del servidor RTMP con tu clave de streaming
- **`MIN_FILE_AGE`**: Segundos que debe tener un archivo antes de procesarlo (default: `30`)
- **`MAX_RETRIES`**: Número máximo de reintentos por archivo (default: `3`)
- **`SCAN_INTERVAL`**: Intervalo de escaneo en segundos (default: `5`)

### Configuración RTMP

Edita las variables en `.env` o directamente en `streamer.py`:

```bash
# Para desarrollo/pruebas (tu servidor actual)
export RTMP_URL="rtmp://dev.video360.heligrafics.net:1935/qforest/test_device_001"

# Para YouTube Live (necesitas obtener tu clave)
export RTMP_URL="rtmp://a.rtmp.youtube.com/live2/{tu-clave-secreta}"
```

### YouTube Live

Para streaming a YouTube Live:
1. Ve a [YouTube Studio](https://studio.youtube.com)
2. Ir a "Crear" → "Emitir en directo"
3. Copiar la "URL del servidor" y "Clave de transmisión"
4. Actualizar `RTMP_URL` en el formato: `rtmp://a.rtmp.youtube.com/live2/{tu-clave}`

## 🛠️ Comandos Disponibles

```bash
make help              # Muestra todos los comandos disponibles
make setup             # Configura el proyecto (verifica ffmpeg e instala deps)
make install           # Instala dependencias con uv
make run               # Ejecuta el servicio de streaming
make dev               # Ejecuta en modo desarrollo
make clean             # Limpia archivos temporales
make create-watch-dir  # Crea el directorio de monitoreo
make test-stream       # Prueba la conexión RTMP con video de prueba
make status            # Muestra el estado del servicio
make check-ffmpeg      # Verifica que ffmpeg esté instalado
```

## 📖 Cómo Funciona

El servicio genera un **stream continuo "casi en vivo"** (1-5 min de retraso) a partir de los videos que la cámara va escribiendo:

### 🔄 Lógica de Transmisión Secuencial:

1. **Monitoreo continuo**: Escanea `WATCH_DIR` cada 5 segundos (configurable)

2. **Filtrado por edad**: Solo procesa archivos con >= 30 segundos de antigüedad (evita archivos en escritura)

3. **Limpieza de archivos viejos**: 
   - Si el stream se detuvo y hay videos anteriores al último procesado
   - Los **borra automáticamente** (nunca vuelve atrás en el tiempo)
   - Ejemplo: Si último fue `10:31`, borra `10:28`, `10:29`, `10:30`

4. **Exclusión del último archivo**:
   - El archivo más reciente **SIEMPRE se ignora** (se está escribiendo)
   - Si hay `10:30`, `10:31`, `10:32` → ignora `10:32`

5. **Selección secuencial**:
   - De los archivos disponibles, toma el **MÁS VIEJO** (garantiza orden cronológico)
   - Transmite `10:30` → luego `10:31` → luego `10:32` (siempre hacia adelante)

6. **Validación con ffprobe**: Verifica que el video esté completo antes de transmitir

7. **Transmisión RTMP**: Usa ffmpeg con `-re` (tiempo real) y `-c copy` (sin re-codificar)

8. **Limpieza post-transmisión**: Elimina el archivo exitosamente transmitido

9. **Manejo de errores**:
   - Archivos corruptos: reintenta hasta 3 veces
   - Si falla 3 veces: descarta (borra) y continúa con el siguiente
   - Reintentos automáticos después de 5 minutos

### 📊 Ejemplo de Flujo:

```
Momento 1 (10:31):
  Archivos: 10:28.mp4, 10:29.mp4, 10:30.mp4, 10:31.mp4 (escribiendo)
  Acción: Transmite 10:28, borra 10:28

Momento 2 (10:32):
  Archivos: 10:29.mp4, 10:30.mp4, 10:31.mp4, 10:32.mp4 (escribiendo)
  Acción: Transmite 10:29, borra 10:29

Momento 3 (10:33):
  Archivos: 10:30.mp4, 10:31.mp4, 10:32.mp4, 10:33.mp4 (escribiendo)
  Acción: Transmite 10:30, borra 10:30

(Stream se detiene 10 minutos...)

Momento 4 (10:45 - reinicio):
  Archivos: 10:31-10:44.mp4, 10:45.mp4 (escribiendo)
  Acción: Borra 10:31-10:40 (viejos), transmite 10:41, continúa secuencial
```

**Resultado**: Stream continuo, siempre avanzando en el tiempo, ~1-3 videos de retraso respecto al "vivo".

## 🔧 Desarrollo

### Estructura del Proyecto

```
ftp-stream/
├── streamer.py       # Script principal
├── pyproject.toml    # Configuración de dependencias (uv)
├── Makefile          # Comandos de automatización
└── README.md         # Documentación
```

### Ejecutar en Desarrollo

```bash
# Modo desarrollo (con logs)
make dev

# Ver estado
make status

# Probar conexión RTMP
make test-stream
```

## 📦 Gestión con UV

`uv` es un gestor de paquetes Python ultra-rápido escrito en Rust. Beneficios:

- ⚡ 10-100x más rápido que pip
- 🔒 Resolución de dependencias determinística
- 📦 Gestión automática de entornos virtuales
- 🎯 Compatible con pip y pyproject.toml

### Comandos UV

```bash
# Sincronizar dependencias
uv sync

# Ejecutar script con el entorno de uv
uv run python streamer.py

# Agregar una dependencia
uv add <paquete>

# Actualizar dependencias
uv lock --upgrade
```

## 🐳 Despliegue como Servicio (Systemd)

### Instalación Automática

El proyecto incluye un script que configura automáticamente el servicio:

```bash
# Instalar como servicio systemd
make install-service

# O directamente
./install-service.sh
```

El script:
- ✅ Detecta automáticamente paths y usuario
- ✅ Crea el servicio systemd
- ✅ Habilita inicio automático
- ✅ Configura variables de entorno
- ✅ Opción para iniciar inmediatamente

### Comandos del Servicio

```bash
# Ver estado
make service-status
# o
sudo systemctl status ftp-stream

# Ver logs
make service-logs          # Últimos 50 logs
make service-logs-live     # Seguir logs en vivo

# Controlar servicio
sudo systemctl start ftp-stream      # Iniciar
sudo systemctl stop ftp-stream       # Detener
sudo systemctl restart ftp-stream    # Reiniciar
sudo systemctl enable ftp-stream     # Habilitar inicio automático
sudo systemctl disable ftp-stream    # Deshabilitar inicio automático
```

### Modificar Configuración del Servicio

```bash
# Editar el servicio
sudo nano /etc/systemd/system/ftp-stream.service

# Cambiar variables de entorno en la sección [Service]:
# Environment="WATCH_DIR=/otra/ruta"
# Environment="RTMP_URL=rtmp://servidor:1935/app/key"
# Environment="SCAN_INTERVAL=1"

# Recargar y reiniciar
sudo systemctl daemon-reload
sudo systemctl restart ftp-stream
```

### Desinstalar Servicio

```bash
sudo systemctl stop ftp-stream
sudo systemctl disable ftp-stream
sudo rm /etc/systemd/system/ftp-stream.service
sudo systemctl daemon-reload
```

### Instalación Manual (alternativa)

Si prefieres crear el servicio manualmente:

Crear archivo `/etc/systemd/system/ftp-stream.service`:

```ini
[Unit]
Description=FTP Stream Service
After=network.target

[Service]
Type=simple
User=tu-usuario
WorkingDirectory=/ruta/a/ftp-stream
Environment="WATCH_DIR=/home/tu-usuario/camera_data"
Environment="RTMP_URL=rtmp://servidor:1935/app/key"
ExecStart=/usr/bin/python3 /ruta/a/ftp-stream/streamer.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activar el servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ftp-stream
sudo systemctl start ftp-stream
sudo systemctl status ftp-stream
```

Ver logs:

```bash
sudo journalctl -u ftp-stream -f
```

## 🐛 Solución de Problemas

### FFmpeg no encontrado
```bash
# Verificar instalación
which ffmpeg
ffmpeg -version

# Si no está instalado
sudo apt install ffmpeg  # Ubuntu/Debian
```

### Directorio no existe
```bash
# Crear directorio de monitoreo
make create-watch-dir
```

### Error de conexión RTMP
```bash
# Probar conexión con video de prueba
make test-stream

# Verificar que la URL RTMP esté completa y sea correcta
echo $RTMP_URL
```

### Archivos corruptos ("moov atom not found")
Este error ocurre cuando el archivo aún se está escribiendo o está corrupto:

**Solución automática** (ya implementada):
- El script espera `MIN_FILE_AGE` segundos antes de procesar
- Valida con `ffprobe` antes de transmitir
- Reintenta hasta `MAX_RETRIES` veces
- Mueve archivos fallidos a `_failed/`

**Ajustar manualmente**:
```bash
# Aumentar tiempo de espera (ej: 60 segundos)
export MIN_FILE_AGE=60
make run

# O editar en .env
echo "MIN_FILE_AGE=60" >> .env
```

### Ver archivos fallidos
```bash
# Los archivos corruptos se mueven aquí
ls -lh ~/camera_data/_failed/
```

### Permisos
```bash
# Asegurar permisos de lectura en el directorio
chmod -R 755 ~/camera_data
```

### Logs más detallados
El script ya incluye timestamps y logging mejorado. Para ver logs del servicio systemd:
```bash
sudo journalctl -u ftp-stream -f
```

## 📝 Notas

- El servicio elimina los videos después de transmitirlos para ahorrar espacio
- Se salta el último archivo (puede estar siendo escrito por la cámara)
- Usa `-re` en ffmpeg para streaming en tiempo real
- Usa `-c copy` para evitar re-codificación (más rápido, menos CPU)

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

[Especificar licencia]

## 👤 Autor

[Tu nombre/organización]
