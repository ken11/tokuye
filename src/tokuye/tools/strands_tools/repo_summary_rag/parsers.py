from typing import List, Optional

from tokuye.tools.strands_tools.repo_summary_rag.languages.go import GoSegmenter
from tokuye.tools.strands_tools.repo_summary_rag.languages.js import \
    JavaScriptSegmenter
from tokuye.tools.strands_tools.repo_summary_rag.languages.py import \
    PythonSegmenter
from tokuye.tools.strands_tools.repo_summary_rag.languages.rb import \
    RubySegmenter
from tokuye.tools.strands_tools.repo_summary_rag.languages.segmenter import (
    CodeSegment, CodeSegmenter)
from tokuye.tools.strands_tools.repo_summary_rag.languages.ts import \
    TypeScriptSegmenter

try:
    from tree_sitter import Parser  # type: ignore
    from tree_sitter_languages import get_language  # type: ignore

    TS_AVAILABLE = True
except Exception:  # pragma: no cover
    TS_AVAILABLE = False


# =========================
# 利用ヘルパ
# =========================

EXT_TO_LANG = {
    ".go": "go",
    ".py": "python",
    ".rb": "ruby",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


def guess_language_from_path(path: str) -> Optional[str]:
    p = path.lower()
    for ext, lang in EXT_TO_LANG.items():
        if p.endswith(ext):
            return lang
    return None


def get_segmenter_for_language(lang: str, code: str) -> CodeSegmenter:
    if lang == "python":
        return PythonSegmenter(code)
    if not TS_AVAILABLE:
        # Fallback: entire file only
        return CodeSegmenter(code)
    if lang == "go":
        return GoSegmenter(code)
    if lang == "javascript":
        return JavaScriptSegmenter(code)
    if lang == "typescript":
        return TypeScriptSegmenter(code)
    if lang == "ruby":
        return RubySegmenter(code)
    # Unsupported: return entire file for upper-level splitting
    return CodeSegmenter(code)


def segment_code_by_path(code: str, path: str) -> (str, List[CodeSegment]):
    lang = guess_language_from_path(path) or "plain"
    seg = get_segmenter_for_language(lang, code)
    # Return entire file if syntactically invalid or tree-sitter ERROR
    try:
        if not seg.is_valid():
            return lang, [CodeSegment(1, len(code.splitlines()), code)]
    except Exception:
        return lang, [CodeSegment(1, len(code.splitlines()), code)]
    try:
        parts = seg.extract_functions_classes()
        return lang, parts if parts else [CodeSegment(1, len(code.splitlines()), code)]
    except Exception:
        return lang, [CodeSegment(1, len(code.splitlines()), code)]
