#!/usr/bin/env bash
# ==============================================================================
#   SURA CITAS BOT - LANZADOR DIRECTO DE 1-CLIC PARA MACOS (.command)
#   ENGINEERED BY: SHION
# ==============================================================================

# Cambiar al directorio del script
cd "$(dirname "$0")"

# Colores de consola
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}====================================================================${NC}"
echo -e "${GREEN}      ⚡ SURA Citas Bot - Iniciando en macOS (Modo 1-Clic) ⚡       ${NC}"
echo -e "${BLUE}====================================================================${NC}"

# 1. Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] No se encontró Python 3 en este sistema.${NC}"
    echo "Por favor descarga e instala Python 3 desde: https://www.python.org/downloads/"
    read -p "Presiona ENTER para salir..."
    exit 1
fi

# 2. Comprobar / Crear entorno virtual
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Configurando entorno virtual por primera vez en ${VENV_DIR}...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activar entorno virtual
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# 3. Comprobar librerías instaladas
if ! python3 -c "import playwright" &> /dev/null; then
    echo -e "${YELLOW}Instalando dependencias necesarias (Playwright)...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
    playwright install chromium
fi

# 4. Lanzar la aplicación
echo -e "${GREEN}Lanzando interfaz gráfica de SURA Citas Bot...${NC}"
python3 main.py
