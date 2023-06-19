.. included from index.rst

Example
-------

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
