# -*- coding: utf-8 -*-
"""
================================================================================
  SURA CITAS BOT - GESTOR DE CONFIGURACIÓN Y PERSISTENCIA
  SOPORTE MULTIPLATAFORMA (macOS ~/Library/Application Support / Windows APPDATA)
  ENGINEERED BY: SHION
================================================================================
"""

import json
import os
import sys

def get_config_directory() -> str:
    """Retorna la ruta del directorio de configuración según el sistema operativo."""
    if sys.platform == "darwin":
        # Ruta estándar de macOS para aplicaciones de usuario
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "SuraCitasApp")
    elif sys.platform == "win32":
        # Ruta estándar en Windows (%APPDATA%\SuraCitasApp)
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SuraCitasApp")
    else:
        # Estándar XDG para Linux / POSIX
        xdg_base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
        return os.path.join(xdg_base, "SuraCitasApp")

CONFIG_DIR = get_config_directory()
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_CONFIG = {
    "tipo_documento": "C",        # C = Cédula de Ciudadanía
    "documento": "",
    "clave": "",
    "paciente": "Santiago",        # Nombre o texto para identificar al paciente en el grupo familiar
    "servicio": "CONSULTA MEDICINA GENERAL SALUD CITA PRESENCIAL",
    "dia_deseado": "manana",       # "cualquiera", "manana", "hoy"
    "jornada": "cualquiera",       # "cualquiera", "manana", "tarde"
    "recordar": True,
    "intervalo_segundos": 15,
    "modo_silencioso": False       # Si True, oculta el navegador en segundo plano
}

def load_config() -> dict:
    """Carga la configuración guardada o devuelve los valores por defecto."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception as e:
            print(f"[CONFIG] Error al leer configuración: {e}", file=sys.stderr)
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config_data: dict) -> bool:
    """Guarda la configuración del usuario en el directorio correspondiente."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        # Si el usuario no quiere recordar la clave, no la guardamos
        to_save = config_data.copy()
        if not to_save.get("recordar", False):
            to_save["clave"] = ""
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[CONFIG] Error al guardar configuración: {e}", file=sys.stderr)
        return False
