"""
SitePilot AI — Agentic No-Code Website Builder
Phase 3: Predefined HTML/CSS Renderer & Live Streamlit Preview
"""

import streamlit as st
import streamlit.components.v1 as components
from src.config import get_llm_config, SUPPORTED_PROVIDERS
from src.providers.factory import get_provider
from src.planner import plan_website
from src.generator import generate_website_json, WebsiteGenerationError
from src.renderer import render_website

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

    # Placeholder for Phase 4 Edit Agent
    st.subheader("2. Conversational Edit")
    st.text_input(
        "Request a change (e.g., 'Make the hero darker' or 'Change CTA to Book a Trial'):",
        disabled=True,
        help="Will be enabled in Phase 4 (Conversational Edit Agent & Patch Engine).",
    )
    col_edit_btn, col_edit_badge = st.columns([1, 2])
    with col_edit_btn:
        st.button("💬 Apply Edit", disabled=True)
    with col_edit_badge:
        st.markdown(
            '<span class="status-badge badge-pending">Phase 4: Edit Agent</span> Coming next',
            unsafe_allow_html=True,
        )

    with st.expander("📜 Edit History & Version Log", expanded=False):
        curr_state = st.session_state.get("website_state")
        v = curr_state.version if curr_state else 0
        st.info(f"Current Version: v{v} (Initial state created upon generation)")

with col_right:
    st.subheader("3. Live Website Preview")
    current_state = st.session_state.get("website_state")

    if current_state:
        # Top banner with Title and Section Badges
        col_hdr1, col_hdr2 = st.columns([2, 1])
        with col_hdr1:
            st.markdown(f"### {current_state.title}")
        with col_hdr2:
            st.markdown(
                f'<div style="text-align: right;"><span class="status-badge badge-active">Version v{current_state.version}</span></div>',
                unsafe_allow_html=True,
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
            st.caption(f"Font Family: {current_state.theme.font_family}")

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

    with st.expander("🛠️ Developer Diagnostics / Planner & Generation Log", expanded=False):
        st.markdown("**Latest Website Plan:**")
        plan_data = st.session_state.get("website_plan")
        if plan_data:
            st.json(plan_data.model_dump())
        else:
            st.caption("No plan generated yet.")

        st.markdown("**Generation Metadata:**")
        meta_data = st.session_state.get("generation_meta")
        if meta_data:
            st.json(meta_data)
        else:
            st.caption("No generation metadata yet.")
