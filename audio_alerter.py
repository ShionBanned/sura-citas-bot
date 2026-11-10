# -*- coding: utf-8 -*-
"""
================================================================================
  SURA CITAS BOT - SISTEMA ACÚSTICO DE ALERTA DE ALTA FIDELIDAD
  SOPORTE NATIVO MULTIPLATAFORMA (macOS afplay / Windows winsound)
  ENGINEERED BY: SHION
================================================================================
"""

import os
import sys
import wave
import math
import struct
import tempfile
import threading
import subprocess
from typing import Optional

_alarm_active = False
_lock = threading.Lock()
_wav_path: Optional[str] = None
_mac_process: Optional[subprocess.Popen] = None
_mac_thread: Optional[threading.Thread] = None

def _get_or_create_siren_wav() -> str:
    """
    Genera o recupera un archivo WAV PCM 16-bit de alta fidelidad (44.1 kHz) con sonido de sirena
    de emergencia ("uiuiuiuiuiuiui") diseñado para reproducirse en bucle continuo e ininterrumpido.
    Almacenado de forma segura en tempfile.gettempdir().
    """
    global _wav_path
    if _wav_path and os.path.exists(_wav_path):
        return _wav_path
    
    wav_file = os.path.join(tempfile.gettempdir(), "sura_siren_alarm.wav")
    
    # Reutilizar si ya fue sintetizado y tiene tamaño correcto (> 100 KB)
    if os.path.exists(wav_file) and os.path.getsize(wav_file) > 100000:
        _wav_path = wav_file
        return _wav_path

    sample_rate = 44100
    duration = 2.5  # 2.5 segundos por ciclo
    num_samples = int(sample_rate * duration)
    
    # 3 ciclos completos en 2.5 segundos (1.2 Hz de oscilación tonal 'ui-ui-ui')
    cycles = 3
    mod_freq = cycles / duration
    f_center = 1250.0
    f_dev = 550.0  # Barrido continuo entre 700 Hz y 1800 Hz
    
    phase = 0.0
    data = bytearray()
    
    for i in range(num_samples):
        t = i / sample_rate
        # Frecuencia instantánea modulada senoidalmente
        inst_freq = f_center - f_dev * math.cos(2 * math.pi * mod_freq * t)
        phase += 2 * math.pi * inst_freq / sample_rate
        
        # Mezcla rica de armónicos para un tono de sirena penetrante y estridente
        val = (
            0.68 * math.sin(phase) +
            0.24 * math.sin(2 * phase) +
            0.08 * math.sin(3 * phase)
        )
        # Saturación acústica para presencia de alto volumen
        val = math.tanh(val * 1.5)
        
        # Suavizado de bordes milimétrico para garantizar cero "pops" o "clicks" en el loop
        if i < 120:
            val *= (i / 120.0)
        elif i > num_samples - 120:
            val *= ((num_samples - i) / 120.0)
            
        sample_int = int(val * 31500)
        data.extend(struct.pack('<h', max(-32767, min(32767, sample_int))))
        
    try:
        with wave.open(wav_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(data)
    except Exception as e:
        print(f"[AUDIO] Error generando WAV de alarma: {e}", file=sys.stderr)
        return ""
        
    _wav_path = wav_file
    return _wav_path

def _macos_audio_worker(wav_file: str):
    """Hilo trabajador para reproducción continua en macOS usando la utilidad nativa afplay."""
    global _mac_process
    while _alarm_active:
        try:
            with _lock:
                if not _alarm_active:
                    break
                _mac_process = subprocess.Popen(
                    ["afplay", wav_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            _mac_process.wait()
        except Exception:
            break
        finally:
            with _lock:
                _mac_process = None

def start_alarm():
    """Inicia la alarma sonora continua tipo sirena de emergencia hasta que sea detenida."""
    global _alarm_active, _mac_thread
    with _lock:
        if _alarm_active:
            return
        _alarm_active = True
        
    try:
        wav_file = _get_or_create_siren_wav()
        if not wav_file or not os.path.exists(wav_file):
            print("[AUDIO] No se pudo obtener el archivo WAV de la sirena.", file=sys.stderr)
            return

        if sys.platform == "darwin":
            # Soporte nativo para macOS mediante afplay en hilo en bucle
            _mac_thread = threading.Thread(
                target=_macos_audio_worker,
                args=(wav_file,),
                daemon=True,
                name="SuraAudioMacWorker"
            )
            _mac_thread.start()
        elif sys.platform == "win32":
            # Compatibilidad nativa Windows
            import winsound
            winsound.PlaySound(wav_file, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        else:
            # Fallback en otros entornos POSIX
            try:
                subprocess.Popen(["aplay", wav_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    except Exception as e:
        print(f"[AUDIO] Error iniciando alarma sonora: {e}", file=sys.stderr)

def stop_alarm() -> bool:
    """
    Detiene la alarma sonora inmediatamente de forma limpia y segura según el sistema operativo.
    Retorna True si la alarma estaba activa.
    """
    global _alarm_active, _mac_process
    was_active = False
    with _lock:
        was_active = _alarm_active
        _alarm_active = False
        
        # En macOS: terminar proceso afplay si existe
        if _mac_process is not None:
            try:
                _mac_process.terminate()
                try:
                    _mac_process.wait(timeout=0.2)
                except Exception:
                    _mac_process.kill()
            except Exception:
                pass
            _mac_process = None

    # En Windows: purgar audio winsound
    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
            
    return was_active

def is_alarm_active() -> bool:
    """Indica si la sirena está sonando actualmente."""
    return _alarm_active

def trigger_alert_sound():
    """Compatibilidad: inicia la alarma continua en bucle."""
    start_alarm()
