Declarative Config Parsing API
==============================

Declaring a Configuration File
------------------------------------

.. currentmodule:: yosys_mau.config_parser

.. autoclass:: ConfigParser
   :members:
   :exclude-members: sections, mark_as_processed

   See :ref:`the extending page <extend-ConfigParser>` for details on how to use this class when extending the declarative API.

Declaring Individual Configuration Sections
-------------------------------------------

.. autoclass:: SectionParser

   See :ref:`the extending page <extend-SectionParser>` for details on how to use this class when extending the declarative API.

.. autoclass:: RawSection
   :show-inheritance:
   :members:
   :exclude-members: parse

.. autoclass:: SectionContentsParser
   :show-inheritance:
   :members:
   :exclude-members: arg_sections, redirect_result

   See :ref:`the extending page <extend-SectionContentsParser>` for details on how to use this class when extending the declarative API.

.. autoclass:: StrSection
   :show-inheritance:
   :members:
   :exclude-members: parse

.. autoclass:: ArgSection
   :show-inheritance:
   :members:
   :exclude-members: parse, validate

.. autofunction:: postprocess_section

.. autoclass:: PostprocessSection
   :show-inheritance:
   :members:
   :exclude-members: parse, validate, instantiate_for


Declaring Options Sections
--------------------------

.. autoclass:: ConfigOptions
   :members:
   :exclude-members: options, mark_as_processed

   See :ref:`the extending page <extend-ConfigOptions>` for details on how to use this class when extending the declarative API.

.. autoclass:: OptionParser
   :show-inheritance:

.. autoclass:: RawOption
   :show-inheritance:
   :members:
   :exclude-members: parse

.. autoclass:: Option
   :show-inheritance:
   :members:
   :exclude-members: parse

.. autoclass:: MultiOption
   :show-inheritance:
   :members:
   :exclude-members: parse

.. autoclass:: OptionsSection
   :show-inheritance:
   :members:
   :exclude-members: parse, validate

Declaring Commands Sections
---------------------------

.. autoclass:: ConfigCommands
   :members:

.. autofunction:: command

.. autoclass:: CommandsSection
   :show-inheritance:
   :members:
   :exclude-members: parse, validate
