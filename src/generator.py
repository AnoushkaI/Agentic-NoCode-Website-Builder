"""
Website Generator module for SitePilot AI.
Produces structured WebsiteState JSON from a brief and plan, validates via Pydantic,
enforces section completeness against the plan, and provides a bounded one-step repair.
Ensures strong design diversity, tailored form fields, and rich testimonials.
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
    normalize_website_state_dict,
    normalize_section_content,
)
from src.providers.base import BaseProvider
from src.providers.factory import get_provider
from src.json_utils import extract_json_from_text
from src.image_service import retrieve_image_for_description, retrieve_image_slots

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
6. CRITICAL RULE: Do NOT include any star emojis or symbols (e.g. ⭐, ★, ✨, 🌟, ☆, 💫, 🌠) in the website title, brand name, brand_icon, or any section headings.
7. The 'theme' object MUST include:
   - "background": Background color hex
   - "primary_color": Primary brand color hex
   - "text_color": Text color hex
   - "font_family": Body font family
   - "heading_font": Distinctive heading font family (e.g. 'Playfair Display, serif', 'Outfit, sans-serif', 'Plus Jakarta Sans, sans-serif')
   - "background_style": Aesthetic style ('solid', 'warm_ivory', 'dark_glow', 'editorial_cream', 'tech_dark', 'gradient_mesh')
   - "nav_style": Navigation style ('sticky_glass', 'floating_pill', 'clean_minimal', 'centered_brand')

7. Section requirements:
   - 'hero':
     * "title": Punchy, memorable headline
     * "subtitle": 2-3 engaging sentences explaining the unique value proposition
     * "pill_badge": Short trust badge matching the brand
     * "cta_text": Primary action button text (e.g. "Book Consultation", "Request Demo", "Order Fresh")
     * "cta_link": Primary target anchor: MUST point to "#appointment-form"
     * "secondary_cta_text": Secondary action (e.g. "Explore Packages", "View Daily Menu")
     * "secondary_cta_link": Target section anchor (e.g. "#pricing-1" or "#features-1")
     * "trust_points": List of 3 key assurances
     * "rating": Social proof string (e.g. "Client rating 4.9/5")
     * "highlight_service": Short highlight
     * "brand_icon": Appropriate emoji icon (e.g. 🏛️, 🛡️, 🥐)
     * "image_description": Descriptive prompt for visual card

   - 'features':
     * "heading": Catchy section title
     * "subheading": Helpful overview paragraph
     * "items": 3-4 feature items, each having "title", "description" (2 full sentences), "icon" (emoji), and optional "tag"

   - 'pricing':
     * "heading": Section title
     * "subheading": Reassurance on transparent pricing
     * "plans": 3 distinct tiered plans, each with:
       "name", "price", "description", "features" (4-5 bullet items), "cta_text", and "highlighted": true for the recommended tier

   - 'testimonials':
     * "heading": Customer review title
     * "subheading": Social proof subtitle
     * "items": 2-3 authentic, glowing customer reviews with "quote", "author", "role", "rating": 5, and "tag": "Illustrative Client Feedback"

   - 'contact':
     * "heading": Action-oriented headline matching the business goal
     * "subheading": Helpful instructions for booking, demo, or inquiries
     * "form_type": One of 'booking', 'demo', 'inquiry', 'order', 'contact'
     * "fields": List of 4-6 business-specific form fields
     * "submit_text": Action button label (e.g. "🚀 Request Live Demo", "🏛️ Submit Studio Inquiry", "🥐 Submit Bakery Order")
     * "email": Realistic contact email
     * "phone": Realistic phone number
     * "hours": Operating hours

   - 'text':
     * "heading", "subheading", and "body" with engaging multi-paragraph story

   - 'image':
     * "image_description", "alt", and "caption"

   - 'cta':
     * "heading", "subheading", "button_text", and "button_link" pointing to "#appointment-form"

8. Output ONLY the raw JSON object. Do not wrap in markdown fences, do not add introductory commentary.
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
    using the planned sections, layout strategy, and styling without hardcoded templates.
    """
    title = plan.suggested_title if plan else "Modern Business Studio"
    sections_to_build = plan.planned_sections if plan else ["hero", "features", "pricing", "testimonials", "contact"]
    font = plan.typography if plan else "Inter, sans-serif"
    heading_font = plan.heading_font if plan else "Inter, sans-serif"
    bg_style = plan.background_style if plan else "solid"
    nav_style = plan.nav_style if plan else "sticky_glass"
    brand_icon = plan.brand_icon if plan else "🔹"
    form_type = plan.form_type if plan else "contact"
    form_fields = plan.form_fields if plan else ["Full Name", "Email Address", "Phone Number", "Service Needed", "Message"]
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
                        "pill_badge": f"{brand_icon} Premier Quality & Service".strip(),
                        "cta_text": plan.nav_cta_text if plan else "Get Started",
                        "cta_link": plan.nav_cta_link if plan else "#appointment-form",
                        "secondary_cta_text": "Explore Packages",
                        "secondary_cta_link": "#pricing-1",
                        "trust_points": ["Certified Experts", "100% Satisfaction Guarantee", "Dedicated Support"],
                        "rating": "Client rating 4.9/5",
                        "highlight_service": "Premier Service Package",
                        "brand_icon": brand_icon,
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
                                "icon": "🏆",
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
                                "icon": "🤝",
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
                        "subheading": "Real feedback from people who have experienced our service.",
                        "items": [
                            {
                                "quote": "Working with this team was an effortless experience. Their attention to detail and care exceeded my expectations!",
                                "author": "Emily Richardson",
                                "role": "Verified Client",
                                "tag": "Illustrative Client Feedback",
                                "rating": 5,
                            },
                            {
                                "quote": "Remarkable professionalism and genuine dedication. I highly recommend them to anyone seeking top quality.",
                                "author": "Michael Chang",
                                "role": "Long-term Customer",
                                "tag": "Illustrative Client Feedback",
                                "rating": 5,
                            },
                            {
                                "quote": "Fast, courteous, and impeccably reliable. They delivered exactly what they promised on time.",
                                "author": "Sarah Bennett",
                                "role": "Community Member",
                                "tag": "Illustrative Client Feedback",
                                "rating": 5,
                            },
                        ],
                    },
                    style=SectionStyle(alignment="center", padding="large", layout_variant=l_var),
                )
            )
        elif s_type == "contact":
            submit_label = (
                "🚀 Request Live Demo" if form_type == "demo"
                else "🏛️ Submit Consultation Inquiry" if form_type == "inquiry"
                else "🥐 Submit Bakery Order" if form_type == "order"
                else "📅 Book Appointment Now"
            )
            form_head = (
                "Schedule an Interactive Live Demo" if form_type == "demo"
                else "Initiate a Private Design Consultation" if form_type == "inquiry"
                else "Fresh Daily Order & Catering Request" if form_type == "order"
                else "Get in Touch & Book Today"
            )
            sections.append(
                Section(
                    id=sec_id,
                    type="contact",
                    content={
                        "heading": form_head,
                        "subheading": "Send us your inquiry and our team will get back to you shortly.",
                        "form_type": form_type,
                        "fields": form_fields,
                        "submit_text": submit_label,
                        "email": "contact@studio.com",
                        "phone": "(555) 234-5678",
                        "hours": "Monday – Saturday: 9:00 AM – 6:00 PM",
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
                        "button_link": "#appointment-form",
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
            heading_font=heading_font,
            background_style=bg_style,
            nav_style=nav_style,
        ),
        sections=sections,
    )


# -----------------------------------------------------------------------------
# Benchmark Diverse Fallback Fixtures (Luxury Design, Cloud SaaS, Artisan Bakery)
# -----------------------------------------------------------------------------

def create_luxury_interior_fallback_website() -> WebsiteState:
    """Benchmark reference preset for luxury interior design studio."""
    slots = retrieve_image_slots("luxury interior design architecture")
    return WebsiteState(
        title="Aura Interior Architecture",
        version=1,
        theme=ThemeConfig(
            background="#FDFBF7",
            primary_color="#936F38",
            text_color="#1C1917",
            font_family="Plus Jakarta Sans, sans-serif",
            heading_font="Playfair Display, serif",
            background_style="editorial_cream",
            nav_style="clean_minimal",
        ),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={
                    "title": "Bespoke Spaces Crafted for Inspired Living",
                    "subtitle": "Award-winning interior architecture studio harmonizing natural light, noble natural materials, and timeless proportions for distinguished private residences.",
                    "pill_badge": "🏛️ Bespoke Interior Architecture & Styling",
                    "cta_text": "Book Private Consultation",
                    "cta_link": "#appointment-form",
                    "secondary_cta_text": "Explore Portfolio",
                    "secondary_cta_link": "#features-1",
                    "quote": "Architecture is the learned game, correct and magnificent, of forms assembled in the light.",
                    "quote_author": "Elena Rostova, Principal Architect",
                    "image_url": slots.get("hero_url"),
                    "image_description": "Luxury minimalist living room with floor to ceiling windows and custom marble table",
                    "rating": "Architectural Digest Featured Studio",
                    "highlight_service": "Turnkey Residential Commissions",
                    "brand_icon": "🏛️",
                },
                style=SectionStyle(alignment="left", padding="large", layout_variant="editorial_showcase"),
            ),
            Section(
                id="features-1",
                type="features",
                content={
                    "heading": "Architectural Disciplines & Spatial Capabilities",
                    "subheading": "Comprehensive spatial design from structural planning through custom furnishings and final styling.",
                    "items": [
                        {
                            "title": "Spatial Architecture & Reconfiguration",
                            "description": "Reimagining interior flow, natural light axes, and structural volume to achieve harmonious daily living.",
                            "icon": "📐",
                            "tag": "Architecture",
                        },
                        {
                            "title": "Bespoke Millwork & Custom Furnishings",
                            "description": "Collaborations with world-class master artisans to design one-of-a-kind cabinetry, stone elements, and seating.",
                            "icon": "🪑",
                            "tag": "Craftsmanship",
                        },
                        {
                            "title": "Curated Lighting & Material Tactility",
                            "description": "Atmospheric architectural illumination paired with hand-selected French limestone, raw brass, and honed oak.",
                            "icon": "✨",
                            "tag": "Atmosphere",
                        },
                        {
                            "title": "Turnkey Project Administration",
                            "description": "White-glove coordination from municipal permits through contractor management and white-glove art installation.",
                            "icon": "🏛️",
                            "tag": "Turnkey",
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="list"),
            ),
            Section(
                id="image-1",
                type="image",
                content={
                    "alt": "Aura Interior Architecture Commission Portfolio",
                    "caption": "Recent residential commissions completed across Manhattan, Zurich, and Kensington.",
                    "image_url": slots.get("hero_url"),
                    "gallery": slots.get("gallery_urls", []),
                    "image_description": "Curated photographs of realized luxury penthouses and townhouses",
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="gallery"),
            ),
            Section(
                id="testimonials-1",
                type="testimonials",
                content={
                    "heading": "Patron Reflections & Architectural Honors",
                    "subheading": "Words from homeowners and residential developers who trusted our vision.",
                    "items": [
                        {
                            "quote": "Aura transformed our duplex penthouse into a serene, light-filled haven. Every millwork joint and limestone reveal was executed with peerless precision.",
                            "author": "Julian & Vivienne Sterling",
                            "role": "Tribeca Duplex Penthouse",
                            "tag": "Illustrative Client Feedback",
                            "rating": 5,
                        },
                        {
                            "quote": "Their intuitive mastery of proportions and custom lighting elevated our historic brownstone beyond anything we envisioned.",
                            "author": "Marcus Aurelius Thorne",
                            "role": "Kensington Townhouse Commission",
                            "tag": "Illustrative Client Feedback",
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
                    "heading": "Initiate Your Architectural Commission",
                    "subheading": "We accept a strictly limited number of private residential commissions each calendar year.",
                    "form_type": "inquiry",
                    "fields": [
                        "Full Name",
                        "Email Address & Telephone",
                        "Project Scope (Residential / Boutique Commercial)",
                        "Estimated Construction & FF&E Budget",
                        "Property Location & Square Footage",
                        "Target Timeline & Design Vision",
                    ],
                    "submit_text": "🏛️ Submit Consultation Inquiry",
                    "email": "inquire@aurainteriors.com",
                    "phone": "+1 (212) 555-0192",
                    "hours": "Studio Visits by Private Appointment: Mon – Fri",
                },
                style=SectionStyle(alignment="center", padding="large"),
            ),
        ],
    )


def create_cloud_security_fallback_website() -> WebsiteState:
    """Benchmark reference preset for cloud security B2B SaaS."""
    slots = retrieve_image_slots("cloud security saas tech")
    return WebsiteState(
        title="ShieldCloud Security",
        version=1,
        theme=ThemeConfig(
            background="#0A0F1D",
            primary_color="#00D2FF",
            text_color="#F8FAFC",
            font_family="Inter, sans-serif",
            heading_font="Outfit, sans-serif",
            background_style="tech_dark",
            nav_style="sticky_glass",
        ),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={
                    "title": "Autonomous Cloud Security for Multi-Cloud & Kubernetes",
                    "subtitle": "Agentless vulnerability scanning, real-time compliance drift detection, and autonomous remediation across AWS, GCP, and Azure in under 5 minutes.",
                    "pill_badge": "🛡️ Zero-Trust Cloud Security Platform",
                    "cta_text": "Request Live Demo",
                    "cta_link": "#appointment-form",
                    "secondary_cta_text": "View Platform Pricing",
                    "secondary_cta_link": "#pricing-1",
                    "trust_points": [
                        "Agentless 5-Minute Onboarding",
                        "Zero Compute Overhead",
                        "Continuous SOC2 & ISO27001 Auditing",
                    ],
                    "rating": "Rated 4.9 on G2 & Gartner Peer Insights",
                    "highlight_service": "Autonomous Drift Remediation",
                    "image_url": slots.get("hero_url"),
                    "image_description": "Modern cybersecurity threat intelligence dashboard with zero-trust topology",
                    "brand_icon": "🛡️",
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="centered"),
            ),
            Section(
                id="features-1",
                type="features",
                content={
                    "heading": "Unified Cloud Native Application Protection",
                    "subheading": "Unify posture management, container security, identity governance, and threat detection in a single pane.",
                    "items": [
                        {
                            "title": "Agentless Posture Management (CSPM)",
                            "description": "Continuous discovery and graph-based misconfiguration mapping across all cloud accounts without installing agents.",
                            "icon": "🌐",
                            "tag": "CSPM",
                        },
                        {
                            "title": "Autonomous Threat Remediation",
                            "description": "Context-aware automated fixes that isolate compromised pods and close security groups without breaking production.",
                            "icon": "⚡",
                            "tag": "Autonomous",
                        },
                        {
                            "title": "Continuous Compliance Automation",
                            "description": "Pre-built audit policies for SOC 2 Type II, ISO 27001, HIPAA, and PCI-DSS with one-click auditor evidence exports.",
                            "icon": "📋",
                            "tag": "Compliance",
                        },
                        {
                            "title": "Cloud Identity & Entitlement (CIEM)",
                            "description": "Detect excessive permissions, shadow credentials, and privilege escalation paths across IAM roles instantly.",
                            "icon": "🔑",
                            "tag": "CIEM",
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="grid"),
            ),
            Section(
                id="pricing-1",
                type="pricing",
                content={
                    "heading": "Transparent Cloud Compute Pricing",
                    "subheading": "Predictable pricing based on monitored workloads with unlimited user seats.",
                    "plans": [
                        {
                            "name": "Cloud Starter",
                            "price": "$499 / mo",
                            "description": "Up to 50 cloud workloads with automated daily posture scans and basic compliance.",
                            "features": ["Agentless scanning", "50 cloud workloads", "Weekly compliance reports", "Slack alerts"],
                            "cta_text": "Start Free Trial",
                        },
                        {
                            "name": "Enterprise Shield",
                            "price": "$1,499 / mo",
                            "description": "Up to 250 workloads with real-time remediation, CIEM, and dedicated TAM.",
                            "features": ["All Starter features", "Real-time auto-remediation", "CIEM & Kubernetes security", "SOC2 compliance export", "Dedicated solutions architect"],
                            "cta_text": "Request Live Demo",
                            "highlighted": True,
                        },
                        {
                            "name": "Global Sovereign",
                            "price": "Custom Tier",
                            "description": "Unlimited workloads with custom on-premises control plane and 24/7 incident response.",
                            "features": ["Unlimited workloads", "Self-hosted control plane", "Custom SLA & 24/7 SOC phone hotline", "Dedicated security engineer"],
                            "cta_text": "Contact Security Sales",
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="table"),
            ),
            Section(
                id="testimonials-1",
                type="testimonials",
                content={
                    "heading": "Defending 10M+ Workloads Worldwide",
                    "subheading": "How leading DevOps and DevSecOps engineering teams maintain zero-trust posture.",
                    "items": [
                        {
                            "quote": "ShieldCloud cut our critical vulnerability triage time by 84% in the first two weeks. The agentless setup took under 10 minutes for 300+ AWS accounts.",
                            "author": "Devon Vance",
                            "role": "VP of Infrastructure, PayScale Financial",
                            "tag": "Illustrative Client Feedback",
                            "rating": 5,
                        },
                        {
                            "quote": "The automated SOC 2 audit evidence collection saved our security team over 120 manual hours during audit season.",
                            "author": "Sophia Chen",
                            "role": "Chief Information Security Officer, DataCore AI",
                            "tag": "Illustrative Client Feedback",
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
                    "heading": "Schedule an Interactive Live Demo",
                    "subheading": "Connect with our cloud security architects to see ShieldCloud audit your staging environment live.",
                    "form_type": "demo",
                    "fields": [
                        "Work Email Address",
                        "Full Name",
                        "Company Name & Role",
                        "Primary Cloud Environment (AWS / GCP / Azure)",
                        "Estimated Cloud Workloads",
                        "Preferred Demo Time",
                    ],
                    "submit_text": "🚀 Request Live Demo",
                    "email": "demo@shieldcloud.io",
                    "phone": "+1 (800) 555-0184",
                    "hours": "Global Technical Coverage 24/7/365",
                },
                style=SectionStyle(alignment="center", padding="large"),
            ),
        ],
    )


def create_artisan_bakery_fallback_website() -> WebsiteState:
    """Benchmark reference preset for artisan sourdough bakery & cafe."""
    slots = retrieve_image_slots("artisan sourdough bakery bread")
    return WebsiteState(
        title="Crust & Crumb Bakery",
        version=1,
        theme=ThemeConfig(
            background="#FFFBEB",
            primary_color="#D97706",
            text_color="#1F2937",
            font_family="Inter, sans-serif",
            heading_font="Plus Jakarta Sans, sans-serif",
            background_style="warm_ivory",
            nav_style="floating_pill",
        ),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={
                    "title": "Naturally Fermented Sourdough & Fresh Daily Bakes",
                    "subtitle": "Slow-fermented for 36 hours using organic stone-ground heritage flours, natural wild yeasts, and wood-fired stone hearths for incomparable flavor and golden crusts.",
                    "pill_badge": "🥐 Fresh Hearth Bakes Daily From 6:30 AM",
                    "cta_text": "Order Fresh Bakes",
                    "cta_link": "#appointment-form",
                    "secondary_cta_text": "View Daily Oven Menu",
                    "secondary_cta_link": "#features-1",
                    "trust_points": [
                        "100% Organic Heritage Grains",
                        "Wild Natural Yeast Leaven",
                        "Zero Artificial Additives",
                    ],
                    "rating": "Awarded Best Neighborhood Sourdough 2026",
                    "highlight_service": "Signature Country Boule",
                    "image_url": slots.get("hero_url"),
                    "image_description": "Golden sourdough bread loaves and flaky croissants cooling on wooden bakery shelves",
                    "brand_icon": "🥐",
                },
                style=SectionStyle(alignment="left", padding="large", layout_variant="storefront"),
            ),
            Section(
                id="features-1",
                type="features",
                content={
                    "heading": "Our Daily Hearth Specialties",
                    "subheading": "Hand-shaped before dawn and baked directly on natural refractory stone deck ovens.",
                    "items": [
                        {
                            "title": "Country Sourdough Boule",
                            "description": "Crisp blistered mahogany crust with an open, custardy crumb and balanced wild fermentation tang.",
                            "icon": "🍞",
                            "tag": "Daily Classic",
                        },
                        {
                            "title": "Laminated Butter Croissant",
                            "description": "Eighty-one flaky golden layers folded with pure cultured Normandy butter for unmatched lightness.",
                            "icon": "🥐",
                            "tag": "Viennoiserie",
                        },
                        {
                            "title": "Cardamom & Brown Butter Knot",
                            "description": "Enriched brioche dough ribboned with freshly ground green cardamom and caramelized sugar glaze.",
                            "icon": "🥨",
                            "tag": "Signature",
                        },
                        {
                            "title": "Ancient Grain Seeded Baton",
                            "description": "Packed with toasted flax, pumpkin, and sunflower seeds with sprouted rye for dense nutty flavor.",
                            "icon": "🥖",
                            "tag": "Heritage",
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="pill_cards"),
            ),
            Section(
                id="pricing-1",
                type="pricing",
                content={
                    "heading": "Weekly Bread Subscriptions & Bundles",
                    "subheading": "Reserve fresh weekly loaves or pre-order bakery bundles with neighborhood pickup.",
                    "plans": [
                        {
                            "name": "The Morning Pair",
                            "price": "$16.50",
                            "description": "Two fresh country sourdough boules baked fresh for your weekend table.",
                            "features": ["2 Country Boules", "Sliced on request", "Fresh morning pickup guarantee"],
                            "cta_text": "Order Morning Pair",
                        },
                        {
                            "name": "Weekly Baker's Table",
                            "price": "$38.00 / wk",
                            "description": "Our complete weekly subscription: 2 artisan loaves, 4 pastries, and fresh brioche.",
                            "features": ["2 Sourdough Loaves", "4 Laminated Pastries", "1 Brioche Loaf", "Priority weekend pickup", "10% pantry discount"],
                            "cta_text": "Subscribe Weekly",
                            "highlighted": True,
                        },
                        {
                            "name": "Community Brunch Platter",
                            "price": "$78.00",
                            "description": "Large assorted party box of 16 fresh baked croissants, danishes, and mini baguettes.",
                            "features": ["16 Assorted pastries", "Artisan jam jars included", "Free local delivery (within 3 miles)"],
                            "cta_text": "Order Brunch Box",
                        },
                    ],
                },
                style=SectionStyle(alignment="center", padding="large", layout_variant="cards"),
            ),
            Section(
                id="testimonials-1",
                type="testimonials",
                content={
                    "heading": "Stories From Our Morning Bread Lovers",
                    "subheading": "Reflections from community regulars who stop by for warm loaves and espresso.",
                    "items": [
                        {
                            "quote": "The crust has that unmistakable shattering crackle, and the crumb is delightfully tangy and tender. Picking up warm loaves on Saturday morning is our favorite ritual.",
                            "author": "Clara Moreau",
                            "role": "Neighborhood Regular",
                            "tag": "Illustrative Client Feedback",
                            "rating": 5,
                        },
                        {
                            "quote": "Hands down the best sourdough in the city. You can taste the quality of the heritage grain in every single slice.",
                            "author": "Liam O'Connor",
                            "role": "Local Chef & Food Writer",
                            "tag": "Illustrative Client Feedback",
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
                    "heading": "Fresh Daily Order & Catering Request",
                    "subheading": "Reserve custom loaves, pastry boxes, or catering orders with guaranteed morning pickup.",
                    "form_type": "order",
                    "fields": [
                        "Customer Name",
                        "Phone Number & Email",
                        "Items Requested (Loaves / Pastry Platters)",
                        "Desired Pickup Date & Time Window",
                        "Special Notes / Dietary Inquiries",
                    ],
                    "submit_text": "🥐 Submit Bakery Order",
                    "email": "hello@crustandcrumbbakery.com",
                    "phone": "+1 (555) 782-9381",
                    "hours": "Tue – Sun: 6:30 AM – 3:00 PM (Or Until Sold Out)",
                },
                style=SectionStyle(alignment="center", padding="large"),
            ),
        ],
    )


def create_pet_grooming_fallback_website() -> WebsiteState:
    """Reference demo preset for pet grooming briefs (matching design specifications)."""
    slots = retrieve_image_slots("pet grooming dog spa")
    return WebsiteState(
        title="Pawfect Grooming",
        version=1,
        theme=ThemeConfig(
            background="#FDFBF7",
            primary_color="#FF7043",
            text_color="#1E293B",
            font_family="Plus Jakarta Sans, sans-serif",
            heading_font="Plus Jakarta Sans, sans-serif",
            background_style="warm_ivory",
            nav_style="sticky_glass",
        ),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={
                    "title": "Fresh cuts, clean coats, and happy tails.",
                    "subtitle": "Give your pet a gentle, stress-free grooming experience with expert care, spa-style baths, breed-specific cuts, and lots of love.",
                    "pill_badge": "Trusted local pet spa for dogs and cats",
                    "cta_text": "Book a Groom",
                    "cta_link": "#appointment-form",
                    "secondary_cta_text": "View Services",
                    "secondary_cta_link": "#features-1",
                    "trust_points": ["Gentle handling", "Safe products", "Personalized care"],
                    "rating": "Client rating 4.9/5",
                    "highlight_service": "Bath + Brush + Nail Trim",
                    "image_url": slots.get("hero_url"),
                    "image_description": "Friendly dog in a warm boutique pet spa",
                    "brand_icon": "🐾",
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
                            "tag": "Illustrative Client Feedback",
                            "rating": 5,
                        },
                        {
                            "quote": "Best grooming in town! Clean facility, transparent pricing, and wonderful staff. Highly recommended.",
                            "author": "David Chen",
                            "role": "Owner of Bella (French Bulldog)",
                            "tag": "Illustrative Client Feedback",
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
                    "form_type": "booking",
                    "fields": ["Owner's Name", "Pet Breed & Name", "Service Desired", "Preferred Date & Time"],
                    "submit_text": "📅 Book Appointment Now",
                    "phone": "(555) 729-3328",
                    "email": "hello@pawfectgrooming.com",
                    "hours": "Mon - Sat: 8:00 AM - 6:00 PM",
                },
                style=SectionStyle(alignment="center", padding="large"),
            ),
        ],
    )


def create_fitness_fallback_website() -> WebsiteState:
    """Reference demo preset for fitness studio briefs."""
    slots = retrieve_image_slots("fitness studio athletic gym")
    return WebsiteState(
        title="PulseFit Studio",
        version=1,
        theme=ThemeConfig(
            background="#0F172A",
            primary_color="#F97316",
            text_color="#F8FAFC",
            font_family="Inter, sans-serif",
            heading_font="Inter, sans-serif",
            background_style="dark_glow",
            nav_style="sticky_glass",
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
                    "cta_link": "#appointment-form",
                    "secondary_cta_text": "Explore Packages",
                    "secondary_cta_link": "#pricing-1",
                    "trust_points": ["Certified Elite Coaches", "State-of-the-art Equipment", "Results Guaranteed"],
                    "rating": "4.9/5 from 300+ Athletes",
                    "highlight_service": "Unlimited HIIT Classes",
                    "image_url": slots.get("hero_url"),
                    "image_description": "Modern dark athletic gym with barbells and intense lighting",
                    "brand_icon": "⚡",
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
                            "tag": "Illustrative Client Feedback",
                            "rating": 5,
                        },
                        {
                            "quote": "Lost 25 lbs in 6 months while building real functional strength. The programming actually works!",
                            "author": "Elena Rostova",
                            "role": "Marathon Runner & Athlete",
                            "tag": "Illustrative Client Feedback",
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
                    "form_type": "booking",
                    "fields": ["Full Name", "Email Address", "Phone Number", "Fitness Goals"],
                    "submit_text": "⚡ Claim Free Trial",
                    "phone": "(555) 987-6543",
                    "email": "train@pulsefitstudio.com",
                    "hours": "Mon - Fri: 5:00 AM - 9:00 PM | Sat - Sun: 7:00 AM - 6:00 PM",
                },
                style=SectionStyle(alignment="center", padding="large"),
            ),
        ],
    )


def create_deterministic_fallback_website(brief: str, plan: Optional[WebsitePlan] = None) -> WebsiteState:
    """
    Contextual fallback selector.
    Routes contrasting benchmark briefs to distinct fixtures, and any other business to contextual generic fallback.
    """
    lower_brief = (brief or "").lower()

    if any(k in lower_brief for k in ("interior", "architect", "decor", "home styling", "renovation")):
        return create_luxury_interior_fallback_website()

    if any(k in lower_brief for k in ("security", "cyber", "saas", "cloud security", "devops", "soc2", "infosec")):
        return create_cloud_security_fallback_website()

    if any(k in lower_brief for k in ("bakery", "sourdough", "bread", "pastry", "croissant")):
        return create_artisan_bakery_fallback_website()

    if "pet" in lower_brief or "groom" in lower_brief:
        return create_pet_grooming_fallback_website()

    if "fitness" in lower_brief or "gym" in lower_brief:
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
- Typography (Body): {plan.typography}
- Heading Font: {plan.heading_font}
- Layout Strategy: {plan.layout_strategy}
- Hero Variant: {plan.hero_variant}
- Navigation Style: {plan.nav_style}
- Form Type: {plan.form_type}
- Tailored Form Fields: {plan.form_fields}
- Brand Icon: {plan.brand_icon}
- Background Style: {plan.background_style}
- Sections to Include (in order): {plan.planned_sections}
- Chosen Layout Variants: {json.dumps(plan.layout_preferences)}
- Color Palette: {json.dumps(plan.color_scheme)}

Return strictly valid JSON matching WebsiteState schema.
You MUST generate every single section in planned_sections: {plan.planned_sections}.
For each section, assign 'layout_variant' in its 'style' object.
Make sure the CTA button in the hero section has cta_link pointing to "#appointment-form".
Make sure each section has a unique ID (e.g. hero-1, features-1, pricing-1, testimonials-1, contact-1), valid type, rich detailed content, and valid internal CTA anchors."""

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

    # Pre-validation normalization: convert string/malformed section content into structured dicts
    if parsed_json and isinstance(parsed_json, dict):
        parsed_json = normalize_website_state_dict(parsed_json)

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
    "font_family": "{plan.typography}",
    "heading_font": "{plan.heading_font}",
    "background_style": "{plan.background_style}",
    "nav_style": "{plan.nav_style}"
  }},
  "sections": [
    ... MUST generate ALL planned sections in order: {plan.planned_sections} ...
  ]
}}

CRITICAL SECTION CONTENT SCHEMA REQUIREMENTS:
Each item in "sections" MUST have:
- "id": string (e.g. "hero-1", "features-1", "pricing-1", "testimonials-1", "contact-1")
- "type": one of {SUPPORTED_SECTION_TYPES}
- "content": A valid JSON OBJECT / DICTIONARY (NEVER a plain string).
  Detailed content dictionary structures per section type:
  * "hero": {{"title": "...", "subtitle": "...", "cta_text": "...", "cta_link": "#appointment-form", "secondary_cta_text": "...", "secondary_cta_link": "#pricing-1", "trust_points": ["...", "..."], "rating": "...", "highlight_service": "...", "image_description": "..."}}
  * "text": {{"heading": "...", "subheading": "...", "body": "..."}}
  * "image": {{"alt": "...", "image_description": "...", "caption": "...", "image_url": null}}
  * "features": {{"heading": "...", "subheading": "...", "items": [{{"title": "...", "description": "...", "icon": "✨", "tag": "Feature"}}, ...]}}
  * "testimonials": {{"heading": "...", "subheading": "...", "items": [{{"quote": "...", "author": "...", "role": "...", "tag": "Illustrative Client Feedback", "rating": 5}}, ...]}}
  * "pricing": {{"heading": "...", "subheading": "...", "plans": [{{"name": "...", "price": "...", "description": "...", "features": ["...", "..."], "cta_text": "...", "highlighted": false}}, ...]}}
  * "cta": {{"heading": "...", "subheading": "...", "button_text": "...", "button_link": "#appointment-form"}}
  * "contact": {{"heading": "...", "subheading": "...", "form_type": "{plan.form_type}", "fields": {json.dumps(plan.form_fields)}, "submit_text": "...", "email": "...", "phone": "...", "hours": "..."}}
- "style": {{"alignment": "left"|"center"|"right", "padding": "small"|"medium"|"large", "layout_variant": "..."}}

Raw Output to fix:
{response.content[:800]}
"""

    repair_response = active_provider.complete(
        prompt=repair_prompt,
        system_prompt="You are a JSON repair specialist. Output ONLY strictly valid JSON matching the schema and include all required sections. Ensure each section has content as a dictionary.",
        temperature=0.0,
    )

    if repair_response.success and repair_response.content:
        repaired_json = extract_json_from_text(repair_response.content)
        if repaired_json and isinstance(repaired_json, dict):
            repaired_json = normalize_website_state_dict(repaired_json)
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
