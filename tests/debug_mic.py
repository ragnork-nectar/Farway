import speech_recognition as sr
import pyttsx3

engine = pyttsx3.init("sapi5")
voices = engine.getProperty("voices")
for v in voices:
    if "david" in v.name.lower():
        engine.setProperty("voice", v.id)
        break

def speak(text):
    print(f"[Jarvis] {text}")
    engine.say(text)
    engine.runAndWait()

speak("Testing one two three")

recognizer = sr.Recognizer()
mic = sr.Microphone()

with mic as source:
    recognizer.adjust_for_ambient_noise(source, duration=1)

print("\n[Debug] Bol kuch bhi...")
while True:
    try:
        with mic as source:
            print("[Debug] Listening...")
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)
        text = recognizer.recognize_google(audio)
        print(f"[Debug] Heard: '{text}'")
        speak(f"You said: {text}")
    except sr.UnknownValueError:
        print("[Debug] Google ne kuch samjha nahi")
    except sr.RequestError as e:
        print(f"[Debug] Google error: {e}")
    except Exception as e:
        print(f"[Debug] Error: {e}")