"""
Renderer module for SitePilot AI.
Safely transforms validated WebsiteState into professional, responsive HTML/CSS.
Supports hybrid template layout variants for Hero, Features, Pricing, and Testimonials.
All user and model text is strictly escaped to prevent XSS or arbitrary execution.
All CTA and navigation links use robust anchor resolution to prevent iframe replacement.
"""

import html
import re
from typing import Any, Dict, List, Optional
from src.schema import WebsiteState, Section, SectionStyle
from src.image_service import retrieve_image_for_description


def sanitize_url(url: Optional[str]) -> str:
    """
    Sanitize and escape URLs to prevent script injection (e.g. javascript:).
    Allows http, https, #anchors, mailto, and tel.
    """
    if not url:
        return "#"
    clean = url.strip()
    if re.match(r"^\s*(javascript|data|vbscript):", clean, re.IGNORECASE):
        return "#"
    return html.escape(clean, quote=True)


def escape_text(text: Any) -> str:
    """Convert any value to string and safely HTML escape it."""
    if text is None:
        return ""
    return html.escape(str(text))


# -----------------------------------------------------------------------------
# Safe Anchor & Navigation Resolution
# -----------------------------------------------------------------------------

def resolve_target_section_id(raw_target: Optional[str], sections: List[Section]) -> str:
    """
    Resolve any CTA or nav link target into a guaranteed matching section ID.
    Maps intents like '#contact', 'booking', '#pricing', '#services' to existing section IDs.
    """
    if not sections:
        return "top"

    existing_ids = [s.id for s in sections]
    type_map = {s.type: s.id for s in sections}

    if not raw_target:
        return type_map.get("contact") or type_map.get("cta") or sections[0].id

    clean = raw_target.strip().lstrip("#").lower()

    if clean in existing_ids:
        return clean

    if any(k in clean for k in ("contact", "book", "appoint", "trial", "start", "quote", "inquir")):
        return type_map.get("contact") or type_map.get("cta") or sections[-1].id

    if any(k in clean for k in ("price", "pricing", "plan", "pack", "tier", "cost")):
        return type_map.get("pricing") or sections[0].id

    if any(k in clean for k in ("feature", "service", "what", "benefit", "why")):
        return type_map.get("features") or sections[0].id

    if any(k in clean for k in ("testimoni", "review", "story", "client", "rating")):
        return type_map.get("testimonials") or sections[0].id

    if any(k in clean for k in ("about", "story", "text")):
        return type_map.get("text") or sections[0].id

    if any(k in clean for k in ("hero", "home", "top")):
        return type_map.get("hero") or sections[0].id

    return type_map.get("contact") or sections[0].id


def render_action_link(
    raw_href: Optional[str],
    text: str,
    css_class: str = "btn btn-primary",
    sections: Optional[List[Section]] = None,
) -> str:
    """
    Render a safe link or CTA button.
    External links open in new tab; internal anchors smooth scroll safely without iframe replacement.
    """
    safe_text = escape_text(text)
    clean_href = (raw_href or "").strip()

    if clean_href.startswith(("http://", "https://")):
        safe_url = sanitize_url(clean_href)
        return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" class="{css_class}">{safe_text}</a>'

    if clean_href.startswith(("mailto:", "tel:")):
        safe_url = sanitize_url(clean_href)
        return f'<a href="{safe_url}" class="{css_class}">{safe_text}</a>'

    target_id = resolve_target_section_id(clean_href, sections or [])
    onclick_js = (
        f"event.preventDefault(); var target = document.getElementById('{target_id}'); "
        "if(target) { target.scrollIntoView({behavior: 'smooth', block: 'start'}); }"
    )

    return f'<a href="#{target_id}" onclick="{onclick_js}" class="{css_class}">{safe_text}</a>'


def get_section_style_css(style: SectionStyle, default_bg: str, default_text: str) -> str:
    """Compute inline CSS declarations from SectionStyle."""
    styles = []

    if style.background_color:
        styles.append(f"background-color: {escape_text(style.background_color)};")
    elif style.variant == "dark":
        styles.append("background-color: #0f172a;")
    elif style.variant == "light":
        styles.append("background-color: #f8fafc;")

    if style.text_color:
        styles.append(f"color: {escape_text(style.text_color)};")
    elif style.variant == "dark":
        styles.append("color: #f8fafc;")
    elif style.variant == "light":
        styles.append("color: #1e293b;")

    padding_map = {
        "small": "40px 24px",
        "medium": "72px 24px",
        "large": "96px 24px",
    }
    padding_val = padding_map.get(style.padding or "medium", "72px 24px")
    styles.append(f"padding: {padding_val};")

    if style.alignment in ("left", "center", "right"):
        styles.append(f"text-align: {style.alignment};")

    return " ".join(styles)


# -----------------------------------------------------------------------------
# Safe Visual Media Rendering with Graceful Placeholder Fallback
# -----------------------------------------------------------------------------

def render_visual_media(
    image_url: Optional[str] = None,
    image_description: Optional[str] = None,
    alt: str = "Showcase Visual",
    css_class: str = "",
    overlay_badge: Optional[str] = None,
    card_highlight: Optional[str] = None,
) -> str:
    """
    Safely render an image with fallback to an attractive visual placeholder card.
    If image_url is missing or fails to load, gracefully displays a stylized CSS card
    with an icon, title, and description, avoiding broken images or invented URLs.
    """
    safe_alt = escape_text(alt)
    safe_desc = escape_text(image_description or "")
    badge_html_parts = []
    if overlay_badge:
        badge_html_parts.append(f'<div class="floating-badge top-badge">{escape_text(overlay_badge)}</div>')
    if card_highlight:
        badge_html_parts.append(
            f'<div class="floating-badge bottom-badge">'
            f'<span class="badge-label">Highlight</span>'
            f'<span class="badge-value">{escape_text(card_highlight)}</span>'
            f'</div>'
        )
    badges_markup = "\n".join(badge_html_parts)

    placeholder_card = (
        f'<div class="visual-placeholder-card">'
        f'<div class="placeholder-icon">✨</div>'
        f'<div class="placeholder-title">{safe_alt}</div>'
        f'{"<p class=\"placeholder-desc\">" + safe_desc + "</p>" if safe_desc else ""}'
        f'<div class="placeholder-tag">Showcase Feature</div>'
        f'</div>'
    )

    if image_url and str(image_url).strip().startswith(("http://", "https://")):
        safe_src = sanitize_url(image_url)
        return (
            f'<div class="visual-media-box {css_class}">'
            f'<img src="{safe_src}" alt="{safe_alt}" class="visual-media-img" loading="lazy" '
            f'onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';" />'
            f'<div class="visual-placeholder-card" style="display: none;">'
            f'<div class="placeholder-icon">✨</div>'
            f'<div class="placeholder-title">{safe_alt}</div>'
            f'{"<p class=\"placeholder-desc\">" + safe_desc + "</p>" if safe_desc else ""}'
            f'<div class="placeholder-tag">Showcase Feature</div>'
            f'</div>'
            f'{badges_markup}'
            f'</div>'
        )

    return (
        f'<div class="visual-media-box {css_class}">'
        f'{placeholder_card}'
        f'{badges_markup}'
        f'</div>'
    )


# -----------------------------------------------------------------------------
# Component Renderers & Layout Variants
# -----------------------------------------------------------------------------

def render_hero_section(section: Section, all_sections: Optional[List[Section]] = None) -> str:
    """
    Render Hero section supporting 3 layout variants:
    1. 'split' (default): 2-column layout with left content and right visual card.
    2. 'centered': Focused headline, subtitle, buttons, trust bar, and showcase image below.
    3. 'minimal': Editorial asymmetric layout with bold typography and stat callouts.
    """
    c = section.content
    all_sec = all_sections or [section]
    variant = (section.style.layout_variant or c.get("layout_variant") or "split").lower()

    title = escape_text(c.get("title", "Elevate Your Experience"))
    subtitle = escape_text(c.get("subtitle", ""))
    pill_badge = escape_text(c.get("pill_badge") or c.get("badge") or "✨ Premier Quality & Care")

    cta_text = c.get("cta_text") or c.get("cta") or "Book Appointment"
    cta_link = c.get("cta_link", "#contact-1")
    primary_btn = render_action_link(cta_link, cta_text, css_class="btn btn-primary btn-large", sections=all_sec)

    sec_btn_text = c.get("secondary_cta_text") or "Explore Packages"
    sec_btn_link = c.get("secondary_cta_link") or "#pricing-1"
    secondary_btn = render_action_link(sec_btn_link, sec_btn_text, css_class="btn btn-secondary btn-large", sections=all_sec)

    trust_items = c.get("trust_points") or [
        "Certified Specialists",
        "100% Satisfaction Guarantee",
        "Gentle & Personalized Care",
    ]
    trust_html = "".join([f'<span class="trust-badge">✓ {escape_text(t)}</span>' for t in trust_items])

    image_url = c.get("image_url")
    image_desc = c.get("image_description") or c.get("image_prompt")
    if not image_url and image_desc:
        image_url = retrieve_image_for_description(image_desc)

    rating_badge = escape_text(c.get("rating") or "Client Rating 4.9★")
    card_highlight = escape_text(c.get("highlight_service") or "Top Rated Experience")

    visual_media_html = render_visual_media(
        image_url=image_url,
        image_description=image_desc or f"Showcase visual for {title}",
        alt=title,
        css_class="hero-visual-card",
        overlay_badge=rating_badge,
        card_highlight=card_highlight,
    )

    # Variant A: Centered Layout
    if variant == "centered":
        return f"""
        <div class="container hero-centered">
            <div class="pill-tag">{pill_badge}</div>
            <h1 class="hero-title hero-title-center">{title}</h1>
            {f'<p class="hero-subtitle hero-sub-center">{subtitle}</p>' if subtitle else ''}
            <div class="hero-actions hero-actions-center">
                {primary_btn}
                {secondary_btn}
            </div>
            <div class="hero-trust-row hero-trust-center">
                {trust_html}
            </div>
            <div class="hero-showcase-box">
                {visual_media_html}
            </div>
        </div>
        """

    # Variant B: Minimal Editorial Layout
    elif variant == "minimal":
        return f"""
        <div class="container hero-minimal">
            <div class="pill-tag">{pill_badge}</div>
            <div class="hero-minimal-row">
                <div class="hero-minimal-left">
                    <h1 class="hero-title">{title}</h1>
                </div>
                <div class="hero-minimal-right">
                    {f'<p class="hero-subtitle">{subtitle}</p>' if subtitle else ''}
                    <div class="hero-actions">
                        {primary_btn}
                        {secondary_btn}
                    </div>
                    <div class="minimal-stats-bar">
                        <div class="stat-item"><span class="stat-num">500+</span><span class="stat-lbl">Clients</span></div>
                        <div class="stat-item"><span class="stat-num">4.9★</span><span class="stat-lbl">Rating</span></div>
                        <div class="stat-item"><span class="stat-num">100%</span><span class="stat-lbl">Guaranteed</span></div>
                    </div>
                </div>
            </div>
        </div>
        """

    # Variant C (Default): Split 2-Column with Visual Card
    return f"""
    <div class="container hero-grid">
        <div class="hero-content">
            <div class="pill-tag">{pill_badge}</div>
            <h1 class="hero-title">{title}</h1>
            {f'<p class="hero-subtitle">{subtitle}</p>' if subtitle else ''}
            <div class="hero-actions">
                {primary_btn}
                {secondary_btn}
            </div>
            <div class="hero-trust-row">
                {trust_html}
            </div>
        </div>
        <div class="hero-visual">
            {visual_media_html}
        </div>
    </div>
    """


def render_features_section(section: Section, all_sections: Optional[List[Section]] = None) -> str:
    """
    Render Features section supporting 3 layout variants:
    1. 'grid' (default): 3-4 column modern card grid with icon box and tag.
    2. 'pill_cards': Circular category pills row followed by feature highlights.
    3. 'list': Alternating horizontal feature rows with detailed highlights.
    """
    c = section.content
    variant = (section.style.layout_variant or c.get("layout_variant") or "grid").lower()

    heading = escape_text(c.get("heading", "Our Premier Services"))
    subheading = escape_text(c.get("subheading", "Designed with exceptional care and attention to detail."))
    items = c.get("items", [])

    # Variant A: Circular Pill Cards (inspired by Reference Image 2)
    if variant == "pill_cards":
        pill_items_html = []
        for item in items:
            if isinstance(item, dict):
                i_title = escape_text(item.get("title", "Service"))
                i_icon = escape_text(item.get("icon", "🐾"))
                pill_items_html.append(
                    f"""
                    <div class="pill-cat-item">
                        <div class="pill-cat-circle">{i_icon}</div>
                        <span class="pill-cat-label">{i_title}</span>
                    </div>
                    """
                )

        highlights_html = []
        for item in items[:4]:
            if isinstance(item, dict):
                i_title = escape_text(item.get("title", "Feature"))
                i_desc = escape_text(item.get("description", "Quality care you can rely on."))
                i_icon = escape_text(item.get("icon", "✨"))
                highlights_html.append(
                    f"""
                    <div class="apart-item">
                        <div class="apart-icon">{i_icon}</div>
                        <div>
                            <h4>{i_title}</h4>
                            <p>{i_desc}</p>
                        </div>
                    </div>
                    """
                )

        return f"""
        <div class="container">
            <div class="section-header-center">
                <h2 class="section-title">{heading}</h2>
                {f'<p class="section-subtitle">{subheading}</p>' if subheading else ''}
            </div>
            <div class="pill-categories-row">
                {''.join(pill_items_html)}
            </div>
            <div class="apart-panel">
                <h3 class="apart-panel-title">What Sets Us Apart</h3>
                <div class="apart-grid">
                    {''.join(highlights_html)}
                </div>
            </div>
        </div>
        """

    # Variant B: Detailed Horizontal List
    elif variant == "list":
        list_html = []
        for i, item in enumerate(items, 1):
            if isinstance(item, dict):
                i_title = escape_text(item.get("title", "Feature"))
                i_desc = escape_text(item.get("description", "Designed for exceptional results."))
                i_icon = escape_text(item.get("icon", "⭐"))
                list_html.append(
                    f"""
                    <div class="feature-list-row">
                        <span class="list-step-num">0{i}</span>
                        <div class="list-icon-box">{i_icon}</div>
                        <div class="list-body">
                            <h3 class="feature-title">{i_title}</h3>
                            <p class="feature-desc">{i_desc}</p>
                        </div>
                    </div>
                    """
                )

        return f"""
        <div class="container">
            <div class="section-header-center">
                <h2 class="section-title">{heading}</h2>
                {f'<p class="section-subtitle">{subheading}</p>' if subheading else ''}
            </div>
            <div class="features-list-wrapper">
                {''.join(list_html)}
            </div>
        </div>
        """

    # Variant C (Default): 3-Column Modern Grid
    cards_html = []
    for item in items:
        if isinstance(item, dict):
            i_title = escape_text(item.get("title", "Specialized Care"))
            i_desc = escape_text(item.get("description", "Delivering premium results tailored to your needs."))
            i_icon = escape_text(item.get("icon", "✨"))
            i_tag = escape_text(item.get("tag") or item.get("badge") or "")
            tag_html = f'<span class="feature-tag">{i_tag}</span>' if i_tag else ""

            cards_html.append(
                f"""
                <div class="feature-card">
                    <div class="feature-card-header">
                        <div class="feature-icon-box">{i_icon}</div>
                        {tag_html}
                    </div>
                    <h3 class="feature-title">{i_title}</h3>
                    <p class="feature-desc">{i_desc}</p>
                </div>
                """
            )

    return f"""
    <div class="container">
        <div class="section-header-center">
            <h2 class="section-title">{heading}</h2>
            {f'<p class="section-subtitle">{subheading}</p>' if subheading else ''}
        </div>
        <div class="features-grid">
            {''.join(cards_html)}
        </div>
    </div>
    """


def render_pricing_section(section: Section, all_sections: Optional[List[Section]] = None) -> str:
    """
    Render Pricing section supporting 2 layout variants:
    1. 'cards' (default): 3-column vertical comparison cards with top price pill.
    2. 'table': Horizontal wide package rows with price badges and inline CTA buttons.
    """
    c = section.content
    all_sec = all_sections or [section]
    variant = (section.style.layout_variant or c.get("layout_variant") or "cards").lower()

    heading = escape_text(c.get("heading", "Our Packages & Pricing"))
    subheading = escape_text(c.get("subheading", "Transparent pricing with no hidden surprises."))
    plans = c.get("plans", [])

    # Variant A: Horizontal Table / Rows
    if variant in ("table", "rows"):
        rows_html = []
        for i, plan in enumerate(plans):
            if isinstance(plan, dict):
                p_name = escape_text(plan.get("name", "Standard Package"))
                p_price = escape_text(plan.get("price", "$99"))
                p_desc = escape_text(plan.get("description", "Comprehensive care session."))
                p_cta = plan.get("cta_text") or "Book Package"
                is_highlighted = plan.get("highlighted", i == 1)

                features = plan.get("features", [])
                feature_chips = "".join([f'<span class="feature-chip">✓ {escape_text(f)}</span>' for f in features])

                btn_class = "btn btn-primary" if is_highlighted else "btn btn-secondary"
                action_btn = render_action_link("#contact", p_cta, css_class=btn_class, sections=all_sec)

                row_class = "pricing-row-card featured-row" if is_highlighted else "pricing-row-card"

                rows_html.append(
                    f"""
                    <div class="{row_class}">
                        <div class="row-left">
                            <h3 class="plan-name">{p_name}</h3>
                            <p class="plan-desc">{p_desc}</p>
                            <div class="feature-chips-box">
                                {feature_chips}
                            </div>
                        </div>
                        <div class="row-right">
                            <div class="price-pill-lg">{p_price}</div>
                            {action_btn}
                        </div>
                    </div>
                    """
                )

        return f"""
        <div class="container">
            <div class="section-header-center">
                <h2 class="section-title">{heading}</h2>
                {f'<p class="section-subtitle">{subheading}</p>' if subheading else ''}
            </div>
            <div class="pricing-rows-container">
                {''.join(rows_html)}
            </div>
        </div>
        """

    # Variant B (Default): Vertical Cards
    cards_html = []
    for i, plan in enumerate(plans):
        if isinstance(plan, dict):
            p_name = escape_text(plan.get("name", "Standard Package"))
            p_price = escape_text(plan.get("price", "$99"))
            p_desc = escape_text(plan.get("description", "Comprehensive care tailored to your needs."))
            p_cta = plan.get("cta_text") or "Book Package"
            is_highlighted = plan.get("highlighted", i == 1)

            features = plan.get("features", [])
            feature_list_html = "".join(
                [f'<li><span class="check-icon">✓</span> {escape_text(f)}</li>' for f in features]
            )

            btn_class = "btn btn-primary btn-block" if is_highlighted else "btn btn-secondary btn-block"
            action_btn = render_action_link("#contact", p_cta, css_class=btn_class, sections=all_sec)

            highlight_class = "pricing-card featured-card" if is_highlighted else "pricing-card"
            badge_html = '<span class="popular-pill">Most Popular</span>' if is_highlighted else ""

            cards_html.append(
                f"""
                <div class="{highlight_class}">
                    <div class="pricing-card-header">
                        {badge_html}
                        <div class="price-pill">{p_price}</div>
                        <h3 class="plan-name">{p_name}</h3>
                        <p class="plan-desc">{p_desc}</p>
                    </div>
                    <div class="pricing-divider"></div>
                    <ul class="plan-features">
                        {feature_list_html}
                    </ul>
                    <div class="pricing-card-footer">
                        {action_btn}
                    </div>
                </div>
                """
            )

    return f"""
    <div class="container">
        <div class="section-header-center">
            <h2 class="section-title">{heading}</h2>
            {f'<p class="section-subtitle">{subheading}</p>' if subheading else ''}
        </div>
        <div class="pricing-grid">
            {''.join(cards_html)}
        </div>
    </div>
    """


def render_testimonials_section(section: Section, all_sections: Optional[List[Section]] = None) -> str:
    """
    Render Testimonials section supporting 2 layout variants:
    1. 'grid' (default): Multi-column review cards.
    2. 'spotlight': Large featured spotlight testimonial banner accompanied by client reviews.
    """
    c = section.content
    variant = (section.style.layout_variant or c.get("layout_variant") or "grid").lower()

    heading = escape_text(c.get("heading", "Loved by Our Community"))
    subheading = escape_text(c.get("subheading", "Real feedback from genuine clients and families."))
    items = c.get("items", [])

    # Variant A: Spotlight Testimonial
    if variant == "spotlight" and items:
        featured = items[0] if isinstance(items[0], dict) else {}
        quote = escape_text(featured.get("quote", "An exceptional experience from start to finish!"))
        author = escape_text(featured.get("author", "Valued Client"))
        role = escape_text(featured.get("role", "Verified Member"))

        supporting_cards = []
        for item in items[1:]:
            if isinstance(item, dict):
                s_quote = escape_text(item.get("quote", ""))
                s_author = escape_text(item.get("author", "Customer"))
                supporting_cards.append(
                    f"""
                    <div class="spotlight-sub-card">
                        <div class="star-rating">★★★★★</div>
                        <p class="testimonial-quote">“{s_quote}”</p>
                        <span class="author-name">{s_author}</span>
                    </div>
                    """
                )

        return f"""
        <div class="container">
            <div class="section-header-center">
                <h2 class="section-title">{heading}</h2>
                {f'<p class="section-subtitle">{subheading}</p>' if subheading else ''}
            </div>
            <div class="testimonial-spotlight-wrapper">
                <div class="spotlight-main-card">
                    <div class="spotlight-quote-mark">“</div>
                    <div class="star-rating">★★★★★</div>
                    <blockquote class="spotlight-quote">{quote}</blockquote>
                    <div class="spotlight-author-row">
                        <div class="author-avatar">{author[:1]}</div>
                        <div>
                            <div class="author-name">{author}</div>
                            <div class="author-role">{role}</div>
                        </div>
                    </div>
                </div>
                {f'<div class="spotlight-side-cards">{"".join(supporting_cards)}</div>' if supporting_cards else ''}
            </div>
        </div>
        """

    # Variant B (Default): Multi-Column Cards Grid
    cards_html = []
    for item in items:
        if isinstance(item, dict):
            quote = escape_text(item.get("quote", "An exceptional experience!"))
            author = escape_text(item.get("author", "Valued Client"))
            role = escape_text(item.get("role", "Verified Customer"))
            avatar_letter = author[:1].upper() if author else "C"

            cards_html.append(
                f"""
                <div class="testimonial-card">
                    <div class="star-rating">★★★★★</div>
                    <p class="testimonial-quote">“{quote}”</p>
                    <div class="testimonial-author-box">
                        <div class="author-avatar">{avatar_letter}</div>
                        <div class="author-info">
                            <span class="author-name">{author}</span>
                            <span class="author-role">{role}</span>
                        </div>
                    </div>
                </div>
                """
            )

    return f"""
    <div class="container">
        <div class="section-header-center">
            <h2 class="section-title">{heading}</h2>
            {f'<p class="section-subtitle">{subheading}</p>' if subheading else ''}
        </div>
        <div class="testimonials-grid">
            {''.join(cards_html)}
        </div>
    </div>
    """


def render_text_section(section: Section, all_sections: Optional[List[Section]] = None) -> str:
    """Render Text section with heading, subtitle, and formatted narrative paragraphs."""
    c = section.content
    heading = escape_text(c.get("heading", ""))
    subheading = escape_text(c.get("subheading", ""))
    body = escape_text(c.get("body", ""))

    heading_html = f'<h2 class="section-title">{heading}</h2>' if heading else ""
    sub_html = f'<p class="section-subtitle">{subheading}</p>' if subheading else ""

    paragraphs = [p.strip() for p in body.split("\n") if p.strip()]
    paragraphs_html = "".join([f'<p class="text-body">{p}</p>' for p in paragraphs])

    return f"""
    <div class="container text-container">
        {heading_html}
        {sub_html}
        <div class="text-card">
            {paragraphs_html}
        </div>
    </div>
    """


def render_image_section(section: Section, all_sections: Optional[List[Section]] = None) -> str:
    """Render responsive Image section with caption or graceful visual placeholder."""
    c = section.content
    image_url = c.get("url") or c.get("image_url")
    image_desc = c.get("image_description") or c.get("alt")
    if not image_url and image_desc:
        image_url = retrieve_image_for_description(image_desc)

    alt = c.get("alt", "Visual Showcase")
    caption = escape_text(c.get("caption", ""))
    caption_html = f'<p class="image-caption">{caption}</p>' if caption else ""

    media_html = render_visual_media(
        image_url=image_url,
        image_description=image_desc,
        alt=alt,
        css_class="standalone-image-box",
    )

    return f"""
    <div class="container image-container">
        <div class="image-wrapper">
            {media_html}
            {caption_html}
        </div>
    </div>
    """


def render_cta_section(section: Section, all_sections: Optional[List[Section]] = None) -> str:
    """Render CTA conversion banner with high contrast and prominent action."""
    c = section.content
    all_sec = all_sections or [section]
    heading = escape_text(c.get("heading", "Ready to Get Started?"))
    subheading = escape_text(c.get("subheading", "Book your visit today and experience the difference."))
    button_text = c.get("button_text") or c.get("cta_text") or "Book Appointment Now"
    button_link = c.get("button_link", "#contact")

    action_btn = render_action_link(button_link, button_text, css_class="btn btn-primary btn-large", sections=all_sec)

    return f"""
    <div class="container cta-card">
        <h2 class="cta-heading">{heading}</h2>
        {f'<p class="cta-subheading">{subheading}</p>' if subheading else ''}
        <div class="cta-btn-wrapper">
            {action_btn}
        </div>
    </div>
    """


def render_contact_section(section: Section, all_sections: Optional[List[Section]] = None) -> str:
    """Render Contact & Appointment Booking section with company info and interactive inquiry form."""
    c = section.content
    heading = escape_text(c.get("heading", "Book Your Appointment"))
    subheading = escape_text(c.get("subheading", "Select your preferences below or contact our friendly team directly."))
    email = escape_text(c.get("email", "hello@studio.com"))
    phone = escape_text(c.get("phone", "(555) 234-5678"))
    hours = escape_text(c.get("hours", "Monday – Saturday: 8:00 AM – 6:00 PM"))
    fields = c.get("fields", ["Full Name", "Phone or Email", "Service Needed", "Preferred Date & Time"])

    info_items = [
        f'<div class="contact-info-row"><span class="contact-icon">📞</span> <div><strong>Phone:</strong><br><a href="tel:{phone}">{phone}</a></div></div>',
        f'<div class="contact-info-row"><span class="contact-icon">📧</span> <div><strong>Email:</strong><br><a href="mailto:{email}">{email}</a></div></div>',
        f'<div class="contact-info-row"><span class="contact-icon">🕒</span> <div><strong>Hours:</strong><br>{hours}</div></div>',
    ]

    form_fields_html = []
    for field in fields:
        field_name = escape_text(str(field))
        if any(k in field_name.lower() for k in ("message", "detail", "note")):
            form_fields_html.append(
                f"""
                <div class="form-group">
                    <label>{field_name}</label>
                    <textarea class="form-control" rows="3" placeholder="Tell us more about your request..."></textarea>
                </div>
                """
            )
        else:
            form_fields_html.append(
                f"""
                <div class="form-group">
                    <label>{field_name}</label>
                    <input type="text" class="form-control" placeholder="Enter {field_name.lower()}" />
                </div>
                """
            )

    return f"""
    <div class="container contact-container">
        <div class="section-header-center">
            <h2 class="section-title">{heading}</h2>
            {f'<p class="section-subtitle">{subheading}</p>' if subheading else ''}
        </div>
        
        <div class="contact-layout">
            <div class="contact-info-card">
                <h3>Contact & Hours</h3>
                <p>We are dedicated to providing an exceptional experience. Reach out directly or stop by.</p>
                <div class="contact-info-list">
                    {''.join(info_items)}
                </div>
                <div class="contact-card-badge">
                    <span>✨ Professional, certified specialists</span>
                </div>
            </div>
            
            <div class="contact-form-box">
                <form onsubmit="event.preventDefault(); alert('Thank you! Your appointment request has been submitted.'); return false;">
                    <div class="form-header">
                        <h4>Quick Appointment Request</h4>
                        <p>Fill out the details below and we will confirm shortly.</p>
                    </div>
                    {''.join(form_fields_html)}
                    <button type="submit" class="btn btn-primary btn-block" style="margin-top: 14px;">
                        📅 Book Appointment Now
                    </button>
                </form>
            </div>
        </div>
    </div>
    """


SECTION_RENDERERS = {
    "hero": render_hero_section,
    "text": render_text_section,
    "image": render_image_section,
    "features": render_features_section,
    "testimonials": render_testimonials_section,
    "pricing": render_pricing_section,
    "cta": render_cta_section,
    "contact": render_contact_section,
}


def render_section(section: Section, all_sections: List[Section], default_bg: str, default_text: str) -> str:
    """Render a single section wrapped in its styled container with stable ID and alias anchors."""
    renderer = SECTION_RENDERERS.get(section.type)
    if not renderer:
        return f"""
        <section id="{escape_text(section.id)}" class="site-section fallback-section">
            <div class="container">
                <p>Unsupported section type: {escape_text(section.type)}</p>
            </div>
        </section>
        """

    content_html = renderer(section, all_sections=all_sections)
    custom_styles = get_section_style_css(section.style, default_bg, default_text)

    alias_html = ""
    if section.type == "contact":
        alias_html = '<div id="contact" style="position:relative; top:-80px;"></div><div id="booking" style="position:relative; top:-80px;"></div>'
    elif section.type == "pricing":
        alias_html = '<div id="pricing" style="position:relative; top:-80px;"></div><div id="packages" style="position:relative; top:-80px;"></div>'
    elif section.type == "features":
        alias_html = '<div id="features" style="position:relative; top:-80px;"></div><div id="services" style="position:relative; top:-80px;"></div>'
    elif section.type == "testimonials":
        alias_html = '<div id="testimonials" style="position:relative; top:-80px;"></div><div id="reviews" style="position:relative; top:-80px;"></div>'

    return f"""
    <section id="{escape_text(section.id)}" class="site-section section-{section.type}" style="{custom_styles}">
        {alias_html}
        {content_html}
    </section>
    """


def render_top_navbar(state: WebsiteState) -> str:
    """Render modern top navigation bar with brand badge and anchor links."""
    sections = state.sections
    title = escape_text(state.title)

    nav_links = []
    seen_types = set()

    for s in sections:
        if s.type in ("features", "pricing", "testimonials", "contact", "text") and s.type not in seen_types:
            seen_types.add(s.type)
            label_map = {
                "features": "Services",
                "pricing": "Packages",
                "testimonials": "Reviews",
                "contact": "Contact",
                "text": "About Us",
            }
            label = label_map.get(s.type, s.type.capitalize())
            target_id = s.id
            onclick_js = (
                f"event.preventDefault(); var el = document.getElementById('{target_id}'); "
                "if(el) { el.scrollIntoView({behavior: 'smooth', block: 'start'}); }"
            )
            nav_links.append(f'<a href="#{target_id}" onclick="{onclick_js}" class="nav-link">{label}</a>')

    header_btn = render_action_link("#contact", "Book Appointment", css_class="btn btn-primary btn-sm", sections=sections)

    return f"""
    <header class="site-navbar">
        <div class="container navbar-container">
            <div class="brand-box">
                <span class="brand-icon">✨</span>
                <span class="brand-name">{title}</span>
            </div>
            <nav class="nav-links">
                {''.join(nav_links)}
            </nav>
            <div class="navbar-cta">
                {header_btn}
            </div>
        </div>
    </header>
    """


def render_footer(state: WebsiteState) -> str:
    """Render clean, modern footer with copyright and smooth anchors."""
    title = escape_text(state.title)
    return f"""
    <footer class="site-footer">
        <div class="container footer-content">
            <p>&copy; 2026 {title}. All rights reserved.</p>
            <div class="footer-links">
                <a href="#hero-1" onclick="event.preventDefault(); window.scrollTo({{top: 0, behavior: 'smooth'}});">Back to Top ↑</a>
            </div>
        </div>
    </footer>
    """


BASE_CSS = """
:root {
    --bg-color: #FDFBF7;
    --primary-color: #FF7043;
    --text-color: #1E293B;
    --font-family: -apple-system, BlinkMacSystemFont, 'Plus Jakarta Sans', 'Inter', system-ui, sans-serif;
    --card-bg: #ffffff;
    --border-color: rgba(226, 232, 240, 0.85);
    --shadow-soft: 0 10px 30px -5px rgba(0, 0, 0, 0.05), 0 4px 12px -2px rgba(0, 0, 0, 0.03);
    --shadow-hover: 0 20px 35px -10px rgba(0, 0, 0, 0.09);
}

html { scroll-behavior: smooth; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: var(--font-family);
    background-color: var(--bg-color);
    color: var(--text-color);
    line-height: 1.6;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
}
.container { max-width: 1140px; margin: 0 auto; padding: 0 24px; }
.site-section { position: relative; width: 100%; }

/* Navbar */
.site-navbar {
    position: sticky; top: 0; z-index: 100;
    background-color: rgba(253, 251, 247, 0.95);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border-color);
    padding: 16px 0;
}
.navbar-container { display: flex; justify-content: space-between; align-items: center; }
.brand-box { display: flex; align-items: center; gap: 8px; font-weight: 800; font-size: 1.25rem; letter-spacing: -0.02em; }
.brand-icon { font-size: 1.3rem; }
.nav-links { display: flex; gap: 28px; }
.nav-link { color: var(--text-color); text-decoration: none; font-size: 0.95rem; font-weight: 600; opacity: 0.85; transition: opacity 0.2s, color 0.2s; }
.nav-link:hover { opacity: 1; color: var(--primary-color); }

/* Typography */
.section-header-center { text-align: center; max-width: 720px; margin: 0 auto 3.5rem auto; }
.section-title { font-size: 2.4rem; font-weight: 800; line-height: 1.2; margin-bottom: 0.85rem; letter-spacing: -0.03em; }
.section-subtitle { font-size: 1.12rem; opacity: 0.82; line-height: 1.6; }

/* Buttons */
.btn {
    display: inline-flex; align-items: center; justify-content: center;
    padding: 0.75rem 1.6rem; font-size: 0.98rem; font-weight: 600; text-decoration: none;
    border-radius: 9999px; transition: all 0.2s ease; cursor: pointer; border: none; outline: none;
}
.btn-primary { background-color: var(--primary-color); color: #ffffff !important; box-shadow: 0 4px 14px rgba(255, 112, 67, 0.3); }
.btn-primary:hover { filter: brightness(0.92); transform: translateY(-2px); box-shadow: 0 6px 20px rgba(255, 112, 67, 0.4); }
.btn-secondary { background-color: rgba(255, 255, 255, 0.8); color: var(--text-color) !important; border: 1px solid var(--border-color); }
.btn-secondary:hover { background-color: #ffffff; border-color: var(--primary-color); transform: translateY(-2px); }
.btn-large { padding: 0.9rem 2.2rem; font-size: 1.05rem; }
.btn-sm { padding: 0.5rem 1.2rem; font-size: 0.88rem; }
.btn-block { width: 100%; }

/* Hero Variants */
.hero-grid { display: grid; grid-template-columns: 1.15fr 1fr; gap: 3.5rem; align-items: center; }
.pill-tag {
    display: inline-block; padding: 0.35rem 1rem; background-color: rgba(255, 112, 67, 0.12);
    color: var(--primary-color); font-size: 0.85rem; font-weight: 700; border-radius: 9999px;
    margin-bottom: 1.2rem; letter-spacing: 0.02em;
}
.hero-title { font-size: 3.6rem; font-weight: 800; line-height: 1.12; letter-spacing: -0.04em; margin-bottom: 1.4rem; }
.hero-subtitle { font-size: 1.2rem; line-height: 1.65; opacity: 0.85; margin-bottom: 2.2rem; }
.hero-actions { display: flex; gap: 1rem; align-items: center; margin-bottom: 2rem; flex-wrap: wrap; }
.hero-trust-row { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.trust-badge { font-size: 0.9rem; font-weight: 600; opacity: 0.8; }
.hero-visual-card { position: relative; border-radius: 28px; overflow: visible; box-shadow: var(--shadow-soft); }
.hero-main-img { width: 100%; height: 440px; object-fit: cover; border-radius: 28px; display: block; }
.visual-media-box { position: relative; border-radius: 28px; overflow: visible; width: 100%; }
.visual-media-img { width: 100%; height: 440px; object-fit: cover; border-radius: 28px; display: block; box-shadow: var(--shadow-soft); }
.visual-placeholder-card {
    width: 100%; min-height: 380px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.9));
    border: 2px dashed rgba(203, 213, 225, 0.9); border-radius: 28px;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 2.5rem 2rem; text-align: center; box-shadow: var(--shadow-soft);
}
.placeholder-icon { font-size: 3.2rem; margin-bottom: 0.8rem; }
.placeholder-title { font-size: 1.25rem; font-weight: 700; color: var(--text-color); margin-bottom: 0.4rem; }
.placeholder-desc { font-size: 0.95rem; opacity: 0.78; max-width: 360px; line-height: 1.5; margin-bottom: 1rem; }
.placeholder-tag {
    display: inline-block; font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; padding: 0.3rem 0.8rem; border-radius: 9999px;
    background: rgba(255, 112, 67, 0.12); color: var(--primary-color);
}
.standalone-image-box .visual-media-img { height: auto; max-height: 520px; }
.standalone-image-box .visual-placeholder-card { min-height: 280px; }
.floating-badge { position: absolute; background: #ffffff; padding: 0.75rem 1.2rem; border-radius: 16px; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1); border: 1px solid rgba(226, 232, 240, 0.8); display: flex; flex-direction: column; }
.top-badge { top: 20px; right: -15px; font-weight: 700; font-size: 0.95rem; color: #1E293B; }
.bottom-badge { bottom: -15px; left: 20px; }
.badge-label { font-size: 0.72rem; text-transform: uppercase; color: #64748B; font-weight: 700; letter-spacing: 0.05em; }
.badge-value { font-size: 0.95rem; font-weight: 700; color: #1E293B; }

/* Hero Centered Variant */
.hero-centered { text-align: center; max-width: 900px; margin: 0 auto; }
.hero-title-center { margin-left: auto; margin-right: auto; }
.hero-sub-center { max-width: 720px; margin-left: auto; margin-right: auto; }
.hero-actions-center { justify-content: center; }
.hero-trust-center { justify-content: center; margin-bottom: 3rem; }
.hero-showcase-box { border-radius: 24px; overflow: hidden; box-shadow: var(--shadow-soft); }
.hero-showcase-img { width: 100%; height: 420px; object-fit: cover; display: block; }

/* Hero Minimal Variant */
.hero-minimal { padding: 20px 0; }
.hero-minimal-row { display: grid; grid-template-columns: 1.2fr 1fr; gap: 3rem; align-items: center; }
.minimal-stats-bar { display: flex; gap: 2rem; margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border-color); }
.stat-item { display: flex; flex-direction: column; }
.stat-num { font-size: 1.8rem; font-weight: 800; color: var(--primary-color); }
.stat-lbl { font-size: 0.85rem; opacity: 0.7; font-weight: 600; }

/* Features Variants */
.features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 2rem; }
.feature-card {
    background-color: var(--card-bg); border: 1px solid var(--border-color);
    border-radius: 20px; padding: 2.2rem; box-shadow: var(--shadow-soft);
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.feature-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-hover); }
.feature-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
.feature-icon-box { width: 52px; height: 52px; border-radius: 14px; background: rgba(255, 112, 67, 0.1); display: flex; align-items: center; justify-content: center; font-size: 1.8rem; }
.feature-tag { font-size: 0.75rem; font-weight: 700; padding: 0.25rem 0.6rem; background: #F1F5F9; border-radius: 9999px; color: #475569; }
.feature-title { font-size: 1.25rem; font-weight: 700; margin-bottom: 0.6rem; letter-spacing: -0.01em; }
.feature-desc { font-size: 0.96rem; opacity: 0.82; line-height: 1.6; }

/* Features Pill Categories Variant (Ref Image 2) */
.pill-categories-row { display: flex; justify-content: center; gap: 2.5rem; flex-wrap: wrap; margin-bottom: 3.5rem; }
.pill-cat-item { display: flex; flex-direction: column; align-items: center; gap: 0.8rem; }
.pill-cat-circle {
    width: 86px; height: 86px; border-radius: 50%;
    background: #ffffff; border: 2px solid var(--border-color);
    display: flex; align-items: center; justify-content: center;
    font-size: 2.4rem; box-shadow: var(--shadow-soft); transition: transform 0.2s;
}
.pill-cat-circle:hover { transform: scale(1.06); border-color: var(--primary-color); }
.pill-cat-label { font-weight: 700; font-size: 0.95rem; }
.apart-panel { background: #ffffff; border: 1px solid var(--border-color); border-radius: 24px; padding: 2.5rem; box-shadow: var(--shadow-soft); }
.apart-panel-title { font-size: 1.4rem; font-weight: 800; margin-bottom: 1.8rem; text-align: center; }
.apart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.8rem; }
.apart-item { display: flex; gap: 1rem; align-items: flex-start; }
.apart-icon { font-size: 1.8rem; }
.apart-item h4 { font-size: 1.05rem; font-weight: 700; margin-bottom: 0.25rem; }
.apart-item p { font-size: 0.88rem; opacity: 0.75; }

/* Features List Variant */
.features-list-wrapper { display: flex; flex-direction: column; gap: 1.5rem; max-width: 860px; margin: 0 auto; }
.feature-list-row {
    display: flex; align-items: center; gap: 1.8rem; background: #ffffff;
    border: 1px solid var(--border-color); border-radius: 18px; padding: 1.8rem 2.2rem;
    box-shadow: var(--shadow-soft); transition: transform 0.2s;
}
.feature-list-row:hover { transform: translateX(4px); }
.list-step-num { font-size: 1.8rem; font-weight: 800; color: var(--primary-color); opacity: 0.4; }
.list-icon-box { font-size: 2rem; }

/* Pricing Grid */
.pricing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; align-items: stretch; }
.pricing-card {
    background-color: var(--card-bg); border: 1px solid var(--border-color);
    border-radius: 24px; padding: 2.6rem 2rem; box-shadow: var(--shadow-soft);
    display: flex; flex-direction: column; justify-content: space-between; position: relative; transition: transform 0.2s;
}
.featured-card { border: 2px solid var(--primary-color); transform: scale(1.03); box-shadow: var(--shadow-hover); }
.popular-pill {
    position: absolute; top: -14px; left: 50%; transform: translateX(-50%);
    background: var(--primary-color); color: #ffffff; font-size: 0.75rem; font-weight: 700;
    padding: 0.3rem 0.9rem; border-radius: 9999px; letter-spacing: 0.04em; text-transform: uppercase;
}
.price-pill { display: inline-block; padding: 0.4rem 1.1rem; background: rgba(255, 112, 67, 0.1); color: var(--primary-color); font-size: 1.35rem; font-weight: 800; border-radius: 9999px; margin-bottom: 1rem; }
.plan-name { font-size: 1.45rem; font-weight: 800; margin-bottom: 0.4rem; }
.plan-desc { font-size: 0.92rem; opacity: 0.78; margin-bottom: 1.2rem; }
.pricing-divider { height: 1px; background: var(--border-color); margin: 1.2rem 0; }
.plan-features { list-style: none; margin-bottom: 2rem; text-align: left; }
.plan-features li { padding: 0.45rem 0; font-size: 0.94rem; display: flex; align-items: center; }
.check-icon { color: var(--primary-color); font-weight: 800; margin-right: 0.6rem; font-size: 1.1rem; }

/* Pricing Horizontal Rows Variant */
.pricing-rows-container { display: flex; flex-direction: column; gap: 1.5rem; max-width: 920px; margin: 0 auto; }
.pricing-row-card {
    background-color: var(--card-bg); border: 1px solid var(--border-color);
    border-radius: 20px; padding: 2rem 2.5rem; box-shadow: var(--shadow-soft);
    display: flex; justify-content: space-between; align-items: center; gap: 2rem;
}
.featured-row { border: 2px solid var(--primary-color); box-shadow: var(--shadow-hover); }
.feature-chips-box { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.8rem; }
.feature-chip { font-size: 0.82rem; font-weight: 600; padding: 0.25rem 0.65rem; background: #F1F5F9; border-radius: 9999px; }
.price-pill-lg { font-size: 2rem; font-weight: 800; color: var(--primary-color); margin-bottom: 0.8rem; text-align: right; }
.row-right { display: flex; flex-direction: column; align-items: flex-end; }

/* Testimonials */
.testimonials-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 2rem; }
.testimonial-card {
    background-color: var(--card-bg); border: 1px solid var(--border-color);
    border-radius: 20px; padding: 2.2rem; box-shadow: var(--shadow-soft);
    display: flex; flex-direction: column; justify-content: space-between;
}
.star-rating { color: #F59E0B; font-size: 1.1rem; margin-bottom: 1rem; letter-spacing: 2px; }
.testimonial-quote { font-size: 1.05rem; line-height: 1.65; font-style: italic; opacity: 0.9; margin-bottom: 1.6rem; }
.testimonial-author-box { display: flex; align-items: center; gap: 0.9rem; }
.author-avatar {
    width: 48px; height: 48px; border-radius: 50%; background-color: var(--primary-color);
    color: #ffffff; display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 1.2rem;
}
.author-info { display: flex; flex-direction: column; }
.author-name { font-weight: 700; font-size: 1rem; }
.author-role { font-size: 0.82rem; opacity: 0.7; }

/* Testimonial Spotlight Variant */
.testimonial-spotlight-wrapper { display: grid; grid-template-columns: 1.4fr 1fr; gap: 2.5rem; align-items: center; }
.spotlight-main-card {
    background: var(--card-bg); border: 1px solid var(--border-color);
    border-radius: 28px; padding: 3rem; box-shadow: var(--shadow-soft);
    position: relative;
}
.spotlight-quote-mark { font-size: 5rem; font-family: serif; color: var(--primary-color); opacity: 0.2; position: absolute; top: 10px; right: 25px; line-height: 1; }
.spotlight-quote { font-size: 1.35rem; line-height: 1.6; font-style: italic; font-weight: 500; margin: 1.5rem 0 2rem 0; }
.spotlight-author-row { display: flex; align-items: center; gap: 1rem; }
.spotlight-side-cards { display: flex; flex-direction: column; gap: 1.5rem; }
.spotlight-sub-card { background: #ffffff; border: 1px solid var(--border-color); border-radius: 18px; padding: 1.8rem; box-shadow: var(--shadow-soft); }

/* CTA Card */
.cta-card {
    background: linear-gradient(135deg, rgba(255, 112, 67, 0.15) 0%, rgba(255, 171, 145, 0.25) 100%);
    border: 1px solid rgba(255, 112, 67, 0.2); border-radius: 28px; padding: 4rem 2rem; text-align: center;
}
.cta-heading { font-size: 2.8rem; font-weight: 800; letter-spacing: -0.03em; margin-bottom: 1rem; }
.cta-subheading { font-size: 1.2rem; max-width: 650px; margin: 0 auto 2.2rem auto; opacity: 0.85; }

/* Contact Section */
.contact-layout { display: grid; grid-template-columns: 1fr 1.25fr; gap: 3rem; align-items: start; }
.contact-info-card { background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 24px; padding: 2.5rem; box-shadow: var(--shadow-soft); }
.contact-info-card h3 { font-size: 1.5rem; font-weight: 800; margin-bottom: 0.8rem; }
.contact-info-card p { font-size: 0.96rem; opacity: 0.8; margin-bottom: 2rem; }
.contact-info-list { display: flex; flex-direction: column; gap: 1.4rem; margin-bottom: 2rem; }
.contact-info-row { display: flex; gap: 1rem; align-items: flex-start; }
.contact-icon { font-size: 1.4rem; }
.contact-info-row a { color: inherit; text-decoration: underline; }
.contact-card-badge { padding: 0.9rem 1.2rem; background: #F8FAFC; border-radius: 12px; font-size: 0.85rem; font-weight: 600; border: 1px solid var(--border-color); }
.contact-form-box { background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 24px; padding: 2.5rem; box-shadow: var(--shadow-soft); }
.form-header { margin-bottom: 1.8rem; }
.form-header h4 { font-size: 1.35rem; font-weight: 800; margin-bottom: 0.3rem; }
.form-header p { font-size: 0.9rem; opacity: 0.75; }
.form-group { margin-bottom: 1.3rem; }
.form-group label { display: block; font-size: 0.88rem; font-weight: 700; margin-bottom: 0.45rem; }
.form-control {
    width: 100%; padding: 0.8rem 1.1rem; border-radius: 10px; border: 1px solid var(--border-color);
    background: #FFFFFF; color: inherit; font-family: inherit; font-size: 0.95rem; transition: border-color 0.2s, box-shadow 0.2s;
}
.form-control:focus { outline: none; border-color: var(--primary-color); box-shadow: 0 0 0 3px rgba(255, 112, 67, 0.15); }

/* Footer */
.site-footer { border-top: 1px solid var(--border-color); padding: 2.5rem 0; font-size: 0.9rem; opacity: 0.75; margin-top: 4rem; }
.footer-content { display: flex; justify-content: space-between; align-items: center; }
.footer-links a { color: inherit; text-decoration: none; font-weight: 600; }
.footer-links a:hover { color: var(--primary-color); }

/* Text & Image Sections */
.text-card { background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 20px; padding: 2.5rem; box-shadow: var(--shadow-soft); }
.text-body { font-size: 1.05rem; line-height: 1.7; margin-bottom: 1.2rem; }
.responsive-image { max-width: 100%; border-radius: 24px; box-shadow: var(--shadow-soft); }
.image-caption { font-size: 0.9rem; opacity: 0.75; margin-top: 0.6rem; }

/* Responsive Adjustments */
@media (max-width: 900px) {
    .hero-grid { grid-template-columns: 1fr; gap: 2.5rem; }
    .hero-title { font-size: 2.7rem; }
    .contact-layout { grid-template-columns: 1fr; }
    .testimonial-spotlight-wrapper { grid-template-columns: 1fr; }
    .hero-minimal-row { grid-template-columns: 1fr; }
    .pricing-row-card { flex-direction: column; align-items: flex-start; }
    .row-right { align-items: flex-start; width: 100%; }
    .navbar-container { flex-direction: column; gap: 12px; }
    .nav-links { gap: 16px; }
}
"""


def render_website(state: WebsiteState) -> str:
    """
    Render complete WebsiteState into a standalone, secure HTML document.
    Embeds top navbar, theme CSS variables, safely rendered sections, and footer.
    """
    theme = state.theme
    custom_vars = f"""
    :root {{
        --bg-color: {escape_text(theme.background)};
        --primary-color: {escape_text(theme.primary_color)};
        --text-color: {escape_text(theme.text_color)};
        --font-family: {escape_text(theme.font_family)};
    }}
    """

    navbar_html = render_top_navbar(state)

    sections_html = "\n".join(
        [
            render_section(s, all_sections=state.sections, default_bg=theme.background, default_text=theme.text_color)
            for s in state.sections
        ]
    )

    footer_html = render_footer(state)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <base target="_self">
    <title>{escape_text(state.title)}</title>
    <style>
        {BASE_CSS}
        {custom_vars}
    </style>
</head>
<body>
    {navbar_html}
    <main>
        {sections_html}
    </main>
    {footer_html}
</body>
</html>
"""
    return full_html
