"""Hardware detection for Apple Silicon."""

import platform
import subprocess
from dataclasses import dataclass, field


@dataclass
class HardwareProfile:
    chip: str = "Unknown"
    memory_gb: float = 0.0
    cpu_cores: int = 0
    gpu_cores: int = 0
    mlx_available: bool = False
    mlx_device: str = "cpu"
    os_version: str = ""
    python_version: str = ""
    is_apple_silicon: bool = False

    @property
    def max_trainable_params_m(self) -> int:
        """Rough estimate: how many million params can we train from scratch.

        Rule of thumb: training needs ~4x model size in memory (params + grads + optimizer + activations).
        So 64GB -> ~16GB for model -> ~4B params in fp16, but we leave headroom.
        Conservative: memory_gb * 25M params (leaves room for data, OS, etc.)
        """
        return int(self.memory_gb * 25)

    @property
    def recommended_model_config(self) -> str:
        if self.memory_gb >= 48:
            return "124M (GPT-2 small) — fast iterations, room for larger later"
        elif self.memory_gb >= 24:
            return "30M (GPT-2 nano) — quick experiments"
        else:
            return "10M (tiny) — constrained but workable"


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return ""


def detect() -> HardwareProfile:
    """Detect hardware capabilities of this machine."""
    profile = HardwareProfile()

    # CPU
    profile.chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if not profile.chip:
        profile.chip = platform.processor() or "Unknown"

    # Memory
    mem_bytes = _run(["sysctl", "-n", "hw.memsize"])
    if mem_bytes:
        profile.memory_gb = round(int(mem_bytes) / (1024 ** 3), 1)

    # CPU cores
    cores = _run(["sysctl", "-n", "hw.ncpu"])
    if cores:
        profile.cpu_cores = int(cores)

    # GPU cores (from system_profiler)
    sp_output = _run(["system_profiler", "SPDisplaysDataType"])
    for line in sp_output.splitlines():
        if "Total Number of Cores" in line:
            try:
                profile.gpu_cores = int(line.split(":")[-1].strip())
            except ValueError:
                pass

    # Apple Silicon check
    profile.is_apple_silicon = "Apple" in profile.chip or platform.machine() == "arm64"

    # MLX
    try:
        import mlx.core as mx
        profile.mlx_available = True
        dev = str(mx.default_device())
        # e.g. "device(gpu, 0)" -> "gpu"
        if "gpu" in dev:
            profile.mlx_device = "gpu"
        elif "cpu" in dev:
            profile.mlx_device = "cpu"
        else:
            profile.mlx_device = dev
    except ImportError:
        profile.mlx_available = False
        profile.mlx_device = "unavailable"

    # OS + Python
    profile.os_version = platform.platform()
    profile.python_version = platform.python_version()

    return profile


if __name__ == "__main__":
    p = detect()
    print(f"Chip:       {p.chip}")
    print(f"Memory:     {p.memory_gb} GB")
    print(f"CPU cores:  {p.cpu_cores}")
    print(f"GPU cores:  {p.gpu_cores}")
    print(f"MLX:        {p.mlx_device}")
    print(f"Max train:  ~{p.max_trainable_params_m}M params")
    print(f"Recommend:  {p.recommended_model_config}")
