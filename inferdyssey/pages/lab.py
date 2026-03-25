"""Lab page — hypothesis → experiment → benchmark workspace."""

import reflex as rx
from inferdyssey.state import AppState
from inferdyssey.layout import layout


def result_row(result: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(result["iteration"], size="2")),
        rx.table.cell(rx.text(result["summary"], size="2")),
        rx.table.cell(rx.text(result["val_loss"], size="2")),
        rx.table.cell(rx.text(result["tok_per_sec"], size="2")),
        rx.table.cell(
            rx.cond(
                result["improved"],
                rx.badge("improved", color_scheme="green", size="1"),
                rx.badge("no gain", color_scheme="gray", size="1"),
            ),
        ),
    )


def history_row(run: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(run.get("run_id", ""), size="1")),
        rx.table.cell(rx.text(run.get("summary", ""), size="1")),
        rx.table.cell(rx.text(run.get("val_loss", 0), size="1")),
        rx.table.cell(rx.text(run.get("tok_per_sec", 0), size="1")),
        rx.table.cell(rx.text(run.get("config_name", ""), size="1")),
        rx.table.cell(rx.text(run.get("steps", 0), size="1")),
    )


def lab_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("Lab", size="6"),
            rx.text(
                "Hypothesis → Experiment → Benchmark. Train models, run autoresearch, track results.",
                size="2",
                color="var(--gray-9)",
            ),

            # --- Hypothesis ---
            rx.card(
                rx.vstack(
                    rx.text("Hypothesis", size="3", weight="bold"),
                    rx.text_area(
                        placeholder=(
                            "Describe what you want to test. Example: 'What if we increase attention heads "
                            "from 8 to 12 while keeping total parameters constant? Does validation loss improve?'"
                        ),
                        value=AppState.hypothesis,
                        on_change=AppState.set_hypothesis,
                        rows="3",
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                ),
                width="100%",
            ),

            # --- Experiment config ---
            rx.card(
                rx.vstack(
                    rx.text("Experiment Configuration", size="3", weight="bold"),
                    rx.grid(
                        rx.vstack(
                            rx.text("Model size", size="2", color="var(--gray-9)"),
                            rx.select(
                                ["tiny", "small", "base"],
                                value=AppState.lab_model_config,
                                on_change=AppState.set_lab_model_config,
                            ),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Time budget (seconds)", size="2", color="var(--gray-9)"),
                            rx.slider(
                                default_value=[120],
                                min=30,
                                max=600,
                                step=30,
                                on_value_commit=AppState.set_lab_time_budget,
                            ),
                            rx.text(AppState.lab_time_budget.to(str), "s", size="1", color="var(--gray-9)"),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Iterations (autoresearch)", size="2", color="var(--gray-9)"),
                            rx.input(
                                value=AppState.lab_iterations.to(str),
                                on_change=AppState.set_lab_iterations,
                                type="number",
                            ),
                            spacing="1",
                        ),
                        columns="3",
                        spacing="4",
                        width="100%",
                    ),

                    rx.hstack(
                        rx.button(
                            "Run Baseline",
                            on_click=AppState.run_baseline,
                            loading=AppState.lab_running,
                            size="3",
                        ),
                        rx.button(
                            "Start Autoresearch",
                            variant="surface",
                            size="3",
                            disabled=rx.cond(AppState.api_key == "", True, AppState.lab_running),
                        ),
                        spacing="2",
                    ),

                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),

            # --- Status ---
            rx.cond(
                AppState.lab_status != "",
                rx.callout(
                    AppState.lab_status,
                    icon="flask-conical",
                    variant="surface",
                    width="100%",
                ),
            ),

            # --- Current run results ---
            rx.cond(
                AppState.lab_results.length() > 0,
                rx.card(
                    rx.vstack(
                        rx.text("Current Run", size="3", weight="bold"),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Iter"),
                                    rx.table.column_header_cell("Change"),
                                    rx.table.column_header_cell("Val Loss"),
                                    rx.table.column_header_cell("Tok/s"),
                                    rx.table.column_header_cell("Status"),
                                ),
                            ),
                            rx.table.body(
                                rx.foreach(AppState.lab_results, result_row),
                            ),
                            width="100%",
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    width="100%",
                ),
            ),

            # --- History ---
            rx.card(
                rx.vstack(
                    rx.text("Experiment History", size="3", weight="bold"),
                    rx.hstack(
                        rx.text("Total runs: ", size="2"),
                        rx.text(AppState.benchmark_stats["total_runs"].to(str), size="2", weight="bold"),
                        spacing="1",
                    ),
                    rx.cond(
                        AppState.benchmark_history.length() > 0,
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("ID"),
                                    rx.table.column_header_cell("Summary"),
                                    rx.table.column_header_cell("Val Loss"),
                                    rx.table.column_header_cell("Tok/s"),
                                    rx.table.column_header_cell("Config"),
                                    rx.table.column_header_cell("Steps"),
                                ),
                            ),
                            rx.table.body(
                                rx.foreach(AppState.benchmark_history, history_row),
                            ),
                            width="100%",
                        ),
                        rx.text("No experiments yet. Run a baseline to get started.", size="2", color="var(--gray-9)"),
                    ),
                    spacing="2",
                    width="100%",
                ),
                width="100%",
            ),

            width="100%",
            spacing="4",
        ),
    )
