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
- **Renderer:** Safe, parameterized HTML/CSS component templates with hybrid layout variant support.

---

## 3. Phase Status

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Phase 1** | Project Foundation & Configurable LLM Provider Connection | ✅ **Completed** |
| **Phase 2** | Website Schema, Planner & Initial Website Generation | ✅ **Completed** |
| **Phase 3** | Component HTML/CSS Renderer & Live Streamlit Preview | ✅ **Completed** |
| **Bug Fix** | Website Preview Navigation + Professional Website Quality | ✅ **Completed** |
| **Hybrid Strategy** | Hybrid Layout Variant Architecture & Business Diversity | ✅ **Completed** |
| **Generalized Fix** | Generalized Website Generation, Section Completeness & Visual Media | ✅ **Completed** |
| **Phase 4** | Conversational Edit Agent & Deterministic Patch Engine | ⏳ Pending Next Prompt |
| **Phase 5** | Website State Management, Version History & Diagnostic Logs | ⏳ Pending |
| **Phase 6** | End-to-End Tests, Failure Analysis & Demo Verification | ⏳ Pending |

---

## 4. Phase 1 & 2 Summary
- **Phase 1:** Established project foundation, dependency management, `.env.example`, `.gitignore`, secure key masking, and unified LLM provider adapter for NVIDIA NIM, Ollama, and OpenAI.
- **Phase 2:** Defined Pydantic models for `WebsiteState`, `Section`, `ThemeConfig`, `SectionStyle`, and `WebsitePlan`. Implemented `plan_website()` and `generate_website_json()` with bounded 1-step repair logic and fallback generation.

---

## 5. Phase 3 & Hybrid Layout Strategy Summary
- Established component HTML/CSS renderer with safe text escaping, URL sanitization, sticky navbar, and responsive layout variants for Hero (`split`, `centered`, `minimal`), Features (`grid`, `pill_cards`, `list`), Pricing (`cards`, `table`), and Testimonials (`grid`, `spotlight`).
- Verified navigation anchors and smooth-scrolling link execution preventing preview iframe reloads.

---

## 6. Generalized Website Generation & Section Completeness Fix

### Problem Analysis & Root Causes:
1. **Hardcoded Business Mappings:** Earlier prototype used string keyword checks (e.g. `if "pet" in title: CURATED_IMAGES["pet"]`) inside the renderer, creating brittle coupling to specific business types rather than a generalized pipeline.
2. **Section Omission Under-Enforcement:** LLMs could return structurally valid JSON containing only a single hero section even when the brief and plan specified features, pricing, testimonials, and contact.
3. **Missing Image Vulnerabilities:** Lack of descriptive prompt handling in state caused either missing visual elements or risk of broken external links.
4. **UI Transparency:** Fallback templates (offline/mock mode) were not prominently distinguished from live LLM synthesis in the preview UI.

### Architectural Improvements Implemented:
1. **Generic Section Extraction & Completeness Enforcement (`src/planner.py`, `src/generator.py`):**
   - Implemented `extract_sections_generically_from_brief()` to extract all requested sections without business-specific branching.
   - Implemented `validate_section_completeness(state, plan)` in `generator.py`. If any planned section is omitted by the LLM, a bounded 1-step repair prompt is triggered identifying the exact missing sections.
   - If repair still omits required sections, a clean `WebsiteGenerationError` is raised rather than silently returning an incomplete page.
2. **Generic Semantic Image Retrieval & Graceful Visual Placeholders (`src/image_service.py`, `src/renderer.py`):**
   - Created `src/image_service.py` with `retrieve_image_for_description()` that matches semantic visual themes (culinary, food_dining, active_fitness, wellness_spa, animals_care, technology_digital, craft_artisan, medical_health, workspace_business) based on descriptions/prompts.
   - Implemented `render_visual_media()` in `src/renderer.py`.
   - Never invents broken URLs. If an image URL is unavailable or fails to load, gracefully displays an attractive styled `.visual-placeholder-card` with an icon, title, description, and feature tag.
   - All `<img>` tags include `loading="lazy"` and inline `onerror` fallback to seamlessly reveal the visual placeholder without broken image icons.
   - Removed all hardcoded `CURATED_IMAGES` dictionaries and business-specific branching from `src/renderer.py`.
3. **Unified Generic Fallback Website (`src/generator.py`):**
   - Implemented `create_generic_fallback_website(brief, plan)` that builds fully-formed sections with clean sequential IDs (`hero-1`, `features-1`, `pricing-1`, `testimonials-1`, `contact-1`) for any arbitrary business brief.
   - Retained dedicated pet grooming and fitness demo fixtures for benchmark evaluations.
4. **Transparent UI Badging (`app.py`):**
   - Added prominent header indicators directly above the live website preview:
     - When offline or fallback: `⚠️ Offline Mode / Fallback Template Displayed (Reason: {reason})`.
     - When live: `✨ AI-Generated Website via {provider} ({model})` with auto-repair badges.

---

## 7. Execution & Verification Results

### Relevant Test Suites:
- **Generation Suite (18 tests):**
  ```powershell
  python -m pytest tests/test_generation.py -v
  ```
  *Actual Result:* `18 passed in 3.29s`
  - Verified schema validation, version checks, section completeness enforcement, bounded repair retry, generic fallback generation, 3 substantially different briefs generation, and semantic image retrieval.

- **Renderer Suite (26 tests):**
  ```powershell
  python -m pytest tests/test_renderer.py -v
  ```
  *Actual Result:* `26 passed in 3.68s`
  - Verified XSS prevention, URL scheme sanitization, CTA anchor navigation, iframe protection, layout variants for all components, visual placeholder rendering for missing URLs, and `onerror` fallback attributes.

- **Provider Suite (10 tests):**
  ```powershell
  python -m pytest tests/test_provider.py -v
  ```
  *Actual Result:* `10 passed in 7.62s`

- **Combined Test Run (44 generation + renderer tests):**
  ```powershell
  python -m pytest tests/test_generation.py tests/test_renderer.py -v
  ```
  *Actual Result:* `44 passed in 2.82s`

- **Streamlit Application Smoke Check:**
  ```powershell
  python -c "import app; print('App syntax check passed successfully!')"
  ```
  *Actual Result:* `App syntax check passed successfully!`

---

## 8. Files Created / Modified
- `src/image_service.py` (**Created**: Semantic thematic image retrieval based on description keywords; graceful `None` fallback)
- `src/schema.py` (Maintained: `image_description` support in content, layout variants in `SectionStyle`, `WebsitePlan`)
- `src/planner.py` (Updated: Generic section extraction; fallback plan selector with generic default)
- `src/generator.py` (Updated: `validate_section_completeness()`, bounded 1-step repair for missing sections, `create_generic_fallback_website()`, deterministic type count IDs)
- `src/renderer.py` (Updated: `render_visual_media()`, visual placeholder card styles, removed hardcoded business mappings, safe `onerror` handling)
- `app.py` (Updated: Prominent UI badge distinguishing AI-generated vs fallback websites above preview)
- `tests/test_generation.py` (Updated: Added 5 new tests for section completeness repair, generic fallback, 3 different briefs, and image retrieval)
- `tests/test_renderer.py` (Updated: Added 3 new tests for visual placeholders, missing URLs, and onerror attributes)
- `PROJECT_PROGRESS.md` (Updated)

---

## 9. Next Phase: Phase 4
- Implement conversational Edit Agent receiving current `WebsiteState`, user natural language instruction, and allowed operation schema.
- Implement pure, deterministic Python patch engine for:
  - `update`: Content and style property changes (e.g. `content.cta_text`, `style.variant`, `style.layout_variant`).
  - `add`: Insert new section with stable ID at position.
  - `remove`: Remove section by ID.
  - `reorder`: Reorder section by ID to new position.
- Validate resulting mutated state copy with Pydantic; reject invalid patches and preserve current valid state.
- Increment version counter upon successful edits.
