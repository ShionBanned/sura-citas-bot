#!/usr/bin/env bash
# ==============================================================================
#   SURA CITAS BOT - SCRIPT DE COMPILACIÓN INTEGRAL PARA MACOS
#   CONFIGURA ENTORNO, INSTALA DEPENDENCIAS Y GENERA .APP Y .DMG
#   ENGINEERED BY: SHION
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}====================================================================${NC}"
echo -e "${GREEN}       SURA Citas Bot - Constructor Integral para macOS             ${NC}"
echo -e "${BLUE}====================================================================${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Comprobar instalación de Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 no está instalado en este equipo.${NC}"
    echo -e "Descárgalo desde https://www.python.org/downloads/ o con: brew install python"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}[1/5] Python detectado: versión ${PY_VER}${NC}"

# 2. Configurar entorno virtual aislado (.venv)
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}[2/5] Creando entorno virtual aislado en ${VENV_DIR}...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activar entorno virtual
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# 3. Instalar librerías requeridas
echo -e "${YELLOW}[3/5] Actualizando pip e instalando dependencias de producción...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Instalar binarios mínimos de Playwright
echo -e "${YELLOW}Instalando motor Chromium para Playwright...${NC}"
playwright install chromium

# 4. Compilar aplicación (.app) con PyInstaller
echo -e "${YELLOW}[4/5] Compilando ejecutable nativo (.app) con PyInstaller...${NC}"
pyinstaller packaging/macos/SuraCitas_mac.spec --clean -y

# 5. Generar paquete de distribución (.dmg)
echo -e "${YELLOW}[5/5] Construyendo imagen de disco instalable (.dmg)...${NC}"
chmod +x packaging/macos/build_dmg.sh
./packaging/macos/build_dmg.sh

echo -e "${GREEN}====================================================================${NC}"
echo -e "${GREEN}✔ ¡PROCESO DE CONSTRUCCIÓN COMPLETADO CON ÉXITO!${NC}"
echo -e "  - Paquete de aplicación:  dist/SuraCitas.app"
echo -e "  - Instalador para cliente: dist/Instalador_SuraCitas.dmg"
echo -e "${GREEN}====================================================================${NC}"
