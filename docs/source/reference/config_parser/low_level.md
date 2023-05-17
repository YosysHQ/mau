# Low-Level Config Parsing API

The low-level API is used internally by the declarative API. It consists of
functions that work on strings (usually {class}`SourceStr
<yosys_mau.source_str.SourceStr>`) and split them into components corresponding
to different parts of a configuration file. It also defines dataclasses that
hold several such related components.

:::{autodoc} module yosys_mau.config_parser
  :noindex:
:::

:::{autodoc} function split_into_sections
:::

:::{autodoc} class ConfigSection
  :members:
:::

:::{autodoc} function split_into_commands
:::

:::{autodoc} class ConfigCommand
:::
