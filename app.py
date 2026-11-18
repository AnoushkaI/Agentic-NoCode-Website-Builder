"""
SitePilot AI — Agentic No-Code Website Builder
Phase 1: Project Foundation & Configurable LLM Provider Connection Shell
"""

import streamlit as st
from src.config import get_llm_config, SUPPORTED_PROVIDERS
from src.providers.factory import get_provider, test_provider_connectivity

# Set Streamlit page configuration
st.set_page_config(
    page_title="SitePilot AI - Website Builder",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom header styling
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

    # Provider selection
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

    # Load active configuration for selected provider
    active_config = get_llm_config(provider_override=selected_provider)

    st.markdown("---")
    st.markdown(f"**Model:** `{active_config.model}`")
    st.markdown(f"**Base URL:** `{active_config.base_url}`")
    st.markdown(f"**API Key:** `{active_config.masked_api_key}`")
    st.markdown(f"**Configured:** {'✅ Ready' if active_config.is_configured else '⚠️ Missing Key / Unconfigured'}")

    st.markdown("---")

    # Connectivity Test Button
    test_clicked = st.button("🔌 Test Provider Connection", use_container_width=True, type="primary")

    if test_clicked:
        with st.spinner(f"Pinging {active_config.provider} ({active_config.model})..."):
            provider_instance = get_provider(selected_provider)
            test_result = provider_instance.test_connection()

            if test_result.success:
                st.success(f"**Success!** {test_result.message}")
                if test_result.latency_ms:
                    st.caption(f"⏱ Latency: {test_result.latency_ms:.1f}ms")
                if test_result.sample_response:
                    st.info(f"💬 Sample Response: {test_result.sample_response}")
            else:
                st.error(f"**Connection Failed:** {test_result.message}")
                if test_result.troubleshooting_tip:
                    st.warning(f"💡 **Troubleshooting Tip:**\n{test_result.troubleshooting_tip}")

    st.markdown("---")
    st.caption("SitePilot AI — Workstream B Specification")
    st.caption("Version 1.0 (Phase 1: Foundation & Connectivity)")

# Main Layout
col_left, col_right = st.columns([1, 1], gap="medium")

with col_left:
    st.subheader("1. Website Brief")
    sample_brief = "Create a modern landing page for a fitness studio with pricing, testimonials, and a contact form."
    brief_input = st.text_area(
        "Describe the website you want to generate:",
        value=sample_brief,
        height=120,
        disabled=True,
        help="Will be enabled in Phase 2 (Planner & Generator).",
    )
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        st.button("✨ Generate Website", disabled=True, use_container_width=True)
    with col_info:
        st.markdown(
            '<span class="status-badge badge-pending">Phase 2: Generator</span> Coming next',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("2. Conversational Edit")
    st.text_input(
        "Request a change (e.g., 'Make the hero darker' or 'Change CTA to Book a Trial'):",
        disabled=True,
        help="Will be enabled in Phase 4 (Conversational Edit Agent & Patch Engine).",
    )
    st.button("💬 Apply Edit", disabled=True)

    with st.expander("📜 Edit History & Version Log", expanded=False):
        st.info("Current Version: v0 (No website generated yet)")

with col_right:
    st.subheader("3. Live Website Preview")
    st.markdown(
        """
        <div class="card" style="min-height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; color: #64748B;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">🖥️</div>
            <div style="font-weight: 600; font-size: 1.1rem; color: #334155;">Preview Canvas Ready</div>
            <p style="max-width: 320px; font-size: 0.9rem; margin-top: 0.5rem;">
                Phase 1 verified provider connectivity. Phase 3 will render validated Pydantic WebsiteState into live components here.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("🛠️ Developer Diagnostics / Architecture Inspector", expanded=True):
        st.markdown("**Active Provider Diagnostics:**")
        st.json({
            "provider": active_config.provider,
            "model": active_config.model,
            "base_url": active_config.base_url,
            "is_configured": active_config.is_configured,
            "masked_api_key": active_config.masked_api_key,
            "timeout_seconds": active_config.timeout,
            "temperature": active_config.temperature,
            "phase": "Phase 1 - Provider Connectivity & Project Foundation",
        })
