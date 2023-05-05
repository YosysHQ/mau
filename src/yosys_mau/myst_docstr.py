"""MyST Docstrings for Sphinx autodoc

This module provides MyST docstrings for the Sphinx [autodoc] extension. It [registers] an
`autodoc-process-docstring` event handler (as is done by [napoleon]). This event handler processes
MyST docstrings and it defines two directives {rst:dir}`inline-doc` and {rst:dir}`autodoc`. The
{rst:dir}`inline-doc` directive is used by the docstring processing event handler so it can include
MyST content in the reStructuredText document that autodoc generates. The {rst:dir}`autodoc`
directive switches parsing to reStructuredText, as expected by autodoc and then just invokes the
corresponding `auto*` directive.

[autodoc]: inv:sphinx#usage/extensions/autodoc

[napoleon]: inv:sphinx#usage/extensions/napoleon

[registers]: inv:sphinx#sphinx.application.Sphinx.connect

:::{rst:directive} inline-doc

This directive allows including content that uses a different parser within the same document. It
takes one optional argument which is the path the content pretends to be from. If it's not given,
the current document's path is used.

::::{rst:directive:option} parser

The `parser` option specifies how the content is parsed. Using `myst_parser.sphinx_` switches to
MyST parsing and `rst` switches to reStructuredText parsing. Overall, it supports the same values as
the [`include`] directive's `parser` option.

[`include`]:https://docutils.sourceforge.io/docs/ref/rst/directives.html\
#including-an-external-document-fragment

::::
:::


:::{rst:directive} autodoc

This directive switches parsing to reStructuredText, which is required to use any of autodoc's
`auto*` directives. It takes two required arguments: the first is the name of the autodoc directive
to use without the `auto` prefix and the second argument is forwarded to the corresponding `auto*`
directive.

It also forwards all options as well as the content to the corresponding `auto*` directive. The
content is automatically wrapped in an {rst:dir}`inline-doc` to switch the parsing back to MyST.

:::

"""

from __future__ import annotations

from typing import Any, Callable

import sphinx
from docutils import utils
from docutils.nodes import Node
from docutils.parsers.rst import Directive, directives
from sphinx.application import Sphinx


class InlineDoc(Directive):
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True
    option_spec = {
        "parser": directives.parser_name,
    }

    def run(self) -> list[Node]:
        if self.arguments:
            path = directives.path(self.arguments[0])
        else:
            path = f"{self.state.document.current_source}/_inline_doc_{self.lineno}"
        document = utils.new_document(path, self.state.document.settings)
        parser = self.options["parser"]()
        parser.parse("\n".join(self.content), document)
        document.transformer.populate_from_components((parser,))
        document.transformer.apply_transforms()
        return document.children


class _ForwardOptions:
    def __getitem__(self, key) -> Callable[[str], Any]:
        return directives.unchanged


class Autodoc(Directive):
    required_arguments = 2
    final_argument_whitespace = True
    has_content = True

    option_spec = _ForwardOptions()

    def run(self) -> list[Node]:
        path = f"{self.state.document.current_source}/_autodoc_{self.lineno}"
        document = utils.new_document(path, self.state.document.settings)
        parser = directives.parser_name("rst")()
        parser.parse(
            "\n".join(
                [
                    f".. auto{self.arguments[0]}:: {self.arguments[1]}",
                    *(f"  :{option}: {value}" for option, value in self.options.items()),
                    "",
                    "  .. inline-doc::",
                    "    :parser: myst_parser.sphinx_",
                    "",
                    *(f"    {line}" for line in self.content),
                ]
            ),
            document,
        )
        document.transformer.populate_from_components((parser,))
        document.transformer.apply_transforms()
        return document.children


def setup(app: Sphinx) -> dict[str, Any]:
    app.add_directive("inline-doc", InlineDoc)
    app.add_directive("autodoc", Autodoc)
    app.connect("autodoc-process-docstring", _process_docstring)

    return {"version": sphinx.__display_version__, "parallel_read_safe": True}


def _process_docstring(
    app: Sphinx, what: str, name: str, obj: Any, options: Any, lines: list[str]
) -> None:
    app.config

    lines[:] = [
        f".. inline-doc:: _myst_docstr/{what}/{name}",
        "  :parser: myst_parser.sphinx_",
        "",
        *(f"  {line}" for line in lines),
    ]
