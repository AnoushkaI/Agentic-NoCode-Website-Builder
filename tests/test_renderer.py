"""
Unit tests for Phase 3: Predefined HTML/CSS Renderer, Link Sanitization, and Navigation Safety.
"""

import pytest
from src.schema import WebsiteState, Section, SectionStyle, ThemeConfig
from src.renderer import (
    render_website,
    render_section,
    sanitize_url,
    escape_text,
    get_section_style_css,
    resolve_target_section_id,
    render_action_link,
    render_hero_section,
    render_text_section,
    render_image_section,
    render_features_section,
    render_testimonials_section,
    render_pricing_section,
    render_cta_section,
    render_contact_section,
)
from src.generator import create_fitness_fallback_website, create_pet_grooming_fallback_website


# -----------------------------------------------------------------------------
# 1. URL Sanitization, Anchors, and Navigation Safety Tests
# -----------------------------------------------------------------------------

def test_escape_text_prevents_xss():
    """Verify script tags and html characters are properly escaped."""
    malicious = '<script>alert("XSS")</script>'
    escaped = escape_text(malicious)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    assert "alert" in escaped


def test_sanitize_url_blocks_javascript_schemes():
    """Verify malicious URL protocols (javascript, data, vbscript) are blocked."""
    assert sanitize_url("javascript:alert(1)") == "#"
    assert sanitize_url("JAVASCRIPT:void(0)") == "#"
    assert sanitize_url("data:text/html,<script>alert(1)</script>") == "#"
    assert sanitize_url("vbscript:msgbox") == "#"

    # Valid URLs preserved
    assert sanitize_url("https://example.com") == "https://example.com"
    assert sanitize_url("#pricing-1") == "#pricing-1"
    assert sanitize_url("mailto:test@example.com") == "mailto:test@example.com"
    assert sanitize_url("tel:1234567890") == "tel:1234567890"


def test_resolve_target_section_id():
    """Verify intent resolution maps navigation anchors to valid section IDs."""
    sections = [
        Section(id="hero-1", type="hero", content={"title": "Hero"}),
        Section(id="features-1", type="features", content={"heading": "Services"}),
        Section(id="pricing-1", type="pricing", content={"heading": "Packages"}),
        Section(id="testimonials-1", type="testimonials", content={"heading": "Reviews"}),
        Section(id="contact-1", type="contact", content={"heading": "Contact"}),
    ]

    # Exact matches
    assert resolve_target_section_id("pricing-1", sections) == "pricing-1"
    assert resolve_target_section_id("#pricing-1", sections) == "pricing-1"

    # Intent mappings
    assert resolve_target_section_id("#contact", sections) == "contact-1"
    assert resolve_target_section_id("booking", sections) == "contact-1"
    assert resolve_target_section_id("#appointment", sections) == "contact-1"
    assert resolve_target_section_id("#pricing", sections) == "pricing-1"
    assert resolve_target_section_id("#packages", sections) == "pricing-1"
    assert resolve_target_section_id("#services", sections) == "features-1"
    assert resolve_target_section_id("#reviews", sections) == "testimonials-1"
    assert resolve_target_section_id(None, sections) == "contact-1"


def test_render_action_link_internal_anchor_prevents_iframe_navigation():
    """
    Verify internal links include event.preventDefault() and scrollIntoView
    to strictly prevent iframe navigation to the Streamlit app.
    """
    sections = [
        Section(id="contact-1", type="contact", content={"heading": "Contact"}),
    ]
    html_link = render_action_link("#contact", "Book Appointment Now", sections=sections)

    assert 'href="#contact-1"' in html_link
    assert "event.preventDefault()" in html_link
    assert "scrollIntoView" in html_link
    assert "target=" not in html_link  # Internal links stay in iframe


def test_render_action_link_external_opens_new_tab():
    """Verify external URLs open safely in a new tab with noopener."""
    html_link = render_action_link("https://google.com", "External Site")

    assert 'href="https://google.com"' in html_link
    assert 'target="_blank"' in html_link
    assert 'rel="noopener noreferrer"' in html_link
    assert "scrollIntoView" not in html_link


# -----------------------------------------------------------------------------
# 2. Individual Section Renderer Tests
# -----------------------------------------------------------------------------

def test_render_hero_section():
    """Verify rich hero section renders title, subtitle, CTAs, trust points and visual card."""
    sec = Section(
        id="hero-1",
        type="hero",
        content={
            "title": "Welcome to Peak Fitness",
            "subtitle": "Crush your health goals with us.",
            "cta_text": "Book a Trial",
            "cta_link": "#contact-1",
            "image_url": "https://images.unsplash.com/sample.jpg",
        },
    )
    html_out = render_hero_section(sec)
    assert "Welcome to Peak Fitness" in html_out
    assert "Crush your health goals with us." in html_out
    assert "Book a Trial" in html_out
    assert 'href="#hero-1"' in html_out or 'href="#contact-1"' in html_out
    assert 'src="https://images.unsplash.com/sample.jpg"' in html_out
    assert "hero-visual-card" in html_out


def test_render_text_section():
    """Verify text section renders heading and paragraphs."""
    sec = Section(
        id="text-1",
        type="text",
        content={
            "heading": "Our Philosophy",
            "body": "First paragraph of story.\n\nSecond paragraph of story.",
        },
    )
    html_out = render_text_section(sec)
    assert "Our Philosophy" in html_out
    assert "First paragraph of story." in html_out
    assert "Second paragraph of story." in html_out


def test_render_image_section():
    """Verify image section renders image tag and caption."""
    sec = Section(
        id="image-1",
        type="image",
        content={
            "url": "https://images.unsplash.com/gym.jpg",
            "alt": "Modern Gym Floor",
            "caption": "Our state-of-the-art facility",
        },
    )
    html_out = render_image_section(sec)
    assert 'src="https://images.unsplash.com/gym.jpg"' in html_out
    assert 'alt="Modern Gym Floor"' in html_out
    assert "Our state-of-the-art facility" in html_out


def test_render_features_section():
    """Verify features section renders card grid."""
    sec = Section(
        id="features-1",
        type="features",
        content={
            "heading": "Key Benefits",
            "items": [
                {"title": "Cardio Area", "description": "Rowers and treadmills", "icon": "🏃"},
                {"title": "Free Weights", "description": "Dumbbells up to 120lbs", "icon": "🏋️"},
            ],
        },
    )
    html_out = render_features_section(sec)
    assert "Key Benefits" in html_out
    assert "Cardio Area" in html_out
    assert "Rowers and treadmills" in html_out
    assert "Free Weights" in html_out


def test_render_testimonials_section():
    """Verify testimonials section renders quotes, star rating, and author info."""
    sec = Section(
        id="testimonials-1",
        type="testimonials",
        content={
            "heading": "Member Reviews",
            "items": [
                {"quote": "Best workout in town!", "author": "Alice Smith", "role": "Member"},
            ],
        },
    )
    html_out = render_testimonials_section(sec)
    assert "Member Reviews" in html_out
    assert "Best workout in town!" in html_out
    assert "Alice Smith" in html_out
    assert "Member" in html_out
    assert "★★★★★" in html_out


def test_render_pricing_section():
    """Verify pricing section renders plan cards with price pills and features."""
    sec = Section(
        id="pricing-1",
        type="pricing",
        content={
            "heading": "Memberships",
            "plans": [
                {
                    "name": "Standard Plan",
                    "price": "$50/mo",
                    "cta_text": "Join Standard",
                    "features": ["Gym Access", "Locker Access"],
                }
            ],
        },
    )
    html_out = render_pricing_section(sec)
    assert "Memberships" in html_out
    assert "Standard Plan" in html_out
    assert "$50/mo" in html_out
    assert "Gym Access" in html_out
    assert "Join Standard" in html_out
    assert "pricing-card" in html_out


def test_render_cta_section():
    """Verify CTA banner section renders."""
    sec = Section(
        id="cta-1",
        type="cta",
        content={
            "heading": "Start Today",
            "subheading": "Get your first week free",
            "button_text": "Claim Free Week",
            "button_link": "#contact-1",
        },
    )
    html_out = render_cta_section(sec)
    assert "Start Today" in html_out
    assert "Get your first week free" in html_out
    assert "Claim Free Week" in html_out


def test_render_contact_section():
    """Verify contact section renders email, phone and interactive form."""
    sec = Section(
        id="contact-1",
        type="contact",
        content={
            "heading": "Contact Us",
            "subheading": "Drop by our studio",
            "email": "info@studio.com",
            "phone": "555-0199",
            "fields": ["Name", "Email", "Your Message"],
        },
    )
    html_out = render_contact_section(sec)
    assert "Contact Us" in html_out
    assert "mailto:info@studio.com" in html_out
    assert "tel:555-0199" in html_out
    assert "Name" in html_out
    assert "Your Message" in html_out
    assert "Book Appointment Now" in html_out


# -----------------------------------------------------------------------------
# 3. Missing Content and Edge Case Tests
# -----------------------------------------------------------------------------

def test_missing_optional_content_renders_safely():
    """Verify sections render without crashing when optional content fields are omitted."""
    sec_hero = Section(id="hero-min", type="hero", content={"title": "Bare Hero"})
    html_hero = render_hero_section(sec_hero)
    assert "Bare Hero" in html_hero

    sec_feat = Section(id="feat-empty", type="features", content={"heading": "Features", "items": []})
    html_feat = render_features_section(sec_feat)
    assert "Features" in html_feat

    sec_price = Section(id="price-empty", type="pricing", content={"heading": "Pricing", "plans": []})
    html_price = render_pricing_section(sec_price)
    assert "Pricing" in html_price


def test_unsupported_section_fallback():
    """Verify unexpected section type returns safe fallback rather than crashing."""
    sec = Section(
        id="custom-1",
        type="text",
        content={"heading": "Test"},
    )
    sec.type = "unsupported_unknown"
    out = render_section(sec, all_sections=[sec], default_bg="#fff", default_text="#000")
    assert 'id="custom-1"' in out
    assert "Unsupported section type: unsupported_unknown" in out


# -----------------------------------------------------------------------------
# 4. Full Website State Rendering Tests
# -----------------------------------------------------------------------------

def test_render_full_website():
    """Verify complete HTML document contains doctype, meta, theme CSS, top navbar and all sections."""
    state = WebsiteState(
        title="Modern Yoga Studio",
        version=1,
        theme=ThemeConfig(
            background="#111827",
            primary_color="#3b82f6",
            text_color="#f9fafb",
            font_family="Roboto, sans-serif",
        ),
        sections=[
            Section(
                id="hero-1",
                type="hero",
                content={"title": "Yoga Practice", "cta_text": "Join Class"},
                style=SectionStyle(padding="large", variant="dark"),
            ),
            Section(
                id="contact-1",
                type="contact",
                content={"heading": "Contact Us", "email": "yoga@studio.com"},
            ),
        ],
    )

    full_html = render_website(state)

    assert "<!DOCTYPE html>" in full_html
    assert "<title>Modern Yoga Studio</title>" in full_html
    assert '<base target="_self">' in full_html
    assert "--bg-color: #111827;" in full_html
    assert "--primary-color: #3b82f6;" in full_html
    assert 'id="hero-1"' in full_html
    assert 'id="contact-1"' in full_html
    assert "Yoga Practice" in full_html
    assert "yoga@studio.com" in full_html
    assert "site-navbar" in full_html


def test_render_pet_grooming_fallback_website():
    """Verify benchmark Pet Grooming website renders with complete professional sections."""
    pet_site = create_pet_grooming_fallback_website()
    rendered = render_website(pet_site)

    assert "<!DOCTYPE html>" in rendered
    assert "Pawfect Grooming" in rendered
    assert 'id="hero-1"' in rendered
    assert 'id="features-1"' in rendered
    assert 'id="pricing-1"' in rendered
    assert 'id="testimonials-1"' in rendered
    assert 'id="contact-1"' in rendered
    assert "Fresh cuts, clean coats, and happy tails." in rendered
    assert "Book a Groom" in rendered
    assert "event.preventDefault()" in rendered


def test_render_fitness_fallback_website():
    """Verify reference fitness studio website renders completely."""
    fitness_site = create_fitness_fallback_website()
    rendered = render_website(fitness_site)

    assert "<!DOCTYPE html>" in rendered
    assert "PulseFit Studio" in rendered
    assert 'id="hero-1"' in rendered
    assert 'id="features-1"' in rendered
    assert 'id="pricing-1"' in rendered
    assert 'id="testimonials-1"' in rendered
    assert 'id="contact-1"' in rendered
    assert "Claim Free Trial" in rendered


# -----------------------------------------------------------------------------
# 5. Hybrid Layout Variant Rendering Tests
# -----------------------------------------------------------------------------

def test_hero_layout_variants():
    """Verify hero section renders differently based on layout_variant."""
    content = {
        "title": "Variant Hero",
        "subtitle": "Test subtitle description",
        "cta_text": "Action",
    }

    # 1. Split variant
    sec_split = Section(
        id="hero-1",
        type="hero",
        content=content,
        style=SectionStyle(layout_variant="split"),
    )
    html_split = render_hero_section(sec_split)
    assert "hero-grid" in html_split
    assert "hero-visual-card" in html_split

    # 2. Centered variant
    sec_center = Section(
        id="hero-1",
        type="hero",
        content=content,
        style=SectionStyle(layout_variant="centered"),
    )
    html_center = render_hero_section(sec_center)
    assert "hero-centered" in html_center
    assert "hero-showcase-box" in html_center
    assert "hero-grid" not in html_center

    # 3. Minimal variant
    sec_minimal = Section(
        id="hero-1",
        type="hero",
        content=content,
        style=SectionStyle(layout_variant="minimal"),
    )
    html_minimal = render_hero_section(sec_minimal)
    assert "hero-minimal" in html_minimal
    assert "minimal-stats-bar" in html_minimal


def test_features_layout_variants():
    """Verify features section renders differently based on layout_variant."""
    content = {
        "heading": "Features Variant",
        "items": [
            {"title": "Bath", "description": "Soothing bath", "icon": "🛁"},
            {"title": "Styling", "description": "Custom haircut", "icon": "✂️"},
        ],
    }

    # 1. Grid variant
    sec_grid = Section(
        id="features-1",
        type="features",
        content=content,
        style=SectionStyle(layout_variant="grid"),
    )
    html_grid = render_features_section(sec_grid)
    assert "features-grid" in html_grid
    assert "feature-card" in html_grid

    # 2. Pill cards variant (Ref Image 2)
    sec_pills = Section(
        id="features-1",
        type="features",
        content=content,
        style=SectionStyle(layout_variant="pill_cards"),
    )
    html_pills = render_features_section(sec_pills)
    assert "pill-categories-row" in html_pills
    assert "pill-cat-circle" in html_pills
    assert "apart-panel" in html_pills

    # 3. List variant
    sec_list = Section(
        id="features-1",
        type="features",
        content=content,
        style=SectionStyle(layout_variant="list"),
    )
    html_list = render_features_section(sec_list)
    assert "features-list-wrapper" in html_list
    assert "feature-list-row" in html_list


def test_pricing_layout_variants():
    """Verify pricing section renders vertical cards vs horizontal rows."""
    content = {
        "heading": "Pricing Variant",
        "plans": [
            {"name": "Standard", "price": "$50", "features": ["Feature A"]},
        ],
    }

    # 1. Cards variant
    sec_cards = Section(
        id="pricing-1",
        type="pricing",
        content=content,
        style=SectionStyle(layout_variant="cards"),
    )
    html_cards = render_pricing_section(sec_cards)
    assert "pricing-grid" in html_cards
    assert "pricing-card" in html_cards

    # 2. Table / Rows variant
    sec_table = Section(
        id="pricing-1",
        type="pricing",
        content=content,
        style=SectionStyle(layout_variant="table"),
    )
    html_table = render_pricing_section(sec_table)
    assert "pricing-rows-container" in html_table
    assert "pricing-row-card" in html_table


def test_testimonials_layout_variants():
    """Verify testimonials section renders grid vs spotlight banner."""
    content = {
        "heading": "Reviews Variant",
        "items": [
            {"quote": "Great service!", "author": "John Doe", "role": "Client"},
            {"quote": "Very satisfied!", "author": "Jane Smith", "role": "Member"},
        ],
    }

    # 1. Grid variant
    sec_grid = Section(
        id="testimonials-1",
        type="testimonials",
        content=content,
        style=SectionStyle(layout_variant="grid"),
    )
    html_grid = render_testimonials_section(sec_grid)
    assert "testimonials-grid" in html_grid
    assert "testimonial-card" in html_grid

    # 2. Spotlight variant
    sec_spotlight = Section(
        id="testimonials-1",
        type="testimonials",
        content=content,
        style=SectionStyle(layout_variant="spotlight"),
    )
    html_spotlight = render_testimonials_section(sec_spotlight)
    assert "testimonial-spotlight-wrapper" in html_spotlight
    assert "spotlight-main-card" in html_spotlight
    assert "spotlight-quote" in html_spotlight


def test_business_diversity_structure():
    """
    Verify that pet grooming and fitness studio websites produce
    noticeably distinct layout structures and components using the same library.
    """
    pet_site = create_pet_grooming_fallback_website()
    fitness_site = create_fitness_fallback_website()

    html_pet = render_website(pet_site)
    html_fitness = render_website(fitness_site)

    # Pet site has split hero and circular pill category layout
    assert "hero-grid" in html_pet
    assert "pill-categories-row" in html_pet
    assert "pricing-grid" in html_pet

    # Fitness site has centered hero, package table rows, and spotlight testimonial
    assert "hero-centered" in html_fitness
    assert "pricing-rows-container" in html_fitness
    assert "testimonial-spotlight-wrapper" in html_fitness


# -----------------------------------------------------------------------------
# 6. Generalized Visual Media & Placeholder Tests
# -----------------------------------------------------------------------------

def test_render_image_section_missing_url_renders_visual_placeholder():
    """Verify that when no image URL is provided, an attractive visual placeholder is rendered."""
    sec = Section(
        id="image-1",
        type="image",
        content={
            "image_description": "Handcrafted ceramic mug on potter's wheel",
            "alt": "Ceramic Pottery Showcase",
            "caption": "Handmade in small batches",
        },
    )
    html_out = render_image_section(sec)
    assert "visual-placeholder-card" in html_out
    assert "Ceramic Pottery Showcase" in html_out
    assert "Handcrafted ceramic mug" in html_out
    assert "Handmade in small batches" in html_out
    # Must NOT render broken empty src
    assert 'src=""' not in html_out
    assert "src=\"#\"" not in html_out


def test_render_hero_with_missing_image_renders_placeholder():
    """Verify hero section displays visual placeholder when no image URL exists."""
    sec = Section(
        id="hero-1",
        type="hero",
        content={
            "title": "Quantum Mechanics Lab",
            "subtitle": "Advanced particle physics research.",
            "cta_text": "Read Papers",
            "image_description": "Superconducting particle detector apparatus",
        },
    )
    html_out = render_hero_section(sec)
    assert "visual-placeholder-card" in html_out
    assert "Quantum Mechanics Lab" in html_out
    assert "Superconducting particle detector apparatus" in html_out


def test_render_visual_media_onerror_and_safe_attributes():
    """Verify that when a valid URL is provided, img includes lazy loading and onerror fallback."""
    from src.renderer import render_visual_media

    html_out = render_visual_media(
        image_url="https://images.unsplash.com/photo-test.jpg",
        image_description="Modern Workspace",
        alt="Creative Studio",
        overlay_badge="4.9★",
        card_highlight="Flagship Service",
    )
    assert '<img src="https://images.unsplash.com/photo-test.jpg"' in html_out
    assert 'alt="Creative Studio"' in html_out
    assert 'loading="lazy"' in html_out
    assert "onerror=" in html_out
    assert "4.9★" in html_out
    assert "Flagship Service" in html_out


def test_render_hero_editorial_and_storefront_variants():
    """Verify editorial showcase and storefront hero variants render correctly."""
    # Editorial showcase
    sec_editorial = Section(
        id="hero-1",
        type="hero",
        content={
            "title": "Bespoke Residences",
            "subtitle": "Masterfully tailored interiors.",
            "quote": "Design is the silent ambassador of your brand.",
            "quote_author": "Principal Architect",
            "pill_badge": "Private Commission",
        },
        style=SectionStyle(layout_variant="editorial_showcase"),
    )
    html_editorial = render_hero_section(sec_editorial)
    assert "hero-editorial-showcase" in html_editorial
    assert "editorial-main-title" in html_editorial
    assert "Design is the silent ambassador" in html_editorial
    assert "Principal Architect" in html_editorial

    # Storefront
    sec_storefront = Section(
        id="hero-1",
        type="hero",
        content={
            "title": "Fresh Daily Hearth Bakes",
            "subtitle": "Naturally fermented organic sourdough.",
            "pill_badge": "Oven Warm at 6:30 AM",
        },
        style=SectionStyle(layout_variant="storefront"),
    )
    html_storefront = render_hero_section(sec_storefront)
    assert "hero-storefront-wrapper" in html_storefront
    assert "storefront-strip" in html_storefront
    assert "Fresh Daily Hearth Bakes" in html_storefront


def test_render_image_section_gallery_layout():
    """Verify image section gallery layout renders grid of images safely."""
    sec_gallery = Section(
        id="image-1",
        type="image",
        content={
            "images": [
                {"url": "https://images.unsplash.com/photo-1.jpg", "caption": "Living Lounge"},
                {"url": "https://images.unsplash.com/photo-2.jpg", "caption": "Stone Kitchen"},
            ],
            "alt": "Architectural Portfolio",
        },
        style=SectionStyle(layout_variant="gallery"),
    )
    html_gallery = render_image_section(sec_gallery)
    assert "gallery-grid-row" in html_gallery
    assert "https://images.unsplash.com/photo-1.jpg" in html_gallery
    assert "https://images.unsplash.com/photo-2.jpg" in html_gallery


def test_render_navigation_variants_and_form_pulse_highlight():
    """Verify navbar styling variations and form pulse highlight support."""
    state_pill = WebsiteState(
        title="Boutique Cafe",
        version=1,
        theme=ThemeConfig(
            background="#FFFFFF",
            primary_color="#D97706",
            text_color="#1F2937",
            nav_style="floating_pill",
            heading_font="Playfair Display, serif",
        ),
        sections=[
            Section(id="hero-1", type="hero", content={"title": "Cafe", "brand_icon": "☕"}),
            Section(
                id="contact-1",
                type="contact",
                content={
                    "heading": "Reserve Table",
                    "form_type": "booking",
                    "fields": ["Guest Name", "Party Size", "Reservation Time"],
                },
            ),
        ],
    )
    html_pill = render_website(state_pill)
    assert "navbar-floating_pill" in html_pill
    assert "☕" in html_pill
    assert "Playfair Display" in html_pill
    assert "id=\"appointment-form\"" in html_pill
    assert "formPulseHighlight" in html_pill
    assert "target.scrollIntoView" in html_pill



