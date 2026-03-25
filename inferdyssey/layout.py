"""Shared layout — sidebar + main content area."""

import reflex as rx
from inferdyssey.state import AppState


def nav_item(label: str, href: str, icon_name: str) -> rx.Component:
    """A sidebar navigation link."""
    return rx.link(
        rx.hstack(
            rx.icon(icon_name, size=18),
            rx.text(label, size="2", weight="medium"),
            spacing="2",
            align="center",
            width="100%",
            padding_x="12px",
            padding_y="8px",
            border_radius="8px",
            _hover={"bg": "var(--gray-a3)"},
        ),
        href=href,
        underline="none",
        width="100%",
    )


def chat_list_item(chat: dict) -> rx.Component:
    """A chat session in the sidebar."""
    return rx.hstack(
        rx.link(
            rx.text(
                chat["title"],
                size="1",
                truncate=True,
                color=rx.cond(
                    AppState.active_chat_id == chat["id"],
                    "var(--accent-11)",
                    "var(--gray-11)",
                ),
                weight=rx.cond(
                    AppState.active_chat_id == chat["id"],
                    "bold",
                    "regular",
                ),
            ),
            on_click=AppState.set_active_chat(chat["id"]),
            flex="1",
            underline="none",
            cursor="pointer",
        ),
        rx.icon_button(
            rx.icon("archive", size=12),
            size="1",
            variant="ghost",
            on_click=AppState.archive_chat(chat["id"]),
        ),
        width="100%",
        padding_x="12px",
        padding_y="4px",
        align="center",
    )


def archived_item(chat: dict) -> rx.Component:
    return rx.hstack(
        rx.text(chat["title"], size="1", color="var(--gray-9)", truncate=True),
        rx.icon_button(
            rx.icon("undo-2", size=12),
            size="1",
            variant="ghost",
            on_click=AppState.restore_chat(chat["id"]),
        ),
        width="100%",
        padding_x="12px",
        padding_y="2px",
        align="center",
    )


def sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Logo
            rx.hstack(
                rx.icon("flask-conical", size=24, color="var(--accent-9)"),
                rx.heading("InferDyssey", size="4", weight="bold"),
                spacing="2",
                align="center",
                padding="16px",
            ),
            rx.text("Research OS", size="1", color="var(--gray-9)", padding_x="16px", margin_top="-8px"),

            rx.separator(margin_y="8px"),

            # Navigation
            rx.vstack(
                nav_item("Explorer", "/explorer", "search"),
                nav_item("Lab", "/lab", "flask-conical"),
                nav_item("Library", "/", "book-open"),
                nav_item("Specs", "/specs", "cpu"),
                nav_item("Settings", "/settings", "settings"),
                spacing="1",
                padding_x="8px",
                width="100%",
            ),

            rx.separator(margin_y="8px"),

            # Chat sessions
            rx.hstack(
                rx.text("Chats", size="1", weight="bold", color="var(--gray-9)"),
                rx.spacer(),
                rx.icon_button(
                    rx.icon("plus", size=14),
                    size="1",
                    variant="ghost",
                    on_click=AppState.new_chat,
                ),
                padding_x="16px",
                width="100%",
                align="center",
            ),

            rx.scroll_area(
                rx.vstack(
                    rx.foreach(AppState.active_chats, chat_list_item),
                    # Archived folder
                    rx.cond(
                        AppState.archived_chats.length() > 0,
                        rx.box(
                            rx.separator(margin_y="4px"),
                            rx.text("Archived", size="1", color="var(--gray-8)", padding_x="12px", padding_y="4px"),
                            rx.foreach(AppState.archived_chats, archived_item),
                            width="100%",
                        ),
                    ),
                    spacing="0",
                    width="100%",
                ),
                max_height="40vh",
                width="100%",
            ),

            rx.spacer(),

            # Hardware badge at bottom
            rx.cond(
                AppState.hw_detected,
                rx.box(
                    rx.separator(margin_y="4px"),
                    rx.hstack(
                        rx.icon("cpu", size=14, color="var(--gray-9)"),
                        rx.text(
                            AppState.chip,
                            size="1",
                            color="var(--gray-9)",
                        ),
                        rx.badge(
                            rx.text(AppState.memory_gb.to(str), "GB"),
                            size="1",
                            variant="surface",
                        ),
                        spacing="2",
                        padding="12px",
                        align="center",
                    ),
                ),
            ),

            height="100vh",
            width="100%",
            spacing="0",
        ),
        width="240px",
        min_width="240px",
        border_right="1px solid var(--gray-a4)",
        bg="var(--gray-a2)",
        position="fixed",
        left="0",
        top="0",
        height="100vh",
        overflow_y="auto",
    )


def layout(content: rx.Component) -> rx.Component:
    """Wrap any page content with the sidebar layout."""
    return rx.hstack(
        sidebar(),
        rx.box(
            content,
            margin_left="240px",
            width="calc(100% - 240px)",
            min_height="100vh",
            padding="24px",
        ),
        spacing="0",
        width="100%",
    )
