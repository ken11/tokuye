from tokuye.tools.strands_tools.repo_summary_rag.languages.segmenter import \
    TreeSitterSegmenter


class GoSegmenter(TreeSitterSegmenter):
    """
    Go:
      - function_declaration
      - method_declaration
      - type_declaration (struct/interface/type in general)
    """

    line_comment_prefixes = ("//",)
    supports_block_comments = True

    def get_ts_language_name(self) -> str:
        return "go"

    def get_query(self) -> str:
        # Also capture type_declaration as there is no class equivalent
        return r"""
        [
          (function_declaration) @function
          (method_declaration)   @method
          (type_declaration)     @type
        ]
        """.strip()
