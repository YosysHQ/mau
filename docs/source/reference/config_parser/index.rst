Configuration File Parsing
==========================

.. automodule:: yosys_mau.config_parser

The configuration file parsing API is split into the following parts:

* :doc:`A value parsing API <values>` that parses individual values like option values, command arguments, section parameters, etc.
* :doc:`A declarative API <declarative>` that parses a configuration file into an instance of a configuration class. It incorporates the value parsing API. The parts of :doc:`the API required for extending the declarative API <extend_declarative>` are documented separately.
* :doc:`A low-level API <low_level>` for sections as well as for options and/or commands, used internally by the declarative API, but occasionally also useful on its own.

.. include with a :parser: option is the only way to add a final toc-tree as a sibling to the last subsection.

.. include:: example.rst.inc
   :parser: restructuredtext

.. toctree::
   :hidden:
   :maxdepth: 2

   values
   declarative
   extend_declarative
   low_level

