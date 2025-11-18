# app/utils/device_sync.py

import os
import json
import shutil
from datetime import datetime

from app.models import Medication, Dosage
from gtts import gTTS
from pydub import AudioSegment
from pydub.utils import which

# ---------------------------------------------------------
# Windows Fix: Force pydub to use ffmpeg correctly
# ---------------------------------------------------------
AudioSegment.converter = which("ffmpeg")
AudioSegment.ffprobe = which("ffprobe")

# ---------------------------------------------------------
# BASE AUDIO DIRECTORY
# ---------------------------------------------------------
BASE_AUDIO_DIR = os.path.join("app", "static", "audio")

# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

# =========================================================
# CONFIG JSON
# =========================================================
def build_config_json(user):
    dev = user.devices[0]

    data = {
        "device_code": dev.device_code,
        "language": dev.language or "en",
        "patient": user.name,
        "total_compartments": dev.total_compartments or 8,

        "snooze_minutes": 10,
        "volume": 100,
        "timestamp": datetime.utcnow().isoformat()
    }

    return {"config": data}

# =========================================================
# SCHEDULE JSON
# =========================================================
def build_schedule_json(user):
    meds = Medication.query.filter_by(patient_id=user.id).all()
    schedule_list = []

    for m in meds:
        dose_list = []
        dosages = Dosage.query.filter_by(medication_id=m.id).all()

        for d in dosages:
            dose_list.append({
                "id": d.id,
                "start": d.time_range_start.strftime("%H:%M"),
                "end": d.time_range_end.strftime("%H:%M"),
                "food": d.food_status,
                "remark": d.remark
            })

        schedule_list.append({
            "id": m.id,
            "name": m.name,
            "critical": m.critical,
            "compartment": m.compartment,
            "expiry": m.expiry.strftime("%Y-%m-%d") if m.expiry else None,
            "dosages": dose_list
        })

    payload = {
        "schedule": schedule_list,
        "timestamp": datetime.utcnow().isoformat()
    }

    return {"schedule": payload}

# =========================================================
# LANGUAGE NORMALIZATION
# =========================================================
SUPPORTED_LANGS = {
    "english": "en", "en": "en",
    "hindi": "hi", "hi": "hi",
    "marathi": "mr", "mr": "mr",
    "tamil": "ta", "ta": "ta",
    "telugu": "te", "te": "te",
    "bengali": "bn", "bn": "bn",
    "gujarati": "gu", "gu": "gu",
    "kannada": "kn", "kn": "kn",
    "malayalam": "ml", "ml": "ml",
    "punjabi": "pa", "pa": "pa",
    "urdu": "ur", "ur": "ur",
}

def normalize_lang(l):
    return SUPPORTED_LANGS.get(l.lower(), "en")

# =========================================================
# TTS GENERATOR — NORMALIZED + BOOSTED WAV
# =========================================================
def generate_wav_tts(text, wav_path, lang):
    ensure_dir(os.path.dirname(wav_path))

    temp_mp3 = wav_path.replace(".wav", ".mp3")

    tts = gTTS(text=text, lang=lang)
    tts.save(temp_mp3)

    audio = AudioSegment.from_mp3(temp_mp3)

    # LOUD & CLEAN
    audio = audio.normalize(headroom=0.1)
    audio = audio.apply_gain(+6)

    # ESP32-compatible
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    audio.export(wav_path, format="wav")

    try: os.remove(temp_mp3)
    except: pass

# =========================================================
# SENTENCE BUILDER
# =========================================================
def build_sentence(m, d):
    parts = [
        f"It is {d.time_range_start.strftime('%I:%M %p')}.",
        f"Take {m.name}."
    ]
    if d.food_status:
        parts.append(f"{d.food_status}.")
    if d.remark:
        parts.append(f"Note: {d.remark}.")
    return " ".join(parts)

# =========================================================
# AUDIO MANIFEST
# =========================================================
def build_audio_manifest_cached(user):

    device = user.devices[0]
    lang = normalize_lang(device.language or "en")

    patient_dir = os.path.join(BASE_AUDIO_DIR, str(user.id), lang)

    # Clean old audio
    if os.path.exists(patient_dir):
        shutil.rmtree(patient_dir, ignore_errors=True)
    ensure_dir(patient_dir)

    meds = Medication.query.filter_by(patient_id=user.id).all()

    manifest = {"global": {}, "medicines": {}}

    # ----------------------------------------------------
    # GLOBAL AUDIO
    # ----------------------------------------------------
    global_lines = {
        "snooze": "I will remind you again.",
        "dispense_alarm": "Your medicine is ready. Please collect it.",
        "dustbin_alarm": "Eat your medicine and then put the wrapper in the dustbin."
    }

    for key, text in global_lines.items():
        wav_path = os.path.join(patient_dir, f"{key}.wav")
        generate_wav_tts(text, wav_path, lang)
        manifest["global"][key] = f"audio/{user.id}/{lang}/{key}.wav"

    # ----------------------------------------------------
    # MEDICINE-SPECIFIC AUDIO
    # ----------------------------------------------------
    for m in meds:

        med_folder = os.path.join(patient_dir, f"med_{m.id}")
        ensure_dir(med_folder)

        manifest["medicines"][str(m.id)] = {}

        dosages = Dosage.query.filter_by(medication_id=m.id).all()

        for idx, d in enumerate(dosages, start=1):

            fname = f"dosage_{idx}.wav"
            wav_path = os.path.join(med_folder, fname)

            text = build_sentence(m, d)
            generate_wav_tts(text, wav_path, lang)

            manifest["medicines"][str(m.id)][f"dosage_{idx}"] = \
                f"audio/{user.id}/{lang}/med_{m.id}/{fname}"

    return {
        "audio_files": manifest,
        "timestamp": datetime.utcnow().isoformat()
    }
