from __future__ import annotations

from textwrap import dedent
from typing import Any

from yosys_mau import source_str
from yosys_mau.config_parser import (
    CommandsSection,
    ConfigCommands,
    ConfigParser,
    IntValue,
    StrValue,
    command,
)


def test_commands_example():
    test_input = """\
        [steps]
        prep foo
        wait 10
        prep bar
        wait 20
        prep baz
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleCommands(ConfigCommands):
        def setup(self):
            self.steps: list[Any] = []

        @command(StrValue())
        def prep(self, val: str):
            self.steps.append(("prep", val))

        @command(IntValue())
        def wait(self, val: int):
            self.steps.append(("wait", val))

    class ExampleConfig(ConfigParser):
        steps = CommandsSection(ExampleCommands)

    config = ExampleConfig(test_input)

    assert config.steps.steps == [
        ("prep", "foo"),
        ("wait", 10),
        ("prep", "bar"),
        ("wait", 20),
        ("prep", "baz"),
    ]
