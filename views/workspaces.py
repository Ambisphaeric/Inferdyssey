"""Workspaces page — experiment dashboard + autoresearch control."""

import streamlit as st
import plotly.graph_objects as go
from core.trainer import CONFIGS
from core import benchmark


def render():
    st.header("Workspaces")

    tab1, tab2 = st.tabs(["Run Experiment", "History"])

    # ===================================================================
    # TAB 1: Run Experiment
    # ===================================================================
    with tab1:
        st.subheader("Autoresearch Loop")
        st.caption("AI agent experiments on your training code — keeps wins, reverts losses.")

        col1, col2, col3 = st.columns(3)

        config_name = col1.selectbox(
            "Model Size",
            list(CONFIGS.keys()),
            index=1,  # default to "small"
            format_func=lambda x: f"{x} (~{CONFIGS[x].n_params / 1e6:.0f}M params)",
        )

        time_budget = col2.slider(
            "Time budget per iteration (seconds)",
            min_value=30,
            max_value=600,
            value=120,
            step=30,
        )

        num_iters = col3.number_input(
            "Number of iterations",
            min_value=1,
            max_value=50,
            value=5,
        )

        # Show config details
        cfg = CONFIGS[config_name]
        st.write(
            f"**Config:** {cfg.n_layers} layers, {cfg.n_heads} heads, "
            f"{cfg.d_model} dim, {cfg.d_ff} FFN dim | "
            f"~{cfg.n_params / 1e6:.0f}M params | "
            f"Estimated total time: ~{(time_budget * (num_iters + 1)) / 60:.0f} min"
        )

        api_key = st.session_state.get("api_key", "")
        has_key = bool(api_key)

        if not has_key:
            st.warning("Set your OpenRouter API key in **Settings** to enable AI-driven experiments. You can still run a baseline without it.")

        # --- Run controls ---
        run_col1, run_col2 = st.columns([1, 1])

        if run_col1.button(
            "Start Autoresearch" if has_key else "Run Baseline Only",
            type="primary",
            use_container_width=True,
        ):
            _run_experiment(config_name, time_budget, num_iters if has_key else 0, api_key)

        if run_col2.button("Quick Baseline (60s)", use_container_width=True):
            _run_experiment(config_name, 60, 0, "")

    # ===================================================================
    # TAB 2: History
    # ===================================================================
    with tab2:
        _render_history()


def _run_experiment(config_name: str, time_budget: int, num_iters: int, api_key: str):
    """Run training / autoresearch and display live progress."""
    from core.trainer import train
    from core.agent import Agent
    from core.autoresearch import AutoresearchLoop
    from core.hardware import HardwareProfile
    import time

    hw: HardwareProfile = st.session_state.hardware

    progress_bar = st.progress(0, text="Starting...")
    status = st.empty()
    chart_placeholder = st.empty()
    results_placeholder = st.container()

    losses = []
    tok_speeds = []
    labels = []

    if num_iters == 0:
        # Baseline only
        status.info("Running baseline training...")

        def cb(info):
            step = info["step"]
            progress_bar.progress(
                min(info["elapsed"] / time_budget, 0.99),
                text=f"Step {step} | Loss {info['train_loss']:.4f} | {info['tok_per_sec']:.0f} tok/s",
            )

        result = train(
            config_name=config_name,
            data_path="data/shakespeare.txt",
            max_time_seconds=time_budget,
            progress_callback=cb,
        )

        progress_bar.progress(1.0, text="Done!")

        benchmark.log_result(
            val_loss=result.val_loss,
            train_loss=result.train_loss,
            tok_per_sec=result.tok_per_sec,
            peak_memory_mb=result.peak_memory_mb,
            wall_time_s=result.wall_time_s,
            steps=result.steps,
            config_name=config_name,
            n_params=result.n_params,
            hardware=hw.chip,
            summary="baseline",
        )

        st.success(
            f"Baseline complete: val_loss={result.val_loss:.4f}, "
            f"{result.tok_per_sec:.0f} tok/s, {result.steps} steps in {result.wall_time_s:.0f}s"
        )
        if result.checkpoint_path:
            st.info(f"Model saved to: `{result.checkpoint_path}/`")
    else:
        # Autoresearch loop
        agent = Agent(api_key=api_key, model=st.session_state.get("agent_model"))
        loop = AutoresearchLoop(
            agent=agent,
            config_name=config_name,
            data_path="data/shakespeare.txt",
            time_budget_s=time_budget,
            hardware_name=hw.chip,
        )

        for iter_result in loop.run(num_iterations=num_iters):
            i = iter_result.iteration
            total = num_iters + 1  # +1 for baseline

            progress_bar.progress(
                min((i + 1) / total, 1.0),
                text=f"Iteration {i}/{num_iters} — {iter_result.summary[:60]}",
            )

            losses.append(iter_result.val_loss)
            tok_speeds.append(iter_result.tok_per_sec)
            labels.append(f"{'baseline' if i == 0 else f'iter {i}'}")

            # Update chart
            fig = go.Figure()
            colors = ["green" if iter_result.improved else "red" for _ in losses]
            fig.add_trace(go.Bar(x=labels, y=losses, marker_color=[
                "green" if l == min(losses[:j+1]) else "gray"
                for j, l in enumerate(losses)
            ], name="Val Loss"))
            fig.update_layout(
                title="Validation Loss by Iteration",
                yaxis_title="Val Loss",
                height=300,
                margin=dict(t=40, b=20),
            )
            chart_placeholder.plotly_chart(fig, use_container_width=True)

            # Log result
            with results_placeholder:
                icon = "✅" if iter_result.improved else "❌"
                st.write(
                    f"{icon} **Iter {i}** | val_loss={iter_result.val_loss:.4f} | "
                    f"{iter_result.tok_per_sec:.0f} tok/s | {iter_result.summary}"
                )

        progress_bar.progress(1.0, text="Autoresearch complete!")
        best = min(losses) if losses else None
        if best:
            st.success(f"Best val_loss: {best:.4f} (started at {losses[0]:.4f})")


def _render_history():
    """Render experiment history from SQLite."""
    stats = benchmark.get_stats()
    if stats["total_runs"] == 0:
        st.info("No experiments yet. Run a baseline or autoresearch loop to get started.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Runs", stats["total_runs"])
    col2.metric("Best Val Loss", f"{stats['best_val_loss']:.4f}" if stats['best_val_loss'] else "N/A")
    col3.metric("Best Tok/s", f"{stats['best_tok_per_sec']:.0f}" if stats['best_tok_per_sec'] else "N/A")

    st.divider()

    history = benchmark.get_history(limit=50)
    if history:
        # Loss over time chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(len(history))),
            y=[r["val_loss"] for r in reversed(history)],
            mode="lines+markers",
            name="Val Loss",
        ))
        fig.update_layout(
            title="Validation Loss Over Time",
            xaxis_title="Run",
            yaxis_title="Val Loss",
            height=300,
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Table
        st.subheader("Run History")
        for run in history:
            with st.expander(
                f"`{run['run_id']}` | {run['summary'] or 'baseline'} | "
                f"val_loss={run['val_loss']:.4f} | {run['tok_per_sec']:.0f} tok/s"
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.write(f"**Config:** {run['config_name']}")
                c2.write(f"**Params:** {run['n_params']:,}")
                c3.write(f"**Steps:** {run['steps']}")
                c4.write(f"**Time:** {run['wall_time_s']:.0f}s")
                st.write(f"**Hardware:** {run['hardware']}")
                st.write(f"**Timestamp:** {run['timestamp']}")
                if run.get("code_diff"):
                    st.write(f"**Change:** {run['code_diff']}")
