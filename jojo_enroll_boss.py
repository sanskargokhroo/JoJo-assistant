import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import sounddevice as sd
import scipy.signal as signal

AUDIO_DEVICE_ID = 1     # Realtek Microphone Array
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
RECORD_SECONDS = 3.5
SAVE_PATH = "boss_voice_profile.npy"

# Calibrated physical frequency grid in Hertz (covering human vocal pitch & formant bands)
TARGET_FREQ_GRID = np.arange(30) * (44100.0 / 1024.0)

def extract_features(mono_audio, sr=AUDIO_SAMPLE_RATE):
    audio = mono_audio.astype(np.float32)
    if np.max(np.abs(audio)) > 0:
        audio = audio / np.max(np.abs(audio))
    
    nperseg = min(1024, len(audio))
    freqs, psd = signal.welch(audio, sr, nperseg=nperseg)
    psd_interp = np.interp(TARGET_FREQ_GRID, freqs, psd)
    psd_norm = psd_interp / (np.linalg.norm(psd_interp) + 1e-10)
    sc = (np.sum(freqs * psd) / (np.sum(psd) + 1e-10)) / 4000.0
    pf = freqs[np.argmax(psd)] / 2000.0
    feat = np.hstack(([sc, pf], psd_norm))
    return feat / (np.linalg.norm(feat) + 1e-10)

if __name__ == "__main__":
    print("==========================================")
    print("📢 BOSS VOICE ENROLLMENT SYSTEM (16kHz Calibrated)")
    print("==========================================")
    input("Jab bolne ke liye ready hon, Enter dabayein (3.5 seconds)...")
    
    print("🎤 Recording shuru... Boliye: 'JoJo main tumhara boss hoon'")
    recording = sd.rec(
        int(RECORD_SECONDS * AUDIO_SAMPLE_RATE),
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype='int16',
        device=AUDIO_DEVICE_ID
    )
    sd.wait()
    print("✅ Recording complete!")
    
    mono_audio = recording.flatten().astype(np.int16)
    profile = extract_features(mono_audio, AUDIO_SAMPLE_RATE)
    np.save(SAVE_PATH, profile)
    
    print(f"🎯 Boss Voice Frequency Profile locked and saved: '{SAVE_PATH}'")