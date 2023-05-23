from __future__ import annotations

from abc import ABCMeta
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from yosys_mau import source_str
from yosys_mau.source_str import report

from ._low_level import ConfigCommand, split_into_commands
from ._sections import SectionContentsParser
from ._values import ValueParser

T = TypeVar("T")


class ConfigCommands:
    """Base class for defining commands sections."""

    __contents: str

    __tmp_command_parsers: list[CommandParser]
    __command_parsers: list[CommandParser] = []
    __command_parser_dict: dict[str, CommandParser]

    def __init__(self, contents: str):
        self.__contents = contents
        self.__commands = split_into_commands(contents)

        self.setup()

        for command in self.__commands:
            try:
                handler = self.__command_parser_dict[command.name].handler
            except KeyError:
                handler = type(self).unrecognized_command
            handler(self, command)

        self.validate()

    def setup(self):
        """Invoked before any commands are parsed."""
        pass

    def validate(self):
        """Invoked after all commands are parsed."""
        pass

    def unrecognized_command(self, command: ConfigCommand):
        """Invoked when a command is not recognized.

        By default this raises an `InputError`, but subclasses may override this to provide
        different behavior
        """
        raise report.InputError(
            command.name,
            f"unrecognized command `{command.name}`",
        )

    @classmethod
    def __register_option_parser__(cls, parser: CommandParser):
        try:
            registry = cls.__tmp_command_parsers
        except AttributeError:
            registry = cls.__tmp_command_parsers = list(cls.__command_parsers)

        registry.append(parser)

    def __init_subclass__(cls) -> None:
        cls.__command_parsers = cls.__tmp_command_parsers
        del cls.__tmp_command_parsers
        cls.__command_parser_dict = {parser.attr_name: parser for parser in cls.__command_parsers}


@dataclass(eq=False)
class CommandParser(metaclass=ABCMeta):
    """Helper class for command parsers.

    This just wraps a function, :attr:`handler`, that takes the :attr:`config_commands` instance and
    the parsed `ConfigCommand`. This is needed to implement ``__set_name__``, so that command
    handlers can register themselves in a `ConfigCommands` subclass when assigned to a class
    attribute.

    Currently not part of the public API, but may become part of the API for extending the
    declarative API in the future.
    """

    config_commands: ConfigCommands = field(init=False)
    """The config commands instance that this command parser is associated with."""

    attr_name: str = field(init=False)
    """The name of the attribute in the config commands class that this command parser is
    associated with."""

    handler: Callable[[Any, ConfigCommand], None]
    """Function that actually handles the command parsing."""

    def __set_name__(self, owner: object, name: str) -> None:
        if not hasattr(self, "attr_name"):
            self.attr_name = name
        if isinstance(owner, type) and issubclass(owner, ConfigCommands):
            owner.__register_option_parser__(self)


def command(arguments: ValueParser[T]) -> Callable[[Callable[[Any, T], None]], CommandParser]:
    """Decorator for defining command handlers.

    Decorate a method with this to turn it into a command handler for commands with the same name as
    the method.
    """

    def wrapper(handler: Callable[[Any, T], None]) -> CommandParser:
        return CommandParser(
            lambda config_commands, command: handler(
                config_commands, arguments.parse(command.arguments)
            )
        )

    return wrapper


SomeConfigCommands = TypeVar("SomeConfigCommands", bound=ConfigCommands)


@dataclass(repr=False, eq=False)
class CommandsSection(SectionContentsParser[SomeConfigCommands]):
    """A section parser that parses a section into a `ConfigCommands` instance. Use this to add
    `ConfigCommands` to a `ConfigParser`."""

    config_commands: Callable[[str], SomeConfigCommands]

    required: bool = False
    """If set, raises an error if the section is absent."""

    unique: bool = False
    """If set, raises an error if the section is present multiple times. Otherwise the commands of
    all sections are combined."""

    def parse(self) -> None:
        matches = self.matching_sections(
            arguments=False, required=self.required, unique=self.unique
        )

        all_commands = source_str.concat(section.contents for section in matches)

        self.result = self.config_commands(all_commands)
