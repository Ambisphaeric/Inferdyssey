"""Specs page — the abstraction chain.

Hardware → Repos Downloaded → Capabilities → Trainable Models → Hypothesis Builder
"""

import streamlit as st
from core.hardware import HardwareProfile
from core.repos import list_available, list_cloned, get_all_capabilities
from core.trainer import CONFIGS
from core.agent import Agent


def render():
    st.header("Specs")
    st.caption("Hardware → Repos → Capabilities → Models → Hypotheses")

    hw: HardwareProfile = st.session_state.hardware

    # -----------------------------------------------------------------------
    # 1. HARDWARE
    # -----------------------------------------------------------------------
    st.subheader("1. Hardware Detected")
    cols = st.columns(4)
    cols[0].metric("Chip", hw.chip.replace("Apple ", ""))
    cols[1].metric("Unified Memory", f"{hw.memory_gb} GB")
    cols[2].metric("MLX", hw.mlx_device.upper())
    cols[3].metric("Est. Max Train", f"~{hw.max_trainable_params_m}M params")

    if not hw.is_apple_silicon:
        st.warning("Not running on Apple Silicon — MLX training may not work.")

    st.divider()

    # -----------------------------------------------------------------------
    # 2. REPOSITORIES
    # -----------------------------------------------------------------------
    st.subheader("2. Repositories")
    repos = list_available()
    cloned = [r for r in repos if r.is_cloned]
    not_cloned = [r for r in repos if not r.is_cloned]

    if cloned:
        st.write(f"**{len(cloned)} cloned** | {len(not_cloned)} available")
        for repo in cloned:
            st.write(f"- ✅ **{repo.name}** (`{repo.stack_layer}`) — {repo.description[:80]}")
    else:
        st.info("No repos cloned yet. Go to **Settings** to clone frontier repos.")

    if not_cloned:
        with st.expander(f"Available to clone ({len(not_cloned)})"):
            for repo in not_cloned:
                st.write(f"- ⬜ **{repo.name}** (`{repo.stack_layer}`) — {repo.description[:80]}")

    st.divider()

    # -----------------------------------------------------------------------
    # 3. CAPABILITIES
    # -----------------------------------------------------------------------
    st.subheader("3. System Capabilities")
    caps = get_all_capabilities(hw.memory_gb)

    if caps:
        # Flatten to unique capabilities
        all_caps = set()
        for repo_caps in caps.values():
            all_caps.update(repo_caps)

        # Always have local training
        all_caps.add("local_mlx_training")

        # Display as tags
        tag_cols = st.columns(min(len(all_caps), 4))
        for i, cap in enumerate(sorted(all_caps)):
            tag_cols[i % len(tag_cols)].success(cap.replace("_", " ").title())

        # Per-repo breakdown
        with st.expander("Capability breakdown by repo"):
            for repo_name, repo_caps in caps.items():
                st.write(f"**{repo_name}:** {', '.join(repo_caps)}")
    else:
        st.write("**Local MLX Training** — always available on Apple Silicon")
        st.info("Clone repos from Settings to unlock more capabilities.")

    st.divider()

    # -----------------------------------------------------------------------
    # 4. TRAINABLE MODELS
    # -----------------------------------------------------------------------
    st.subheader("4. Trainable Models")
    st.caption("Models you can train from scratch on your hardware.")

    for name, cfg in CONFIGS.items():
        params_m = cfg.n_params / 1_000_000
        mem_needed = (cfg.n_params * 4 * 3) / (1024 ** 3)  # ~3x for training
        feasible = hw.memory_gb >= mem_needed * 1.5  # leave headroom

        icon = "✅" if feasible else "⚠️"
        st.write(
            f"{icon} **{name}** — ~{params_m:.0f}M params "
            f"({cfg.n_layers}L, {cfg.n_heads}H, {cfg.d_model}D) "
            f"| ~{mem_needed:.1f} GB needed"
        )

    st.divider()

    # -----------------------------------------------------------------------
    # 5. HYPOTHESIS BUILDER
    # -----------------------------------------------------------------------
    st.subheader("5. Hypothesis Builder")

    hypothesis = st.text_area(
        "Describe your experiment hypothesis",
        placeholder=(
            "Example: What if we increase the number of attention heads from 8 to 12 "
            "while keeping total parameters constant? Does this improve validation loss "
            "on character-level language modeling?"
        ),
        height=100,
    )

    # Cross-repo flag
    if cloned and len(cloned) >= 2:
        cross_repo = st.multiselect(
            "Repos involved (select 2+ for cross-repo experiments)",
            [r.name for r in cloned],
        )
        if len(cross_repo) >= 2:
            st.info(f"Cross-repo experiment: will coordinate changes across **{', '.join(cross_repo)}**")

    if st.button("Generate Hypotheses with AI", disabled=not st.session_state.get("api_key")):
        agent = Agent(
            api_key=st.session_state.get("api_key", ""),
            model=st.session_state.get("agent_model"),
        )

        hw_summary = f"{hw.chip}, {hw.memory_gb}GB, MLX {hw.mlx_device}"
        repo_data = [
            {"name": r.name, "description": r.description, "capabilities": r.capabilities}
            for r in cloned
        ]
        # Add base training capability
        repo_data.append({
            "name": "InferDyssey (local)",
            "description": "MLX GPT-2 training from scratch (10M-124M params)",
            "capabilities": ["local_training", "autoresearch", "benchmarking"],
        })

        with st.spinner("Agent generating hypotheses..."):
            suggestions = agent.suggest_hypotheses(hw_summary, repo_data)
        st.markdown(suggestions)

    if not st.session_state.get("api_key"):
        st.caption("Set your OpenRouter API key in Settings to enable AI hypothesis generation.")
