#!/usr/bin/env bash
# ==============================================================================
#   SURA CITAS BOT - GENERADOR DE INSTALADOR DISK IMAGE (.DMG) PARA MACOS
#   ENGINEERED BY: SHION
# ==============================================================================

set -euo pipefail

# Colores para salida en consola
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}====================================================================${NC}"
echo -e "${GREEN}   SURA Citas Bot - Empaquetador DMG para macOS (Shion Enterprise)   ${NC}"
echo -e "${BLUE}====================================================================${NC}"

# Localizar la raíz del repositorio
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

APP_NAME="SuraCitas"
APP_BUNDLE="dist/${APP_NAME}.app"
DMG_NAME="Instalador_SuraCitas.dmg"
OUTPUT_DMG="dist/${DMG_NAME}"
TEMP_DMG_DIR="build/dmg_pack"

# 1. Verificar o compilar la aplicación con PyInstaller
if [ ! -d "$APP_BUNDLE" ]; then
    echo -e "${YELLOW}[1/4] No se detectó ${APP_BUNDLE}. Compilando con PyInstaller...${NC}"
    if ! command -v pyinstaller &> /dev/null; then
        echo -e "${RED}[ERROR] pyinstaller no está instalado o no se encuentra en el PATH.${NC}"
        echo -e "Ejecuta: pip install pyinstaller"
        exit 1
    fi
    pyinstaller packaging/macos/SuraCitas_mac.spec --clean -y
else
    echo -e "${GREEN}[1/4] Bundle encontrado: ${APP_BUNDLE}${NC}"
fi

# 2. Preparar el directorio temporal de ensamblado para el DMG
echo -e "${YELLOW}[2/4] Estructurando el volumen de instalación...${NC}"
rm -rf "$TEMP_DMG_DIR"
mkdir -p "$TEMP_DMG_DIR"

# Copiar el paquete .app
cp -R "$APP_BUNDLE" "$TEMP_DMG_DIR/"

# Crear enlace simbólico hacia /Applications para instalación mediante Drag-and-Drop
ln -s /Applications "$TEMP_DMG_DIR/Applications"

# 3. Generar la imagen de disco (.dmg) comprimida (formato UDZO) con hdiutil
echo -e "${YELLOW}[3/4] Generando imagen de disco UDZO comprimida...${NC}"
mkdir -p dist
rm -f "$OUTPUT_DMG"

hdiutil create \
    -volname "Sura Citas Bot" \
    -srcfolder "$TEMP_DMG_DIR" \
    -ov \
    -format UDZO \
    "$OUTPUT_DMG"

# 4. Limpieza de archivos temporales
echo -e "${YELLOW}[4/4] Limpiando archivos temporales...${NC}"
rm -rf "$TEMP_DMG_DIR"

echo -e "${GREEN}====================================================================${NC}"
echo -e "${GREEN}✔ ¡ÉXITO! Instalador DMG generado satisfactoriamente:${NC}"
echo -e "  Ruta: ${OUTPUT_DMG}"
echo -e "  Tamaño: $(du -sh "$OUTPUT_DMG" | awk '{print $1}')"
echo -e "${GREEN}====================================================================${NC}"
