"""
Image retrieval service for SitePilot AI.
Provides generic topic-based visual media matching and safe URL resolution
supporting separate hero, background, gallery, and product slots without invented URLs.
"""

import re
from typing import Optional, Dict, List, Any

# Curated, verified royalty-free high-resolution Unsplash images organized by semantic visual themes and slots.
THEMATIC_MEDIA_SLOTS: Dict[str, Dict[str, Any]] = {
    "luxury_interior": {
        "hero": "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Bespoke Architectural & Interior Photography",
    },
    "cybersecurity_tech": {
        "hero": "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1510511459019-5dda7724fd87?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Cloud Infrastructure & Cybersecurity Analytics",
    },
    "artisan_bakery": {
        "hero": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1517433670267-08bbd4be890f?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1549931319-a545dcf3bc73?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Artisan Sourdough & Fresh Bakery Showcase",
    },
    "culinary": {
        "hero": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1517433670267-08bbd4be890f?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Culinary & Cafe Photography",
    },
    "food_dining": {
        "hero": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1544025162-d76694265947?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Restaurant & Fine Dining",
    },
    "active_fitness": {
        "hero": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1574680096145-d05b474e2155?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Fitness & Athletic Performance",
    },
    "wellness_spa": {
        "hero": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1519823551278-64ac92734fb1?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1515377905703-c4788e51af15?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Wellness, Skincare & Spa",
    },
    "animals_care": {
        "hero": "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Pet Care & Veterinary",
    },
    "technology_digital": {
        "hero": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Modern Tech & SaaS",
    },
    "craft_artisan": {
        "hero": "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1452860606245-08befc0ff44b?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Artisan Craft & Workshop",
    },
    "medical_health": {
        "hero": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1538108149393-fbbd81895907?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Medical & Healthcare",
    },
    "workspace_business": {
        "hero": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1000&auto=format&fit=crop&q=80",
        "background": "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&auto=format&fit=crop&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1497366216548-37526070297c?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&auto=format&fit=crop&q=80",
        ],
        "label": "Corporate & Professional Advisory",
    },
}

THEME_KEYWORDS = {
    "luxury_interior": (
        "interior design", "interior", "decor", "architect", "architecture",
        "luxury living", "furniture", "living room", "minimalist home",
        "renovation", "residential design", "commercial interior", "home styling",
    ),
    "cybersecurity_tech": (
        "security", "cyber", "cybersecurity", "cloud security", "devops",
        "soc2", "compliance", "threat", "firewall", "encryption", "b2b saas",
        "infosec", "cloud software",
    ),
    "artisan_bakery": (
        "bakery", "sourdough", "bread", "croissant", "pastry", "bake",
        "baker", "patisserie", "flour", "daily menu", "pastries",
    ),
    "culinary": (
        "coffee", "roaster", "cafe", "tea", "roasting", "barista", "dessert",
    ),
    "food_dining": (
        "restaurant", "bistro", "dining", "chef", "cuisine", "gourmet", "kitchen", "dinner", "catering",
    ),
    "active_fitness": (
        "fitness", "gym", "workout", "crossfit", "training", "pilates", "yoga", "athletic", "exercise",
    ),
    "wellness_spa": (
        "spa", "massage", "wellness", "relaxation", "therapy", "skincare", "beauty", "salon", "facial",
    ),
    "animals_care": (
        "pet", "dog", "cat", "groom", "veterinary", "puppy", "kitten", "animal", "canine", "feline",
    ),
    "technology_digital": (
        "software", "saas", "tech", "app", "cloud", "ai", "data", "digital", "platform", "code",
    ),
    "craft_artisan": (
        "artisan", "pottery", "handmade", "woodwork", "studio", "craft", "tailor", "jewelry", "ceramic",
    ),
    "medical_health": (
        "dental", "clinic", "doctor", "health", "physio", "chiro", "medical", "care", "patient", "dentist",
    ),
    "workspace_business": (
        "consult", "agency", "corporate", "law", "finance", "strategy", "office", "business", "advisory",
    ),
}


def match_theme_key(description: Optional[str]) -> Optional[str]:
    """Find matching theme key based on description keywords."""
    if not description or not str(description).strip():
        return None

    desc_lower = str(description).lower()
    for theme, keywords in THEME_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(k)}", desc_lower) for k in keywords):
            return theme

    return None


def retrieve_image_for_description(description: Optional[str]) -> Optional[str]:
    """
    Generic semantic image retrieval based on prompt/description keywords.
    Returns a verified royalty-free high-res hero/showcase image URL, or None if no confident match.
    Never invents broken URLs.
    """
    theme = match_theme_key(description)
    if theme and theme in THEMATIC_MEDIA_SLOTS:
        return THEMATIC_MEDIA_SLOTS[theme]["hero"]
    return None


def retrieve_image_slots(description_or_brief: Optional[str]) -> Dict[str, Any]:
    """
    Retrieve full multi-slot image resources (hero, background, gallery) for a brief/description.
    Returns dictionary with slot URLs and attribution.
    """
    theme = match_theme_key(description_or_brief)
    if theme and theme in THEMATIC_MEDIA_SLOTS:
        data = THEMATIC_MEDIA_SLOTS[theme]
        return {
            "theme_name": theme,
            "label": data.get("label", "Curated Royalty-Free Photography"),
            "hero_url": data.get("hero"),
            "bg_url": data.get("background"),
            "gallery_urls": data.get("gallery", []),
            "is_placeholder": False,
        }

    return {
        "theme_name": "generic_placeholder",
        "label": "Stylized Visual Placeholder Cards (No external image configured)",
        "hero_url": None,
        "bg_url": None,
        "gallery_urls": [],
        "is_placeholder": True,
    }
