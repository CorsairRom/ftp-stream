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

test-stream: check-ffmpeg ## Prueba la conexión RTMP (sin procesar archivos)
	@echo "🧪 Probando conexión RTMP..."
	@echo "Presiona Ctrl+C para detener"
	@ffmpeg -f lavfi -i testsrc=size=1280x720:rate=30 -f lavfi -i sine=frequency=1000 -c:v libx264 -preset ultrafast -c:a aac -f flv $(RTMP_URL)

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
