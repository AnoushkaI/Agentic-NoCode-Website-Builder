# SitePilot AI — Agentic No-Code Website Builder

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![Pydantic v2](https://img.shields.io/badge/schema-Pydantic%20v2-red.svg)](https://docs.pydantic.dev/)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](https://pytest.org/)

SitePilot AI is a lightweight, explainable AI-powered no-code website builder. A user describes a business or idea in natural language (e.g., *"Create a modern landing page for a fitness studio with pricing, testimonials, and a contact form"*); the application turns that request into a working, editable website rendered from a predefined component library.

Users can preview the generated website and apply conversational follow-up edits (e.g., *"Change the hero CTA to Book a Trial"* or *"Make the hero darker"*) via **structured in-place patches** without full regeneration.

---

## 🏛️ System Architecture

```text
USER
 │
 ▼
STREAMLIT UI (prompt + chat + live preview + status/errors)
 │
 ├── Initial Brief ──────────────────────────────────────┐
 │                                                       ▼
 │                                             PLANNER (LLM Call)
 │                                             Extracts business type, style, sections
 │                                                       │
 │                                                       ▼
 │                                             WEBSITE GENERATOR (LLM Call)
 │                                             Produces structured WebsiteState JSON
 │                                                       │
 │                                                       ▼
 │                                             PYDANTIC SCHEMA VALIDATION
 │                                             (Valid? No -> One repair retry -> Validate again)
 │                                                       │ Yes
 │                                                       ▼
 │                                             WEBSITE STATE MANAGER
 │                                             Tracks current JSON, version, and edit history
 │                                                       │
 │                                                       ▼
 │                                             HTML/CSS RENDERER ──────────┐
 │                                                                         ▼
 ├── Follow-up Conversational Edit ──────────────────────┐        LIVE WEBSITE PREVIEW
 │                                                       ▼
 │                                             EDIT AGENT (LLM Call)
 │                                             Instruction + current JSON + operation schema
 │                                                       │
 │                                                       ▼
 │                                             STRUCTURED PATCH PROPOSAL
 │                                             (Update / Add / Remove / Reorder)
 │                                                       │
 │                                                       ▼
 │                                             DETERMINISTIC PATCH ENGINE (Python)
 │                                             Never executes model-generated code
 │                                                       │
 │                                                       ▼
 │                                             PYDANTIC VALIDATION
 │                                             (Valid? No -> Reject; preserve last valid state)
 │                                                       │ Yes
 └─────────────────────────────────────────────► SAVE NEW STATE + INCREMENT VERSION
                                               Re-renders preview automatically
```

---

## 🚀 Supported Model Providers

SitePilot AI features a unified OpenAI-compatible client adapter that allows switching seamlessly between cloud and local providers without code changes:

| Provider | Role | Recommended / Default Model | Base URL |
| :--- | :--- | :--- | :--- |
| **NVIDIA NIM** *(Default)* | Primary Prototype | `nvidia/nemotron-3.5-bolt-e4b` | `https://integrate.api.nvidia.com/v1` |
| **Ollama** | Local Backup | `qwen2.5:3b` | `http://localhost:11434/v1` |
| **OpenAI** | Benchmarks / Docs | `gpt-4o-mini` | `https://api.openai.com/v1` |

---

## 🛠️ Quickstart & Setup

### 1. Clone & Set Up Environment

```powershell
# Clone repository
git clone https://github.com/your-username/Agentic-NoCode-Website-Builder.git
cd Agentic-NoCode-Website-Builder

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate   # On Windows
# source venv/bin/activate # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials (`.env`)

Copy `.env.example` to `.env`:

```powershell
copy .env.example .env
```

Edit `.env` for your chosen provider:

#### Option A: NVIDIA NIM (Primary Prototype Choice)
```ini
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-nvidia-api-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=nvidia/nemotron-3.5-bolt-e4b
```
*(Get your free API key at [NVIDIA Build](https://build.nvidia.com/))*

#### Option B: Ollama (Local Backup with Qwen 2.5 3B)
```ini
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b
```
Make sure Ollama is running and the model is pulled:
```powershell
ollama pull qwen2.5:3b
ollama serve
```

#### Option C: OpenAI (Standard API Option)
```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

---

## 🧪 Running Tests

The test suite validates provider resolution, configuration parsing, API key masking, missing credentials detection, and graceful error handling:

```powershell
python -m pytest -v
```

---

## 🖥️ Launching the Streamlit Application

```powershell
streamlit run app.py
```

The application opens at `http://localhost:8501`. In Phase 1, you can:
- Inspect active provider settings and credentials safely (masked).
- Switch providers dynamically via the sidebar.
- Click **"🔌 Test Provider Connection"** to measure roundtrip latency and verify connectivity.

---

## 📂 Project Structure

```text
Agentic-NoCode-Website-Builder/
├── app.py                     # Streamlit application entrypoint
├── requirements.txt           # Project dependencies
├── .env.example               # Template for environment variables
├── .gitignore                 # Secrets and temporary file exclusions
├── README.md                  # Project documentation & setup instructions
├── PROJECT_PROGRESS.md        # Phase tracking, test results, and roadmap
├── src/
│   ├── __init__.py
│   ├── config.py              # Environment configuration & provider settings
│   └── providers/             # LLM provider adapter architecture
│       ├── __init__.py
│       ├── base.py            # Abstract BaseProvider, test & response models
│       ├── openai_compatible.py # Unified client for NVIDIA NIM, Ollama, OpenAI
│       └── factory.py         # Provider instantiation & health checks
└── tests/
    ├── __init__.py
    └── test_provider.py       # Unit and diagnostic tests for providers
```
