"""External repository management — clone, track, detect capabilities."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


REGISTRY_PATH = Path("registry/repos.yaml")
EXTERNAL_DIR = Path("external")


@dataclass
class RepoSpec:
    name: str
    url: str
    description: str = ""
    stack_layer: str = ""
    capabilities: list[str] = field(default_factory=list)
    min_memory_gb: float = 0
    models: list[str] = field(default_factory=list)
    maintainer: str = ""
    is_cloned: bool = False
    local_path: str = ""
    current_branch: str = ""
    last_commit: str = ""


def load_registry() -> dict[str, dict]:
    """Load the known repos registry."""
    if not REGISTRY_PATH.exists():
        return {}
    with open(REGISTRY_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("repos", {})


def list_available() -> list[RepoSpec]:
    """List all known repos from registry, with clone status."""
    registry = load_registry()
    specs = []
    for name, info in registry.items():
        local_path = EXTERNAL_DIR / name
        is_cloned = (local_path / ".git").exists()

        branch = ""
        commit = ""
        if is_cloned:
            branch = _git(local_path, ["rev-parse", "--abbrev-ref", "HEAD"])
            commit = _git(local_path, ["log", "-1", "--format=%h %s"])

        specs.append(RepoSpec(
            name=name,
            url=info.get("url", ""),
            description=info.get("description", ""),
            stack_layer=info.get("stack_layer", ""),
            capabilities=info.get("capabilities", []),
            min_memory_gb=info.get("min_memory_gb", 0),
            models=info.get("models", []),
            maintainer=info.get("maintainer", ""),
            is_cloned=is_cloned,
            local_path=str(local_path) if is_cloned else "",
            current_branch=branch,
            last_commit=commit,
        ))
    return specs


def list_cloned() -> list[RepoSpec]:
    """List only repos that are cloned locally."""
    return [r for r in list_available() if r.is_cloned]


def clone_repo(name: str) -> tuple[bool, str]:
    """Clone a repo from registry into external/. Returns (success, message)."""
    registry = load_registry()
    if name not in registry:
        return False, f"Unknown repo: {name}. Available: {list(registry.keys())}"

    url = registry[name]["url"]
    dest = EXTERNAL_DIR / name

    if (dest / ".git").exists():
        return True, f"{name} already cloned at {dest}"

    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return True, f"Cloned {name} into {dest}"
        return False, f"Clone failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Clone timed out (120s)"
    except Exception as e:
        return False, str(e)


def update_repo(name: str) -> tuple[bool, str]:
    """Pull latest for a cloned repo."""
    dest = EXTERNAL_DIR / name
    if not (dest / ".git").exists():
        return False, f"{name} is not cloned"

    result = _git(dest, ["pull", "--ff-only"])
    return True, result or "Up to date"


def remove_repo(name: str) -> tuple[bool, str]:
    """Remove a cloned repo."""
    import shutil
    dest = EXTERNAL_DIR / name
    if not dest.exists():
        return False, f"{name} is not cloned"
    shutil.rmtree(dest)
    return True, f"Removed {name}"


def get_all_capabilities(memory_gb: float = 0) -> dict[str, list[str]]:
    """Get unified capability map from all cloned repos, filtered by hardware."""
    capabilities = {}
    for repo in list_cloned():
        if memory_gb and repo.min_memory_gb > memory_gb:
            capabilities[repo.name] = [f"Requires {repo.min_memory_gb}GB (you have {memory_gb}GB)"]
        else:
            capabilities[repo.name] = repo.capabilities
    return capabilities


def get_readme(name: str) -> str:
    """Read a repo's README for context."""
    dest = EXTERNAL_DIR / name
    for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
        readme_path = dest / readme_name
        if readme_path.exists():
            return readme_path.read_text(errors="replace")[:5000]
    return "(No README found)"


def _git(path: Path, args: list[str]) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(path)] + args,
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout.strip()
    except Exception:
        return ""
