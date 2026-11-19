"""
Color utilities for SitePilot AI.
Implements WCAG 2.1 relative luminance and contrast ratio calculations.
Dynamically resolves high-contrast, accessible foreground colors, button text,
card backgrounds, overlays, navigation bars, and form controls across all themes.
"""

import math
import re
from typing import Any, Dict, Optional, Tuple

# Common standard CSS color names mapped to hex for robust parsing
CSS_NAMED_COLORS: Dict[str, str] = {
    "black": "#000000",
    "white": "#FFFFFF",
    "slate": "#0F172A",
    "gray": "#6B7280",
    "grey": "#6B7280",
    "darkslate": "#1E293B",
    "navy": "#0A192F",
    "blue": "#2563EB",
    "indigo": "#4F46E5",
    "purple": "#7C3AED",
    "pink": "#EC4899",
    "red": "#DC2626",
    "orange": "#F97316",
    "amber": "#D97706",
    "yellow": "#F59E0B",
    "green": "#10B981",
    "emerald": "#059669",
    "teal": "#0D9488",
    "cyan": "#06B6D4",
    "cream": "#FDFBF7",
    "ivory": "#FFFDF9",
}


def parse_color_to_rgb(color_str: Optional[str]) -> Tuple[int, int, int]:
    """
    Parse a color string into an (R, G, B) tuple with 0-255 integer channels.
    Supports hex (#RGB, #RRGGBB, #RRGGBBAA), rgb(), rgba(), and standard named colors.
    Falls back gracefully to white (255, 255, 255) if parsing fails.
    """
    if not color_str or not isinstance(color_str, str):
        return (255, 255, 255)

    clean = color_str.strip().lower()

    # Named color lookup
    if clean in CSS_NAMED_COLORS:
        clean = CSS_NAMED_COLORS[clean]

    # Hex formats
    if clean.startswith("#"):
        hex_digits = clean[1:]
        if len(hex_digits) == 3:
            # #RGB -> #RRGGBB
            r = int(hex_digits[0] * 2, 16)
            g = int(hex_digits[1] * 2, 16)
            b = int(hex_digits[2] * 2, 16)
            return (r, g, b)
        elif len(hex_digits) in (6, 8):
            # #RRGGBB or #RRGGBBAA
            r = int(hex_digits[0:2], 16)
            g = int(hex_digits[2:4], 16)
            b = int(hex_digits[4:6], 16)
            return (r, g, b)

    # rgb() or rgba()
    rgb_match = re.search(r"rgba?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)", clean)
    if rgb_match:
        r = max(0, min(255, int(rgb_match.group(1))))
        g = max(0, min(255, int(rgb_match.group(2))))
        b = max(0, min(255, int(rgb_match.group(3))))
        return (r, g, b)

    return (255, 255, 255)


def get_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """
    Compute WCAG 2.1 relative luminance for an sRGB tuple (0-255).
    Formula: L = 0.2126 * R_lin + 0.7152 * G_lin + 0.0722 * B_lin
    where channel_lin = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    Returns float in range [0.0, 1.0].
    """
    channels = []
    for c in rgb:
        s = c / 255.0
        if s <= 0.04045:
            linear = s / 12.92
        else:
            linear = math.pow((s + 0.055) / 1.055, 2.4)
        channels.append(linear)

    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def get_contrast_ratio(color_a: str, color_b: str) -> float:
    """
    Calculate WCAG 2.1 contrast ratio between two colors:
    CR = (L1 + 0.05) / (L2 + 0.05) where L1 is the lighter luminance.
    Returns float in range [1.0, 21.0].
    """
    rgb_a = parse_color_to_rgb(color_a)
    rgb_b = parse_color_to_rgb(color_b)

    l_a = get_relative_luminance(rgb_a)
    l_b = get_relative_luminance(rgb_b)

    lighter = max(l_a, l_b)
    darker = min(l_a, l_b)

    return (lighter + 0.05) / (darker + 0.05)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert an (R, G, B) integer tuple into a normalized #RRGGBB hex string."""
    r = max(0, min(255, int(round(rgb[0]))))
    g = max(0, min(255, int(round(rgb[1]))))
    b = max(0, min(255, int(round(rgb[2]))))
    return f"#{r:02X}{g:02X}{b:02X}"


def adjust_color_brightness(color_str: str, factor: float) -> str:
    """
    Adjust the brightness of a color by factor.
    factor > 1.0 brightens; factor < 1.0 darkens.
    Interpolates toward white (#FFFFFF) when brightening to handle near-black colors gracefully.
    Returns normalized #RRGGBB hex string.
    """
    r, g, b = parse_color_to_rgb(color_str)
    if factor >= 1.0:
        t = min(1.0, factor - 1.0)
        new_r = int(round(r + (255 - r) * t))
        new_g = int(round(g + (255 - g) * t))
        new_b = int(round(b + (255 - b) * t))
    else:
        new_r = int(round(r * factor))
        new_g = int(round(g * factor))
        new_b = int(round(b * factor))
    return rgb_to_hex((new_r, new_g, new_b))


def is_readable_contrast(bg_color: str, fg_color: str, min_ratio: float = 4.5) -> bool:
    """
    Check if foreground text against background meets or exceeds WCAG contrast ratio.
    Default threshold is 4.5:1 (WCAG AA for normal text; 3:1 for large text).
    """
    return get_contrast_ratio(bg_color, fg_color) >= min_ratio


def get_readable_foreground(
    bg_color: str,
    preferred_color: Optional[str] = None,
    min_ratio: float = 4.5,
) -> str:
    """
    Select or calculate a high-contrast foreground color against bg_color.
    1. Tests preferred_color: if it already achieves min_ratio, returns it.
    2. Otherwise, evaluates standard accessible candidates (#FFFFFF, #0F172A, #F8FAFC, #1E293B, #000000).
    3. Selects the candidate that exceeds min_ratio with the highest contrast margin.
    Guarantees text is never invisible or low-contrast.
    """
    if preferred_color and is_readable_contrast(bg_color, preferred_color, min_ratio=min_ratio):
        return preferred_color

    bg_rgb = parse_color_to_rgb(bg_color)
    bg_lum = get_relative_luminance(bg_rgb)

    # Candidate palette: dark tones and light tones
    dark_candidates = ["#0F172A", "#1E293B", "#000000", "#111827"]
    light_candidates = ["#FFFFFF", "#F8FAFC", "#F1F5F9", "#FFFFFF"]

    candidates = dark_candidates if bg_lum > 0.25 else light_candidates

    best_color = candidates[0]
    best_ratio = get_contrast_ratio(bg_color, best_color)

    for c in candidates:
        r = get_contrast_ratio(bg_color, c)
        if r > best_ratio:
            best_ratio = r
            best_color = c

    # If the chosen direction still doesn't satisfy min_ratio (rare edge cases), check the other direction
    if best_ratio < min_ratio:
        alternative = light_candidates[0] if candidates is dark_candidates else dark_candidates[0]
        alt_ratio = get_contrast_ratio(bg_color, alternative)
        if alt_ratio > best_ratio:
            best_color = alternative

    return best_color


def resolve_theme_colors(
    background: str,
    primary_color: str,
    text_color: Optional[str] = None,
    background_style: Optional[str] = "solid",
    **kwargs: Any,
) -> Dict[str, str]:
    """
    Compute complete, WCAG-compliant design tokens and CSS variables for a website theme.
    Ensures that body text, buttons, cards, navigation, overlays, and form controls
    maintain readable contrast regardless of what colors the LLM generated or user edited.
    """
    bg_rgb = parse_color_to_rgb(background)
    bg_lum = get_relative_luminance(bg_rgb)
    is_dark_theme = bg_lum < 0.25

    # 1. Body and Heading text
    body_text = get_readable_foreground(background, preferred_color=text_color, min_ratio=4.5)
    heading_text = get_readable_foreground(background, preferred_color=text_color, min_ratio=4.5)

    # 2. Primary Button text contrast (calculated against primary_color)
    btn_primary_text = get_readable_foreground(primary_color, preferred_color="#ffffff", min_ratio=4.5)
    pri_rgb = parse_color_to_rgb(primary_color)
    p_r, p_g, p_b = pri_rgb

    # Primary Button interactive states
    btn_pri_hover_bg = adjust_color_brightness(primary_color, 1.12 if is_dark_theme else 0.88)
    btn_pri_hover_text = get_readable_foreground(btn_pri_hover_bg, preferred_color=btn_primary_text, min_ratio=4.5)
    btn_pri_active_bg = adjust_color_brightness(primary_color, 1.22 if is_dark_theme else 0.78)
    btn_pri_active_text = get_readable_foreground(btn_pri_active_bg, preferred_color=btn_primary_text, min_ratio=4.5)
    btn_pri_focus_ring = f"rgba({p_r}, {p_g}, {p_b}, 0.45)"

    # 3. Surface & Interactive Tokens (Theme-dependent)
    if is_dark_theme:
        # Elevated surface on dark background
        card_bg = "#1E293B"
        card_border = "rgba(255, 255, 255, 0.12)"
        card_text = get_readable_foreground(card_bg, preferred_color="#F8FAFC", min_ratio=4.5)
        card_hover_bg = "#283548"
        card_hover_text = get_readable_foreground(card_hover_bg, preferred_color="#F8FAFC", min_ratio=4.5)

        nav_bg = "rgba(15, 23, 42, 0.92)"
        nav_border = "rgba(255, 255, 255, 0.1)"
        nav_text = get_readable_foreground("#0F172A", preferred_color="#F8FAFC", min_ratio=4.5)
        nav_link_color = get_readable_foreground("#0F172A", preferred_color="#F8FAFC", min_ratio=4.5)
        nav_link_hover_bg = "rgba(255, 255, 255, 0.08)"
        # Nav hover color: verify primary has >= 4.5 contrast on dark nav, otherwise pick accessible tone
        nav_link_hover_color = (
            primary_color
            if is_readable_contrast("#0F172A", primary_color, min_ratio=4.5)
            else get_readable_foreground("#0F172A", preferred_color="#60A5FA", min_ratio=4.5)
        )

        input_bg = "#0F172A"
        input_text = get_readable_foreground(input_bg, preferred_color="#F8FAFC", min_ratio=4.5)
        input_border = "rgba(255, 255, 255, 0.2)"
        input_hover_border = primary_color if is_readable_contrast(input_bg, primary_color, min_ratio=3.0) else "#94A3B8"
        input_focus_bg = input_bg
        input_focus_text = input_text
        input_focus_border = primary_color
        input_focus_ring = f"rgba({p_r}, {p_g}, {p_b}, 0.35)"
        input_placeholder = "#94A3B8"

        overlay_bg = "rgba(10, 15, 29, 0.82)"
        muted_text = "rgba(241, 245, 249, 0.72)"

        btn_sec_bg = "rgba(30, 41, 59, 0.85)"
        btn_sec_text = get_readable_foreground("#1E293B", preferred_color="#F8FAFC", min_ratio=4.5)
        btn_sec_hover_bg = "#334155"
        btn_sec_hover_text = get_readable_foreground(btn_sec_hover_bg, preferred_color="#F8FAFC", min_ratio=4.5)
        btn_sec_active_bg = "#475569"
        btn_sec_active_text = get_readable_foreground(btn_sec_active_bg, preferred_color="#F8FAFC", min_ratio=4.5)

        btn_dis_bg = "#334155"
        btn_dis_text = get_readable_foreground(btn_dis_bg, preferred_color="#94A3B8", min_ratio=4.5)
    else:
        # Elevated surface on light background
        card_bg = "#FFFFFF"
        card_border = "rgba(226, 232, 240, 0.85)"
        card_text = get_readable_foreground(card_bg, preferred_color="#1E293B", min_ratio=4.5)
        card_hover_bg = "#F8FAFC"
        card_hover_text = get_readable_foreground(card_hover_bg, preferred_color="#1E293B", min_ratio=4.5)

        nav_bg = "rgba(255, 255, 255, 0.94)"
        nav_border = "rgba(226, 232, 240, 0.85)"
        nav_text = get_readable_foreground("#FFFFFF", preferred_color="#1E293B", min_ratio=4.5)
        nav_link_color = get_readable_foreground("#FFFFFF", preferred_color="#1E293B", min_ratio=4.5)
        nav_link_hover_bg = "rgba(0, 0, 0, 0.05)"
        # Nav hover color: verify primary has >= 4.5 contrast on light nav, otherwise pick accessible tone
        nav_link_hover_color = (
            primary_color
            if is_readable_contrast("#FFFFFF", primary_color, min_ratio=4.5)
            else get_readable_foreground("#FFFFFF", preferred_color="#1D4ED8", min_ratio=4.5)
        )

        input_bg = "#FFFFFF"
        input_text = get_readable_foreground(input_bg, preferred_color="#1E293B", min_ratio=4.5)
        input_border = "rgba(203, 213, 225, 0.9)"
        input_hover_border = primary_color if is_readable_contrast(input_bg, primary_color, min_ratio=3.0) else "#64748B"
        input_focus_bg = input_bg
        input_focus_text = input_text
        input_focus_border = primary_color
        input_focus_ring = f"rgba({p_r}, {p_g}, {p_b}, 0.25)"
        input_placeholder = "#64748B"

        overlay_bg = "rgba(15, 23, 42, 0.65)"
        muted_text = "rgba(30, 41, 59, 0.75)"

        btn_sec_bg = "rgba(255, 255, 255, 0.9)"
        btn_sec_text = get_readable_foreground("#FFFFFF", preferred_color="#1E293B", min_ratio=4.5)
        btn_sec_hover_bg = "#F1F5F9"
        btn_sec_hover_text = get_readable_foreground(btn_sec_hover_bg, preferred_color="#1E293B", min_ratio=4.5)
        btn_sec_active_bg = "#E2E8F0"
        btn_sec_active_text = get_readable_foreground(btn_sec_active_bg, preferred_color="#1E293B", min_ratio=4.5)

        btn_dis_bg = "#E2E8F0"
        btn_dis_text = get_readable_foreground(btn_dis_bg, preferred_color="#64748B", min_ratio=4.5)

    return {
        "bg_color": background,
        "text_color": body_text,
        "heading_color": heading_text,
        "primary_color": primary_color,
        "btn_primary_bg": primary_color,
        "btn_primary_text": btn_primary_text,
        "btn_primary_hover_bg": btn_pri_hover_bg,
        "btn_primary_hover_text": btn_pri_hover_text,
        "btn_primary_active_bg": btn_pri_active_bg,
        "btn_primary_active_text": btn_pri_active_text,
        "btn_primary_focus_ring": btn_pri_focus_ring,
        "btn_secondary_bg": btn_sec_bg,
        "btn_secondary_text": btn_sec_text,
        "btn_secondary_hover_bg": btn_sec_hover_bg,
        "btn_secondary_hover_text": btn_sec_hover_text,
        "btn_secondary_active_bg": btn_sec_active_bg,
        "btn_secondary_active_text": btn_sec_active_text,
        "btn_disabled_bg": btn_dis_bg,
        "btn_disabled_text": btn_dis_text,
        "card_bg": card_bg,
        "card_text": card_text,
        "card_hover_bg": card_hover_bg,
        "card_hover_text": card_hover_text,
        "card_border": card_border,
        "nav_bg": nav_bg,
        "nav_text": nav_text,
        "nav_border": nav_border,
        "nav_link_color": nav_link_color,
        "nav_link_hover_color": nav_link_hover_color,
        "nav_link_hover_bg": nav_link_hover_bg,
        "input_bg": input_bg,
        "input_text": input_text,
        "input_border": input_border,
        "input_hover_border": input_hover_border,
        "input_focus_bg": input_focus_bg,
        "input_focus_text": input_focus_text,
        "input_focus_border": input_focus_border,
        "input_focus_ring": input_focus_ring,
        "input_placeholder_color": input_placeholder,
        "overlay_bg": overlay_bg,
        "muted_text": muted_text,
    }
