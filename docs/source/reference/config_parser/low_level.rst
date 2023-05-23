Low-Level Config Parsing API
============================

The low-level API is used internally by the declarative API. It consists of
functions that work on strings (usually `SourceStr`) and split them into components corresponding
to different parts of a configuration file. It also defines dataclasses that
hold several such related components.

.. currentmodule:: yosys_mau.config_parser


.. autofunction:: split_into_sections


.. autoclass:: ConfigSection
   :members:


.. autofunction:: split_into_commands


.. autoclass:: ConfigCommand

