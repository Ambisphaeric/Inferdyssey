"""zvec-powered semantic code search across external repos."""

import ast
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

INDEX_DIR = Path("data/zvec_index")
META_PATH = INDEX_DIR / "_meta.json"

# File extensions to index
CODE_EXTENSIONS = {".py", ".c", ".cpp", ".h", ".metal", ".swift", ".m"}
DOC_EXTENSIONS = {".md", ".rst", ".txt"}
ALL_EXTENSIONS = CODE_EXTENSIONS | DOC_EXTENSIONS

EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"

# Chunking parameters
MAX_SINGLE_CHUNK_LINES = 100
FIXED_CHUNK_LINES = 50
FIXED_CHUNK_OVERLAP = 10
MAX_FUNCTION_LINES = 100


def _get_model():
    """Lazy-load sentence-transformers model."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def _chunk_python_file(text: str, repo: str, rel_path: str) -> list[dict]:
    """Chunk a Python file by AST (functions/classes), with fallback."""
    lines = text.split("\n")
    if len(lines) <= MAX_SINGLE_CHUNK_LINES:
        return [{"repo": repo, "file": rel_path, "start_line": 1,
                 "end_line": len(lines), "text": f"# {repo}/{rel_path}\n{text}"}]

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _chunk_fixed(text, repo, rel_path)

    chunks = []
    covered = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start + 1)
            chunk_lines = lines[start:end]

            if len(chunk_lines) > MAX_FUNCTION_LINES:
                # Split large functions into overlapping sub-chunks
                for i in range(0, len(chunk_lines), FIXED_CHUNK_LINES - FIXED_CHUNK_OVERLAP):
                    sub = chunk_lines[i:i + FIXED_CHUNK_LINES]
                    if sub:
                        chunk_text = "\n".join(sub)
                        chunks.append({
                            "repo": repo, "file": rel_path,
                            "start_line": start + i + 1,
                            "end_line": start + i + len(sub),
                            "text": f"# {repo}/{rel_path}\n{chunk_text}",
                        })
                        covered.update(range(start + i, start + i + len(sub)))
            else:
                chunk_text = "\n".join(chunk_lines)
                chunks.append({
                    "repo": repo, "file": rel_path,
                    "start_line": start + 1, "end_line": end,
                    "text": f"# {repo}/{rel_path}\n{chunk_text}",
                })
                covered.update(range(start, end))

    # Capture module-level code not inside any function/class
    uncovered = []
    for i, line in enumerate(lines):
        if i not in covered and line.strip():
            uncovered.append((i, line))

    if uncovered:
        # Group consecutive uncovered lines
        groups = []
        current_group = [uncovered[0]]
        for j in range(1, len(uncovered)):
            if uncovered[j][0] - uncovered[j - 1][0] <= 2:
                current_group.append(uncovered[j])
            else:
                if len(current_group) >= 3:
                    groups.append(current_group)
                current_group = [uncovered[j]]
        if len(current_group) >= 3:
            groups.append(current_group)

        for group in groups:
            chunk_text = "\n".join(line for _, line in group)
            chunks.append({
                "repo": repo, "file": rel_path,
                "start_line": group[0][0] + 1,
                "end_line": group[-1][0] + 1,
                "text": f"# {repo}/{rel_path}\n{chunk_text}",
            })

    return chunks if chunks else _chunk_fixed(text, repo, rel_path)


def _chunk_fixed(text: str, repo: str, rel_path: str) -> list[dict]:
    """Fixed-size overlapping chunks for non-Python or fallback."""
    lines = text.split("\n")
    if len(lines) <= MAX_SINGLE_CHUNK_LINES:
        return [{"repo": repo, "file": rel_path, "start_line": 1,
                 "end_line": len(lines), "text": f"# {repo}/{rel_path}\n{text}"}]

    chunks = []
    step = FIXED_CHUNK_LINES - FIXED_CHUNK_OVERLAP
    for i in range(0, len(lines), step):
        chunk_lines = lines[i:i + FIXED_CHUNK_LINES]
        if chunk_lines:
            chunk_text = "\n".join(chunk_lines)
            chunks.append({
                "repo": repo, "file": rel_path,
                "start_line": i + 1,
                "end_line": i + len(chunk_lines),
                "text": f"# {repo}/{rel_path}\n{chunk_text}",
            })
    return chunks


def _collect_files(external_dir: Path) -> list[tuple[str, Path]]:
    """Collect all indexable files from external repos. Returns (repo_name, path) pairs."""
    files = []
    if not external_dir.exists():
        return files
    for repo_dir in sorted(external_dir.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name.startswith("."):
            continue
        repo_name = repo_dir.name
        for fpath in repo_dir.rglob("*"):
            if fpath.suffix in ALL_EXTENSIONS and fpath.is_file():
                # Skip hidden dirs, __pycache__, node_modules, .git
                parts = fpath.relative_to(repo_dir).parts
                if any(p.startswith(".") or p == "__pycache__" or p == "node_modules" for p in parts):
                    continue
                files.append((repo_name, fpath))
    return files


class ZvecIndex:
    """Semantic code search index using zvec + sentence-transformers."""

    def __init__(self, index_dir: str | Path = INDEX_DIR):
        self.index_dir = Path(index_dir)
        self._model = None
        self._collection = None
        self._chunk_meta: list[dict] = []  # id -> metadata mapping

    def _load_model(self):
        if self._model is None:
            self._model = _get_model()
        return self._model

    def _open_collection(self):
        if self._collection is not None:
            return self._collection
        import zvec
        if not self.index_dir.exists():
            return None
        try:
            self._collection = zvec.open_collection(path=str(self.index_dir))
            # Load metadata
            if META_PATH.exists():
                self._chunk_meta = json.loads(META_PATH.read_text())
            return self._collection
        except Exception:
            return None

    def build(self, external_dir: str | Path = "external", progress_callback=None):
        """Build the vector index from all files in external repos.

        Args:
            external_dir: Path to the external/ directory with cloned repos.
            progress_callback: Optional callable(stage: str, current: int, total: int)
        """
        import zvec

        external_dir = Path(external_dir)

        # Collect files
        if progress_callback:
            progress_callback("Collecting files", 0, 0)
        files = _collect_files(external_dir)
        if not files:
            return {"files": 0, "chunks": 0}

        # Chunk all files
        if progress_callback:
            progress_callback("Chunking files", 0, len(files))
        all_chunks = []
        for i, (repo, fpath) in enumerate(files):
            try:
                text = fpath.read_text(errors="replace")
            except Exception:
                continue
            rel_path = str(fpath.relative_to(external_dir))
            if fpath.suffix == ".py":
                chunks = _chunk_python_file(text, repo, rel_path)
            else:
                chunks = _chunk_fixed(text, repo, rel_path)
            all_chunks.extend(chunks)
            if progress_callback and i % 50 == 0:
                progress_callback("Chunking files", i, len(files))

        if not all_chunks:
            return {"files": 0, "chunks": 0}

        # Embed all chunks
        if progress_callback:
            progress_callback("Generating embeddings", 0, len(all_chunks))
        model = self._load_model()
        texts = [c["text"] for c in all_chunks]
        embeddings = model.encode(texts, batch_size=64, show_progress_bar=False)

        # Clear old index
        if self.index_dir.exists():
            shutil.rmtree(self.index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Create zvec collection
        schema = zvec.CollectionSchema(
            name="code_chunks",
            vectors=[
                zvec.VectorSchema(
                    name="embedding",
                    dimension=EMBEDDING_DIM,
                ),
            ],
        )
        collection = zvec.create_collection(schema=schema, path=str(self.index_dir))

        # Insert in batches
        if progress_callback:
            progress_callback("Indexing vectors", 0, len(all_chunks))

        chunk_meta = []
        batch_size = 500
        for batch_start in range(0, len(all_chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(all_chunks))
            docs = []
            for i in range(batch_start, batch_end):
                doc_id = f"chunk_{i}"
                docs.append(zvec.Doc(
                    id=doc_id,
                    vectors={"embedding": embeddings[i].tolist()},
                ))
                chunk_meta.append({
                    "id": doc_id,
                    "repo": all_chunks[i]["repo"],
                    "file": all_chunks[i]["file"],
                    "start_line": all_chunks[i]["start_line"],
                    "end_line": all_chunks[i]["end_line"],
                    "text": all_chunks[i]["text"][:500],  # truncate for storage
                })
            collection.insert(docs)
            if progress_callback:
                progress_callback("Indexing vectors", batch_end, len(all_chunks))

        collection.optimize()

        # Save metadata as JSON (zvec STRING fields would work too,
        # but sidecar JSON is simpler for arbitrary text)
        meta_file = self.index_dir / "_meta.json"
        meta_file.write_text(json.dumps(chunk_meta))

        # Save build info
        build_info = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "total_files": len(files),
            "total_chunks": len(all_chunks),
            "repos": list(set(r for r, _ in files)),
        }
        (self.index_dir / "_build_info.json").write_text(json.dumps(build_info, indent=2))

        self._collection = collection
        self._chunk_meta = chunk_meta

        return {"files": len(files), "chunks": len(all_chunks)}

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """Search for code chunks semantically similar to the query.

        Returns list of dicts with keys: repo, file, start_line, end_line, text, score
        """
        import zvec

        collection = self._open_collection()
        if collection is None or not self._chunk_meta:
            return []

        model = self._load_model()
        query_vec = model.encode(query).tolist()

        results = collection.query(
            zvec.VectorQuery(
                field_name="embedding",
                vector=query_vec,
                limit=top_k,
            ),
        )

        # Map results back to metadata
        meta_by_id = {m["id"]: m for m in self._chunk_meta}
        hits = []
        for r in results:
            doc_id = r["id"] if isinstance(r, dict) else r.id
            score = r["score"] if isinstance(r, dict) else r.score
            meta = meta_by_id.get(doc_id)
            if meta:
                hits.append({
                    "repo": meta["repo"],
                    "file": meta["file"],
                    "start_line": meta["start_line"],
                    "end_line": meta["end_line"],
                    "text": meta["text"],
                    "score": float(score),
                })
        return hits

    def status(self) -> dict:
        """Return index status info."""
        info_path = self.index_dir / "_build_info.json"
        if not info_path.exists():
            return {"built": False, "total_files": 0, "total_chunks": 0,
                    "built_at": "", "repos": []}
        info = json.loads(info_path.read_text())
        info["built"] = True
        return info
