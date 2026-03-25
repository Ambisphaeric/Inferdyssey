"""Learn page — exploration platform with X feed search via Grok, multi-chat sessions."""

import json
import uuid
from datetime import datetime

import streamlit as st
from core.agent import Agent
from core.repos import list_cloned, get_readme, list_available


# ---------------------------------------------------------------------------
# Chat session management
# ---------------------------------------------------------------------------

def _ensure_chat_state():
    """Initialize chat session state if missing."""
    if "chats" not in st.session_state:
        st.session_state.chats = {}
    if "archived_chats" not in st.session_state:
        st.session_state.archived_chats = {}
    if "active_chat" not in st.session_state:
        _new_chat(auto=True)


def _new_chat(auto=False) -> str:
    chat_id = str(uuid.uuid4())[:8]
    st.session_state.chats[chat_id] = {
        "id": chat_id,
        "title": "New Chat",
        "messages": [],
        "created": datetime.now().isoformat(),
        "model": st.session_state.get("agent_model", "minimax/minimax-m2.5"),
    }
    st.session_state.active_chat = chat_id
    return chat_id


def _get_active_chat() -> dict:
    _ensure_chat_state()
    chat_id = st.session_state.active_chat
    if chat_id not in st.session_state.chats:
        _new_chat(auto=True)
        chat_id = st.session_state.active_chat
    return st.session_state.chats[chat_id]


def _auto_title(messages: list[dict]) -> str:
    """Generate a short title from the first user message."""
    for msg in messages:
        if msg["role"] == "user":
            text = msg["content"][:50]
            return text + ("..." if len(msg["content"]) > 50 else "")
    return "New Chat"


# ---------------------------------------------------------------------------
# System prompt for exploration
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are InferDyssey's research exploration assistant powered by Grok.

Your role: Help users understand and contribute to the Apple Silicon LLM inference ecosystem.

Key people and projects you know about:
- Alex Cheema (@Alexintosh / EXO Labs): Distributed LLM inference across Apple Silicon devices
- @danveloper / @anemll (Flash-MoE): Custom Metal kernel engine for streaming massive MoE models from SSD
- Prince Canuma (@Prince_Canuma / @Blaizzy): MLX vision-language models (mlx-vlm, mlx-audio, mlx-swift)
- @danpacary: Context-window optimization, batching, systems integration
- Apple MLX team (ml-explore): The MLX framework itself

When the user asks about X/Twitter activity, recent work, or "what's happening":
- Share what you know about these contributors' recent work and focus areas
- Reference specific repos, techniques, and breakthroughs
- Explain technical concepts at the user's level

When the user asks about the stack:
- Hardware layer: M1-M5, unified memory, ANE, Metal, Thunderbolt clustering
- Framework layer: MLX, mlx-lm, mlx-vlm, mlx-swift
- Engine layer: Flash-MoE (custom Metal kernels, SSD streaming, Morton-order GEMM)
- Clustering layer: EXO (distributed inference, RDMA, device discovery)
- Optimization: Quantization (INT4, FP8), Flash Attention, expert prefetch, KV-cache compression

Always be concrete. Reference specific repos, files, and techniques.
If the user wants to try something, suggest how InferDyssey can help (Workspaces for experiments, Specs for hardware/capability checking).

{context}"""


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render():
    _ensure_chat_state()

    # --- Sidebar: chat session management ---
    with st.sidebar:
        st.divider()
        st.subheader("Chats")

        if st.button("+ New Chat", use_container_width=True):
            _new_chat()
            st.rerun()

        # List active chats (newest first)
        sorted_chats = sorted(
            st.session_state.chats.values(),
            key=lambda c: c["created"],
            reverse=True,
        )
        for chat in sorted_chats:
            label = chat["title"]
            is_active = chat["id"] == st.session_state.active_chat
            col1, col2 = st.columns([5, 1])
            if col1.button(
                f"{'> ' if is_active else ''}{label}",
                key=f"chat_{chat['id']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.active_chat = chat["id"]
                st.rerun()
            if col2.button("📦", key=f"archive_{chat['id']}", help="Archive"):
                st.session_state.archived_chats[chat["id"]] = st.session_state.chats.pop(chat["id"])
                if st.session_state.active_chat == chat["id"]:
                    if st.session_state.chats:
                        st.session_state.active_chat = next(iter(st.session_state.chats))
                    else:
                        _new_chat(auto=True)
                st.rerun()

        # Archived chats folder
        if st.session_state.archived_chats:
            with st.expander(f"Archived ({len(st.session_state.archived_chats)})"):
                sorted_archived = sorted(
                    st.session_state.archived_chats.values(),
                    key=lambda c: c["created"],
                    reverse=True,
                )
                for chat in sorted_archived:
                    col1, col2 = st.columns([5, 1])
                    col1.caption(chat["title"])
                    if col2.button("↩", key=f"unarchive_{chat['id']}", help="Restore"):
                        st.session_state.chats[chat["id"]] = st.session_state.archived_chats.pop(chat["id"])
                        st.session_state.active_chat = chat["id"]
                        st.rerun()

    # --- Main area ---
    chat = _get_active_chat()

    # Header
    st.header("Learn")
    col1, col2 = st.columns([3, 1])
    col1.caption("Explore the Apple Silicon inference stack. Search X feeds. Learn by doing.")

    # Model selector for this chat (dynamic from OpenRouter)
    from core.models import fetch_models, get_model_display, FAVORITES

    if "openrouter_models" not in st.session_state:
        st.session_state.openrouter_models = fetch_models()

    models = st.session_state.openrouter_models
    model_ids = [m.id for m in models]
    display_map = get_model_display(models)

    current_model = chat.get("model", FAVORITES[0])
    idx = model_ids.index(current_model) if current_model in model_ids else 0
    selected_model = col2.selectbox(
        "Model",
        model_ids,
        index=idx,
        format_func=lambda mid: display_map.get(mid, mid),
        key=f"model_select_{chat['id']}",
        label_visibility="collapsed",
    )
    chat["model"] = selected_model

    # --- Quick starters (only show if chat is empty) ---
    if not chat["messages"]:
        st.divider()
        st.subheader("Start exploring")
        starters = [
            ("What's happening on X?", "What are @Alexintosh, @danveloper, @Prince_Canuma, and @danpacary working on right now? Give me a snapshot of the latest activity in the Apple Silicon inference space."),
            ("Explain the stack", "Give me a thorough guided tour of the Apple Silicon inference stack: what projects exist, who maintains them, what part of the stack they operate on, and how they fit together."),
            ("Flash-MoE deep dive", "How does Flash-MoE stream 397B parameter MoE models from SSD? Explain the Metal kernel tricks, Morton-order GEMM, and expert prefetch."),
            ("EXO clustering", "How does EXO cluster multiple Macs for distributed inference? Explain Thunderbolt RDMA, device discovery, and model sharding."),
            ("My first experiment", "I'm on an M1 Max 64GB. I want to train a small model from scratch and start contributing. What should my first experiment be?"),
            ("Cross-repo hypothesis", "What would happen if we combined EXO's distributed clustering with Flash-MoE's SSD expert streaming? Walk me through a hypothesis."),
        ]

        cols = st.columns(2)
        for i, (title, full_prompt) in enumerate(starters):
            if cols[i % 2].button(title, key=f"starter_{i}", use_container_width=True):
                chat["messages"].append({"role": "user", "content": full_prompt})
                chat["title"] = title
                st.rerun()

    # --- Chat messages ---
    for msg in chat["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # --- Chat input ---
    prompt = st.chat_input("Ask about the stack, search X feeds, propose experiments...")

    if prompt:
        chat["messages"].append({"role": "user", "content": prompt})

        # Auto-title from first message
        if len([m for m in chat["messages"] if m["role"] == "user"]) == 1:
            chat["title"] = _auto_title(chat["messages"])

        with st.chat_message("user"):
            st.markdown(prompt)

        # Build context
        context_parts = []
        cloned = list_cloned()
        if cloned:
            context_parts.append("User has these repos cloned locally:")
            for repo in cloned:
                readme = get_readme(repo.name)
                context_parts.append(
                    f"- {repo.name} ({repo.stack_layer}): {repo.description}\n"
                    f"  README excerpt: {readme[:800]}"
                )

        all_repos = list_available()
        context_parts.append("\nAll known repos in registry:")
        for repo in all_repos:
            context_parts.append(
                f"- {repo.name}: {repo.description} (maintainer: {repo.maintainer}, "
                f"capabilities: {', '.join(repo.capabilities)})"
            )

        hw = st.session_state.hardware
        context_parts.append(
            f"\nUser hardware: {hw.chip}, {hw.memory_gb}GB unified memory, "
            f"MLX {hw.mlx_device}, est. max trainable ~{hw.max_trainable_params_m}M params"
        )

        context = "\n".join(context_parts)
        system = SYSTEM_PROMPT.format(context=context)

        # Build full message history for the API
        api_messages = [{"role": "system", "content": system}]
        for msg in chat["messages"]:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        # Call agent
        api_key = st.session_state.get("api_key", "")

        with st.chat_message("assistant"):
            if not api_key:
                response = (
                    "I need an OpenRouter API key to chat. "
                    "Go to **Settings** and paste your key.\n\n"
                    "Get one at [openrouter.ai/keys](https://openrouter.ai/keys)\n\n"
                    "**Tip:** Grok 4.1 has direct access to X/Twitter data — "
                    "it can search feeds and surface what people are working on."
                )
                st.markdown(response)
            else:
                with st.spinner("Searching and thinking..."):
                    agent = Agent(api_key=api_key, model=selected_model)
                    try:
                        resp = agent.client.chat.completions.create(
                            model=selected_model,
                            messages=api_messages,
                            max_tokens=4096,
                            temperature=0.7,
                        )
                        response = resp.choices[0].message.content or ""
                    except Exception as e:
                        response = f"**Error:** {e}"
                st.markdown(response)

        chat["messages"].append({"role": "assistant", "content": response})
