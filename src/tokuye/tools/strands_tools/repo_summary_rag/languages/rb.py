from tokuye.tools.strands_tools.repo_summary_rag.languages.segmenter import \
    TreeSitterSegmenter


class RubySegmenter(TreeSitterSegmenter):
    """
    Ruby:
      - method / singleton_method / class / module
      - Capture leading comments (# ...)
    """

    line_comment_prefixes = ("#",)
    supports_block_comments = (
        False  # Ruby uses # only (==begin/==end is special but not supported in simple implementation)
    )

    def get_ts_language_name(self) -> str:
        return "ruby"

    def get_query(self) -> str:
        return r"""
        [
          (method)           @method
          (singleton_method) @method
          (class)            @class
          (module)           @module
        ]
        """.strip()
