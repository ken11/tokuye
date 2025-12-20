from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, List, Optional

import faiss
import numpy as np
from tokuye.utils.config import settings

from . import embedder

logger = logging.getLogger(__name__)

INDEX: Optional[faiss.IndexIDMap2] = None
CHUNK_BY_ID: Dict[int, Dict] = {}
NEXT_ID: int = 0
LAST_GENERATED_AT: str = ""


def _tokuye_dir() -> str:
    return os.path.join(settings.project_root, ".tokuye")


def _index_path() -> str:
    return os.path.join(_tokuye_dir(), "faiss.index")


def _chunks_meta_path() -> str:
    return os.path.join(_tokuye_dir(), "faiss-chunks.json")


def _timestamp_path() -> str:
    return os.path.join(_tokuye_dir(), "repo-summary-timestamp.txt")


def _ensure_dir():
    os.makedirs(_tokuye_dir(), exist_ok=True)


def _new_index_ip_idmap(dim: int) -> faiss.IndexIDMap2:
    base = faiss.IndexFlatIP(dim)  # Equivalent to cosine assuming normalize=True
    return faiss.IndexIDMap2(base)


def _get_index_dim() -> Optional[int]:
    """Return vector dimension of INDEX (from inside IDMap2)"""
    if INDEX is None:
        return None
    # Assuming inner Flat is in IDMap2.index
    inner = getattr(INDEX, "index", None)
    if inner is not None and hasattr(inner, "d"):
        return int(inner.d)
    # Just in case
    if hasattr(INDEX, "d"):
        return int(INDEX.d)
    return None


def _ids_selector(ids: List[int]) -> faiss.IDSelectorBatch:
    return faiss.IDSelectorBatch(np.asarray(ids, dtype=np.int64))


def save_index(generated_at: str):
    global LAST_GENERATED_AT
    if INDEX is None:
        logger.warning("save_index: INDEX is None; nothing to save.")
        return
    _ensure_dir()
    faiss.write_index(INDEX, _index_path())

    meta_list = []
    for cid, meta in CHUNK_BY_ID.items():
        m = dict(meta)
        m["id"] = cid
        meta_list.append(m)
    with open(_chunks_meta_path(), "w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False)

    with open(_timestamp_path(), "w", encoding="utf-8") as f:
        f.write(generated_at or "")

    LAST_GENERATED_AT = generated_at or ""

    logger.info(
        "Saved FAISS index: vectors=%s, files=%s, generatedAt=%s",
        INDEX.ntotal,
        len({m["path"] for m in CHUNK_BY_ID.values()}),
        LAST_GENERATED_AT,
    )


def _load_index() -> bool:
    """Load saved index (ignoring freshness). Returns True on success."""
    global INDEX, CHUNK_BY_ID, NEXT_ID, LAST_GENERATED_AT
    t0 = time.perf_counter()
    try:
        if not os.path.exists(_index_path()):
            logger.info("No index file found at %s", _index_path())
            return False

        idx = faiss.read_index(_index_path())
        if not isinstance(idx, faiss.IndexIDMap2):
            idx = faiss.IndexIDMap2(idx)
        INDEX = idx

        with open(_chunks_meta_path(), "r", encoding="utf-8") as f:
            meta_list = json.load(f)
        CHUNK_BY_ID = {
            int(m["id"]): {k: v for k, v in m.items() if k != "id"}
            for m in meta_list
        }
        NEXT_ID = (max(CHUNK_BY_ID.keys()) + 1) if CHUNK_BY_ID else 0

        try:
            with open(_timestamp_path(), "r", encoding="utf-8") as f:
                LAST_GENERATED_AT = f.read().strip()
        except Exception:
            LAST_GENERATED_AT = ""

        t1 = time.perf_counter()
        logger.info(
            "Loaded FAISS index: vectors=%s, files=%s, generatedAt=%s (%.2fs)",
            INDEX.ntotal,
            len({m["path"] for m in CHUNK_BY_ID.values()}),
            LAST_GENERATED_AT,
            t1 - t0,
        )
        return True
    except Exception as e:
        logger.exception("Failed to load FAISS index: %s", e)
        INDEX = None
        CHUNK_BY_ID = {}
        NEXT_ID = 0
        LAST_GENERATED_AT = ""
        return False


def load_index_if_fresh(current_generated_at: str | None) -> bool:
    """
    Load if saved generatedAt matches current.
    Return False if not matched (caller should rebuild/update diff).
    """
    if not os.path.exists(_index_path()):
        return False
    ok = _load_index()
    if not ok:
        return False
    fresh = (current_generated_at or "") == (LAST_GENERATED_AT or "")
    logger.info(
        "Fresh check: current=%s saved=%s -> %s",
        current_generated_at,
        LAST_GENERATED_AT,
        "fresh" if fresh else "stale",
    )
    return fresh


def try_load() -> bool:
    """Try to load if it exists, regardless of freshness."""
    return _load_index()


def build_index(chunks: List[Dict], generated_at: str | None) -> Dict:
    """
    Build new IDMap index with received chunks (overwrite).
    Returns: statistics
    """
    global INDEX, CHUNK_BY_ID, NEXT_ID
    t0 = time.perf_counter()
    CHUNK_BY_ID = {}
    NEXT_ID = 0

    if not chunks:
        INDEX = _new_index_ip_idmap(embedder.EMBED_DIM)
        save_index(generated_at or "")
        logger.warning("Build index: no chunks provided; created empty index.")
        return {"total_chunks": 0, "dim": embedder.EMBED_DIM, "built_in_sec": 0.0}

    logger.info("Build index: embedding %d chunks...", len(chunks))
    vecs = []
    ids = []
    metas = []
    for ch in chunks:
        emb = embedder.get_embedding(ch["content"])
        v = np.asarray(emb, dtype=np.float32)
        vecs.append(v)
        cid = NEXT_ID
        ids.append(cid)
        metas.append((cid, ch))
        NEXT_ID += 1

    mat = np.vstack(vecs)
    dim = int(mat.shape[1])
    INDEX = _new_index_ip_idmap(dim)
    INDEX.add_with_ids(mat, np.asarray(ids, dtype=np.int64))
    for cid, meta in metas:
        CHUNK_BY_ID[cid] = meta

    save_index(generated_at or "")
    t1 = time.perf_counter()
    logger.info(
        "Build index completed: vectors=%s, dim=%s, files=%s (%.2fs)",
        INDEX.ntotal,
        dim,
        len({m["path"] for m in CHUNK_BY_ID.values()}),
        t1 - t0,
    )
    return {
        "total_chunks": len(chunks),
        "dim": dim,
        "built_in_sec": round(t1 - t0, 3),
    }


def add_chunks(new_chunks: List[Dict]) -> int:
    """Add chunks and return number of assigned chunks."""
    global INDEX, CHUNK_BY_ID, NEXT_ID
    if not new_chunks:
        return 0

    t0 = time.perf_counter()
    # Embed all first to determine dimension
    vecs = []
    ids = []
    metas = []
    for ch in new_chunks:
        emb = embedder.get_embedding(ch["content"])
        vecs.append(np.asarray(emb, dtype=np.float32))
        cid = NEXT_ID
        ids.append(cid)
        metas.append((cid, ch))
        NEXT_ID += 1

    mat = np.vstack(vecs)
    dim = int(mat.shape[1])

    if INDEX is None:
        INDEX = _new_index_ip_idmap(dim)
    else:
        cur_dim = _get_index_dim()
        if cur_dim is not None and cur_dim != dim:
            # ベクトル次元が途中で変わるのは運用上ありえない前提
            raise ValueError(
                f"Embedding dimension mismatch: current {cur_dim} vs new {dim}"
            )

    INDEX.add_with_ids(mat, np.asarray(ids, dtype=np.int64))
    for cid, meta in metas:
        CHUNK_BY_ID[cid] = meta

    t1 = time.perf_counter()
    logger.info(
        "Added chunks: %d (vectors now %s) in %.2fs",
        len(new_chunks),
        INDEX.ntotal if INDEX else 0,
        t1 - t0,
    )
    return len(new_chunks)


def remove_by_ids(ids: List[int]) -> int:
    """Remove specified IDs and return number of deletions."""
    global INDEX, CHUNK_BY_ID
    if not ids:
        return 0
    if INDEX is None:
        return 0

    t0 = time.perf_counter()
    selector = _ids_selector(ids)
    before = INDEX.ntotal
    INDEX.remove_ids(selector)
    for cid in ids:
        CHUNK_BY_ID.pop(cid, None)
    after = INDEX.ntotal
    removed = max(0, before - after)

    t1 = time.perf_counter()
    logger.info("Removed chunks: %d (vectors now %s) in %.2fs", removed, after, t1 - t0)
    return removed


def update_index_diff(latest_chunks: List[Dict], new_generated_at: str | None) -> Dict:
    """
    Take diff between existing index and latest chunks, execute additions/deletions.
    - Update judgment per file (presence of path and mtime difference)
    - For updated files: delete all old chunks of that file → add all new chunks
    Returns: statistics (added/removed/churn, etc.)
    """
    t0 = time.perf_counter()

    if INDEX is None:
        # Full build if no existing index
        stats = build_index(latest_chunks, new_generated_at or "")
        return {"action": "build", **stats}

    # Old: mtime per file (maximum)
    old_file_mtime: Dict[str, float] = {}
    for meta in CHUNK_BY_ID.values():
        p = meta["path"]
        mt = float(meta.get("mtime", 0))
        if p not in old_file_mtime or mt > old_file_mtime[p]:
            old_file_mtime[p] = mt
    old_files = set(old_file_mtime.keys())

    # New: mtime per file (maximum)
    new_file_mtime: Dict[str, float] = {}
    for ch in latest_chunks:
        p = ch["path"]
        mt = float(ch.get("mtime", 0))
        if p not in new_file_mtime or mt > new_file_mtime[p]:
            new_file_mtime[p] = mt
    new_files = set(new_file_mtime.keys())

    added_files = new_files - old_files
    removed_files = old_files - new_files
    maybe_updated = new_files & old_files
    updated_files = {
        p for p in maybe_updated if new_file_mtime[p] != old_file_mtime[p]
    }

    files_to_remove = removed_files | updated_files
    files_to_add = added_files | updated_files

    # Collect IDs to remove
    ids_to_remove: List[int] = [
        cid for cid, meta in CHUNK_BY_ID.items() if meta["path"] in files_to_remove
    ]

    removed_vecs = remove_by_ids(ids_to_remove)
    chunks_to_add = [ch for ch in latest_chunks if ch["path"] in files_to_add]
    added_vecs = add_chunks(chunks_to_add)

    save_index(new_generated_at or "")
    t1 = time.perf_counter()

    logger.info(
        "Diff update: files +%d ~%d -%d | vectors +%d -%d => total=%s (%.2fs)",
        len(added_files),
        len(updated_files),
        len(removed_files),
        added_vecs,
        removed_vecs,
        INDEX.ntotal if INDEX is not None else 0,
        t1 - t0,
    )

    return {
        "action": "update",
        "files": {
            "added": len(added_files),
            "removed": len(removed_files),
            "updated": len(updated_files),
        },
        "vectors": {
            "removed": removed_vecs,
            "added": added_vecs,
            "total": INDEX.ntotal if INDEX is not None else 0,
        },
        "updated_in_sec": round(t1 - t0, 3),
    }


def search(query_vec: List[float], top_k: int) -> List[Dict]:
    """FAISS search (inner product). Returns list of chunk metadata dictionaries."""
    if INDEX is None or INDEX.ntotal == 0:
        logger.info("Search: index is empty.")
        return []
    q = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)
    k = min(top_k, INDEX.ntotal)
    D, I = INDEX.search(q, k)
    out: List[Dict] = []
    for cid in I[0]:
        if cid == -1:
            continue
        meta = CHUNK_BY_ID.get(int(cid))
        if meta:
            out.append(meta)
    logger.info("Search: top_k=%d -> hits=%d", top_k, len(out))
    return out


def status() -> Dict:
    files = set(m["path"] for m in CHUNK_BY_ID.values())
    dim = _get_index_dim() or embedder.EMBED_DIM
    return {
        "ntotal": INDEX.ntotal if INDEX is not None else 0,
        "nids": len(CHUNK_BY_ID),
        "nfiles": len(files),
        "generated_at": LAST_GENERATED_AT,
        "dim": dim,
    }
