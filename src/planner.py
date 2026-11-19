"""
Planner module for SitePilot AI.
Extracts business type, style, goals, planned sections, layout strategy,
typography, background style, form type, and layout variants from a user brief.
Ensures comprehensive section coverage and high design diversity without hardcoded templates.
"""

import logging
import re
from typing import List, Optional
from src.schema import WebsitePlan, SUPPORTED_SECTION_TYPES, SectionTypeLiteral
from src.providers.base import BaseProvider
from src.providers.factory import get_provider
from src.json_utils import extract_json_from_text

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = f"""You are an elite website architect and creative director.
Your job is to thoroughly analyze the user's website brief and construct a complete, structured website plan that ensures high visual and structural diversity.

REQUIREMENTS:
1. Extract ALL requested features, capabilities, and sections from the brief:
   - If pricing/plans/packages mentioned -> MUST include 'pricing'
   - If reviews/testimonials/stories mentioned -> MUST include 'testimonials'
   - If contact/form/booking/demo/inquiries mentioned -> MUST include 'contact'
   - If services/features/offerings mentioned -> MUST include 'features'
   - If gallery/portfolio/photos mentioned -> MUST include 'image'
   - If about/story/mission mentioned -> MUST include 'text'
   - Every website MUST have a 'hero' section at the top.
   Allowed section types are ONLY: {SUPPORTED_SECTION_TYPES}.

2. Determine a unique Design Direction tailored to the business category:
   - layout_strategy: 'luxury_editorial' | 'saas_modern' | 'artisan_storefront' | 'portfolio_showcase' | 'bold_promotional'
   - hero_variant: 'split' | 'centered' | 'minimal' | 'editorial_showcase' | 'storefront'
   - nav_style: 'sticky_glass' | 'floating_pill' | 'clean_minimal' | 'centered_brand'
   - nav_cta_text: e.g. "Book Consultation", "Request Demo", "Order Fresh", "Claim Trial"
   - nav_cta_link: destination anchor, typically '#appointment-form' or '#contact-1'
   - typography: Body font ('Inter, sans-serif', 'Plus Jakarta Sans, sans-serif', 'Roboto, sans-serif')
   - heading_font: Distinctive heading font ('Playfair Display, serif', 'Outfit, sans-serif', 'Plus Jakarta Sans, sans-serif', 'Inter, sans-serif')
   - background_style: 'solid' | 'warm_ivory' | 'dark_glow' | 'editorial_cream' | 'tech_dark' | 'gradient_mesh'
   - brand_icon: A single appropriate emoji symbol (e.g. 🏛️, 🛡️, 🥐, ⚡, 🐾, 💎)
   - form_type: 'booking' | 'demo' | 'inquiry' | 'signup' | 'contact'
   - form_fields: 4-6 business-specific field names (e.g. for interior design: ["Full Name", "Email & Phone", "Project Scope", "Estimated Budget", "Timeline"])
   - layout_preferences:
     * hero: 'split' | 'centered' | 'minimal' | 'editorial_showcase' | 'storefront'
     * features: 'grid' | 'pill_cards' | 'list'
     * pricing: 'cards' | 'table'
     * testimonials: 'grid' | 'spotlight'
   - color_scheme: background (hex), primary_color (hex), text_color (hex)

You must output ONLY valid JSON matching this schema:
{{
  "business_type": "<e.g., Luxury Interior Design Studio, Enterprise Cloud Security SaaS, Artisan Sourdough Bakery>",
  "tone_and_style": "<e.g., Architectural and refined, High-tech and authoritative, Warm and appetizing>",
  "primary_goal": "<e.g., Book design consultation, Request interactive demo, Order fresh loaves>",
  "planned_sections": ["hero", "features", "pricing", "testimonials", "contact"],
  "suggested_title": "<Concise brand name>",
  "layout_strategy": "luxury_editorial",
  "hero_variant": "editorial_showcase",
  "nav_style": "clean_minimal",
  "nav_cta_text": "Book Consultation",
  "nav_cta_link": "#appointment-form",
  "typography": "Plus Jakarta Sans, sans-serif",
  "heading_font": "Playfair Display, serif",
  "background_style": "editorial_cream",
  "brand_icon": "🏛️",
  "form_type": "inquiry",
  "form_fields": ["Full Name", "Email & Phone", "Project Scope", "Estimated Budget", "Timeline"],
  "layout_preferences": {{
    "hero": "editorial_showcase",
    "features": "list",
    "pricing": "cards",
    "testimonials": "spotlight"
  }},
  "color_scheme": {{
    "background": "#FDFBF7",
    "primary_color": "#936F38",
    "text_color": "#1C1917"
  }}
}}
Return ONLY raw JSON without markdown code fences or explanatory text.
"""


def extract_sections_generically_from_brief(brief: str) -> List[SectionTypeLiteral]:
    """Generically parse brief to detect explicitly requested section types."""
    b = brief.lower()
    sections: List[SectionTypeLiteral] = ["hero"]

    if any(k in b for k in ("feature", "service", "what we do", "offering", "benefit", "class", "capability")):
        sections.append("features")
    else:
        sections.append("features")

    if any(k in b for k in ("price", "pricing", "cost", "plan", "package", "membership", "tier", "subscription")):
        sections.append("pricing")

    if any(k in b for k in ("testimonial", "review", "story", "client", "customer say", "feedback")):
        sections.append("testimonials")

    if any(k in b for k in ("about", "story", "mission", "philosophy")):
        sections.append("text")

    if any(k in b for k in ("photo", "gallery", "portfolio", "picture", "showcase", "interior", "image")):
        sections.append("image")

    if any(k in b for k in ("cta", "call to action", "banner")):
        sections.append("cta")

    if any(k in b for k in ("contact", "form", "book", "appointment", "inquir", "reach out", "touch", "demo", "order")):
        sections.append("contact")
    else:
        sections.append("contact")

    # If neither pricing nor testimonials were explicitly detected, ensure standard complete landing page
    if "pricing" not in sections and "image" not in sections:
        sections.insert(-1, "pricing")
    if "testimonials" not in sections:
        sections.insert(-1, "testimonials")

    return sections


def create_generic_fallback_plan(brief: str) -> WebsitePlan:
    """
    Generate a tailored fallback plan when LLM is unavailable,
    detecting visual directions dynamically from brief context.
    """
    b = (brief or "").lower()
    sections = extract_sections_generically_from_brief(brief)

    # 1. Luxury Interior Design Studio / Architecture
    if any(k in b for k in ("interior", "architect", "decor", "home styling", "renovation", "luxury living")):
        return WebsitePlan(
            business_type="Luxury Interior Design Studio",
            tone_and_style="Architectural, refined, bespoke luxury",
            primary_goal="Schedule private interior design consultation",
            planned_sections=sections if "image" in sections else ["hero", "features", "image", "testimonials", "contact"],
            suggested_title="Aura Interior Architecture",
            layout_strategy="luxury_editorial",
            hero_variant="editorial_showcase",
            nav_style="clean_minimal",
            nav_cta_text="Book Consultation",
            nav_cta_link="#appointment-form",
            typography="Plus Jakarta Sans, sans-serif",
            heading_font="Playfair Display, serif",
            background_style="editorial_cream",
            brand_icon="🏛️",
            form_type="inquiry",
            form_fields=[
                "Full Name",
                "Email & Phone",
                "Project Scope (Residential / Commercial)",
                "Estimated Budget Range",
                "Property Location",
                "Design Timeline & Vision",
            ],
            layout_preferences={
                "hero": "editorial_showcase",
                "features": "list",
                "pricing": "cards",
                "testimonials": "spotlight",
            },
            color_scheme={
                "background": "#FDFBF7",
                "primary_color": "#936F38",
                "text_color": "#1C1917",
            },
        )

    # 2. Cloud Security / Enterprise SaaS / Software
    if any(k in b for k in ("security", "saas", "cyber", "cloud", "software", "devops", "soc2", "infosec")):
        return WebsitePlan(
            business_type="Enterprise Cloud Security SaaS",
            tone_and_style="High-tech, secure, authoritative, modern",
            primary_goal="Request an interactive live enterprise security demo",
            planned_sections=sections if "pricing" in sections else ["hero", "features", "pricing", "testimonials", "contact"],
            suggested_title="ShieldCloud Security",
            layout_strategy="saas_modern",
            hero_variant="centered",
            nav_style="sticky_glass",
            nav_cta_text="Request Live Demo",
            nav_cta_link="#appointment-form",
            typography="Inter, sans-serif",
            heading_font="Outfit, sans-serif",
            background_style="tech_dark",
            brand_icon="🛡️",
            form_type="demo",
            form_fields=[
                "Work Email",
                "Full Name",
                "Company Name",
                "Cloud Provider (AWS/GCP/Azure)",
                "Total Cloud Workloads",
                "Preferred Demo Date",
            ],
            layout_preferences={
                "hero": "centered",
                "features": "grid",
                "pricing": "table",
                "testimonials": "grid",
            },
            color_scheme={
                "background": "#0A0F1D",
                "primary_color": "#00D2FF",
                "text_color": "#F8FAFC",
            },
        )

    # 3. Artisan Bakery / Cafe / Culinary
    if any(k in b for k in ("bakery", "bread", "sourdough", "croissant", "pastry", "flour", "cafe", "baker")):
        return WebsitePlan(
            business_type="Artisan Sourdough Bakery",
            tone_and_style="Warm, rustic, appetizing, authentic",
            primary_goal="Order fresh sourdough loaves and catering",
            planned_sections=sections if "pricing" in sections else ["hero", "features", "pricing", "testimonials", "contact"],
            suggested_title="Crust & Crumb Bakery",
            layout_strategy="artisan_storefront",
            hero_variant="storefront",
            nav_style="floating_pill",
            nav_cta_text="Order Fresh Bakes",
            nav_cta_link="#appointment-form",
            typography="Inter, sans-serif",
            heading_font="Plus Jakarta Sans, sans-serif",
            background_style="warm_ivory",
            brand_icon="🥐",
            form_type="order",
            form_fields=[
                "Customer Name",
                "Phone Number",
                "Items Needed (Sourdough / Pastries)",
                "Pickup Date & Time",
                "Special Inscription / Requests",
            ],
            layout_preferences={
                "hero": "storefront",
                "features": "pill_cards",
                "pricing": "cards",
                "testimonials": "grid",
            },
            color_scheme={
                "background": "#FFFBEB",
                "primary_color": "#D97706",
                "text_color": "#1F2937",
            },
        )

    # 4. Fallback for other general businesses
    words = [w for w in re.sub(r"[^\w\s]", "", brief).split() if len(w) > 2]
    title = f"{words[0].capitalize()} Studio" if words else "Modern Studio"

    return WebsitePlan(
        business_type="Professional Business",
        tone_and_style="Clean, modern, and accessible",
        primary_goal="Engage visitors and generate customer inquiries",
        planned_sections=sections,
        suggested_title=title,
        layout_strategy="modern_showcase",
        hero_variant="split",
        nav_style="sticky_glass",
        nav_cta_text="Get Started",
        nav_cta_link="#appointment-form",
        typography="Inter, sans-serif",
        heading_font="Inter, sans-serif",
        background_style="solid",
        brand_icon="✨",
        form_type="contact",
        form_fields=["Full Name", "Email Address", "Phone Number", "Service Needed", "Message"],
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
    Uses contextual generic fallback by default; retains pet and fitness demo presets.
    """
    lower_brief = (brief or "").lower()

    if "pet" in lower_brief or "groom" in lower_brief:
        return WebsitePlan(
            business_type="Boutique Pet Grooming & Spa",
            tone_and_style="Warm, playful, trustworthy, and caring",
            primary_goal="Book pet grooming appointments",
            planned_sections=["hero", "features", "pricing", "testimonials", "contact"],
            suggested_title="Pawfect Grooming",
            layout_strategy="modern_showcase",
            hero_variant="split",
            nav_style="sticky_glass",
            nav_cta_text="Book a Groom",
            nav_cta_link="#appointment-form",
            typography="Plus Jakarta Sans, sans-serif",
            heading_font="Plus Jakarta Sans, sans-serif",
            background_style="warm_ivory",
            brand_icon="🐾",
            form_type="booking",
            form_fields=["Owner's Name", "Pet Breed & Name", "Service Desired", "Preferred Date & Time"],
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
            layout_strategy="bold_promotional",
            hero_variant="centered",
            nav_style="sticky_glass",
            nav_cta_text="Claim Free Trial",
            nav_cta_link="#appointment-form",
            typography="Inter, sans-serif",
            heading_font="Inter, sans-serif",
            background_style="dark_glow",
            brand_icon="⚡",
            form_type="booking",
            form_fields=["Full Name", "Email Address", "Phone Number", "Fitness Goals"],
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
        f"suggested_title, layout_strategy, hero_variant, nav_style, nav_cta_text, "
        f"typography, heading_font, background_style, brand_icon, form_type, form_fields, "
        f"layout_preferences, color_scheme.\n\nBrief: {brief}"
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
