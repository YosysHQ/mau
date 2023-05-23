# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import sphinx.application

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "yosys-mau"
author = "YosysHQ GmbH"
copyright = "2023 YosysHQ GmbH"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autodoc",
    "sphinx.ext.todo",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = []
default_role = "any"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]

html_logo = "_static/logo.png"
html_favicon = "_static/favico.png"
html_css_files = ["custom.css"]

# code blocks style
pygments_style = "colorful"

html_theme_options = {
    "sidebar_hide_name": True,
    "light_css_variables": {
        "color-brand-primary": "#d6368f",
        "color-brand-content": "#4b72b8",
        "color-api-name": "#8857a3",
        "color-api-pre-name": "#4b72b8",
        "color-link": "#8857a3",
    },
    "dark_css_variables": {
        "color-brand-primary": "#e488bb",
        "color-brand-content": "#98bdff",
        "color-api-name": "#8857a3",
        "color-api-pre-name": "#4b72b8",
        "color-link": "#be95d5",
    },
}

# -- Options for autodoc -----------------------------------------------------

autodoc_typehints = "description"
autoclass_content = "both"
autodoc_member_order = "bysource"

# -- Options for intersphinx -------------------------------------------------

intersphinx_mapping = {
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
    "py": ("https://docs.python.org/3", None),
}

# -- Options for todo --------------------------------------------------------

todo_include_todos = True
todo_link_only = True

# -- setup -------------------------------------------------------------------


def setup(app: sphinx.application.Sphinx):
    import re
    from pathlib import Path

    from docutils import utils
    from docutils.parsers.rst import Directive, directives

    class ReadmeInclude(Directive):
        required_arguments = 1
        optional_arguments = 0
        final_argument_whitespace = True
        has_content = False
        option_spec = {
            "start-after": directives.unchanged,
            "end-before": directives.unchanged,
        }

        def run(self):
            path = directives.path(self.arguments[0])
            full_path = Path(self.state.document.current_source).parent / path
            document = utils.new_document(path, self.state.document.settings)
            parser = directives.parser_name("rst")()
            with full_path.open() as file:
                content = file.read()

            start_after = self.options.get("start-after", "")
            end_before = self.options.get("end-before", "")

            if start_after and start_after in content:
                content = content.split(start_after, 1)[1]
            if end_before and end_before in content:
                content = content.split(end_before, 1)[0]

            content = re.sub(
                r"^# (.*)$",
                lambda match: f"{match[1]}\n{'=' * len(match[1])}",
                content,
                flags=re.MULTILINE,
            )

            content = re.sub(
                r"^## (.*)$",
                lambda match: f"{match[1]}\n{'-' * len(match[1])}",
                content,
                flags=re.MULTILINE,
            )

            content = re.sub(
                r"(^    .*$\n?)+",
                lambda match: f".. code::\n\n{match[0]}",
                content,
                flags=re.MULTILINE,
            )

            parser.parse(content, document)
            document.transformer.populate_from_components((parser,))
            document.transformer.apply_transforms()
            return document.children

    app.add_directive("readme-include", ReadmeInclude)
