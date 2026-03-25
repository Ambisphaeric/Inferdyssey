"""InferDyssey — Research OS for Apple Silicon Inference.

Reflex app entry point. Registers all pages.
"""

import reflex as rx
from inferdyssey.state import AppState
from inferdyssey.pages.library import library_page
from inferdyssey.pages.explorer import explorer_page
from inferdyssey.pages.lab import lab_page
from inferdyssey.pages.specs import specs_page
from inferdyssey.pages.settings import settings_page


app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="blue",
        radius="medium",
    ),
)

app.add_page(library_page, route="/", title="Library | InferDyssey", on_load=AppState.on_load)
app.add_page(explorer_page, route="/explorer", title="Explorer | InferDyssey", on_load=AppState.on_load)
app.add_page(lab_page, route="/lab", title="Lab | InferDyssey", on_load=AppState.on_load)
app.add_page(specs_page, route="/specs", title="Specs | InferDyssey", on_load=AppState.on_load)
app.add_page(settings_page, route="/settings", title="Settings | InferDyssey", on_load=AppState.on_load)
