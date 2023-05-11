# Strings With Source Tracking

:::{autodoc} module yosys_mau.source_str
:::

The correspondence between the contents of a {py:class}`SourceStr` and the source file is stored in a {py:class}`SourceMap` which stores a collection of {py:class}`SourceMapSpan`s, each mapping a contiguous range of characters.

## Obtaining and Manipulating Source Strings

The easiest way to obtain a {py:class}`SourceStr` from a file is to use the {py:func}`read_file` function:

:::{autodoc} function read_file
:::

The {py:class}`SourceStr` class overrides some of the standard `str` methods to keep track of their contents.
For some standard python string operations this isn't possible though, and in that case alternative methods may be present.

There is also a {py:mod}`yosys_mau.source_str.re` module which provides the same API as the standard library's <inv:py#re> module, but with support for tracking sources when matching within {py:class}`SourceStr` objects.

:::{autodoc} class SourceStr
:members:
:special-members: __add__, __getitem__
:show-inheritance:
:::

## Inspecting String Sources

The correspondence between the contents of a {py:class}`SourceStr` and the source file is stored in a {py:class}`SourceMap` which stores a collection of {py:class}`SourceMapSpan`s.
The {py:class}`SourceMap` class inherits from {py:class}`SourceSpans` and {py:class}`SourceMapSpan` from {py:class}`SourceSpan`, where either super-class only stores the source spans without associating them to any specific string.
They are mostly used when generating diagnostic messages from source strings.

To obtain a {py:class}`SourceMap` from either {py:class}`SourceStr` or a plain `str`, use the {py:func}`source_map` function, which will return an empty mapping for a plain `str`:

:::{autodoc} function source_map
:::

:::{autodoc} class SourceMap
:members:
:show-inheritance:
:::

:::{autodoc} class SourceSpans
:members:
:::

:::{autodoc} class SourceMapSpan
:members:
:show-inheritance:
:::

:::{autodoc} class SourceSpan
:members:
:::

## Generating Diagnostics

:::{autodoc} module yosys_mau.source_str.report
:members:
:::

## Regular Expression Support

:::{autodoc} module yosys_mau.source_str.re
:members: compile, search, match, fullmatch, split, findall, finditer

The {py:mod}`yosys_mau.source_str.re` module provides the same API as the standard <inv:py#re> module, but with support for tracking sources when matching within {py:class}`SourceStr` objects.

Apart from the module contents listed her, this also re-exports the flags
constants defined by the standard <inv:py#re> module.
:::

:::{autodoc} class Pattern
:members:
:::

:::{autodoc} class Match
:members:
:special-members: __getitem__
:::

<!-- return back to the parent module -->
:::{py:module} yosys_mau.source_str
:noindex:
:::
