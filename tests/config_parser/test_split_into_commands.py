from __future__ import annotations

from textwrap import dedent

import pytest
from yosys_mau import config_parser, source_str
from yosys_mau.config_parser import ConfigCommand
from yosys_mau.source_str import re
from yosys_mau.source_str.report import InputError


def test_simple():
    test_input = """\
        no_argument
        single_argument on
        multiple_arguments 1 2 3
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    commands = list(config_parser.split_into_commands(test_input))
    assert commands == [
        ConfigCommand(index=0, name="no_argument", arguments=""),
        ConfigCommand(index=1, name="single_argument", arguments="on"),
        ConfigCommand(index=2, name="multiple_arguments", arguments="1 2 3"),
    ]
    assert commands[0].arg_list == []
    assert commands[1].arg_list == ["on"]
    assert commands[2].arg_list == ["1", "2", "3"]


def test_comments():
    test_input = """\
        # This is a comment
        no_argument
        single_argument on # This is also a comment
        multiple_arguments 1 2 3
        # As is this
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    commands = list(config_parser.split_into_commands(test_input))
    assert commands == [
        ConfigCommand(index=0, name="no_argument", arguments=""),
        ConfigCommand(index=1, name="single_argument", arguments="on"),
        ConfigCommand(index=2, name="multiple_arguments", arguments="1 2 3"),
    ]
    assert commands[0].arg_list == []
    assert commands[1].arg_list == ["on"]
    assert commands[2].arg_list == ["1", "2", "3"]


def test_extra_whitespace():
    test_input = """\
           # This is a comment


            no_argument

        single_argument     on   # This is also a comment


           multiple_arguments    1  2  3
        # As is this


    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    commands = list(config_parser.split_into_commands(test_input))
    assert commands == [
        ConfigCommand(index=0, name="no_argument", arguments=""),
        ConfigCommand(index=1, name="single_argument", arguments="on"),
        ConfigCommand(index=2, name="multiple_arguments", arguments="1  2  3"),
    ]
    assert commands[0].arg_list == []
    assert commands[1].arg_list == ["on"]
    assert commands[2].arg_list == ["1", "2", "3"]


def test_indented_section_header():
    test_input = """\
        meow on
          [engines]
          abc xyz
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    with pytest.raises(
        InputError, match=r"unexpected `\[`, remove the leading whitespace to start a new section"
    ) as exc_info:
        list(config_parser.split_into_commands(test_input))

    assert source_str.source_map(exc_info.value.where or "") == source_str.source_map(
        re.findall(r"\[", test_input)[0]
    )
