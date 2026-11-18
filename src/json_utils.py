"""
JSON parsing and repair helpers for SitePilot AI.
Extracts structured JSON from LLM outputs cleanly.
"""

import json
import re
from typing import Any, Dict, Optional


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract and parse the first valid JSON object found in text.
    Handles markdown code fences, trailing commas, and conversational text.
    """
    if not text or not text.strip():
        return None

    cleaned = text.strip()

    # 1. Direct parse attempt
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. Extract from markdown code blocks ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        code_block_content = match.group(1).strip()
        try:
            return json.loads(code_block_content)
        except Exception:
            cleaned = code_block_content

    # 3. Find outermost curly braces { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = cleaned[first_brace : last_brace + 1]
        try:
            return json.loads(json_candidate)
        except Exception:
            # 4. Remove common trailing commas before closing braces/brackets
            fixed = re.sub(r",\s*([\]}])", r"\1", json_candidate)
            try:
                return json.loads(fixed)
            except Exception:
                pass

    return None
