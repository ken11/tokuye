"""
JavaScript code segmentation using tree-sitter.

Based on langchain-community's language parsers:
https://github.com/langchain-ai/langchain-community (MIT License)
"""

from tokuye.tools.strands_tools.repo_summary_rag.languages.segmenter import \
    TreeSitterSegmenter


class JavaScriptSegmenter(TreeSitterSegmenter):
    """
    JavaScript:
      - function_declaration / class_declaration / method_definition
      - Assignment-style functions: const f = function() {} / const f = () => {}
      - Also supports export modifiers
    """

    line_comment_prefixes = ("//",)
    supports_block_comments = True

    def get_ts_language_name(self) -> str:
        return "javascript"

    def get_query(self) -> str:
        # Covers assignment forms/exports (including var/let/const, export default)
        return r"""
        [
          (function_declaration)                 @function
          (class_declaration)                    @class
          (method_definition)                    @method
        
          ;; Function/arrow function assignment with const/let
          (lexical_declaration
            (variable_declarator
              name: (identifier)
              value: (function_expression)))     @var_function
        
          (lexical_declaration
            (variable_declarator
              name: (identifier)
              value: (arrow_function)))          @var_arrow
        
          ;; Function/arrow function assignment with var
          (variable_declaration
            (variable_declarator
              name: (identifier)
              value: (function_expression)))     @var_function
        
          (variable_declaration
            (variable_declarator
              name: (identifier)
              value: (arrow_function)))          @var_arrow
        
          ;; With export
          (export_statement (function_declaration))                                @export_function
          (export_statement declaration: (class_declaration))                      @export_class
          (export_statement declaration:
            (lexical_declaration
              (variable_declarator
                name: (identifier)
                value: (function_expression))))                                    @export_var_function
          (export_statement declaration:
            (lexical_declaration
              (variable_declarator
                name: (identifier)
                value: (arrow_function))))                                         @export_var_arrow
        
          ;; export default
          (export_default_declaration (function_expression))                       @export_default_function
          (export_default_declaration (class_declaration))                         @export_default_class
        ]
        """.strip()
