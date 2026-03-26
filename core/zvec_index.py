"""zvec-powered semantic code search across external repos."""

import ast
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import zvec
from zvec import (
    CollectionSchema, DataType, Doc, FieldSchema, VectorQuery, VectorSchema,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = _PROJECT_ROOT / "data" / "zvec_index"
EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"

# File extensions to index
CODE_EXTENSIONS = {".py", ".c", ".cpp", ".h", ".metal", ".swift", ".m"}
DOC_EXTENSIONS = {".md", ".rst", ".txt"}
ALL_EXTENSIONS = CODE_EXTENSIONS | DOC_EXTENSIONS

# Chunking parameters
MAX_SINGLE_CHUNK_LINES = 100
FIXED_CHUNK_LINES = 50
FIXED_CHUNK_OVERLAP = 10
MAX_FUNCTION_LINES = 100

_model_cache = None


def _get_model():
    global _model_cache
    if _model_cache is None:
        from sentence_transformers import SentenceTransformer
        _model_cache = SentenceTransformer(MODEL_NAME)
    return _model_cache


def _chunk_python_file(text: str, repo: str, rel_path: str) -> list[dict]:
    """Chunk a Python file by AST (functions/classes), with fallback."""
    lines = text.split("\n")
    prefix = f"# {repo}/{rel_path}\n"

    if len(lines) <= MAX_SINGLE_CHUNK_LINES:
        return [{"repo": repo, "file": rel_path, "start_line": 1,
                 "end_line": len(lines), "text": prefix + text}]

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _chunk_fixed(text, repo, rel_path)

    chunks = []
    covered = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = node.lineno - 1
        end = getattr(node, "end_lineno", start + 1)
        chunk_lines = lines[start:end]

        if len(chunk_lines) > MAX_FUNCTION_LINES:
            step = FIXED_CHUNK_LINES - FIXED_CHUNK_OVERLAP
            for i in range(0, len(chunk_lines), step):
                sub = chunk_lines[i:i + FIXED_CHUNK_LINES]
                if sub:
                    chunks.append({
                        "repo": repo, "file": rel_path,
                        "start_line": start + i + 1,
                        "end_line": start + i + len(sub),
                        "text": prefix + "\n".join(sub),
                    })
                    covered.update(range(start + i, start + i + len(sub)))
        else:
            chunks.append({
                "repo": repo, "file": rel_path,
                "start_line": start + 1, "end_line": end,
                "text": prefix + "\n".join(chunk_lines),
            })
            covered.update(range(start, end))

    # Module-level code not inside any function/class
    uncovered = [(i, line) for i, line in enumerate(lines)
                 if i not in covered and line.strip()]
    if uncovered:
        groups, current = [], [uncovered[0]]
        for j in range(1, len(uncovered)):
            if uncovered[j][0] - uncovered[j - 1][0] <= 2:
                current.append(uncovered[j])
            else:
                if len(current) >= 3:
                    groups.append(current)
                current = [uncovered[j]]
        if len(current) >= 3:
            groups.append(current)
        for group in groups:
            chunks.append({
                "repo": repo, "file": rel_path,
                "start_line": group[0][0] + 1,
                "end_line": group[-1][0] + 1,
                "text": prefix + "\n".join(line for _, line in group),
            })

    return chunks if chunks else _chunk_fixed(text, repo, rel_path)


def _chunk_fixed(text: str, repo: str, rel_path: str) -> list[dict]:
    """Fixed-size overlapping chunks for non-Python or fallback."""
    lines = text.split("\n")
    prefix = f"# {repo}/{rel_path}\n"

    if len(lines) <= MAX_SINGLE_CHUNK_LINES:
        return [{"repo": repo, "file": rel_path, "start_line": 1,
                 "end_line": len(lines), "text": prefix + text}]

    chunks = []
    step = FIXED_CHUNK_LINES - FIXED_CHUNK_OVERLAP
    for i in range(0, len(lines), step):
        chunk_lines = lines[i:i + FIXED_CHUNK_LINES]
        if chunk_lines:
            chunks.append({
                "repo": repo, "file": rel_path,
                "start_line": i + 1,
                "end_line": i + len(chunk_lines),
                "text": prefix + "\n".join(chunk_lines),
            })
    return chunks


def _collect_files(external_dir: Path) -> list[tuple[str, Path]]:
    """Collect all indexable files from external repos."""
    files = []
    if not external_dir.exists():
        return files
    skip = {".git", "__pycache__", "node_modules", ".eggs", "dist"}
    for repo_dir in sorted(external_dir.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name.startswith("."):
            continue
        for fpath in repo_dir.rglob("*"):
            if fpath.suffix in ALL_EXTENSIONS and fpath.is_file():
                parts = fpath.relative_to(repo_dir).parts
                if not any(p in skip or p.startswith(".") for p in parts):
                    files.append((repo_dir.name, fpath))
    return files


def _make_schema() -> CollectionSchema:
    return CollectionSchema(
        name="code_chunks",
        vectors=VectorSchema("embedding", DataType.VECTOR_FP32, dimension=EMBEDDING_DIM),
        fields=[
            FieldSchema("repo", DataType.STRING),
            FieldSchema("file", DataType.STRING),
            FieldSchema("start_line", DataType.INT32),
            FieldSchema("end_line", DataType.INT32),
            FieldSchema("text", DataType.STRING),
        ],
    )


class ZvecIndex:
    """Semantic code search index using zvec + sentence-transformers."""

    def __init__(self, index_dir: str | Path = INDEX_DIR):
        self.index_dir = Path(index_dir)
        self._collection = None

    def _open(self):
        if self._collection is not None:
            return self._collection
        if not self.index_dir.exists():
            return None
        try:
            self._collection = zvec.open(path=str(self.index_dir))
            return self._collection
        except Exception:
            return None

    def build(self, external_dir: str | Path = _PROJECT_ROOT / "external"):
        """Build the vector index from all files in external repos."""
        external_dir = Path(external_dir)
        files = _collect_files(external_dir)
        if not files:
            return {"files": 0, "chunks": 0}

        # Chunk all files
        all_chunks = []
        for repo, fpath in files:
            try:
                text = fpath.read_text(errors="replace")
            except Exception:
                continue
            rel_path = str(fpath.relative_to(external_dir))
            if fpath.suffix == ".py":
                all_chunks.extend(_chunk_python_file(text, repo, rel_path))
            else:
                all_chunks.extend(_chunk_fixed(text, repo, rel_path))

        if not all_chunks:
            return {"files": 0, "chunks": 0}

        # Embed all chunks
        model = _get_model()
        texts = [c["text"] for c in all_chunks]
        embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

        # Clear old index — zvec.create_and_open needs a non-existing path
        if self.index_dir.exists():
            shutil.rmtree(self.index_dir)
        self.index_dir.parent.mkdir(parents=True, exist_ok=True)

        collection = zvec.create_and_open(schema=_make_schema(), path=str(self.index_dir))

        # Insert in batches
        batch_size = 500
        for batch_start in range(0, len(all_chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(all_chunks))
            docs = []
            for i in range(batch_start, batch_end):
                docs.append(Doc(
                    id=str(i),
                    vectors={"embedding": embeddings[i].tolist()},
                    fields={
                        "repo": all_chunks[i]["repo"],
                        "file": all_chunks[i]["file"],
                        "start_line": all_chunks[i]["start_line"],
                        "end_line": all_chunks[i]["end_line"],
                        "text": all_chunks[i]["text"][:1000],
                    },
                ))
            collection.insert(docs)

        collection.optimize()

        # Save build info
        build_info = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "total_files": len(files),
            "total_chunks": len(all_chunks),
            "repos": sorted(set(r for r, _ in files)),
        }
        (self.index_dir / "_build_info.json").write_text(json.dumps(build_info, indent=2))

        self._collection = collection
        return {"files": len(files), "chunks": len(all_chunks)}

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """Semantic search. Returns list of {repo, file, start_line, end_line, text, score}."""
        collection = self._open()
        if collection is None:
            return []

        model = _get_model()
        query_vec = model.encode(query).tolist()

        results = collection.query(
            vectors=VectorQuery("embedding", vector=query_vec),
            topk=top_k,
            output_fields=["repo", "file", "start_line", "end_line", "text"],
        )

        return [
            {
                "repo": doc.fields.get("repo", ""),
                "file": doc.fields.get("file", ""),
                "start_line": doc.fields.get("start_line", 0),
                "end_line": doc.fields.get("end_line", 0),
                "text": doc.fields.get("text", ""),
                "score": float(doc.score) if doc.score is not None else 0.0,
            }
            for doc in results
        ]

    def status(self) -> dict:
        """Return index status info."""
        info_path = self.index_dir / "_build_info.json"
        if not info_path.exists():
            return {"built": False, "total_files": 0, "total_chunks": 0,
                    "built_at": "", "repos": []}
        info = json.loads(info_path.read_text())
        info["built"] = True
        return info
