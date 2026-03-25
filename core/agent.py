"""LLM agent interface via OpenRouter (OpenAI-compatible API)."""

import json
import os
from dataclasses import dataclass


@dataclass
class CodeEdit:
    summary: str
    new_code: str
    reasoning: str


class Agent:
    """Thin wrapper around OpenRouter API using the openai SDK."""

    DEFAULT_MODEL = "google/gemini-2.0-flash-lite-001"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
            )
        return self._client

    def ask(self, prompt: str, system: str = "") -> str:
        """General-purpose question."""
        if not self.is_configured:
            return "[No API key set. Go to Settings to configure OpenRouter.]"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=4096,
                temperature=0.7,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            return f"[Agent error: {e}]"

    def explain(self, topic: str, level: str = "beginner", context: str = "") -> str:
        """Explain a topic at a given level."""
        system = (
            "You are InferDyssey's learning assistant. You explain Apple Silicon "
            "inference concepts clearly. Adjust depth to the requested level. "
            "Use analogies for beginners. Be concise but thorough."
        )
        prompt = f"Level: {level}\n\nExplain: {topic}"
        if context:
            prompt += f"\n\nAdditional context from local repos:\n{context}"
        return self.ask(prompt, system=system)

    def suggest_code_edit(self, current_code: str, results_history: list[dict]) -> CodeEdit:
        """Suggest an improvement to training code based on past results."""
        if not self.is_configured:
            return CodeEdit(
                summary="No API key",
                new_code=current_code,
                reasoning="Set your OpenRouter API key in Settings.",
            )

        system = (
            "You are an ML research agent running autoresearch experiments on Apple Silicon (MLX). "
            "Your job: suggest ONE small, targeted improvement to the training code. "
            "Focus on things like: learning rate schedules, weight initialization, "
            "normalization, attention modifications, positional encoding, "
            "activation functions, optimizer tweaks, data preprocessing. "
            "Return ONLY valid JSON with keys: summary, reasoning, new_code. "
            "new_code must be the COMPLETE updated training script (not a diff)."
        )

        history_str = ""
        for r in results_history[-5:]:
            history_str += (
                f"- val_loss={r.get('val_loss', '?'):.4f}, "
                f"tok/s={r.get('tok_per_sec', '?'):.0f}, "
                f"change: {r.get('summary', 'baseline')}\n"
            )

        prompt = (
            f"## Current training code:\n```python\n{current_code}\n```\n\n"
            f"## Recent experiment results (newest last):\n{history_str or 'No history yet — this is the baseline run.'}\n\n"
            f"Suggest ONE improvement. Return JSON only."
        )

        raw = self.ask(prompt, system=system)

        # Parse JSON from response (handle markdown code blocks)
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            data = json.loads(cleaned)
            return CodeEdit(
                summary=data.get("summary", "unknown change"),
                new_code=data.get("new_code", current_code),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError):
            return CodeEdit(
                summary="failed to parse agent response",
                new_code=current_code,
                reasoning=f"Raw response: {raw[:500]}",
            )

    def suggest_hypotheses(self, hardware_summary: str, repo_capabilities: list[dict]) -> str:
        """Suggest experiment hypotheses based on hardware + repo capabilities."""
        system = (
            "You are an ML research advisor. Given a user's hardware and the repos/capabilities "
            "they have available, suggest 3-5 concrete experiment hypotheses they could test. "
            "Flag hypotheses that require changes in multiple repos. "
            "Be specific about what to test and what metric to measure."
        )
        repos_str = "\n".join(
            f"- {r['name']}: {r.get('description', '')} (capabilities: {', '.join(r.get('capabilities', []))})"
            for r in repo_capabilities
        )
        prompt = (
            f"## Hardware:\n{hardware_summary}\n\n"
            f"## Available repos:\n{repos_str}\n\n"
            f"Suggest 3-5 hypotheses."
        )
        return self.ask(prompt, system=system)
