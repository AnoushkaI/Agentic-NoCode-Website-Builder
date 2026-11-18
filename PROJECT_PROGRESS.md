# Project Progress — SitePilot AI

## 1. Product Purpose & Scope
SitePilot AI is a lightweight, reliable, and explainable AI-powered no-code website builder. A user submits a business brief in natural language, and the system synthesizes a website based on a predefined component library (hero, text, image, features, testimonials, pricing, CTA, contact). Users can preview the website and apply conversational in-place edits (content changes, style adjustments, adding/removing/reordering sections) without full regeneration.

The system uses structured Pydantic schemas as the contract between AI modules and the frontend renderer, applying deterministic Python patches and bounded repair logic.

---

## 2. Core Architecture Overview
- **UI & State Layer:** Streamlit with session state tracking current JSON, version number, and chronological edit history.
- **Data Contract:** Pydantic `WebsiteState` and `Section` schemas with strict validation.
- **LLM Layer:** Unified OpenAI-compatible provider adapter supporting:
  - **NVIDIA NIM** (Default prototype: `nvidia/nemotron-3.5-bolt-e4b`)
  - **Ollama** (Local backup: `qwen2.5:3b`)
  - **OpenAI** (Baseline option: `gpt-4o-mini`)
- **Patch Engine:** Pure, deterministic Python operations (`update`, `add`, `remove`, `reorder`) executed on a state copy before validation. No arbitrary model-generated code is ever executed.
- **Renderer:** Safe, parameterized HTML/CSS component templates.

---

## 3. Phase Status

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Phase 1** | Project Foundation & Configurable LLM Provider Connection | ✅ **Completed** |
| **Phase 2** | Website Schema, Planner & Initial Website Generation | ⏳ Pending Next Prompt |
| **Phase 3** | Component HTML/CSS Renderer & Live Streamlit Preview | ⏳ Pending |
| **Phase 4** | Conversational Edit Agent & Deterministic Patch Engine | ⏳ Pending |
| **Phase 5** | Website State Management, Version History & Diagnostic Logs | ⏳ Pending |
| **Phase 6** | End-to-End Tests, Failure Analysis & Demo Verification | ⏳ Pending |

---

## 4. Phase 1 Details & Verification

### Completed Tasks:
1. **Repository Foundation:**
   - Initialized `.gitignore` protecting credentials (`.env`), caches, and build artifacts.
   - Initialized `requirements.txt` with `streamlit`, `pydantic`, `openai`, `python-dotenv`, `pytest`, `requests`, `httpx`.
   - Initialized `.env.example` documenting configurations for NVIDIA NIM (Nemotron 3.5 Bolt E4B), Ollama (Qwen 2.5 3B), and OpenAI (`gpt-4o-mini`).
2. **Configuration & Security (`src/config.py`):**
   - Implemented environment variable loading with defaults.
   - Built `LLMConfig` with `is_configured` logic and safe masked API key representation (`nvap...6789`) to prevent accidental secret leakage in logs and UI.
3. **Provider Adapter Architecture (`src/providers/`):**
   - `base.py`: Declared `BaseProvider`, `ProviderTestResult`, and `ProviderResponse`.
   - `openai_compatible.py`: Built unified OpenAI client handler supporting NVIDIA NIM, Ollama, and OpenAI endpoints. Added specific troubleshooting tips for missing credentials, rate limits, timeouts, connection errors, and missing local models.
   - `factory.py`: Provided `get_provider()` and `test_provider_connectivity()` helpers.
4. **Streamlit UI Shell (`app.py`):**
   - Interactive sidebar for inspecting active provider, model, base URL, and masked credentials.
   - Live **"🔌 Test Provider Connection"** button with latency measurement and diagnostic guidance.
   - Two-column layout with placeholders for Brief Input, Conversational Edit, Live Preview, and Architecture Inspector.
5. **Testing Suite (`tests/test_provider.py`):**
   - 10 automated unit and diagnostic tests covering provider resolution, config overrides, key masking, missing credentials detection, unreachable network handling, mocked successful completions, and factory functions.

### Execution & Verification Commands:
- **Unit Tests:**
  ```powershell
  python -m pytest -v
  ```
  *Result:*
  ```text
  ============================= test session starts =============================
  platform win32 -- Python 3.12.6, pytest-9.1.1, pluggy-1.6.0
  collecting ... collected 10 items

  tests/test_provider.py::test_supported_providers_list PASSED             [ 10%]
  tests/test_provider.py::test_default_config_loading PASSED               [ 20%]
  tests/test_provider.py::test_provider_overrides PASSED                   [ 30%]
  tests/test_provider.py::test_masked_api_key_security PASSED              [ 40%]
  tests/test_provider.py::test_missing_credentials_graceful_handling PASSED [ 50%]
  tests/test_provider.py::test_unreachable_endpoint_graceful_handling PASSED [ 60%]
  tests/test_provider.py::test_mocked_successful_connection PASSED         [ 70%]
  tests/test_provider.py::test_mocked_completion_call PASSED               [ 80%]
  tests/test_provider.py::test_factory_get_provider PASSED                 [ 90%]
  tests/test_provider.py::test_convenience_run_provider_connectivity PASSED [100%]

  ============================= 10 passed in 7.61s ==============================
  ```
- **App Module Verification:**
  ```powershell
  python -c "import app; print('App module imported successfully!')"
  ```
  *Result:* `App module imported successfully!` (Exit code 0)

---

## 5. Files Created / Modified in Phase 1
- `requirements.txt` (New)
- `.gitignore` (New)
- `.env.example` (New)
- `README.md` (Updated with complete setup, architecture, and provider documentation)
- `PROJECT_PROGRESS.md` (New)
- `src/__init__.py` (New)
- `src/config.py` (New)
- `src/providers/__init__.py` (New)
- `src/providers/base.py` (New)
- `src/providers/openai_compatible.py` (New)
- `src/providers/factory.py` (New)
- `app.py` (New)
- `tests/__init__.py` (New)
- `tests/test_provider.py` (New)

---

## 6. Known Issues / Limitations
- No API keys are committed or stored in repository files (tested via masked secrets).
- Phase 1 strictly isolates provider connectivity. Website planning, generation, schema, preview, and editing are intentionally deferred to subsequent phases as required by the build plan.

---

## 7. Next Step: Phase 2
- Define Pydantic `WebsiteState` and `Section` schemas with strict validation.
- Implement Planner and Generator functions using the configured LLM provider.
- Implement bounded repair retry logic for schema violations.
- Validate deterministic fallback/demo generation.
