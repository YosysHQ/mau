from __future__ import annotations

from textwrap import dedent

import pytest
from yosys_mau import source_str
from yosys_mau.config_parser import (
    ConfigParser,
    ConfigSection,
    RawSection,
    StrSection,
    postprocess_section,
)
from yosys_mau.source_str.report import InputError

from tests.test_utils import assert_dataclass_list_match


def test_single_str_section():
    test_input = """\
        [script]
        cat meow.txt
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\n"


def test_two_different_str_section():
    test_input = """\
        [script]
        cat meow.txt
        [misc]
        :)
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        misc = StrSection(default="?\n")

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\n"
    assert config.misc == ":)\n"


def test_missing_default_str_section():
    test_input = """\
        [script]
        cat meow.txt
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        misc = StrSection(default="?\n")

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\n"
    assert config.misc == "?\n"


def test_missing_required_str_section():
    test_input = """\
        [misc]
        :(
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        misc = StrSection(default="?\n")

    with pytest.raises(InputError, match=r"missing section"):
        ExampleConfig(test_input)


def test_unknown_section():
    test_input = """\
        [script]
        cat meow.txt
        [misc]
        :(
        [unknown]
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        misc = StrSection(default="?\n")

    with pytest.raises(InputError, match=r"unknown section"):
        ExampleConfig(test_input)


def test_duplicate_str_section():
    test_input = """\
        [script]
        cat meow.txt
        [misc]
        :(
        [script]
        yes meow
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        misc = StrSection(default="?\n")

    with pytest.raises(InputError, match=r"defined multiple times"):
        ExampleConfig(test_input)


def test_concat_str_section():
    test_input = """\
        [script]
        cat meow.txt
        [misc]
        :)
        [script]
        yes meow
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection(default=None, concat=True)
        misc = StrSection(default="?\n")

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\nyes meow\n"
    assert config.misc == ":)\n"


def test_file_section_single():
    test_input = """\
        [script]
        cat meow.txt
        [file meow.txt]
        meow!
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        file = StrSection().with_arguments()

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\n"
    assert config.file == {"meow.txt": "meow!\n"}


def test_file_section_multiple():
    test_input = """\
        [script]
        cat meow.txt
        [file meow.txt]
        meow!
        [file numbers.txt]
        1, 2, 3
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        file = StrSection().with_arguments()

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\n"
    assert config.file == {"meow.txt": "meow!\n", "numbers.txt": "1, 2, 3\n"}


def test_file_section_duplicate():
    test_input = """\
        [script]
        cat meow.txt
        [file numbers.txt]
        1, 2, 3
        [file meow.txt]
        meow!
        [file numbers.txt]
        4, 5, 6
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        file = StrSection().with_arguments()

    with pytest.raises(InputError, match=r"defined multiple times"):
        ExampleConfig(test_input)


def test_file_section_concat():
    test_input = """\
        [script]
        cat meow.txt
        [file numbers.txt]
        1, 2, 3
        [file meow.txt]
        meow!
        [file numbers.txt]
        4, 5, 6
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        file = StrSection(concat=True).with_arguments()

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\n"
    assert config.file == {"meow.txt": "meow!\n", "numbers.txt": "1, 2, 3\n" "4, 5, 6\n"}


def test_raw_section_fallback():
    test_input = """\
        [script]
        cat meow.txt
        [file numbers.txt]
        1, 2, 3
        [file meow.txt]
        meow!
        [file numbers.txt]
        4, 5, 6
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()
        fallback = RawSection(all_sections=True)

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\n"
    assert_dataclass_list_match(
        config.fallback,
        ConfigSection,
        [
            dict(name="file", arguments="numbers.txt", contents="1, 2, 3\n"),
            dict(name="file", arguments="meow.txt", contents="meow!\n"),
            dict(name="file", arguments="numbers.txt", contents="4, 5, 6\n"),
        ],
    )


def test_postprocess_section():
    test_input = """\
        [script]
        cat meow.txt
        yes meow
        [file numbers.txt]
        1, 2, 3
        [file meow.txt]
        meow!
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        @postprocess_section(StrSection())
        def script(self, script: str) -> list[str]:
            return script.splitlines()

        file = StrSection().with_arguments()

    config = ExampleConfig(test_input)
    assert config.script == ["cat meow.txt", "yes meow"]
    assert config.file == {"meow.txt": "meow!\n", "numbers.txt": "1, 2, 3\n"}


def test_assign_result():
    test_input = """\
        [script]
        cat meow.txt
    """
    test_input = source_str.from_content(dedent(test_input), "test_input.sby")

    class ExampleConfig(ConfigParser):
        script = StrSection()

    config = ExampleConfig(test_input)
    assert config.script == "cat meow.txt\n"
    config.script = "python meow.py\n"
    assert config.script == "python meow.py\n"
