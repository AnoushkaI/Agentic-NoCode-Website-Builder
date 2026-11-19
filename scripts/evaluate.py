"""
SitePilot AI — Comprehensive Evaluation Benchmark Harness
Evaluates end-to-end website generation, schema validity, design diversity,
WCAG 2.1 AA accessibility contrast, conversational editing, and version rollback
across 10 diverse industry test cases.

Outputs:
  - data/evaluation_results.json (Full diagnostic telemetry & aggregated metrics)
  - data/evaluation_results.csv  (Tabular summary for reporting and spreadsheet analysis)
"""

import argparse
import copy
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add repository root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.schema import WebsiteState, WebsitePlan, PatchOperation, strip_star_emojis
from src.planner import plan_website
from src.generator import generate_website_json
from src.renderer import render_website
from src.editor import plan_edits
from src.patch_engine import apply_patches, restore_version
from src.color_utils import resolve_theme_colors, get_contrast_ratio
from src.providers.factory import get_provider
from src.providers.base import BaseProvider, ProviderResponse, ProviderTestResult
from src.config import LLMConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evaluate")


class OfflineBenchmarkProvider(BaseProvider):
    """Zero-latency offline provider triggering deterministic fallback paths without network delays."""

    def __init__(self):
        super().__init__(LLMConfig(provider="offline", api_key="none", base_url="", model="deterministic-benchmark-v1"))

    def test_connection(self) -> ProviderTestResult:
        return ProviderTestResult(success=True, message="Offline benchmark engine active", provider="offline", model="deterministic", base_url="local", latency_ms=0.1)

    def complete(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 4096) -> ProviderResponse:
        return ProviderResponse(content="", success=False, error="Offline evaluation benchmark mode: deterministic fallback active")


def evaluate_single_sample(
    sample: Dict[str, Any],
    provider: Optional[Any] = None,
    allow_fallback: bool = True,
) -> Dict[str, Any]:
    """
    Execute full end-to-end evaluation lifecycle on a single sample brief:
    1. Plan synthesis & schema validation
    2. Website generation & Pydantic validation
    3. Section completeness & star emoji check
    4. WCAG 2.1 AA interactive color contrast check
    5. HTML/CSS rendering & anchor validation
    6. Conversational editing, no-op detection, and version rollback
    """
    sample_id = sample.get("id", "unknown")
    name = sample.get("business_name", "Unknown Business")
    industry = sample.get("industry", "General")
    brief = sample.get("brief", "")
    sample_edits = sample.get("sample_conversational_edits", [])

    logger.info("Evaluating [%s] %s (%s)...", sample_id, name, industry)

    start_time = time.perf_counter()

    # Step 1: Planning
    t0 = time.perf_counter()
    try:
        plan = plan_website(brief, provider=provider)
        plan_valid = isinstance(plan, WebsitePlan)
        plan_latency = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        logger.error("[%s] Planning failed: %s", sample_id, e)
        plan = None
        plan_valid = False
        plan_latency = round((time.perf_counter() - t0) * 1000, 2)

    # Step 2: Generation
    t1 = time.perf_counter()
    try:
        state, meta = generate_website_json(brief, plan=plan, provider=provider)
        state_valid = isinstance(state, WebsiteState)
        gen_latency = round((time.perf_counter() - t1) * 1000, 2)
    except Exception as e:
        logger.error("[%s] Generation failed: %s", sample_id, e)
        state = None
        meta = {"is_fallback": True, "error": str(e)}
        state_valid = False
        gen_latency = round((time.perf_counter() - t1) * 1000, 2)

    if not state_valid or not state:
        return {
            "sample_id": sample_id,
            "business_name": name,
            "industry": industry,
            "plan_valid": plan_valid,
            "state_valid": False,
            "section_completeness": False,
            "section_count": 0,
            "layout_strategy": getattr(plan, "layout_strategy", "none") if plan else "none",
            "hero_variant": "none",
            "wcag_aa_compliant": False,
            "min_contrast_ratio": 0.0,
            "emoji_free": False,
            "html_rendered": False,
            "html_bytes": 0,
            "edit_patch_success": False,
            "noop_detected_properly": False,
            "rollback_success": False,
            "is_fallback": meta.get("is_fallback", False),
            "total_latency_ms": round((time.perf_counter() - start_time) * 1000, 2),
            "status": "FAILED",
        }

    # Step 3: Section Completeness & Emoji Cleanliness
    sec_types = [s.type for s in state.sections]
    hero_sec = next((s for s in state.sections if s.type == "hero"), None)
    hero_variant = getattr(getattr(hero_sec, "style", None), "layout_variant", "default") if hero_sec else "none"

    has_empty_content = any(not s.content for s in state.sections)
    section_completeness = (len(state.sections) >= 3) and (not has_empty_content)

    # Check star emojis
    star_symbols = ["★", "⭐", "🌟", "✨", "*"]
    has_star_in_title = any(sym in state.title for sym in ["★", "⭐", "🌟", "✨"])
    has_star_in_headings = False
    for s in state.sections:
        c = s.content or {}
        for k in ["title", "heading", "tagline", "subtitle"]:
            val = str(c.get(k, ""))
            if any(sym in val for sym in ["★", "⭐", "🌟", "✨"]):
                has_star_in_headings = True
                break
    emoji_free = not (has_star_in_title or has_star_in_headings)

    # Step 4: WCAG 2.1 AA Contrast Verification
    theme_tokens = resolve_theme_colors(
        state.theme.background,
        state.theme.primary_color,
        state.theme.text_color,
        background_style=state.theme.background_style,
    )
    r_pri = get_contrast_ratio(theme_tokens["btn_primary_bg"], theme_tokens["btn_primary_text"])
    r_pri_hover = get_contrast_ratio(theme_tokens["btn_primary_hover_bg"], theme_tokens["btn_primary_hover_text"])
    r_sec_hover = get_contrast_ratio(theme_tokens["btn_secondary_hover_bg"], theme_tokens["btn_secondary_hover_text"])
    r_nav = get_contrast_ratio(theme_tokens["nav_bg"], theme_tokens["nav_link_color"])
    r_text = get_contrast_ratio(theme_tokens["bg_color"], theme_tokens["text_color"])

    min_contrast = min(r_pri, r_pri_hover, r_sec_hover, r_nav, r_text)
    wcag_aa_compliant = min_contrast >= 4.5

    # Step 5: HTML Rendering
    t_render = time.perf_counter()
    html_output = render_website(state)
    html_rendered = len(html_output) > 500 and "<!DOCTYPE html>" in html_output
    html_bytes = len(html_output.encode("utf-8"))

    # Step 6: Conversational Edit, No-Op Check & Rollback
    snapshot_v1 = copy.deepcopy(state)
    edit_instruction = sample_edits[0] if sample_edits else "Change the hero CTA to Get Started Today"

    # Conversational Edit
    edit_plan = plan_edits(edit_instruction, state, provider=provider)
    state_v2, edit_ok, edit_msg, _ = apply_patches(state, edit_plan.operations, instruction=edit_instruction)
    edit_patch_success = edit_ok and (state_v2.version == state.version + 1)

    # Test No-Op Rejection
    active_for_noop = state_v2 if edit_patch_success else state
    curr_hero_title = active_for_noop.sections[0].content.get("title", "")
    identical_op = PatchOperation(op="update_section", target_id=active_for_noop.sections[0].id, content={"title": curr_hero_title})
    _, noop_ok, noop_msg, _ = apply_patches(active_for_noop, [identical_op], instruction="Re-set identical title")
    noop_detected_properly = (noop_ok is False) and ("No changes were made" in noop_msg)

    # Test Version Rollback
    target_state = state_v2 if edit_patch_success else active_for_noop
    restored_v3, rb_ok, _, _ = restore_version(snapshot_v1, target_state, instruction="Undo edit and restore v1")
    rollback_success = rb_ok and (restored_v3.version == target_state.version + 1) and (restored_v3.title == snapshot_v1.title)

    total_latency = round((time.perf_counter() - start_time) * 1000, 2)

    status = "PASSED" if (plan_valid and state_valid and section_completeness and wcag_aa_compliant and edit_patch_success and noop_detected_properly and rollback_success) else "WARNING"

    return {
        "sample_id": sample_id,
        "business_name": name,
        "industry": industry,
        "plan_valid": plan_valid,
        "state_valid": state_valid,
        "section_completeness": section_completeness,
        "section_count": len(state.sections),
        "sections": sec_types,
        "layout_strategy": getattr(plan, "layout_strategy", "standard"),
        "hero_variant": hero_variant,
        "wcag_aa_compliant": wcag_aa_compliant,
        "min_contrast_ratio": round(min_contrast, 2),
        "emoji_free": emoji_free,
        "html_rendered": html_rendered,
        "html_bytes": html_bytes,
        "edit_patch_success": edit_patch_success,
        "noop_detected_properly": noop_detected_properly,
        "rollback_success": rollback_success,
        "is_fallback": meta.get("is_fallback", False),
        "total_latency_ms": total_latency,
        "status": status,
    }


def run_benchmark(
    samples_path: Path,
    output_json_path: Path,
    output_csv_path: Path,
    provider_name: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Execute the evaluation benchmark suite over all sample inputs."""
    if not samples_path.exists():
        raise FileNotFoundError(f"Samples file not found at {samples_path}")

    with open(samples_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = data.get("samples", [])
    logger.info("Loaded %d sample test cases from %s", len(samples), samples_path)

    provider = None
    if provider_name and provider_name.lower() != "offline":
        try:
            provider = get_provider(provider_name)
            logger.info("Using configured provider: %s", provider_name)
        except Exception as e:
            logger.warning("Provider '%s' unavailable (%s). Falling back to offline benchmark provider.", provider_name, e)
            provider = OfflineBenchmarkProvider()
    else:
        provider = OfflineBenchmarkProvider()
        logger.info("Running in offline deterministic benchmark mode (fast, zero-network).")

    results: List[Dict[str, Any]] = []
    for s in samples:
        res = evaluate_single_sample(s, provider=provider)
        results.append(res)

    # Compute Aggregate Metrics
    n = len(results)
    plan_valid_count = sum(1 for r in results if r["plan_valid"])
    state_valid_count = sum(1 for r in results if r["state_valid"])
    completeness_count = sum(1 for r in results if r["section_completeness"])
    wcag_count = sum(1 for r in results if r["wcag_aa_compliant"])
    emoji_count = sum(1 for r in results if r["emoji_free"])
    html_count = sum(1 for r in results if r["html_rendered"])
    edit_count = sum(1 for r in results if r["edit_patch_success"])
    noop_count = sum(1 for r in results if r["noop_detected_properly"])
    rb_count = sum(1 for r in results if r["rollback_success"])
    avg_latency = round(sum(r["total_latency_ms"] for r in results) / n, 2) if n else 0.0

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_samples": n,
        "provider_tested": provider_name or "offline_deterministic_engine",
        "metrics": {
            "plan_schema_validity_rate_pct": round((plan_valid_count / n) * 100, 1),
            "state_schema_validity_rate_pct": round((state_valid_count / n) * 100, 1),
            "section_completeness_rate_pct": round((completeness_count / n) * 100, 1),
            "wcag_2_1_aa_contrast_rate_pct": round((wcag_count / n) * 100, 1),
            "emoji_sanitization_rate_pct": round((emoji_count / n) * 100, 1),
            "html_render_success_rate_pct": round((html_count / n) * 100, 1),
            "conversational_edit_success_rate_pct": round((edit_count / n) * 100, 1),
            "noop_detection_rate_pct": round((noop_count / n) * 100, 1),
            "version_rollback_success_rate_pct": round((rb_count / n) * 100, 1),
            "average_end_to_end_latency_ms": avg_latency,
        },
        "overall_status": "ALL_PASSED" if all(r["status"] == "PASSED" for r in results) else "COMPLETED_WITH_WARNINGS",
    }

    # Save JSON output
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
    logger.info("Saved JSON evaluation results to %s", output_json_path)

    # Save CSV output
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_fields = [
        "sample_id",
        "business_name",
        "industry",
        "status",
        "plan_valid",
        "state_valid",
        "section_completeness",
        "section_count",
        "layout_strategy",
        "hero_variant",
        "wcag_aa_compliant",
        "min_contrast_ratio",
        "emoji_free",
        "html_rendered",
        "html_bytes",
        "edit_patch_success",
        "noop_detected_properly",
        "rollback_success",
        "is_fallback",
        "total_latency_ms",
    ]
    with open(output_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            row = {k: r.get(k, "") for k in csv_fields}
            writer.writerow(row)
    logger.info("Saved CSV evaluation results to %s", output_csv_path)

    return summary, results


def print_summary_table(summary: Dict[str, Any], results: List[Dict[str, Any]]) -> None:
    """Print an attractive summary table to stdout."""
    print("\n" + "=" * 90)
    print("SitePilot AI — Evaluation Benchmark Results Summary")
    print("=" * 90)
    print(f"Timestamp:        {summary['timestamp']}")
    print(f"Provider Tested:  {summary['provider_tested']}")
    print(f"Total Test Cases: {summary['total_samples']}")
    print(f"Overall Status:   {summary['overall_status']}")
    print("-" * 90)
    print(f"{'Metric':<40} {'Score':>12}")
    print("-" * 90)
    m = summary["metrics"]
    print(f"{'Plan Schema Validity Rate':<40} {m['plan_schema_validity_rate_pct']:>11}%")
    print(f"{'State Schema Validity Rate':<40} {m['state_schema_validity_rate_pct']:>11}%")
    print(f"{'Section Completeness Rate':<40} {m['section_completeness_rate_pct']:>11}%")
    print(f"{'WCAG 2.1 AA Contrast Rate (>=4.5:1)':<40} {m['wcag_2_1_aa_contrast_rate_pct']:>11}%")
    print(f"{'Heading & Title Emoji-Free Rate':<40} {m['emoji_sanitization_rate_pct']:>11}%")
    print(f"{'HTML/CSS Render Success Rate':<40} {m['html_render_success_rate_pct']:>11}%")
    print(f"{'Conversational Edit Success Rate':<40} {m['conversational_edit_success_rate_pct']:>11}%")
    print(f"{'No-Op Detection & Rejection Rate':<40} {m['noop_detection_rate_pct']:>11}%")
    print(f"{'Version Rollback Success Rate':<40} {m['version_rollback_success_rate_pct']:>11}%")
    print(f"{'Average End-to-End Latency':<40} {m['average_end_to_end_latency_ms']:>9} ms")
    print("-" * 90)
    print(f"{'ID':<28} {'Industry':<22} {'Sections':<9} {'WCAG':<6} {'Edit':<6} {'Status':<8}")
    print("-" * 90)
    for r in results:
        wcag_str = "PASS" if r["wcag_aa_compliant"] else "FAIL"
        edit_str = "PASS" if r["edit_patch_success"] else "FAIL"
        print(f"{r['sample_id']:<28} {r['industry'][:20]:<22} {r['section_count']:<9} {wcag_str:<6} {edit_str:<6} {r['status']:<8}")
    print("=" * 90 + "\n")


def main():
    parser = argparse.ArgumentParser(description="SitePilot AI Evaluation Benchmark Harness")
    parser.add_argument(
        "--samples",
        type=Path,
        default=REPO_ROOT / "data" / "sample_inputs.json",
        help="Path to sample inputs JSON file",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=REPO_ROOT / "data" / "evaluation_results.json",
        help="Path for evaluation output JSON",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=REPO_ROOT / "data" / "evaluation_results.csv",
        help="Path for evaluation output CSV",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Optional provider to test against (nvidia, ollama, openai)",
    )
    args = parser.parse_args()

    summary, results = run_benchmark(
        samples_path=args.samples,
        output_json_path=args.output_json,
        output_csv_path=args.output_csv,
        provider_name=args.provider,
    )
    print_summary_table(summary, results)


if __name__ == "__main__":
    main()
