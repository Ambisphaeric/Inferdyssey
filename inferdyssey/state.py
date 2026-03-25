"""Global application state for InferDyssey."""

import uuid
import subprocess
from datetime import datetime

import reflex as rx
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str = ""
    content: str = ""


class Chat(BaseModel):
    id: str = ""
    title: str = "New Chat"
    messages: list[ChatMessage] = []
    model: str = "minimax/minimax-m2.5"
    created: str = ""
    archived: bool = False


class SearchResult(BaseModel):
    file: str = ""
    line: int = 0
    text: str = ""
    repo: str = ""


class AppState(rx.State):
    """Root application state."""

    # --- Settings ---
    api_key: str = ""
    default_model: str = "minimax/minimax-m2.5"

    # --- Hardware ---
    chip: str = ""
    memory_gb: float = 0.0
    cpu_cores: int = 0
    gpu_cores: int = 0
    mlx_device: str = ""
    max_trainable: int = 0
    hw_detected: bool = False

    # --- Chat state ---
    chats: list[Chat] = []
    active_chat_id: str = ""
    chat_input: str = ""
    chat_loading: bool = False

    # --- Explorer state ---
    search_query: str = ""
    search_results: list[SearchResult] = []
    searching: bool = False

    # --- Lab state ---
    hypothesis: str = ""
    lab_model_config: str = "small"
    lab_time_budget: int = 120
    lab_iterations: int = 5
    lab_running: bool = False
    lab_status: str = ""
    lab_results: list[dict] = []

    # --- Repos ---
    available_repos: list[dict] = []

    # --- Models list ---
    model_options: list[str] = []
    models_loaded: bool = False

    def on_load(self):
        """Initialize on first page load."""
        if not self.hw_detected:
            self._detect_hardware()
        if not self.chats:
            self._new_chat()
        if not self.available_repos:
            self._load_repos()
        if not self.models_loaded:
            self._load_models()

    def _detect_hardware(self):
        from core.hardware import detect
        hw = detect()
        self.chip = hw.chip
        self.memory_gb = hw.memory_gb
        self.cpu_cores = hw.cpu_cores
        self.gpu_cores = hw.gpu_cores
        self.mlx_device = hw.mlx_device
        self.max_trainable = hw.max_trainable_params_m
        self.hw_detected = True

    def _load_repos(self):
        from core.repos import list_available
        repos = list_available()
        self.available_repos = [
            {
                "name": r.name,
                "url": r.url,
                "description": r.description,
                "stack_layer": r.stack_layer,
                "capabilities": r.capabilities,
                "maintainer": r.maintainer,
                "is_cloned": r.is_cloned,
                "current_branch": r.current_branch,
                "min_memory_gb": r.min_memory_gb,
            }
            for r in repos
        ]

    def _load_models(self):
        try:
            from core.models import fetch_models, FAVORITES
            models = fetch_models()
            self.model_options = [m.id for m in models]
            self.models_loaded = True
        except Exception:
            self.model_options = [
                "minimax/minimax-m2.5",
                "x-ai/grok-4.1-fast",
                "google/gemini-2.5-pro",
                "google/gemini-2.0-flash-001",
                "google/gemini-2.0-flash-lite-001",
                "anthropic/claude-opus-4",
            ]
            self.models_loaded = True

    # --- Chat ---

    def _new_chat(self) -> str:
        chat_id = str(uuid.uuid4())[:8]
        chat = Chat(
            id=chat_id,
            title="New Chat",
            messages=[],
            model=self.default_model,
            created=datetime.now().isoformat(),
        )
        self.chats.append(chat)
        self.active_chat_id = chat_id
        return chat_id

    def new_chat(self):
        self._new_chat()

    def set_active_chat(self, chat_id: str):
        self.active_chat_id = chat_id

    def archive_chat(self, chat_id: str):
        for chat in self.chats:
            if chat.id == chat_id:
                chat.archived = True
                break
        if self.active_chat_id == chat_id:
            active = [c for c in self.chats if not c.archived]
            if active:
                self.active_chat_id = active[0].id
            else:
                self._new_chat()

    def restore_chat(self, chat_id: str):
        for chat in self.chats:
            if chat.id == chat_id:
                chat.archived = False
                self.active_chat_id = chat_id
                break

    def set_chat_input(self, value: str):
        self.chat_input = value

    def send_message(self):
        if not self.chat_input.strip():
            return
        self._send_message_text(self.chat_input.strip())
        self.chat_input = ""

    def send_starter(self, prompt: str):
        self._send_message_text(prompt)

    def _send_message_text(self, text: str):
        # Find active chat
        chat = None
        for c in self.chats:
            if c.id == self.active_chat_id:
                chat = c
                break
        if not chat:
            return

        chat.messages.append(ChatMessage(role="user", content=text))

        # Auto-title
        user_msgs = [m for m in chat.messages if m.role == "user"]
        if len(user_msgs) == 1:
            chat.title = text[:50] + ("..." if len(text) > 50 else "")

        self.chat_loading = True
        return AppState._get_ai_response

    def _get_ai_response(self):
        chat = None
        for c in self.chats:
            if c.id == self.active_chat_id:
                chat = c
                break
        if not chat:
            self.chat_loading = False
            return

        if not self.api_key:
            chat.messages.append(ChatMessage(
                role="assistant",
                content="Set your OpenRouter API key in **Settings** to start chatting.\n\nGet one at [openrouter.ai/keys](https://openrouter.ai/keys)",
            ))
            self.chat_loading = False
            return

        from core.agent import Agent
        agent = Agent(api_key=self.api_key, model=chat.model)

        # Build context
        from core.repos import list_available
        repos = list_available()
        context = f"User hardware: {self.chip}, {self.memory_gb}GB, MLX {self.mlx_device}\n"
        context += "Known repos:\n"
        for r in repos:
            context += f"- {r.name} ({r.stack_layer}): {r.description} by {r.maintainer}\n"

        system = (
            "You are InferDyssey's research assistant. Help users understand and contribute to "
            "the Apple Silicon LLM inference ecosystem. Key people: Alex Cheema (@Alexintosh/EXO), "
            "@danveloper/@anemll (Flash-MoE), Prince Canuma (@Prince_Canuma/mlx-vlm), @danpacary. "
            "Be concrete — reference specific repos, techniques, files. "
            f"\n\n{context}"
        )

        messages = [{"role": "system", "content": system}]
        for m in chat.messages:
            messages.append({"role": m.role, "content": m.content})

        try:
            resp = agent.client.chat.completions.create(
                model=chat.model,
                messages=messages,
                max_tokens=4096,
                temperature=0.7,
            )
            reply = resp.choices[0].message.content or ""
        except Exception as e:
            reply = f"**Error:** {e}"

        chat.messages.append(ChatMessage(role="assistant", content=reply))
        self.chat_loading = False

    # --- Explorer (code search) ---

    def set_search_query(self, value: str):
        self.search_query = value

    def run_search(self):
        if not self.search_query.strip():
            return
        self.searching = True
        return AppState._do_search

    def _do_search(self):
        from pathlib import Path
        query = self.search_query.strip()
        results = []

        external = Path("external")
        if not external.exists():
            self.search_results = []
            self.searching = False
            return

        # Use ripgrep if available, else fall back to grep
        try:
            cmd = ["rg", "--no-heading", "-n", "--max-count", "50", "-t", "py", "-t", "c", "-t", "md", query, str(external)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = proc.stdout.strip().split("\n") if proc.stdout.strip() else []
        except FileNotFoundError:
            cmd = ["grep", "-rn", "--include=*.py", "--include=*.c", "--include=*.md", "-m", "50", query, str(external)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = proc.stdout.strip().split("\n") if proc.stdout.strip() else []

        for line in lines[:50]:
            parts = line.split(":", 2)
            if len(parts) >= 3:
                filepath = parts[0]
                try:
                    lineno = int(parts[1])
                except ValueError:
                    lineno = 0
                text = parts[2].strip()[:200]
                # Extract repo name
                repo = filepath.replace(str(external) + "/", "").split("/")[0]
                results.append(SearchResult(
                    file=filepath,
                    line=lineno,
                    text=text,
                    repo=repo,
                ))

        self.search_results = results
        self.searching = False

    # --- Lab ---

    def set_hypothesis(self, value: str):
        self.hypothesis = value

    def set_lab_model_config(self, value: str):
        self.lab_model_config = value

    def set_lab_time_budget(self, value: list):
        if value:
            self.lab_time_budget = int(value[0])

    def set_lab_iterations(self, value: str):
        try:
            self.lab_iterations = int(value)
        except ValueError:
            pass

    def run_baseline(self):
        self.lab_running = True
        self.lab_status = "Running baseline..."
        self.lab_results = []
        return AppState._do_baseline

    def _do_baseline(self):
        from core.trainer import train
        from core import benchmark

        try:
            result = train(
                config_name=self.lab_model_config,
                data_path="data/shakespeare.txt",
                max_time_seconds=self.lab_time_budget,
            )

            run_id = benchmark.log_result(
                val_loss=result.val_loss,
                train_loss=result.train_loss,
                tok_per_sec=result.tok_per_sec,
                peak_memory_mb=result.peak_memory_mb,
                wall_time_s=result.wall_time_s,
                steps=result.steps,
                config_name=self.lab_model_config,
                n_params=result.n_params,
                hardware=self.chip,
                summary="baseline",
            )

            self.lab_status = (
                f"Baseline complete: val_loss={result.val_loss:.4f}, "
                f"{result.tok_per_sec:.0f} tok/s, {result.steps} steps"
            )
            if result.checkpoint_path:
                self.lab_status += f" | Saved to {result.checkpoint_path}"

            self.lab_results.append({
                "iteration": 0,
                "summary": "baseline",
                "val_loss": round(result.val_loss, 4),
                "tok_per_sec": round(result.tok_per_sec, 0),
                "improved": True,
            })
        except Exception as e:
            self.lab_status = f"Error: {e}"

        self.lab_running = False

    # --- Settings ---

    def set_api_key(self, value: str):
        self.api_key = value

    def set_default_model(self, value: str):
        self.default_model = value

    def clone_repo(self, name: str):
        from core.repos import clone_repo
        ok, msg = clone_repo(name)
        self._load_repos()

    def refresh_models(self):
        self.models_loaded = False
        self._load_models()

    @rx.var
    def active_chats(self) -> list[Chat]:
        return [c for c in self.chats if not c.archived]

    @rx.var
    def archived_chats(self) -> list[Chat]:
        return [c for c in self.chats if c.archived]

    @rx.var
    def current_chat(self) -> Chat | None:
        for c in self.chats:
            if c.id == self.active_chat_id:
                return c
        return None

    @rx.var
    def current_messages(self) -> list[ChatMessage]:
        for c in self.chats:
            if c.id == self.active_chat_id:
                return c.messages
        return []

    @rx.var
    def cloned_repos(self) -> list[dict]:
        return [r for r in self.available_repos if r.get("is_cloned")]

    @rx.var
    def uncloned_repos(self) -> list[dict]:
        return [r for r in self.available_repos if not r.get("is_cloned")]

    @rx.var
    def all_capabilities(self) -> list[str]:
        caps = set(["local_mlx_training"])
        for r in self.available_repos:
            if r.get("is_cloned"):
                for c in r.get("capabilities", []):
                    caps.add(c)
        return sorted(caps)

    @rx.var
    def benchmark_history(self) -> list[dict]:
        try:
            from core.benchmark import get_history
            return get_history(limit=20)
        except Exception:
            return []

    @rx.var
    def benchmark_stats(self) -> dict:
        try:
            from core.benchmark import get_stats
            return get_stats()
        except Exception:
            return {"total_runs": 0, "best_val_loss": None, "best_tok_per_sec": None}
