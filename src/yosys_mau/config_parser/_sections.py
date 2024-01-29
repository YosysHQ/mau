from __future__ import annotations

import copy
import typing
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Iterable, TypeVar

from typing_extensions import ParamSpec, Self

from yosys_mau import source_str
from yosys_mau.source_str import report

from ._low_level import ConfigSection, split_into_sections
from ._values import StrValue, ValueParser

A = TypeVar("A")
S = TypeVar("S")
T = TypeVar("T")
Args = ParamSpec("Args")


class ConfigParser:
    """Base class for config parsers.

    Derive from this class to implement a config parser. To specify the sections that can be
    present, assign `SectionParser` objects to class attributes of the derived class.
    """

    # NOTE as this class is intended to be subclassed by user code that is oblivious to
    # implementation details, make sure to use private attributes (`__foo`) to avoid any accidental
    # name clashes

    __tmp_section_parser_protos: list[SectionParser[Any]]
    __section_parser_protos: list[SectionParser[Any]] = []

    __sections: list[ConfigSection]
    __sections_by_name: dict[str, list[ConfigSection]]
    __processed: dict[ConfigSection, bool]
    __parsers: dict[SectionParser[Any], SectionParser[Any]]
    __in_repr: bool = False
    __contents: str

    def __init__(self, contents: str) -> None:
        """Initializing a config parser will automatically start parsing the contents of the config
        file.

        A config parser first splits the file contents into sections. Next it invokes all registered
        section parsers in order, each of which can parse one or more sections. The config parser
        keeps track of which sections are parsed. Then a second pass through the registered section
        parsers is done giving each a chance to perform validation on the parsed sections. Finally
        any unparsed sections are treated as errors.

        :param contents: The contents of the config file. This should be a `SourceStr` for proper
            error reporting.
        """
        sections = list(split_into_sections(contents))

        sections_by_name: dict[str, list[ConfigSection]] = {}

        for section in sections:
            sections_by_name.setdefault(section.name, []).append(section)

        self.__contents = contents

        self.__sections = sections
        self.__sections_by_name = sections_by_name
        self.__processed = {section: False for section in sections}

        self.__parsers = {
            proto: proto.instantiate_for(self) for proto in self.__section_parser_protos
        }

        self.setup()

        for parser in self.__parsers.values():
            parser.parse()

        for parser in self.__parsers.values():
            parser.validate()

        self.validate()

        for section in self.__sections:
            if not self.__processed[section]:
                if section.arguments:
                    raise report.InputError(
                        section.header, f"unknown section `{section.name} {section.arguments}`"
                    )
                else:
                    raise report.InputError(section.header, f"unknown section `{section.name}`")

    def setup(self):
        """Invoked before any sections are parsed."""
        pass

    def validate(self):
        """Invoked after all sections are parsed and validated."""
        pass

    def sections(
        self, name: str | None = None, unprocessed_only: bool = False
    ) -> list[ConfigSection]:
        """Returns all sections or all sections with a given name.

        :param name: The name of the section to return or ``None`` to return all sections.
        :param unprocessed_only: If ``True`` only unprocessed sections are returned.
        """
        if name is None:
            sections = self.__sections
        else:
            sections = self.__sections_by_name.setdefault(name, [])

        if unprocessed_only:
            sections = [s for s in sections if not self.__processed[s]]
        else:
            sections = list(sections)

        return sections

    @property
    def contents(self) -> str:
        """The complete unprocessed contents of the config file."""
        return self.__contents

    def mark_as_processed(self, section: ConfigSection | Iterable[ConfigSection]) -> None:
        """Marks a given section as processed.

        Sections that are marked as unprocessed at the end of parsing generate an error.
        """
        if isinstance(section, ConfigSection):
            self.__processed[section] = True
        else:
            for s in section:
                self.mark_as_processed(s)

    @classmethod
    def __register_section_parser__(cls, parser_proto: SectionParser[Any]):
        """Register a section parser for a config parser subclass.

        This is called by `SectionParser` when it is assigned to a class attribute and there should
        be no need to manually call this.
        """
        try:
            registry = cls.__tmp_section_parser_protos
        except AttributeError:
            registry = cls.__tmp_section_parser_protos = list(cls.__section_parser_protos)

        registry.append(parser_proto)

    def __init_subclass__(cls) -> None:
        try:
            cls.__section_parser_protos = cls.__tmp_section_parser_protos
        except AttributeError:
            cls.__section_parser_protos = []
        else:
            del cls.__tmp_section_parser_protos

    def __section_parser_result__(self, proto: SectionParser[T]) -> T:
        """Returns the result of a section parser.

        This is called by `SectionParser` to implement the descriptor protocol and there should be
        no need to manually call this. The argument is the protype parser associated with this
        class, not the parser bound to an instance of this class.
        """
        return self.__parsers[proto].result

    def __section_parser_set_result__(self, proto: SectionParser[T], value: T) -> None:
        """Sets the result of a section parser.

        This is called by `SectionParser` to implement the descriptor protocol and there should be
        no need to manually call this.  The argument is the protype parser associated with this
        class, not the parser bound to an instance of this class.
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
class SectionParser(Generic[T], metaclass=ABCMeta):
    """Base class for section parsers."""

    config_parser: ConfigParser = field(init=False)
    """The parser for the config file containing the section being parsed."""

    attr_name: str = field(init=False)
    """The name of the attribute in the config parser class that this section parser was assigned
    to."""

    _result: T = field(init=False)

    @property
    def result(self) -> T:
        return self._result

    @result.setter
    def result(self, value: T) -> None:
        self._result = value

    @abstractmethod
    def parse(self) -> None:
        """Parses all sections that this section parser is responsible for.

        This method is called once for each section parser. The section parser itself is responsible
        for collecting all sections that it is responsible for. It also has to mark those sections
        as parsed using `ConfigParser.mark_as_processed`. In many cases all this can be
        done automatically using :meth:`matching_sections`.

        Finally the section parser should set the :attr:`result` property to the result of
        parsing the sections.
        """
        ...

    def validate(self) -> None:
        """Validates this parser's sections.

        This method is called once for each section parser after all sections have been parsed. When
        all validation can be done during parsing, this method can be left unimplemented.
        """
        pass

    def __repr__(self):  # pragma: no cover (debug only)
        if hasattr(self, "config_parser"):
            return f"{self.attr_name}={self.result!r}"
        else:
            return f"{self.attr_name}"

    def _arg_sections(self) -> list[ConfigSection] | None:
        return None

    @typing.overload
    def matching_sections(
        self,
        *,
        required: bool = False,
        unique: bool = False,
        arguments: None | bool = None,
        all_sections: bool = False,
        mark_as_processed: bool = True,
    ) -> list[ConfigSection]: ...

    @typing.overload
    def matching_sections(
        self,
        *,
        required: bool = False,
        unique: bool = False,
        arguments: ValueParser[A],
        mark_as_processed: bool = True,
    ) -> dict[A, list[ConfigSection]]: ...

    def matching_sections(
        self,
        *,
        required: bool = False,
        unique: bool = False,
        arguments: None | bool | ValueParser[A] = None,
        all_sections: bool = False,
        mark_as_processed: bool = True,
    ) -> list[ConfigSection] | dict[A, list[ConfigSection]]:
        """Returns a list of matching unprocessed sections and marks them as processed.

        By default all sections that have the same name as the attribute storing this section parser
        are returned.

        :param required: If ``True`` and no matching sections are found, an error is raised.
        :param unique: If ``True`` and more than one matching section is found, an error is raised.
        :param arguments: If ``True``, check that all matching sections have arguments and apply
            `required` and `unique` per unique argument value. If ``False``, check that no arguments
            are present. If ``None``, do not check arguments. If a `ValueParser`, group sections by
            their parsed section arguments and return a dict keyed by their parsed arguments.
        :param all_sections: If ``True``, do not match sections by name but return all unprocessed
            sections.
        :param mark_as_processed: If ``False``, do not mark matching sections as processed.
        """
        if all_sections and required:
            raise TypeError("all_sections and required are mutually exclusive")

        arg_sections = self._arg_sections()

        if arg_sections is not None:
            if arguments:
                raise TypeError("cannot use arguments in a SectionContentParser")
            sections = arg_sections
        elif all_sections:
            if arguments:
                raise TypeError("cannot use arguments together with all_sections")
            sections = self.config_parser.sections(unprocessed_only=True)
        else:
            sections = self.config_parser.sections(self.attr_name, unprocessed_only=True)

        if not sections and required:
            span = self.config_parser.contents[-1:] if self.config_parser.contents else None
            raise report.InputError(span, f"missing section `{self.attr_name}`")

        arg_to_key: Callable[[ConfigSection], Any]

        if all_sections:
            arg_to_key = lambda section: (
                section.name,
                section.arguments,
            )
        elif isinstance(arguments, ValueParser):
            arg_to_key = lambda section: arguments.parse(section.arguments)
        else:
            arg_to_key = lambda section: section.arguments

        if arguments is not None and arg_sections is None:
            if arguments is True:
                for section in sections:
                    section.ensure_arguments()
            elif arguments is False:
                for section in sections:
                    section.ensure_no_arguments()

        groups: Iterable[list[ConfigSection]]
        grouped: dict[Any, list[ConfigSection]] = {}
        if arg_sections is None:
            for section in sections:
                try:
                    grouped.setdefault(arg_to_key(section), []).append(section)
                except report.InputError as error:
                    error.fallback_span(section.header[-1:])
                    raise
            groups = grouped.values()
        else:
            groups = [sections]

        if unique:
            for group in groups:
                if len(group) > 1:
                    first_name = group[0].name
                    first_arguments = group[0].arguments

                    if first_arguments:
                        raise report.InputError(
                            source_str.concat(section.arguments for section in group),
                            f"section `{first_name} {first_arguments}` defined multiple times",
                        )
                    else:
                        raise report.InputError(
                            source_str.concat(section.name for section in group),
                            f"section `{first_name}` defined multiple times",
                        )

        if mark_as_processed:
            self.config_parser.mark_as_processed(sections)
        if isinstance(arguments, ValueParser):
            return grouped
        return sections

    def instantiate_for(self, config_parser: ConfigParser, attr_name: str | None = None) -> Self:
        """Returns a copy of this section parser bound to a given config parser instance."""
        if hasattr(self, "config_parser"):
            raise RuntimeError("section parser already bound to a config parser instance")
        if not hasattr(self, "attr_name") and attr_name is None:
            raise RuntimeError("section parser not assigned to a config parser attribute")
        instance = copy.copy(self)
        instance.config_parser = config_parser
        if attr_name is not None:
            instance.attr_name = attr_name
        return instance

    def __set_name__(self, owner: object, name: str) -> None:
        if not hasattr(self, "attr_name"):
            self.attr_name = name
        if isinstance(owner, type) and issubclass(owner, ConfigParser):
            owner.__register_section_parser__(self)

    @typing.overload
    def __get__(self, instance: ConfigParser, owner: type[ConfigParser]) -> T: ...

    @typing.overload
    def __get__(self, instance: object, owner: object = None) -> Self: ...

    def __get__(self, instance: object, owner: object = None) -> T | Self:
        if isinstance(instance, ConfigParser):
            return instance.__section_parser_result__(self)
        return self

    @typing.overload
    def __set__(self, instance: object, value: Self) -> None: ...

    @typing.overload
    def __set__(self, instance: ConfigParser, value: T) -> None: ...

    def __set__(self, instance: Any, value: Self | T) -> None:
        if isinstance(instance, ConfigParser):
            assert not isinstance(value, self.__class__)
            instance.__section_parser_set_result__(self, value)  # type: ignore
        else:
            raise RuntimeError


@dataclass(repr=False, eq=False)
class RawSection(SectionParser["list[ConfigSection]"]):
    """Section parser that returns the raw `ConfigSection` objects."""

    required: bool = False
    """Passed to :meth:`SectionParser.matching_sections`."""

    unique: bool = False
    """Passed to :meth:`SectionParser.matching_sections`."""

    arguments: None | bool = None
    """Passed to :meth:`SectionParser.matching_sections`."""

    all_sections: bool = False
    """Passed to :meth:`SectionParser.matching_sections`."""

    def parse(self) -> None:
        self.result = self.matching_sections(
            required=self.required,
            unique=self.unique,
            arguments=self.arguments,
            all_sections=self.all_sections,
        )


@dataclass(repr=False, eq=False)
class SectionContentsParser(SectionParser[T]):
    """Base class for section parsers that only handle section contents, not arguments.

    This allows delegating the parsing of section arguments, e.g. by using `with_arguments`.
    """

    arg_sections: list[ConfigSection] | None = field(init=False, default=None)
    """Set to override the sections considered by :meth:`SectionParser.matching_sections`."""

    redirect_result: tuple[dict[Any, Any], Any] | None = field(init=False, default=None)
    """Set to store the parse result in a dictionary instead of within this section parser."""

    def _arg_sections(self) -> list[ConfigSection] | None:
        return self.arg_sections

    @property
    def result(self) -> T:
        if self.redirect_result:
            result_dict, result_key = self.redirect_result
            return result_dict[result_key]
        return self._result

    @result.setter
    def result(self, value: T) -> None:
        if self.redirect_result:
            result_dict, result_key = self.redirect_result
            result_dict[result_key] = value
        else:
            self._result = value

    @typing.overload
    def with_arguments(self, value_parser: ValueParser[A]) -> ArgSection[A, T]: ...

    @typing.overload
    def with_arguments(self, value_parser: None = None) -> ArgSection[str, T]: ...

    def with_arguments(self, value_parser: ValueParser[Any] | None = None) -> ArgSection[Any, T]:
        """Wraps this section parser in an `ArgSection` parser."""
        if value_parser:
            return ArgSection(self, value_parser)
        else:
            return ArgSection(self)


@dataclass(repr=False, eq=False)
class StrSection(SectionContentsParser[str]):
    """Section parser that returns the section contents as a single string."""

    concat: bool = False
    """Specifies the behavior when multiple sections match. If ``True``, the contents of all
    matching sections are concatenated, for ``False``, an error is raised."""

    default: str | None = None
    """The default value to return when no sections match. If ``None``, the section must be present
    or an error is raised."""

    def parse(self) -> None:
        matches = self.matching_sections(
            required=self.default is None, unique=not self.concat, arguments=False
        )

        if not matches:
            assert self.default is not None
            self.result = self.default
            return

        self.result = source_str.concat(match.contents for match in matches)


@dataclass(repr=False, eq=False)
class FilesSection(SectionContentsParser["list[str]"]):
    def parse(self) -> None:
        matches = self.matching_sections(required=False, unique=False, arguments=False)

        result: list[str] = []

        for section in matches:
            for line in section.contents.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # TODO support some form of escaping
                result.append(line)

        self.result = result


@dataclass(repr=False, eq=False)
class ArgSection(SectionParser[typing.Mapping[A, T]]):
    """Section parser that handles section arguments and delegates to another section parser for the
    section contents. It uses a `ValueParser` to parse the argument value.

    When using a fixed :attr:`content_parser`, prefer using
    `SectionContentsParser.with_arguments` over using this class directly.
    """

    content_parser: SectionContentsParser[T] | Callable[[A], SectionContentsParser[T]]
    """The section content parser to use for the section contents. If a callable is passed, the
    specific parser used can be selected based on the parsed arguments."""

    arguments_parser: ValueParser[A] = field(default_factory=StrValue)  # type: ignore
    """The parser to use for parsing the section arguments."""

    __parsers: dict[A, SectionContentsParser[T]] = field(init=False)

    if typing.TYPE_CHECKING:

        @typing.overload
        def __new__(
            cls,
            content_parser: SectionContentsParser[T] | Callable[[A], SectionContentsParser[T]],
            argument_parser: ValueParser[A],
        ) -> ArgSection[A, T]: ...

        @typing.overload
        def __new__(
            cls,
            content_parser: SectionContentsParser[T] | Callable[[str], SectionContentsParser[T]],
        ) -> ArgSection[str, T]: ...

        def __new__(cls, *args: Any, **kwargs: Any) -> ArgSection[Any, T]: ...

    def parse(self) -> None:
        sections = self.matching_sections(mark_as_processed=False, arguments=self.arguments_parser)
        self.__parsers = parsers = {}
        self.result = result = {}
        for arg, arg_sections in sections.items():
            if isinstance(self.content_parser, SectionContentsParser):
                content_parser = self.content_parser
            else:
                content_parser = self.content_parser(arg)
            content_parser = content_parser.instantiate_for(self.config_parser, self.attr_name)
            content_parser.arg_sections = arg_sections
            content_parser.redirect_result = (result, arg)
            content_parser.parse()
            parsers[arg] = content_parser

    def validate(self) -> None:
        for parser in self.__parsers.values():
            parser.validate()


@dataclass(repr=False, eq=False)
class PostprocessSection(SectionParser[T], Generic[T, S]):
    """Section parser that postprocesses the result of another section parser.

    Prefer using the :func:`postprocess_section` decorator over using this class directly.
    """

    inner_parser: SectionParser[S] = field()
    """Section parser used to initially parse the section."""

    postprocess: Callable[[Any, S], T]
    """Function that postprocesses the result of `inner_parser`."""

    def parse(self) -> None:
        self.inner_parser.parse()
        self.result = self.postprocess(self.config_parser, self.inner_parser.result)

    def validate(self) -> None:
        self.inner_parser.validate()

    def instantiate_for(self, config_parser: ConfigParser, attr_name: str | None = None) -> Self:
        instanciated = super().instantiate_for(config_parser, attr_name)

        instanciated.inner_parser = instanciated.inner_parser.instantiate_for(
            config_parser, self.attr_name
        )
        return instanciated


def postprocess_section(
    inner: SectionParser[S],
) -> Callable[[Callable[[Any, S], T]], SectionParser[T]]:
    """Decorator for postprocessing the result of another section parser.

    Within a config parser class, use it like this::

        @postprocess_section(InnerSection(...))
        def some_name(self, result: S) -> T:
            ...

    Here ``InnerSection(...)`` is another section parser, like e.g. `RawSection` or `StrSection`,
    with ``S`` being the result type of ``InnerSection(...)`` and ``T`` the result type of the
    postprocessing section parser. The name ``some_name`` of the post-processing method is forwarded
    to the inner parser, as if it were declared like ``some_name = InnerSection(...)``.

    :param inner: The inner section parser.
    :return: A decorator for the postprocessing method, which when applied to a method, returns a
        new section parser.
    """

    def wrapper(postprocess: Callable[[Any, S], T]) -> SectionParser[T]:
        return PostprocessSection(inner, postprocess)

    return wrapper
