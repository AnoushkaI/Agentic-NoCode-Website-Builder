"""
Conversational Edit Agent for SitePilot AI.
Interprets user natural language instructions in context of the current WebsiteState,
and produces structured, deterministic EditPlan patch operations without arbitrary code execution.
Includes bounded 1-step LLM repair and robust deterministic rule-based fallbacks.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import ValidationError

from src.schema import (
    WebsiteState,
    EditPlan,
    PatchOperation,
    SUPPORTED_SECTION_TYPES,
)
from src.providers.base import BaseProvider
from src.providers.factory import get_provider
from src.json_utils import extract_json_from_text

logger = logging.getLogger(__name__)


class EditAgentError(Exception):
    """Raised when the edit agent fails to parse or validate edit operations."""
    pass


EDIT_AGENT_SYSTEM_PROMPT = f"""You are the SitePilot AI Conversational Edit Agent.
Your task is to convert a user's natural language edit instruction into a strictly structured EditPlan JSON object containing deterministic patch operations.

ALLOWED PATCH OPERATIONS:
1. update_section:
   - "target_id": ID of existing section (e.g. "hero-1", "features-1", "pricing-1", "testimonials-1", "faq-1", "contact-1")
   - "content": Optional dictionary of content fields to update (e.g. {{"cta_text": "Book a Trial", "title": "New Title", "fields": ["Name", "Email", "Phone"]}})
   - "style": Optional dictionary of styling overrides (e.g. {{"variant": "dark", "background_color": "#0F172A", "text_color": "#F8FAFC", "layout_variant": "centered"}})

2. add_section:
   - "section_type": One of {SUPPORTED_SECTION_TYPES} (hero, text, image, features, testimonials, pricing, faq, cta, contact)
   - "content": Structured dictionary containing relevant fields for that section type.
     For "faq" sections, always provide at least 5 question and answer items in "items": [{{"question": "...", "answer": "..."}}, ...]
     For "text" sections, always provide structured dictionary with "heading", optional "subheading", and "body" with engaging multi-paragraph narrative text (and optional "image_url").
   - "style": Optional styling overrides (e.g. {{"alignment": "center"|"left"|"right", "padding": "medium"}})
   - "placement": "after" | "before" | "end" | "start" (default "end")
   - "target_id": Optional existing section ID to place relative to (e.g. before "contact-1")

3. remove_section:
   - "target_id": ID of existing section to remove

4. reorder_sections:
   - "section_ids": Complete list of all existing section IDs in the desired new sequence
   OR
   - "target_id": Section ID to move
   - "position": 0-indexed destination index

5. update_theme:
   - "theme": Dictionary of theme properties (e.g. {{"primary_color": "#8B5CF6", "background": "#0F172A", "heading_font": "Playfair Display, serif"}})

CRITICAL RULES:
- COMPOUND EDITS: If the user requests multiple changes (e.g. "Make hero darker, change CTA to Book a Trial, and add an FAQ section"), you MUST decompose them into separate, distinct PatchOperation objects in the "operations" list. NEVER merge distinct edits into a single operation or omit any requested change.
- TARGET EXISTING SECTIONS: Always target existing section IDs from the provided website state context. If a user refers to a section by name (e.g. "About Us" or "Contact"), match it to the corresponding section ID in the state. If no matching section exists, do not hallucinate an ID.
- SECTION ALIGNMENT: When user requests alignment changes (e.g. "Center align contact section", "Align about us to right", "Make contact center aligned"), use "update_section" targeting that section's ID with "style": {{"alignment": "center"|"left"|"right"}}.
- THEME COLORS: When user requests brand/theme/button color changes (e.g. "Make primary color emerald", "Change buttons to purple"), use "update_theme" with "theme": {{"primary_color": "<hex>"}}.
- NEVER generate arbitrary HTML, JavaScript, or executable CSS.
- Do NOT include any star emojis or symbols (e.g. ⭐, ★, ✨, 🌟, ☆, 💫, 🌠) in any website title, brand name, or section headings.
- Output ONLY valid JSON matching the EditPlan schema:
  {{
    "summary": "Short description of changes",
    "operations": [
      {{"op": "update_section", "target_id": "hero-1", "content": {{...}}, "style": {{...}}}},
      ...
    ]
  }}
- Preserve all existing sections and content not explicitly mentioned in the user's edit request.
"""


def _create_deterministic_fallback_edit_plan(instruction: str, state: WebsiteState) -> Optional[EditPlan]:
    """
    Context-aware heuristic fallback for common edit instructions.
    Decomposes compound instructions into separate operations and supports FAQ additions.
    Used when the LLM provider is offline or unreachable.
    """
    lower = instruction.lower().strip()
    sections = state.sections
    existing_ids = [s.id for s in sections]
    hero_sec = next((s for s in sections if s.type == "hero"), None)
    contact_sec = next((s for s in sections if s.type == "contact"), None)
    pricing_sec = next((s for s in sections if s.type == "pricing"), None)
    features_sec = next((s for s in sections if s.type == "features"), None)

    ops: List[PatchOperation] = []
    summaries: List[str] = []

    # 1. Darker hero
    if "hero" in lower and any(k in lower for k in ("dark", "darker", "night", "black")):
        target = hero_sec.id if hero_sec else (existing_ids[0] if existing_ids else "hero-1")
        ops.append(
            PatchOperation(
                op="update_section",
                target_id=target,
                style={
                    "variant": "dark",
                    "background_color": "#0F172A",
                    "text_color": "#F8FAFC",
                },
            )
        )
        summaries.append("Make hero section dark with high contrast text")

    # 2. Change CTA button text
    cta_match = re.search(
        r'(?:change|update|set)\s+(?:the\s+)?(?:hero\s+)?(?:cta|button|cta\s+button)(?:\s+text)?\s+to\s+["\']?([^"\',]+)["\']?',
        instruction,
        re.IGNORECASE,
    )
    if not cta_match:
        cta_match = re.search(r'(?:cta|button)\s+to\s+["\']?([^"\',]+)["\']?', instruction, re.IGNORECASE)
    if cta_match:
        new_cta = cta_match.group(1).strip().strip(".")
        target = hero_sec.id if hero_sec else (existing_ids[0] if existing_ids else "hero-1")
        ops.append(
            PatchOperation(
                op="update_section",
                target_id=target,
                content={"cta_text": new_cta, "button_text": new_cta},
            )
        )
        summaries.append(f"Update CTA text to '{new_cta}'")

    # 2b. Change hero heading or subtitle
    if "hero" in lower and any(k in lower for k in ("heading", "title")) and any(k in lower for k in ("change", "update", "set")):
        title_match = re.search(r'(?:heading|title)\s+to\s+["\']?([^"\',]+)["\']?', instruction, re.IGNORECASE)
        if title_match:
            new_title = title_match.group(1).strip().strip(".")
            target = hero_sec.id if hero_sec else (existing_ids[0] if existing_ids else "hero-1")
            ops.append(
                PatchOperation(
                    op="update_section",
                    target_id=target,
                    content={"title": new_title},
                )
            )
            summaries.append(f"Update hero title to '{new_title}'")

    if "hero" in lower and "subtitle" in lower and any(k in lower for k in ("change", "update", "set")):
        sub_match = re.search(r'subtitle\s+to\s+["\']?([^"\',]+)["\']?', instruction, re.IGNORECASE)
        if sub_match:
            new_sub = sub_match.group(1).strip().strip(".")
            target = hero_sec.id if hero_sec else (existing_ids[0] if existing_ids else "hero-1")
            ops.append(
                PatchOperation(
                    op="update_section",
                    target_id=target,
                    content={"subtitle": new_sub},
                )
            )
            summaries.append(f"Update hero subtitle to '{new_sub}'")

    # 3. Add FAQ section (including 5 Q&A items, placement relative to requested section)
    if "faq" in lower or "frequently asked" in lower or ("question" in lower and "add" in lower):
        target_id = None
        placement = "end"
        if "before contact" in lower and contact_sec:
            target_id = contact_sec.id
            placement = "before"
        elif "before pricing" in lower and pricing_sec:
            target_id = pricing_sec.id
            placement = "before"
        elif "before features" in lower and features_sec:
            target_id = features_sec.id
            placement = "before"
        elif "before" in lower:
            for s in sections:
                if f"before {s.type}" in lower or f"before {s.id}" in lower:
                    target_id = s.id
                    placement = "before"
                    break
            if not target_id and contact_sec:
                target_id = contact_sec.id
                placement = "before"
        elif "after" in lower:
            for s in sections:
                if f"after {s.type}" in lower or f"after {s.id}" in lower:
                    target_id = s.id
                    placement = "after"
                    break
        else:
            if contact_sec:
                target_id = contact_sec.id
                placement = "before"

        ops.append(
            PatchOperation(
                op="add_section",
                section_type="faq",
                content={
                    "heading": "Frequently Asked Questions",
                    "subheading": "Everything you need to know about our services and policies.",
                    "items": [
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
                    ],
                },
                style={"alignment": "center", "padding": "medium"},
                placement=placement,
                target_id=target_id,
            )
        )
        summaries.append(f"Add FAQ section ({placement} {target_id or 'end'})")

    # 4. Add testimonials section
    if "add" in lower and ("testimonial" in lower or "review" in lower):
        if not any(s.type == "testimonials" for s in sections):
            ops.append(
                PatchOperation(
                    op="add_section",
                    section_type="testimonials",
                    content={
                        "heading": "Client Endorsements & Feedback",
                        "subheading": "Verified experiences from our community.",
                        "items": [
                            {
                                "quote": "Remarkable attention to detail and outstanding service from start to finish.",
                                "author": "Morgan Vance",
                                "role": "Verified Client",
                                "tag": "Illustrative Client Feedback",
                                "rating": 5,
                            },
                            {
                                "quote": "Transformed our experience completely. Highly recommend to anyone seeking premium care.",
                                "author": "Dr. Leslie Chen",
                                "role": "Regular Client",
                                "tag": "Illustrative Client Feedback",
                                "rating": 5,
                            },
                        ],
                    },
                    style={"alignment": "center", "layout_variant": "grid"},
                    placement="after",
                    target_id=existing_ids[-2] if len(existing_ids) >= 2 else None,
                )
            )
            summaries.append("Add client testimonials section")

    # 5. Add pricing section
    if "add" in lower and ("pricing" in lower or "package" in lower or "plan" in lower):
        if not any(s.type == "pricing" for s in sections):
            ops.append(
                PatchOperation(
                    op="add_section",
                    section_type="pricing",
                    content={
                        "heading": "Transparent Packages & Pricing",
                        "subheading": "Select the plan that fits your exact requirements.",
                        "plans": [
                            {
                                "name": "Essential",
                                "price": "$89",
                                "description": "Standard comprehensive service.",
                                "features": ["Core service delivery", "Quality assurance", "Direct email support"],
                                "cta_text": "Select Essential",
                            },
                            {
                                "name": "Premier",
                                "price": "$179",
                                "description": "Full-service package with priority support.",
                                "features": ["Complete service delivery", "Priority scheduling", "Dedicated concierge"],
                                "cta_text": "Select Premier",
                                "highlighted": True,
                            },
                        ],
                    },
                    style={"alignment": "center", "layout_variant": "cards"},
                    placement="after",
                    target_id="features-1" if "features-1" in existing_ids else None,
                )
            )
            summaries.append("Add transparent pricing packages section")

    # 5b. Add text section (About Us / Story)
    if "add" in lower and any(k in lower for k in ("about us", "about section", "our story", "story section", "about")):
        if not any(s.type == "text" for s in sections):
            target_id = None
            placement = "after"
            if hero_sec:
                target_id = hero_sec.id
                placement = "after"
            elif features_sec:
                target_id = features_sec.id
                placement = "before"

            ops.append(
                PatchOperation(
                    op="add_section",
                    section_type="text",
                    content={
                        "heading": "Our Story & Commitment",
                        "subheading": "Dedicated to excellence, passion, and personal care.",
                        "body": "Founded with a passion for exceptional quality and genuine client care, we strive to exceed expectations with every service we deliver.\n\nOur team brings certified experience, tailored approaches, and an uncompromising dedication to your peace of mind.",
                    },
                    style={"alignment": "left", "padding": "large"},
                    placement=placement,
                    target_id=target_id,
                )
            )
            summaries.append(f"Add About Us story section ({placement} {target_id or 'start'})")

    # 5c. Update text section (About Us / Story)
    if any(s.type == "text" for s in sections) and any(k in lower for k in ("about", "story")) and any(k in lower for k in ("update", "change", "edit", "heading", "text", "body", "title")):
        text_sec = next(s for s in sections if s.type == "text")
        h_match = re.search(r'(?:heading|title)\s+to\s+["\']?([^"\',]+)["\']?', instruction, re.IGNORECASE)
        b_match = re.search(r'(?:body|text|content|description)\s+to\s+["\']?([^"\']+)["\']?', instruction, re.IGNORECASE)
        c_updates = {}
        if h_match:
            c_updates["heading"] = h_match.group(1).strip()
        if b_match:
            c_updates["body"] = b_match.group(1).strip()
        if not c_updates:
            c_updates["body"] = "We are dedicated to delivering premium, personalized service with attention to every single detail.\n\nOur journey is built on trust, craft, and lasting community relationships."
        ops.append(
            PatchOperation(
                op="update_section",
                target_id=text_sec.id,
                content=c_updates,
            )
        )
        summaries.append(f"Update {text_sec.id} text section content")

    # 6. Remove section
    if any(k in lower for k in ("remove", "delete", "drop", "hide")):
        for s in sections:
            if s.type in lower or s.id in lower:
                ops.append(
                    PatchOperation(
                        op="remove_section",
                        target_id=s.id,
                    )
                )
                summaries.append(f"Remove section '{s.id}' ({s.type})")
                break

    # 7. Section Alignment updates (e.g. "center align contact section", "align contact to center")
    if any(k in lower for k in ("align", "alignment", "center", "left align", "right align")):
        target_sec = None
        if "contact" in lower:
            target_sec = contact_sec
        elif "about" in lower or "story" in lower or "text" in lower:
            target_sec = next((s for s in sections if s.type == "text"), None)
        elif "hero" in lower:
            target_sec = hero_sec

        align_val = "center"
        if "left" in lower:
            align_val = "left"
        elif "right" in lower:
            align_val = "right"

        if target_sec:
            ops.append(
                PatchOperation(
                    op="update_section",
                    target_id=target_sec.id,
                    style={"alignment": align_val},
                )
            )
            summaries.append(f"Set {target_sec.id} alignment to {align_val}")
        elif "contact" in lower or ("center" in lower and contact_sec):
            target = contact_sec.id if contact_sec else "contact-1"
            ops.append(
                PatchOperation(
                    op="update_section",
                    target_id=target,
                    style={"alignment": align_val},
                )
            )
            summaries.append(f"Set {target} alignment to {align_val}")

    # 8. Theme / Color updates
    if any(k in lower for k in ("primary color", "theme color", "brand color", "change color", "color to", "make primary", "theme to", "emerald", "palette", "button color", "buttons to", "button to", "buttons green", "buttons blue", "buttons purple")):
        color_hex = "#2563EB"
        hex_match = re.search(r"#(?:[0-9a-fA-F]{3}){1,2}\b", instruction)
        if hex_match:
            color_hex = hex_match.group(0).upper()
        elif "purple" in lower:
            color_hex = "#7C3AED"
        elif "green" in lower or "emerald" in lower:
            color_hex = "#10B981"
        elif "orange" in lower:
            color_hex = "#F97316"
        elif "red" in lower:
            color_hex = "#DC2626"
        elif "amber" in lower or "gold" in lower or "yellow" in lower:
            color_hex = "#D97706"
        elif "blue" in lower or "navy" in lower:
            color_hex = "#1E40AF"

        ops.append(
            PatchOperation(
                op="update_theme",
                theme={"primary_color": color_hex},
            )
        )
        summaries.append(f"Update primary brand color to {color_hex}")

    # 8b. Background color update
    if "background" in lower and any(k in lower for k in ("theme", "site", "website", "to", "set")) and re.search(r"#(?:[0-9a-fA-F]{3}){1,2}\b", instruction):
        hex_match = re.search(r"#(?:[0-9a-fA-F]{3}){1,2}\b", instruction)
        bg_hex = hex_match.group(0).upper()
        ops.append(
            PatchOperation(
                op="update_theme",
                theme={"background": bg_hex},
            )
        )
        summaries.append(f"Update theme background color to {bg_hex}")

    # 8. Dark theme global
    if "dark mode" in lower or "dark theme" in lower or "make whole website dark" in lower or "make website dark" in lower:
        ops.append(
            PatchOperation(
                op="update_theme",
                theme={
                    "background": "#0F172A",
                    "text_color": "#F8FAFC",
                    "background_style": "dark_glow",
                    "nav_style": "sticky_glass",
                },
            )
        )
        summaries.append("Switch website theme to sleek dark mode")

    # 9. Reorder sections (e.g. move pricing before features)
    if "reorder" in lower or "move" in lower:
        if "pricing" in lower and "features" in lower and "pricing-1" in existing_ids and "features-1" in existing_ids:
            new_ids = list(existing_ids)
            p_idx = new_ids.index("pricing-1")
            f_idx = new_ids.index("features-1")
            if p_idx > f_idx:
                new_ids.remove("pricing-1")
                new_ids.insert(f_idx, "pricing-1")
                ops.append(
                    PatchOperation(
                        op="reorder_sections",
                        section_ids=new_ids,
                    )
                )
                summaries.append("Reorder pricing before features")

    # 10. Modify form fields
    if ("form" in lower or "contact" in lower) and ("field" in lower or "add phone" in lower or "require" in lower):
        target = contact_sec.id if contact_sec else "contact-1"
        ops.append(
            PatchOperation(
                op="update_section",
                target_id=target,
                content={
                    "fields": ["Full Name", "Email Address", "Phone Number", "Preferred Date", "Detailed Message"],
                },
            )
        )
        summaries.append("Update contact form fields")

    if ops:
        return EditPlan(
            summary="; ".join(summaries),
            operations=ops,
        )

    return None


def plan_edits(
    instruction: str,
    state: WebsiteState,
    provider: Optional[BaseProvider] = None,
    provider_name: Optional[str] = None,
) -> EditPlan:
    """
    Generate an EditPlan of deterministic patch operations from a user natural language edit request.
    Uses configured LLM provider via dependency injection or provider factory with bounded 1-step repair.
    Provides graceful error handling and deterministic offline fallbacks.
    """
    clean_instr = (instruction or "").strip()
    if not clean_instr:
        raise EditAgentError("Edit instruction cannot be empty.")

    # 1. Obtain active provider via dependency injection or factory
    active_provider: Optional[BaseProvider] = provider
    provider_init_error: Optional[str] = None

    if active_provider is None:
        try:
            active_provider = get_provider(provider_override=provider_name)
        except Exception as p_err:
            logger.warning("Could not initialize LLM provider via factory: %s", p_err)
            provider_init_error = str(p_err)
            active_provider = None

    # If provider could not be initialized, attempt deterministic fallback
    if active_provider is None:
        fallback_plan = _create_deterministic_fallback_edit_plan(clean_instr, state)
        if fallback_plan and fallback_plan.operations:
            logger.info("Provider unavailable; successfully applied deterministic fallback for '%s'", clean_instr)
            return fallback_plan
        raise EditAgentError(
            f"LLM provider initialization error ({provider_init_error or 'Provider unconfigured'}). "
            f"Unable to process edit instruction: '{clean_instr}'"
        )

    # 2. Format state context for LLM
    theme_info = state.theme.model_dump()
    sections_summary = []
    for s in state.sections:
        c = s.content
        summary_parts = [f"ID: '{s.id}' (type: {s.type})"]
        if "title" in c:
            summary_parts.append(f"title: '{c['title']}'")
        if "heading" in c:
            summary_parts.append(f"heading: '{c['heading']}'")
        if "cta_text" in c:
            summary_parts.append(f"cta_text: '{c['cta_text']}'")
        if "form_type" in c:
            summary_parts.append(f"form_type: '{c['form_type']}'")
        sections_summary.append(" - " + ", ".join(summary_parts))

    user_prompt = f"""USER EDIT INSTRUCTION:
"{clean_instr}"

CURRENT WEBSITE STATE CONTEXT:
- Title: "{state.title}" (Version: v{state.version})
- Theme: {json.dumps(theme_info)}
- Existing Sections (Ordered):
{chr(10).join(sections_summary)}

Produce an EditPlan JSON object containing:
- "summary": Clear concise description of edits
- "operations": List of deterministic patch operations matching schema
Target existing section IDs where applicable. Never produce raw HTML.
"""

    # 3. LLM Completion with exception handling
    try:
        response = active_provider.complete(
            prompt=user_prompt,
            system_prompt=EDIT_AGENT_SYSTEM_PROMPT,
            temperature=0.1,
        )
    except Exception as api_err:
        logger.warning("LLM provider complete() call raised exception: %s. Attempting fallback.", api_err)
        fallback_plan = _create_deterministic_fallback_edit_plan(clean_instr, state)
        if fallback_plan and fallback_plan.operations:
            return fallback_plan
        raise EditAgentError(
            f"LLM provider API error: {str(api_err)}. Unable to process edit request: '{clean_instr}'"
        )

    # 4. Provider failure handling
    if not response.success or not response.content:
        logger.warning("Edit Agent LLM call failed (%s). Attempting deterministic fallback.", response.error)
        fallback_plan = _create_deterministic_fallback_edit_plan(clean_instr, state)
        if fallback_plan and fallback_plan.operations:
            return fallback_plan
        raise EditAgentError(
            f"LLM provider completion failed ({response.error or 'no response content'}). "
            f"Unable to process edit request: '{clean_instr}'"
        )

    # 5. First Attempt Validation
    parsed_json = extract_json_from_text(response.content)
    if parsed_json and isinstance(parsed_json, dict):
        try:
            return EditPlan.model_validate(parsed_json)
        except ValidationError as v_err:
            logger.warning("EditPlan validation failed on first attempt: %s. Initiating 1 repair.", v_err)
            repair_error = str(v_err)
    else:
        logger.warning("Could not extract JSON from Edit Agent output. Initiating 1 repair.")
        repair_error = "Response did not contain a valid JSON object matching EditPlan schema."

    # 6. Bounded 1-Step Repair Attempt
    repair_prompt = f"""Your previous EditPlan response failed validation:
{repair_error}

User instruction was: "{clean_instr}"
Existing section IDs in state: {[s.id for s in state.sections]}

Return ONLY valid JSON matching EditPlan:
{{
  "summary": "Brief summary",
  "operations": [
    {{"op": "update_section", "target_id": "hero-1", "content": {{...}}, "style": {{...}}}}
  ]
}}
Raw Output to fix:
{response.content[:600]}
"""

    try:
        repair_response = active_provider.complete(
            prompt=repair_prompt,
            system_prompt="You are a JSON schema repair agent. Return ONLY strictly valid EditPlan JSON without prose.",
            temperature=0.0,
        )
        if repair_response.success and repair_response.content:
            repaired_json = extract_json_from_text(repair_response.content)
            if repaired_json and isinstance(repaired_json, dict):
                try:
                    return EditPlan.model_validate(repaired_json)
                except ValidationError as err:
                    logger.warning("Repair attempt also failed validation: %s", err)
    except Exception as rep_err:
        logger.warning("Repair attempt call raised exception: %s", rep_err)

    # 7. Final fallback or clean error reporting
    fallback_plan = _create_deterministic_fallback_edit_plan(clean_instr, state)
    if fallback_plan and fallback_plan.operations:
        return fallback_plan

    raise EditAgentError(
        f"Edit Agent failed to produce valid patch operations after 1 repair attempt: {repair_error}"
    )
