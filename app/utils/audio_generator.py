# app/utils/audio_generator.py

import os
import shutil
from gtts import gTTS
from pydub import AudioSegment

from app.models import Medication, Dosage

BASE_AUDIO_DIR = "app/static/audio"

# --------------------------------------------------------
# Create directory
# --------------------------------------------------------
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

# --------------------------------------------------------
# Supported languages for TTS
# --------------------------------------------------------
SUPPORTED_LANGS = {
    "english": "en",
    "en": "en",
    "hindi": "hi",
    "hi": "hi",
    "marathi": "mr",
    "mr": "mr",
    "telugu": "te",
    "te": "te",
    "tamil": "ta",
    "ta": "ta",
    "bengali": "bn",
    "bn": "bn",
    "gujarati": "gu",
    "gu": "gu",
    "kannada": "kn",
    "kn": "kn",
    "malayalam": "ml",
    "ml": "ml",
    "punjabi": "pa",
    "pa": "pa",
    "oriya": "or",
    "odia": "or",
    "or": "or",
    "urdu": "ur",
    "ur": "ur"
}

def normalize(lang):
    lang = lang.lower()
    return SUPPORTED_LANGS.get(lang, "en")

# --------------------------------------------------------
# Convert MP3 → WAV (ESP32 + MAX98357A format)
# --------------------------------------------------------
def mp3_to_wav(mp3_path, wav_path):
    audio = AudioSegment.from_mp3(mp3_path)

    # ESP32 I2S recommended format
    audio = (
        audio.set_sample_width(2)   # 16-bit PCM
             .set_frame_rate(16000) # 16 kHz
             .set_channels(1)       # Mono
    )

    audio.export(wav_path, format="wav")

# --------------------------------------------------------
# Generate WAV file from text
# --------------------------------------------------------
def generate_wav(text, wav_path, lang):
    ensure_dir(os.path.dirname(wav_path))

    temp_mp3 = wav_path.replace(".wav", ".mp3")

    tts = gTTS(text=text, lang=lang)
    tts.save(temp_mp3)

    mp3_to_wav(temp_mp3, wav_path)
    os.remove(temp_mp3)

    return wav_path

# --------------------------------------------------------
# Build spoken sentence for dosage
# --------------------------------------------------------
def build_sentence(m: Medication, d: Dosage):
    parts = [
        f"It is {d.time_range_start.strftime('%I:%M %p')}.",
        f"Take {m.name}."
    ]
    if d.food_status:
        parts.append(f"{d.food_status}.")
    if d.remark:
        parts.append(f"Note: {d.remark}.")

    return " ".join(parts)

# --------------------------------------------------------
# Main generator for full patient audio pack
# --------------------------------------------------------
def generate_patient_audio(patient, lang="en", force_refresh=True):
    lang = normalize(lang)

    base_dir = os.path.join(BASE_AUDIO_DIR, str(patient.id))
    lang_dir = os.path.join(base_dir, lang)

    if force_refresh and os.path.exists(lang_dir):
        shutil.rmtree(lang_dir)

    ensure_dir(lang_dir)

    result = {
        "global": {},
        "medicines": {}
    }

    # === GLOBAL PROMPTS ===
    global_lines = {
        "snooze": "I will remind you again.",
        "dispense_alarm": "Your medicine is ready. Please collect it."
    }

    for key, text in global_lines.items():
        wav_path = os.path.join(lang_dir, f"{key}.wav")

        if not os.path.isfile(wav_path):
            generate_wav(text, wav_path, lang)

        result["global"][key] = f"{lang}/{key}.wav"

    # === MEDICINE-SPECIFIC PROMPTS ===
    meds = Medication.query.filter_by(patient_id=patient.id).all()

    for m in meds:
        folder = os.path.join(lang_dir, f"med_{m.id}")
        ensure_dir(folder)

        dose_map = {}

        dosages = Dosage.query.filter_by(
            medication_id=m.id
        ).order_by(Dosage.time_range_start).all()

        for idx, d in enumerate(dosages, start=1):
            wav_path = os.path.join(folder, f"dosage_{idx}.wav")
            text = build_sentence(m, d)

            if not os.path.isfile(wav_path):
                generate_wav(text, wav_path, lang)

            relative = f"{lang}/med_{m.id}/dosage_{idx}.wav"
            dose_map[f"dosage_{idx}"] = relative

        result["medicines"][m.name] = dose_map

    return result
