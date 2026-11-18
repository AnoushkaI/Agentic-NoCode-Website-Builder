"""
Unit tests for Phase 2: Website Schema, Planner, and Initial Generation.
"""

import json
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError

from src.schema import (
    WebsiteState,
    WebsitePlan,
    Section,
    ThemeConfig,
    SectionStyle,
    SUPPORTED_SECTION_TYPES,
)
from src.planner import plan_website, create_deterministic_fallback_plan
from src.generator import (
    generate_website_json,
    create_fitness_fallback_website,
    WebsiteGenerationError,
)
from src.providers.base import BaseProvider, ProviderResponse


# -----------------------------------------------------------------------------
# 1. Schema Validation Tests
# -----------------------------------------------------------------------------

def test_supported_section_types_list():
    """Verify all 8 required section types are present in schema."""
    expected = ["hero", "text", "image", "features", "testimonials", "pricing", "cta", "contact"]
    for s_type in expected:
        assert s_type in SUPPORTED_SECTION_TYPES


def test_valid_website_state():
    """Verify that a well-formed WebsiteState passes validation."""
    state = WebsiteState(
        title="Test Studio",
        version=1,
        theme=ThemeConfig(background="#ffffff", primary_color="#2563eb", text_color="#1e293b"),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={"title": "Hero Title", "subtitle": "Hero Subtitle", "cta_text": "Join Now"},
                style=SectionStyle(alignment="center"),
            ),
            Section(
                id="pricing-1",
                type="pricing",
                content={"heading": "Plans", "plans": [{"name": "Basic", "price": "$10"}]},
                style=SectionStyle(variant="card"),
            ),
        ],
    )
    assert state.version == 1
    assert len(state.sections) == 2
    assert state.get_section_ids() == ["hero-1", "pricing-1"]
    assert state.find_section("hero-1") is not None
    assert state.find_section("nonexistent") is None


def test_reject_invalid_section_type():
    """Verify that unsupported section types raise ValidationError."""
    with pytest.raises(ValidationError):
        Section(
            id="unknown-1",
            type="unsupported_widget",  # Invalid type
            content={},
        )


def test_reject_duplicate_section_ids():
    """Verify that duplicate section IDs are detected and rejected."""
    with pytest.raises(ValidationError) as excinfo:
        WebsiteState(
            title="Duplicate Test",
            version=1,
            sections=[
                Section(id="hero-1", type="hero", content={"title": "Hero A"}),
                Section(id="hero-1", type="hero", content={"title": "Hero B"}),  # Duplicate ID
            ],
        )
    assert "Duplicate section id" in str(excinfo.value)


def test_reject_invalid_version():
    """Verify version must be positive integer >= 1."""
    with pytest.raises(ValidationError):
        WebsiteState(title="Bad Version", version=0, sections=[])


def test_deterministic_fitness_fallback_is_valid():
    """Verify that the pre-defined fitness website is strictly schema-compliant."""
    fallback = create_fitness_fallback_website()
    assert isinstance(fallback, WebsiteState)
    assert fallback.version == 1
    section_types = [s.type for s in fallback.sections]
    assert "hero" in section_types
    assert "features" in section_types
    assert "pricing" in section_types
    assert "testimonials" in section_types
    assert "contact" in section_types


# -----------------------------------------------------------------------------
# 2. Planner Tests
# -----------------------------------------------------------------------------

def test_planner_empty_brief_raises_error():
    """Verify planner rejects empty brief."""
    with pytest.raises(ValueError):
        plan_website("   ")


def test_planner_with_mocked_llm():
    """Test planner correctly parses well-formed JSON from provider."""
    mock_provider = MagicMock(spec=BaseProvider)
    mock_provider.complete.return_value = ProviderResponse(
        content=json.dumps({
            "business_type": "Fitness Studio",
            "tone_and_style": "High energy, dark theme",
            "primary_goal": "Book free trial pass",
            "planned_sections": ["hero", "pricing", "testimonials", "contact"],
            "suggested_title": "Apex Gym",
            "color_scheme": {"background": "#000", "primary_color": "#f00", "text_color": "#fff"},
        }),
        success=True,
    )

    plan = plan_website("Make a gym landing page", provider=mock_provider)
    assert isinstance(plan, WebsitePlan)
    assert plan.business_type == "Fitness Studio"
    assert "hero" in plan.planned_sections
    assert plan.suggested_title == "Apex Gym"


def test_planner_provider_failure_returns_fallback():
    """Test planner falls back gracefully when LLM provider fails."""
    mock_provider = MagicMock(spec=BaseProvider)
    mock_provider.complete.return_value = ProviderResponse(
        content="",
        success=False,
        error="Network timeout",
    )

    plan = plan_website("Fitness studio website", provider=mock_provider)
    assert isinstance(plan, WebsitePlan)
    assert plan.business_type == "Fitness Studio"
    assert len(plan.planned_sections) >= 3


# -----------------------------------------------------------------------------
# 3. Generator Tests & Bounded Repair
# -----------------------------------------------------------------------------

def _create_mock_provider() -> MagicMock:
    """Helper to create a configured mock provider."""
    mock_provider = MagicMock()
    mock_provider.config.provider = "mock"
    mock_provider.config.model = "mock-model"
    return mock_provider


def test_generator_valid_output():
    """Verify generator produces valid WebsiteState from mocked LLM response."""
    mock_provider = _create_mock_provider()

    valid_state_dict = {
        "title": "Pulse Yoga",
        "version": 1,
        "theme": {"background": "#ffffff", "primary_color": "#10b981", "text_color": "#111827"},
        "sections": [
            {
                "id": "hero-1",
                "type": "hero",
                "content": {"title": "Find Balance", "subtitle": "Daily Yoga Classes", "cta_text": "Join"},
                "style": {"alignment": "center", "variant": "default"},
            },
            {
                "id": "pricing-1",
                "type": "pricing",
                "content": {"heading": "Plans", "plans": [{"name": "Monthly", "price": "$30"}]},
                "style": {"variant": "card"},
            },
        ],
    }

    mock_provider.complete.return_value = ProviderResponse(
        content=f"```json\n{json.dumps(valid_state_dict)}\n```",
        success=True,
    )

    plan = WebsitePlan(
        business_type="Yoga Studio",
        tone_and_style="Calm and mindful",
        primary_goal="Book classes",
        planned_sections=["hero", "pricing"],
        suggested_title="Pulse Yoga",
    )
    state, meta = generate_website_json("yoga studio", plan, provider=mock_provider)

    assert isinstance(state, WebsiteState)
    assert state.title == "Pulse Yoga"
    assert state.version == 1
    assert len(state.sections) == 2
    assert meta["repaired"] is False


def test_generator_one_repair_attempt_success():
    """Verify generator triggers and succeeds on one bounded repair attempt."""
    mock_provider = _create_mock_provider()

    # Attempt 1: Malformed JSON with duplicate IDs and missing fields
    bad_output = '{"title": "Broken", "sections": [{"id": "hero-1", "type": "bad_type"}]}'

    # Attempt 2 (Repair): Corrected valid JSON matching plan
    repaired_state_dict = {
        "title": "Repaired Studio",
        "version": 1,
        "theme": {"background": "#ffffff", "primary_color": "#2563eb", "text_color": "#1e293b"},
        "sections": [
            {
                "id": "hero-1",
                "type": "hero",
                "content": {"title": "Repaired Title", "cta_text": "Book Trial"},
                "style": {"alignment": "center"},
            }
        ],
    }

    mock_provider.complete.side_effect = [
        ProviderResponse(content=bad_output, success=True),
        ProviderResponse(content=json.dumps(repaired_state_dict), success=True),
    ]

    plan = WebsitePlan(
        business_type="Fitness Studio",
        tone_and_style="Energetic",
        primary_goal="Trial",
        planned_sections=["hero"],
        suggested_title="Repaired Studio",
    )
    state, meta = generate_website_json("fitness studio", plan, provider=mock_provider)

    assert isinstance(state, WebsiteState)
    assert state.title == "Repaired Studio"
    assert meta["repaired"] is True
    assert mock_provider.complete.call_count == 2


def test_section_completeness_validation_triggers_repair_and_succeeds():
    """Verify that when generated website is missing planned sections, repair is triggered."""
    mock_provider = _create_mock_provider()

    # Attempt 1: Only returns hero section, missing 'features' and 'contact'
    incomplete_dict = {
        "title": "Bakery Studio",
        "version": 1,
        "theme": {"background": "#FDFBF7", "primary_color": "#D97706", "text_color": "#1E293B"},
        "sections": [
            {
                "id": "hero-1",
                "type": "hero",
                "content": {"title": "Artisan Breads", "cta_text": "Order Fresh"},
            }
        ],
    }

    # Attempt 2 (Repair): Repaired output contains all 3 planned sections
    complete_repaired_dict = {
        "title": "Bakery Studio",
        "version": 1,
        "theme": {"background": "#FDFBF7", "primary_color": "#D97706", "text_color": "#1E293B"},
        "sections": [
            {
                "id": "hero-1",
                "type": "hero",
                "content": {"title": "Artisan Breads", "cta_text": "Order Fresh"},
            },
            {
                "id": "features-1",
                "type": "features",
                "content": {"heading": "Daily Bakes", "items": [{"title": "Sourdough", "description": "Fermented 24 hrs"}]},
            },
            {
                "id": "contact-1",
                "type": "contact",
                "content": {"heading": "Visit Us", "email": "bake@artisan.com"},
            },
        ],
    }

    mock_provider.complete.side_effect = [
        ProviderResponse(content=json.dumps(incomplete_dict), success=True),
        ProviderResponse(content=json.dumps(complete_repaired_dict), success=True),
    ]

    plan = WebsitePlan(
        business_type="Bakery",
        tone_and_style="Warm & rustic",
        primary_goal="Visit store",
        planned_sections=["hero", "features", "contact"],
        suggested_title="Bakery Studio",
    )

    state, meta = generate_website_json("Artisan bakery with sourdough bread", plan, provider=mock_provider)

    assert isinstance(state, WebsiteState)
    assert meta["repaired"] is True
    assert len(state.sections) == 3
    sec_types = [s.type for s in state.sections]
    assert sec_types == ["hero", "features", "contact"]
    assert mock_provider.complete.call_count == 2


def test_section_completeness_failure_after_repair_raises_error():
    """Verify that if repair output is still missing planned sections, WebsiteGenerationError is raised."""
    mock_provider = _create_mock_provider()

    # Both attempts only return hero
    incomplete_dict = {
        "title": "Minimal Studio",
        "version": 1,
        "sections": [
            {
                "id": "hero-1",
                "type": "hero",
                "content": {"title": "Only Hero", "cta_text": "Start"},
            }
        ],
    }

    mock_provider.complete.side_effect = [
        ProviderResponse(content=json.dumps(incomplete_dict), success=True),
        ProviderResponse(content=json.dumps(incomplete_dict), success=True),
    ]

    plan = WebsitePlan(
        business_type="Consultancy",
        tone_and_style="Modern",
        primary_goal="Book meeting",
        planned_sections=["hero", "pricing", "contact"],
        suggested_title="Minimal Studio",
    )

    with pytest.raises(WebsiteGenerationError) as exc_info:
        generate_website_json("Consultancy brief", plan, provider=mock_provider)

    assert "missing" in str(exc_info.value).lower()
    assert mock_provider.complete.call_count == 2


def test_generic_fallback_website_generates_all_planned_sections():
    """Verify create_generic_fallback_website generates clean, fully-formed sections without hardcoded fixtures."""
    from src.generator import create_generic_fallback_website

    plan = WebsitePlan(
        business_type="Artisan Coffee Roasters",
        tone_and_style="Rich, rustic, craft",
        primary_goal="Sell coffee subscription boxes",
        planned_sections=["hero", "features", "pricing", "testimonials", "contact"],
        suggested_title="RoastCraft Studio",
        typography="Plus Jakarta Sans, sans-serif",
    )

    state = create_generic_fallback_website("Artisan Coffee Roasters with subscription packages", plan=plan)

    assert isinstance(state, WebsiteState)
    assert state.title == "RoastCraft Studio"
    assert len(state.sections) == 5
    ids = state.get_section_ids()
    assert ids == ["hero-1", "features-1", "pricing-1", "testimonials-1", "contact-1"]
    # Check that it's generic and didn't hardcode pet or fitness slogans
    assert "Fresh cuts" not in state.sections[0].content["title"]
    assert "Transform Your Body" not in state.sections[0].content["title"]


def test_three_substantially_different_briefs_generation():
    """
    Test 3 substantially different briefs to verify that the generalized pipeline
    creates different structures and visual directions without business if/else mappings.
    """
    from src.planner import extract_sections_generically_from_brief, create_generic_fallback_plan
    from src.generator import create_generic_fallback_website

    brief_bakery = "Create a warm website for an artisan sourdough bakery with daily pastry menu, customer reviews, and contact form"
    brief_saas = "Modern B2B cloud security software landing page with tiered enterprise pricing plans, feature highlights, and book a demo"
    brief_dental = "Gentle pediatric dental clinic with friendly care philosophy, appointment booking, patient stories, and gallery photos"

    plan_bakery = create_generic_fallback_plan(brief_bakery)
    plan_saas = create_generic_fallback_plan(brief_saas)
    plan_dental = create_generic_fallback_plan(brief_dental)

    # 1. Verify section extraction detects requested sections
    assert "features" in plan_bakery.planned_sections
    assert "contact" in plan_bakery.planned_sections
    assert "pricing" in plan_saas.planned_sections
    assert "image" in plan_dental.planned_sections or "testimonials" in plan_dental.planned_sections

    # 2. Verify complete generation produces distinct titles and states
    site_bakery = create_generic_fallback_website(brief_bakery, plan=plan_bakery)
    site_saas = create_generic_fallback_website(brief_saas, plan=plan_saas)
    site_dental = create_generic_fallback_website(brief_dental, plan=plan_dental)

    assert site_bakery.title != site_saas.title
    assert site_saas.title != site_dental.title
    assert len(site_bakery.sections) >= 4
    assert len(site_saas.sections) >= 4
    assert len(site_dental.sections) >= 4


def test_image_retrieval_service_thematic_matching():
    """Verify semantic image retrieval based on description keywords without broken URLs."""
    from src.image_service import retrieve_image_for_description

    # 1. Matching visual themes
    url_bakery = retrieve_image_for_description("Warm artisan sourdough bakery with fresh bread loaves")
    assert url_bakery is not None
    assert url_bakery.startswith("https://images.unsplash.com/")

    url_dental = retrieve_image_for_description("Modern dental clinic exam room with friendly dentist")
    assert url_dental is not None
    assert url_dental.startswith("https://images.unsplash.com/")

    url_saas = retrieve_image_for_description("Cloud software dashboard with cybersecurity analytics")
    assert url_saas is not None
    assert url_saas.startswith("https://images.unsplash.com/")

    # 2. Obscure / unmatched description returns None (graceful visual placeholder fallback)
    url_unmatched = retrieve_image_for_description("Quantum entanglement neutrino synchrotron chamber")
    assert url_unmatched is None

    # 3. None / empty description returns None
    assert retrieve_image_for_description(None) is None
    assert retrieve_image_for_description("") is None


def test_generator_repair_failure_raises_website_generation_error():
    """Verify that when repair fails too, WebsiteGenerationError is raised."""
    mock_provider = _create_mock_provider()

    # Both attempts return garbage
    mock_provider.complete.side_effect = [
        ProviderResponse(content="not json", success=True),
        ProviderResponse(content="still not json", success=True),
    ]

    plan = create_deterministic_fallback_plan("fitness")
    with pytest.raises(WebsiteGenerationError) as excinfo:
        generate_website_json("fitness studio", plan, provider=mock_provider)

    assert "Website generation failed" in str(excinfo.value)
    assert mock_provider.complete.call_count == 2


def test_generator_provider_failure_returns_fallback():
    """Verify that if LLM provider fails completely, deterministic fallback is returned."""
    mock_provider = _create_mock_provider()

    mock_provider.complete.return_value = ProviderResponse(
        content="",
        success=False,
        error="Authentication failure",
    )

    plan = create_deterministic_fallback_plan("fitness")
    state, meta = generate_website_json("fitness studio", plan, provider=mock_provider)

    assert isinstance(state, WebsiteState)
    assert meta["is_fallback"] is True
    assert len(state.sections) >= 4
