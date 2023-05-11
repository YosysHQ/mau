# pyright: reportPrivateUsage = false
from __future__ import annotations

from textwrap import dedent

import pytest
from yosys_mau import config_parser, source_str
from yosys_mau.config_parser import ConfigSection
from yosys_mau.source_str.report import InputError


def test_single_section():
    test_input = """\
        [options]
        meow on
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [ConfigSection(name="options", arguments="", contents="meow on\n")]


def test_single_empty_section():
    test_input = """\
        [options]
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [ConfigSection(name="options", arguments="", contents="")]


def test_leading_whitespace():
    test_input = """\


        [options]
        meow on
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [ConfigSection(name="options", arguments="", contents="meow on\n")]


def test_leading_comments():
    test_input = """\
        #!/usr/bin/env -S sby -f
        # some more comments
        [options]
        meow on
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [ConfigSection(name="options", arguments="", contents="meow on\n")]


def test_sectionless():
    test_input = """\
        #!/usr/bin/env cat
        This is some content that is not part of a section.
        # This comment is part of the section
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(
            name=None,
            arguments="",
            contents="This is some content that is not part of a section.\n"
            "# This comment is part of the section\n",
        )
    ]


def test_sectionless_indented_header():
    test_input = """\
        #!/usr/bin/env cat
          [does not start a section]
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(
            name=None,
            arguments="",
            contents="  [does not start a section]\n",
        )
    ]


def test_initial_sectionless():
    test_input = """\
        #!/usr/bin/env cat
        This is some content that is not part of a section.
        # This comment is part of the section
        [options]
        meow on
        # Also part of the section
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(
            name=None,
            arguments="",
            contents="This is some content that is not part of a section.\n"
            "# This comment is part of the section\n",
        ),
        ConfigSection(
            name="options", arguments="", contents="meow on\n" "# Also part of the section\n"
        ),
    ]


def test_multiple_sections():
    test_input = """\
        [options]
        meow on
        [engines]
        abc xyz
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(name="options", arguments="", contents="meow on\n"),
        ConfigSection(name="engines", arguments="", contents="abc xyz\n"),
    ]


def test_multiple_sections_empty():
    test_input = """\
        [options]
        [engines]
        abc xyz
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(name="options", arguments="", contents=""),
        ConfigSection(name="engines", arguments="", contents="abc xyz\n"),
    ]


def test_section_arguments():
    test_input = """\
        [options]
        meow on
        [engines]
        abc xyz
        [file top.sv]
        module top;
        // ...
        endmodule
        [file top copy.sv]
        module top;
        // not that spaces in filenames are a good idea ...
        endmodule
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(name="options", arguments="", contents="meow on\n"),
        ConfigSection(name="engines", arguments="", contents="abc xyz\n"),
        ConfigSection(
            name="file", arguments="top.sv", contents="module top;\n" "// ...\n" "endmodule\n"
        ),
        ConfigSection(
            name="file",
            arguments="top copy.sv",
            contents="module top;\n"
            "// not that spaces in filenames are a good idea ...\n"
            "endmodule\n",
        ),
    ]


def test_escaped_brackets():
    test_input = """\
        [options]
        meow on
        [file recursive.sby]
        # Allow section content to start with brackets
        [[engines]
        abc xyz
        # [ But only require escaping on the first column [[
        [file top.sv]
        module top; // ...
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(name="options", arguments="", contents="meow on\n"),
        ConfigSection(
            name="file",
            arguments="recursive.sby",
            contents="# Allow section content to start with brackets\n"
            "[engines]\n"
            "abc xyz\n"
            "# [ But only require escaping on the first column [[\n",
        ),
        ConfigSection(name="file", arguments="top.sv", contents="module top; // ...\n"),
    ]


def test_section_header_comments():
    test_input = """\
        [options] # this is a comment
        meow on
        [engines] # this too
        abc xyz
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(name="options", arguments="", contents="meow on\n"),
        ConfigSection(name="engines", arguments="", contents="abc xyz\n"),
    ]


def test_extra_whitespace():
    test_input = """\
        [  options]         # this is a comment
        meow on
        [engines  ]
        abc xyz
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    sections = list(config_parser.split_into_sections(test_input))
    assert sections == [
        ConfigSection(name="options", arguments="", contents="meow on\n"),
        ConfigSection(name="engines", arguments="", contents="abc xyz\n"),
    ]


def test_missing_closing_brackets():
    test_input = """\
        #!/usr/bin/env -S sby -f
        [options
        meow on
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    with pytest.raises(InputError, match=r"section header is missing a closing `\]`") as exc_info:
        list(config_parser.split_into_sections(test_input))

    assert source_str.source_map(exc_info.value.where or "") == source_str.source_map(
        test_input.splitlines()[1]
    )
