from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

# tree-sitter & tree_sitter_languages は動的に使用
try:
    from tree_sitter import Parser  # type: ignore
    from tree_sitter_languages import get_language  # type: ignore

    TS_AVAILABLE = True
except Exception:  # pragma: no cover
    TS_AVAILABLE = False


@dataclass
class CodeSegment:
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive
    text: str


class CodeSegmenter:
    """Abstract base class for extracting logical blocks like functions/classes from code strings."""

    def __init__(self, code: str):
        self.code = code
        self.source_lines = code.splitlines()

    def is_valid(self) -> bool:
        """Check if syntactically valid. Implementations for unsupported languages can return True."""
        return True

    def extract_functions_classes(self) -> List[CodeSegment]:
        """Extract and return logical blocks like functions/classes."""
        raise NotImplementedError


class TreeSitterSegmenter(CodeSegmenter):
    """
    tree-sitter based segmenter.
    - is_valid=False if (ERROR) node exists
    - Implement get_ts_language_name() and get_query() in language-specific classes
    - Capture preceding comments/blank lines as prefix
    """

    # Settings for language-specific comment detection
    line_comment_prefixes: Tuple[str, ...] = ()
    supports_block_comments: bool = False

    def __init__(self, code: str):
        super().__init__(code)
        if not TS_AVAILABLE:
            raise ImportError(
                "tree_sitter / tree_sitter_languages required. "
                "pip install tree-sitter tree-sitter-languages"
            )
        self._parser = Parser()
        self._parser.set_language(get_language(self.get_ts_language_name()))

    def get_ts_language_name(self) -> str:
        raise NotImplementedError

    def get_query(self) -> str:
        raise NotImplementedError

    def is_valid(self) -> bool:
        # Detect (ERROR) node
        lang = get_language(self.get_ts_language_name())
        error_query = lang.query("(ERROR) @err")
        tree = self._parser.parse(self.code.encode("utf-8"))
        return len(error_query.captures(tree.root_node)) == 0

    def extract_functions_classes(self) -> List[CodeSegment]:
        lang = get_language(self.get_ts_language_name())
        query = lang.query(self.get_query())
        tree = self._parser.parse(self.code.encode("utf-8"))

        processed_lines: set[int] = set()
        segs: List[CodeSegment] = []

        for node, _name in query.captures(tree.root_node):
            s0 = node.start_point[0]
            e0 = node.end_point[0]
            lines_range = range(s0, e0 + 1)
            if any(l in processed_lines for l in lines_range):
                continue

            # Capture preceding comments/blank lines (and block comments if needed)
            s0_adj = self._expand_leading_trivia(s0)

            # Create segment
            text = "\n".join(self.source_lines[s0_adj : e0 + 1])
            segs.append(CodeSegment(start_line=s0_adj + 1, end_line=e0 + 1, text=text))
            processed_lines.update(range(s0_adj, e0 + 1))

        # Return entire file if nothing found (assuming upper-level splitting)
        if not segs:
            segs.append(CodeSegment(1, len(self.source_lines), self.code))

        return segs

    def _expand_leading_trivia(self, start_idx0: int) -> int:
        i = start_idx0 - 1
        in_block = False
        while i >= 0:
            line = self.source_lines[i]
            stripped = line.strip()

            if stripped == "":
                i -= 1
                continue

            # Block comment processing (/* ... */)
            if self.supports_block_comments:
                if in_block:
                    # Capture until block closes
                    if "/*" in stripped:
                        in_block = False
                    i -= 1
                    continue
                else:
                    if stripped.endswith("*/") or "*/" in stripped:
                        in_block = True
                        i -= 1
                        continue

            # Line comments (//, #, etc.)
            if self._is_line_comment(stripped):
                i -= 1
                continue

            break

        return i + 1

    def _is_line_comment(self, stripped: str) -> bool:
        return any(stripped.startswith(p) for p in self.line_comment_prefixes)
