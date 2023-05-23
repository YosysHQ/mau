from __future__ import annotations

from dataclasses import MISSING
from textwrap import dedent

import pytest
from yosys_mau import source_str
from yosys_mau.config_parser import (
    BoolValue,
    ConfigOptions,
    ConfigParser,
    IntValue,
    MultiOption,
    Option,
    OptionsSection,
    StrValue,
)
from yosys_mau.source_str.report import InputError


def test_options_example1():
    test_input = """\
        [options]
        meow on
        name foo
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleOptions(ConfigOptions):
        meow = Option(BoolValue())
        depth = Option(IntValue(min=0), default=3)
        name = MultiOption(StrValue())

    class ExampleConfig(ConfigParser):
        options = OptionsSection(ExampleOptions)

    config = ExampleConfig(test_input)

    assert config.options.meow
    assert config.options.depth == 3
    assert config.options.name == ["foo"]


def test_options_example2():
    test_input = """\
        [options]
        meow on
        depth 10
        name foo
        name bar
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleOptions(ConfigOptions):
        meow = Option(BoolValue())
        depth = Option(IntValue(min=0), default=3)
        name = MultiOption(StrValue())

    class ExampleConfig(ConfigParser):
        options = OptionsSection(ExampleOptions)

    config = ExampleConfig(test_input)

    assert config.options.meow
    assert config.options.depth == 10
    assert config.options.name == ["foo", "bar"]


def test_options_missing_option():
    test_input = """\
        [options]
        depth 10
        name foo
        name bar
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleOptions(ConfigOptions):
        meow = Option(BoolValue())
        depth = Option(IntValue(min=0), default=3)
        name = MultiOption(StrValue())

    class ExampleConfig(ConfigParser):
        options = OptionsSection(ExampleOptions)

    with pytest.raises(InputError, match=r"missing option `meow`"):
        ExampleConfig(test_input)


def test_options_missing_optional_multi_option():
    test_input = """\
        [options]
        meow on
        depth 10
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleOptions(ConfigOptions):
        meow = Option(BoolValue())
        depth = Option(IntValue(min=0), default=3)
        name = MultiOption(StrValue())

    class ExampleConfig(ConfigParser):
        options = OptionsSection(ExampleOptions)

    config = ExampleConfig(test_input)

    assert config.options.meow
    assert config.options.depth == 10
    assert config.options.name == []


def test_options_missing_required_multi_option():
    test_input = """\
        [options]
        meow on
        depth 10
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleOptions(ConfigOptions):
        meow = Option(BoolValue())
        depth = Option(IntValue(min=0), default=3)
        name = MultiOption(StrValue(), default=MISSING)

    class ExampleConfig(ConfigParser):
        options = OptionsSection(ExampleOptions)

    with pytest.raises(InputError, match=r"missing option `name`"):
        ExampleConfig(test_input)


def test_options_duplicated_option():
    test_input = """\
        [options]
        meow on
        depth 10
        name foo
        name bar
        meow on
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleOptions(ConfigOptions):
        meow = Option(BoolValue())
        depth = Option(IntValue(min=0), default=3)
        name = MultiOption(StrValue())

    class ExampleConfig(ConfigParser):
        options = OptionsSection(ExampleOptions)

    with pytest.raises(InputError, match=r"option `meow` defined multiple times"):
        ExampleConfig(test_input)


def test_options_missing_argument():
    test_input = """\
        [options]
        meow
        depth 10
        name foo
        name bar
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleOptions(ConfigOptions):
        meow = Option(BoolValue())
        depth = Option(IntValue(min=0), default=3)
        name = MultiOption(StrValue())

    class ExampleConfig(ConfigParser):
        options = OptionsSection(ExampleOptions)

    with pytest.raises(InputError, match=r"expected `on` or `off`"):
        ExampleConfig(test_input)


def test_options_unknown_option():
    test_input = """\
        [options]
        meow on
        depth 10
        does_not_exist 1000
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleOptions(ConfigOptions):
        meow = Option(BoolValue())
        depth = Option(IntValue(min=0), default=3)
        name = MultiOption(StrValue())

    class ExampleConfig(ConfigParser):
        options = OptionsSection(ExampleOptions)

    with pytest.raises(InputError, match=r"unknown option `does_not_exist`"):
        ExampleConfig(test_input)
