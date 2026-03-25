"""Settings page — API keys, model selection, repo management."""

import reflex as rx
from inferdyssey.state import AppState
from inferdyssey.layout import layout


def repo_manage_card(repo: dict) -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.cond(
                repo["is_cloned"],
                rx.icon("circle-check", size=16, color="var(--green-9)"),
                rx.icon("circle", size=16, color="var(--gray-7)"),
            ),
            rx.vstack(
                rx.text(repo["name"], size="2", weight="bold"),
                rx.text(repo["description"], size="1", color="var(--gray-9)"),
                spacing="1",
                flex="1",
            ),
            rx.cond(
                repo["is_cloned"],
                rx.badge("cloned", color_scheme="green", size="1"),
                rx.button(
                    "Clone",
                    size="1",
                    variant="surface",
                    on_click=AppState.clone_repo(repo["name"]),
                ),
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        width="100%",
    )


def settings_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("Settings", size="6"),

            # API Key
            rx.card(
                rx.vstack(
                    rx.text("API Configuration", size="3", weight="bold"),
                    rx.text("OpenRouter API Key", size="2", color="var(--gray-9)"),
                    rx.input(
                        placeholder="sk-or-...",
                        value=AppState.api_key,
                        on_change=AppState.set_api_key,
                        type="password",
                        size="3",
                        width="100%",
                    ),
                    rx.text(
                        "Get yours at openrouter.ai/keys — Gemini Flash Lite is nearly free.",
                        size="1",
                        color="var(--gray-8)",
                    ),

                    rx.separator(),

                    rx.text("Default Model", size="2", color="var(--gray-9)"),
                    rx.select(
                        AppState.model_options,
                        value=AppState.default_model,
                        on_change=AppState.set_default_model,
                        size="2",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.button(
                            "Refresh Models",
                            variant="surface",
                            size="1",
                            on_click=AppState.refresh_models,
                        ),
                        rx.cond(
                            AppState.api_key != "",
                            rx.badge("Connected", color_scheme="green", size="1"),
                            rx.badge("No API key", color_scheme="orange", size="1"),
                        ),
                        spacing="2",
                    ),

                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),

            # Hardware
            rx.card(
                rx.vstack(
                    rx.text("Hardware Profile", size="3", weight="bold"),
                    rx.grid(
                        rx.vstack(
                            rx.text("Chip", size="1", color="var(--gray-9)"),
                            rx.text(AppState.chip, size="2", weight="bold"),
                        ),
                        rx.vstack(
                            rx.text("Memory", size="1", color="var(--gray-9)"),
                            rx.text(AppState.memory_gb.to(str), " GB", size="2", weight="bold"),
                        ),
                        rx.vstack(
                            rx.text("CPU Cores", size="1", color="var(--gray-9)"),
                            rx.text(AppState.cpu_cores.to(str), size="2", weight="bold"),
                        ),
                        rx.vstack(
                            rx.text("GPU Cores", size="1", color="var(--gray-9)"),
                            rx.text(AppState.gpu_cores.to(str), size="2", weight="bold"),
                        ),
                        rx.vstack(
                            rx.text("MLX Device", size="1", color="var(--gray-9)"),
                            rx.text(AppState.mlx_device, size="2", weight="bold"),
                        ),
                        rx.vstack(
                            rx.text("Max Trainable", size="1", color="var(--gray-9)"),
                            rx.text("~", AppState.max_trainable.to(str), "M", size="2", weight="bold"),
                        ),
                        columns="3",
                        spacing="4",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),

            # Repos
            rx.card(
                rx.vstack(
                    rx.text("Repository Management", size="3", weight="bold"),
                    rx.text("Clone frontier repos to enable experiments and code search.", size="2", color="var(--gray-9)"),
                    rx.foreach(AppState.available_repos, repo_manage_card),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),

            width="100%",
            spacing="4",
            max_width="800px",
        ),
    )
