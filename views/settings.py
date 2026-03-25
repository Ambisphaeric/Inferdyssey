"""Settings page — API keys, hardware, model selection, repo management."""

import streamlit as st
from core.hardware import detect
from core.models import fetch_models, get_model_display, FAVORITES


def render():
    st.header("Settings")

    hw = st.session_state.hardware

    # --- API Key ---
    st.subheader("API Configuration")
    api_key = st.text_input(
        "OpenRouter API Key",
        value=st.session_state.get("api_key", ""),
        type="password",
        help="Get yours at https://openrouter.ai/keys — Gemini Flash Lite is nearly free.",
    )
    if api_key != st.session_state.get("api_key", ""):
        st.session_state.api_key = api_key
        st.success("API key saved for this session.")

    # --- Model selection (fetched from OpenRouter) ---
    st.subheader("Default Model (Workspaces & Specs)")
    st.caption("Learn page has its own per-chat model selector.")

    # Fetch/cache models
    if "openrouter_models" not in st.session_state:
        with st.spinner("Fetching available models from OpenRouter..."):
            st.session_state.openrouter_models = fetch_models()

    models = st.session_state.openrouter_models
    model_ids = [m.id for m in models]
    display_map = get_model_display(models)

    # Find current selection index
    current = st.session_state.get("agent_model", FAVORITES[0])
    idx = model_ids.index(current) if current in model_ids else 0

    model = st.selectbox(
        "Model",
        model_ids,
        index=idx,
        format_func=lambda mid: display_map.get(mid, mid),
        label_visibility="collapsed",
        help=f"{len(model_ids)} models available. ★ = favorites.",
    )
    st.session_state.agent_model = model

    # Show selected model info
    selected = next((m for m in models if m.id == model), None)
    if selected:
        info_parts = []
        if selected.context_length:
            info_parts.append(f"Context: {selected.context_length:,} tokens")
        if selected.pricing_prompt > 0:
            info_parts.append(f"Input: ${selected.pricing_prompt:.2f}/M tokens")
        if selected.pricing_completion > 0:
            info_parts.append(f"Output: ${selected.pricing_completion:.2f}/M tokens")
        if info_parts:
            st.caption(" | ".join(info_parts))

    col_refresh, col_status = st.columns([1, 2])
    if col_refresh.button("Refresh Models"):
        with st.spinner("Fetching..."):
            st.session_state.openrouter_models = fetch_models(use_cache=False)
        st.rerun()

    if st.session_state.get("api_key"):
        col_status.success(f"Connected — using **{model}**")
    else:
        col_status.warning("No API key set.")

    st.divider()

    # --- Hardware ---
    st.subheader("Hardware Profile")
    col1, col2, col3 = st.columns(3)
    col1.metric("Chip", hw.chip)
    col2.metric("Memory", f"{hw.memory_gb} GB")
    col3.metric("MLX Device", hw.mlx_device)

    col4, col5, col6 = st.columns(3)
    col4.metric("CPU Cores", hw.cpu_cores)
    col5.metric("GPU Cores", hw.gpu_cores or "N/A")
    col6.metric("Max Trainable", f"~{hw.max_trainable_params_m}M params")

    if st.button("Re-detect Hardware"):
        st.session_state.hardware = detect()
        st.rerun()

    st.divider()

    # --- Repo Management ---
    st.subheader("Repository Management")
    st.caption("Clone frontier repos to enable experiments and learning context.")

    from core.repos import list_available, clone_repo, remove_repo, update_repo

    repos = list_available()
    for repo in repos:
        with st.expander(
            f"{'✅' if repo.is_cloned else '⬜'} **{repo.name}** — {repo.stack_layer}",
            expanded=False,
        ):
            st.write(repo.description)
            st.write(f"**Maintainer:** {repo.maintainer}")
            st.write(f"**Capabilities:** {', '.join(repo.capabilities)}")
            st.write(f"**Min memory:** {repo.min_memory_gb} GB")
            st.write(f"**Models:** {', '.join(repo.models)}")

            if repo.is_cloned:
                st.write(f"**Branch:** `{repo.current_branch}`")
                st.write(f"**Last commit:** `{repo.last_commit}`")
                c1, c2 = st.columns(2)
                if c1.button("Update", key=f"update_{repo.name}"):
                    ok, msg = update_repo(repo.name)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                if c2.button("Remove", key=f"remove_{repo.name}"):
                    ok, msg = remove_repo(repo.name)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                can_run = hw.memory_gb >= repo.min_memory_gb
                if not can_run:
                    st.warning(f"Your {hw.memory_gb}GB may not be enough (needs {repo.min_memory_gb}GB).")
                if st.button(
                    f"Clone {repo.name}",
                    key=f"clone_{repo.name}",
                ):
                    with st.spinner(f"Cloning {repo.name}..."):
                        ok, msg = clone_repo(repo.name)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
