# InferDyssey

A learning platform for exploring cutting-edge AI inference on Apple Silicon. Built with Reflex, powered by MLX, designed for hands-on experimentation with the Apple Neural Engine (ANE).

## Quickstart

```bash
git clone https://github.com/yourname/inferdyssey.git
cd inferdyssey
chmod +x setup.sh && ./setup.sh
uv run reflex run
```

## What it does

- **Learn** — Interactive explainer for the Apple Silicon inference stack (EXO, Flash-MoE, MLX, ANE)
- **Vector Code Search** — Semantic search across external repos using embeddings
- **Workspaces** — Run autoresearch experiments on 10M-124M param transformers via MLX
- **Specs** — Hardware detection → repo capabilities → trainable models → hypothesis builder

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- OpenRouter API key (optional, for AI features)

## Architecture

```
inferdyssey/
├── app.py              # Reflex entry point
├── views/              # UI views
├── core/               # Training, benchmarks, autoresearch, repo management
├── registry/           # Known repo capabilities (YAML)
├── data/               # Training data (shakespeare.txt)
├── experiments/        # Benchmark results (SQLite)
└── external/           # Managed external repo clones
```

## Tech Stack

- **Frontend**: Reflex (formerly Pynecone)
- **ML Framework**: MLX (Apple's ML framework for Silicon)
- **Vector Search**: Integrating embeddings for code search
- **Storage**: SQLite for experiment tracking