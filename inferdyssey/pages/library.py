"""Library page — chat exploration with AI, X feed search, learn by doing."""

import reflex as rx
from inferdyssey.state import AppState, ChatMessage
from inferdyssey.layout import layout


def message_bubble(msg: ChatMessage) -> rx.Component:
    is_user = msg.role == "user"
    return rx.box(
        rx.markdown(msg.content, size="2"),
        bg=rx.cond(is_user, "var(--accent-a3)", "var(--gray-a2)"),
        padding="12px 16px",
        border_radius="12px",
        max_width="75%",
        align_self=rx.cond(is_user, "flex-end", "flex-start"),
    )


def starter_button(label: str, prompt: str) -> rx.Component:
    return rx.button(
        label,
        variant="surface",
        size="2",
        on_click=AppState.send_starter(prompt),
        cursor="pointer",
    )


def library_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("Library", size="6"),
            rx.text("Explore the Apple Silicon inference stack. Ask anything.", size="2", color="var(--gray-9)"),

            # Model selector
            rx.hstack(
                rx.text("Model:", size="1", color="var(--gray-9)"),
                rx.select(
                    AppState.model_options,
                    value=AppState.default_model,
                    on_change=AppState.set_default_model,
                    size="1",
                    width="300px",
                ),
                align="center",
                spacing="2",
            ),

            rx.separator(),

            # Quick starters (only when chat is empty)
            rx.cond(
                AppState.current_messages.length() == 0,
                rx.vstack(
                    rx.text("Start exploring", size="3", weight="medium"),
                    rx.flex(
                        starter_button(
                            "What's happening on X?",
                            "What are @Alexintosh, @danveloper, @Prince_Canuma, and @danpacary working on right now? Give me a snapshot of the latest activity.",
                        ),
                        starter_button(
                            "Explain the stack",
                            "Give me a thorough guided tour of the Apple Silicon inference stack: what projects exist, who maintains them, how they fit together.",
                        ),
                        starter_button(
                            "Flash-MoE deep dive",
                            "How does Flash-MoE stream 397B parameter MoE models from SSD? Explain Metal kernels, Morton-order GEMM, expert prefetch.",
                        ),
                        starter_button(
                            "My first experiment",
                            "I'm on an M1 Max 64GB. I want to train a small model from scratch and start contributing. What should my first experiment be?",
                        ),
                        wrap="wrap",
                        spacing="2",
                    ),
                    spacing="3",
                ),
            ),

            # Messages
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(AppState.current_messages, message_bubble),
                    rx.cond(
                        AppState.chat_loading,
                        rx.box(
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Thinking...", size="1", color="var(--gray-9)"),
                                spacing="2",
                            ),
                            padding="12px",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                    padding_y="8px",
                ),
                flex="1",
                width="100%",
            ),

            # Input
            rx.hstack(
                rx.input(
                    placeholder="Ask about the stack, search X feeds, propose experiments...",
                    value=AppState.chat_input,
                    on_change=AppState.set_chat_input,
                    size="3",
                    flex="1",
                ),
                rx.button(
                    rx.icon("send", size=16),
                    on_click=AppState.send_message,
                    size="3",
                    disabled=AppState.chat_loading,
                ),
                width="100%",
                spacing="2",
            ),

            height="calc(100vh - 48px)",
            width="100%",
            spacing="3",
        ),
    )
