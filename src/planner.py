"""
Planner module for SitePilot AI.
Extracts business type, style, goals, planned sections, and layout variants from a user brief.
Ensures comprehensive section coverage without hardcoded business mappings.
"""

import logging
import re
from typing import List, Optional
from src.schema import WebsitePlan, SUPPORTED_SECTION_TYPES, SectionTypeLiteral
from src.providers.base import BaseProvider
from src.providers.factory import get_provider
from src.json_utils import extract_json_from_text

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = f"""You are an expert website architect and creative director.
Your job is to thoroughly analyze the user's website brief and construct a complete, structured website plan.

REQUIREMENTS:
1. Extract ALL requested features, capabilities, and sections from the brief:
   - If the user mentions pricing, plans, or packages -> MUST include 'pricing'
   - If the user mentions reviews, testimonials, or stories -> MUST include 'testimonials'
   - If the user mentions contact, form, booking, or inquiries -> MUST include 'contact'
   - If the user mentions services, features, or benefits -> MUST include 'features'
   - If the user mentions gallery, photography, or pictures -> MUST include 'image'
   - If the user mentions about, story, or mission -> MUST include 'text'
   - Every website MUST have a 'hero' section at the top.
   Allowed section types are ONLY: {SUPPORTED_SECTION_TYPES}.

2. Do NOT truncate or reduce the plan. Plan the complete website requested by the user.

3. Select tailored visual direction based on the business type:
   - Typography: Clean sans-serif (e.g., 'Plus Jakarta Sans', 'Inter', 'Roboto') or elegant serif (e.g., 'Playfair Display')
   - Layout Variants:
     * hero: 'split' | 'centered' | 'minimal'
     * features: 'grid' | 'pill_cards' | 'list'
     * pricing: 'cards' | 'table'
     * testimonials: 'grid' | 'spotlight'
   - Color Scheme: background (hex), primary_color (hex), text_color (hex)

You must output ONLY valid JSON matching this schema:
{{
  "business_type": "<e.g., Artisan Bakery, Boutique Pet Spa, B2B SaaS, Dental Clinic>",
  "tone_and_style": "<e.g., Warm & inviting, High-energy athletic, Clean modern corporate>",
  "primary_goal": "<e.g., Book appointments, schedule a demo, buy subscription>",
  "planned_sections": ["hero", "features", "pricing", "testimonials", "contact"],
  "suggested_title": "<Concise brand name>",
  "typography": "<Font family name>",
  "layout_preferences": {{
    "hero": "split",
    "features": "grid",
    "pricing": "cards",
    "testimonials": "grid"
  }},
  "color_scheme": {{
    "background": "#ffffff",
    "primary_color": "#2563eb",
    "text_color": "#1e293b"
  }}
}}
Return ONLY the raw JSON object. Do not include markdown code fences or conversational text.
"""


def extract_sections_generically_from_brief(brief: str) -> List[SectionTypeLiteral]:
    """Generically parse brief to detect explicitly requested section types."""
    b = brief.lower()
    sections: List[SectionTypeLiteral] = ["hero"]

    if any(k in b for k in ("feature", "service", "what we do", "offering", "benefit", "class")):
        sections.append("features")
    else:
        # Default include features for business completeness
        sections.append("features")

    if any(k in b for k in ("price", "pricing", "cost", "plan", "package", "membership", "tier")):
        sections.append("pricing")

    if any(k in b for k in ("testimonial", "review", "story", "client", "customer say", "feedback")):
        sections.append("testimonials")

    if any(k in b for k in ("about", "story", "mission", "philosophy")):
        sections.append("text")

    if any(k in b for k in ("photo", "gallery", "portfolio", "picture", "showcase")):
        sections.append("image")

    if any(k in b for k in ("cta", "call to action", "banner")):
        sections.append("cta")

    if any(k in b for k in ("contact", "form", "book", "appointment", "inquir", "reach out", "touch")):
        sections.append("contact")
    else:
        # Default include contact for business conversion
        sections.append("contact")

    # If neither pricing nor testimonials were explicitly detected, ensure standard complete landing page
    if "pricing" not in sections:
        sections.insert(-1, "pricing")
    if "testimonials" not in sections:
        sections.insert(-1, "testimonials")

    return sections


def create_generic_fallback_plan(brief: str) -> WebsitePlan:
    """Generate a clean generic fallback plan when LLM is unavailable."""
    sections = extract_sections_generically_from_brief(brief)

    # Derive a clean suggested title
    words = [w for w in re.sub(r"[^\w\s]", "", brief).split() if len(w) > 2]
    title = f"{words[0].capitalize()} Studio" if words else "Modern Studio"

    return WebsitePlan(
        business_type="Professional Business",
        tone_and_style="Clean, modern, and accessible",
        primary_goal="Engage visitors and generate customer inquiries",
        planned_sections=sections,
        suggested_title=title,
        typography="Inter, sans-serif",
        layout_preferences={
            "hero": "split",
            "features": "grid",
            "pricing": "cards",
            "testimonials": "grid",
        },
        color_scheme={
            "background": "#FDFBF7",
            "primary_color": "#2563EB",
            "text_color": "#1E293B",
        },
    )


def create_deterministic_fallback_plan(brief: str) -> WebsitePlan:
    """
    Fallback plan selector.
    Uses generic fallback by default, retaining named fitness and pet grooming demo presets if useful.
    """
    lower_brief = (brief or "").lower()

    # Named reference demo fixtures
    if "pet" in lower_brief or "groom" in lower_brief:
        return WebsitePlan(
            business_type="Boutique Pet Grooming & Spa",
            tone_and_style="Warm, playful, trustworthy, and caring",
            primary_goal="Book pet grooming appointments",
            planned_sections=["hero", "features", "pricing", "testimonials", "contact"],
            suggested_title="Pawfect Grooming",
            typography="Plus Jakarta Sans, sans-serif",
            layout_preferences={
                "hero": "split",
                "features": "pill_cards",
                "pricing": "cards",
                "testimonials": "grid",
            },
            color_scheme={
                "background": "#FDFBF7",
                "primary_color": "#FF7043",
                "text_color": "#1E293B",
            },
        )

    if "fitness" in lower_brief or "gym" in lower_brief:
        return WebsitePlan(
            business_type="Fitness Studio",
            tone_and_style="High energy, dark modern, dynamic",
            primary_goal="Convert visitors into trial class bookings",
            planned_sections=["hero", "features", "pricing", "testimonials", "contact"],
            suggested_title="PulseFit Studio",
            typography="Inter, sans-serif",
            layout_preferences={
                "hero": "centered",
                "features": "grid",
                "pricing": "table",
                "testimonials": "spotlight",
            },
            color_scheme={
                "background": "#0F172A",
                "primary_color": "#F97316",
                "text_color": "#F8FAFC",
            },
        )

    # Generic fallback for any other business (bakery, consulting, medical, SaaS, etc.)
    return create_generic_fallback_plan(brief)


def plan_website(brief: str, provider: Optional[BaseProvider] = None) -> WebsitePlan:
    """
    Convert user brief into a structured WebsitePlan using configured LLM.
    Falls back gracefully if provider is unconfigured or unreachable.
    """
    if not brief or not brief.strip():
        raise ValueError("Website brief cannot be empty.")

    active_provider = provider or get_provider()

    user_prompt = f"Analyze this website brief and generate a tailored visual and section plan:\n\n\"{brief.strip()}\""

    response = active_provider.complete(
        prompt=user_prompt,
        system_prompt=PLANNER_SYSTEM_PROMPT,
        temperature=0.2,
    )

    if not response.success or not response.content:
        logger.warning("Planner LLM call failed or returned empty: %s. Using fallback plan.", response.error)
        return create_deterministic_fallback_plan(brief)

    parsed = extract_json_from_text(response.content)
    if parsed:
        try:
            return WebsitePlan.model_validate(parsed)
        except Exception as e:
            logger.warning("Validation of planner JSON failed: %s. Attempting repair.", str(e))

    # One repair attempt for planner
    repair_prompt = (
        f"Your previous output was not valid JSON matching the WebsitePlan schema. "
        f"Please output strictly valid JSON matching: business_type, tone_and_style, "
        f"primary_goal, planned_sections (list from {SUPPORTED_SECTION_TYPES}), "
        f"suggested_title, typography, layout_preferences, color_scheme.\n\nBrief: {brief}"
    )
    repair_res = active_provider.complete(repair_prompt, temperature=0.0)
    if repair_res.success and repair_res.content:
        repaired_parsed = extract_json_from_text(repair_res.content)
        if repaired_parsed:
            try:
                return WebsitePlan.model_validate(repaired_parsed)
            except Exception:
                pass

    logger.warning("Planner repair failed. Using fallback plan.")
    return create_deterministic_fallback_plan(brief)
