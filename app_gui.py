# -*- coding: utf-8 -*-
"""
================================================================================
  SURA CITAS BOT - INTERFAZ GRÁFICA MODERNA
  ADAPTADA PARA MACOS (Fuentes Apple, Thread-Safe, Detección de Chrome)
  ENGINEERED BY: SHION
================================================================================
"""

import asyncio
import datetime
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from audio_alerter import stop_alarm, is_alarm_active
from config_manager import load_config, save_config
from sura_engine import SuraCitasEngine, find_system_browser

# Tipografía adaptada por plataforma
if sys.platform == "darwin":
    FONT_FAMILY = "Helvetica Neue"
    FONT_MONO = "Menlo"
else:
    FONT_FAMILY = "Segoe UI"
    FONT_MONO = "Consolas"

# Paleta de colores Dark Modern
BG_COLOR = "#0f172a"          # Slate 900
CARD_BG = "#1e293b"           # Slate 800
INPUT_BG = "#334155"          # Slate 700
TEXT_COLOR = "#f8fafc"        # Slate 50
TEXT_MUTED = "#94a3b8"        # Slate 400
ACCENT_GREEN = "#10b981"      # Emerald 500
ACCENT_GREEN_HOVER = "#059669"
ACCENT_RED = "#ef4444"        # Red 500
ACCENT_RED_HOVER = "#dc2626"
BORDER_COLOR = "#333b47"

TIPO_DOC_MAP = {
    "Cédula de Ciudadanía (CC)": "C",
    "Tarjeta de Identidad (TI)": "TI",
    "Cédula de Extranjería (CE)": "E",
    "Pasaporte (PA)": "P",
    "Permiso Especial (PEP)": "PE"
}
TIPO_DOC_REVERSE = {v: k for k, v in TIPO_DOC_MAP.items()}

SERVICIOS_DISPONIBLES = [
    "CONSULTA MEDICINA GENERAL SALUD CITA PRESENCIAL",
    "TELEMEDICINA INTERACTIVA MEDICO GENERAL",
    "CONSULTA TELEMEDICINA MEDICO GENERAL PRIORITARIA (CITA VIRTUAL)",
    "CONSULTA OPTOMETRIA GENERAL",
    "CONSULTA DE VALORACION POR ODONTOLOGO GENERAL"
]

class SuraCitasApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SURA - Cazador de Citas Automático")
        self.geometry("660x830")
        self.minsize(600, 720)
        self.configure(bg=BG_COLOR)

        self.engine: SuraCitasEngine = None
        self.engine_thread: threading.Thread = None
        self.config = load_config()

        self._setup_styles()
        self._build_ui()
        self._load_saved_values()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Verificación amigable de navegador diferida para garantizar carga del GUI
        self.after(500, self._check_browser_availability)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=BG_COLOR, foreground=TEXT_COLOR)
        style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        style.configure("CardTitle.TLabel", background=CARD_BG, foreground="#38bdf8", font=(FONT_FAMILY, 11, "bold"))
        style.configure("Muted.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=(FONT_FAMILY, 9))
        
        style.configure("TCheckbutton", background=CARD_BG, foreground=TEXT_COLOR, font=(FONT_FAMILY, 9))
        style.configure("TRadiobutton", background=CARD_BG, foreground=TEXT_COLOR, font=(FONT_FAMILY, 9))
        
        style.configure("TCombobox", fieldbackground=INPUT_BG, background=INPUT_BG, foreground=TEXT_COLOR, bordercolor=BORDER_COLOR)

    def _check_browser_availability(self):
        """Verifica la existencia de un navegador compatible y asiste al usuario."""
        browser_exe = find_system_browser()
        if not browser_exe:
            if sys.platform == "darwin":
                messagebox.showwarning(
                    "Google Chrome no detectado",
                    "SURA Citas Bot requiere Google Chrome para interactuar con el portal de citas.\n\n"
                    "No se detectó Chrome en /Applications/Google Chrome.app.\n\n"
                    "Para continuar:\n"
                    "1. Descarga e instala Google Chrome desde:\n"
                    "   https://www.google.com/chrome/\n"
                    "2. Abre Google Chrome al menos una vez.\n"
                    "3. Vuelve a iniciar SURA Citas Bot."
                )
                self.log("⚠️ Atención: No se detectó Google Chrome en las rutas estándar de macOS.", "warning")
            else:
                messagebox.showwarning(
                    "Navegador no detectado",
                    "SURA Citas Bot requiere Google Chrome o Microsoft Edge.\n"
                    "Por favor instala Google Chrome para garantizar el correcto funcionamiento."
                )
                self.log("⚠️ Atención: No se detectó Google Chrome o Microsoft Edge.", "warning")

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding="20 15 20 15")
        main_frame.pack(fill="both", expand=True)

        # 1. ENCABEZADO
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 12))

        title_lbl = tk.Label(
            header_frame, text="⚡ SURA Citas Bot", font=(FONT_FAMILY, 16, "bold"),
            bg=BG_COLOR, fg="#38bdf8"
        )
        title_lbl.pack(side="left")

        self.status_badge = tk.Label(
            header_frame, text="● INACTIVO", font=(FONT_FAMILY, 9, "bold"),
            bg="#2a2f3a", fg="#94a3b8", padx=10, pady=4
        )
        self.status_badge.pack(side="right")

        self.btn_detener_alarma = tk.Button(
            header_frame, text="🔇 Detener Alarma", font=(FONT_FAMILY, 9, "bold"),
            bg="#ef4444", fg="#ffffff", activebackground="#dc2626", activeforeground="#ffffff",
            relief="flat", cursor="hand2", padx=8, pady=3, command=self._silenciar_alarma
        )

        # 2. TARJETA: CREDENCIALES Y PACIENTE
        card_creds = ttk.Frame(main_frame, style="Card.TFrame", padding="14")
        card_creds.pack(fill="x", pady=(0, 10))

        ttk.Label(card_creds, text="Datos de la Cuenta y Paciente", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))

        row1 = ttk.Frame(card_creds, style="Card.TFrame")
        row1.pack(fill="x", pady=(0, 6))

        # Tipo Doc
        col_tipo = ttk.Frame(row1, style="Card.TFrame")
        col_tipo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Label(col_tipo, text="Tipo de Documento:", style="Muted.TLabel").pack(anchor="w")
        self.combo_tipo = ttk.Combobox(col_tipo, values=list(TIPO_DOC_MAP.keys()), state="readonly")
        self.combo_tipo.pack(fill="x", pady=(3, 0))

        # Número Doc
        col_num = ttk.Frame(row1, style="Card.TFrame")
        col_num.pack(side="left", fill="x", expand=True)
        ttk.Label(col_num, text="Número de Cédula:", style="Muted.TLabel").pack(anchor="w")
        self.entry_doc = tk.Entry(
            col_num, bg=INPUT_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            relief="flat", font=(FONT_FAMILY, 10), bd=4
        )
        self.entry_doc.pack(fill="x", pady=(3, 0))

        # Fila 2: Clave y Paciente (Grupo Familiar)
        row2 = ttk.Frame(card_creds, style="Card.TFrame")
        row2.pack(fill="x", pady=(0, 6))

        col_pwd = ttk.Frame(row2, style="Card.TFrame")
        col_pwd.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Label(col_pwd, text="Clave (PIN 4 dígitos):", style="Muted.TLabel").pack(anchor="w")
        
        pwd_box = ttk.Frame(col_pwd, style="Card.TFrame")
        pwd_box.pack(fill="x", pady=(3, 0))
        self.entry_clave = tk.Entry(
            pwd_box, bg=INPUT_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            show="*", relief="flat", font=(FONT_FAMILY, 10), bd=4
        )
        self.entry_clave.pack(side="left", fill="x", expand=True)
        self.btn_show_pwd = tk.Button(
            pwd_box, text="👁", bg=INPUT_BG, fg=TEXT_MUTED, activebackground=BORDER_COLOR,
            relief="flat", command=self._toggle_pwd, width=3, cursor="hand2"
        )
        self.btn_show_pwd.pack(side="right", padx=(4, 0))

        # Paciente
        col_paciente = ttk.Frame(row2, style="Card.TFrame")
        col_paciente.pack(side="left", fill="x", expand=True)
        ttk.Label(col_paciente, text="Paciente (Nombre / Filtro Familiar):", style="Muted.TLabel").pack(anchor="w")
        self.entry_paciente = tk.Entry(
            col_paciente, bg=INPUT_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            relief="flat", font=(FONT_FAMILY, 10), bd=4
        )
        self.entry_paciente.pack(fill="x", pady=(3, 0))

        self.var_recordar = tk.BooleanVar(value=True)
        chk_recordar = ttk.Checkbutton(card_creds, text="Recordar mis datos en este equipo", variable=self.var_recordar)
        chk_recordar.pack(anchor="w", pady=(4, 0))

        # 3. TARJETA: FILTROS DE BÚSQUEDA
        card_filtros = ttk.Frame(main_frame, style="Card.TFrame", padding="14")
        card_filtros.pack(fill="x", pady=(0, 10))

        ttk.Label(card_filtros, text="Criterios para la Cita", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))

        row_filtros = ttk.Frame(card_filtros, style="Card.TFrame")
        row_filtros.pack(fill="x", pady=(0, 8))

        # Día deseado
        col_dia = ttk.Frame(row_filtros, style="Card.TFrame")
        col_dia.pack(side="left", fill="x", expand=True)
        ttk.Label(col_dia, text="Fecha deseada:", style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        self.var_dia = tk.StringVar(value="manana")
        ttk.Radiobutton(col_dia, text="Mañana (Recomendado)", variable=self.var_dia, value="manana").pack(anchor="w", pady=2)
        ttk.Radiobutton(col_dia, text="Mismo día (Hoy)", variable=self.var_dia, value="hoy").pack(anchor="w", pady=2)
        ttk.Radiobutton(col_dia, text="Cualquier fecha disponible", variable=self.var_dia, value="cualquiera").pack(anchor="w", pady=2)

        # Jornada
        col_jornada = ttk.Frame(row_filtros, style="Card.TFrame")
        col_jornada.pack(side="left", fill="x", expand=True)
        ttk.Label(col_jornada, text="Horario preferido:", style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        self.var_jornada = tk.StringVar(value="cualquiera")
        ttk.Radiobutton(col_jornada, text="Cualquiera (Primera libre)", variable=self.var_jornada, value="cualquiera").pack(anchor="w", pady=2)
        ttk.Radiobutton(col_jornada, text="Solo en la mañana (06:00 - 11:59)", variable=self.var_jornada, value="manana").pack(anchor="w", pady=2)
        ttk.Radiobutton(col_jornada, text="Solo en la tarde (12:00 - 18:00)", variable=self.var_jornada, value="tarde").pack(anchor="w", pady=2)

        # Servicio selector
        row_servicio = ttk.Frame(card_filtros, style="Card.TFrame")
        row_servicio.pack(fill="x", pady=(4, 6))
        ttk.Label(row_servicio, text="Tipo de Consulta / Servicio:", style="Muted.TLabel").pack(anchor="w")
        self.combo_servicio = ttk.Combobox(row_servicio, values=SERVICIOS_DISPONIBLES, state="readonly")
        self.combo_servicio.pack(fill="x", pady=(3, 0))

        # Opción silenciosa
        self.var_silencioso = tk.BooleanVar(value=False)
        chk_silencioso = ttk.Checkbutton(card_filtros, text="Modo segundo plano (ocultar ventana del navegador)", variable=self.var_silencioso)
        chk_silencioso.pack(anchor="w", pady=(6, 0))

        # 4. BOTONES DE ACCIÓN
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(0, 10))

        self.btn_iniciar = tk.Button(
            btn_frame, text="▶ INICIAR BÚSQUEDA AUTOMÁTICA", bg=ACCENT_GREEN, fg="#ffffff",
            activebackground=ACCENT_GREEN_HOVER, font=(FONT_FAMILY, 11, "bold"),
            relief="flat", pady=10, cursor="hand2", command=self._start_search
        )
        self.btn_iniciar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_detener = tk.Button(
            btn_frame, text="⏹ DETENER", bg=ACCENT_RED, fg="#ffffff",
            activebackground=ACCENT_RED_HOVER, font=(FONT_FAMILY, 11, "bold"),
            relief="flat", pady=10, cursor="hand2", command=self._stop_search, state="disabled"
        )
        self.btn_detener.pack(side="right", fill="x", expand=False, ipadx=15)

        # 5. CONSOLA DE ESTADO Y REGISTRO EN VIVO
        card_log = ttk.Frame(main_frame, style="Card.TFrame", padding="12")
        card_log.pack(fill="both", expand=True)

        log_header = ttk.Frame(card_log, style="Card.TFrame")
        log_header.pack(fill="x", pady=(0, 6))
        ttk.Label(log_header, text="Registro de Actividad", style="CardTitle.TLabel").pack(side="left")

        btn_clear = tk.Button(
            log_header, text="Limpiar", bg=CARD_BG, fg=TEXT_MUTED, font=(FONT_FAMILY, 8),
            relief="flat", cursor="hand2", command=self._clear_log
        )
        btn_clear.pack(side="right")

        self.txt_log = tk.Text(
            card_log, bg=BG_COLOR, fg=TEXT_COLOR, font=(FONT_MONO, 9),
            relief="flat", bd=5, wrap="word", height=8
        )
        self.txt_log.pack(fill="both", expand=True)

        # Sello y marca de agua oficial (Shion)
        lbl_shion = tk.Label(
            main_frame, text="⚡ Engineered by Shion", font=(FONT_FAMILY, 8),
            bg=BG_COLOR, fg="#475569", cursor="hand2"
        )
        lbl_shion.pack(side="bottom", anchor="e", pady=(4, 0))

        def _easter_egg(e):
            messagebox.showinfo(
                "Autenticidad de Software",
                "SURA Citas Bot - Edición Oficial macOS\n"
                "Desarrollado y firmado por: Shion\n"
                "Estado de integridad: 100% Verificado."
            )
        lbl_shion.bind("<Double-Button-1>", _easter_egg)

        self.txt_log.tag_configure("info", foreground="#93c5fd")
        self.txt_log.tag_configure("success", foreground="#34d399", font=(FONT_MONO, 9, "bold"))
        self.txt_log.tag_configure("warning", foreground="#fbbf24")
        self.txt_log.tag_configure("error", foreground="#f87171", font=(FONT_MONO, 9, "bold"))

        self.log("Bienvenido al Cazador de Citas SURA. Configura tus datos y presiona Iniciar.", "info")

    def _toggle_pwd(self):
        if self.entry_clave.cget("show") == "*":
            self.entry_clave.config(show="")
            self.btn_show_pwd.config(text="🔒")
        else:
            self.entry_clave.config(show="*")
            self.btn_show_pwd.config(text="👁")

    def _clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def log(self, message: str, level: str = "info"):
        """Inserta logs en la interfaz gráfica de forma 100% thread-safe."""
        def append():
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.txt_log.insert(tk.END, f"[{timestamp}] {message}\n", level)
            self.txt_log.see(tk.END)
            # Alerta visible emergente si se agotaron los 3 intentos
            if "tras los 3 intentos permitidos" in message:
                messagebox.showerror(
                    "Credenciales no válidas",
                    "SURA no reconoció tus datos tras 3 intentos.\n\n"
                    "Por favor verifica:\n"
                    "1. Que el Tipo de Documento sea el correcto (CC, TI, etc.).\n"
                    "2. Tu número de cédula.\n"
                    "3. Tu PIN de 4 dígitos para este portal."
                )
        self.after(0, append)

    def _load_saved_values(self):
        tipo_code = self.config.get("tipo_documento", "C")
        label = TIPO_DOC_REVERSE.get(tipo_code, list(TIPO_DOC_MAP.keys())[0])
        self.combo_tipo.set(label)

        self.entry_doc.insert(0, self.config.get("documento", ""))
        self.entry_clave.insert(0, self.config.get("clave", ""))
        self.entry_paciente.insert(0, self.config.get("paciente", "Santiago"))
        
        saved_servicio = self.config.get("servicio", SERVICIOS_DISPONIBLES[0])
        if saved_servicio in SERVICIOS_DISPONIBLES:
            self.combo_servicio.set(saved_servicio)
        else:
            self.combo_servicio.set(SERVICIOS_DISPONIBLES[0])

        self.var_dia.set(self.config.get("dia_deseado", "manana"))
        self.var_jornada.set(self.config.get("jornada", "cualquiera"))
        self.var_recordar.set(self.config.get("recordar", True))
        self.var_silencioso.set(self.config.get("modo_silencioso", False))

    def _save_current_values(self):
        tipo_code = TIPO_DOC_MAP.get(self.combo_tipo.get(), "C")
        self.config["tipo_documento"] = tipo_code
        self.config["documento"] = self.entry_doc.get().strip()
        self.config["clave"] = self.entry_clave.get().strip()
        self.config["paciente"] = self.entry_paciente.get().strip()
        self.config["servicio"] = self.combo_servicio.get()
        self.config["dia_deseado"] = self.var_dia.get()
        self.config["jornada"] = self.var_jornada.get()
        self.config["recordar"] = self.var_recordar.get()
        self.config["modo_silencioso"] = self.var_silencioso.get()
        save_config(self.config)

    def _start_search(self):
        doc = self.entry_doc.get().strip()
        clave = self.entry_clave.get().strip()

        if not doc or not clave:
            messagebox.showwarning("Datos incompletos", "Por favor ingresa tu número de cédula y tu clave de SURA.")
            return

        self._save_current_values()

        self.btn_iniciar.config(state="disabled", bg="#4b5563")
        self.btn_detener.config(state="normal")
        self.status_badge.config(text="● VIGILANDO CITAS", bg="#065f46", fg="#34d399")

        self.engine = SuraCitasEngine(self.config, self.log, on_cita_confirmada=self._on_cita_confirmada)
        self.engine_thread = threading.Thread(target=self._run_async_engine, daemon=True, name="SuraEngineThread")
        self.engine_thread.start()

    def _run_async_engine(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.engine.start())
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self.log(f"Error en ejecución del motor: {err_msg}", "error"))
        finally:
            try:
                loop.close()
            except Exception:
                pass
            self.after(0, self._on_engine_finished)

    def _silenciar_alarma(self):
        stop_alarm()
        self.btn_detener_alarma.pack_forget()
        self.log("Alarma detenida. El navegador continúa abierto para tus acciones.", "info")

    def _on_cita_confirmada(self, cita_info: dict):
        self.after(0, lambda: self._mostrar_ventana_cita(cita_info))

    def _mostrar_ventana_cita(self, cita_info: dict):
        self.status_badge.config(text="● ¡CITA CONSEGUIDA!", bg="#065f46", fg="#34d399")
        self.btn_detener_alarma.pack(side="right", padx=(0, 10))

        popup = tk.Toplevel(self)
        popup.title("🚨 ¡CITA MÉDICA CONFIRMADA! - SURA BOT")
        popup.geometry("640x500")
        popup.minsize(580, 440)
        popup.configure(bg="#0f172a")
        popup.attributes("-topmost", True)

        # Centrar ventana
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - 320
        y = (popup.winfo_screenheight() // 2) - 250
        popup.geometry(f"+{x}+{y}")

        # Cabecera roja de alerta
        header_f = tk.Frame(popup, bg="#dc2626", padx=16, pady=12)
        header_f.pack(fill="x")
        
        lbl_siren = tk.Label(
            header_f, text="🚨 ¡CITA ASIGNADA Y CONFIRMADA AL 100%! 🚨",
            font=(FONT_FAMILY, 13, "bold"), bg="#dc2626", fg="#ffffff"
        )
        lbl_siren.pack()
        
        lbl_sub = tk.Label(
            header_f, text="La alarma de sirena continuará sonando hasta que la detengas.",
            font=(FONT_FAMILY, 9), bg="#dc2626", fg="#fecaca"
        )
        lbl_sub.pack(pady=(2, 0))

        # Tarjeta de detalles
        card = tk.Frame(popup, bg="#1e293b", padx=18, pady=14)
        card.pack(fill="both", expand=True, padx=16, pady=12)

        fecha_val = cita_info.get("fecha", "Confirmada")
        hora_val = cita_info.get("hora", "")
        
        row_dt = tk.Frame(card, bg="#1e293b")
        row_dt.pack(fill="x", pady=(0, 10))
        
        lbl_f = tk.Label(row_dt, text=f"📅 Fecha: {fecha_val}", font=(FONT_FAMILY, 12, "bold"), bg="#1e293b", fg="#38bdf8")
        lbl_f.pack(side="left")
        if hora_val:
            lbl_h = tk.Label(row_dt, text=f"⏰ Hora: {hora_val}", font=(FONT_FAMILY, 12, "bold"), bg="#1e293b", fg="#34d399")
            lbl_h.pack(side="right")

        tk.Label(card, text="Detalle oficial enviado por SURA:", font=(FONT_FAMILY, 10, "bold"), bg="#1e293b", fg="#94a3b8").pack(anchor="w", pady=(0, 4))

        txt_msg = scrolledtext.ScrolledText(
            card, wrap=tk.WORD, height=7, bg="#0f172a", fg="#f1f5f9",
            font=(FONT_FAMILY, 10), relief="flat", bd=4, padx=8, pady=8
        )
        txt_msg.pack(fill="both", expand=True, pady=(0, 10))
        detalle_txt = cita_info.get("detalle", "Cita confirmada exitosamente.")
        txt_msg.insert(tk.END, detalle_txt)
        txt_msg.config(state="disabled")

        lbl_chrome = tk.Label(
            card, text="ℹ️ La ventana del navegador permanece 100% abierta para que tomes acciones o confirmaciones.",
            font=(FONT_FAMILY, 9, "bold"), bg="#1e293b", fg="#38bdf8"
        )
        lbl_chrome.pack(pady=(0, 4))

        def apagar():
            stop_alarm()
            btn_apagar.config(text="✓ ALARMA DETENIDA (Navegador abierto)", bg="#059669", state="disabled")
            self.btn_detener_alarma.pack_forget()
            self.log("Alarma detenida. El navegador continúa abierto para tus acciones.", "info")

        btn_apagar = tk.Button(
            popup, text="🔇 DETENER ALARMA", font=(FONT_FAMILY, 13, "bold"),
            bg="#ef4444", fg="#ffffff", activebackground="#dc2626", activeforeground="#ffffff",
            relief="flat", cursor="hand2", padx=20, pady=10, command=apagar
        )
        btn_apagar.pack(fill="x", padx=16, pady=(0, 14))

        def on_popup_close():
            stop_alarm()
            self.btn_detener_alarma.pack_forget()
            self.log("Alarma detenida. El navegador continúa abierto para tus acciones.", "info")
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_popup_close)

    def _on_engine_finished(self):
        """Actualiza el estado de los controles al finalizar el motor (thread-safe)."""
        self.btn_iniciar.config(state="normal", bg=ACCENT_GREEN)
        self.btn_detener.config(state="disabled")
        if self.engine and getattr(self.engine, "cita_exitosa", False):
            self.status_badge.config(text="● ¡CITA CONSEGUIDA!", bg="#065f46", fg="#34d399")
        else:
            self.status_badge.config(text="● DETENIDO", bg="#2a2f3a", fg="#94a3b8")

    def _stop_search(self):
        if is_alarm_active():
            stop_alarm()
            self.log("Alarma detenida. El navegador continúa abierto para tus acciones.", "info")
        else:
            stop_alarm()
        self.btn_detener_alarma.pack_forget()
        if self.engine:
            if getattr(self.engine, "cita_exitosa", False):
                self.log("La búsqueda ya finalizó exitosamente. El navegador permanece 100% abierto para tus acciones.", "info")
                self.btn_detener.config(state="disabled")
            else:
                self.status_badge.config(text="● DETENIENDO...", bg="#991b1b", fg="#fca5a5")
                self.engine.stop()
                self.btn_detener.config(state="disabled")

    def _on_close(self):
        stop_alarm()
        if self.engine:
            self.engine.stop()
        self._save_current_values()
        self.destroy()

if __name__ == "__main__":
    app = SuraCitasApp()
    app.mainloop()
