import pyttsx3
from pydub import AudioSegment
import os

TEMP_FILE = "temp_speech.wav"
OUTPUT_FILE = "love_you_samdarshi.wav"

# 1. Generate speech using pyttsx3
engine = pyttsx3.init()
engine.setProperty("rate", 150)   # speed
engine.setProperty("volume", 1.0) # max TTS engine volume

print("Generating speech...")
engine.save_to_file("I love you Samdarshi", TEMP_FILE)
engine.runAndWait()

# 2. Load generated WAV with pydub
print("Normalizing audio...")
audio = AudioSegment.from_wav(TEMP_FILE)

# Convert to mono 16-bit PCM 16kHz (what your ESP32 expects)
audio = audio.set_channels(1)
audio = audio.set_sample_width(2)  # 16-bit
audio = audio.set_frame_rate(16000)

# Normalize to 0 dB (max clean volume)
normalized_audio = audio.normalize(headroom=0.1)

# 3. Export final loud WAV
normalized_audio.export(OUTPUT_FILE, format="wav")

# Cleanup temp file
os.remove(TEMP_FILE)

print(f"Done! Created loud WAV: {OUTPUT_FILE}")
