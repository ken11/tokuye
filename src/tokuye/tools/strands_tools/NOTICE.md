# Attribution Notices

This directory contains code derived from or inspired by the following open-source projects:

---

## langchain-community

**Repository**: https://github.com/langchain-ai/langchain-community  
**License**: MIT License  
**Copyright**: © LangChain

### Affected Files

The following files are derived from or substantially inspired by langchain-community's implementation:

- **`file_management.py`**  
  File management toolkit (file_search, copy_file, move_file, file_delete, list_directory, read_lines, write_file)  
  Based on: `langchain-community/tools/file_management/`

- **`repo_summary_rag/languages/segmenter.py`**  
  Code segmentation base classes (CodeSegmenter, TreeSitterSegmenter)  
  Based on: `langchain-community/document_loaders/parsers/language/`

- **`repo_summary_rag/languages/py.py`**  
  Python code segmentation using AST  
  Based on: `langchain-community/document_loaders/parsers/language/python.py`

- **`repo_summary_rag/languages/js.py`**  
  JavaScript code segmentation using tree-sitter  
  Based on: `langchain-community/document_loaders/parsers/language/javascript.py`

- **`repo_summary_rag/languages/ts.py`**  
  TypeScript code segmentation using tree-sitter  
  Based on: `langchain-community/document_loaders/parsers/language/typescript.py`

- **`repo_summary_rag/languages/go.py`**  
  Go code segmentation using tree-sitter  
  Based on: `langchain-community/document_loaders/parsers/language/go.py`

- **`repo_summary_rag/languages/rb.py`**  
  Ruby code segmentation using tree-sitter  
  Based on: `langchain-community/document_loaders/parsers/language/ruby.py`

### MIT License (langchain-community)

```
MIT License

Copyright (c) 2024 LangChain

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## langchain (text-splitters)

**Repository**: https://github.com/langchain-ai/langchain  
**License**: MIT License  
**Copyright**: © LangChain

### Affected Files

The following files are derived from or substantially inspired by langchain's text-splitters implementation:

- **`repo_summary_rag/splitter.py`**  
  Recursive text splitter with offset and line number tracking  
  Based on: `libs/text-splitters/langchain_text_splitters/character.py`

### MIT License (langchain)

```
MIT License

Copyright (c) LangChain, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Note**: This is from the main langchain repository, specifically the text-splitters package, which is separate from langchain-community.

---

## Repomix

**Repository**: https://github.com/yamadashy/repomix  
**License**: MIT License  
**Copyright**: © Kazuki Yamada

### Affected Files

- **`repo_summary.py`**  
  Repository summarization logic (file collection, gitignore handling, XML generation)  
  Inspired by: Repomix's core repository packing functionality

### MIT License (Repomix)

```
Copyright 2024 Kazuki Yamada

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

---

## Modifications

All derived code has been modified and adapted for use in Tokuye:
- Integration with Strands framework
- Custom error handling and validation
- Additional features and optimizations
- Adaptation to Tokuye's architecture and requirements

We are grateful to the maintainers and contributors of these projects for their excellent work.
