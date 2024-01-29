from __future__ import annotations

import copy
import typing
from abc import ABCMeta, abstractmethod
from dataclasses import MISSING, dataclass, field
from typing import Any, Callable, Generic, Iterable, Literal, TypeVar

from typing_extensions import ParamSpec, Self

from yosys_mau import source_str
from yosys_mau.source_str import report

from ._low_level import ConfigCommand, split_into_commands
from ._sections import (
    SectionContentsParser,
)
from ._values import ValueParser

T = TypeVar("T")
Args = ParamSpec("Args")


# Note that the OptionsSectionParser implementation closely follows the ConfigParser implementation
# so any changes to either might have to be reflected in the other.


class ConfigOptions:
    """Base class for defining options sections.

    Derive from this class to implement an options section parser. To specify the options that can
    be present, assign `OptionParser` objects to class attributes of the derived class.

    Note that this is not an instance of `SectionParser` but needs to be wrapped by `OptionsSection`
    to be included in a `ConfigParser`.
    """

    # NOTE as this class is intended to be subclassed by user code that is oblivious to
    # implementation details, make sure to use private attributes (`__foo`) to avoid any accidental
    # name clashes

    __tmp_option_parser_protos: list[OptionParser[Any]]
    __option_parser_protos: list[OptionParser[Any]] = []

    __options: list[ConfigCommand]
    __options_by_name: dict[str, list[ConfigCommand]]
    __processed: dict[ConfigCommand, bool]
    __parsers: dict[OptionParser[Any], OptionParser[Any]]
    __in_repr: bool = False
    __contents: str

    def __init__(self, contents: str):
        """Initializing an options section parser will automatically start parsing the contents of
        the config file.

        An options section parser first splits the file contents into commands. Next it invokes all
        registered option parsers in order, each of which can parse one or more commands as options.
        The options section parser keeps track of which options are parsed. Then a second pass
        through the registered option parsers is done giving each a chance to perform validation on
        the parsed options. Finally any unparsed sections are treated as errors.

        Note that the validation is not done during construction but only when the :meth:`validate`
        method is called. This is different from the `ConfigParser` to ensure that all other
        sections have been parsed before the options are validated.

        :param contents: The contents of the config file. This should be a `SourceStr
            <yosys_mau.source_str.SourceStr>` for proper error reporting.
        """
        options = list(split_into_commands(contents))

        options_by_name: dict[str, list[ConfigCommand]] = {}

        for option in options:
            options_by_name.setdefault(option.name, []).append(option)

        self.__contents = contents

        self.__options = options
        self.__options_by_name = options_by_name
        self.__processed = {option: False for option in options}

        self.__parsers = {
            proto: proto.instantiate_for(self) for proto in self.__option_parser_protos
        }

        self.setup()

        for parser in self.__parsers.values():
            parser.parse()

    def validate_options(self):
        # TODO document

        for parser in self.__parsers.values():
            parser.validate()

        for option in self.__options:
            if not self.__processed[option]:
                raise report.InputError(option.name, f"unknown option `{option.name}`")

        self.validate()

    def setup(self):
        """Invoked before any options are parsed."""
        pass

    def validate(self):
        """Invoked after all options are parsed and validated."""
        pass

    def options(
        self, name: str | None = None, unprocessed_only: bool = False
    ) -> list[ConfigCommand]:
        """Returns all options or all options with a given name.

        :param name: The name of the option to return or `None` to return all options.
        :param unprocessed_only: If `True` only unprocessed options are returned.
        """
        if name is None:
            options = self.__options
        else:
            options = self.__options_by_name.setdefault(name, [])

        if unprocessed_only:
            options = [s for s in options if not self.__processed[s]]
        else:
            options = list(options)

        return options

    @property
    def contents(self) -> str:
        """The complete unprocessed contents of the options section."""
        return self.__contents

    def mark_as_processed(self, section: ConfigCommand | Iterable[ConfigCommand]) -> None:
        """Marks a given section as processed.

        Sections that are marked as unprocessed at the end of parsing generate an error.
        """
        if isinstance(section, ConfigCommand):
            self.__processed[section] = True
        else:
            for s in section:
                self.mark_as_processed(s)

    @classmethod
    def __register_option_parser__(cls, parser_proto: OptionParser[Any]) -> None:
        """Register an option parser factory for an options section parser subclass.

        This is called by `OptionParserFactory` when it is assigned to a class attribute and there
        should be no need to manually call this.
        """
        try:
            registry = cls.__tmp_option_parser_protos
        except AttributeError:
            registry = cls.__tmp_option_parser_protos = list(cls.__option_parser_protos)

        registry.append(parser_proto)

    def __init_subclass__(cls) -> None:
        cls.__option_parser_protos = cls.__tmp_option_parser_protos
        del cls.__tmp_option_parser_protos

    def __option_parser_result__(self, proto: OptionParser[T]) -> T:
        """Returns the result of an option parser identified by its factory.

        This is called by `OptionParserFactory` to implement the descriptor protocol and there
        should be no need to manually call this. The argument is the protype parser associated with
        this class, not the parser bound to an instance of this class.
        """
        return self.__parsers[proto].result

    def __option_parser_set_result__(self, proto: OptionParser[T], value: T) -> None:
        """Sets the result of a section parser identified by its factory.

        This is called by `SectionParserFactory` to implement the descriptor protocol and there
        should be no need to manually call this. The argument is the protype parser associated with
        this class, not the parser bound to an instance of this class.
        """
        self.__parsers[proto].result = value

    def __repr__(self):  # pragma: no cover (debug only)
        if self.__in_repr:
            return "..."
        self.__in_repr = True
        contents = [repr(parser) for parser in self.__parsers.values()]
        self.__in_repr = False
        return f"<{type(self).__name__} {', '.join(contents)}>"


@dataclass(eq=False)
class OptionParser(Generic[T], metaclass=ABCMeta):
    """Base class for option parsers."""

    config_options: ConfigOptions = field(init=False)
    """The parser for the options section containing the option being parsed."""

    attr_name: str = field(init=False)
    """The name of the attribute in the config options class that this option parser is
    associated with."""

    _result: T = field(init=False)

    @property
    def result(self) -> T:
        return self._result

    @result.setter
    def result(self, value: T) -> None:
        self._result = value

    @abstractmethod
    def parse(self) -> None:
        """Parses all options that this option parser is responsible for.

        This method is called once for each option parser. The option parser itself is responsible
        for collecting all options that it is responsible for. It also has to mark those options as
        parsed using {py:meth}`OptionsSectionParser.mark_as_processed`. Finally it should set the
        {py:attr}`result` property to the result of parsing the options.
        """
        ...

    def validate(self) -> None:
        """Validates this parser's options.

        This method is called once for each option parser after all options have been parsed. When
        all validation can be done during parsing, this method can be left unimplemented.
        """
        pass

    def __repr__(self):  # pragma: no cover (debug only)
        if hasattr(self, "config_options"):
            return f"{self.attr_name}={self.result!r}"
        else:
            return f"{self.attr_name}"

    def matching_options(
        self, *, required: bool = False, unique: bool = True
    ) -> list[ConfigCommand]:
        """Returns a list of matching unprocessed options and marks them as processed.

        Which options match depend on the field values of this section parser.
        """
        options = self.config_options.options(self.attr_name or None, unprocessed_only=True)
        if not options and required:
            assert self.attr_name
            span = self.config_options.contents[-1:] if self.config_options.contents else None
            raise report.InputError(span, f"missing option `{self.attr_name}`")

        if unique:
            if len(options) > 1:
                raise report.InputError(
                    source_str.concat(option.name for option in options),
                    f"option `{self.attr_name}` defined multiple times",
                )

        self.config_options.mark_as_processed(options)

        return options

    def instantiate_for(self, config_options: ConfigOptions, attr_name: str | None = None) -> Self:
        """Returns a copy of this option parser bound to a given config options instance."""
        if hasattr(self, "config_options"):
            raise RuntimeError("option parser already bound to a config options instance")
        if not hasattr(self, "attr_name") and attr_name is None:
            raise RuntimeError("option parser not assigned to a config options attribute")
        instance = copy.copy(self)
        instance.config_options = config_options
        if attr_name is not None:
            instance.attr_name = attr_name
        return instance

    def __set_name__(self, owner: object, name: str) -> None:
        if not hasattr(self, "attr_name"):
            self.attr_name = name
        if isinstance(owner, type) and issubclass(owner, ConfigOptions):
            owner.__register_option_parser__(self)

    @typing.overload
    def __get__(self, instance: ConfigOptions, owner: type[ConfigOptions]) -> T: ...

    @typing.overload
    def __get__(self, instance: object, owner: object = None) -> Self: ...

    def __get__(self, instance: object, owner: object = None) -> T | Self:
        if isinstance(instance, ConfigOptions):
            return instance.__option_parser_result__(self)
        return self

    @typing.overload
    def __set__(self, instance: object, value: Self) -> None: ...

    @typing.overload
    def __set__(self, instance: ConfigOptions, value: T) -> None: ...

    def __set__(self, instance: Any, value: Self | T) -> None:
        if isinstance(instance, ConfigOptions):
            assert not isinstance(value, self.__class__)
            instance.__option_parser_set_result__(self, value)  # type: ignore
        else:
            raise RuntimeError


@dataclass(repr=False, eq=False)
class RawOption(OptionParser["list[ConfigCommand]"]):
    """Returns a list of unparsed `ConfigCommand`\\ s for every use of this option."""

    required: bool = False
    """Raise an error if no matching sections are found. Requires a section name."""

    unique: bool = False
    """Raise an error if, among the matching sections, two share the same header (name +
    arguments)."""

    def parse(self) -> None:
        self.result = self.matching_options(
            required=self.required,
            unique=self.unique,
        )


@dataclass(repr=False, eq=False)
class Option(OptionParser[T]):
    """An option that can be specified at most once.

    This uses a `ValueParser` to parse the option's arguments and directly sets the result to the
    parsed value.
    """

    value_parser: ValueParser[T]
    """The parser for the option's arguments."""

    default: T | Literal[MISSING] = field(default_factory=lambda: MISSING)
    """The default value for the option. If the option is not specified, this value is used. If no
    default value is specified, the option is required."""

    def parse(self) -> None:
        options = self.matching_options(required=self.default is MISSING, unique=True)

        if self.default is not MISSING and not options:
            self.result = self.default
        else:
            try:
                self.result = self.value_parser.parse(options[0].arguments)
            except report.InputError as error:
                error.fallback_span(options[0].name[-1:])
                raise error


@dataclass(repr=False, eq=False)
class MultiOption(OptionParser[typing.List[T]]):
    """An option that can be specified multiple times.

    This uses a `ValueParser` to parse the option's arguments and sets the result to a list of all
    parsed values."""

    value_parser: ValueParser[T]
    """The parser for the arguments, used each time the option is specified."""

    default: Iterable[T] | Literal[MISSING] = ()
    """The default values for the option. If the option is not present at all, this value is used,
    by default an empty list. If the default is the special value :data:`dataclasses.MISSING`, the
    option is required to be used at least once."""

    def parse(self) -> None:
        options = self.matching_options(required=self.default is MISSING, unique=False)

        if self.default is not MISSING and not options:
            self.result = list(self.default)
        else:
            result: list[T] = []
            for option in options:
                try:
                    result.append(self.value_parser.parse(option.arguments))
                except report.InputError as error:
                    error.fallback_span(option.name[-1:])
                    raise error
            self.result = result


SomeConfigOptions = TypeVar("SomeConfigOptions", bound=ConfigOptions)


@dataclass(repr=False, eq=False)
class OptionsSection(SectionContentsParser[SomeConfigOptions]):
    """A section parser that parses a section into a `ConfigOptions` instance. Use this to add
    `ConfigOptions` to a `ConfigParser`."""

    config_options: Callable[[str], SomeConfigOptions]
    """A callable that returns a `ConfigOptions` instance for a given section content.

    Usually this is the `ConfigOptions` subclass itself."""

    unique: bool = False
    """If set, raises an error if the section is present multiple times. Otherwise the options of
    all sections are combined."""

    def parse(self) -> None:
        matches = self.matching_sections(arguments=False, unique=self.unique)

        all_options = source_str.concat(section.contents for section in matches)

        self.result = self.config_options(all_options)

    def validate(self) -> None:
        self.result.validate_options()
