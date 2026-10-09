<div align="center">

<img src="https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Windows-10%2F11-0078D6?style=for-the-badge&logo=windows&logoColor=white" />
<img src="https://img.shields.io/badge/AI-Gemini%20%7C%20Ollama-4285F4?style=for-the-badge&logo=google&logoColor=white" />
<img src="https://img.shields.io/badge/Offline-Yes-success?style=for-the-badge" />
<img src="https://img.shields.io/badge/Privacy-100%25-brightgreen?style=for-the-badge" />

<br><br>

<h1>⚡ Sunday &nbsp;+&nbsp; Farway ⚡</h1>
<h3><i>Two voices. One PC. Zero cloud dependency (optional).</i></h3>

<b>An Iron Man style HUD, voice control, memory, code generation, and full PC automation — built from scratch, for the love of it.</b>

<br>
╔══════════════════════════════════════════════════╗
║ ███████╗██╗ ██╗███╗ ██╗██████╗ █████╗ ██╗ ║
║ ██╔════╝██║ ██║████╗ ██║██╔══██╗██╔══██╗██║ ║
║ ███████╗██║ ██║██╔██╗ ██║██║ ██║███████║██║ ║
║ ╚════██║██║ ██║██║╚██╗██║██║ ██║██╔══██║██║ ║
║ ███████║╚██████╔╝██║ ╚████║██████╔╝██║ ██║██║ ║
║ ╚══════╝ ╚═════╝ ╚═╝ ╚═══╝╚═════╝ ╚═╝ ╚═╝╚═╝ ║
╚══════════════════════════════════════════════════╝

text

**Made with ❤️ by [Ragnork Nectar](https://github.com/)**

</div>

---

## 🌟 What is this?

This repo contains **two AI voice assistants** that live on your Windows PC:

### 🎨 **Sunday** — The Online Powerhouse
Smart, fast, and *irreverent*. Powered by Google Gemini. Controls your entire PC, remembers you, writes code, and glows with an Iron Man HUD.

### 🔒 **Farway** — The Offline Guardian
100% offline. Runs on Ollama. No internet, no API keys, no data leak. Just you and your local model.

**Use both. Or use one. But once you use them — you won't go back.**

---

## ✨ Features — The Full Aura

<table>
<tr>
<td width="50%">

### 🎨 **Iron Man HUD**
- Golden arc reactor overlay
- Always-on-top, click-through
- 4 live states: idle, listening, thinking, speaking
- Runs in separate process (no crashes)
- Bottom-right corner, always glowing

### 🧠 **Persistent Memory**
- Remembers your name
- Remembers your projects
- Remembers your preferences
- Personalized greetings — *"Yes Ragnork, I'm listening"*
- Auto-detects: *"Mera naam X hai"* → saved

### 🗣️ **Voice Control**
- Female voice (Zira, Heera, Hazel)
- Wake word: *"Wake up Sunday"*
- Dual mode: Sleep + Command
- Interrupt anytime: *"Stop Sunday"*

</td>
<td width="50%">

### 💻 **Code Generator**
- *"Make a Python calculator"* → writes 83 lines
- *"Make a portfolio website"* → HTML + CSS
- *"Fix the bug in test.py"* → auto-debug
- *"Improve the code"* → refactor
- Supports: Python, HTML, CSS, JS

### 🖥️ **Full PC Control**
- 🔊 Volume (up/down/mute/set)
- 📂 100+ apps (open/close)
- ⏯️ Media (play/pause/next/prev)
- 🔒 System (lock/shutdown/restart/sleep/screenshot)
- 📝 File manager (create/read/write/delete)
- 🎵 Music (no links needed — pywhatkit)
- 🌐 Websites (Google, YouTube, GitHub, etc.)

### 🔑 **Smart API Rotation**
- Multiple Gemini keys
- Auto-switches on quota exhaustion
- Zero downtime
- Multi-model fallback

</td>
</tr>
</table>

---

## 🎬 Demo — The Aura
You: "Wake up Sunday"
Sunday: "Yes Ragnork, I'm listening" ← knows your name

You: "Who is Elon Musk"
Sunday: "Let me think" ← HUD goes THINKING
Sunday: "Elon Musk is the CEO of Tesla and SpaceX, known for..."
← HUD goes SPEAKING

You: "Make a Python calculator"
Sunday: "Let me write that code for you"
Sunday: "Done. I wrote 83 lines of code in calculator.py"
← VS Code opens automatically

You: "Play arzu"
Sunday: "Playing arzu" ← YouTube autoplays

You: "Volume up"
Sunday: "Volume up to 30 percent"

You: "Bye Sunday"
Sunday: "Okay, going back to sleep" ← HUD dims to idle

text

**Every action reflects on the HUD. Live. Reactive. Beautiful.**

---

## 🚀 Quick Start

### Prerequisites

- **Windows 10 or 11**
- **Python 3.12** — [Download](https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe)
- **Microphone** (built-in or external)
- **Speakers / Headphones**
- **Internet** (for Sunday — Gemini AI)
- **Ollama** (optional — for Farway offline mode)

> ⚠️ **Important:** Python 3.12 specifically. Newer versions (3.13+) break `pycaw`, `pyaudio`, and other dependencies.

### Installation

#### **Step 1 — Clone the repo**

```bash
git clone https://github.com/YOUR_USERNAME/Farway-and-Sunday.git
cd Farway-and-Sunday
Step 2 — Create virtual environment
bash
py -3.12 -m venv .venv
.venv\Scripts\activate
Step 3 — Install dependencies
bash
pip install -r requirements.txt
Step 4 — Get your free Gemini API key(s)
Visit aistudio.google.com/app/apikey

Sign in with Google

Click "Create API Key"

Copy the key (starts with AIza...)

Optional but recommended: Create multiple keys from multiple Google accounts to multiply your daily quota.

Step 5 — Create .env file
In the project root, create a file named .env (no extension):

env
# Primary key
GEMINI_API_KEY=AIzaSy...your_key_here

# Optional: multiple keys for rotation
GEMINI_API_KEY_1=AIzaSy...key1
GEMINI_API_KEY_2=AIzaSy...key2
GEMINI_API_KEY_3=AIzaSy...key3
🔒 NEVER share this file. NEVER commit it to GitHub.

Step 6 — Run Sunday
bash
python sunday.py
You'll hear: "Sunday is ready. Say wake up Sunday to activate me."

And the HUD will glow in your bottom-right corner. 🎨

📖 Full Command Reference
🎤 Mode Commands
Command	Action
"Wake up Sunday" / "Hey Sunday"	Activate command mode
"Bye Sunday" / "Bye bye"	Go back to sleep mode
"Goodbye" / "Quit"	Exit completely
"Stop Sunday" / "Chup"	Interrupt ongoing speech
🧠 Memory Commands
Command	Action
"Mera naam X hai"	Saves name
"I like X"	Saves preference
"I am writing X"	Saves project
"What is my name"	Recalls name
"What do you know about me"	Shows full profile
"Remember X"	Saves arbitrary fact
"Forget X"	Deletes X from memory
💻 Code Commands
Command	Action
"Make a Python calculator"	Generates code
"Create a portfolio website"	HTML + CSS
"Fix the bug in test.py"	Debugs file
"Improve the code in app.py"	Refactors
"Run the code test.py"	Executes
🖥️ System Commands
Command	Action
"Volume up" / "Volume down"	Adjusts volume
"Mute" / "Unmute"	Toggles mute
"Volume 50"	Sets to 50%
"Open Chrome" / "Open Spotify"	Launches app
"Close Chrome"	Closes app
"Screenshot"	Takes screenshot
"Lock screen"	Locks PC
"Shutdown in 60"	Delayed shutdown
"Cancel shutdown"	Cancels
"Sleep PC"	Puts PC to sleep
"Play arzu"	Plays on YouTube
"Next song" / "Pause"	Media control
"Open YouTube"	Opens website
"What is the time"	Says time
"What is [anything]"	AI answers
100+ commands. Full reference in docs/COMMANDS.md

🏗️ Architecture
text
┌─────────────────────────────────────────────────────────────┐
│                    SUNDAY (Online Mode)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   🎤 Mic ──► Google STT ──► Command Router                 │
│                                  │                          │
│              ┌───────────────────┼───────────────────┐      │
│              ▼                   ▼                   ▼      │
│         Offline Commands    Memory System        AI Brain   │
│         (volume/apps/etc)   (JSON files)         (Gemini)   │
│                                  │                   │      │
│                                  └───────┬───────────┘      │
│                                          ▼                  │
│                                      Voice Output           │
│                                      (Zira SAPI)            │
│                                          │                  │
│                                          ▼                  │
│                    🎨 HUD ◄────── state file ◄──── IPC      │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    FARWAY (Offline Mode)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   🎤 Mic ──► Whisper ──► Ollama (qwen2.5:1.5b) ──► Voice   │
│                                                             │
│   • 100% offline                                            │
│   • Zero API keys                                           │
│   • Zero data leak                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
📂 Project Structure
text
Farway-and-Sunday/
├── sunday.py              ← Main online assistant
├── farway_simple.py       ← Offline assistant
├── hud.py                 ← Iron Man HUD
├── hud_controller.py      ← HUD process manager
├── memory_manager.py      ← Persistent memory
├── voice_setup.py         ← Voice selector
├── config.py              ← Config manager
├── requirements.txt       ← Dependencies
├── .env                   ← API keys (DO NOT SHARE)
├── .gitignore
├── README.md
│
├── user_files/            ← User data (gitignored)
│   ├── memory/            ← Profile, facts, history
│   │   ├── user_profile.json
│   │   ├── facts.json
│   │   └── conversation_history.json
│   └── code/              ← AI-generated code
│       └── (auto-created)
│
├── temp/                  ← Temporary files
│   ├── hud_state.txt
│   └── (WAV files)
│
├── tests/                 ← Debug and test scripts
│   ├── test_mic.py
│   ├── test_voice.py
│   └── debug_bye.py
│
└── modules/               ← Helper modules
    ├── wake_listener.py
    └── voice_setup.py
🛠️ Troubleshooting
❌ "Python not found" or py -3.12 fails
Reinstall Python 3.12 with "Add to PATH" checked.

❌ pip install pyaudio fails
Fixed by design — we use sounddevice + pywin32 instead.

❌ HUD doesn't show up
bash
# Test HUD alone:
python hud.py

# Delete stale state file:
del temp\hud_state.txt
❌ Volume control not working
bash
pip install --upgrade pycaw comtypes
❌ Gemini error 404
Update model in _call_gemini:

python
models_to_try = ["gemini-flash-latest", "gemini-3.8-flash"]
❌ All API keys exhausted
Wait 24 hours for daily reset, or add more keys to .env.

❌ Voice not heard
Windows Settings → Privacy → Microphone → ON

Check default audio output device

🔒 Privacy & Security
Concern	Status
API keys	Local only (.env, gitignored)
User data	Local JSON files (gitignored)
Voice data	Google STT (online mode only)
AI queries	Gemini (online mode only)
Farway	100% offline — zero external calls
HUD	Local rendering — zero telemetry
Sunday: Google sees your voice + AI queries.
Farway: Nobody sees anything. Ever.

🚀 Roadmap
☑ Voice control (Zira TTS)
☑ Wake word + dual mode
☑ Volume / Apps / Media / System control
☑ Music via pywhatkit
☑ File manager
☑ Code generator
☑ Multi-key Gemini rotation
☑ Persistent memory
☑ Iron Man HUD
□ Whisper offline STT
□ Novel writer mode
□ Screenshot AI analysis
□ Reminders + Notes + Todos
□ Study mode (Pomodoro)
□ Custom wake word
□ Multi-language support
□ Games + fun
□ Smart home integration
🧑‍💻 Tech Stack
Component	Tech
Language	Python 3.12
STT	Google Speech Recognition
TTS	Windows SAPI5 (pywin32)
AI Brain	Google Gemini 2.5+
Offline AI	Ollama + qwen2.5:1.5b
HUD	Tkinter + Canvas
Volume	pycaw (Windows Core Audio)
Automation	pyautogui, psutil, subprocess
Config	python-dotenv
🎨 The Philosophy
This project was born from a simple question:

"What if JARVIS was real, and it was mine?"

Not a wrapper. Not a paid subscription. Not a data-collecting cloud service.

A real assistant. On my PC. With my rules. Remembering my life.

And after two days of relentless building — from Python version hell to threading bugs to Tkinter Tcl conflicts — it exists.

This is not a product. This is a proof.
Proof that one person, one PC, and one weekend of obsession can create magic.

🤝 Contributing
Found a bug? Have an idea? Want to add a feature?

Fork the repo

Create a feature branch

Test thoroughly

Submit a pull request

All contributions welcome. Let's make this even better. 🚀

📜 License
Personal use. Free to modify, extend, share.

If you build something cool with this — tag me. I want to see.

🙏 Credits
Creator: Ragnork Nectar

Built with:

☕ Lots of coffee

🌙 Two sleepless nights

💡 One endless idea

🔥 Zero shortcuts

Special thanks to:

Google AI Studio (for the Gemini API)

The Python community

The developers of pycaw, pywin32, pywhatkit, pyautogui

Everyone who believed this was possible

<div align="center">
⚡ Sunday + Farway ⚡
One PC. Two voices. Zero compromise.


text
"Wake up Sunday."

And the arc reactor starts glowing.




⭐ Star this repo if it inspired you ⭐


Made with ❤️ and 🔥 by Ragnork Nectar

</div> ```