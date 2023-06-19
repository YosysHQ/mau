Parsing Individual Values
=========================

In a config file there are several places where individual values are parsed.
To convert values from the input strings to an appropriate Python type and to restrict the allowed values, the `ValueParser` class is used.

.. currentmodule:: yosys_mau.config_parser

.. autoclass:: ValueParser
   :members:
   :show-inheritance:

.. autoclass:: IntValue
   :members:
   :show-inheritance:
   :exclude-members: parse

.. autoclass:: StrValue
   :members:
   :show-inheritance:
   :exclude-members: parse

.. autoclass:: BoolValue
   :members:
   :show-inheritance:
   :exclude-members: parse

.. autoclass:: EnumValue
   :members:
   :show-inheritance:
   :exclude-members: parse

