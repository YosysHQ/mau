# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

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
    "myst_parser",
    "yosys_mau.myst_docstr",
]

templates_path = ["_templates"]
exclude_patterns = []

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

# -- Options for myst --------------------------------------------------------

myst_enable_extensions = ["colon_fence", "fieldlist"]

# -- Options for intersphinx -------------------------------------------------

intersphinx_mapping = {
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
    "py": ("https://docs.python.org/3", None),
}

# -- Options for todo --------------------------------------------------------

todo_include_todos = True
todo_link_only = True

# -- setup -------------------------------------------------------------------


def setup(app):
    app.connect("autodoc-process-docstring", process_docstring, priority=1)


# -- docstring processing ----------------------------------------------------


# def field_doc_helper(x: T) -> T:
#     first, *rest = getattr(x, "__doc__", "").split("\n", 1)
#     doc = first + "".join(map(textwrap.dedent, rest))

#     for name, value in getattr(x, "__field_doc__", {}).items():
#         doc += f"\n\n:::{{autodoc}} attribute {name}\n{textwrap.dedent(value)}\n:::\n"

#     x.__doc__ = doc
#     return x


def process_docstring(app, what, name, obj, options, lines):
    import textwrap
    # For modules, remove everything before the first empty line
    if what == "module":
        try:
            lines[: lines.index("")] = []
        except ValueError:
            pass

    if hasattr(obj, "__field_doc__"):
        for name, value in obj.__field_doc__.items():
            lines.extend(
                [
                    f":::{{autodoc}} attribute {name}",
                    *textwrap.dedent(value).splitlines(),
                    ":::",
                ]
            )
