"""
Deterministic Patch Engine for SitePilot AI.
Executes pure Python mutations on deep copies of WebsiteState.
Validates all mutations with Pydantic schemas before committing.
Guarantees full rollback on error, preserves unmodified sections, and increments version numbers.
"""

import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import ValidationError

from src.schema import (
    WebsiteState,
    Section,
    PatchOperation,
    EditHistoryItem,
    OperationRecord,
    normalize_section_content,
    SUPPORTED_SECTION_TYPES,
)

logger = logging.getLogger(__name__)


class PatchEngineError(Exception):
    """Base exception for all patch engine errors."""
    pass


class SectionNotFoundError(PatchEngineError):
    """Raised when an operation targets a section ID that does not exist in state."""
    pass


class InvalidPatchError(PatchEngineError):
    """Raised when a patch operation has invalid or missing required parameters."""
    pass


def apply_update_section(state_dict: Dict[str, Any], op: PatchOperation) -> List[OperationRecord]:
    """
    Update content or style of an existing section identified by target_id.
    Merges updates into existing content/style dictionaries without wiping existing keys.
    Returns audit records capturing previous and new property values.
    """
    if not op.target_id:
        raise InvalidPatchError("update_section requires target_id.")

    target = None
    for s in state_dict.get("sections", []):
        if s.get("id") == op.target_id:
            target = s
            break

    if not target:
        existing_ids = [s.get("id") for s in state_dict.get("sections", [])]
        raise SectionNotFoundError(
            f"Section '{op.target_id}' not found in website state. Available sections: {existing_ids}"
        )

    records: List[OperationRecord] = []

    # 1. Update Content
    if op.content:
        target_content = target.get("content", {})
        if not isinstance(target_content, dict):
            target_content = {}
        for k, v in op.content.items():
            prev_val = copy.deepcopy(target_content.get(k))
            target_content[k] = v
            records.append(
                OperationRecord(
                    op="update_section",
                    target_id=op.target_id,
                    property_path=f"content.{k}",
                    previous_value=prev_val,
                    new_value=copy.deepcopy(v),
                    status="success",
                    details=f"Updated section '{op.target_id}' content.{k}",
                )
            )
        target["content"] = target_content

    # 2. Update Style
    if op.style:
        target_style = target.get("style", {})
        if not isinstance(target_style, dict):
            target_style = {}

        STYLE_PROPERTY_MAP = {
            "background": "background_color",
            "background_color": "background_color",
            "bg": "background_color",
            "bg_color": "background_color",
            "text": "text_color",
            "text_color": "text_color",
            "color": "text_color",
            "align": "alignment",
            "alignment": "alignment",
            "layout": "layout_variant",
            "layout_variant": "layout_variant",
            "padding": "padding",
            "variant": "variant",
        }

        for k, v in op.style.items():
            canon_k = STYLE_PROPERTY_MAP.get(k.lower(), k)
            prev_val = copy.deepcopy(target_style.get(canon_k))
            target_style[canon_k] = v
            records.append(
                OperationRecord(
                    op="update_section",
                    target_id=op.target_id,
                    property_path=f"style.{canon_k}",
                    previous_value=prev_val,
                    new_value=copy.deepcopy(v),
                    status="success",
                    details=f"Updated section '{op.target_id}' style.{canon_k}",
                )
            )

        # Convenience handling for "variant": "dark" or "light"
        v_choice = op.style.get("variant")
        if v_choice == "dark":
            if "background_color" not in target_style:
                target_style["background_color"] = "#0F172A"
            if "text_color" not in target_style:
                target_style["text_color"] = "#F8FAFC"
        elif v_choice == "light":
            if "background_color" not in target_style:
                target_style["background_color"] = "#FFFFFF"
            if "text_color" not in target_style:
                target_style["text_color"] = "#1E293B"

        target["style"] = target_style

    # If alignment was provided in content instead of style, sync to target_style
    if op.content and ("alignment" in op.content or "align" in op.content):
        align_v = op.content.get("alignment") or op.content.get("align")
        if align_v in ("center", "left", "right"):
            target_style = target.setdefault("style", {})
            if isinstance(target_style, dict):
                target_style["alignment"] = align_v

    return records


def apply_add_section(state_dict: Dict[str, Any], op: PatchOperation) -> List[OperationRecord]:
    """
    Add a new section of a valid type at specified position or relative placement.
    Auto-generates a unique stable ID (e.g. 'testimonials-1', 'faq-1').
    Returns an audit record capturing the full added section.
    """
    s_type = op.section_type
    if not s_type or s_type not in SUPPORTED_SECTION_TYPES:
        raise InvalidPatchError(
            f"add_section requires a valid section_type from {SUPPORTED_SECTION_TYPES}. Got '{s_type}'."
        )

    sections = state_dict.setdefault("sections", [])
    existing_ids = {s.get("id") for s in sections}

    # Generate stable unique ID (e.g. type-1, type-2)
    count = 1
    new_id = f"{s_type}-{count}"
    while new_id in existing_ids:
        count += 1
        new_id = f"{s_type}-{count}"

    # Build default content and overlay user overrides
    base_content = normalize_section_content(s_type, op.content or {})
    if op.content and isinstance(op.content, dict):
        base_content.update(op.content)

    new_section: Dict[str, Any] = {
        "id": new_id,
        "type": s_type,
        "content": base_content,
        "style": op.style or {"alignment": "center", "padding": "medium"},
    }

    # Determine insertion position
    if op.position is not None:
        idx = max(0, min(len(sections), op.position))
        sections.insert(idx, new_section)
    elif op.target_id:
        target_idx = None
        for i, s in enumerate(sections):
            if s.get("id") == op.target_id:
                target_idx = i
                break
        if target_idx is None:
            # If target_id not found, append to end
            sections.append(new_section)
        elif op.placement == "before":
            sections.insert(target_idx, new_section)
        else:
            sections.insert(target_idx + 1, new_section)
    elif op.placement == "start":
        sections.insert(0, new_section)
    else:
        # Default append to end
        sections.append(new_section)

    return [
        OperationRecord(
            op="add_section",
            target_id=new_id,
            property_path="sections",
            previous_value=None,
            new_value=copy.deepcopy(new_section),
            status="success",
            details=f"Added section '{new_id}' of type '{s_type}' ({op.placement or 'end'})",
        )
    ]


def apply_remove_section(state_dict: Dict[str, Any], op: PatchOperation) -> List[OperationRecord]:
    """
    Remove an existing section by target_id.
    Ensures at least one section remains in the website.
    Returns an audit record capturing the entire removed section dictionary.
    """
    if not op.target_id:
        raise InvalidPatchError("remove_section requires target_id.")

    sections = state_dict.get("sections", [])
    if len(sections) <= 1:
        raise InvalidPatchError("Cannot remove section: website must retain at least one section.")

    target_idx = None
    for i, s in enumerate(sections):
        if s.get("id") == op.target_id:
            target_idx = i
            break

    if target_idx is None:
        existing_ids = [s.get("id") for s in sections]
        raise SectionNotFoundError(
            f"Cannot remove section '{op.target_id}': ID not found. Existing IDs: {existing_ids}"
        )

    removed_sec = copy.deepcopy(sections[target_idx])
    sections.pop(target_idx)

    return [
        OperationRecord(
            op="remove_section",
            target_id=op.target_id,
            property_path="sections",
            previous_value=removed_sec,
            new_value=None,
            status="success",
            details=f"Removed section '{op.target_id}' of type '{removed_sec.get('type')}'",
        )
    ]


def apply_reorder_sections(state_dict: Dict[str, Any], op: PatchOperation) -> List[OperationRecord]:
    """
    Reorder sections using a complete ordered list of section_ids or moving target_id to position.
    Returns an audit record capturing previous and new section order sequences.
    """
    sections = state_dict.get("sections", [])
    existing_map = {s.get("id"): s for s in sections}
    old_order = [s.get("id") for s in sections]

    if op.section_ids:
        # Full list reorder
        if set(op.section_ids) != set(existing_map.keys()) or len(op.section_ids) != len(sections):
            raise InvalidPatchError(
                f"reorder_sections section_ids must be an exact permutation of existing IDs: {list(existing_map.keys())}"
            )
        state_dict["sections"] = [existing_map[sid] for sid in op.section_ids]
        new_order = list(op.section_ids)

    elif op.target_id and op.position is not None:
        # Single section move
        target_idx = None
        for i, s in enumerate(sections):
            if s.get("id") == op.target_id:
                target_idx = i
                break
        if target_idx is None:
            raise SectionNotFoundError(f"Cannot move section '{op.target_id}': not found.")

        item = sections.pop(target_idx)
        new_pos = max(0, min(len(sections), op.position))
        sections.insert(new_pos, item)
        new_order = [s.get("id") for s in state_dict["sections"]]
    else:
        raise InvalidPatchError("reorder_sections requires either section_ids list or target_id with position.")

    return [
        OperationRecord(
            op="reorder_sections",
            target_id=op.target_id,
            property_path="sections_order",
            previous_value=old_order,
            new_value=new_order,
            status="success",
            details=f"Reordered sections from {old_order} to {new_order}",
        )
    ]


def apply_update_theme(state_dict: Dict[str, Any], op: PatchOperation) -> List[OperationRecord]:
    """
    Update theme properties (background, primary_color, text_color, fonts, nav_style, etc.).
    Returns audit records capturing previous and new theme values.
    """
    if not op.theme or not isinstance(op.theme, dict):
        raise InvalidPatchError("update_theme requires a theme dictionary payload.")

    theme = state_dict.setdefault("theme", {})
    if not isinstance(theme, dict):
        theme = {}
        state_dict["theme"] = theme

    THEME_PROPERTY_MAP = {
        "primary": "primary_color",
        "primary_color": "primary_color",
        "brand_color": "primary_color",
        "color": "primary_color",
        "theme_color": "primary_color",
        "button_color": "primary_color",
        "background": "background",
        "background_color": "background",
        "bg": "background",
        "bg_color": "background",
        "text_color": "text_color",
        "text": "text_color",
        "font": "font_family",
        "font_family": "font_family",
        "heading_font": "heading_font",
        "background_style": "background_style",
        "bg_style": "background_style",
        "nav_style": "nav_style",
        "navbar_style": "nav_style",
        "accent": "accent_color",
        "accent_color": "accent_color",
    }

    records: List[OperationRecord] = []
    for k, v in op.theme.items():
        canon_k = THEME_PROPERTY_MAP.get(k.lower(), k)
        prev_val = copy.deepcopy(theme.get(canon_k))
        theme[canon_k] = v
        records.append(
            OperationRecord(
                op="update_theme",
                target_id="theme",
                property_path=f"theme.{canon_k}",
                previous_value=prev_val,
                new_value=copy.deepcopy(v),
                status="success",
                details=f"Updated theme.{canon_k}",
            )
        )

    return records


def apply_patches(
    state: WebsiteState,
    operations: List[PatchOperation],
    instruction: str = "",
    summary: str = "",
) -> Tuple[WebsiteState, bool, str, Optional[EditHistoryItem]]:
    """
    Apply a sequence of patch operations atomically to a deep copy of current WebsiteState.
    1. Executes operations sequentially in pure Python, recording detailed before/after values.
    2. Validates mutated dictionary against Pydantic WebsiteState schema.
    3. If valid: increments version (v_current + 1), logs full audit history, commits.
    4. If invalid or nonexistent target: rolls back completely, returns original state unchanged.

    Returns:
        (resulting_state, success_bool, message_str, history_item_or_none)
    """
    if not operations:
        failed_history_item = EditHistoryItem(
            version=state.version,
            version_before=state.version,
            instruction=instruction or "No-op edit request",
            summary="No changes requested or planned",
            operations=[],
            operation_records=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=False,
            error="No patch operations provided. Please specify what content, section, or styling you would like to edit.",
        )
        return (
            state,
            False,
            "No changes detected: edit plan contains 0 operations. Please specify what content, section, or styling you would like to edit.",
            failed_history_item,
        )

    # Step 1: Deep copy to isolate mutations from original state
    state_copy_dict = copy.deepcopy(state.model_dump())
    accumulated_records: List[OperationRecord] = []

    try:
        # Step 2: Execute each patch operation atomically
        for op in operations:
            if op.op == "update_section":
                records = apply_update_section(state_copy_dict, op)
            elif op.op == "add_section":
                records = apply_add_section(state_copy_dict, op)
            elif op.op == "remove_section":
                records = apply_remove_section(state_copy_dict, op)
            elif op.op == "reorder_sections":
                records = apply_reorder_sections(state_copy_dict, op)
            elif op.op == "update_theme":
                records = apply_update_theme(state_copy_dict, op)
            else:
                raise InvalidPatchError(f"Unsupported patch operation: '{op.op}'")

            accumulated_records.extend(records)

        # Step 3: Verify whether any actual state changes occurred
        test_state = copy.deepcopy(state_copy_dict)
        test_state["version"] = state.version
        if test_state == state.model_dump():
            logger.info("Edit operations resulted in no actual state changes. Treating as no-op.")
            no_op_history = EditHistoryItem(
                version=state.version,
                version_before=state.version,
                instruction=instruction or "No-op edit request",
                summary=summary or "No state properties were modified",
                operations=[op.model_dump() for op in operations],
                operation_records=accumulated_records,
                timestamp=datetime.now(timezone.utc).isoformat(),
                success=False,
                error="No state changes were made. The requested edit did not modify any properties in the website state.",
            )
            return (
                state,
                False,
                "No changes were made: the requested edit did not modify any properties in the website state.",
                no_op_history,
            )

        # Step 4: Increment version number strictly after successful mutation
        state_copy_dict["version"] = state.version + 1

        # Step 5: Strict Pydantic schema validation
        mutated_state = WebsiteState.model_validate(state_copy_dict)

        # Mark all individual operation records as successful
        for r in accumulated_records:
            r.status = "success"

        # Step 6: Construct complete audit log history item
        now_iso = datetime.now(timezone.utc).isoformat()
        history_item = EditHistoryItem(
            version=mutated_state.version,
            version_before=state.version,
            instruction=instruction or "Structured patch application",
            summary=summary or f"Applied {len(operations)} edit operation(s)",
            operations=[op.model_dump() for op in operations],
            operation_records=accumulated_records,
            timestamp=now_iso,
            success=True,
            error=None,
        )

        logger.info(
            "Successfully applied %d edit operations. Version bumped v%d -> v%d",
            len(operations),
            state.version,
            mutated_state.version,
        )
        return (
            mutated_state,
            True,
            f"Successfully updated website to version v{mutated_state.version} ({len(operations)} operations applied).",
            history_item,
        )

    except (PatchEngineError, ValidationError, Exception) as err:
        err_msg = str(err)
        logger.warning("Patch application failed: %s. Rolling back to version v%d.", err_msg, state.version)

        # Mark any executed operations as rolled back
        for r in accumulated_records:
            r.status = "rolled_back"
            r.details = f"Rolled back due to error: {err_msg}"

        # Append failing record
        accumulated_records.append(
            OperationRecord(
                op="transaction_rollback",
                property_path="website_state",
                previous_value=f"v{state.version}",
                new_value=f"v{state.version}",
                status="failed",
                details=err_msg,
            )
        )

        failed_history_item = EditHistoryItem(
            version=state.version,
            version_before=state.version,
            instruction=instruction,
            summary=summary or "Failed edit attempt",
            operations=[op.model_dump() for op in operations],
            operation_records=accumulated_records,
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=False,
            error=err_msg,
        )
        return state, False, f"Edit rejected: {err_msg}. Original state preserved.", failed_history_item


def restore_version(
    target_snapshot: WebsiteState,
    current_state: WebsiteState,
    instruction: Optional[str] = None,
) -> Tuple[WebsiteState, bool, str, EditHistoryItem]:
    """
    Restore a past version snapshot as a brand new version.
    - Does NOT delete or overwrite historical versions.
    - Sets new version to current_state.version + 1.
    - Validates with Pydantic WebsiteState before committing.
    - Creates detailed EditHistoryItem audit log capturing the restoration.
    """
    target_v = target_snapshot.version
    current_v = current_state.version
    new_v = current_v + 1

    snapshot_dict = copy.deepcopy(target_snapshot.model_dump())
    snapshot_dict["version"] = new_v

    try:
        validated_restored_state = WebsiteState.model_validate(snapshot_dict)
    except ValidationError as err:
        err_msg = f"Cannot restore version v{target_v}: schema validation failed: {err}"
        logger.error(err_msg)
        failed_hist = EditHistoryItem(
            version=current_v,
            version_before=current_v,
            instruction=instruction or f"Restore version v{target_v}",
            summary=f"Failed to restore version v{target_v}",
            operations=[{"op": "restore_version", "target_version": target_v}],
            operation_records=[
                OperationRecord(
                    op="restore_version",
                    property_path="state",
                    previous_value=f"v{current_v}",
                    new_value=f"v{target_v}",
                    status="failed",
                    details=err_msg,
                )
            ],
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=False,
            error=err_msg,
        )
        return current_state, False, err_msg, failed_hist

    op_record = OperationRecord(
        op="restore_version",
        property_path="state",
        previous_value=f"v{current_v}",
        new_value=f"v{target_v} (re-committed as v{new_v})",
        status="success",
        details=f"Restored website state from v{target_v} as new version v{new_v}",
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    history_item = EditHistoryItem(
        version=new_v,
        version_before=current_v,
        instruction=instruction or f"Restore version v{target_v}",
        summary=f"Restored website state from version v{target_v} as new version v{new_v}",
        operations=[{"op": "restore_version", "target_version": target_v, "new_version": new_v}],
        operation_records=[op_record],
        timestamp=now_iso,
        success=True,
        error=None,
    )

    logger.info("Restored version v%d as new version v%d", target_v, new_v)
    return validated_restored_state, True, f"Successfully restored state from v{target_v} as new version v{new_v}.", history_item

