"""
Pydantic data schemas for SitePilot AI.
Defines the strict contract between AI agents and the frontend renderer.
"""

import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# Supported section types per assignment specification
SUPPORTED_SECTION_TYPES = [
    "hero",
    "text",
    "image",
    "features",
    "testimonials",
    "pricing",
    "faq",
    "cta",
    "contact",
]

SectionTypeLiteral = Literal[
    "hero",
    "text",
    "image",
    "features",
    "testimonials",
    "pricing",
    "faq",
    "cta",
    "contact",
]


DEFAULT_FAQ_ITEMS = [
    {
        "question": "What services do you offer?",
        "answer": "We provide comprehensive solutions tailored to your unique requirements, from initial consultation through final delivery.",
    },
    {
        "question": "How do I schedule an appointment or get started?",
        "answer": "You can easily book directly through our online form, contact us via phone, or select one of our packages above.",
    },
    {
        "question": "What are your operating hours and availability?",
        "answer": "We are open Monday through Friday from 9:00 AM to 6:00 PM, with flexible weekend appointments available upon request.",
    },
    {
        "question": "What is your cancellation and rescheduling policy?",
        "answer": "We request at least 24 hours notice for cancellations or rescheduling to accommodate other clients.",
    },
    {
        "question": "Do you offer satisfaction guarantees?",
        "answer": "Yes, customer satisfaction is our top priority. If you are not completely satisfied, our team will work with you to make it right.",
    },
]


class ThemeConfig(BaseModel):
    """Global styling and color palette."""
    background: str = Field(default="#ffffff", description="Background color hex or CSS string")
    primary_color: str = Field(default="#2563eb", description="Primary brand color hex")
    text_color: str = Field(default="#1e293b", description="Primary text color hex")
    font_family: str = Field(default="Inter, sans-serif", description="Body font family")
    heading_font: Optional[str] = Field(default=None, description="Distinct heading font family (e.g. Playfair Display, Outfit)")
    background_style: Optional[str] = Field(default="solid", description="Background aesthetic: solid, warm_ivory, dark_glow, editorial_cream, tech_dark, gradient_mesh")
    nav_style: Optional[str] = Field(default="sticky_glass", description="Navigation bar visual style: sticky_glass, floating_pill, clean_minimal, centered_brand")
    accent_color: Optional[str] = Field(default=None, description="Optional secondary accent color")


class SectionStyle(BaseModel):
    """Supported style properties for sections."""
    background_color: Optional[str] = Field(default=None, description="Section background color")
    text_color: Optional[str] = Field(default=None, description="Section text color")
    padding: Optional[str] = Field(default="medium", description="Section padding: small, medium, large")
    alignment: Optional[str] = Field(default="center", description="Content alignment: left, center, right")
    variant: Optional[str] = Field(default="default", description="Visual variant: default, dark, light, card, editorial, glow")
    layout_variant: Optional[str] = Field(default="default", description="Layout structure variant: split, centered, minimal, grid, list, pill_cards, table, spotlight, editorial_showcase, storefront")
    background_image_url: Optional[str] = Field(default=None, description="Optional background image URL")
    has_overlay: Optional[bool] = Field(default=False, description="Whether background image has darkened/tinted overlay")


# -----------------------------------------------------------------------------
# Content Normalization Helpers
# -----------------------------------------------------------------------------

def strip_star_emojis(text: Any) -> Any:
    """
    Strip all star emojis and characters (⭐, ★, ✨, 🌟, ☆, 💫, 🌠) from text.
    Ensures that no star emojis appear in generated website titles or section headings.
    """
    if not text or not isinstance(text, str):
        return text
    cleaned = re.sub(r"[⭐★✨🌟☆💫🌠]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
# -----------------------------------------------------------------------------

def normalize_section_content(section_type: Optional[str], raw_content: Any) -> Dict[str, Any]:
    """
    Normalize raw section content into the expected structured dictionary for section_type.
    Converts plain strings, lists, nulls, missing, and malformed types safely into compliant dicts
    while preserving original text. Keeps strict schema compatibility with the component renderer.
    """
    s_type = (section_type or "").lower().strip()

    # 1. Already a dictionary -> normalize internal lists/fields safely
    if isinstance(raw_content, dict):
        c = dict(raw_content)
        if s_type == "features":
            items = c.get("items")
            if isinstance(items, list):
                norm_items = []
                for it in items:
                    if isinstance(it, dict):
                        norm_items.append(it)
                    elif isinstance(it, str) and it.strip():
                        if " - " in it or ": " in it:
                            t_part, d_part = re.split(r" - |: ", it, maxsplit=1)
                        else:
                            t_part, d_part = it, "Quality service designed to meet your needs."
                        norm_items.append({
                            "title": t_part.strip().lstrip("•-0123456789. "),
                            "description": d_part.strip(),
                            "icon": "✨",
                            "tag": "Feature",
                        })
                c["items"] = norm_items
            elif "items" not in c or not isinstance(items, list):
                c["items"] = []
        elif s_type == "testimonials":
            items = c.get("items")
            if isinstance(items, list):
                norm_items = []
                for it in items:
                    if isinstance(it, dict):
                        it_copy = dict(it)
                        if "tag" not in it_copy:
                            it_copy["tag"] = "Illustrative Client Feedback"
                        if "rating" not in it_copy:
                            it_copy["rating"] = 5
                        norm_items.append(it_copy)
                    elif isinstance(it, str) and it.strip():
                        if " - " in it or " — " in it or "--" in it:
                            q_part, a_part = re.split(r" - | — |--", it, maxsplit=1)
                        else:
                            q_part, a_part = it, "Valued Client"
                        norm_items.append({
                            "quote": q_part.strip(' "“‘”’'),
                            "author": a_part.strip(),
                            "role": "Customer",
                            "tag": "Illustrative Client Feedback",
                            "rating": 5,
                        })
                c["items"] = norm_items
            elif "items" not in c or not isinstance(items, list):
                c["items"] = []
        elif s_type == "pricing":
            plans = c.get("plans")
            if isinstance(plans, list):
                norm_plans = []
                for p in plans:
                    if isinstance(p, dict):
                        norm_plans.append(p)
                    elif isinstance(p, str) and p.strip():
                        price_match = re.search(r"\$[0-9]+(?:\.[0-9]{2})?", p)
                        price_str = price_match.group(0) if price_match else "$99"
                        clean_name = p.replace(price_str, "").strip(" -:,").strip() or "Standard Plan"
                        norm_plans.append({
                            "name": clean_name,
                            "price": price_str,
                            "description": "Comprehensive service package.",
                            "features": ["Full service delivery", "Quality assurance", "Direct support"],
                            "cta_text": "Get Started",
                            "highlighted": len(norm_plans) == 1,
                        })
                c["plans"] = norm_plans
            elif "plans" not in c or not isinstance(plans, list):
                c["plans"] = []
        elif s_type == "faq":
            items = c.get("items")
            if isinstance(items, list):
                norm_items = []
                for it in items:
                    if isinstance(it, dict):
                        norm_items.append({
                            "question": it.get("question", "General Inquiry"),
                            "answer": it.get("answer", "Please contact our team for full details."),
                        })
                    elif isinstance(it, str) and it.strip():
                        if "? " in it:
                            q_p, a_p = it.split("? ", 1)
                            q_p = q_p.strip() + "?"
                        elif " - " in it:
                            q_p, a_p = it.split(" - ", 1)
                        else:
                            q_p, a_p = it, "Contact us for more details."
                        norm_items.append({"question": q_p.strip(), "answer": a_p.strip()})
                c["items"] = norm_items if len(norm_items) >= 5 else (norm_items + DEFAULT_FAQ_ITEMS[len(norm_items):])
            else:
                c["items"] = list(DEFAULT_FAQ_ITEMS)
            if "heading" not in c:
                c["heading"] = "Frequently Asked Questions"
            if "subheading" not in c:
                c["subheading"] = "Everything you need to know about our services and policies."
        elif s_type == "text":
            # 1. Heading aliases
            heading = (
                c.get("heading")
                or c.get("title")
                or c.get("name")
                or c.get("header")
                or "About Us"
            )
            c["heading"] = str(heading).strip() or "About Us"

            # 2. Subheading aliases
            subheading = (
                c.get("subheading")
                or c.get("subtitle")
                or c.get("tagline")
                or c.get("eyebrow")
                or ""
            )
            c["subheading"] = str(subheading).strip() if subheading else ""

            # 3. Body aliases (body, text, content, description, story, paragraphs, details, copy, about, bio)
            body_val = None
            for key in ["body", "text", "content", "description", "story", "paragraphs", "paragraph", "details", "copy", "about", "bio", "message"]:
                if key in c and c[key] is not None:
                    body_val = c[key]
                    break

            if isinstance(body_val, list):
                joined = "\n\n".join(str(p).strip() for p in body_val if str(p).strip())
                c["body"] = joined or "Dedicated to delivering exceptional quality, personalized service, and genuine passion in everything we do."
            elif isinstance(body_val, str) and body_val.strip():
                c["body"] = body_val.strip()
            elif body_val is not None and not isinstance(body_val, (dict, list)):
                c["body"] = str(body_val).strip()
            else:
                c["body"] = "Dedicated to delivering exceptional quality, personalized service, and genuine passion in everything we do."

            # 4. Optional image aliases
            img_url = (
                c.get("image_url")
                or c.get("url")
                or c.get("image")
                or c.get("img")
                or c.get("photo")
            )
            if img_url and isinstance(img_url, str) and img_url.strip():
                c["image_url"] = img_url.strip()

            img_desc = (
                c.get("image_description")
                or c.get("alt")
                or c.get("caption")
            )
            if img_desc and isinstance(img_desc, str) and img_desc.strip():
                c["image_description"] = img_desc.strip()
        return c

    # 2. Null, missing, or boolean values
    if raw_content is None or isinstance(raw_content, bool):
        raw_str = ""
    elif isinstance(raw_content, (int, float)):
        raw_str = str(raw_content)
    elif isinstance(raw_content, list):
        if s_type == "features":
            norm_items = []
            for it in raw_content:
                if isinstance(it, dict):
                    norm_items.append(it)
                elif isinstance(it, str) and it.strip():
                    norm_items.append({
                        "title": it.strip().lstrip("•-0123456789. "),
                        "description": "Quality service tailored to your needs.",
                        "icon": "✨",
                        "tag": "Feature",
                    })
            return {
                "heading": "Our Services & Capabilities",
                "subheading": "Carefully tailored solutions built around your needs.",
                "items": norm_items,
            }
        elif s_type == "testimonials":
            norm_items = []
            for it in raw_content:
                if isinstance(it, dict):
                    norm_items.append(it)
                elif isinstance(it, str) and it.strip():
                    norm_items.append({
                        "quote": it.strip(' "“‘”’'),
                        "author": "Valued Client",
                        "role": "Customer",
                        "tag": "Illustrative Client Feedback",
                        "rating": 5,
                    })
            return {
                "heading": "What Our Clients Say",
                "subheading": "Real feedback from our satisfied clients.",
                "items": norm_items,
            }
        elif s_type == "pricing":
            norm_plans = []
            for p in raw_content:
                if isinstance(p, dict):
                    norm_plans.append(p)
                elif isinstance(p, str) and p.strip():
                    norm_plans.append({
                        "name": p.strip(),
                        "price": "$99",
                        "description": "Comprehensive service package.",
                        "features": ["Core service delivery", "Dedicated support"],
                        "cta_text": "Get Started",
                        "highlighted": len(norm_plans) == 1,
                    })
            return {
                "heading": "Packages & Pricing",
                "subheading": "Straightforward rates designed to suit your project scope.",
                "plans": norm_plans,
            }
        elif s_type == "faq":
            norm_items = []
            for it in raw_content:
                if isinstance(it, dict):
                    norm_items.append({
                        "question": it.get("question", "General Question"),
                        "answer": it.get("answer", "Please contact our team for full details."),
                    })
                elif isinstance(it, str) and it.strip():
                    if "? " in it:
                        q_p, a_p = it.split("? ", 1)
                        q_p = q_p.strip() + "?"
                    elif " - " in it:
                        q_p, a_p = it.split(" - ", 1)
                    else:
                        q_p, a_p = it, "Contact us for more details."
                    norm_items.append({"question": q_p.strip(), "answer": a_p.strip()})
            if len(norm_items) < 5:
                norm_items += DEFAULT_FAQ_ITEMS[len(norm_items):]
            return {
                "heading": "Frequently Asked Questions",
                "subheading": "Everything you need to know about our services and policies.",
                "items": norm_items,
            }
        elif s_type == "text":
            joined = "\n\n".join(str(x).strip() for x in raw_content if str(x).strip())
            return {
                "heading": "About Us",
                "subheading": "",
                "body": joined or "Dedicated to delivering exceptional quality, personalized service, and genuine passion in everything we do.",
            }
        elif s_type == "image":
            gallery_urls = [str(x) for x in raw_content if str(x).strip().startswith(("http://", "https://"))]
            if gallery_urls:
                return {
                    "alt": "Showcase Gallery",
                    "caption": "Curated visual portfolio",
                    "gallery": gallery_urls,
                    "url": gallery_urls[0],
                }
            raw_str = " ".join(str(x) for x in raw_content)
        else:
            raw_str = "\n\n".join(str(x) for x in raw_content)
    elif isinstance(raw_content, str):
        raw_str = raw_content.strip()
    else:
        raw_str = str(raw_content).strip()

    # 3. Empty after string conversion -> default structured dictionaries
    if not raw_str:
        if s_type == "hero":
            return {
                "title": "Welcome",
                "subtitle": "",
                "cta_text": "Get Started",
                "cta_link": "#appointment-form",
                "brand_icon": "✨",
            }
        elif s_type == "text":
            return {"heading": "About Us", "subheading": "", "body": "Dedicated to excellence in every detail."}
        elif s_type == "image":
            return {"alt": "Visual Feature", "image_description": "Professional showcase photography", "caption": ""}
        elif s_type == "features":
            return {
                "heading": "Our Services & Capabilities",
                "subheading": "Carefully tailored solutions built around your needs.",
                "items": [],
            }
        elif s_type == "testimonials":
            return {
                "heading": "What Our Clients Say",
                "subheading": "Real experiences and feedback from our community.",
                "items": [],
            }
        elif s_type == "pricing":
            return {
                "heading": "Packages & Pricing",
                "subheading": "Transparent rates with no hidden fees.",
                "plans": [],
            }
        elif s_type == "faq":
            return {
                "heading": "Frequently Asked Questions",
                "subheading": "Everything you need to know about our services and policies.",
                "items": list(DEFAULT_FAQ_ITEMS),
            }
        elif s_type == "cta":
            return {
                "heading": "Ready to Get Started?",
                "subheading": "Connect with our team today.",
                "button_text": "Book Appointment Now",
                "button_link": "#appointment-form",
            }
        elif s_type == "contact":
            return {
                "heading": "Contact Us",
                "subheading": "We would love to hear from you.",
                "form_type": "contact",
                "fields": ["Full Name", "Email Address", "Phone Number", "Message"],
                "submit_text": "Send Message",
                "email": "contact@example.com",
                "phone": "(555) 123-4567",
                "hours": "Mon - Fri: 9:00 AM - 6:00 PM",
            }
        return {"raw_text": ""}

    # 4. Non-empty string content -> map to section properties while strictly preserving all text
    if s_type == "hero":
        lines = [l.strip() for l in raw_str.splitlines() if l.strip()]
        if len(lines) > 1:
            title = lines[0]
            subtitle = " ".join(lines[1:])
        else:
            if len(raw_str) > 70 and ("." in raw_str or "!" in raw_str):
                parts = re.split(r"(?<=[.!?])\s+", raw_str, maxsplit=1)
                title = parts[0]
                subtitle = parts[1] if len(parts) > 1 else ""
            else:
                title = raw_str
                subtitle = ""
        return {
            "title": title or "Welcome",
            "subtitle": subtitle,
            "cta_text": "Book Appointment",
            "cta_link": "#appointment-form",
            "secondary_cta_text": "Explore Packages",
            "secondary_cta_link": "#pricing-1",
            "pill_badge": "Premier Quality & Care",
            "trust_points": ["Certified Specialists", "100% Satisfaction Guarantee", "Gentle & Personalized Care"],
            "rating": "Client rating 4.9/5",
            "highlight_service": "Top Rated Experience",
            "image_description": raw_str,
            "brand_icon": "🔹",
        }

    elif s_type == "text":
        lines = [l.strip() for l in raw_str.splitlines() if l.strip()]
        if len(lines) > 1 and len(lines[0]) <= 60:
            heading = lines[0]
            body = "\n\n".join(lines[1:])
        else:
            heading = "About Us"
            body = raw_str
        return {
            "heading": heading,
            "subheading": "",
            "body": body,
        }

    elif s_type == "image":
        if raw_str.startswith(("http://", "https://")):
            return {
                "image_url": raw_str,
                "url": raw_str,
                "alt": "Visual Showcase",
                "image_description": "Curated visual photography",
                "caption": "",
            }
        return {
            "image_url": None,
            "url": None,
            "alt": raw_str[:60],
            "image_description": raw_str,
            "caption": raw_str,
        }

    elif s_type == "features":
        raw_items = [it.strip() for it in re.split(r"[\n;]+|(?:\s*•\s*)", raw_str) if it.strip()]
        parsed_items = []
        for it in raw_items:
            clean_it = re.sub(r"^\d+[\.\)]\s*", "", it).strip()
            if not clean_it:
                continue
            if " - " in clean_it:
                t_part, d_part = clean_it.split(" - ", 1)
            elif ": " in clean_it:
                t_part, d_part = clean_it.split(": ", 1)
            elif " — " in clean_it:
                t_part, d_part = clean_it.split(" — ", 1)
            else:
                t_part = clean_it
                d_part = "Delivering premium results tailored to your exact needs."
            parsed_items.append({
                "title": t_part.strip(),
                "description": d_part.strip(),
                "icon": "🔹",
                "tag": "Feature",
            })
        if not parsed_items:
            parsed_items.append({
                "title": "Core Services",
                "description": raw_str,
                "icon": "🔹",
                "tag": "Feature",
            })
        return {
            "heading": "Our Services & Capabilities",
            "subheading": "Carefully tailored solutions built around your needs.",
            "items": parsed_items,
        }

    elif s_type == "testimonials":
        raw_items = [it.strip() for it in re.split(r"[\n;]+|(?:\s*•\s*)", raw_str) if it.strip()]
        parsed_items = []
        for it in raw_items:
            clean_it = it.strip(' "“‘”’')
            if not clean_it:
                continue
            if " - " in clean_it:
                q_part, a_part = clean_it.split(" - ", 1)
            elif " — " in clean_it:
                q_part, a_part = clean_it.split(" — ", 1)
            elif "--" in clean_it:
                q_part, a_part = clean_it.split("--", 1)
            else:
                q_part = clean_it
                a_part = "Verified Client"
            parsed_items.append({
                "quote": q_part.strip(),
                "author": a_part.strip() or "Verified Client",
                "role": "Customer",
                "tag": "Illustrative Client Feedback",
                "rating": 5,
            })
        if not parsed_items:
            parsed_items.append({
                "quote": raw_str,
                "author": "Valued Client",
                "role": "Customer",
                "tag": "Illustrative Client Feedback",
                "rating": 5,
            })
        return {
            "heading": "What Our Clients Say",
            "subheading": "Real feedback from our satisfied clients.",
            "items": parsed_items,
        }

    elif s_type == "pricing":
        raw_chunks = [it.strip() for it in re.split(r"[\n;]+|(?:\s*•\s*)", raw_str) if it.strip()]
        parsed_plans = []
        for chunk in raw_chunks:
            clean_chunk = re.sub(r"^\d+[\.\)]\s*", "", chunk).strip()
            if not clean_chunk:
                continue
            price_match = re.search(r"\$[0-9]+(?:\.[0-9]{2})?", clean_chunk)
            price_str = price_match.group(0) if price_match else "$99"
            name_str = clean_chunk.replace(price_str, "").strip(" -:,").strip() or "Standard Plan"
            parsed_plans.append({
                "name": name_str,
                "price": price_str,
                "description": "Comprehensive service package.",
                "features": ["Core service delivery", "Quality assurance", "Direct support"],
                "cta_text": "Get Started",
                "highlighted": len(parsed_plans) == 1,
            })
        if not parsed_plans:
            parsed_plans.append({
                "name": "Standard Plan",
                "price": "$99",
                "description": raw_str,
                "features": ["Full service delivery", "Quality assurance", "Dedicated support"],
                "cta_text": "Get Started",
                "highlighted": True,
            })
        return {
            "heading": "Packages & Pricing",
            "subheading": "Transparent rates with no hidden fees.",
            "plans": parsed_plans,
        }

    elif s_type == "cta":
        if len(raw_str) <= 60:
            heading = raw_str
            subheading = "Connect with our team today and experience the difference."
        else:
            heading = "Ready to Get Started?"
            subheading = raw_str
        return {
            "heading": heading,
            "subheading": subheading,
            "button_text": "Book Appointment Now",
            "button_link": "#appointment-form",
        }

    elif s_type == "contact":
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_str)
        phone_match = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", raw_str)
        return {
            "heading": "Contact Us",
            "subheading": raw_str,
            "form_type": "contact",
            "fields": ["Full Name", "Email Address", "Phone Number", "Message"],
            "submit_text": "Send Message",
            "email": email_match.group(0) if email_match else "contact@example.com",
            "phone": phone_match.group(0) if phone_match else "(555) 123-4567",
            "hours": "Mon - Fri: 9:00 AM - 6:00 PM",
        }

    elif s_type == "faq":
        return {
            "heading": "Frequently Asked Questions",
            "subheading": raw_str if raw_str else "Everything you need to know about our services and policies.",
            "items": list(DEFAULT_FAQ_ITEMS),
        }

    return {"raw_text": raw_str}


def normalize_website_state_dict(data: Any) -> Any:
    """
    Recursively normalize raw dictionary data before Pydantic validation into WebsiteState.
    Ensures all sections have structured dictionary content and valid layout structures.
    """
    if not isinstance(data, dict):
        return data

    clean_data = dict(data)
    sections = clean_data.get("sections")
    if isinstance(sections, list):
        norm_sections = []
        for s in sections:
            if isinstance(s, dict):
                s_copy = dict(s)
                s_type = s_copy.get("type")
                s_copy["content"] = normalize_section_content(s_type, s_copy.get("content"))
                norm_sections.append(s_copy)
            elif isinstance(s, str):
                norm_sections.append({
                    "id": f"section-{len(norm_sections)+1}",
                    "type": "text",
                    "content": normalize_section_content("text", s),
                })
            else:
                norm_sections.append(s)
        clean_data["sections"] = norm_sections
    return clean_data


class Section(BaseModel):
    """A distinct component section of the website with a stable unique ID."""
    id: str = Field(..., description="Unique, stable identifier (e.g. hero-1, pricing-1)")
    type: SectionTypeLiteral = Field(..., description="Component type from predefined library")
    content: Dict[str, Any] = Field(default_factory=dict, description="Component-specific content data")
    style: SectionStyle = Field(default_factory=SectionStyle, description="Component styling overrides")

    @model_validator(mode="before")
    @classmethod
    def normalize_section_input(cls, data: Any) -> Any:
        """Normalize content before Pydantic validation while strictly preserving all text."""
        if isinstance(data, dict):
            s_type = data.get("type")
            content = data.get("content")
            data["content"] = normalize_section_content(s_type, content)
        return data

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Section id cannot be empty.")
        return v

    @model_validator(mode="after")
    def validate_content_for_type(self) -> "Section":
        """Validate that content contains sensible fields for the section type."""
        c = self.content
        t = self.type

        # Supply sensible defaults if missing
        if t == "hero":
            if "title" not in c:
                c["title"] = "Welcome"
            if "subtitle" not in c:
                c["subtitle"] = ""
            if "cta_text" not in c:
                c["cta_text"] = "Get Started"
        elif t == "text":
            if not c.get("heading"):
                c["heading"] = "About Us"
            if not c.get("body"):
                c["body"] = "Dedicated to delivering exceptional quality, personalized service, and genuine passion in everything we do."
        elif t == "image":
            if "alt" not in c:
                c["alt"] = "Visual Feature"
            if "image_description" not in c and not c.get("url"):
                c["image_description"] = "Professional showcase photography"
        elif t == "features":
            if "items" not in c or not isinstance(c["items"], list):
                c["items"] = []
        elif t == "testimonials":
            if "items" not in c or not isinstance(c["items"], list):
                c["items"] = []
        elif t == "pricing":
            if "plans" not in c or not isinstance(c["plans"], list):
                c["plans"] = []
        elif t == "cta":
            if "heading" not in c:
                c["heading"] = "Ready to start?"
            if "button_text" not in c:
                c["button_text"] = "Join Now"
        elif t == "contact":
            if "heading" not in c:
                c["heading"] = "Contact Us"
        elif t == "faq":
            if "heading" not in c:
                c["heading"] = "Frequently Asked Questions"
            if "subheading" not in c:
                c["subheading"] = "Everything you need to know about our services and policies."
            items = c.get("items")
            if not isinstance(items, list) or len(items) < 5:
                existing = items if isinstance(items, list) else []
                c["items"] = existing + DEFAULT_FAQ_ITEMS[len(existing):]

        # Ensure no star emojis in any website headings, titles, subheadings, or item names
        for key in ("title", "heading", "subheading", "name"):
            if key in c and isinstance(c[key], str):
                c[key] = strip_star_emojis(c[key])
        if "items" in c and isinstance(c["items"], list):
            for it in c["items"]:
                if isinstance(it, dict):
                    for k in ("title", "heading", "name", "question", "answer"):
                        if k in it and isinstance(it[k], str):
                            it[k] = strip_star_emojis(it[k])
        if "plans" in c and isinstance(c["plans"], list):
            for p in c["plans"]:
                if isinstance(p, dict) and "name" in p and isinstance(p["name"], str):
                    p["name"] = strip_star_emojis(p["name"])

        return self


class WebsitePlan(BaseModel):
    """Output of the Planner step before full website generation."""
    business_type: str = Field(..., description="Categorized business type (e.g. Fitness Studio)")
    tone_and_style: str = Field(..., description="Target aesthetic/tone (e.g. Modern, energetic, clean)")
    primary_goal: str = Field(..., description="Primary conversion goal (e.g. Book trial memberships)")
    planned_sections: List[SectionTypeLiteral] = Field(
        default_factory=list,
        description="Ordered sequence of section types to generate",
    )
    suggested_title: str = Field(default="My Website", description="Suggested site title")
    typography: str = Field(default="Inter, sans-serif", description="Recommended body font family for visual direction")
    heading_font: str = Field(default="Inter, sans-serif", description="Recommended heading font family")
    layout_strategy: str = Field(default="modern_showcase", description="High-level layout strategy: luxury_editorial, saas_modern, artisan_storefront, portfolio_showcase, bold_promotional")
    hero_variant: str = Field(default="split", description="Hero section layout variant: split, centered, minimal, editorial_showcase, storefront")
    nav_style: str = Field(default="sticky_glass", description="Navbar style: sticky_glass, floating_pill, clean_minimal, centered_brand")
    nav_cta_text: str = Field(default="Get Started", description="Text for navbar CTA button")
    nav_cta_link: str = Field(default="#appointment-form", description="Anchor destination for navbar CTA button")
    form_type: str = Field(default="contact", description="Tailored form type: booking, inquiry, demo, signup, contact")
    form_fields: List[str] = Field(
        default_factory=lambda: ["Full Name", "Email Address", "Phone Number", "Message"],
        description="Business-specific form fields",
    )
    brand_icon: str = Field(default="🔹", description="Brand emoji or symbol")
    background_style: str = Field(default="solid", description="Global background aesthetic: solid, warm_ivory, dark_glow, editorial_cream, tech_dark, gradient_mesh")
    layout_preferences: Dict[str, str] = Field(
        default_factory=lambda: {
            "hero": "split",
            "features": "grid",
            "pricing": "cards",
            "testimonials": "grid",
        },
        description="Recommended layout variants per section type",
    )
    color_scheme: Dict[str, str] = Field(
        default_factory=lambda: {
            "background": "#ffffff",
            "primary_color": "#2563eb",
            "text_color": "#1e293b",
        }
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_plan_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tone" in data and "tone_and_style" not in data:
                data["tone_and_style"] = data["tone"]
            if "font_family" in data and "typography" not in data:
                data["typography"] = data["font_family"]
        return data

    @property
    def tone(self) -> str:
        """Backwards compatibility alias for tone_and_style."""
        return self.tone_and_style

    @property
    def font_family(self) -> str:
        """Backwards compatibility alias for typography."""
        return self.typography

    @field_validator("suggested_title", mode="after")
    @classmethod
    def clean_suggested_title(cls, v: str) -> str:
        return strip_star_emojis(v)

    @field_validator("planned_sections")
    @classmethod
    def validate_sections_not_empty(cls, v: List[str]) -> List[str]:
        if not v:
            # Default to standard landing page layout if empty
            return ["hero", "features", "pricing", "testimonials", "contact"]
        return v


class WebsiteState(BaseModel):
    """Complete structured website state acting as source of truth."""
    title: str = Field(..., description="Website title")
    version: int = Field(default=1, description="Sequential version number")
    theme: ThemeConfig = Field(default_factory=ThemeConfig, description="Global theme settings")
    sections: List[Section] = Field(default_factory=list, description="Ordered list of page sections")

    @field_validator("title", mode="after")
    @classmethod
    def clean_website_title(cls, v: str) -> str:
        return strip_star_emojis(v)

    @model_validator(mode="before")
    @classmethod
    def normalize_website_state_input(cls, data: Any) -> Any:
        """Recursively normalize sections and dictionary content before validation."""
        return normalize_website_state_dict(data)

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Version must be a positive integer >= 1.")
        return v

    @model_validator(mode="after")
    def validate_unique_section_ids(self) -> "WebsiteState":
        """Ensure all section IDs in the website are unique."""
        seen = set()
        for s in self.sections:
            if s.id in seen:
                raise ValueError(f"Duplicate section id '{s.id}' found in website state.")
            seen.add(s.id)
        return self

    def get_section_ids(self) -> List[str]:
        """Return list of all section IDs in order."""
        return [s.id for s in self.sections]

    def find_section(self, section_id: str) -> Optional[Section]:
        """Lookup section by its unique ID."""
        for s in self.sections:
            if s.id == section_id:
                return s
        return None


# -----------------------------------------------------------------------------
# Phase 4: Patch Engine & Conversational Editing Schemas
# -----------------------------------------------------------------------------

PatchActionLiteral = Literal[
    "update_section",
    "add_section",
    "remove_section",
    "reorder_sections",
    "update_theme",
]


class PatchOperation(BaseModel):
    """
    Deterministic patch operation to mutate a WebsiteState.
    Supports section content/style updates, adding, removing, reordering, and theme updates.
    """
    op: PatchActionLiteral = Field(..., description="Action to perform: update_section, add_section, remove_section, reorder_sections, update_theme")
    target_id: Optional[str] = Field(default=None, description="Target section ID for update or removal")
    content: Optional[Dict[str, Any]] = Field(default=None, description="Content dictionary updates or new section content")
    style: Optional[Dict[str, Any]] = Field(default=None, description="Style dictionary updates or new section style")
    section_type: Optional[SectionTypeLiteral] = Field(default=None, description="Section type for add_section")
    position: Optional[int] = Field(default=None, description="Insertion index or new position")
    placement: Optional[Literal["before", "after", "end", "start"]] = Field(default="end", description="Relative placement for added sections")
    section_ids: Optional[List[str]] = Field(default=None, description="Complete sequence of section IDs for reorder_sections")
    theme: Optional[Dict[str, Any]] = Field(default=None, description="Theme updates for update_theme")

    @model_validator(mode="before")
    @classmethod
    def normalize_patch_operation(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map action to op
            if not data.get("op") and data.get("action"):
                data["op"] = data["action"]

            # Map target_section_id to target_id
            if not data.get("target_id") and data.get("target_section_id"):
                data["target_id"] = data["target_section_id"]

            # Map content_updates / new_section_content to content
            if not data.get("content"):
                if data.get("content_updates") is not None:
                    data["content"] = data["content_updates"]
                elif data.get("new_section_content") is not None:
                    data["content"] = data["new_section_content"]

            # Map style_updates / new_section_style to style
            if not data.get("style"):
                if data.get("style_updates") is not None:
                    data["style"] = data["style_updates"]
                elif data.get("new_section_style") is not None:
                    data["style"] = data["new_section_style"]

            # Map new_order to section_ids
            if not data.get("section_ids") and data.get("new_order") is not None:
                data["section_ids"] = data["new_order"]

            # Map theme_updates to theme
            if not data.get("theme") and data.get("theme_updates") is not None:
                data["theme"] = data["theme_updates"]

            # Normalize operation name synonyms
            raw_op = str(data.get("op", "")).lower().strip()
            if raw_op in ("update", "modify", "update_content", "update_style", "update_section_content", "update_section_style"):
                data["op"] = "update_section"
            elif raw_op in ("add", "insert", "new_section", "create_section"):
                data["op"] = "add_section"
            elif raw_op in ("remove", "delete", "drop"):
                data["op"] = "remove_section"
            elif raw_op in ("reorder", "move", "sort", "reorder_sections"):
                data["op"] = "reorder_sections"
            elif raw_op in ("theme", "update_theme_config", "style_theme", "theme_update"):
                data["op"] = "update_theme"

            # Clean target_id
            if data.get("target_id") and isinstance(data["target_id"], str):
                data["target_id"] = data["target_id"].strip().lstrip("#")

            # Extract section_type if passed as 'type'
            if not data.get("section_type") and data.get("type"):
                t = str(data["type"]).lower().strip()
                if t in SUPPORTED_SECTION_TYPES:
                    data["section_type"] = t

            # Normalize content if passed as string
            s_type = data.get("section_type")
            if "content" in data and not isinstance(data["content"], dict):
                data["content"] = normalize_section_content(s_type or "text", data["content"])
        return data

    @property
    def action(self) -> str:
        return self.op

    @property
    def target_section_id(self) -> Optional[str]:
        return self.target_id

    @property
    def content_updates(self) -> Optional[Dict[str, Any]]:
        return self.content

    @property
    def style_updates(self) -> Optional[Dict[str, Any]]:
        return self.style

    @property
    def new_section_content(self) -> Optional[Dict[str, Any]]:
        return self.content

    @property
    def new_order(self) -> Optional[List[str]]:
        return self.section_ids

    @property
    def theme_updates(self) -> Optional[Dict[str, Any]]:
        return self.theme


class EditPlan(BaseModel):
    """Structured plan of deterministic patch operations generated by Edit Agent."""
    summary: str = Field(..., description="Brief natural language summary of planned changes")
    operations: List[PatchOperation] = Field(default_factory=list, description="Ordered list of operations to execute")


class OperationRecord(BaseModel):
    """Detailed audit record for an individual patch operation."""
    op: str = Field(..., description="Operation type: update_section, add_section, remove_section, reorder_sections, update_theme, restore_version")
    target_id: Optional[str] = Field(default=None, description="Target section ID if applicable")
    property_path: Optional[str] = Field(default=None, description="Affected property or path (e.g. style.variant, content.cta_text, sections)")
    previous_value: Any = Field(default=None, description="Value prior to mutation")
    new_value: Any = Field(default=None, description="Value after mutation")
    status: Literal["success", "failed", "rolled_back"] = Field(default="success", description="Status of this individual operation")
    details: Optional[str] = Field(default=None, description="Human-readable outcome or failure reason")


class EditHistoryItem(BaseModel):
    """Audit log record for an edit operation."""
    version: int = Field(..., description="Website version resulting from this edit (or current version if rejected)")
    version_before: int = Field(default=1, description="Website version prior to this edit")
    instruction: str = Field(..., description="User's original conversational request")
    summary: str = Field(default="", description="Summary of applied changes")
    operations: List[Dict[str, Any]] = Field(default_factory=list, description="Applied patch operations")
    operation_records: List[OperationRecord] = Field(default_factory=list, description="Individual operation before/after records")
    timestamp: str = Field(..., description="ISO 8601 timestamp of edit")
    success: bool = Field(default=True, description="Whether the edit succeeded and was committed")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")

    @property
    def version_after(self) -> int:
        return self.version

    @property
    def operations_applied(self) -> List[Dict[str, Any]]:
        return self.operations
