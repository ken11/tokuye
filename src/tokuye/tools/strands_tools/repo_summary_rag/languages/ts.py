"""
TypeScript code segmentation using tree-sitter.

Based on langchain-community's language parsers:
https://github.com/langchain-ai/langchain-community (MIT License)
"""

from tokuye.tools.strands_tools.repo_summary_rag.languages.segmenter import \
    TreeSitterSegmenter


class TypeScriptSegmenter(TreeSitterSegmenter):
    """
    TypeScript:
      - Equivalent to JS + interface_declaration / type_alias_declaration
    """

    line_comment_prefixes = ("//",)
    supports_block_comments = True

    def get_ts_language_name(self) -> str:
        return "typescript"

    def get_query(self) -> str:
        return r"""
        [
          (function_declaration)                 @function
          (class_declaration)                    @class
          (method_definition)                    @method
          (interface_declaration)                @interface
          (type_alias_declaration)               @type_alias
        
          (lexical_declaration
            (variable_declarator
              name: (identifier)
              value: (function_expression)))     @var_function
        
          (lexical_declaration
            (variable_declarator
              name: (identifier)
              value: (arrow_function)))          @var_arrow
        
          (variable_declaration
            (variable_declarator
              name: (identifier)
              value: (function_expression)))     @var_function
        
          (variable_declaration
            (variable_declarator
              name: (identifier)
              value: (arrow_function)))          @var_arrow
        
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
        
          (export_default_declaration (function_expression))                       @export_default_function
          (export_default_declaration (class_declaration))                         @export_default_class
        ]
        """.strip()
