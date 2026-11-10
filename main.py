# -*- coding: utf-8 -*-
"""
================================================================================
  SURA CITAS BOT - ENTORNO DE EJECUCIÓN PRINCIPAL (macOS & MULTIPLATAFORMA)
  ENGINEERED BY: SHION
================================================================================
"""

import sys
import traceback
import security_shield  # Escudo de seguridad anti-IA y anti-depuración
from app_gui import SuraCitasApp

def main():
    try:
        app = SuraCitasApp()
        app.mainloop()
    except Exception as e:
        err_msg = traceback.format_exc()
        try:
            import tkinter as tk
            from tkinter import messagebox as mb
            root = tk.Tk()
            root.withdraw()
            mb.showerror(
                "Error Crítico - SURA Citas Bot",
                f"Ocurrió un error inesperado al iniciar la aplicación:\n\n{err_msg}\n"
                f"Si estás en macOS, verifica que Google Chrome esté instalado."
            )
            root.destroy()
        except Exception:
            pass
        print(f"[FATAL ERROR] {err_msg}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
