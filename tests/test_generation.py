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


def test_contrasting_briefs_produce_diverse_architecture_and_styling():
    """Verify 3 distinct business briefs produce diverse layouts, fonts, themes, and forms."""
    from src.generator import (
        create_luxury_interior_fallback_website,
        create_cloud_security_fallback_website,
        create_artisan_bakery_fallback_website,
        create_deterministic_fallback_website,
    )
    from src.planner import plan_website

    brief_luxury = "High-end luxury interior design studio in Manhattan for bespoke residences"
    brief_saas = "Enterprise cloud cybersecurity and kubernetes threat detection SaaS platform"
    brief_bakery = "Charming neighborhood artisan bakery with sourdough bakes, morning pastries, and bread subscriptions"

    mock_provider = _create_mock_provider()
    mock_provider.complete.return_value = ProviderResponse(content="", success=False)

    site_luxury = create_deterministic_fallback_website(brief_luxury)
    site_saas = create_deterministic_fallback_website(brief_saas)
    site_bakery = create_deterministic_fallback_website(brief_bakery)

    # 1. Themes & Typography Pairs must be distinctly tailored
    assert site_luxury.theme.heading_font != site_saas.theme.heading_font
    assert site_saas.theme.heading_font != site_bakery.theme.heading_font
    assert "Playfair" in site_luxury.theme.heading_font
    assert "Outfit" in site_saas.theme.heading_font

    # 2. Background and Nav Styles must vary
    assert site_luxury.theme.background_style == "editorial_cream"
    assert site_saas.theme.background_style == "tech_dark"
    assert site_bakery.theme.background_style == "warm_ivory"
    assert site_bakery.theme.nav_style == "floating_pill"

    # 3. Form types and fields must be domain-specific
    contact_luxury = next(s for s in site_luxury.sections if s.type == "contact")
    contact_saas = next(s for s in site_saas.sections if s.type == "contact")
    contact_bakery = next(s for s in site_bakery.sections if s.type == "contact")

    assert contact_luxury.content["form_type"] == "inquiry"
    assert any("Budget" in f or "Scope" in f for f in contact_luxury.content["fields"])

    assert contact_saas.content["form_type"] == "demo"
    assert any("Work Email" in f or "Cloud" in f for f in contact_saas.content["fields"])

    assert contact_bakery.content["form_type"] == "order"
    assert any("Pickup" in f or "Items" in f for f in contact_bakery.content["fields"])

    # 4. Hero layout variants must be distinct
    hero_luxury = next(s for s in site_luxury.sections if s.type == "hero")
    hero_saas = next(s for s in site_saas.sections if s.type == "hero")
    hero_bakery = next(s for s in site_bakery.sections if s.type == "hero")

    assert hero_luxury.style.layout_variant == "editorial_showcase"
    assert hero_saas.style.layout_variant == "centered"
    assert hero_bakery.style.layout_variant == "storefront"


def test_image_service_multi_slot_retrieval():
    """Verify retrieve_image_slots returns hero, bg, gallery, and labels for domains."""
    from src.image_service import retrieve_image_slots

    interior_slots = retrieve_image_slots("luxury interior design architecture")
    assert interior_slots.get("hero_url") is not None
    assert interior_slots.get("bg_url") is not None
    assert len(interior_slots.get("gallery_urls", [])) >= 2
    assert "Architectural" in interior_slots.get("label", "")

    cyber_slots = retrieve_image_slots("cloud security saas tech")
    assert cyber_slots.get("hero_url") is not None
    assert "Cybersecurity" in cyber_slots.get("label", "")

    bakery_slots = retrieve_image_slots("artisan sourdough bakery bread")
    assert bakery_slots.get("hero_url") is not None
    assert "Bakery" in bakery_slots.get("label", "")


# -----------------------------------------------------------------------------
# 7. Section Content Normalization & Diagnostics Regression Tests
# -----------------------------------------------------------------------------

def test_section_content_normalization_string_to_dict():
    """Verify plain string content is normalized into valid structured dicts for all 8 section types."""
    from src.schema import normalize_section_content, Section

    # 1. Hero
    hero_str = "Elite Boxing Studio\nHigh-intensity workouts designed to build champions."
    hero_dict = normalize_section_content("hero", hero_str)
    assert isinstance(hero_dict, dict)
    assert hero_dict["title"] == "Elite Boxing Studio"
    assert "High-intensity" in hero_dict["subtitle"]
    assert hero_dict["cta_link"] == "#appointment-form"
    sec_hero = Section(id="hero-1", type="hero", content=hero_str)
    assert isinstance(sec_hero.content, dict)
    assert sec_hero.content["title"] == "Elite Boxing Studio"

    # 2. Text
    text_str = "Our Heritage\nFounded in 1994, our studio has trained Olympic athletes."
    text_dict = normalize_section_content("text", text_str)
    assert isinstance(text_dict, dict)
    assert text_dict["heading"] == "Our Heritage"
    assert "Founded in 1994" in text_dict["body"]

    # 3. Image
    img_url_str = "https://images.unsplash.com/photo-sample.jpg"
    img_dict = normalize_section_content("image", img_url_str)
    assert isinstance(img_dict, dict)
    assert img_dict["image_url"] == img_url_str

    img_desc_str = "Boutique bakery with rustic sourdough loaves"
    img_dict2 = normalize_section_content("image", img_desc_str)
    assert img_dict2["image_description"] == img_desc_str
    assert img_dict2["alt"] == img_desc_str[:60]

    # 4. Features
    feat_str = "1. Technical Sparring - Ring sparring with coaches\n2. Heavy Bag - Cardio conditioning"
    feat_dict = normalize_section_content("features", feat_str)
    assert isinstance(feat_dict, dict)
    assert len(feat_dict["items"]) == 2
    assert "Technical Sparring" in feat_dict["items"][0]["title"]
    assert "Ring sparring" in feat_dict["items"][0]["description"]

    # 5. Testimonials
    testim_str = "The coaching completely transformed my stamina! - Alex Rivera"
    testim_dict = normalize_section_content("testimonials", testim_str)
    assert isinstance(testim_dict, dict)
    assert len(testim_dict["items"]) >= 1
    assert "transformed my stamina" in testim_dict["items"][0]["quote"]
    assert testim_dict["items"][0]["author"] == "Alex Rivera"
    assert testim_dict["items"][0]["tag"] == "Illustrative Client Feedback"

    # 6. Pricing
    pricing_str = "Basic Plan: $79\nPro Plan: $149"
    pricing_dict = normalize_section_content("pricing", pricing_str)
    assert isinstance(pricing_dict, dict)
    assert len(pricing_dict["plans"]) == 2
    assert "$79" in pricing_dict["plans"][0]["price"]
    assert "$149" in pricing_dict["plans"][1]["price"]

    # 7. CTA
    cta_str = "Claim Your Free First Session Today!"
    cta_dict = normalize_section_content("cta", cta_str)
    assert isinstance(cta_dict, dict)
    assert "Claim Your Free" in cta_dict["heading"]
    assert cta_dict["button_link"] == "#appointment-form"

    # 8. Contact
    contact_str = "Reach us at team@pulseboxing.com or call (555) 392-1049"
    contact_dict = normalize_section_content("contact", contact_str)
    assert isinstance(contact_dict, dict)
    assert contact_dict["email"] == "team@pulseboxing.com"
    assert contact_dict["phone"] == "(555) 392-1049"
    assert len(contact_dict["fields"]) >= 4


def test_section_content_normalization_valid_dict_preservation():
    """Verify that an already valid dictionary is preserved without losing custom fields."""
    from src.schema import normalize_section_content

    custom_content = {
        "title": "Custom Title",
        "subtitle": "Custom Subtitle",
        "custom_key": "custom_value",
        "cta_text": "Sign Up",
    }
    normalized = normalize_section_content("hero", custom_content)
    assert normalized["title"] == "Custom Title"
    assert normalized["subtitle"] == "Custom Subtitle"
    assert normalized["custom_key"] == "custom_value"
    assert normalized["cta_text"] == "Sign Up"

    # List of string items in features dictionary is normalized to list of dicts
    feat_content = {
        "heading": "Our Services",
        "items": ["Strength Conditioning", "Mobility Drills"],
    }
    norm_feat = normalize_section_content("features", feat_content)
    assert len(norm_feat["items"]) == 2
    assert norm_feat["items"][0]["title"] == "Strength Conditioning"
    assert isinstance(norm_feat["items"][0], dict)


def test_section_content_normalization_missing_and_null_content():
    """Verify None, empty string, and empty dict gracefully produce complete valid dictionaries."""
    from src.schema import normalize_section_content, Section

    for s_type in ["hero", "text", "image", "features", "testimonials", "pricing", "cta", "contact"]:
        norm_none = normalize_section_content(s_type, None)
        assert isinstance(norm_none, dict)
        sec_none = Section(id=f"{s_type}-1", type=s_type, content=None)
        assert isinstance(sec_none.content, dict)

        norm_empty_str = normalize_section_content(s_type, "")
        assert isinstance(norm_empty_str, dict)
        sec_str = Section(id=f"{s_type}-1", type=s_type, content="")
        assert isinstance(sec_str.content, dict)

        norm_empty_dict = normalize_section_content(s_type, {})
        assert isinstance(norm_empty_dict, dict)
        sec_dict = Section(id=f"{s_type}-1", type=s_type, content={})
        assert isinstance(sec_dict.content, dict)


def test_section_content_normalization_malformed_content():
    """Verify numeric, boolean, and list inputs are safely normalized without throwing."""
    from src.schema import normalize_section_content, Section

    # Number
    norm_num = normalize_section_content("text", 42)
    assert isinstance(norm_num, dict)
    assert "42" in norm_num["body"]

    # Boolean
    norm_bool = normalize_section_content("hero", False)
    assert isinstance(norm_bool, dict)
    assert "title" in norm_num or "title" in norm_bool

    # List of strings for features
    norm_list = normalize_section_content("features", ["Cardio", "Resistance", "Yoga"])
    assert isinstance(norm_list, dict)
    assert len(norm_list["items"]) == 3
    assert norm_list["items"][1]["title"] == "Resistance"


def test_generator_successful_generation_after_normalization():
    """Verify generator validates and returns WebsiteState when LLM returns string section content."""
    from src.generator import generate_website_json
    from src.planner import create_deterministic_fallback_plan

    mock_provider = _create_mock_provider()
    # LLM returns JSON where hero and features have plain string content
    raw_llm_json = json.dumps({
        "title": "Boxing Club",
        "version": 1,
        "theme": {
            "background": "#0F172A",
            "primary_color": "#F97316",
            "text_color": "#F8FAFC",
            "font_family": "Inter, sans-serif",
            "heading_font": "Inter, sans-serif",
            "background_style": "dark_glow",
            "nav_style": "sticky_glass",
        },
        "sections": [
            {
                "id": "hero-1",
                "type": "hero",
                "content": "Championship Boxing & HIIT. Train with elite world-class coaches.",
                "style": {"alignment": "center", "layout_variant": "split"},
            },
            {
                "id": "features-1",
                "type": "features",
                "content": "Heavy bag training; Ring sparring; Contrast hydrotherapy",
                "style": {"alignment": "center", "layout_variant": "grid"},
            },
            {
                "id": "pricing-1",
                "type": "pricing",
                "content": "Standard: $89\nUnlimited: $169",
                "style": {"alignment": "center", "layout_variant": "cards"},
            },
            {
                "id": "testimonials-1",
                "type": "testimonials",
                "content": "Great coaches and amazing workout! - Marcus V.",
                "style": {"alignment": "center", "layout_variant": "grid"},
            },
            {
                "id": "contact-1",
                "type": "contact",
                "content": "Email us at coach@boxingclub.com or call (555) 999-1234",
                "style": {"alignment": "center"},
            },
        ],
    })
    mock_provider.complete.return_value = ProviderResponse(content=raw_llm_json, success=True)

    plan = create_deterministic_fallback_plan("fitness")
    state, meta = generate_website_json("fitness boxing gym", plan, provider=mock_provider)

    assert isinstance(state, WebsiteState)
    assert meta["is_fallback"] is False
    assert len(state.sections) == 5

    # Check that string contents were normalized into dicts
    hero_sec = state.sections[0]
    assert isinstance(hero_sec.content, dict)
    assert "Championship Boxing" in hero_sec.content["title"]
    assert hero_sec.content["cta_link"] == "#appointment-form"

    features_sec = state.sections[1]
    assert isinstance(features_sec.content, dict)
    assert len(features_sec.content["items"]) >= 2

    contact_sec = state.sections[4]
    assert isinstance(contact_sec.content, dict)
    assert contact_sec.content["email"] == "coach@boxingclub.com"


def test_diagnostics_rendering_with_absent_optional_plan_fields():
    """Verify that WebsitePlan with missing/legacy/optional fields does not crash or raise AttributeError."""
    from src.schema import WebsitePlan

    # 1. Plan constructed with legacy tone and font_family
    plan_dict = {
        "business_type": "Fitness Studio",
        "tone": "Energetic and powerful",
        "font_family": "Roboto, sans-serif",
        "primary_goal": "Book free passes",
        "planned_sections": ["hero", "pricing", "contact"],
    }
    plan = WebsitePlan.model_validate(plan_dict)
    assert plan.tone == "Energetic and powerful"
    assert plan.tone_and_style == "Energetic and powerful"
    assert plan.font_family == "Roboto, sans-serif"
    assert plan.typography == "Roboto, sans-serif"

    # 2. Verify safe attribute access patterns used in app.py
    assert getattr(plan, "tone", None) == "Energetic and powerful"
    assert getattr(plan, "tone_and_style", None) == "Energetic and powerful"
    assert getattr(plan, "typography", None) == "Roboto, sans-serif"
    assert getattr(plan, "font_family", None) == "Roboto, sans-serif"
    assert getattr(plan, "non_existent_field", "fallback") == "fallback"


