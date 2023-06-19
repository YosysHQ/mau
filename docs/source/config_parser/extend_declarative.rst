Extending the Declarative Config Parsing API
============================================

.. currentmodule:: yosys_mau.config_parser



Writing custom `SectionParser`\ s
---------------------------------

.. _extend-ConfigParser:

.. class:: ConfigParser
   :noindex:

   See :class:`~yosys_mau.config_parser.ConfigParser` for the user API.

   .. automethod:: sections
   .. automethod:: mark_as_processed


.. _extend-SectionParser:

.. class:: SectionParser
   :noindex:

   .. autoattribute:: config_parser
   .. autoattribute:: attr_name

   .. autoproperty:: result

   See :class:`~yosys_mau.config_parser.SectionParser` for the user API.

.. _extend-SectionContentsParser:

.. class:: SectionContentsParser
   :noindex:

   See `SectionContentsParser` for the user API.

   This part of the API is needed to invoke a section content parser on a custom set of sections and to redirect the result (see `ArgSection` for an example).

   .. autoattribute:: arg_sections
   .. autoattribute:: redirect_result



Writing custom `OptionParser`\ s
---------------------------------

.. _extend-ConfigOptions:

.. class:: ConfigOptions
   :noindex:

   See :class:`~yosys_mau.config_parser.ConfigOptions` for the user API.

   .. automethod:: options
   .. automethod:: mark_as_processed

.. _extend-OptionParser:

.. class:: OptionParser
   :noindex:

   .. autoattribute:: config_options
   .. autoattribute:: attr_name

   .. autoproperty:: result

   See :class:`~yosys_mau.config_parser.OptionParser` for the user API.
