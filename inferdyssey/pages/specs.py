"""Specs page — hardware → repos → capabilities → models → hypotheses."""

import reflex as rx
from inferdyssey.state import AppState
from inferdyssey.layout import layout


def capability_badge(cap: str) -> rx.Component:
    return rx.badge(cap, variant="surface", size="1")


def repo_card(repo: dict) -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.cond(
                repo["is_cloned"],
                rx.icon("circle-check", size=16, color="var(--green-9)"),
                rx.icon("circle", size=16, color="var(--gray-7)"),
            ),
            rx.vstack(
                rx.hstack(
                    rx.text(repo["name"], size="2", weight="bold"),
                    rx.badge(repo["stack_layer"], variant="outline", size="1"),
                    spacing="2",
                    align="center",
                ),
                rx.text(repo["description"], size="1", color="var(--gray-9)"),
                rx.text("Maintainer: ", repo["maintainer"], size="1", color="var(--gray-8)"),
                spacing="1",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def model_config_row(name: str, layers: str, heads: str, dim: str, params: str, feasible: bool) -> rx.Component:
    return rx.hstack(
        rx.cond(
            feasible,
            rx.icon("check", size=14, color="var(--green-9)"),
            rx.icon("triangle-alert", size=14, color="var(--yellow-9)"),
        ),
        rx.text(name, size="2", weight="bold", min_width="60px"),
        rx.text(params, size="2", color="var(--gray-9)"),
        rx.text(f"{layers}L / {heads}H / {dim}D", size="1", color="var(--gray-8)"),
        spacing="3",
        align="center",
    )


def specs_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("Specs", size="6"),
            rx.text("Hardware → Repos → Capabilities → Trainable Models", size="2", color="var(--gray-9)"),

            # 1. Hardware
            rx.card(
                rx.vstack(
                    rx.text("1. Hardware Detected", size="3", weight="bold"),
                    rx.grid(
                        rx.vstack(
                            rx.text("Chip", size="1", color="var(--gray-9)"),
                            rx.text(AppState.chip, size="3", weight="bold"),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Unified Memory", size="1", color="var(--gray-9)"),
                            rx.text(AppState.memory_gb.to(str), " GB", size="3", weight="bold"),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("MLX Device", size="1", color="var(--gray-9)"),
                            rx.text(AppState.mlx_device, size="3", weight="bold"),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Est. Max Training", size="1", color="var(--gray-9)"),
                            rx.text("~", AppState.max_trainable.to(str), "M params", size="3", weight="bold"),
                            spacing="1",
                        ),
                        columns="4",
                        spacing="4",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),

            # 2. Repositories
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.text("2. Repositories", size="3", weight="bold"),
                        rx.spacer(),
                        rx.badge(
                            rx.text(AppState.cloned_repos.length().to(str), " cloned"),
                            color_scheme="green",
                            size="1",
                        ),
                        align="center",
                    ),
                    rx.foreach(AppState.available_repos, repo_card),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),

            # 3. Capabilities
            rx.card(
                rx.vstack(
                    rx.text("3. System Capabilities", size="3", weight="bold"),
                    rx.flex(
                        rx.foreach(AppState.all_capabilities, capability_badge),
                        wrap="wrap",
                        spacing="2",
                    ),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),

            # 4. Trainable Models
            rx.card(
                rx.vstack(
                    rx.text("4. Trainable Models", size="3", weight="bold"),
                    rx.text("Models you can train from scratch on your hardware.", size="2", color="var(--gray-9)"),
                    model_config_row("tiny", "6", "6", "384", "~10M params", True),
                    model_config_row("small", "6", "8", "512", "~30M params", True),
                    model_config_row("base", "12", "12", "768", "~124M params", True),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),

            width="100%",
            spacing="4",
        ),
    )
