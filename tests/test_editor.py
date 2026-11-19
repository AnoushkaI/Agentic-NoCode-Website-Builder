"""
Unit and Integration Tests for Phase 4:
Conversational Edit Agent & Deterministic Patch Engine with WCAG Dynamic Color Contrast.
"""

import json
import pytest
from unittest.mock import MagicMock
from src.schema import (
    WebsiteState,
    Section,
    SectionStyle,
    ThemeConfig,
    PatchOperation,
    EditPlan,
    OperationRecord,
)
from src.color_utils import (
    parse_color_to_rgb,
    get_relative_luminance,
    get_contrast_ratio,
    is_readable_contrast,
    get_readable_foreground,
    resolve_theme_colors,
)
from src.patch_engine import (
    apply_update_section,
    apply_add_section,
    apply_remove_section,
    apply_reorder_sections,
    apply_update_theme,
    apply_patches,
    restore_version,
)
from src.editor import (
    plan_edits,
    _create_deterministic_fallback_edit_plan,
    EditAgentError,
)
from src.schema import strip_star_emojis
from unittest.mock import patch
from src.renderer import render_website
from src.providers.base import ProviderResponse


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_website_state() -> WebsiteState:
    """Fixture providing a valid 3-section WebsiteState for testing mutations."""
    return WebsiteState(
        title="Zenith Fitness Club",
        version=1,
        theme=ThemeConfig(
            background="#FFFFFF",
            primary_color="#2563EB",
            text_color="#1E293B",
            font_family="Inter, sans-serif",
            heading_font="Outfit, sans-serif",
            nav_style="sticky_glass",
            background_style="solid",
        ),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={
                    "title": "Transform Your Body and Mind",
                    "subtitle": "State of the art equipment and expert coaches.",
                    "cta_text": "Join Now",
                    "cta_link": "#appointment-form",
                },
                style=SectionStyle(alignment="center", padding="large"),
            ),
            Section(
                id="features-1",
                type="features",
                content={
                    "heading": "Why Train With Us",
                    "features": [
                        {"title": "Elite Trainers", "description": "Certified olympic-level coaches."},
                        {"title": "Open 24/7", "description": "Train on your schedule, day or night."},
                    ],
                },
                style=SectionStyle(alignment="left", padding="medium"),
            ),
            Section(
                id="contact-1",
                type="contact",
                content={
                    "heading": "Book a Free Consultation",
                    "form_type": "appointment",
                    "fields": ["Full Name", "Email Address", "Preferred Date"],
                    "submit_label": "Reserve Free Pass",
                },
                style=SectionStyle(alignment="center", padding="medium"),
            ),
        ],
    )


# -----------------------------------------------------------------------------
# 1. Color Utilities & WCAG 2.1 Contrast Tests
# -----------------------------------------------------------------------------

def test_parse_color_to_rgb():
    """Verify robust parsing of hex (#3, #6, #8), rgb/rgba, and named CSS colors."""
    assert parse_color_to_rgb("#FFF") == (255, 255, 255)
    assert parse_color_to_rgb("#000000") == (0, 0, 0)
    assert parse_color_to_rgb("#2563eb") == (37, 99, 235)
    assert parse_color_to_rgb("rgb(10, 20, 30)") == (10, 20, 30)
    assert parse_color_to_rgb("rgba(10, 20, 30, 0.5)") == (10, 20, 30)
    assert parse_color_to_rgb("white") == (255, 255, 255)
    assert parse_color_to_rgb("black") == (0, 0, 0)
    assert parse_color_to_rgb("invalid_color") == (255, 255, 255)  # safe fallback


def test_wcag_luminance_and_contrast_ratio_formula():
    """Verify WCAG 2.1 relative luminance and contrast ratio calculations."""
    black_rgb = (0, 0, 0)
    white_rgb = (255, 255, 255)

    assert get_relative_luminance(black_rgb) == 0.0
    assert pytest.approx(get_relative_luminance(white_rgb), 0.001) == 1.0

    # Black vs White must be 21.0:1
    bw_ratio = get_contrast_ratio("#000000", "#FFFFFF")
    assert pytest.approx(bw_ratio, 0.1) == 21.0

    # Symmetric property: ratio(a, b) == ratio(b, a)
    assert pytest.approx(get_contrast_ratio("#2563EB", "#FFFFFF"), 0.01) == get_contrast_ratio("#FFFFFF", "#2563EB")

    # Identical colors must have ratio 1.0:1
    assert pytest.approx(get_contrast_ratio("#FFFFFF", "#FFFFFF"), 0.01) == 1.0


def test_wcag_readable_foreground_resolution():
    """
    Verify dynamic foreground selection satisfies WCAG AA (>= 4.5:1)
    across light, dark, and challenging vibrant hues.
    """
    # 1. Dark background must select a light readable text
    dark_fg = get_readable_foreground("#0F172A")
    assert get_contrast_ratio("#0F172A", dark_fg) >= 4.5

    # 2. Light background must select a dark readable text
    light_fg = get_readable_foreground("#FFFDF9")
    assert get_contrast_ratio("#FFFDF9", light_fg) >= 4.5

    # 3. Challenging vibrant color: Amber / Yellow (#F59E0B)
    # White on yellow fails WCAG severely (~1.8:1). Must pick dark text!
    yellow_fg = get_readable_foreground("#F59E0B")
    assert yellow_fg.upper() in ("#0F172A", "#1E293B", "#000000", "#111827")
    assert get_contrast_ratio("#F59E0B", yellow_fg) >= 4.5

    # 4. Challenging vibrant color: Navy Blue (#1E3A8A)
    # Must pick light text!
    navy_fg = get_readable_foreground("#1E3A8A")
    assert navy_fg.upper() in ("#FFFFFF", "#F8FAFC", "#F1F5F9")
    assert get_contrast_ratio("#1E3A8A", navy_fg) >= 4.5


def test_resolve_theme_colors_tokens():
    """Verify that resolve_theme_colors produces a complete token set meeting contrast criteria."""
    tokens = resolve_theme_colors(
        background="#0F172A",  # Dark theme
        primary_color="#F59E0B",  # Vibrant amber
        text_color="#E2E8F0",
    )

    required_keys = [
        "bg_color",
        "text_color",
        "heading_color",
        "primary_color",
        "btn_primary_text",
        "btn_secondary_bg",
        "btn_secondary_text",
        "card_bg",
        "card_text",
        "card_border",
        "nav_bg",
        "nav_text",
        "input_bg",
        "input_text",
    ]
    for k in required_keys:
        assert k in tokens, f"Missing token {k}"

    # Verify primary button text contrast against primary color (amber)
    btn_contrast = get_contrast_ratio(tokens["primary_color"], tokens["btn_primary_text"])
    assert btn_contrast >= 4.5, f"Button text contrast too low: {btn_contrast}"

    # Verify card text contrast against card background
    card_contrast = get_contrast_ratio(tokens["card_bg"], tokens["card_text"])
    assert card_contrast >= 4.5, f"Card text contrast too low: {card_contrast}"


# -----------------------------------------------------------------------------
# 2. Deterministic Patch Engine Tests
# -----------------------------------------------------------------------------

def test_patch_update_section_content_and_style(sample_website_state):
    """Test updating section content and style targeting existing section ID."""
    op = PatchOperation(
        action="update_section",
        target_section_id="hero-1",
        content_updates={"cta_text": "Book a Free Session", "subtitle": "Updated coaching subtitle."},
        style_updates={"background_color": "#0F172A", "alignment": "left"},
    )

    new_state, success, msg, item = apply_patches(sample_website_state, [op], instruction="Make hero darker and change CTA")

    assert success is True
    assert new_state.version == 2
    hero = next(s for s in new_state.sections if s.id == "hero-1")
    assert hero.content["cta_text"] == "Book a Free Session"
    assert hero.content["subtitle"] == "Updated coaching subtitle."
    assert hero.style.background_color == "#0F172A"
    assert hero.style.alignment == "left"
    # Original sections must be preserved
    assert len(new_state.sections) == 3
    assert item is not None
    assert item.version_after == 2


def test_patch_update_form_fields(sample_website_state):
    """Test modifying form fields in a contact/booking section."""
    op = PatchOperation(
        action="update_section",
        target_section_id="contact-1",
        content_updates={"fields": ["Full Name", "Phone Number", "Fitness Goals", "Experience Level"]},
    )

    new_state, success, msg, _ = apply_patches(sample_website_state, [op], instruction="Update consultation fields")

    assert success is True
    contact = next(s for s in new_state.sections if s.id == "contact-1")
    assert contact.content["fields"] == ["Full Name", "Phone Number", "Fitness Goals", "Experience Level"]


def test_patch_add_section(sample_website_state):
    """Test adding a new section with auto-stable ID and correct positioning."""
    op = PatchOperation(
        action="add_section",
        section_type="testimonials",
        placement="before",
        target_section_id="contact-1",
        new_section_content={
            "heading": "Member Testimonials",
            "testimonials": [
                {"name": "Sarah Connor", "role": "CrossFit Athlete", "quote": "Best gym in town!"}
            ],
        },
    )

    new_state, success, msg, _ = apply_patches(sample_website_state, [op], instruction="Add testimonials section")

    assert success is True
    assert len(new_state.sections) == 4
    section_ids = [s.id for s in new_state.sections]
    assert "testimonials-1" in section_ids
    # Testimonials should be placed before contact-1
    testim_idx = section_ids.index("testimonials-1")
    contact_idx = section_ids.index("contact-1")
    assert testim_idx == contact_idx - 1


def test_patch_remove_section(sample_website_state):
    """Test safely removing an existing section by ID."""
    op = PatchOperation(
        action="remove_section",
        target_section_id="features-1",
    )

    new_state, success, msg, _ = apply_patches(sample_website_state, [op], instruction="Remove features section")

    assert success is True
    assert len(new_state.sections) == 2
    assert "features-1" not in [s.id for s in new_state.sections]
    assert new_state.version == 2


def test_patch_remove_section_prevents_empty_website():
    """Test that patch engine safety guard prevents deleting all sections."""
    single_sec_state = WebsiteState(
        title="Minimal",
        version=1,
        theme=ThemeConfig(background="#fff", primary_color="#000", text_color="#111"),
        sections=[Section(id="hero-1", type="hero", content={"title": "Hello"})],
    )
    op = PatchOperation(action="remove_section", target_section_id="hero-1")

    new_state, success, msg, _ = apply_patches(single_sec_state, [op], instruction="Delete hero")

    # Must fail safely and keep the existing state untouched
    assert success is False
    assert "Cannot remove" in msg or "at least one" in msg
    assert len(single_sec_state.sections) == 1
    assert single_sec_state.version == 1


def test_patch_reorder_sections(sample_website_state):
    """Test reordering sections via full permutation list."""
    original_ids = [s.id for s in sample_website_state.sections]
    # Reverse order: ["contact-1", "features-1", "hero-1"]
    reversed_ids = list(reversed(original_ids))

    op = PatchOperation(
        action="reorder_sections",
        new_order=reversed_ids,
    )

    new_state, success, msg, _ = apply_patches(sample_website_state, [op], instruction="Move contact to top")

    assert success is True
    assert [s.id for s in new_state.sections] == reversed_ids
    assert new_state.version == 2


def test_patch_update_theme(sample_website_state):
    """Test updating theme typography, colors, and background treatment."""
    op = PatchOperation(
        action="update_theme",
        theme_updates={
            "primary_color": "#10B981",
            "font_family": "Plus Jakarta Sans, sans-serif",
            "background_style": "warm_ivory",
        },
    )

    new_state, success, msg, _ = apply_patches(sample_website_state, [op], instruction="Change theme to emerald")

    assert success is True
    assert new_state.theme.primary_color == "#10B981"
    assert new_state.theme.font_family == "Plus Jakarta Sans, sans-serif"
    assert new_state.theme.background_style == "warm_ivory"
    assert new_state.version == 2


def test_consecutive_edits_preserve_earlier_state(sample_website_state):
    """
    Crucial requirement: Test at least two consecutive edits while preserving earlier changes!
    Edit 1: "Make the hero section darker"
    Edit 2: "Change the CTA to Book a Trial"
    Edit 3: "Add a testimonials section"
    """
    # --- Edit 1: Dark hero ---
    op1 = PatchOperation(
        action="update_section",
        target_section_id="hero-1",
        style_updates={"background_color": "#0F172A", "variant": "dark"},
    )
    state_v2, s1, _, hist1 = apply_patches(sample_website_state, [op1], instruction="Make the hero section darker")
    assert s1 is True
    assert state_v2.version == 2
    hero_v2 = next(s for s in state_v2.sections if s.id == "hero-1")
    assert hero_v2.style.background_color == "#0F172A"
    assert hero_v2.content["cta_text"] == "Join Now"  # not changed yet

    # --- Edit 2: Change CTA ---
    op2 = PatchOperation(
        action="update_section",
        target_section_id="hero-1",
        content_updates={"cta_text": "Book a Trial"},
    )
    state_v3, s2, _, hist2 = apply_patches(state_v2, [op2], instruction="Change the CTA to Book a Trial")
    assert s2 is True
    assert state_v3.version == 3
    hero_v3 = next(s for s in state_v3.sections if s.id == "hero-1")
    # Verify BOTH earlier change (dark background) and new change (Book a Trial) are present!
    assert hero_v3.style.background_color == "#0F172A"
    assert hero_v3.content["cta_text"] == "Book a Trial"
    # Other sections still intact
    assert len(state_v3.sections) == 3

    # --- Edit 3: Add testimonials ---
    op3 = PatchOperation(
        action="add_section",
        section_type="testimonials",
        placement="after",
        target_section_id="features-1",
        new_section_content={
            "heading": "Client Success",
            "testimonials": [{"name": "Mark D.", "quote": "Gained 10lbs of muscle in 3 months!"}],
        },
    )
    state_v4, s3, _, hist3 = apply_patches(state_v3, [op3], instruction="Add a testimonials section")
    assert s3 is True
    assert state_v4.version == 4
    assert len(state_v4.sections) == 4
    hero_v4 = next(s for s in state_v4.sections if s.id == "hero-1")
    # Both earlier edits must STILL be preserved in v4!
    assert hero_v4.style.background_color == "#0F172A"
    assert hero_v4.content["cta_text"] == "Book a Trial"


def test_patch_rollback_on_invalid_operation(sample_website_state):
    """Test that if an invalid operation or nonexistent target is encountered, state is rolled back cleanly."""
    original_dump = sample_website_state.model_dump()

    # Target an ID that doesn't exist
    bad_op = PatchOperation(
        action="update_section",
        target_section_id="nonexistent-section-999",
        content_updates={"title": "This should fail"},
    )

    new_state, success, msg, _ = apply_patches(sample_website_state, [bad_op], instruction="Faulty edit")

    assert success is False
    assert "not found" in msg.lower()
    # The original state in memory must not be altered or incremented
    assert sample_website_state.version == 1
    assert sample_website_state.model_dump() == original_dump


# -----------------------------------------------------------------------------
# 3. Conversational Edit Agent (plan_edits) Tests
# -----------------------------------------------------------------------------

def test_plan_edits_with_mocked_llm(sample_website_state):
    """Test plan_edits converts natural language into structured EditPlan via mocked provider."""
    mock_provider = MagicMock()
    mock_provider.complete.return_value = ProviderResponse(
        content=json.dumps({
            "summary": "Updated Hero CTA button text to 'Start Free Trial'.",
            "operations": [
                {
                    "action": "update_section",
                    "target_section_id": "hero-1",
                    "content_updates": {"cta_text": "Start Free Trial"},
                }
            ],
        }),
        success=True,
        model="mock-model",
    )

    plan = plan_edits("Change CTA to Start Free Trial", sample_website_state, provider=mock_provider)

    assert isinstance(plan, EditPlan)
    assert len(plan.operations) == 1
    assert plan.operations[0].action == "update_section"
    assert plan.operations[0].target_section_id == "hero-1"
    assert plan.operations[0].content_updates["cta_text"] == "Start Free Trial"


def test_plan_edits_one_repair_attempt_on_malformed_json(sample_website_state):
    """Test bounded 1-attempt repair when LLM initially returns non-JSON or malformed payload."""
    mock_provider = MagicMock()
    # First call returns non-JSON text; second call (repair) returns valid JSON
    mock_provider.complete.side_effect = [
        ProviderResponse(content="Sure, I made the hero section darker by updating the background color to black.", success=True, model="mock-model"),
        ProviderResponse(
            content=json.dumps({
                "summary": "Repaired: Make hero section darker.",
                "operations": [
                    {
                        "action": "update_section",
                        "target_section_id": "hero-1",
                        "style_updates": {"background_color": "#0F172A", "variant": "dark"},
                    }
                ],
            }),
            success=True,
            model="mock-model",
        ),
    ]

    plan = plan_edits("Make the hero section darker", sample_website_state, provider=mock_provider)

    assert mock_provider.complete.call_count == 2
    assert isinstance(plan, EditPlan)
    assert plan.operations[0].style_updates["background_color"] == "#0F172A"


def test_plan_edits_deterministic_fallbacks(sample_website_state):
    """Test deterministic fallback planning when LLM provider is offline or None."""
    # 1. "Make the hero section darker"
    plan_dark = _create_deterministic_fallback_edit_plan("Make the hero section darker", sample_website_state)
    assert plan_dark.operations[0].action == "update_section"
    assert plan_dark.operations[0].target_section_id == "hero-1"
    assert plan_dark.operations[0].style_updates.get("background_color") == "#0F172A"

    # 2. "Change the CTA to Book a Trial"
    plan_cta = _create_deterministic_fallback_edit_plan("Change the CTA to Book a Trial", sample_website_state)
    assert plan_cta.operations[0].action == "update_section"
    assert plan_cta.operations[0].content_updates.get("cta_text") == "Book a Trial"

    # 3. "Add a testimonials section"
    plan_add = _create_deterministic_fallback_edit_plan("Add a testimonials section", sample_website_state)
    assert plan_add.operations[0].action == "add_section"
    assert plan_add.operations[0].section_type == "testimonials"

    # 4. "Change theme color to emerald"
    plan_theme = _create_deterministic_fallback_edit_plan("Make the primary color emerald", sample_website_state)
    assert plan_theme.operations[0].action == "update_theme"
    assert plan_theme.operations[0].theme_updates.get("primary_color") == "#10B981"


# -----------------------------------------------------------------------------
# 4. Integration with HTML Renderer
# -----------------------------------------------------------------------------

def test_edited_website_renders_accessible_html(sample_website_state):
    """Verify that an edited website renders accessible, responsive HTML with correct tokens."""
    # Apply two consecutive edits
    op1 = PatchOperation(
        action="update_section",
        target_section_id="hero-1",
        content_updates={"cta_text": "Claim Your Pass Now"},
        style_updates={"background_color": "#0F172A"},
    )
    op2 = PatchOperation(
        action="update_theme",
        theme_updates={"primary_color": "#F59E0B"},  # Amber primary button
    )

    state_v2, s1, _, _ = apply_patches(sample_website_state, [op1, op2], instruction="Dark hero with amber CTA")
    assert s1 is True

    # Render HTML
    html = render_website(state_v2)

    # 1. Content check
    assert "Claim Your Pass Now" in html
    # 2. Background check
    assert "background-color: #0F172A;" in html
    # 3. Dynamic token check
    assert "--primary-color: #F59E0B;" in html
    # 4. Button primary text contrast: Amber button must get high-contrast dark text
    assert "--btn-primary-text:" in html
    # Ensure button does NOT have hardcoded white text
    assert ".btn-primary { background-color: var(--primary-color); color: var(--btn-primary-text) !important;" in html


# -----------------------------------------------------------------------------
# 5. Provider Initialization, Failure Handling, and Emoji Cleanliness Tests
# -----------------------------------------------------------------------------

def test_plan_edits_uses_factory_when_provider_is_none(sample_website_state):
    """Test plan_edits obtains provider through factory when provider argument is None."""
    mock_factory_provider = MagicMock()
    mock_factory_provider.complete.return_value = ProviderResponse(
        content=json.dumps({
            "summary": "Updated Hero CTA to Schedule Visit.",
            "operations": [
                {
                    "action": "update_section",
                    "target_section_id": "hero-1",
                    "content_updates": {"cta_text": "Schedule Visit"},
                }
            ],
        }),
        success=True,
        model="mock-factory-model",
    )

    with patch("src.editor.get_provider", return_value=mock_factory_provider) as mock_get_provider:
        plan = plan_edits("Change CTA to Schedule Visit", sample_website_state, provider=None)
        assert mock_get_provider.called
        assert len(plan.operations) == 1
        assert plan.operations[0].content_updates["cta_text"] == "Schedule Visit"


def test_plan_edits_provider_initialization_error_with_fallback(sample_website_state):
    """Test that when provider initialization fails, deterministic fallback handles standard instructions."""
    with patch("src.editor.get_provider", side_effect=RuntimeError("Cannot connect to credentials service")):
        # "Make the hero section darker" should succeed via offline fallback
        plan = plan_edits("Make the hero section darker", sample_website_state, provider=None)
        assert len(plan.operations) == 1
        assert plan.operations[0].style_updates["background_color"] == "#0F172A"


def test_plan_edits_provider_initialization_error_unhandled_raises_error(sample_website_state):
    """Test that when provider initialization fails and instruction is unhandled, EditAgentError is raised."""
    with patch("src.editor.get_provider", side_effect=RuntimeError("Missing API Key")):
        with pytest.raises(EditAgentError) as exc_info:
            plan_edits("Completely redesign this website into an e-commerce spaceship", sample_website_state, provider=None)
        assert "initialization error" in str(exc_info.value).lower()
        assert "missing api key" in str(exc_info.value).lower()


def test_plan_edits_provider_api_failure_unhandled_raises_error(sample_website_state):
    """Test that when LLM provider returns an API failure, EditAgentError is raised with the error details."""
    mock_provider = MagicMock()
    mock_provider.complete.return_value = ProviderResponse(
        content="",
        success=False,
        error="Gateway Timeout 504",
        model="mock-model",
    )

    with pytest.raises(EditAgentError) as exc_info:
        plan_edits("Add an interactive 3D particle accelerator", sample_website_state, provider=mock_provider)
    assert "gateway timeout 504" in str(exc_info.value).lower()


def test_plan_edits_provider_exception_raises_error(sample_website_state):
    """Test that when LLM provider complete() raises an unhandled exception, EditAgentError is raised."""
    mock_provider = MagicMock()
    mock_provider.complete.side_effect = ConnectionResetError("Connection abruptly closed by peer")

    with pytest.raises(EditAgentError) as exc_info:
        plan_edits("Add a complex multi-tenant billing workflow", sample_website_state, provider=mock_provider)
    assert "connection abruptly closed" in str(exc_info.value).lower()


def test_no_star_emojis_in_website_name_and_headings(sample_website_state):
    """
    Verify that star emojis (⭐, ★, ✨, 🌟, ☆, 💫, 🌠) are strictly stripped from:
    1. WebsiteState title
    2. Section titles and headings
    3. Rendered HTML brand name and section headings
    """
    # 1. strip_star_emojis unit behavior
    assert strip_star_emojis("✨ Zenith Fitness ⭐") == "Zenith Fitness"
    assert strip_star_emojis("🌟 Top Features ★") == "Top Features"
    assert strip_star_emojis("Clean Name") == "Clean Name"

    # 2. Schema field validation cleaning
    state_with_stars = WebsiteState(
        title="✨ Stellar Fitness Club ⭐",
        version=1,
        theme=ThemeConfig(background="#FFFFFF", primary_color="#2563EB", text_color="#1E293B"),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={
                    "title": "🌟 Transform Your Body ✨",
                    "subtitle": "No stars in title",
                    "brand_icon": "✨",  # Star icon
                },
            ),
            Section(
                id="features-1",
                type="features",
                content={
                    "heading": "⭐ Why Choose Us 🌟",
                    "items": [{"title": "✨ Elite Coaches ⭐", "description": "Top tier."}],
                },
            ),
        ],
    )

    # State title must be sanitized
    assert state_with_stars.title == "Stellar Fitness Club"
    hero_sec = next(s for s in state_with_stars.sections if s.id == "hero-1")
    assert hero_sec.content["title"] == "Transform Your Body"

    feat_sec = next(s for s in state_with_stars.sections if s.id == "features-1")
    assert feat_sec.content["heading"] == "Why Choose Us"
    assert feat_sec.content["items"][0]["title"] == "Elite Coaches"

    # 3. Rendered HTML check: brand-name and section-title must have no star emojis
    rendered_html = render_website(state_with_stars)
    assert '<span class="brand-name">Stellar Fitness Club</span>' in rendered_html
    assert "✨ Stellar Fitness Club" not in rendered_html
    assert "⭐" not in rendered_html
    assert "🌟 Transform Your Body" not in rendered_html
    assert '<h1 class="hero-title">Transform Your Body</h1>' in rendered_html or 'Transform Your Body' in rendered_html


def test_compound_edits_atomic_application_and_individual_results(sample_website_state):
    """
    Test compound edits:
    1. Instruction contains multiple independent changes (hero darker, change CTA text, add FAQ section before contact).
    2. Edit agent produces separate structured operations.
    3. Patch engine applies all operations atomically.
    4. Individual operation results, targets, and before/after values are recorded in history.
    """
    instruction = "Make the hero section darker, change CTA to Book a Consultation, and add an FAQ section before contact"
    plan = _create_deterministic_fallback_edit_plan(instruction, sample_website_state)
    assert plan is not None
    assert len(plan.operations) >= 3

    # Operations must be separate structured operations
    ops_types = [op.op for op in plan.operations]
    assert "update_section" in ops_types
    assert "add_section" in ops_types

    # Execute atomically
    new_state, success, msg, hist = apply_patches(
        sample_website_state,
        plan.operations,
        instruction=instruction,
        summary=plan.summary,
    )

    assert success is True
    assert new_state.version == sample_website_state.version + 1

    # Check hero is dark
    hero = new_state.find_section("hero-1")
    assert hero.style.variant == "dark"
    assert hero.style.background_color == "#0F172A"

    # Check CTA is updated
    assert hero.content["cta_text"] == "Book a Consultation"

    # Check FAQ is added with 5 Q&A items placed before contact-1
    faq = next((s for s in new_state.sections if s.type == "faq"), None)
    assert faq is not None
    assert len(faq.content["items"]) == 5
    faq_idx = [s.id for s in new_state.sections].index(faq.id)
    contact_idx = [s.id for s in new_state.sections].index("contact-1")
    assert faq_idx < contact_idx

    # Check individual operation results recorded
    assert hist is not None
    assert hist.success is True
    assert len(hist.operation_records) >= 3
    for rec in hist.operation_records:
        assert rec.status == "success"
        assert rec.new_value is not None


def test_compound_edits_atomic_rollback_on_failure(sample_website_state):
    """
    Test compound edits atomic rollback:
    When one operation in a compound edit fails (e.g. nonexistent section target),
    the entire transaction must roll back, preserving the website state and version.
    """
    v_orig = sample_website_state.version
    hero_orig_style = sample_website_state.find_section("hero-1").style.variant

    compound_ops = [
        # Op 1: Valid change (make hero darker)
        PatchOperation(
            op="update_section",
            target_id="hero-1",
            style={"variant": "dark", "background_color": "#0F172A"},
        ),
        # Op 2: Invalid change (target nonexistent section 'about-us')
        PatchOperation(
            op="update_section",
            target_id="about-us",
            content={"heading": "New About Us Heading"},
        ),
    ]

    mutated_state, success, msg, hist = apply_patches(
        sample_website_state,
        compound_ops,
        instruction="Make hero dark and update about us",
    )

    # Must fail and rollback
    assert success is False
    assert mutated_state.version == v_orig
    assert mutated_state.find_section("hero-1").style.variant == hero_orig_style
    assert "about-us" in msg

    # Audit history captures rollback
    assert hist is not None
    assert hist.success is False
    assert any(r.status == "rolled_back" for r in hist.operation_records)
    assert any(r.status == "failed" for r in hist.operation_records)


def test_missing_about_us_target_handling(sample_website_state):
    """
    Test that targeting a missing section ID like 'about-us' is rejected gracefully
    without mutating the website or incrementing the version.
    """
    v_orig = sample_website_state.version
    op = PatchOperation(
        op="update_section",
        target_id="about-us",
        content={"body": "New story"},
    )

    state, success, msg, hist = apply_patches(sample_website_state, [op], instruction="Edit about us")
    assert success is False
    assert state.version == v_orig
    assert "not found in website" in msg
    assert "hero-1" in msg
    assert hist.success is False


def test_empty_operations_no_op_handling(sample_website_state):
    """
    Test that empty patch operations produce a useful clarification message,
    preserve the website unchanged, and do not increment the version or report success.
    """
    v_orig = sample_website_state.version
    state, success, msg, hist = apply_patches(
        sample_website_state,
        operations=[],
        instruction="Random non-edit chatter",
    )

    assert success is False
    assert state.version == v_orig
    assert "0 operations" in msg
    assert hist is not None
    assert hist.success is False


def test_faq_addition_schema_renderer_and_placement(sample_website_state):
    """
    Test FAQ component:
    1. Schema validation with 5 default Q&A items.
    2. Insertion before contact section.
    3. Rendered HTML accordion layout, questions, answers, and navbar navigation link.
    """
    # 1. Pydantic validation of FAQ section
    faq_section = Section(
        id="faq-1",
        type="faq",
        content={"heading": "Answers to Common Inquiries"},
    )
    assert faq_section.type == "faq"
    assert len(faq_section.content["items"]) == 5

    # 2. Patch operation adding FAQ before contact-1
    add_op = PatchOperation(
        op="add_section",
        section_type="faq",
        target_id="contact-1",
        placement="before",
    )

    new_state, success, msg, hist = apply_patches(sample_website_state, [add_op])
    assert success is True
    assert "faq-1" in new_state.get_section_ids()

    # Verify insertion order: faq-1 precedes contact-1
    s_ids = new_state.get_section_ids()
    assert s_ids.index("faq-1") < s_ids.index("contact-1")

    # 3. HTML Renderer check
    html_out = render_website(new_state)
    assert '<details class="faq-item">' in html_out
    assert 'class="faq-toggle-icon"' in html_out
    assert 'Frequently Asked Questions' in html_out or 'Answers to Common Inquiries' in html_out
    assert 'What services do you offer?' in html_out
    assert '<div id="faq"' in html_out
    assert 'href="#faq-1"' in html_out


def test_accurate_before_and_after_history_tracking(sample_website_state):
    """
    Test that OperationRecord accurately captures previous and new values for:
    - Content property changes
    - Style property changes
    - Adding a section (captures full added section)
    - Removing a section (captures full removed section dict)
    - Reordering sections (captures before and after section order sequence)
    - Updating theme (captures previous and new color/tokens)
    """
    # 1. Update content & style
    op_update = PatchOperation(
        op="update_section",
        target_id="hero-1",
        content={"cta_text": "Schedule Consultation"},
        style={"variant": "dark"},
    )
    s1, ok1, _, h1 = apply_patches(sample_website_state, [op_update])
    assert ok1 is True
    rec_cta = next(r for r in h1.operation_records if r.property_path == "content.cta_text")
    assert rec_cta.previous_value == "Join Now"
    assert rec_cta.new_value == "Schedule Consultation"

    # 2. Add section
    op_add = PatchOperation(op="add_section", section_type="faq")
    s2, ok2, _, h2 = apply_patches(s1, [op_add])
    assert ok2 is True
    rec_add = next(r for r in h2.operation_records if r.op == "add_section")
    assert rec_add.previous_value is None
    assert rec_add.new_value["type"] == "faq"

    # 3. Remove section (captures full removed section content)
    op_remove = PatchOperation(op="remove_section", target_id="features-1")
    s3, ok3, _, h3 = apply_patches(s2, [op_remove])
    assert ok3 is True
    rec_rem = next(r for r in h3.operation_records if r.op == "remove_section")
    assert rec_rem.previous_value["id"] == "features-1"
    assert "heading" in rec_rem.previous_value["content"]
    assert rec_rem.new_value is None

    # 4. Reorder sections
    current_ids = s3.get_section_ids()
    reversed_ids = list(reversed(current_ids))
    op_reorder = PatchOperation(op="reorder_sections", section_ids=reversed_ids)
    s4, ok4, _, h4 = apply_patches(s3, [op_reorder])
    assert ok4 is True
    rec_reorder = next(r for r in h4.operation_records if r.op == "reorder_sections")
    assert rec_reorder.previous_value == current_ids
    assert rec_reorder.new_value == reversed_ids

    # 5. Update theme
    op_theme = PatchOperation(op="update_theme", theme={"primary_color": "#10B981"})
    s5, ok5, _, h5 = apply_patches(s4, [op_theme])
    assert ok5 is True
    rec_theme = next(r for r in h5.operation_records if r.property_path == "theme.primary_color")
    assert rec_theme.previous_value == "#2563EB"
    assert rec_theme.new_value == "#10B981"


def test_undo_last_edit_restores_state_as_new_version(sample_website_state):
    """
    Test Undo Last Edit:
    1. State at v1.
    2. Edit to v2 changes CTA text.
    3. Undo restores v1 snapshot as new version v3 (v3 = v2 + 1).
    4. Mutated state matches v1 while preserving history.
    """
    v1 = sample_website_state
    op = PatchOperation(op="update_section", target_id="hero-1", content={"cta_text": "Sign Up Today"})
    v2, ok, _, h_edit = apply_patches(v1, [op], instruction="Change CTA to Sign Up Today")
    assert ok is True
    assert v2.version == 2
    assert v2.find_section("hero-1").content["cta_text"] == "Sign Up Today"

    # Restore v1 as new version
    v3, ok_undo, msg_undo, h_undo = restore_version(v1, v2, instruction="Undo last edit")
    assert ok_undo is True
    assert v3.version == 3  # New version incremented!
    assert v3.find_section("hero-1").content["cta_text"] == "Join Now"  # Content reverted!
    assert h_undo.version == 3
    assert h_undo.version_before == 2
    assert h_undo.success is True


def test_consecutive_edits_restoration_and_subsequent_edit(sample_website_state):
    """
    Test lifecycle requirement:
    Verify at least two consecutive edits and restoration followed by another edit.
    - v1: Initial website
    - v2: Edit 1 (Make hero darker)
    - v3: Edit 2 (Add FAQ section)
    - v4: Restore v1 (reverting back to original state as new version v4)
    - v5: Edit 3 on restored v4 (Change primary brand color)
    All 5 versions must exist, be valid, and preserve full audit trail.
    """
    # Version 1
    v1 = sample_website_state
    assert v1.version == 1
    snapshots = {1: v1}
    history = []

    # Edit 1 -> Version 2: Make hero darker
    op1 = PatchOperation(op="update_section", target_id="hero-1", style={"variant": "dark"})
    v2, ok1, _, h1 = apply_patches(v1, [op1], instruction="Make hero dark")
    assert ok1 is True
    assert v2.version == 2
    snapshots[2] = v2
    history.append(h1)

    # Edit 2 -> Version 3: Add FAQ section
    op2 = PatchOperation(op="add_section", section_type="faq")
    v3, ok2, _, h2 = apply_patches(v2, [op2], instruction="Add FAQ section")
    assert ok2 is True
    assert v3.version == 3
    snapshots[3] = v3
    history.append(h2)

    # Restoration -> Version 4: Restore Version 1
    v4, ok3, _, h3 = restore_version(snapshots[1], v3, instruction="Restore initial version 1")
    assert ok3 is True
    assert v4.version == 4
    # Content matches v1 (hero is default, no FAQ)
    assert v4.find_section("hero-1").style.variant == "default"
    assert not any(s.type == "faq" for s in v4.sections)
    snapshots[4] = v4
    history.append(h3)

    # Edit 3 -> Version 5: Subsequent edit on restored state (Update theme primary color)
    op3 = PatchOperation(op="update_theme", theme={"primary_color": "#7C3AED"})
    v5, ok4, _, h4 = apply_patches(v4, [op3], instruction="Change theme to purple")
    assert ok4 is True
    assert v5.version == 5
    assert v5.theme.primary_color == "#7C3AED"
    snapshots[5] = v5
    history.append(h4)

    # Confirm all 5 versions exist and audit trail is completely preserved
    assert len(snapshots) == 5
    assert len(history) == 4
    for h in history:
        assert h.success is True


def test_text_section_normalization_all_field_variations():
    """Verify that Section.content normalization supports all text field aliases into body."""
    from src.schema import normalize_section_content, Section

    # 1. Alias 'text' -> body
    c1 = normalize_section_content("text", {"heading": "About Us", "text": "We groom dogs with love."})
    assert c1["heading"] == "About Us"
    assert c1["body"] == "We groom dogs with love."

    # 2. Alias 'description' -> body
    c2 = normalize_section_content("text", {"title": "Our Heritage", "description": "Founded in 2018 in Brooklyn."})
    assert c2["heading"] == "Our Heritage"
    assert c2["body"] == "Founded in 2018 in Brooklyn."

    # 3. Alias 'content' -> body
    c3 = normalize_section_content("text", {"heading": "Who We Are", "content": "Master pet stylists with deep passion."})
    assert c3["body"] == "Master pet stylists with deep passion."

    # 4. Alias 'paragraphs' (list of strings) -> joined body with double newline
    c4 = normalize_section_content("text", {
        "heading": "Our Journey",
        "paragraphs": ["First paragraph about our beginnings.", "Second paragraph about our spa philosophy."]
    })
    assert "First paragraph about our beginnings." in c4["body"]
    assert "Second paragraph about our spa philosophy." in c4["body"]
    assert "\n\n" in c4["body"]

    # 5. Raw list of strings normalized into text section
    c5 = normalize_section_content("text", ["Welcome to our studio.", "We provide tailored care."])
    assert c5["heading"] == "About Us"
    assert "Welcome to our studio." in c5["body"]
    assert "We provide tailored care." in c5["body"]

    # 6. Pydantic Section validation guarantees heading and body presence
    sec = Section(id="text-1", type="text", content={"title": "Pawfect Story", "story": "Started by animal lovers."})
    assert sec.content["heading"] == "Pawfect Story"
    assert sec.content["body"] == "Started by animal lovers."


def test_render_text_section_paragraphs_alignment_and_optional_image():
    """Verify that render_text_section produces headings, subheadings, multiple paragraphs, alignment and optional image split layout."""
    from src.renderer import render_text_section
    from src.schema import Section, SectionStyle

    # 1. Standard multi-paragraph text section with center alignment
    sec_center = Section(
        id="text-1",
        type="text",
        content={
            "heading": "About Pawfect Grooming",
            "subheading": "Boutique Pet Care in Brooklyn",
            "body": "First paragraph of our story.\n\nSecond paragraph detailing our gentle organic products.\n\nThird paragraph on our certified team.",
        },
        style=SectionStyle(alignment="center"),
    )
    html_center = render_text_section(sec_center)
    assert "About Pawfect Grooming" in html_center
    assert "Boutique Pet Care in Brooklyn" in html_center
    assert '<p class="text-body">First paragraph of our story.</p>' in html_center
    assert '<p class="text-body">Second paragraph detailing our gentle organic products.</p>' in html_center
    assert '<p class="text-body">Third paragraph on our certified team.</p>' in html_center
    assert "text-align-center" in html_center

    # 2. Text section with optional image (split layout)
    sec_image = Section(
        id="text-2",
        type="text",
        content={
            "heading": "Our Craft & Philosophy",
            "body": "We believe every pet deserves a stress-free experience.",
            "image_url": "https://images.unsplash.com/photo-1548199973-03cce0bbc87b",
            "image_description": "Friendly dog at groomer",
        },
        style=SectionStyle(alignment="left", layout_variant="split"),
    )
    html_image = render_text_section(sec_image)
    assert "text-split-grid" in html_image
    assert "text-media-col" in html_image
    assert "text-content-col" in html_image
    assert "Our Craft &amp; Philosophy" in html_image
    assert "We believe every pet deserves a stress-free experience." in html_image
    assert "https://images.unsplash.com/photo-1548199973-03cce0bbc87b" in html_image


def test_text_section_content_preservation_across_edits(sample_website_state):
    """Verify that creating, editing, and restoring text sections preserves heading and body text."""
    # 1. Add text section
    op_add = PatchOperation(
        op="add_section",
        section_type="text",
        content={
            "heading": "Our Dedicated Story",
            "subheading": "Care from Heart to Tail",
            "body": "Paragraph 1: Founded in 2016.\n\nParagraph 2: Serving over 5,000 happy pets.",
        },
        style={"alignment": "left"},
        placement="after",
        target_id="hero-1",
    )
    s2, ok1, _, _ = apply_patches(sample_website_state, [op_add], instruction="Add our story")
    assert ok1 is True
    text_sec = s2.find_section("text-1")
    assert text_sec is not None
    assert text_sec.content["heading"] == "Our Dedicated Story"
    assert "Serving over 5,000 happy pets." in text_sec.content["body"]

    # 2. Update heading only -> verify body text is strictly preserved
    op_update_heading = PatchOperation(
        op="update_section",
        target_id="text-1",
        content={"heading": "Our Brooklyn Story"},
    )
    s3, ok2, _, _ = apply_patches(s2, [op_update_heading], instruction="Update heading to Our Brooklyn Story")
    assert ok2 is True
    text_sec_v3 = s3.find_section("text-1")
    assert text_sec_v3.content["heading"] == "Our Brooklyn Story"
    assert "Serving over 5,000 happy pets." in text_sec_v3.content["body"], "Body text was accidentally lost!"

    # 3. Update body only -> verify heading is strictly preserved
    op_update_body = PatchOperation(
        op="update_section",
        target_id="text-1",
        content={"body": "Updated narrative: Award-winning pet wellness center in NYC."},
    )
    s4, ok3, _, _ = apply_patches(s3, [op_update_body], instruction="Update body text")
    assert ok3 is True
    text_sec_v4 = s4.find_section("text-1")
    assert text_sec_v4.content["heading"] == "Our Brooklyn Story", "Heading was accidentally lost!"
    assert text_sec_v4.content["body"] == "Updated narrative: Award-winning pet wellness center in NYC."

    # 4. Restore v2 snapshot -> verify original story is restored
    s5, ok4, _, _ = restore_version(s2, s4, instruction="Restore to v2")
    assert ok4 is True
    text_sec_v5 = s5.find_section("text-1")
    assert text_sec_v5.content["heading"] == "Our Dedicated Story"
    assert "Serving over 5,000 happy pets." in text_sec_v5.content["body"]


def test_wcag_interactive_contrast_light_dark_vibrant_themes():
    """Verify WCAG contrast compliance (>= 4.5:1) across normal, hover, active, and disabled states on light, dark, and vibrant themes."""
    test_themes = [
        {"bg": "#FFFFFF", "primary": "#2563EB", "name": "Standard Light"},
        {"bg": "#FFFDF9", "primary": "#D97706", "name": "Warm Ivory / Amber"},
        {"bg": "#FFFDF9", "primary": "#F59E0B", "name": "Warm Ivory / Yellow"},
        {"bg": "#0F172A", "primary": "#10B981", "name": "Dark Slate / Emerald"},
        {"bg": "#0A0F1D", "primary": "#7C3AED", "name": "Deep Tech / Purple"},
        {"bg": "#0F172A", "primary": "#F59E0B", "name": "Dark / Vibrant Yellow"},
        {"bg": "#FFFFFF", "primary": "#DC2626", "name": "Light / Vibrant Red"},
    ]

    for th in test_themes:
        tokens = resolve_theme_colors(
            background=th["bg"],
            primary_color=th["primary"],
        )
        theme_name = th["name"]

        # 1. Primary button normal state >= 4.5:1
        c_pri_norm = get_contrast_ratio(tokens["btn_primary_bg"], tokens["btn_primary_text"])
        assert c_pri_norm >= 4.5, f"[{theme_name}] Primary button text contrast {c_pri_norm:.2f} < 4.5"

        # 2. Primary button hover state >= 4.5:1
        c_pri_hover = get_contrast_ratio(tokens["btn_primary_hover_bg"], tokens["btn_primary_hover_text"])
        assert c_pri_hover >= 4.5, f"[{theme_name}] Primary button hover text contrast {c_pri_hover:.2f} < 4.5"

        # 3. Primary button active state >= 4.5:1
        c_pri_active = get_contrast_ratio(tokens["btn_primary_active_bg"], tokens["btn_primary_active_text"])
        assert c_pri_active >= 4.5, f"[{theme_name}] Primary button active text contrast {c_pri_active:.2f} < 4.5"

        # 4. Secondary button normal state >= 4.5:1
        c_sec_norm = get_contrast_ratio(tokens["btn_secondary_bg"], tokens["btn_secondary_text"])
        assert c_sec_norm >= 4.5, f"[{theme_name}] Secondary button text contrast {c_sec_norm:.2f} < 4.5"

        # 5. Secondary button hover state >= 4.5:1 (NO invisible white on white!)
        c_sec_hover = get_contrast_ratio(tokens["btn_secondary_hover_bg"], tokens["btn_secondary_hover_text"])
        assert c_sec_hover >= 4.5, f"[{theme_name}] Secondary button hover text contrast {c_sec_hover:.2f} < 4.5"

        # 6. Secondary button active state >= 4.5:1
        c_sec_active = get_contrast_ratio(tokens["btn_secondary_active_bg"], tokens["btn_secondary_active_text"])
        assert c_sec_active >= 4.5, f"[{theme_name}] Secondary button active text contrast {c_sec_active:.2f} < 4.5"

        # 7. Disabled button state >= 4.5:1
        c_dis = get_contrast_ratio(tokens["btn_disabled_bg"], tokens["btn_disabled_text"])
        assert c_dis >= 4.5, f"[{theme_name}] Disabled button text contrast {c_dis:.2f} < 4.5"

        # 8. Nav link normal & hover state >= 4.5:1
        c_nav_link = get_contrast_ratio(tokens["nav_bg"], tokens["nav_link_color"])
        assert c_nav_link >= 4.5, f"[{theme_name}] Nav link text contrast {c_nav_link:.2f} < 4.5"

        c_nav_hover = get_contrast_ratio(tokens["nav_bg"], tokens["nav_link_hover_color"])
        assert c_nav_hover >= 4.5, f"[{theme_name}] Nav link hover text contrast {c_nav_hover:.2f} < 4.5"

        # 9. Card text normal & hover state >= 4.5:1
        c_card = get_contrast_ratio(tokens["card_bg"], tokens["card_text"])
        assert c_card >= 4.5, f"[{theme_name}] Card text contrast {c_card:.2f} < 4.5"

        c_card_hover = get_contrast_ratio(tokens["card_hover_bg"], tokens["card_hover_text"])
        assert c_card_hover >= 4.5, f"[{theme_name}] Card hover text contrast {c_card_hover:.2f} < 4.5"

        # 10. Form control input text >= 4.5:1
        c_input = get_contrast_ratio(tokens["input_bg"], tokens["input_text"])
        assert c_input >= 4.5, f"[{theme_name}] Input text contrast {c_input:.2f} < 4.5"


def test_preview_rendering_pipeline_and_html_refresh(sample_website_state):
    """Verify that WebsiteState -> renderer -> HTML produces updated HTML on version edits and calls components.html safely."""
    import streamlit.components.v1 as components
    import inspect

    # Verify components.html parameter compatibility
    sig = inspect.signature(components.html)
    assert "key" not in sig.parameters, "Streamlit components.html must not be called with unsupported key param"
    assert "html" in sig.parameters
    assert "height" in sig.parameters
    assert "scrolling" in sig.parameters

    # Version 1 HTML
    v1_html = render_website(sample_website_state)
    assert "--btn-secondary-hover-bg" in v1_html
    assert "--nav-link-hover-color" in v1_html

    # Apply edit -> Version 2
    op = PatchOperation(op="update_section", target_id="hero-1", content={"cta_text": "Join Club"})
    v2, ok, _, _ = apply_patches(sample_website_state, [op], instruction="Change CTA")
    assert ok is True
    assert v2.version == 2

    # Version 2 HTML
    v2_html = render_website(v2)
    assert "Join Club" in v2_html
    assert v1_html != v2_html, "HTML must update dynamically after edit"


def test_contact_section_alignment_edit_and_rendering(sample_website_state):
    """Verify that editing contact section alignment stores alignment and renderer applies it to contact details & location."""
    # Ensure starting alignment is left so edit is an active mutation
    contact_sec = next(s for s in sample_website_state.sections if s.id == "contact-1")
    contact_sec.style.alignment = "left"

    # 1. Test fallback conversational planning recognizes contact center alignment
    plan = plan_edits("align contact details to center", sample_website_state, provider=None)
    assert len(plan.operations) > 0
    assert plan.operations[0].target_id == "contact-1"
    assert plan.operations[0].style.get("alignment") == "center"

    # 2. Apply patch and verify state updates
    new_state, ok, msg, _ = apply_patches(sample_website_state, plan.operations, instruction="Center align contact")
    assert ok is True
    assert new_state is not None
    updated_contact = next(s for s in new_state.sections if s.id == "contact-1")
    assert updated_contact.style.alignment == "center"

    # 3. Verify HTML rendering has centered classes for contact info card, container and header
    html = render_website(new_state)
    assert "contact-info-card text-align-center" in html
    assert "contact-container text-align-center" in html
    assert "section-header-center" in html

    # 4. Test right alignment
    op_right = PatchOperation(op="update_section", target_id="contact-1", style={"alignment": "right"})
    right_state, ok_r, _, _ = apply_patches(new_state, [op_right], instruction="Right align contact")
    assert ok_r is True
    html_right = render_website(right_state)
    assert "contact-info-card text-align-right" in html_right
    assert "section-header-right" in html_right


def test_theme_color_update_propagates_to_rendered_css_tokens(sample_website_state):
    """Verify that updated theme colors reach the rendered CSS tokens including button hover, focus, and active states."""
    # 1. Update theme primary color to Emerald Green (#10B981)
    plan = plan_edits("change button color to #10B981", sample_website_state, provider=None)
    assert len(plan.operations) > 0
    assert plan.operations[0].op == "update_theme"
    assert plan.operations[0].theme.get("primary_color") == "#10B981"

    new_state, ok, msg, _ = apply_patches(sample_website_state, plan.operations, instruction="Green buttons")
    assert ok is True
    assert new_state.theme.primary_color == "#10B981"

    # 2. Verify rendered CSS contains dynamic tokens
    html = render_website(new_state)
    assert "--primary-color: #10b981;" in html.lower()
    assert "--btn-primary-bg:" in html
    assert "--btn-primary-hover-bg:" in html
    assert "--btn-primary-active-bg:" in html

    # 3. Verify WCAG contrast is >= 4.5:1 for interactive states
    tokens = resolve_theme_colors(new_state.theme.background, new_state.theme.primary_color, new_state.theme.text_color)
    assert get_contrast_ratio(tokens["btn_primary_bg"], tokens["btn_primary_text"]) >= 4.5
    assert get_contrast_ratio(tokens["btn_primary_hover_bg"], tokens["btn_primary_hover_text"]) >= 4.5
    assert get_contrast_ratio(tokens["btn_primary_active_bg"], tokens["btn_primary_active_text"]) >= 4.5


def test_no_op_edit_returns_failure_without_version_increment(sample_website_state):
    """Verify that an edit that does not modify state properties returns failure and does not increment version."""
    original_version = sample_website_state.version

    # Case 1: Target nonexistent section
    op_bad = PatchOperation(op="update_section", target_id="nonexistent-xyz", content={"title": "test"})
    res_state, ok, msg, hist = apply_patches(sample_website_state, [op_bad], instruction="Update ghost section")
    assert ok is False
    assert res_state.version == original_version
    assert "Section 'nonexistent-xyz' not found" in msg

    # Case 2: Operation that provides identical values (no actual mutation)
    current_title = sample_website_state.sections[0].content["title"]
    op_identical = PatchOperation(op="update_section", target_id="hero-1", content={"title": current_title})
    res_state2, ok2, msg2, hist2 = apply_patches(sample_website_state, [op_identical], instruction="Re-set identical title")
    assert ok2 is False
    assert res_state2.version == original_version
    assert "No changes were made" in msg2


def test_local_preview_server_serves_latest_html(sample_website_state):
    """Verify that the local preview server serves the latest rendered HTML with no-cache headers."""
    import io
    from src.preview_server import (
        update_preview_html,
        get_preview_url,
        get_latest_preview_html,
        _PreviewRequestHandler,
    )

    # 1. Render initial HTML and update preview server
    v1_html = render_website(sample_website_state)
    url = update_preview_html(v1_html)

    assert url is not None
    assert url.startswith("http://localhost:") or url.startswith("http://127.0.0.1:")
    assert get_preview_url() == url
    assert get_latest_preview_html() == v1_html

    # 2. Test request handling and headers via mock transport
    class MockSocket:
        def __init__(self):
            self.output = io.BytesIO()

        def makefile(self, mode, *args, **kwargs):
            if "b" in mode and "r" in mode:
                return io.BytesIO(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
            elif "b" in mode and "w" in mode:
                return self.output
            return io.BytesIO()

        def sendall(self, data):
            self.output.write(data)

    mock_sock = MockSocket()
    _PreviewRequestHandler(mock_sock, ("127.0.0.1", 12345), None)
    response_data = mock_sock.output.getvalue().decode("utf-8")

    assert "200 OK" in response_data or "HTTP/1.0 200" in response_data
    assert "Content-Type: text/html; charset=utf-8" in response_data
    assert "Cache-Control: no-cache, no-store, must-revalidate" in response_data
    assert sample_website_state.title in response_data

    # 3. Update to new HTML content
    v2_html = v1_html + "\n<!-- TEST_PREVIEW_V2_SENTINEL -->"
    update_preview_html(v2_html)
    assert get_latest_preview_html() == v2_html

    # Verify latest content is served
    mock_sock2 = MockSocket()
    _PreviewRequestHandler(mock_sock2, ("127.0.0.1", 12345), None)
    response_data2 = mock_sock2.output.getvalue().decode("utf-8")
    assert "TEST_PREVIEW_V2_SENTINEL" in response_data2




