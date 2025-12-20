from __future__ import annotations

import logging
import time

from strands import tool
from tokuye.tools.strands_tools.repo_summary_rag.data_loader import \
    parse_repository
from tokuye.tools.strands_tools.repo_summary_rag.vector_store import (
    build_index, load_index_if_fresh, status, try_load, update_index_diff)

logger = logging.getLogger(__name__)


@tool(
    name="manage_code_index",
    description="Manage FAISS index for code search. Supports build, update (differential), and rebuild operations.",
)
def manage_code_index(action: str = "update") -> str:
    """Manage FAISS index for code search

    Args:
        action: Action to perform
            - "build": Build new if doesn't exist (do nothing if existing and fresh)
            - "update": Differential update (detect and apply additions/updates/deletions)
            - "rebuild": Force full rebuild (discard existing and recreate)

    Returns:
        Summary string of execution result (details also output in logs)
    """
    t0 = time.perf_counter()
    action = (action or "update").lower()
    logger.info("manage_code_index start: action=%s", action)

    try:
        chunks, generated_at = parse_repository()
        logger.info(
            "Repository parsed: chunks=%d, generatedAt=%s",
            len(chunks),
            generated_at,
        )

        if action == "build":
            if load_index_if_fresh(generated_at or ""):
                st = status()
                msg = (
                    "✅ Existing index is up-to-date, no build needed.\n"
                    f"- vectors: {st['ntotal']}, files: {st['nfiles']}, generated_at: {st['generated_at']}"
                )
                logger.info("BUILD skipped (fresh). %s", msg.replace("\n", " "))
                return msg

            stats = build_index(chunks, generated_at or "")
            st = status()
            msg = (
                "🆕 New index built.\n"
                f"- vectors: {st['ntotal']} (dim={st['dim']}), files: {st['nfiles']}, generated_at: {st['generated_at']}\n"
                f"- built_in_sec: {stats.get('built_in_sec')}"
            )
            logger.info("BUILD done. %s", msg.replace("\n", " "))
            return msg

        elif action == "update":
            if not try_load():
                stats = build_index(chunks, generated_at or "")
                st = status()
                msg = (
                    "🆕 Built new index as no existing index found.\n"
                    f"- vectors: {st['ntotal']} (dim={st['dim']}), files: {st['nfiles']}, generated_at: {st['generated_at']}\n"
                    f"- built_in_sec: {stats.get('built_in_sec')}"
                )
                logger.info("UPDATE -> BUILD (no existing). %s", msg.replace("\n", " "))
                return msg

            stats = update_index_diff(chunks, generated_at or "")
            st = status()
            msg = (
                "🔄 Differential update completed.\n"
                f"- files: +{stats['files']['added']} / ~{stats['files']['updated']} / -{stats['files']['removed']}\n"
                f"- vectors: +{stats['vectors']['added']} / -{stats['vectors']['removed']} / total={stats['vectors']['total']}\n"
                f"- generated_at: {st['generated_at']}\n"
                f"- updated_in_sec: {stats.get('updated_in_sec')}"
            )
            logger.info("UPDATE done. %s", msg.replace("\n", " "))
            return msg

        elif action == "rebuild":
            stats = build_index(chunks, generated_at or "")
            st = status()
            msg = (
                "♻️ Forced full rebuild completed.\n"
                f"- vectors: {st['ntotal']} (dim={st['dim']}), files: {st['nfiles']}, generated_at: {st['generated_at']}\n"
                f"- built_in_sec: {stats.get('built_in_sec')}"
            )
            logger.info("REBUILD done. %s", msg.replace("\n", " "))
            return msg

        else:
            logger.error("Invalid action: %s", action)
            return "❌ action must be one of 'build' | 'update' | 'rebuild'."

    except FileNotFoundError as e:
        logger.exception("manage_code_index: repo-summary.xml missing.")
        return f"❌ repo-summary.xml not found: {e}"
    except Exception as e:
        logger.exception("manage_code_index: unexpected error.")
        return f"❌ Error: {e}"
    finally:
        t1 = time.perf_counter()
        logger.info("manage_code_index end: action=%s (%.2fs)", action, t1 - t0)
