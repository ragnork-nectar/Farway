"""Debug — see what Google STT hears for 'bye' and similar words."""
import speech_recognition as sr

recognizer = sr.Recognizer()
mic = sr.Microphone()

with mic as source:
    recognizer.adjust_for_ambient_noise(source, duration=1)

print("Say 'bye' 5 times clearly. Watch what gets heard.\n")

for i in range(5):
    try:
        with mic as source:
            print(f"[{i+1}/5] Listening... (say 'bye')")
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=4)
        text = recognizer.recognize_google(audio, language="en-IN").lower()
        print(f"[{i+1}] Heard: '{text}'\n")
    except sr.UnknownValueError:
        print(f"[{i+1}] Could not understand\n")
    except Exception as e:
        print(f"[{i+1}] Error: {e}\n")