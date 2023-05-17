from __future__ import annotations

import typing
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Iterable, Literal, TypeVar

from typing_extensions import Concatenate, ParamSpec, Self

from yosys_mau import source_str
from yosys_mau.source_str import report

from ._low_level import ConfigSection, split_into_sections

T = TypeVar("T")
S = typing.TypeVar("S")
Args = ParamSpec("Args")


class ConfigParser:
    """Base class for config parsers.

    Derive from this class to implement a config parser. To specify the sections that can be
    present, invoke section parser factory methods within the class definition, assigning the result
    to attributes of the class.
    """

    # NOTE as this class is intended to be subclassed by user code that is oblivious to
    # implementation details, make sure to use private attributes (`__foo`) to avoid any accidental
    # name clashes

    __section_parser_factories: list[SectionParserFactory[Any]]

    __sections: list[ConfigSection]
    __sections_by_name: dict[str, list[ConfigSection]]
    __processed: dict[ConfigSection, bool]
    __parsers: dict[SectionParserFactory[Any], SectionParser[Any]]
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

        :param contents: The contents of the config file. This should be a {py:class}`SourceStr
            <yosys_mau.source_str.SourceStr>` for proper error reporting.
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
            factory: factory.build_section_parser(self)
            for factory in self.__section_parser_factories
        }

        for parser in self.__parsers.values():
            parser.parse()

        for parser in self.__parsers.values():
            parser.validate()

        for section in self.__sections:
            if not self.__processed[section]:
                raise report.InputError(section.header, "unknown section")

    def sections(
        self, name: str | None = None, unprocessed_only: bool = False
    ) -> list[ConfigSection]:
        """Returns all sections or all sections with a given name.

        :param name: The name of the section to return or `None` to return all sections.
        :param unprocessed_only: If `True` only unprocessed sections are returned.
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
    def __register_section_parser__(cls, parser_factory: SectionParserFactory[Any]):
        """Register a section parser factory for a config parser subclass.

        This is called by `SectionParserFactory` when it is assigned to a class attribute and there
        should be no need to manually call this.
        """
        try:
            registry = cls.__section_parser_factories
        except AttributeError:
            registry = cls.__section_parser_factories = []

        registry.append(parser_factory)

    def __section_parser_result__(self, parser_factory: SectionParserFactory[T]) -> T:
        """Returns the result of a section parser identified by its factory.

        This is called by `SectionParserFactory` to implement the descriptor protocol and there
        should be no need to manually call this.
        """
        parser = self.__parsers.get(parser_factory, None)
        return typing.cast(SectionParser[T], parser).result()

    def __repr__(self):  # pragma: no cover (debug only)
        if self.__in_repr:
            return "..."
        self.__in_repr = True
        contents = [repr(parser) for parser in self.__parsers.values()]
        self.__in_repr = False
        return f"<{type(self).__name__} {', '.join(contents)}>"


@dataclass
class SectionParser(Generic[T], metaclass=ABCMeta):
    """Base class for section parsers."""

    config_parser: ConfigParser
    """The parser for the config file containing the section being parsed."""

    attr_name: str | None
    """The name of the attribute in the config parser class that this section parser is associated
    with."""

    @abstractmethod
    def parse(self) -> None:
        """Parses all sections that this section parser is responsible for.

        This method is called once for each section parser. The section parser itself is responsible
        for collecting all sections that it is responsible for. It also has to mark those sections
        as parsed using {py:meth}`ConfigParser.mark_as_processed`.
        """
        ...

    def validate(self) -> None:
        """Validates this parser's sections.

        This method is called once for each section parser after all sections have been parsed. When
        all validation can be done during parsing, this method can be left unimplemented.
        """
        pass

    @abstractmethod
    def result(self) -> T:
        """Returns the result of parsing this parser's sections.

        This can be called multiple times and thus should not perform significant work and should
        always return the same result.
        """
        ...

    def __repr__(self):  # pragma: no cover (debug only)
        if self.attr_name is not None:
            return f"{self.attr_name}={self.result()!r}"
        else:
            return f"<{type(self).__name__}>={self.result()!r}"


@dataclass(repr=False)
class StandardSectionParser(SectionParser[T]):
    """Common functionality for section parsers.

    This class provides common functionality that simplifies the implementation of section parsers.
    It provides a {py:func}`matching_sections` method that retrieves a list of sections, optionally
    performs a few checks, marks them as processed and finally returns the list of sections. Which
    sections are returned and which checks are performed can be controlled using the fields of this
    class.

    When deriving from this class, `__post_init__` can be overriden to adjust or check the fields
    before calling `super().__post_init__()` when the derived section parser can only support a
    subset of the possible configurations.
    """

    section_name: str | Literal[False] | None = None
    """Only return sections having this name. If it is `False`, all sections are returned. If it is
    `None`, the name of the attribute within the config parser is used as section name."""

    required: bool = False
    """Raise an error if no matching sections are found. Requires a section name."""

    unique: bool = False
    """Raise an error if, among the matching sections, two share the same header (name +
    arguments)."""

    arguments: None | bool = None
    """Whether to require or forbid arguments for matching sections. For `None`, no check is
    performed, when `True` arguments are required for all matching sections and for `False` section
    arguments are forbidden."""

    def __post_init__(self) -> None:
        if self.section_name is None and self.attr_name is not None:
            self.section_name = self.attr_name

        if self.required and not self.section_name:
            raise TypeError("required section parsers must have a section name")

    def matching_sections(self) -> list[ConfigSection]:
        """Returns a list of matching unprocessed sections and marks them as processed.

        Which sections match depend on the field values of this section parser.
        """
        sections = self.config_parser.sections(self.section_name or None, unprocessed_only=True)
        if not sections and self.required:
            assert self.section_name
            span = self.config_parser.contents[-1:] if self.config_parser.contents else None
            raise report.InputError(span, f"missing section `{self.section_name}`")

        if self.arguments is not None:
            if self.arguments:
                for section in sections:
                    section.ensure_arguments()
            else:
                for section in sections:
                    section.ensure_no_arguments()

        grouped: dict[tuple[str, str], list[ConfigSection]] = {}

        for section in sections:
            grouped.setdefault((section.name, section.arguments), []).append(section)

        if self.unique:
            for (name, arguments), group in grouped.items():
                if len(group) > 1:
                    if arguments:
                        raise report.InputError(
                            source_str.concat(section.arguments for section in group),
                            f"section `{name} {arguments}` defined multiple times",
                        )
                    else:
                        raise report.InputError(
                            source_str.concat(section.name for section in group),
                            f"section `{name}` defined multiple times",
                        )

        self.config_parser.mark_as_processed(sections)

        return sections


class SectionParserFactory(Generic[T]):
    """Factory wrapper for section parsers.

    For our declarative API we want to allow users to declare section parsers as class attributes.
    To create a section parser instance, we require a config parser, the name of the section
    parser's attribute in the config parser and any additional arguments to the section parser.

    The config parser and attribute name should be set automatically, with the config parser only
    being available when the config parser class is instantiated. The section parser arguments on
    the other hand should be set by the user when defining the config parser class.

    This class provides a wrapper for section parser constructors that stores any section parser
    arguments, detects the attribute name, registers the section parser and forwards everything to
    the section parser's constructor when the config parser is instantiated.
    """

    def __init__(self, factory_fn: Callable[[ConfigParser, str | None], SectionParser[T]]) -> None:
        self.__factory_fn = factory_fn
        self.__name = None

    def build_section_parser(self, config_parser: ConfigParser) -> SectionParser[T]:
        built = self.__factory_fn(config_parser, self.__name)
        return built

    def __set_name__(self, owner: object, name: str) -> None:
        self.__name = name
        if isinstance(owner, type) and issubclass(owner, ConfigParser):
            owner.__register_section_parser__(self)

    @typing.overload
    def __get__(self, instance: None, owner: object = None) -> Self:
        ...

    @typing.overload
    def __get__(self, instance: ConfigParser, owner: object) -> T:
        ...

    def __get__(self, instance: object, owner: object = None) -> T | Self:
        if instance is None:
            return self
        return typing.cast(ConfigParser, instance).__section_parser_result__(self)


def section_parser_factory(
    constructor: Callable[Concatenate[ConfigParser, str | None, Args], SectionParser[T]]
) -> Callable[Args, SectionParserFactory[T]]:
    def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> SectionParserFactory[T]:
        def build_section_parser(config_parser: ConfigParser, name: str | None) -> SectionParser[T]:
            return constructor(config_parser, name, *args, **kwargs)

        return SectionParserFactory(build_section_parser)

    wrapper.__wrapped__ = lambda **kwargs: None  # type: ignore
    wrapper.__doc__ = f"""\
        Section parser factory for {{py:class}}`{constructor.__name__}`. The keyword arguments are
        forwarded to {{py:class}}`{constructor.__name__}`'s constructor. Assign the return value to
        a class attribute of a derived config parser class to register the section parser.
    """
    return wrapper


@dataclass(repr=False)
class RawSectionParser(StandardSectionParser["list[ConfigSection]"]):
    """Section parser that returns the raw {py:class}`ConfigSection` objects."""

    sections: list[ConfigSection] = field(init=False)

    def parse(self) -> None:
        matches = self.matching_sections()
        self.config_parser.mark_as_processed(matches)
        self.sections = matches

    def result(self) -> list[ConfigSection]:
        return self.sections


raw_section = section_parser_factory(RawSectionParser)


@dataclass(repr=False)
class StrSectionParser(StandardSectionParser[str]):
    """Section parser that returns the section contents as a single string."""

    concat: bool = False
    """Specifies the behavior when multiple sections match. If `True`, the contents of all matching
    sections are concatenated, for `False`, an error is raised."""

    default: str = ""
    """The default value to return when no sections match."""

    contents: str = field(init=False)

    arguments: None | bool = field(init=False)
    unique: bool = field(init=False)

    def __post_init__(self) -> None:
        self.arguments = False
        self.unique = not self.concat
        super().__post_init__()
        if self.section_name is None:
            raise TypeError("section_name must be set for str_section")

    def parse(self) -> None:
        matches = self.matching_sections()

        if not matches:
            self.contents = self.default
            return

        self.contents = source_str.concat(match.contents for match in matches)

    def result(self) -> str:
        return self.contents


str_section = section_parser_factory(StrSectionParser)


@dataclass(repr=False)
class FileSectionParser(StandardSectionParser["dict[str, str]"]):
    """Section parser that returns the section contents as a dictionary mapping section
    arguments to a single string each."""

    concat: bool = False
    """Specifies the behavior when multiple matching sections have the same name and argument. If
    `True`, the contents of those sections are concatenated, for `False`, an error is raised.
    """

    files: dict[str, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.arguments = True
        self.unique = not self.concat
        super().__post_init__()
        if self.section_name is None:
            raise TypeError("section_name must be set for file_section")

    def parse(self) -> None:
        matches = self.matching_sections()

        files: dict[str, list[str]] = {}

        for section in matches:
            files.setdefault(section.arguments, []).append(section.contents)

        self.files = {name: source_str.concat(chunks) for name, chunks in files.items()}

    def result(self) -> dict[str, str]:
        return self.files


file_section = section_parser_factory(FileSectionParser)


@dataclass(repr=False)
class PostprocessSectionParser(SectionParser[T], Generic[T, S]):
    """Section parser that postprocesses the result of another section parser."""

    inner_parser: SectionParser[S]
    """Section parser used to initially parse the section."""

    postprocess: Callable[[Any, S], T]
    """Function that postprocesses the result of `inner_parser`."""

    __cached_result: T = field(init=False)

    def parse(self) -> None:
        self.inner_parser.parse()

    def validate(self) -> None:
        self.inner_parser.validate()

    def result(self) -> T:
        try:
            return self.__cached_result
        except AttributeError:
            pass
        self.__cached_result = self.postprocess(self.config_parser, self.inner_parser.result())
        return self.__cached_result


def postprocess_section(
    inner: SectionParserFactory[S],
) -> Callable[[Callable[[Any, S], T]], SectionParserFactory[T]]:
    """Decorator for postprocessing the result of another section parser.

    Within a config parser class, use it like this:

    ```python
    @postprocess_section(inner_parser(...))
    def some_name(self, result: S) -> T:
        ...
    ```

    Here `inner_parser(...)` is another section parser factory, like e.g. {py:func}`raw_section` or
    {py:func}`str_section`, with `S` being the result type of `inner_parser(...)` and `T` the result
    type of the postprocessing section parser. The name `some_name` of the post-processing method is
    forwarded to the inner parser's factory, as if it were declared like `some_name =
    inner_parser(...)`.

    :param inner: The inner section parser factory.
    :return: A decorator for the postprocessing method, which when applied to a method, returns a
        new section parser factory.
    """

    def wrapper(postprocess: Callable[[Any, S], T]) -> SectionParserFactory[T]:
        def factory_fn(config_parser: ConfigParser, name: str | None) -> SectionParser[T]:
            if name is not None:
                inner.__set_name__(None, name)
            return PostprocessSectionParser(
                config_parser,
                name,
                inner.build_section_parser(config_parser),
                postprocess,
            )

        return SectionParserFactory(factory_fn)

    return wrapper
