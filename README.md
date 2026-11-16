# O.M.E.N. (formerly J.A.R.V.I.S.) — Tactical AI Desktop Assistant

A modular, native Windows desktop application built with **Python**, **PySide6**, and **SQLite**, designed with a futuristic cybernetic HUD interface (deep space navy, obsidian black, glowing cyan, and blue accents).

---

## ⚡ Current Implementation: AI Engine + App Discovery + HUD + Skill Forge + Voice + Media

O.M.E.N. includes tightly integrated subsystems:

### 1. Universal AI Task & Conversation Engine
- **Configurable AI Providers**: Supports Google Gemini (with Google Search Grounding), OpenAI / Compatible (Groq, DeepSeek, OpenRouter), local Ollama (`localhost:11434`), and a built-in offline Local NLU engine.
- **Natural Language Understanding**: Understands queries and commands regardless of phrasing (e.g. *"Can you open my code editor?"*, *"In Spotify please play Element"*, *"Explain this Python TypeError"*, *"What is recursion?"*).
- **Multi-Step Execution**: Recognizes and executes composite requests in sequence (e.g. *"Open VS Code and check my system health"*).
- **Secure Credentials**: Configure API keys via environment variables (`GEMINI_API_KEY`, `OPENAI_API_KEY`) or in-app directives (`set key gemini <api_key>`). Keys are kept out of source code.
- **Structured Tool Registry**: Approved tools callable by AI models with strict schema validation (`launch_application`, `open_folder`, `open_website`, `search_web`, `system_diagnostics`, `list_applications`, `list_skills`, `run_skill`, `test_skill`, `create_skill`, `play_music`, `control_media`, `set_timer`, `list_timers`, `windows_automation`, `find_files`, `analyze_screen`).

### 2. Music & Media Playback Control
- **Direct Spotify Search & Play**: Launches Spotify directly to tracks, artists, or playlists with automatic browser fallback.
- **Global Media Controls**: Vocal directives for play/pause, next track, previous track, volume up/down, and mute.

### 3. Screen Vision & Multimodal Inspection
- **Look at My Screen**: On-demand display capture submitted to Gemini 2.5 Flash Multimodal Vision to analyze visible windows, error tracebacks, or code.

### 4. Smart Timers & Desktop Automations
- **Background Timers & Reminders**: Scheduled reminders in SQLite with Windows notification banners and spoken voice alerts.
- **Workstation Controls**: Safe lock workstation (`LockWorkStation`), show desktop, and safe user file search.

### 5. Windows General Application Discovery
- **Start Menu & Registry Discovery**: Automatically scans and indexes hundreds of installed applications across Windows Start Menu, `App Paths`, and Registry `Uninstall` entries.
- **Protocol Schemes**: Supports direct URI protocols (`spotify:`, `discord:`, `steam:`, `calc:`, `ms-settings:`).
- **Category Aliases**: Maps conversational terms (e.g. "code editor" -> VS Code, "music" -> Spotify, "browser" -> Chrome/Edge).
- **Missing App Handling**: Clearly explains when an application is not installed and offers to open its official service online.

### 6. Voice Interaction & Wake-Word Engine
- **Hands-Free Wake-Word**: Background listening daemon responding to `"Hey Omen"` (or legacy `"Hey Jarvis"`) to restore and foreground the window.
- **HUD Microphone & Push-to-Talk (PTT)**: Interactive microphone toggle on HUD and `Ctrl+Space` push-to-talk hotkey.
- **Text-to-Speech (TTS)**: Non-blocking Windows SAPI5 synthesizer vocalizes assistant replies with markdown sanitization and instant `Escape` silence control.

### 7. Directives HUD & Safe Application Launcher
- **Cybernetic Interface**: Real-time glowing status badge (`ONLINE`, `READY`, `THINKING`, `EXECUTING`, `SPEAKING`, `ERROR`), conversation log, and one-click directives.
- **Strict Security Sandbox**: Zero arbitrary shell injection. Dangerous metacharacters (`&&`, `||`, `;`, `rmdir`, `del`, `powershell`) are strictly blocked.
- **Hardware Telemetry**: Real-time diagnostic reporting for CPU, memory, disk, uptime, and OS details via `psutil`.

### 8. Skill Forge (Automated Multi-Step Workflow Engine)
- **Workflow Workshop Interface**: Dedicated split-view panel for creating, testing, reordering, and executing multi-step workflows.
- **Dry-Run (Test Preview)**: Simulates workflows safely without real-world side effects.
- **Persistence**: Workflows, steps, and execution histories persist in SQLite (`data/jarvis.db`).


---

## 📁 Project Architecture

```
jarvius/
├── .venv/                      # Python virtual environment
├── data/
│   └── jarvis.db               # SQLite database for apps, skills, steps, and history
├── jarvis/
│   ├── __init__.py             # Package metadata
│   ├── config.py               # Constants, theme colors, and database paths
│   ├── main.py                 # Application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite connection and application registry
│   │   ├── launcher.py         # Application path resolution and safe launch
│   │   ├── system_info.py      # System diagnostic metrics collector
│   │   └── command_processor.py # Whitelist-based command processor and safety engine
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic data models for skills, steps, and results
│   │   ├── action_registry.py  # Approved action definitions and argument validation
│   │   ├── storage.py          # SQLite persistence for skills and execution records
│   │   └── engine.py           # Ordered execution engine with dry-run and cancellation
│   └── ui/
│       ├── __init__.py
│       ├── styles.py           # Futuristic cyber QSS stylesheet
│       ├── main_window.py      # Main window with HUD and Skill Forge navigation
│       ├── widgets/
│       │   ├── __init__.py
│       │   ├── console_view.py     # Conversation and diagnostics viewer
│       │   ├── shortcut_bar.py     # Quick launch buttons
│       │   └── status_indicator.py # Glowing status badge
│       └── skills/
│           ├── __init__.py
│           ├── skill_dialog.py     # Modal dialog for creating/editing skills
│           ├── step_dialog.py      # Modal dialog with dynamic parameter forms
│           └── skill_forge_view.py # Full workflow builder and manager view
├── tests/
│   ├── __init__.py
│   ├── test_command_processor.py # Command routing and security tests
│   ├── test_database.py        # SQLite database tests
│   ├── test_launcher.py        # Application launcher and path resolution tests
│   ├── test_skills.py          # Skill Forge validation, persistence, and execution tests
│   ├── test_system_info.py     # System telemetry tests
│   └── test_ui.py              # PySide6 GUI component and view switching tests
├── requirements.txt            # Project dependencies
└── README.md                   # Documentation
```

---

## 🛠️ Setup & Running JARVIS

### 1. Requirements
- **Windows 10 or 11**
- **Python 3.11+**

### 2. Virtual Environment Setup
```powershell
# Create virtual environment inside project
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
# (or in cmd.exe: .\.venv\Scripts\activate.bat)

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch JARVIS Automatically

You can launch JARVIS in any of the following ways:

- **Desktop Shortcut**: Double-click the **`J.A.R.V.I.S.`** shortcut on your Windows Desktop.
- **One-Click Script**: Double-click **`run_jarvis.bat`** in the project directory.
- **PowerShell / Terminal**:
  ```powershell
  .\.venv\Scripts\python.exe -m jarvis.main
  ```

---

## 🎮 How to Use Skill Forge

### From the Graphical Interface
1. Launch JARVIS.
2. In the top navigation bar, click **`⚡ SKILL FORGE`** (or click the **`⚡ Skill Forge`** button in the quick directives bar).
3. **Select a Skill** from the left list (pre-seeded with *"Start Coding Session"* and *"System Health Check"*).
4. Click **`🔍 DRY RUN (TEST)`** to preview every step without executing side effects.
5. Click **`▶ RUN WORKFLOW`** to execute the sequence live with real-time step progress and status feedback.
6. **Create a New Skill**: Click **`+ NEW SKILL`**, enter a name and description, then click **`+ ADD STEP`** to configure actions (Launch App, Open Folder, Diagnostics, Log Message, Wait).
7. Reorder steps anytime using **`▲ MOVE UP`** and **`▼ MOVE DOWN`**.
8. Click **`🛰 HUD DIRECTIVES`** in the header to return to the interactive console.

### From the Typed HUD Console
You can also run and inspect skills directly through typed directives in the HUD console:

| Typed Directive | Action |
|---|---|
| `list skills` / `skills` | Lists all saved skills, their step counts, and enabled status |
| `run skill <name>` | Executes the named workflow live |
| `test skill <name>` | Runs a dry-run preview of the workflow |
| `Open Notepad` | Launches the verified Windows application |
| `Show system information` | Displays live CPU, RAM, Disk, and OS metrics |
| `list apps` | Displays registered desktop applications |
| `help` | Shows all available commands |

---

## 🧪 Running Automated Tests

Execute all 45 automated unit, integration, and UI tests using `pytest`:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
