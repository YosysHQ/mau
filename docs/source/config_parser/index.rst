Configuration File Parsing
==========================

.. toctree::
   :hidden:

   values
   declarative
   extend_declarative
   low_level


.. automodule:: yosys_mau.config_parser

The configuration file parsing API is split into the following parts:

* :doc:`A value parsing API <values>` that parses individual values like option values, command arguments, section parameters, etc.
* :doc:`A declarative API <declarative>` that parses a configuration file into an instance of a configuration class. It incorporates the value parsing API. The parts of :doc:`the API required for extending the declarative API <extend_declarative>` are documented separately.
* :doc:`A low-level API <low_level>` for sections as well as for options and/or commands, used internally by the declarative API, but occasionally also useful on its own.

.. include with a :parser: option is the only way to add a final toc-tree as a sibling to the last subsection.


.. rubric:: Example

The following example uses the declarative API to define a small subset of the SBY config syntax:

.. literalinclude:: ../../../tests/config_parser/test_config_parser_example.py
   :start-after: # example begin
   :end-before: # example end
   :dedent:

It can parse a config file like this:

.. literalinclude:: ../../../tests/config_parser/test_config_parser_example.py
   :start-after: example_input = """\
   :end-before: """
   :dedent:

When the contents of the file are read into a string ``example_input`` using
`read_file`, the parsed configuration can be accessed as follows:

.. literalinclude:: ../../../tests/config_parser/test_config_parser_example.py
   :start-after: # assertions begin
   :end-before: # assertions end
   :dedent:
