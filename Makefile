.PHONY: help install run dev clean setup check-ffmpeg

# Variables
PYTHON := python3
WATCH_DIR := ~/camera_data
RTMP_URL := rtmp://a.rtmp.youtube.com/live2

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: check-ffmpeg install ## Configura el proyecto completo (verifica ffmpeg e instala dependencias)
	@echo "✅ Proyecto configurado correctamente"

check-ffmpeg: ## Verifica que ffmpeg esté instalado
	@echo "🔍 Verificando ffmpeg..."
	@which ffmpeg > /dev/null || (echo "❌ ERROR: ffmpeg no está instalado. Instálalo con: sudo apt install ffmpeg" && exit 1)
	@echo "✅ ffmpeg encontrado: $$(ffmpeg -version | head -n1)"

install: ## Instala dependencias con uv (crea venv si no existe)
	@echo "📦 Creando entorno virtual..."
	@uv venv 2>/dev/null || true
	@echo "✅ Entorno listo"

run: check-ffmpeg ## Ejecuta el servicio de streaming
	@echo "🚀 Iniciando servicio de streaming..."
	@echo "📁 Directorio: $(WATCH_DIR)"
	@echo "📡 URL RTMP: $(RTMP_URL)"
	@$(PYTHON) streamer.py

dev: check-ffmpeg ## Ejecuta el servicio en modo desarrollo (con logs verbosos)
	@echo "🔧 Modo desarrollo"
	@$(PYTHON) streamer.py

clean: ## Limpia archivos temporales y cache
	@echo "🧹 Limpiando archivos temporales..."
	@rm -rf .venv __pycache__ *.pyc .pytest_cache .coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Limpieza completada"

create-watch-dir: ## Crea el directorio de monitoreo si no existe
	@echo "📁 Creando directorio de monitoreo..."
	@mkdir -p $(WATCH_DIR)
	@echo "✅ Directorio creado: $(WATCH_DIR)"

test-connection: ## Prueba conectividad al servidor RTMP
	@echo "🔍 Probando conectividad RTMP..."
	@echo "URL: $(RTMP_URL)"
	@echo ""
	@echo "1. Extrayendo host y puerto..."
	@HOST=$$(echo $(RTMP_URL) | sed -n 's|rtmp://\([^:/]*\).*|\1|p'); \
	PORT=$$(echo $(RTMP_URL) | sed -n 's|rtmp://[^:]*:\([0-9]*\)/.*|\1|p'); \
	if [ -z "$$PORT" ]; then PORT=1935; fi; \
	echo "   Host: $$HOST"; \
	echo "   Puerto: $$PORT"; \
	echo ""; \
	echo "2. Probando conectividad TCP..."; \
	if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$$HOST/$$PORT" 2>/dev/null; then \
		echo "   ✅ Puerto $$PORT está ABIERTO en $$HOST"; \
	else \
		echo "   ❌ NO se puede conectar a $$HOST:$$PORT"; \
		echo "   Posibles causas:"; \
		echo "      • Servidor RTMP apagado"; \
		echo "      • Firewall bloqueando puerto $$PORT"; \
		echo "      • Host incorrecto"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "3. Probando transmisión RTMP real (3 segundos)..."; \
	timeout 3 ffmpeg -f lavfi -i testsrc=size=640x480:rate=1 -f lavfi -i sine=frequency=440 \
		-c:v libx264 -preset ultrafast -tune zerolatency -c:a aac \
		-f flv $(RTMP_URL) -loglevel error 2>&1 || true; \
	echo ""; \
	echo "✅ Diagnóstico completo"

test-stream: check-ffmpeg ## Transmite video de prueba continuo (Ctrl+C para detener)
	@echo "🧪 Transmitiendo video de prueba al servidor RTMP..."
	@echo "URL: $(RTMP_URL)"
	@echo "Presiona Ctrl+C para detener"
	@echo ""
	@ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=30 -f lavfi -i sine=frequency=1000 \
		-c:v libx264 -preset ultrafast -tune zerolatency -c:a aac -f flv $(RTMP_URL)

status: ## Muestra el estado del servicio
	@echo "📊 Estado del servicio:"
	@echo "  Directorio: $(WATCH_DIR)"
	@if [ -d "$(WATCH_DIR)" ]; then \
		echo "  ✅ Directorio existe"; \
		echo "  📄 Archivos MP4: $$(find $(WATCH_DIR) -name '*.mp4' 2>/dev/null | wc -l)"; \
	else \
		echo "  ❌ Directorio no existe"; \
	fi
	@echo "  Python: $$($(PYTHON) --version)"
	@if which ffmpeg > /dev/null; then \
		echo "  ✅ ffmpeg instalado"; \
	else \
		echo "  ❌ ffmpeg no instalado"; \
	fi

install-service: ## Instala el servicio systemd (requiere sudo)
	@echo "🔧 Instalando como servicio systemd..."
	@./install-service.sh

service-status: ## Muestra el estado del servicio systemd
	@sudo systemctl status ftp-stream --no-pager || echo "Servicio no instalado. Ejecuta: make install-service"

service-logs: ## Muestra los logs del servicio systemd
	@sudo journalctl -u ftp-stream -n 50 --no-pager

service-logs-live: ## Sigue los logs del servicio en tiempo real
	@sudo journalctl -u ftp-stream -f

logs: ## Muestra los últimos logs del archivo (modo manual)
	@tail -n 50 ~/ftp-stream.log 2>/dev/null || echo "No hay logs aún. El archivo se crea al ejecutar el servicio."

logs-live: ## Sigue los logs del archivo en tiempo real (modo manual)
	@tail -f ~/ftp-stream.log
