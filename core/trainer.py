"""MLX GPT-2 style transformer — trainable from scratch on Apple Silicon.

Configs:
  - tiny:  ~10M params (6 layers, 6 heads, 384 dim)  — debug speed
  - small: ~30M params (6 layers, 8 heads, 512 dim)  — fast experiments
  - base:  ~124M params (12 layers, 12 heads, 768 dim) — GPT-2 small
"""

import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np


# ---------------------------------------------------------------------------
# Model configs
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    name: str = "small"
    n_layers: int = 6
    n_heads: int = 8
    d_model: int = 512
    d_ff: int = 2048
    vocab_size: int = 256  # character-level by default
    max_seq_len: int = 256
    dropout: float = 0.1

    @property
    def n_params(self) -> int:
        # rough estimate
        embed = self.vocab_size * self.d_model + self.max_seq_len * self.d_model
        attn = self.n_layers * (4 * self.d_model * self.d_model)
        ffn = self.n_layers * (2 * self.d_model * self.d_ff)
        out = self.d_model * self.vocab_size
        return embed + attn + ffn + out


CONFIGS = {
    "tiny": ModelConfig(name="tiny", n_layers=6, n_heads=6, d_model=384, d_ff=1536),
    "small": ModelConfig(name="small", n_layers=6, n_heads=8, d_model=512, d_ff=2048),
    "base": ModelConfig(name="base", n_layers=12, n_heads=12, d_model=768, d_ff=3072),
}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class CausalSelfAttention(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.n_heads = cfg.n_heads
        self.d_model = cfg.d_model
        self.head_dim = cfg.d_model // cfg.n_heads

        self.qkv_proj = nn.Linear(cfg.d_model, 3 * cfg.d_model)
        self.out_proj = nn.Linear(cfg.d_model, cfg.d_model)

    def __call__(self, x: mx.array) -> mx.array:
        B, T, C = x.shape
        qkv = self.qkv_proj(x)
        q, k, v = mx.split(qkv, 3, axis=-1)

        q = q.reshape(B, T, self.n_heads, self.head_dim).transpose(0, 2, 1, 3)
        k = k.reshape(B, T, self.n_heads, self.head_dim).transpose(0, 2, 1, 3)
        v = v.reshape(B, T, self.n_heads, self.head_dim).transpose(0, 2, 1, 3)

        scale = math.sqrt(self.head_dim)
        attn = (q @ k.transpose(0, 1, 3, 2)) / scale

        # causal mask
        mask = mx.triu(mx.full((T, T), float("-inf")), k=1)
        attn = attn + mask

        attn = mx.softmax(attn, axis=-1)
        out = (attn @ v).transpose(0, 2, 1, 3).reshape(B, T, C)
        return self.out_proj(out)


class TransformerBlock(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.d_model)
        self.attn = CausalSelfAttention(cfg)
        self.ln2 = nn.LayerNorm(cfg.d_model)
        self.mlp = nn.Sequential(
            nn.Linear(cfg.d_model, cfg.d_ff),
            nn.GELU(),
            nn.Linear(cfg.d_ff, cfg.d_model),
        )

    def __call__(self, x: mx.array) -> mx.array:
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.pos_emb = nn.Embedding(cfg.max_seq_len, cfg.d_model)
        self.blocks = [TransformerBlock(cfg) for _ in range(cfg.n_layers)]
        self.ln_f = nn.LayerNorm(cfg.d_model)
        self.head = nn.Linear(cfg.d_model, cfg.vocab_size)

    def __call__(self, idx: mx.array) -> mx.array:
        B, T = idx.shape
        tok = self.tok_emb(idx)
        pos = self.pos_emb(mx.arange(T))
        x = tok + pos

        for block in self.blocks:
            x = block(x)

        x = self.ln_f(x)
        logits = self.head(x)
        return logits


# ---------------------------------------------------------------------------
# Data loading (character-level)
# ---------------------------------------------------------------------------

class CharDataset:
    def __init__(self, text: str, seq_len: int = 256):
        self.data = np.array([ord(c) % 256 for c in text], dtype=np.int32)
        self.seq_len = seq_len

    def __len__(self):
        return max(1, len(self.data) - self.seq_len - 1)

    def get_batch(self, batch_size: int) -> tuple[mx.array, mx.array]:
        idxs = np.random.randint(0, len(self), size=batch_size)
        x = np.stack([self.data[i : i + self.seq_len] for i in idxs])
        y = np.stack([self.data[i + 1 : i + self.seq_len + 1] for i in idxs])
        return mx.array(x), mx.array(y)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

@dataclass
class TrainResult:
    val_loss: float = float("inf")
    train_loss: float = float("inf")
    tok_per_sec: float = 0.0
    peak_memory_mb: float = 0.0
    wall_time_s: float = 0.0
    steps: int = 0
    config_name: str = ""
    n_params: int = 0
    checkpoint_path: str = ""


def load_data(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    return p.read_text(encoding="utf-8", errors="replace")


def train(
    config_name: str = "small",
    data_path: str = "data/shakespeare.txt",
    max_time_seconds: int = 180,
    batch_size: int = 32,
    learning_rate: float = 3e-4,
    eval_interval: int = 50,
    progress_callback=None,
) -> TrainResult:
    """Train a model for a fixed time budget. Returns results."""
    cfg = CONFIGS[config_name]
    result = TrainResult(config_name=config_name, n_params=cfg.n_params)

    # Load data
    text = load_data(data_path)
    split = int(len(text) * 0.9)
    train_data = CharDataset(text[:split], cfg.max_seq_len)
    val_data = CharDataset(text[split:], cfg.max_seq_len)

    # Model
    model = GPT(cfg)
    mx.eval(model.parameters())
    from mlx.utils import tree_flatten
    n_params = sum(p.size for _, p in tree_flatten(model.parameters()))
    result.n_params = n_params

    optimizer = optim.AdamW(learning_rate=learning_rate)

    def loss_fn(model, x, y):
        logits = model(x)
        loss = nn.losses.cross_entropy(
            logits.reshape(-1, cfg.vocab_size),
            y.reshape(-1),
        )
        return mx.mean(loss)

    loss_and_grad = nn.value_and_grad(model, loss_fn)

    # Training loop
    start = time.time()
    step = 0
    total_tokens = 0
    train_losses = []

    while True:
        elapsed = time.time() - start
        if elapsed >= max_time_seconds:
            break

        x, y = train_data.get_batch(batch_size)
        loss, grads = loss_and_grad(model, x, y)
        optimizer.update(model, grads)
        mx.eval(model.parameters(), optimizer.state)

        loss_val = loss.item()
        train_losses.append(loss_val)
        total_tokens += batch_size * cfg.max_seq_len
        step += 1

        if progress_callback and step % 10 == 0:
            progress_callback({
                "step": step,
                "train_loss": loss_val,
                "elapsed": elapsed,
                "tok_per_sec": total_tokens / max(elapsed, 0.01),
            })

        # Eval
        if step % eval_interval == 0:
            val_x, val_y = val_data.get_batch(batch_size * 4)
            val_loss = loss_fn(model, val_x, val_y)
            mx.eval(val_loss)
            result.val_loss = val_loss.item()

    # Final eval
    val_x, val_y = val_data.get_batch(batch_size * 4)
    val_loss = loss_fn(model, val_x, val_y)
    mx.eval(val_loss)

    end = time.time()
    result.val_loss = val_loss.item()
    result.train_loss = float(np.mean(train_losses[-50:])) if train_losses else float("inf")
    result.wall_time_s = end - start
    result.steps = step
    result.tok_per_sec = total_tokens / max(result.wall_time_s, 0.01)

    # Memory estimate (model params in float32 = 4 bytes each)
    result.peak_memory_mb = (n_params * 4 * 3) / (1024 * 1024)  # params + grads + optimizer ~3x

    # Save checkpoint
    import uuid
    import json as _json
    run_id = str(uuid.uuid4())[:8]
    ckpt_dir = Path("experiments") / "runs" / run_id
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Save model weights
    from mlx.utils import tree_flatten as _tree_flatten
    weights = dict(_tree_flatten(model.parameters()))
    mx.savez(str(ckpt_dir / "model.npz"), **weights)

    # Save config + results metadata
    meta = {
        "config_name": config_name,
        "n_layers": cfg.n_layers,
        "n_heads": cfg.n_heads,
        "d_model": cfg.d_model,
        "d_ff": cfg.d_ff,
        "vocab_size": cfg.vocab_size,
        "max_seq_len": cfg.max_seq_len,
        "n_params": n_params,
        "val_loss": result.val_loss,
        "train_loss": result.train_loss,
        "tok_per_sec": result.tok_per_sec,
        "steps": result.steps,
        "wall_time_s": result.wall_time_s,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
    }
    (ckpt_dir / "config.json").write_text(_json.dumps(meta, indent=2))

    result.checkpoint_path = str(ckpt_dir)

    return result


if __name__ == "__main__":
    import sys
    cfg_name = sys.argv[1] if len(sys.argv) > 1 else "tiny"
    time_s = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    def cb(info):
        print(f"  step {info['step']:4d} | loss {info['train_loss']:.4f} | {info['tok_per_sec']:.0f} tok/s")

    print(f"Training {cfg_name} for {time_s}s...")
    r = train(config_name=cfg_name, max_time_seconds=time_s, progress_callback=cb)
    print(f"\nDone: val_loss={r.val_loss:.4f}, tok/s={r.tok_per_sec:.0f}, steps={r.steps}")
