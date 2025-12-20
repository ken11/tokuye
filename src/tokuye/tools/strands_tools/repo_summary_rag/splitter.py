from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass
from typing import Callable, List, Literal, Optional, Tuple

Language = Literal["go", "javascript", "typescript", "python", "ruby"]


DEFAULT_SEPARATORS: List[str] = ["\n\n", "\n", " ", ""]


@dataclass(frozen=True)
class ChunkSpan:
    start_char: int
    end_char: int
    start_line: int  # 1-based, relative to given text
    end_line: int  # 1-based, relative to given text
    content: str


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


def _newline_positions(text: str) -> List[int]:
    return [i for i, ch in enumerate(text) if ch == "\n"]


def _line_of_index(newlines: List[int], idx: int) -> int:
    """Return the 1-based line number for the character at index idx."""
    return 1 + bisect_left(newlines, idx)


def _split_with_regex_spans(
    text: str, sep_pat: str, keep_separator: bool
) -> List[_Span]:
    """
    Split text using regex pattern and return spans.

    Args:
        text: Input text to split
        sep_pat: Separator pattern (regex)
        keep_separator: If True, separators are included at the start of the next span.
                       If False, separators are discarded.

    Returns:
        List of _Span objects representing non-empty segments.
        When keep_separator=True, spans are continuous with no gaps.
    """
    n = len(text)
    if n == 0:
        return []

    if not sep_pat:
        return [_Span(i, i + 1) for i in range(n)]

    matches = list(re.finditer(sep_pat, text))
    if not matches:
        return [_Span(0, n)]

    spans: List[_Span] = []

    if keep_separator:
        first_start = matches[0].start()
        if first_start > 0:
            spans.append(_Span(0, first_start))

        for i, m in enumerate(matches):
            start = m.start()
            next_start = matches[i + 1].start() if i + 1 < len(matches) else n
            spans.append(_Span(start, next_start))
    else:
        prev = 0
        for m in matches:
            if prev < m.start():
                spans.append(_Span(prev, m.start()))
            prev = m.end()
        if prev < n:
            spans.append(_Span(prev, n))

    return [sp for sp in spans if sp.start != sp.end]


class OffsetRecursiveSplitter:
    """
    Recursive text splitter with offset and line number tracking.

    Returns chunks as continuous slices with character offsets and line numbers.

    Features:
    - Language-specific separators for go/js/ts/py/rb
    - Falls back to DEFAULT_SEPARATORS for other cases
    - Returns chunks as continuous text[start:end] slices for accurate line tracking

    Args:
        language: Programming language for language-specific separators
        separators: Custom separator list (overrides language-specific ones)
        chunk_size: Maximum chunk size
        chunk_overlap: Overlap size between chunks
        keep_separator: Must be True for accurate offset tracking
        is_separator_regex: Whether separators are regex patterns
        length_function: Function to measure text length
    """

    def __init__(
        self,
        language: Optional[Language] = None,
        *,
        separators: Optional[List[str]] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        keep_separator: bool = True,
        is_separator_regex: bool = False,
        length_function: Callable[[str], int] = len,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if chunk_overlap > chunk_size:
            raise ValueError("chunk_overlap must be <= chunk_size")
        if keep_separator is not True:
            raise ValueError(
                "For accurate (start,end) slice chunks, keep_separator=True is required."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.keep_separator = keep_separator
        self.is_separator_regex = is_separator_regex
        self.length_function = length_function

        if separators is not None:
            self.separators = separators
        elif language is not None:
            self.separators = self.get_separators_for_language(language)
        else:
            self.separators = DEFAULT_SEPARATORS

    @staticmethod
    def get_separators_for_language(language: Language) -> List[str]:
        if language == "go":
            return [
                "\nfunc ",
                "\nvar ",
                "\nconst ",
                "\ntype ",
                "\nif ",
                "\nfor ",
                "\nswitch ",
                "\ncase ",
                "\n\n",
                "\n",
                " ",
                "",
            ]
        if language == "javascript":
            return [
                "\nfunction ",
                "\nconst ",
                "\nlet ",
                "\nvar ",
                "\nclass ",
                "\nif ",
                "\nfor ",
                "\nwhile ",
                "\nswitch ",
                "\ncase ",
                "\ndefault ",
                "\n\n",
                "\n",
                " ",
                "",
            ]
        if language == "typescript":
            return [
                "\nenum ",
                "\ninterface ",
                "\nnamespace ",
                "\ntype ",
                "\nclass ",
                "\nfunction ",
                "\nconst ",
                "\nlet ",
                "\nvar ",
                "\nif ",
                "\nfor ",
                "\nwhile ",
                "\nswitch ",
                "\ncase ",
                "\ndefault ",
                "\n\n",
                "\n",
                " ",
                "",
            ]
        if language == "python":
            return ["\nclass ", "\ndef ", "\n\tdef ", "\n\n", "\n", " ", ""]
        if language == "ruby":
            return [
                "\ndef ",
                "\nclass ",
                "\nif ",
                "\nunless ",
                "\nwhile ",
                "\nfor ",
                "\ndo ",
                "\nbegin ",
                "\nrescue ",
                "\n\n",
                "\n",
                " ",
                "",
            ]
        raise ValueError(f"unsupported language: {language}")

    def split_with_offsets(self, text: str) -> List[Tuple[int, int]]:
        """
        Split text and return character offsets.

        Returns:
            List of (start_char, end_char) tuples.
        """
        spans = self._split_text_spans(text, 0, len(text), self.separators)
        return [(sp.start, sp.end) for sp in spans]

    def split_with_lines(self, text: str) -> List[ChunkSpan]:
        """
        Split text and return chunks with line numbers.

        Returns:
            List of ChunkSpan objects with start/end positions and line numbers
            (relative to the input text).
        """
        newlines = _newline_positions(text)
        spans = self._split_text_spans(text, 0, len(text), self.separators)
        out: List[ChunkSpan] = []
        for sp in spans:
            if sp.start >= sp.end:
                continue
            start_line = _line_of_index(newlines, sp.start)
            last_idx = sp.end - 1 if sp.end > sp.start else sp.start
            end_line = _line_of_index(newlines, last_idx)
            out.append(
                ChunkSpan(
                    start_char=sp.start,
                    end_char=sp.end,
                    start_line=start_line,
                    end_line=end_line,
                    content=text[sp.start : sp.end],
                )
            )
        return out

    def _split_text_spans(
        self, text: str, base: int, end: int, separators: List[str]
    ) -> List[_Span]:
        """
        Recursively split text into spans.

        Process:
          1) Select appropriate separator from the list
          2) Split text using the separator
          3) Merge short splits together
          4) Recursively split oversized chunks with next separators

        Returns:
            List of _Span objects representing the final chunks.
        """
        if base >= end:
            return []

        sub = text[base:end]

        separator = separators[-1]
        new_separators: List[str] = []
        for i, s in enumerate(separators):
            if s == "":
                separator = s
                break
            pat = s if self.is_separator_regex else re.escape(s)
            if re.search(pat, sub):
                separator = s
                new_separators = separators[i + 1 :]
                break

        sep_pat = separator if self.is_separator_regex else re.escape(separator)

        local_spans = _split_with_regex_spans(sub, sep_pat, keep_separator=True)
        splits = [_Span(base + sp.start, base + sp.end) for sp in local_spans]

        final_chunks: List[_Span] = []
        good: List[_Span] = []

        for sp in splits:
            if self.length_function(text[sp.start : sp.end]) < self.chunk_size:
                good.append(sp)
                continue

            if good:
                final_chunks.extend(self._merge_spans(text, good))
                good = []

            if not new_separators:
                final_chunks.append(sp)
            else:
                final_chunks.extend(
                    self._split_text_spans(text, sp.start, sp.end, new_separators)
                )

        if good:
            final_chunks.extend(self._merge_spans(text, good))

        return final_chunks

    def _merge_spans(self, text: str, spans: List[_Span]) -> List[_Span]:
        """
        Merge spans into chunks with overlap.

        Returns:
            List of merged _Span objects with overlap between consecutive chunks.
        """
        docs: List[_Span] = []
        current: List[_Span] = []

        def cur_len(parts: List[_Span]) -> int:
            return sum(self.length_function(text[p.start : p.end]) for p in parts)

        for sp in spans:
            if not current:
                current.append(sp)
                continue

            if (
                cur_len(current) + self.length_function(text[sp.start : sp.end])
                > self.chunk_size
            ):
                docs.append(_Span(current[0].start, current[-1].end))

                while current and cur_len(current) > self.chunk_overlap:
                    current.pop(0)

                current.append(sp)
            else:
                current.append(sp)

        if current:
            docs.append(_Span(current[0].start, current[-1].end))

        return docs
