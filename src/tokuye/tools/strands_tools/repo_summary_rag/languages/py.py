"""
Python code segmentation using AST.

Based on langchain-community's language parsers:
https://github.com/langchain-ai/langchain-community (MIT License)
"""

import ast
from typing import List

from tokuye.tools.strands_tools.repo_summary_rag.languages.segmenter import (
    CodeSegment, CodeSegmenter)


class PythonSegmenter(CodeSegmenter):
    """
    Python: Extract FunctionDef / AsyncFunctionDef / ClassDef with AST.
    - Extend start line to include decorators (@...)
    - Also capture preceding consecutive comments/blank lines
    """

    def is_valid(self) -> bool:
        try:
            ast.parse(self.code)
            return True
        except SyntaxError:
            return False

    def extract_functions_classes(self) -> List[CodeSegment]:
        tree = ast.parse(self.code)
        segs: List[CodeSegment] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 1) - 1
                end = getattr(node, "end_lineno", None)
                if end is None:
                    # Fallback for Python < 3.8 compatibility
                    end = self._infer_end_line(node)
                # Include decorator lines
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.decorator_list
                ):
                    first_dec = min(d.lineno for d in node.decorator_list) - 1
                    start = min(start, first_dec)

                # Capture preceding consecutive comments/blank lines
                start = self._expand_leading_comments(start)

                text = "\n".join(self.source_lines[start:end])
                segs.append(CodeSegment(start + 1, end, text))

        if not segs:
            segs.append(CodeSegment(1, len(self.source_lines), self.code))

        return segs

    def _infer_end_line(self, node: ast.AST) -> int:
        # Rough estimation (look at end_lineno of last child node)
        end = getattr(node, "lineno", 1)
        for child in ast.iter_child_nodes(node):
            end = max(end, getattr(child, "end_lineno", getattr(child, "lineno", end)))
        return end

    def _expand_leading_comments(self, start_idx0: int) -> int:
        i = start_idx0 - 1
        while i >= 0:
            stripped = self.source_lines[i].strip()
            if stripped == "" or stripped.startswith("#"):
                i -= 1
                continue
            break
        return i + 1
