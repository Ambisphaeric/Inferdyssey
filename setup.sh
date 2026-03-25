#!/bin/bash
set -e

echo "================================================"
echo "  InferDyssey — Research OS Setup"
echo "================================================"
echo ""

# --- Check macOS + Apple Silicon ---
if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: InferDyssey requires macOS with Apple Silicon."
    exit 1
fi

ARCH=$(uname -m)
if [[ "$ARCH" != "arm64" ]]; then
    echo "WARNING: Expected arm64 (Apple Silicon), got $ARCH. MLX may not work."
fi

# --- Detect hardware ---
CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
MEM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
MEM_GB=$((MEM_BYTES / 1073741824))
echo "Hardware: $CHIP | ${MEM_GB}GB unified memory"
echo ""

# --- Install UV if missing ---
if ! command -v uv &> /dev/null; then
    echo "Installing UV (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo ""
fi

echo "UV version: $(uv --version)"

# --- Create venv + install deps ---
echo ""
echo "Installing dependencies..."
uv sync
echo ""

# --- Download Shakespeare dataset if missing ---
if [ ! -f "data/shakespeare.txt" ]; then
    echo "Downloading Shakespeare dataset (~1MB)..."
    mkdir -p data
    curl -sL "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt" \
        -o data/shakespeare.txt
    echo "Dataset ready: $(wc -c < data/shakespeare.txt | tr -d ' ') bytes"
fi

echo ""

# --- Check for OPENROUTER_API_KEY ---
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "NOTE: No OPENROUTER_API_KEY found in environment."
    echo "You can set it in the Settings page of the app."
    echo "Get a key at: https://openrouter.ai/keys"
else
    echo "OpenRouter API key detected."
fi

echo ""
echo "================================================"
echo "  Setup complete!"
echo ""
echo "  To start InferDyssey:"
echo "    uv run streamlit run app.py"
echo ""
echo "  Or for quick hardware test:"
echo "    uv run python core/hardware.py"
echo "================================================"
