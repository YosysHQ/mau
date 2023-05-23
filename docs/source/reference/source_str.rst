Strings With Source Tracking
============================

.. automodule:: yosys_mau.source_str

The correspondence between the contents of a `SourceStr` and the source file is stored in a `SourceMap` which stores a collection of `SourceMapSpan`\ s, each mapping a contiguous range of characters.

Obtaining and Manipulating Source Strings
-----------------------------------------

The easiest way to obtain a `SourceStr` from a file is to use the `read_file` function:

.. autofunction:: read_file

The `SourceStr` class overrides some of the standard `str` methods to keep track of their contents.
For some standard python string operations this isn't possible though, and in that case alternative methods may be present.

There is also a `yosys_mau.source_str.re` module which provides the same API as the standard library's :external:mod:`re` module, but with support for tracking sources when matching within `SourceStr` objects.

.. autoclass:: SourceStr
  :members:
  :special-members: __add__, __getitem__
  :show-inheritance:

Inspecting String Sources
-------------------------

The correspondence between the contents of a `SourceStr` and the source file is stored in a `SourceMap` which stores a collection of `SourceMapSpan`\ s.
The `SourceMap` class inherits from `SourceSpan`\ s and `SourceMapSpan` from `SourceSpan`, where either super-class only stores the source spans without associating them to any specific string.
They are mostly used when generating diagnostic messages from source strings.

To obtain a `SourceMap` from either `SourceStr` or a plain `str`, use the `source_map` function, which will return an empty mapping for a plain `str`:

.. autofunction:: source_map


.. autoclass:: SourceMap
  :members:
  :show-inheritance:


.. autoclass:: SourceSpans
  :members:


.. autoclass:: SourceMapSpan
  :members:
  :show-inheritance:


.. autoclass:: SourceSpan
  :members:


Generating Diagnostics
----------------------

.. automodule:: yosys_mau.source_str.report
  :members:


Regular Expression Support
--------------------------

.. automodule:: yosys_mau.source_str.re
  :members: compile, search, match, fullmatch, split, findall, finditer

  The `yosys_mau.source_str.re` module provides the same API as the standard :external:mod:`re` module, but with support for tracking sources when matching within `SourceStr` objects.

  Apart from the module contents listed her, this also re-exports the flags
  constants defined by the standard :external:mod:`re` module.


.. autoclass:: Pattern
  :members:

.. autoclass:: Match
  :members:
  :special-members: __getitem__

