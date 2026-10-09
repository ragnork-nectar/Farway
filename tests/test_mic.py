"""Simple mic test."""

import speech_recognition as sr
from faster_whisper import WhisperModel

print("[Test] Loading Whisper tiny.en...")
model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

r = sr.Recognizer()
mic = sr.Microphone()

with mic as source:
    print("[Test] Calibrating ambient noise (2s)... stay quiet.")
    r.adjust_for_ambient_noise(source, duration=2)
    print(f"[Test] Energy threshold: {r.energy_threshold}")

print("")
print("[Test] Speak now... (5 seconds)")
try:
    with mic as source:
        audio = r.listen(source, timeout=5, phrase_time_limit=5)
    print("[Test] Audio captured! Transcribing...")
    with open("test_mic.wav", "wb") as f:
        f.write(audio.get_wav_data())
    segments, info = model.transcribe("test_mic.wav", beam_size=5, language="en")
    text = " ".join(s.text for s in segments).strip()
    print("")
    print(f"[Test] You said: '{text}'")
    if text:
        print("[Test] Mic works!")
    else:
        print("[Test] Audio captured but Whisper ne kuch nahi suna.")
except sr.WaitTimeoutError:
    print("[Test] NO AUDIO CAPTURED.")