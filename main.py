#!/usr/bin/env python3
import os
import sys
import time
import queue
import threading
import tempfile
from pathlib import Path
import ctypes
from ctypes import wintypes

import sounddevice as sd
import soundfile as sf
import keyboard
import pyperclip

from PIL import Image
import pystray
from pystray import MenuItem as item
from win10toast_click import ToastNotifier  # ✅ Agora permite fechar a anterior

from openai import OpenAI

# ------------------ CONFIG ------------------
HOTKEY = "ctrl+alt+space"
CANCEL_HOTKEY = "ctrl+alt+backspace"
PRINT_DEVICES_KEY = "F10"

INPUT_DEVICE_NAME = None  # ex: "Logi", "G733", "C920e"

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

PRIMARY_STT_MODEL = "gpt-4o-transcribe"
FALLBACK_STT_MODEL = "whisper-1"
# Modelo atual (inicia como GPT-4o Transcribe)
CURRENT_STT_MODEL = PRIMARY_STT_MODEL

ADD_TRAILING_SPACE = True
ADD_TRAILING_NEWLINE = False

MAX_RECORD_SECONDS = 180  # 3 minutos
MUTEX_NAME = "Global\\DictatePasteMutex"
# ------------------------------------------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
toaster = ToastNotifier()

recording_lock = threading.Lock()
is_recording = False
audio_q = queue.Queue()
stream = None
record_start_time = 0
last_toast = None  # ✅ agora controlamos notificações


# ============== SINGLE INSTANCE ==============
def ensure_single_instance():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)


# ============== NOTIFICAÇÃO SEM ACÚMULO ==============
def notify(title, msg):
    global last_toast
    try:
        if last_toast and last_toast.is_alive():
            last_toast.stop()  # ✅ fecha notificação anterior
        last_toast = toaster.show_toast(title, msg, duration=2, threaded=True)
    except:
        pass


# ============== UTILITÁRIOS ==============
def _find_input_device(match):
    if not match:
        return None
    match = match.lower()
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0 and match in d["name"].lower():
            return i
    return None


def print_devices():
    print("\n=== Microfones Disponíveis ===")
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0:
            print(f"[{i}] {d['name']}")
    print("==============================\n")


def audio_callback(indata, frames, time_info, status):
    global is_recording
    audio_q.put(indata.copy())
    if is_recording and (time.time() - record_start_time) >= MAX_RECORD_SECONDS:
        stop_recording(save=True)


# ============== GRAVAÇÃO ==============
def start_recording():
    global is_recording, stream, record_start_time
    with recording_lock:
        if is_recording:
            return

        record_start_time = time.time()
        device_index = _find_input_device(INPUT_DEVICE_NAME)

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=audio_callback,
            device=device_index
        )

        while not audio_q.empty():
            audio_q.get_nowait()

        stream.start()
        is_recording = True
        notify("🎙️ Gravando...", "Pressione novamente para parar.")


def stop_recording(save=True):
    global is_recording, stream
    with recording_lock:
        if not is_recording:
            return

        try:
            stream.stop()
            stream.close()
        except:
            pass

        is_recording = False

    if not save:
        while not audio_q.empty():
            audio_q.get_nowait()
        notify("❌ Cancelado", "Nenhuma transcrição.")
        return

    notify("⏹️ Processando...", "Convertendo fala em texto...")

    frames = []
    while not audio_q.empty():
        frames.append(audio_q.get())

    if not frames:
        notify("⚠️ Nenhum áudio", "Nada foi dito.")
        return

    wav_path = Path(tempfile.gettempdir()) / "dictate.wav"
    with sf.SoundFile(wav_path, mode="w", samplerate=SAMPLE_RATE, channels=CHANNELS, subtype="PCM_16") as f:
        for chunk in frames:
            f.write(chunk)

    text = transcribe_audio(wav_path)
    wav_path.unlink(missing_ok=True)

    if not text:
        notify("⚠️ Falha", "Não foi possível transcrever.")
        return

    if ADD_TRAILING_SPACE:
        text += " "
    if ADD_TRAILING_NEWLINE:
        text += "\n"

    paste(text)
    notify("✅ Inserido", text[:40] + "...")


# ============== TRANSCRIÇÃO + COLA ==============
def paste(text):
    old = pyperclip.paste()
    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    time.sleep(0.05)
    pyperclip.copy(old)


def transcribe_audio(path):
    for model in (CURRENT_STT_MODEL, FALLBACK_STT_MODEL):
        try:
            with open(path, "rb") as f:
                resp = client.audio.transcriptions.create(file=f, model=model)
            return resp.text
        except:
            continue
    return None


def toggle():
    if is_recording:
        stop_recording(True)
    else:
        start_recording()


def cancel():
    if is_recording:
        stop_recording(False)


# ============== TRAY ICON ==============
def tray_thread():
    def use_gpt4_transcribe(_=None):
        global CURRENT_STT_MODEL
        CURRENT_STT_MODEL = "gpt-4o-transcribe"
        notify("Modelo de transcrição", "Usando GPT-4o Transcribe")

    def use_gpt4_mini_transcribe(_=None):
        global CURRENT_STT_MODEL
        CURRENT_STT_MODEL = "gpt-4o-mini-transcribe"
        notify("Modelo de transcrição", "Usando GPT-4o Mini Transcribe")

    def is_gpt4(_item=None):
        return CURRENT_STT_MODEL == "gpt-4o-transcribe"

    def is_gpt4_mini(_item=None):
        return CURRENT_STT_MODEL == "gpt-4o-mini-transcribe"

    icon = pystray.Icon(
        "Dictate",
        Image.open("mic_icon.ico"),
        menu=pystray.Menu(
            item("Usar GPT-4 Transcribe", use_gpt4_transcribe, checked=lambda i: is_gpt4()),
            item("Usar GPT-4 Mini Transcribe", use_gpt4_mini_transcribe, checked=lambda i: is_gpt4_mini()),
            item("Listar microfones", lambda: print_devices()),
            item("Sair", lambda: os._exit(0))
        )
    )
    icon.run()


# ============== MAIN ==============
def main():
    ensure_single_instance()
    if not os.getenv("OPENAI_API_KEY"):
        notify("❗ ERRO", "OPENAI_API_KEY não configurada.")
        sys.exit(1)

    keyboard.add_hotkey(HOTKEY, toggle)
    keyboard.add_hotkey(CANCEL_HOTKEY, cancel)
    keyboard.add_hotkey(PRINT_DEVICES_KEY, print_devices)

    threading.Thread(target=tray_thread, daemon=True).start()
    notify("🎤 Dictate & Paste ativo", "Use Ctrl+Alt+Space para ditar.")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
