"""Explorer page — code search across all external repos."""

import reflex as rx
from inferdyssey.state import AppState, SearchResult
from inferdyssey.layout import layout


def search_result_row(result: SearchResult) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.badge(result.repo, variant="surface", size="1"),
            rx.text(result.file, size="1", color="var(--gray-9)", truncate=True),
            rx.badge(rx.text("L", result.line.to(str)), variant="outline", size="1"),
            spacing="2",
            align="center",
        ),
        rx.code_block(
            result.text,
            language="python",
            show_line_numbers=False,
        ),
        padding="8px",
        border="1px solid var(--gray-a4)",
        border_radius="8px",
        width="100%",
    )


def explorer_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("Explorer", size="6"),
            rx.text(
                "Search code across all cloned repositories. Find implementations, patterns, and APIs.",
                size="2",
                color="var(--gray-9)",
            ),

            # Search bar
            rx.hstack(
                rx.input(
                    placeholder="Search code... (e.g. 'flash_attention', 'expert_prefetch', 'Metal kernel')",
                    value=AppState.search_query,
                    on_change=AppState.set_search_query,
                    size="3",
                    flex="1",
                ),
                rx.button(
                    rx.icon("search", size=16),
                    "Search",
                    on_click=AppState.run_search,
                    size="3",
                    loading=AppState.searching,
                ),
                width="100%",
                spacing="2",
            ),

            # Cloned repos info
            rx.cond(
                AppState.cloned_repos.length() == 0,
                rx.callout(
                    "No repos cloned yet. Go to Settings to clone frontier repos like EXO, Flash-MoE, mlx-vlm.",
                    icon="info",
                    variant="surface",
                ),
                rx.hstack(
                    rx.text("Searching across:", size="1", color="var(--gray-9)"),
                    rx.foreach(
                        AppState.cloned_repos,
                        lambda r: rx.badge(r["name"], variant="surface", size="1"),
                    ),
                    spacing="2",
                    align="center",
                ),
            ),

            rx.separator(),

            # Results
            rx.cond(
                AppState.searching,
                rx.vstack(
                    rx.skeleton(height="60px", width="100%"),
                    rx.skeleton(height="60px", width="100%"),
                    rx.skeleton(height="60px", width="100%"),
                    spacing="2",
                    width="100%",
                ),
                rx.cond(
                    AppState.search_results.length() > 0,
                    rx.vstack(
                        rx.text(
                            rx.text(AppState.search_results.length().to(str), " results"),
                            size="2",
                            weight="medium",
                        ),
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(AppState.search_results, search_result_row),
                                spacing="2",
                                width="100%",
                            ),
                            max_height="70vh",
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.cond(
                        AppState.search_query != "",
                        rx.text("No results found.", size="2", color="var(--gray-9)"),
                    ),
                ),
            ),

            width="100%",
            spacing="4",
        ),
    )
