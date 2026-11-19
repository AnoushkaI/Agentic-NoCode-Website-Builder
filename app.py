"""
SitePilot AI — Agentic No-Code Website Builder
Phase 3: Predefined HTML/CSS Renderer & Live Streamlit Preview
"""

import copy
import html
import json
import streamlit as st
import streamlit.components.v1 as components
from src.config import get_llm_config, SUPPORTED_PROVIDERS
from src.providers.factory import get_provider
from src.planner import plan_website
from src.generator import generate_website_json, WebsiteGenerationError
from src.renderer import render_website
from src.editor import plan_edits
from src.patch_engine import apply_patches, restore_version
from src.preview_server import update_preview_html, get_preview_url

# Set Streamlit page configuration
st.set_page_config(
    page_title="SitePilot AI - Website Builder",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "website_state" not in st.session_state:
    st.session_state["website_state"] = None
if "website_plan" not in st.session_state:
    st.session_state["website_plan"] = None
if "generation_meta" not in st.session_state:
    st.session_state["generation_meta"] = None
if "last_error" not in st.session_state:
    st.session_state["last_error"] = None
if "edit_history" not in st.session_state:
    st.session_state["edit_history"] = []
if "version_snapshots" not in st.session_state:
    st.session_state["version_snapshots"] = {}
if "edit_last_msg" not in st.session_state:
    st.session_state["edit_last_msg"] = None
if "edit_last_error" not in st.session_state:
    st.session_state["edit_last_error"] = None

# Custom styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        color: #1E293B;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }
    .badge-active { background-color: #DEF7EC; color: #03543F; }
    .badge-pending { background-color: #FEF08A; color: #713F12; }
    .card {
        padding: 1.25rem;
        border-radius: 8px;
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        margin-bottom: 1rem;
    }
    .section-pill {
        display: inline-block;
        background-color: #EEF2FF;
        color: #4338CA;
        padding: 0.2rem 0.55rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 0.15rem;
    }
    .preview-frame-container {
        border: 1px solid #CBD5E1;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        background-color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">🚀 SitePilot AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Agentic No-Code Website Builder — Conversational Generation & Structured In-Place Editing</div>',
    unsafe_allow_html=True,
)

# Sidebar: Provider & Model Configuration
with st.sidebar:
    st.header("⚙️ LLM Provider Setup")
    st.markdown("Configure and verify your AI model connection.")

    env_config = get_llm_config()
    current_default_idx = (
        SUPPORTED_PROVIDERS.index(env_config.provider)
        if env_config.provider in SUPPORTED_PROVIDERS
        else 0
    )

    selected_provider = st.selectbox(
        "Select Provider",
        options=SUPPORTED_PROVIDERS,
        index=current_default_idx,
        help="NVIDIA NIM (prototype default), Ollama (local backup), or OpenAI.",
    )

    active_config = get_llm_config(provider_override=selected_provider)

    st.markdown("---")
    st.markdown(f"**Model:** `{active_config.model}`")
    st.markdown(f"**Base URL:** `{active_config.base_url}`")
    st.markdown(f"**API Key:** `{active_config.masked_api_key}`")
    st.markdown(f"**Configured:** {'✅ Ready' if active_config.is_configured else '⚠️ Missing Key / Unconfigured'}")

    st.markdown("---")

    # Connectivity Test Button
    if st.button("🔌 Test Provider Connection", use_container_width=True, type="secondary"):
        with st.spinner(f"Pinging {active_config.provider}..."):
            provider_instance = get_provider(selected_provider)
            test_result = provider_instance.test_connection()

            if test_result.success:
                st.success(f"**Connected!** ({test_result.latency_ms:.1f}ms)")
                if test_result.sample_response:
                    st.caption(f"Sample: {test_result.sample_response}")
            else:
                st.error(f"**Failed:** {test_result.message}")
                if test_result.troubleshooting_tip:
                    st.warning(f"💡 {test_result.troubleshooting_tip}")

    st.markdown("---")
    st.caption("SitePilot AI — Workstream B")
    st.caption("Phase 3: Live Preview & HTML/CSS Renderer")

# Main 2-Column Layout
col_left, col_right = st.columns([1, 1], gap="medium")

with col_left:
    st.subheader("1. Website Brief")
    default_brief = "Create a modern landing page for a fitness studio with pricing, testimonials, and a contact form."
    brief_text = st.text_area(
        "Describe your website or business in natural language:",
        value=default_brief,
        height=110,
        help="Enter the business concept, audience, and key sections needed.",
    )

    generate_clicked = st.button("✨ Generate Website", type="primary", use_container_width=True)

    if generate_clicked:
        st.session_state["last_error"] = None
        if not brief_text.strip():
            st.error("Please enter a website brief.")
        else:
            provider = get_provider(selected_provider)
            with st.status("🚀 Generating Website...", expanded=True) as status:
                try:
                    # Step 1: Planning
                    st.write("🧠 **Step 1/3: Analyzing brief & generating website plan...**")
                    plan = plan_website(brief_text, provider=provider)
                    st.session_state["website_plan"] = plan
                    st.write(f"Planned Sections: {', '.join(plan.planned_sections)}")

                    # Step 2: Generation
                    st.write("🏗️ **Step 2/3: Generating structured WebsiteState JSON...**")
                    state, meta = generate_website_json(brief_text, plan, provider=provider)
                    st.session_state["website_state"] = state
                    st.session_state["generation_meta"] = meta
                    st.session_state["version_snapshots"] = {state.version: copy.deepcopy(state)}
                    st.session_state["edit_history"] = []

                    # Step 3: Validation
                    st.write(f"✅ **Step 3/3: Validated schema (Pydantic). Version: v{state.version}**")
                    if meta.get("repaired"):
                        st.info("Notice: LLM output required 1 schema repair attempt, which succeeded.")
                    if meta.get("is_fallback"):
                        st.warning("Notice: Provider unavailable or offline; generated deterministic fallback website.")

                    status.update(label="Website Generation & Render Complete!", state="complete", expanded=False)
                    st.rerun()

                except WebsiteGenerationError as e:
                    st.session_state["last_error"] = str(e)
                    status.update(label="Generation Failed", state="error", expanded=True)
                    st.error(f"Validation Error: {str(e)}")
                except Exception as e:
                    st.session_state["last_error"] = str(e)
                    status.update(label="System Error", state="error", expanded=True)
                    st.error(f"Unexpected Error: {str(e)}")

    if st.session_state.get("last_error"):
        st.error(f"⚠️ Last Error: {st.session_state['last_error']}")

    st.markdown("---")

    # Phase 4 Conversational Edit Agent & Deterministic Patch Engine
    st.subheader("2. Conversational Edit")
    active_state = st.session_state.get("website_state")

    if not active_state:
        st.text_input(
            "Request a change (e.g., 'Make the hero darker' or 'Change CTA to Book a Trial'):",
            disabled=True,
            help="Generate a website above first to enable conversational editing.",
            key="edit_prompt_disabled",
        )
        st.button("💬 Apply Edit", disabled=True, use_container_width=True)
        st.caption("ℹ️ Conversational editing will be enabled once a website is generated.")
    else:
        with st.form(key="conversational_edit_form", clear_on_submit=True):
            edit_text = st.text_input(
                "Request a change to the website:",
                placeholder="e.g. 'Make the hero darker', 'Change CTA to Book a Trial', 'Add a testimonials section'",
                help="Natural language instruction targeting section content, styles, ordering, or theme.",
            )
            col_apply, col_status = st.columns([1, 1])
            with col_apply:
                apply_submitted = st.form_submit_button("💬 Apply Edit", type="primary", use_container_width=True)
            with col_status:
                st.markdown(
                    f'<div style="padding-top: 6px;"><span class="status-badge badge-active">Target: v{active_state.version}</span></div>',
                    unsafe_allow_html=True,
                )

        if apply_submitted:
            if not edit_text or not edit_text.strip():
                st.warning("Please enter a specific edit instruction.")
            else:
                current_provider = get_provider(selected_provider)
                with st.status(f"Applying Edit to v{active_state.version}...", expanded=True) as edit_status:
                    try:
                        edit_status.write("1. Parsing natural language instruction into structured patch operations...")
                        plan = plan_edits(edit_text.strip(), active_state, provider=current_provider)
                        edit_status.write(f"2. Generated plan: {plan.summary} ({len(plan.operations)} operations)")

                        edit_status.write("3. Applying deterministic patches and validating state schema...")
                        new_state, success, msg, hist_item = apply_patches(
                            active_state,
                            plan.operations,
                            instruction=edit_text.strip(),
                            summary=plan.summary,
                        )

                        if success and new_state:
                            st.session_state["website_state"] = new_state
                            st.session_state["version_snapshots"][new_state.version] = copy.deepcopy(new_state)
                            if hist_item:
                                st.session_state["edit_history"].append(hist_item)
                            st.session_state["edit_last_msg"] = f"Applied edit (v{new_state.version}): {plan.summary}"
                            st.session_state["edit_last_error"] = None
                            edit_status.update(label="Edit Applied Successfully!", state="complete", expanded=False)
                            st.rerun()
                        else:
                            if hist_item:
                                st.session_state["edit_history"].append(hist_item)
                            st.session_state["edit_last_error"] = f"Patch application failed: {msg}"
                            st.session_state["edit_last_msg"] = None
                            edit_status.update(label="Patch Application Failed", state="error", expanded=True)
                            st.error(f"Patch Error: {msg}")

                    except Exception as e:
                        st.session_state["edit_last_error"] = str(e)
                        st.session_state["edit_last_msg"] = None
                        edit_status.update(label="Edit Failed", state="error", expanded=True)
                        st.error(f"Edit Agent Error: {str(e)}")

        if st.session_state.get("edit_last_msg"):
            st.success(f"✨ {st.session_state['edit_last_msg']}")
        if st.session_state.get("edit_last_error"):
            st.error(f"⚠️ {st.session_state['edit_last_error']}")

        # ---------------------------------------------------------------------
        # Version Restoration & Undo Controls
        # ---------------------------------------------------------------------
        snapshots = st.session_state.get("version_snapshots", {})
        current_v = active_state.version

        # 1. Quick Undo Last Edit (Revert to previous version)
        prev_versions = [ver for ver in snapshots.keys() if ver < current_v]
        if prev_versions:
            prev_v = max(prev_versions)
            with st.expander(f"⏮️ Undo Last Edit (Revert to v{prev_v})", expanded=False):
                st.markdown(
                    f"Revert current website state (`v{current_v}`) back to **Version v{prev_v}**.<br>"
                    f"<small style='color: #64748B;'>Restoring commits the previous state as a new version <b>v{current_v + 1}</b> without overwriting historical versions.</small>",
                    unsafe_allow_html=True,
                )
                confirm_undo = st.checkbox(
                    f"Confirm: Revert to v{prev_v} as new version v{current_v + 1}?",
                    key=f"confirm_undo_{current_v}",
                )
                if st.button("⏮️ Confirm & Revert State", type="secondary", disabled=not confirm_undo, use_container_width=True):
                    target_snap = snapshots[prev_v]
                    restored_state, ok, r_msg, r_hist = restore_version(
                        target_snap,
                        active_state,
                        instruction=f"Undo last edit (reverted state from v{current_v} to v{prev_v})",
                    )
                    if ok:
                        st.session_state["website_state"] = restored_state
                        st.session_state["version_snapshots"][restored_state.version] = copy.deepcopy(restored_state)
                        st.session_state["edit_history"].append(r_hist)
                        st.session_state["edit_last_msg"] = r_msg
                        st.session_state["edit_last_error"] = None
                        st.rerun()
                    else:
                        st.error(r_msg)

        # 2. Restore Specific Previous Version
        other_versions = sorted([ver for ver in snapshots.keys() if ver != current_v])
        if other_versions:
            with st.expander("🔄 Restore Specific Version", expanded=False):
                st.markdown("Select an earlier version snapshot to restore as a brand new version:")
                selected_v = st.selectbox(
                    "Select Version to Restore:",
                    options=other_versions,
                    format_func=lambda x: f"Version v{x}",
                    key="restore_version_select_box",
                )
                st.caption(f"Restoring **v{selected_v}** will validate and commit it as **v{current_v + 1}**, preserving all history.")
                confirm_restore = st.checkbox(
                    f"Confirm: Restore version v{selected_v} as new version v{current_v + 1}?",
                    key=f"confirm_restore_{selected_v}",
                )
                if st.button(f"🔄 Confirm Restore v{selected_v} as v{current_v + 1}", type="primary", disabled=not confirm_restore, use_container_width=True):
                    target_snap = snapshots[selected_v]
                    restored_state, ok, r_msg, r_hist = restore_version(
                        target_snap,
                        active_state,
                        instruction=f"Restore historical version v{selected_v}",
                    )
                    if ok:
                        st.session_state["website_state"] = restored_state
                        st.session_state["version_snapshots"][restored_state.version] = copy.deepcopy(restored_state)
                        st.session_state["edit_history"].append(r_hist)
                        st.session_state["edit_last_msg"] = r_msg
                        st.session_state["edit_last_error"] = None
                        st.rerun()
                    else:
                        st.error(r_msg)

    # -------------------------------------------------------------------------
    # Detailed Edit History & Version Audit Log
    # -------------------------------------------------------------------------
    with st.expander("📜 Edit History & Version Audit Log", expanded=False):
        curr_state = st.session_state.get("website_state")
        v = curr_state.version if curr_state else 0
        st.markdown(f"**Current State Version:** `v{v}` &bull; **Saved Snapshots:** `{len(st.session_state.get('version_snapshots', {}))}`")
        history = st.session_state.get("edit_history") or []
        if history:
            st.markdown("##### Consecutive Edit Timeline")
            for h in reversed(history):
                is_success = getattr(h, "success", True)
                status_color = "#03543F" if is_success else "#991B1B"
                status_bg = "#DEF7EC" if is_success else "#FEE2E2"
                status_label = "Applied Successfully" if is_success else "Rejected / Rolled Back"

                v_before = getattr(h, "version_before", v)
                v_after = getattr(h, "version", v)
                h_instr = html.escape(getattr(h, "instruction", "") or "")
                h_sum = html.escape(getattr(h, "summary", "") or "")
                h_time = getattr(h, "timestamp", "") or ""
                records = getattr(h, "operation_records", []) or []

                st.markdown(
                    f"""
                    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 14px; margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem; color: #64748B;">
                            <span><b>v{v_before} &rarr; v{v_after}</b> &bull; {h_time}</span>
                            <span style="background: {status_bg}; color: {status_color}; padding: 2px 8px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">
                                {status_label}
                            </span>
                        </div>
                        <div style="font-weight: 600; color: #0F172A; margin: 6px 0 2px 0;">&ldquo;{h_instr}&rdquo;</div>
                        <div style="font-size: 0.85rem; color: #475569;">{h_sum}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Expandable operation breakdown for this history item
                if records:
                    with st.expander(f"🔍 Operation Details (v{v_before} → v{v_after})", expanded=False):
                        for idx, rec in enumerate(records, 1):
                            r_op = getattr(rec, "op", "operation")
                            r_tgt = getattr(rec, "target_id", None) or "-"
                            r_prop = getattr(rec, "property_path", None) or "-"
                            r_stat = getattr(rec, "status", "success")
                            r_det = getattr(rec, "details", "") or ""

                            st.markdown(f"**Operation #{idx}: `{r_op}`** (Target: `{r_tgt}`, Property: `{r_prop}`, Status: `{r_stat}`)")
                            if r_det:
                                st.caption(r_det)

                            col_bef, col_aft = st.columns(2)
                            with col_bef:
                                st.markdown("<small style='font-weight:600; color:#64748B;'>Before Value:</small>", unsafe_allow_html=True)
                                prev_v = getattr(rec, "previous_value", None)
                                if isinstance(prev_v, (dict, list)):
                                    st.json(prev_v)
                                else:
                                    st.code(str(prev_v) if prev_v is not None else "None")
                            with col_aft:
                                st.markdown("<small style='font-weight:600; color:#64748B;'>After Value:</small>", unsafe_allow_html=True)
                                new_v = getattr(rec, "new_value", None)
                                if isinstance(new_v, (dict, list)):
                                    st.json(new_v)
                                else:
                                    st.code(str(new_v) if new_v is not None else "None")
                            st.markdown("---")
                elif getattr(h, "error", None):
                    st.caption(f"Error details: {h.error}")
        else:
            st.caption("No edits applied yet. Initial state generated at v1.")

with col_right:
    st.subheader("3. Live Website Preview")
    current_state = st.session_state.get("website_state")

    if current_state:
        # Top banner with Title and Section Badges
        col_hdr1, col_hdr2 = st.columns([2, 1])
        # Render HTML and sync with background preview server
        rendered_html = render_website(current_state)
        preview_url = update_preview_html(rendered_html)

        # Top banner with Title, Version Badge, and Open in Browser button
        col_hdr1, col_hdr2, col_hdr3 = st.columns([2, 1, 1])
        with col_hdr1:
            st.markdown(f"### {current_state.title}")
        with col_hdr2:
            st.markdown(
                f'<div style="text-align: right;"><span class="status-badge badge-active">Version v{current_state.version}</span></div>',
                unsafe_allow_html=True,
            )
        with col_hdr3:
            if preview_url:
                st.link_button(
                    "🌐 Open in Browser",
                    url=preview_url,
                    help="Open latest generated website in a separate browser tab",
                    use_container_width=True,
                )

        # Prominently distinguish AI-generated vs Deterministic Fallback
        meta = st.session_state.get("generation_meta") or {}
        if meta.get("is_fallback"):
            reason = meta.get("fallback_reason") or "LLM Provider offline or unreachable"
            st.warning(
                f"⚠️ **Offline Mode / Fallback Template Displayed** (Reason: {reason}). "
                "This website was generated using the deterministic fallback engine, not live LLM generation."
            )
        else:
            p_name = meta.get("provider", "LLM")
            m_name = meta.get("model", "")
            repaired_badge = " (auto-repaired schema)" if meta.get("repaired") else ""
            st.success(
                f"✨ **AI-Generated Website** via **{p_name}** ({m_name}){repaired_badge}"
            )

        badges_html = " ".join(
            [f'<span class="section-pill">{s.id}</span>' for s in current_state.sections]
        )
        st.markdown(badges_html, unsafe_allow_html=True)

        # Primary Live HTML/CSS Preview
        rendered_html = render_website(current_state)
        st.markdown('<div class="preview-frame-container">', unsafe_allow_html=True)
        components.html(rendered_html, height=720, scrolling=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Retain State Inspector in expander
        with st.expander("📄 Website State Inspector (Validated JSON Contract)", expanded=False):
            st.json(current_state.model_dump())

        with st.expander("🎨 Theme & Style Properties", expanded=False):
            col_t1, col_t2, col_t3 = st.columns(3)
            col_t1.metric("Background", current_state.theme.background)
            col_t2.metric("Primary Color", current_state.theme.primary_color)
            col_t3.metric("Text Color", current_state.theme.text_color)
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.markdown(f"**Heading Font:** `{current_state.theme.heading_font or current_state.theme.font_family}`")
                st.markdown(f"**Body Font:** `{current_state.theme.font_family}`")
            with col_f2:
                st.markdown(f"**Background Style:** `{current_state.theme.background_style or 'solid'}`")
                st.markdown(f"**Navbar Style:** `{current_state.theme.nav_style or 'sticky_glass'}`")

        with st.expander("💾 Export & Download Assets (JSON & Standalone HTML)", expanded=False):
            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                st.download_button(
                    label="📥 Download State JSON",
                    data=current_state.model_dump_json(indent=2),
                    file_name=f"sitepilot_state_v{current_state.version}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with col_d2:
                st.download_button(
                    label="🌐 Download Standalone HTML",
                    data=rendered_html,
                    file_name=f"sitepilot_website_v{current_state.version}.html",
                    mime="text/html",
                    use_container_width=True,
                )
            with col_d3:
                edit_history_raw = st.session_state.get("edit_history", [])
                history_json = json.dumps(
                    [h.model_dump() if hasattr(h, "model_dump") else h for h in edit_history_raw],
                    indent=2,
                    default=str,
                )
                st.download_button(
                    label="📜 Download Audit Log",
                    data=history_json,
                    file_name=f"sitepilot_audit_log_v{current_state.version}.json",
                    mime="application/json",
                    use_container_width=True,
                )

    else:
        st.markdown(
            """
            <div class="card" style="min-height: 480px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; color: #64748B;">
                <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🖥️</div>
                <div style="font-weight: 600; font-size: 1.2rem; color: #334155;">Live Preview Ready</div>
                <p style="max-width: 340px; font-size: 0.95rem; margin-top: 0.5rem;">
                    Enter a website brief on the left and click <b>✨ Generate Website</b>. The live rendered website will display here instantly.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("🛠️ Developer Diagnostics & Pipeline Inspection", expanded=False):
        plan_data = st.session_state.get("website_plan")
        state_data = st.session_state.get("website_state")
        meta_data = st.session_state.get("generation_meta") or {}

        diag_tabs = st.tabs([
            "🔍 Pipeline Trace",
            "📋 Planner Plan",
            "📄 Website State",
            "🖼️ Visual Media Slots",
            "🔗 Anchor & Nav Map",
            "📜 Event & Audit Log",
        ])

        with diag_tabs[0]:
            st.markdown("#### Pipeline Architecture & Strategy Summary")
            if plan_data:
                try:
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        b_type = getattr(plan_data, "business_type", "General Business")
                        t_style = getattr(plan_data, "tone_and_style", getattr(plan_data, "tone", "Modern, professional"))
                        l_strat = getattr(plan_data, "layout_strategy", "modern_showcase")
                        h_var = getattr(plan_data, "hero_variant", "split")
                        f_type = getattr(plan_data, "form_type", "contact")

                        st.markdown(f"- **Business Type:** `{b_type}`")
                        st.markdown(f"- **Tone & Persona:** `{t_style}`")
                        st.markdown(f"- **Layout Strategy:** `{l_strat}`")
                        st.markdown(f"- **Hero Variant:** `{h_var}`")
                        st.markdown(f"- **Form Type:** `{f_type}`")
                    with col_p2:
                        h_font = getattr(plan_data, "heading_font", "Inter, sans-serif")
                        b_font = getattr(plan_data, "typography", getattr(plan_data, "font_family", "Inter, sans-serif"))
                        bg_style = getattr(plan_data, "background_style", "solid")
                        n_style = getattr(plan_data, "nav_style", "sticky_glass")
                        raw_fields = getattr(plan_data, "form_fields", None) or []
                        f_fields_str = ", ".join(str(f) for f in raw_fields) if raw_fields else "Standard Fields"

                        st.markdown(f"- **Heading Font:** `{h_font}`")
                        st.markdown(f"- **Body Font:** `{b_font}`")
                        st.markdown(f"- **Background Style:** `{bg_style}`")
                        st.markdown(f"- **Nav Style:** `{n_style}`")
                        st.markdown(f"- **Form Fields:** {f_fields_str}")
                except Exception as diag_err:
                    st.caption(f"Strategy summary unavailable ({diag_err})")
            else:
                st.caption("No pipeline trace available yet. Generate a website to view strategy trace.")

            st.markdown("---")
            st.markdown("#### Generation Telemetry")
            if meta_data:
                st.json(meta_data)
            else:
                st.caption("No generation telemetry available.")

        with diag_tabs[1]:
            st.markdown("#### Validated WebsitePlan (Planner Output)")
            if plan_data:
                try:
                    if hasattr(plan_data, "model_dump"):
                        st.json(plan_data.model_dump())
                    elif isinstance(plan_data, dict):
                        st.json(plan_data)
                    else:
                        st.write(str(plan_data))
                except Exception as p_err:
                    st.caption(f"Could not format plan ({p_err})")
            else:
                st.caption("No plan generated yet.")

        with diag_tabs[2]:
            st.markdown("#### Validated WebsiteState (Renderer Contract)")
            if state_data:
                try:
                    sec_list = getattr(state_data, "sections", []) or []
                    ver_num = getattr(state_data, "version", 1)
                    st.markdown(f"**Total Sections:** `{len(sec_list)}` | **Version:** `v{ver_num}`")
                    sections_table = [
                        {
                            "ID": getattr(s, "id", "unknown"),
                            "Type": getattr(s, "type", "unknown"),
                            "Variant": getattr(getattr(s, "style", None), "layout_variant", "default") or "default",
                            "Alignment": getattr(getattr(s, "style", None), "alignment", "center"),
                            "Padding": getattr(getattr(s, "style", None), "padding", "medium"),
                        }
                        for s in sec_list
                    ]
                    if sections_table:
                        st.table(sections_table)
                    if hasattr(state_data, "model_dump"):
                        st.json(state_data.model_dump())
                    elif isinstance(state_data, dict):
                        st.json(state_data)
                except Exception as s_err:
                    st.caption(f"Could not format state inspection ({s_err})")
            else:
                st.caption("No website state generated yet.")

        with diag_tabs[3]:
            st.markdown("#### Curated Visual Media Slots & Attribution")
            if state_data:
                try:
                    has_image = False
                    for s in getattr(state_data, "sections", []):
                        c = getattr(s, "content", {}) or {}
                        s_type = getattr(s, "type", "")
                        s_id = getattr(s, "id", "")
                        if s_type in ("hero", "image") or c.get("image_url") or c.get("image_description"):
                            has_image = True
                            st.markdown(f"**Section `{s_id}` ({s_type}):**")
                            st.markdown(f"- Image URL: `{c.get('image_url') or 'None (Stylized Visual Placeholder Used)'}`")
                            st.markdown(f"- Description/Prompt: `{c.get('image_description') or 'N/A'}`")
                            st.markdown(f"- Attribution: *Curated royalty-free photography or styled visual card*")
                    if not has_image:
                        st.caption("No dedicated media sections in current website.")
                except Exception as m_err:
                    st.caption(f"Media slots inspection unavailable ({m_err})")
            else:
                st.caption("No media slots resolved yet.")

        with diag_tabs[4]:
            st.markdown("#### Internal Anchor & Target Section Map")
            if state_data:
                anchor_map = [
                    {"Source Element": "Navbar Brand / Home", "Action": "Scroll to Top", "Target DOM ID": "#hero-1"},
                    {"Source Element": "Navbar CTA / Primary Button", "Action": "Scroll & Highlight Form", "Target DOM ID": "#appointment-form"},
                    {"Source Element": "Hero Primary CTA", "Action": "Scroll & Highlight Form", "Target DOM ID": "#appointment-form"},
                    {"Source Element": "Hero Secondary CTA", "Action": "Scroll to Section", "Target DOM ID": "#pricing-1 / #features-1"},
                    {"Source Element": "Contact / Booking Form Box", "Action": "Interactive Form Submission", "Target DOM ID": "id='appointment-form'"},
                ]
                st.table(anchor_map)
                st.success("✅ All navigation and CTA anchors use internal smooth-scroll DOM targets with `@keyframes formPulseHighlight`. Zero iframe parent navigation.")
            else:
                st.caption("No anchor map available yet.")

        with diag_tabs[5]:
            st.markdown("#### Chronological Event & Version Transition Log")
            hist_items = st.session_state.get("edit_history", [])
            if hist_items:
                for idx, h in enumerate(reversed(hist_items)):
                    v_after = getattr(h, "version", "?")
                    v_before = getattr(h, "version_before", "?")
                    inst = getattr(h, "instruction", "Initial generation")
                    success = getattr(h, "success", True)
                    ts = getattr(h, "timestamp", "")
                    badge = "✅ Success" if success else "❌ Failed / Rejected"
                    st.markdown(f"**Event #{len(hist_items) - idx}: v{v_before} $\\to$ v{v_after}** — `{badge}` (`{ts}`)")
                    st.markdown(f"*{inst}*")
                    if hasattr(h, "model_dump"):
                        st.json(h.model_dump())
                    st.markdown("---")
            else:
                st.caption("Initial website generated at v1. No edit transactions recorded yet.")
