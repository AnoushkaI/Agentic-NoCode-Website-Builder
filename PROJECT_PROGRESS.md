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
| **Design Diversity Fix** | Generation Intelligence, Diverse Layouts & Form Interaction Fix | ✅ **Completed** |
| **Validation & Diagnostics Fix** | Content Normalization, Bounded Repair & Diagnostics Safety | ✅ **Completed** |
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

## 7. Generation Intelligence & Design Diversity Fix

### Problem Analysis & Root Causes:
1. **Schema & Planner Expressiveness Gap:** `ThemeConfig` lacked heading font, background style, and navigation style fields; `WebsitePlan` lacked layout strategy, hero variant, dynamic navigation properties, and business-specific form type/fields. Consequently, every generated website looked like the same cookie-cutter template.
2. **Hardcoded Component Assumptions:** The top navigation bar hardcoded the brand icon (`✨`) and CTA ("Book Appointment"); heading typography had no dedicated font pairings; the contact section hardcoded appointment booking text rather than domain-specific inquiry or demo fields.
3. **CTA / Navigation Target Mismatch:** CTA buttons mapped to generic section IDs rather than centering on the interactive form box, with no visual focus or highlight.
4. **Imagery & Gallery Limitations:** Image service only returned a single URL without support for dedicated hero, background, or multi-item gallery slots.

### Architectural Improvements Implemented:
1. **Schema & Plan Enhancements (`src/schema.py`, `src/planner.py`):**
   - Extended `ThemeConfig` with `heading_font`, `background_style`, `nav_style`, and `accent_color`.
   - Extended `SectionStyle` with `background_image_url`, `has_overlay`, and expanded layout variants (`editorial_showcase`, `storefront`, `centered`, `minimal`, `split`).
   - Extended `WebsitePlan` to prescribe layout strategy, hero variant, nav style/CTA, form type (`demo`, `booking`, `inquiry`, `order`, `contact`), and custom form fields.
2. **Design Diversity & Typography Pairs (`src/renderer.py`):**
   - Embedded Google Fonts (`Playfair Display`, `Outfit`, `Plus Jakarta Sans`, `Inter`).
   - Added dynamic background styles (`warm_ivory`, `editorial_cream`, `tech_dark`, `dark_glow`, `gradient_mesh`).
   - Added navbar styles (`sticky_glass`, `floating_pill`, `clean_minimal`, `centered_brand`).
   - Added hero layout variants: `editorial_showcase` (luxury editorial quote callout), `storefront` (fresh bakery schedule banner), `centered`, `minimal`, and `split`.
   - Added multi-image gallery grid support in `render_image_section()`.
3. **Form & Appointment Interaction Fix (`src/renderer.py`):**
   - Contact form now features `id="appointment-form"` with smooth-scroll centering and `@keyframes formPulseHighlight` animation.
   - Dynamic form types support custom field sets (e.g. Work Email/Cloud for SaaS, Heritage Grains/Pickup for Bakery, Budget/Square Footage for Architecture).
4. **Multi-Slot Media Retrieval (`src/image_service.py`):**
   - Implemented `retrieve_image_slots()` with curated `hero`, `background`, and `gallery` slots for luxury interiors, cybersecurity SaaS, artisan bakery, culinary, and fitness.
   - Transparent attribution and safe visual placeholder cards for missing or offline media.
5. **Rich Developer Diagnostics (`app.py`):**
   - Multi-tab diagnostics panel inspecting: Pipeline Trace & Architecture Summary, Planner Plan JSON, Validated `WebsiteState` JSON & Section Table, Curated Media Slots & Attribution, and Internal Anchor/Target Map.
6. **Benchmark Fallbacks (`src/generator.py`):**
   - Added dedicated benchmark fallback presets for Luxury Interior Design Studio, Cloud Security SaaS, and Artisan Bakery alongside the existing Pet Grooming and Fitness presets.

---

## 8. Execution & Verification Results

### Relevant Test Suites:
- **Generation Suite (20 tests):**
  ```powershell
  python -m pytest tests/test_generation.py -v
  ```
  *Actual Result:* `20 passed in 2.91s`
  - Verified contrasting briefs produce diverse typography pairs, background styles, navigation styles, form types, and layout variants.
  - Verified multi-slot image retrieval and semantic keyword matching.

- **Renderer Suite (29 tests):**
  ```powershell
  python -m pytest tests/test_renderer.py -v
  ```
  *Actual Result:* `29 passed in 3.65s`
  - Verified editorial showcase, storefront, centered, minimal, and split hero layouts.
  - Verified multi-image gallery grid, circular pill category features, navbar styles, and `#appointment-form` target resolution with pulse animation.

- **Full Project Test Suite (59 tests):**
  ```powershell
  python -m pytest
  ```
  *Actual Result:* `59 passed in 7.60s` (100% pass rate across provider, generation, and renderer suites).

- **Streamlit Application Smoke Check:**
  ```powershell
  python -c "import app; print('App imported successfully!')"
  ```
  *Actual Result:* `App imported successfully!`

---

## 8. Website Generation Validation & Diagnostics Error Fix

### Problem Analysis & Root Causes:
1. **Section Content String Mismatch:** LLMs occasionally returned `Section.content` as a plain string instead of the dictionary required by the `WebsiteState` schema. In raw Pydantic validation, this raised `Input should be a valid dictionary [type=dict_type, input_type=str]`.
2. **Missing/Malformed Content Handling:** Missing, null, or list-based content inputs could lead to validation failures or missing required fields in downstream rendering.
3. **Diagnostics AttributeError (`app.py:313`):** The developer diagnostics panel referenced `plan_data.tone` and `plan_data.font_family`, which were obsolete property names on `WebsitePlan` (where the model fields are `tone_and_style` and `typography`). This triggered an unhandled `AttributeError` during inspection.
4. **Repair Prompt Insufficiency:** The 1-step repair prompt did not explicitly articulate the required dictionary structure for each section type, risking repeated validation failures.

### Architectural Improvements Implemented:
1. **Section Content Normalization Engine (`src/schema.py`):**
   - Implemented `normalize_section_content(section_type, raw_content)` covering all 8 section types (`hero`, `text`, `image`, `features`, `testimonials`, `pricing`, `cta`, `contact`).
   - Plain strings are converted into compliant, structured dictionaries while strictly preserving all text in titles, bodies, descriptions, quotes, and plans.
   - List inputs (e.g. string arrays for features or testimonials) are parsed into component dictionaries.
   - Null, missing, or boolean values safely resolve to complete default dictionaries matching renderer expectations.
   - Existing dictionaries are preserved, with internal item lists sanitized.
   - Wired into `Section` and `WebsiteState` via `@model_validator(mode="before")`.
2. **Pre-Validation Normalization & Bounded Repair (`src/generator.py`):**
   - Added pre-validation normalization via `normalize_website_state_dict` before the first Pydantic validation attempt.
   - Enhanced the bounded repair prompt with explicit dictionary schema requirements and example structures for all 8 section types.
   - Re-applied normalization to repaired JSON before the final validation check, returning clean `WebsiteGenerationError` if validation still fails.
3. **Plan Compatibility & Diagnostics Safety (`src/schema.py`, `app.py`):**
   - Added `@model_validator(mode="before")` on `WebsitePlan` to support legacy `tone` and `font_family` aliases, plus backwards-compatible properties.
   - Fixed `app.py` line 313: replaced direct attribute access with safe `getattr` calls (`plan_data.tone_and_style`, `plan_data.typography`) and default fallbacks.
   - Wrapped diagnostics tabs in safe try/except handlers to guarantee that diagnostics inspection can never crash website generation or the live preview.

---

## 9. Execution & Verification Results

### Relevant Test Suites:
- **Generation Suite (26 tests):**
  ```powershell
  python -m pytest tests/test_generation.py -v
  ```
  *Actual Result:* `26 passed in 4.95s`
  - Verified string-to-dictionary normalization for all 8 section types.
  - Verified valid dictionary preservation with custom fields.
  - Verified missing, null, and empty content fallback to valid dictionaries.
  - Verified malformed numeric, boolean, and list content handling.
  - Verified end-to-end generator success when LLM returns string section content.
  - Verified diagnostics rendering with absent or legacy plan fields.

- **Renderer Suite (29 tests):**
  ```powershell
  python -m pytest tests/test_renderer.py -v
  ```
  *Actual Result:* `29 passed in 3.65s`
  - All layout variants, navigation anchors, visual media fallbacks, and form interactions verified.

- **Full Project Test Suite (65 tests):**
  ```powershell
  python -m pytest
  ```
  *Actual Result:* `65 passed in 17.33s` (100% pass rate across provider, generation, and renderer suites).

- **Streamlit Application Smoke Check:**
  ```powershell
  python -c "import app; print('App smoke check passed!')"
  ```
  *Actual Result:* `App smoke check passed!`

---

## 10. Files Created / Modified
- `src/schema.py` (Added: `normalize_section_content()`, `normalize_website_state_dict()`, `Section` pre-validator, `WebsitePlan` alias validator & properties, `WebsiteState` pre-validator)
- `src/generator.py` (Updated: Pre-validation normalization of initial and repaired LLM outputs; comprehensive section content schema specifications in repair prompt)
- `app.py` (Fixed: `plan_data.tone` -> `plan_data.tone_and_style`, `plan_data.font_family` -> `plan_data.typography`; safe `getattr` fallbacks; error-isolated diagnostics tabs)
- `tests/test_generation.py` (Added: 6 targeted regression tests for normalization, valid dict preservation, missing/null content, malformed types, LLM generation with string content, and diagnostics plan field safety)
- `PROJECT_PROGRESS.md` (Updated)

---

## 11. Next Phase: Phase 4
- Implement conversational Edit Agent receiving current `WebsiteState`, user natural language instruction, and allowed operation schema.
- Implement pure, deterministic Python patch engine for:
  - `update`: Content and style property changes (e.g. `content.cta_text`, `style.variant`, `style.layout_variant`).
  - `add`: Insert new section with stable ID at position.
  - `remove`: Remove section by ID.
  - `reorder`: Reorder section by ID to new position.
- Validate resulting mutated state copy with Pydantic; reject invalid patches and preserve current valid state.
- Increment version counter upon successful edits.
- Note: Phase 4 has **not** been started in accordance with project constraints.
