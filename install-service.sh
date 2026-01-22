#!/bin/bash
set -e

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Instalador de FTP-Stream como Servicio Systemd ===${NC}\n"

# Detectar el directorio del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "📁 Directorio del proyecto: ${PROJECT_DIR}"

# Detectar el usuario actual
CURRENT_USER="${SUDO_USER:-$USER}"
echo -e "👤 Usuario: ${CURRENT_USER}"

# Obtener el home del usuario
USER_HOME=$(eval echo ~${CURRENT_USER})
echo -e "🏠 Home: ${USER_HOME}"

# Detectar Python
PYTHON_BIN=$(which python3 || which python)
if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}❌ Error: Python no encontrado${NC}"
    exit 1
fi
echo -e "🐍 Python: ${PYTHON_BIN}"

# Verificar FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}❌ Error: ffmpeg no encontrado${NC}"
    echo -e "Instálalo con: sudo apt install ffmpeg"
    exit 1
fi
echo -e "🎬 FFmpeg: $(which ffmpeg)"

# Leer configuración (o usar defaults)
WATCH_DIR="${WATCH_DIR:-${USER_HOME}/camera_data}"
RTMP_URL="${RTMP_URL:-rtmp://dev.video360.heligrafics.net:1935/qforest/test_device_001}"

echo -e "\n${YELLOW}📋 Configuración:${NC}"
echo -e "   Directorio monitoreo: ${WATCH_DIR}"
echo -e "   URL RTMP: ${RTMP_URL}"

# Preguntar confirmación
read -p "¿Continuar con la instalación? (s/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[SsYy]$ ]]; then
    echo -e "${RED}Instalación cancelada${NC}"
    exit 1
fi

# Crear archivo de servicio
SERVICE_FILE="/tmp/ftp-stream.service"
echo -e "\n📝 Creando archivo de servicio..."

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=FTP Stream - Servicio de streaming de video a RTMP
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}

# Variables de entorno
Environment="WATCH_DIR=${WATCH_DIR}"
Environment="RTMP_URL=${RTMP_URL}"
Environment="MIN_FILE_AGE=30"
Environment="MAX_RETRIES=3"
Environment="SCAN_INTERVAL=5"

# Comando de ejecución
ExecStart=${PYTHON_BIN} ${PROJECT_DIR}/streamer.py

# Reinicio automático en caso de fallo
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ftp-stream

# Límites de recursos (opcional)
# LimitNOFILE=65536
# MemoryLimit=512M

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✅ Archivo de servicio creado${NC}"

# Instalar el servicio
echo -e "\n🔧 Instalando servicio..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/ftp-stream.service
sudo chmod 644 /etc/systemd/system/ftp-stream.service

# Recargar systemd
echo -e "🔄 Recargando systemd..."
sudo systemctl daemon-reload

# Habilitar el servicio para inicio automático
echo -e "✨ Habilitando inicio automático..."
sudo systemctl enable ftp-stream.service

# Preguntar si iniciar ahora
echo -e "\n${YELLOW}¿Deseas iniciar el servicio ahora? (s/n):${NC}"
read -p "" -n 1 -r
echo
if [[ $REPLY =~ ^[SsYy]$ ]]; then
    echo -e "🚀 Iniciando servicio..."
    sudo systemctl start ftp-stream.service
    sleep 2
    
    # Mostrar estado
    echo -e "\n📊 Estado del servicio:"
    sudo systemctl status ftp-stream.service --no-pager
fi

# Información útil
echo -e "\n${GREEN}=== ✅ Instalación completada ===${NC}\n"
echo -e "📚 Comandos útiles:"
echo -e "   ${YELLOW}Iniciar servicio:${NC}    sudo systemctl start ftp-stream"
echo -e "   ${YELLOW}Detener servicio:${NC}    sudo systemctl stop ftp-stream"
echo -e "   ${YELLOW}Reiniciar servicio:${NC}  sudo systemctl restart ftp-stream"
echo -e "   ${YELLOW}Ver estado:${NC}          sudo systemctl status ftp-stream"
echo -e "   ${YELLOW}Ver logs en vivo:${NC}    sudo journalctl -u ftp-stream -f"
echo -e "   ${YELLOW}Ver logs recientes:${NC}  sudo journalctl -u ftp-stream -n 50"
echo -e "   ${YELLOW}Deshabilitar inicio:${NC} sudo systemctl disable ftp-stream"
echo -e "   ${YELLOW}Habilitar inicio:${NC}    sudo systemctl enable ftp-stream"
echo -e "\n📝 Para cambiar configuración:"
echo -e "   1. Edita: /etc/systemd/system/ftp-stream.service"
echo -e "   2. Recarga: sudo systemctl daemon-reload"
echo -e "   3. Reinicia: sudo systemctl restart ftp-stream"
echo -e "\n🗑️  Para desinstalar:"
echo -e "   sudo systemctl stop ftp-stream"
echo -e "   sudo systemctl disable ftp-stream"
echo -e "   sudo rm /etc/systemd/system/ftp-stream.service"
echo -e "   sudo systemctl daemon-reload"
echo ""
