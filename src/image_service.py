"""
Image retrieval service for SitePilot AI.
Provides generic topic-based visual media matching and safe URL resolution
without hardcoded business-specific branching or invented URLs.
"""

import re
from typing import Optional, Dict

# Curated, verified royalty-free high-resolution Unsplash images organized by semantic visual themes.
THEMATIC_MEDIA_LIBRARY: Dict[str, str] = {
    "culinary": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&auto=format&fit=crop&q=80",
    "food_dining": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&auto=format&fit=crop&q=80",
    "active_fitness": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800&auto=format&fit=crop&q=80",
    "wellness_spa": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=800&auto=format&fit=crop&q=80",
    "animals_care": "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800&auto=format&fit=crop&q=80",
    "technology_digital": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&auto=format&fit=crop&q=80",
    "craft_artisan": "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?w=800&auto=format&fit=crop&q=80",
    "medical_health": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=800&auto=format&fit=crop&q=80",
    "workspace_business": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=800&auto=format&fit=crop&q=80",
}

THEME_KEYWORDS = {
    "culinary": ("bakery", "bread", "pastry", "coffee", "roaster", "cafe", "tea", "roasting", "barista", "dessert"),
    "food_dining": ("restaurant", "bistro", "dining", "chef", "cuisine", "gourmet", "kitchen", "dinner", "catering"),
    "active_fitness": ("fitness", "gym", "workout", "crossfit", "training", "pilates", "yoga", "athletic", "exercise"),
    "wellness_spa": ("spa", "massage", "wellness", "relaxation", "therapy", "skincare", "beauty", "salon", "facial"),
    "animals_care": ("pet", "dog", "cat", "groom", "veterinary", "puppy", "kitten", "animal", "canine", "feline"),
    "technology_digital": ("software", "saas", "tech", "app", "cloud", "ai", "data", "digital", "platform", "code"),
    "craft_artisan": ("artisan", "pottery", "handmade", "woodwork", "studio", "craft", "tailor", "jewelry", "ceramic"),
    "medical_health": ("dental", "clinic", "doctor", "health", "physio", "chiro", "medical", "care", "patient", "dentist"),
    "workspace_business": ("consult", "agency", "corporate", "law", "finance", "strategy", "office", "business", "advisory"),
}


def retrieve_image_for_description(description: Optional[str]) -> Optional[str]:
    """
    Generic semantic image retrieval based on prompt/description keywords.
    Returns a verified royalty-free high-res image URL, or None if no confident match.
    Never invents broken URLs.
    """
    if not description or not str(description).strip():
        return None

    desc_lower = str(description).lower()
    for theme, keywords in THEME_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(k)}", desc_lower) for k in keywords):
            return THEMATIC_MEDIA_LIBRARY.get(theme)

    return None
