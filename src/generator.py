"""
Website Generator module for SitePilot AI.
Produces structured WebsiteState JSON from a brief and plan, validates via Pydantic,
enforces section completeness against the plan, and provides a bounded one-step repair.
"""

import json
import logging
from typing import List, Optional, Tuple
from pydantic import ValidationError
from src.schema import (
    WebsiteState,
    WebsitePlan,
    Section,
    ThemeConfig,
    SectionStyle,
    SUPPORTED_SECTION_TYPES,
)
from src.providers.base import BaseProvider
from src.providers.factory import get_provider
from src.json_utils import extract_json_from_text

logger = logging.getLogger(__name__)


class WebsiteGenerationError(Exception):
    """Raised when website generation fails validation or section completeness after repair retry."""
    pass


GENERATOR_SYSTEM_PROMPT = f"""You are an elite web architect and frontend copywriter.
Your task is to generate a comprehensive, highly aesthetic, professional website as a valid JSON object matching the WebsiteState schema.

CRITICAL RULES:
1. Version MUST be 1.
2. Every section MUST have a unique stable ID (e.g. 'hero-1', 'features-1', 'pricing-1', 'testimonials-1', 'contact-1').
3. You MUST generate EVERY section listed in the plan's 'planned_sections'. Do NOT omit any section. A website with only a hero section when other sections were planned will be rejected.
4. Allowed section types are ONLY: {SUPPORTED_SECTION_TYPES}.
5. Generate rich, persuasive, professional business copy — never minimal placeholders.
6. Section requirements:
   - 'hero':
     * "title": Punchy, memorable headline
     * "subtitle": 2-3 engaging sentences explaining the unique value proposition
     * "pill_badge": Short trust badge (e.g. "✨ Premier Quality & Service")
     * "cta_text": Primary action button text
     * "cta_link": Target section anchor (e.g. "#contact-1")
     * "secondary_cta_text": Secondary action (e.g. "Explore Packages")
     * "secondary_cta_link": Target section anchor (e.g. "#pricing-1" or "#features-1")
     * "trust_points": List of 3 key assurances
     * "rating": Social proof string (e.g. "Client rating 4.9★")
     * "highlight_service": Short highlight
     * "image_description": Descriptive prompt for visual card (e.g. "Modern artisan bakery counter with fresh sourdough bread")

   - 'features':
     * "heading": Catchy section title
     * "subheading": Helpful overview paragraph
     * "items": 3-4 feature items, each having "title", "description" (2 full sentences), "icon" (emoji), and optional "tag"

   - 'pricing':
     * "heading": Section title
     * "subheading": Reassurance on transparent pricing
     * "plans": 3 distinct tiered plans (e.g. Starter, Standard, Premium), each with:
       "name", "price", "description", "features" (4-5 specific bullet items), "cta_text", and "highlighted": true for the recommended tier

   - 'testimonials':
     * "heading": Customer review title
     * "subheading": Social proof subtitle
     * "items": 2-3 authentic, glowing customer reviews with "quote", "author", "role", and "rating": 5

   - 'contact':
     * "heading": Action-oriented headline
     * "subheading": Instructions for booking/contact
     * "email": Realistic contact email
     * "phone": Realistic phone number
     * "hours": Operating hours
     * "fields": Form fields list (e.g. ["Full Name", "Phone / Email", "Service Needed", "Preferred Date & Time"])

   - 'text':
     * "heading", "subheading", and "body" with engaging multi-paragraph story

   - 'image':
     * "image_description", "alt", and "caption"

   - 'cta':
     * "heading", "subheading", "button_text", and "button_link" pointing to "#contact-1"

7. Output ONLY the raw JSON object. Do not wrap in markdown fences, do not add introductory commentary.
"""


def validate_section_completeness(state: WebsiteState, plan: WebsitePlan) -> List[str]:
    """Check if all planned sections are present in the generated website."""
    generated_types = {s.type for s in state.sections}
    missing = [req for req in plan.planned_sections if req not in generated_types]
    return missing


# -----------------------------------------------------------------------------
# Fallback Generators (Generic + Named Reference Demos)
# -----------------------------------------------------------------------------

def create_generic_fallback_website(brief: str, plan: Optional[WebsitePlan] = None) -> WebsiteState:
    """
    Generate a complete, high-quality generic fallback website for any business
    using the planned sections without hardcoded business-specific mappings.
    """
    title = plan.suggested_title if plan else "Modern Business Studio"
    sections_to_build = plan.planned_sections if plan else ["hero", "features", "pricing", "testimonials", "contact"]
    font = plan.typography if plan else "Inter, sans-serif"
    palette = plan.color_scheme if plan else {
        "background": "#FDFBF7",
        "primary_color": "#2563EB",
        "text_color": "#1E293B",
    }
    layout_prefs = plan.layout_preferences if plan else {}

    sections: List[Section] = []
    type_counts: dict[str, int] = {}

    for s_type in sections_to_build:
        count = type_counts.get(s_type, 0) + 1
        type_counts[s_type] = count
        sec_id = f"{s_type}-{count}"
        l_var = layout_prefs.get(s_type, "default")

        if s_type == "hero":
            sections.append(
                Section(
                    id=sec_id,
                    type="hero",
                    content={
                        "title": f"Exceptional Quality & Care at {title}",
                        "subtitle": "Discover our dedicated services designed with passion, precision, and a commitment to excellence.",
                        "pill_badge": "✨ Professional Service & Support",
                        "cta_text": "Get Started",
                        "cta_link": "#contact-1",
                        "secondary_cta_text": "Explore Packages",
                        "secondary_cta_link": "#pricing-1",
                        "trust_points": ["Certified Experts", "100% Satisfaction Guarantee", "Dedicated Support"],
                        "rating": "Client rating 4.9★",
                        "highlight_service": "Premier Service Package",
                        "image_description": f"Professional showcase photography for {title}",
                    },
                    style=SectionStyle(alignment="left", padding="large", layout_variant=l_var),
                )
            )
        elif s_type == "features":
            sections.append(
                Section(
                    id=sec_id,
                    type="features",
                    content={
                        "heading": "Services Built Around Your Needs",
                        "subheading": "Carefully tailored solutions delivered with attention to every detail.",
                        "items": [
                            {
                                "title": "Comprehensive Consultation",
                                "description": "We understand your specific goals and provide personalized recommendations.",
                                "icon": "🎯",
                                "tag": "Personalized",
                            },
                            {
                                "title": "Master Craftsmanship",
                                "description": "Decades of combined experience ensuring top-tier execution and lasting results.",
                                "icon": "⭐",
                                "tag": "Expertise",
                            },
                            {
                                "title": "Transparent Process",
                                "description": "Clear timelines, open communication, and no unexpected surprises along the way.",
                                "icon": "💎",
                                "tag": "Trusted",
                            },
                            {
                                "title": "Ongoing Support",
                                "description": "Dedicated assistance and follow-up care to ensure complete client satisfaction.",
                                "icon": "✨",
                                "tag": "Support",
                            },
                        ],
                    },
                    style=SectionStyle(alignment="center", padding="large", layout_variant=l_var),
                )
            )
        elif s_type == "pricing":
            sections.append(
                Section(
                    id=sec_id,
                    type="pricing",
                    content={
                        "heading": "Transparent Packages & Pricing",
                        "subheading": "Straightforward rates designed to suit your project scope.",
                        "plans": [
                            {
                                "name": "Essential",
                                "price": "$79",
                                "description": "Perfect for essential needs and quick turnaround.",
                                "features": ["Core service delivery", "Quality assurance check", "Direct phone/email support"],
                                "cta_text": "Choose Essential",
                            },
                            {
                                "name": "Professional",
                                "price": "$149",
                                "description": "Our most popular complete solution for maximum value.",
                                "features": [
                                    "All Essential features",
                                    "Priority scheduling",
                                    "Comprehensive service review",
                                    "Dedicated client manager",
                                ],
                                "cta_text": "Choose Professional",
                                "highlighted": True,
                            },
                            {
                                "name": "Enterprise / Custom",
                                "price": "$249",
                                "description": "Full-service package tailored to advanced requirements.",
                                "features": [
                                    "All Professional features",
                                    "Custom specifications",
                                    "Extended warranty / guarantee",
                                    "24/7 VIP assistance",
                                ],
                                "cta_text": "Choose Custom",
                            },
                        ],
                    },
                    style=SectionStyle(alignment="center", padding="large", variant="card", layout_variant=l_var),
                )
            )
        elif s_type == "testimonials":
            sections.append(
                Section(
                    id=sec_id,
                    type="testimonials",
                    content={
                        "heading": "Trusted by Satisfied Clients",
                        "subheading": "Hear directly from people who have experienced our service.",
                        "items": [
                            {
                                "quote": "Working with this team was an effortless experience. Their attention to detail and care exceeded my expectations!",
                                "author": "Emily Richardson",
                                "role": "Verified Client",
                            },
                            {
                                "quote": "Remarkable professionalism and genuine dedication. I highly recommend them to anyone seeking top quality.",
                                "author": "Michael Chang",
                                "role": "Long-term Customer",
                            },
                            {
                                "quote": "Fast, courteous, and impeccably reliable. They delivered exactly what they promised on time.",
                                "author": "Sarah Bennett",
                                "role": "Community Member",
                            },
                        ],
                    },
                    style=SectionStyle(alignment="center", padding="large", layout_variant=l_var),
                )
            )
        elif s_type == "contact":
            sections.append(
                Section(
                    id=sec_id,
                    type="contact",
                    content={
                        "heading": "Get in Touch & Book Today",
                        "subheading": "Send us your inquiry or visit us during normal operating hours.",
                        "email": "contact@studio.com",
                        "phone": "(555) 234-5678",
                        "hours": "Monday – Saturday: 9:00 AM – 6:00 PM",
                        "fields": ["Your Full Name", "Email or Phone", "Service Requested", "Preferred Date & Notes"],
                    },
                    style=SectionStyle(alignment="center", padding="large"),
                )
            )
        elif s_type == "text":
            sections.append(
                Section(
                    id=sec_id,
                    type="text",
                    content={
                        "heading": f"About {title}",
                        "subheading": "Our Story & Core Philosophy",
                        "body": "Founded with a mission to bring craft, care, and integrity to our industry, we take pride in delivering exceptional experiences every single day.\n\nEvery member of our team is trained, certified, and committed to upholding the highest standards of safety, quality, and hospitality.",
                    },
                    style=SectionStyle(alignment="left", padding="large"),
                )
            )
        elif s_type == "image":
            sections.append(
                Section(
                    id=sec_id,
                    type="image",
                    content={
                        "alt": f"{title} Showcase",
                        "caption": f"Behind the scenes at {title}",
                        "image_description": f"Artisanal craftsmanship and team at work in {title}",
                    },
                    style=SectionStyle(alignment="center", padding="medium"),
                )
            )
        elif s_type == "cta":
            sections.append(
                Section(
                    id=sec_id,
                    type="cta",
                    content={
                        "heading": "Ready to Experience the Difference?",
                        "subheading": "Take the next step with our team today and enjoy our satisfaction guarantee.",
                        "button_text": "Book an Appointment",
                        "button_link": "#contact-1",
                    },
                    style=SectionStyle(alignment="center", padding="large"),
                )
            )

    return WebsiteState(
        title=title,
        version=1,
        theme=ThemeConfig(
            background=palette.get("background", "#FDFBF7"),
            primary_color=palette.get("primary_color", "#2563EB"),
            text_color=palette.get("text_color", "#1E293B"),
            font_family=font,
        ),
        sections=sections,
    )


def create_pet_grooming_fallback_website() -> WebsiteState:
    """Reference demo preset for pet grooming briefs (matching design specifications)."""
    return WebsiteState(
        title="Pawfect Grooming",
        version=1,
        theme=ThemeConfig(
            background="#FDFBF7",
            primary_color="#FF7043",
            text_color="#1E293B",
            font_family="Plus Jakarta Sans, sans-serif",
        ),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={
                    "title": "Fresh cuts, clean coats, and happy tails.",
                    "subtitle": "Give your pet a gentle, stress-free grooming experience with expert care, spa-style baths, breed-specific cuts, and lots of love.",
                    "pill_badge": "✨ Trusted local pet spa for dogs and cats",
                    "cta_text": "Book a Groom",
                    "cta_link": "#contact-1",
                    "secondary_cta_text": "View Services",
                    "secondary_cta_link": "#features-1",
                    "trust_points": ["Gentle handling", "Safe products", "Personalized care"],
                    "rating": "Client rating 4.9★",
                    "highlight_service": "Bath + Brush + Nail Trim",
                    "image_description": "Friendly dog in a warm boutique pet spa",
                },
                style=SectionStyle(alignment="left", padding="large", layout_variant="split"),
            ),
            Section(
                id="features-1",
                type="features",
                content={
                    "heading": "Services that make pets look and feel amazing",
                    "subheading": "Simple, clear service cards help visitors understand what you offer right away.",
                    "items": [
                        {"title": "Haircut", "description": "Custom breed styling and precision clipping by gentle master groomers.", "icon": "✂️", "tag": "Styling"},
                        {"title": "Bath", "description": "Hypoallergenic warm bubble bath with organic coat conditioner.", "icon": "🛁", "tag": "Spa"},
                        {"title": "Nail Care", "description": "Safe claw clipping and smoothing to keep paws healthy.", "icon": "🐾", "tag": "Hygiene"},
                        {"title": "Blueberry Facial", "description": "Tearless brightening facial scrub that removes stains.", "icon": "🫐", "tag": "Luxury"},
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="pill_cards"),
            ),
            Section(
                id="pricing-1",
                type="pricing",
                content={
                    "heading": "Our packages",
                    "subheading": "Sed mollis, eros et ultrices tempus, mauris ipsum aliquam libero.",
                    "plans": [
                        {
                            "name": "Basic grooming",
                            "price": "$150.00 USD",
                            "description": "Pets needing regular maintenance with no major grooming requirements.",
                            "features": ["relaxing bath", "brushing", "ear cleaning", "nail trimming"],
                            "cta_text": "get started",
                        },
                        {
                            "name": "Standard grooming",
                            "price": "$250.00 USD",
                            "description": "Pets that need a full grooming session including a fresh haircut.",
                            "features": ["same as basic+", "haircut", "teeth brushing", "basic medical check"],
                            "cta_text": "get started",
                            "highlighted": True,
                        },
                        {
                            "name": "Pro grooming",
                            "price": "$400.00 USD",
                            "description": "Pets requiring extra attention to their coat, teeth, and skin care.",
                            "features": ["same as standard +", "de-shedding", "coat whitening", "extra medical check"],
                            "cta_text": "get started",
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="cards"),
            ),
            Section(
                id="testimonials-1",
                type="testimonials",
                content={
                    "heading": "What pet parents are saying",
                    "subheading": "Over 500 happy dogs and cats have enjoyed our boutique grooming spa.",
                    "items": [
                        {
                            "quote": "The team at Pawfect handled my anxious dog with unbelievable patience. He came home looking fabulous and completely relaxed!",
                            "author": "Jessica Miller",
                            "role": "Owner of Milo (Golden Doodle)",
                            "rating": 5,
                        },
                        {
                            "quote": "Best grooming in town! Clean facility, transparent pricing, and wonderful staff. Highly recommended.",
                            "author": "David Chen",
                            "role": "Owner of Bella (French Bulldog)",
                            "rating": 5,
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="grid"),
            ),
            Section(
                id="contact-1",
                type="contact",
                content={
                    "heading": "Book Your Pet's Spa Day",
                    "subheading": "Appointments fill quickly. Reserve your slot or contact us directly.",
                    "phone": "(555) 729-3328",
                    "email": "hello@pawfectgrooming.com",
                    "hours": "Mon - Sat: 8:00 AM - 6:00 PM",
                    "fields": ["Owner's Name", "Pet Breed & Name", "Service Desired", "Preferred Date & Time"],
                },
                style=SectionStyle(alignment="center", padding="large"),
            ),
        ],
    )


def create_fitness_fallback_website() -> WebsiteState:
    """Reference demo preset for fitness studio briefs."""
    return WebsiteState(
        title="PulseFit Studio",
        version=1,
        theme=ThemeConfig(
            background="#0F172A",
            primary_color="#F97316",
            text_color="#F8FAFC",
            font_family="Inter, sans-serif",
        ),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={
                    "title": "Transform Your Body & Mind",
                    "subtitle": "High-intensity interval training, strength conditioning, and personalized wellness coaching designed to unlock your ultimate athletic potential.",
                    "pill_badge": "⚡ High-Performance Training",
                    "cta_text": "Claim Free Trial",
                    "cta_link": "#contact-1",
                    "secondary_cta_text": "Explore Packages",
                    "secondary_cta_link": "#pricing-1",
                    "trust_points": ["Certified Elite Coaches", "State-of-the-art Equipment", "Results Guaranteed"],
                    "rating": "4.9★ from 300+ Athletes",
                    "highlight_service": "Unlimited HIIT Classes",
                    "image_description": "Modern dark athletic gym with barbells and intense lighting",
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="centered"),
            ),
            Section(
                id="features-1",
                type="features",
                content={
                    "heading": "Built for Peak Performance",
                    "subheading": "Every workout is programmed by world-class exercise physiologists.",
                    "items": [
                        {"title": "Functional HIIT", "description": "High-octane metabolic intervals combining cardio endurance with strength.", "icon": "🔥", "tag": "Endurance"},
                        {"title": "Olympic Lifting", "description": "Structured barbell technique and heavy strength progression coaching.", "icon": "🏋️", "tag": "Strength"},
                        {"title": "Recovery Lounge", "description": "Contrast hydrotherapy, infrared sauna, and targeted compression boots.", "icon": "🧊", "tag": "Recovery"},
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="grid"),
            ),
            Section(
                id="pricing-1",
                type="pricing",
                content={
                    "heading": "Membership Plans & Passes",
                    "subheading": "No hidden fees, no lock-in contracts. Cancel anytime with 7 days notice.",
                    "plans": [
                        {
                            "name": "Standard Access",
                            "price": "$89 / mo",
                            "description": "Ideal for independent athletes focusing on open gym training.",
                            "features": ["Full facility access", "Locker & towel service", "Fitness assessment"],
                            "cta_text": "Join Standard",
                        },
                        {
                            "name": "Unlimited Performance",
                            "price": "$169 / mo",
                            "description": "Our most popular tier for daily coached group training.",
                            "features": ["Unlimited coached classes", "Monthly nutrition review", "Recovery suite access", "Guest passes"],
                            "cta_text": "Claim Free Trial",
                            "highlighted": True,
                        },
                        {
                            "name": "1-on-1 Coaching",
                            "price": "$299 / mo",
                            "description": "Direct personal training paired with tailored macro planning.",
                            "features": ["2 weekly private sessions", "Bespoke workout split", "24/7 coach messaging"],
                            "cta_text": "Book Consultation",
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="table"),
            ),
            Section(
                id="testimonials-1",
                type="testimonials",
                content={
                    "heading": "Real Results from Real Members",
                    "subheading": "Hear how PulseFit transformed our members' lives and fitness routines.",
                    "items": [
                        {
                            "quote": "Joining PulseFit was the best health decision I've ever made. The coaches hold you accountable and the community is unmatched.",
                            "author": "Marcus Vance",
                            "role": "Member for 2 years",
                            "rating": 5,
                        },
                        {
                            "quote": "Lost 25 lbs in 6 months while building real functional strength. The programming actually works!",
                            "author": "Elena Rostova",
                            "role": "Marathon Runner & Athlete",
                            "rating": 5,
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="spotlight"),
            ),
            Section(
                id="contact-1",
                type="contact",
                content={
                    "heading": "Start Your 7-Day Free Trial",
                    "subheading": "Drop in, meet our coaches, and experience the PulseFit energy firsthand.",
                    "phone": "(555) 987-6543",
                    "email": "train@pulsefitstudio.com",
                    "hours": "Mon - Fri: 5:00 AM - 9:00 PM | Sat - Sun: 7:00 AM - 6:00 PM",
                    "fields": ["Full Name", "Email Address", "Phone Number", "Fitness Goals"],
                },
                style=SectionStyle(alignment="center", padding="large"),
            ),
        ],
    )


def create_deterministic_fallback_website(brief: str, plan: Optional[WebsitePlan] = None) -> WebsiteState:
    """
    Unified fallback selector.
    Uses generic fallback by default; retains named fitness and pet grooming demo presets if useful.
    """
    lower_brief = (brief or "").lower()
    if "pet" in lower_brief and "groom" in lower_brief:
        return create_pet_grooming_fallback_website()
    if "fitness" in lower_brief and "gym" in lower_brief:
        return create_fitness_fallback_website()
    return create_generic_fallback_website(brief, plan)


# -----------------------------------------------------------------------------
# Main Generation Pipeline with Section Completeness & Bounded Repair
# -----------------------------------------------------------------------------

def generate_website_json(
    brief: str,
    plan: WebsitePlan,
    provider: Optional[BaseProvider] = None,
) -> Tuple[WebsiteState, dict]:
    """
    Generate valid WebsiteState from brief and plan using LLM provider.
    Validates output with Pydantic and executes one repair retry if needed.
    Enforces section completeness ensuring all planned sections are generated.
    Returns (WebsiteState, metadata_dict).
    """
    active_provider = provider or get_provider()

    user_prompt = f"""Generate a full WebsiteState JSON for the following brief and plan:

WEBSITE BRIEF:
"{brief.strip()}"

PLAN DETAILS:
- Business Type: {plan.business_type}
- Tone and Style: {plan.tone_and_style}
- Primary Goal: {plan.primary_goal}
- Title: {plan.suggested_title}
- Typography: {plan.typography}
- Sections to Include (in order): {plan.planned_sections}
- Chosen Layout Variants: {json.dumps(plan.layout_preferences)}
- Color Palette: {json.dumps(plan.color_scheme)}

Return strictly valid JSON matching WebsiteState schema.
You MUST generate every single section in planned_sections: {plan.planned_sections}.
For each section, assign 'layout_variant' in its 'style' object (e.g. style: {{"layout_variant": "...", "alignment": "...", "padding": "large"}}).
Make sure each section has a unique ID (e.g. hero-1, features-1, pricing-1, testimonials-1, contact-1), valid type, rich detailed content, and valid internal CTA anchors (e.g. '#contact-1', '#pricing-1', '#features-1')."""

    metadata = {
        "provider": active_provider.config.provider,
        "model": active_provider.config.model,
        "repaired": False,
        "is_fallback": False,
        "fallback_reason": None,
        "validation_errors": [],
    }

    response = active_provider.complete(
        prompt=user_prompt,
        system_prompt=GENERATOR_SYSTEM_PROMPT,
        temperature=0.2,
    )

    # Provider execution failure -> use fallback
    if not response.success or not response.content:
        logger.warning("Website Generator LLM failed: %s. Using fallback.", response.error)
        metadata["is_fallback"] = True
        metadata["fallback_reason"] = response.error or "LLM Provider endpoint unreachable"
        return create_deterministic_fallback_website(brief, plan), metadata

    parsed_json = extract_json_from_text(response.content)

    # First validation attempt (Pydantic schema + section completeness)
    if parsed_json:
        try:
            state = WebsiteState.model_validate(parsed_json)
            missing = validate_section_completeness(state, plan)
            if not missing:
                return state, metadata
            # Section completeness violation
            msg = f"Generated website is missing required planned sections: {missing}. Expected all: {plan.planned_sections}."
            logger.warning("Section completeness failed: %s. Initiating one bounded repair.", msg)
            metadata["validation_errors"].append(f"Attempt 1: {msg}")
        except (ValidationError, Exception) as err:
            logger.warning("First validation attempt failed: %s. Initiating one bounded repair.", str(err))
            metadata["validation_errors"].append(f"Attempt 1: {str(err)}")
    else:
        logger.warning("Could not extract JSON from LLM output. Initiating one bounded repair.")
        metadata["validation_errors"].append("Attempt 1: Could not parse JSON from output.")

    # One Bounded Repair Attempt
    metadata["repaired"] = True
    error_summary = "; ".join(metadata["validation_errors"])
    repair_prompt = f"""Your previous response failed validation:
{error_summary}

Please fix the issue and return ONLY the corrected, strictly valid JSON matching WebsiteState:
{{
  "title": "{plan.suggested_title}",
  "version": 1,
  "theme": {{
    "background": "{plan.color_scheme.get('background', '#FDFBF7')}",
    "primary_color": "{plan.color_scheme.get('primary_color', '#2563EB')}",
    "text_color": "{plan.color_scheme.get('text_color', '#1E293B')}",
    "font_family": "{plan.typography}"
  }},
  "sections": [
    ... MUST generate ALL planned sections in order: {plan.planned_sections} ...
  ]
}}
Raw Output to fix:
{response.content[:800]}
"""

    repair_response = active_provider.complete(
        prompt=repair_prompt,
        system_prompt="You are a JSON repair specialist. Output ONLY strictly valid JSON matching the schema and include all required sections.",
        temperature=0.0,
    )

    if repair_response.success and repair_response.content:
        repaired_json = extract_json_from_text(repair_response.content)
        if repaired_json:
            try:
                state = WebsiteState.model_validate(repaired_json)
                missing_after_repair = validate_section_completeness(state, plan)
                if not missing_after_repair:
                    return state, metadata
                metadata["validation_errors"].append(
                    f"Attempt 2 (Repair): Still missing sections: {missing_after_repair}"
                )
                raise WebsiteGenerationError(
                    f"Website generation failed section completeness after 1 repair attempt. Missing: {missing_after_repair}"
                )
            except (ValidationError, Exception) as repair_err:
                metadata["validation_errors"].append(f"Attempt 2 (Repair): {str(repair_err)}")
                raise WebsiteGenerationError(
                    f"Website generation failed schema validation after 1 repair attempt: {repair_err}"
                )

    raise WebsiteGenerationError(
        f"Website generation failed: Invalid JSON or schema violation after 1 repair attempt. Errors: {metadata['validation_errors']}"
    )
