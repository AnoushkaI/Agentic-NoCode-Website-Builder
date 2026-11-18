"""
Pydantic data schemas for SitePilot AI.
Defines the strict contract between AI agents and the frontend renderer.
"""

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
    "cta",
    "contact",
]


class ThemeConfig(BaseModel):
    """Global styling and color palette."""
    background: str = Field(default="#ffffff", description="Background color hex or CSS string")
    primary_color: str = Field(default="#2563eb", description="Primary brand color hex")
    text_color: str = Field(default="#1e293b", description="Primary text color hex")
    font_family: str = Field(default="Inter, sans-serif", description="Font family")


class SectionStyle(BaseModel):
    """Supported style properties for sections."""
    background_color: Optional[str] = Field(default=None, description="Section background color")
    text_color: Optional[str] = Field(default=None, description="Section text color")
    padding: Optional[str] = Field(default="medium", description="Section padding: small, medium, large")
    alignment: Optional[str] = Field(default="center", description="Content alignment: left, center, right")
    variant: Optional[str] = Field(default="default", description="Visual variant: default, dark, light, card")
    layout_variant: Optional[str] = Field(default="default", description="Layout structure variant: split, centered, minimal, grid, list, pill_cards, table, spotlight")


class Section(BaseModel):
    """A distinct component section of the website with a stable unique ID."""
    id: str = Field(..., description="Unique, stable identifier (e.g. hero-1, pricing-1)")
    type: SectionTypeLiteral = Field(..., description="Component type from predefined library")
    content: Dict[str, Any] = Field(default_factory=dict, description="Component-specific content data")
    style: SectionStyle = Field(default_factory=SectionStyle, description="Component styling overrides")

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
            if "body" not in c and "heading" not in c:
                c["body"] = "About Us"
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
    typography: str = Field(default="Plus Jakarta Sans, sans-serif", description="Recommended font family for visual direction")
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
