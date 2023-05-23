from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from yosys_mau.source_str import re, report

__all__ = [
    "split_into_sections",
    "ConfigSection",
    "split_into_commands",
    "ConfigCommand",
]


@dataclass(frozen=True)
class ConfigSection:
    """A single section within a config file."""

    index: int
    """Sequential index of the section within the config file."""

    name: str
    """Name of the section.

    The ``name`` part in a section header of the form ``[name]`` or ``[name arguments]``.

    For the initial content of a config file that precedes the first section, the name is ``""``.
    For proper sections, the name must be non-empty.
    """

    arguments: str
    """Arguments of the section.

    The ``arguments`` part in a section ``[name arguments]`` or the empty string if not present.

    Can contain spaces.
    """

    contents: str = field(compare=False)
    """Contents of the section.

    The contents following the section header up to the start of the next section or the end of the
    file.
    """

    header: str = field(compare=False)
    """The section header.

    A section header looks like ``[name]`` or ``[name arguments]`` and includes the ``[`` and ``]``
    characters.
    """

    def ensure_no_arguments(self) -> Any:
        """Raise an error if the section has arguments."""
        if self.arguments:
            raise report.InputError(
                self.arguments, f"unexpected arguments for section `{self.name}`"
            )

    def ensure_arguments(self) -> Any:
        """Raise an error if the section has no arguments."""
        if not self.arguments:
            raise report.InputError(self.header, f"missing arguments for section `{self.name}`")


@dataclass(frozen=True)
class ConfigCommand:
    """A single command or option within a config file."""

    index: int
    name: str
    arguments: str

    @property
    def arg_list(self) -> list[str]:
        # TODO support some form of quoting or escaping
        return self.arguments.split()


_SKIP_EMPTY_PREFIX_RE = re.compile(r"(\s*(#.*)?(\n|\Z))*")
_CHECK_INDENTED_SECTION_HEADER_RE = re.compile(r"[ \t]*(?P<indented_section_header>\[)")
_SECTION_HEADER_RE = re.compile(
    r"""
        (?P<header>
            ^\[(?!\[) [ \t]*
            (?P<name>\S+?)
            ([ \t]+ (?P<arguments>.*?))?
            (?P<closing_bracket>  # the closing bracket is optional for error reporting
                \] [ \t]* ([#].*)?
            )?
        )
        (\n|\Z)
    """,
    re.VERBOSE | re.MULTILINE,
)
_SECTION_END_RE = re.compile(r"^\[(?!\[)|\Z", re.MULTILINE)

_COMMAND_RE = re.compile(
    r"""
        ([ \t]*([#].*)?(\n|\Z))*
        [ \t]* (?P<command>
            (?P<name>[^[#\s][^#\s]*?)
            ([ \t]+ (?P<arguments>.*?))? # TODO support some form of quoting or escaping
            [ \t]* ([#].*)?
            (\n|\Z)
        |(?P<indented_section_header>\[)
        |\Z)
    """,
    re.VERBOSE | re.MULTILINE,
)

# We use lookahead below for improved source tracking
_ESCAPED_BRACKET = re.compile(r"^\[(?=\[)", re.MULTILINE)


def split_into_sections(contents: str, start_index: int = 0) -> Iterable[ConfigSection]:
    """Split the contents of a config file into individual sections."""
    match = _SKIP_EMPTY_PREFIX_RE.match(contents)
    assert match is not None
    pos = match.end()

    index = start_index

    while pos < len(contents):
        start_pos = pos

        end_of_section = _SECTION_END_RE.search(contents, pos + 1)
        assert end_of_section is not None
        pos = end_of_section.start()

        if not (header_match := _SECTION_HEADER_RE.match(contents, start_pos)):
            # sectionless content at the start of the file
            section_contents = contents[start_pos:pos]

            # Sectionless content cannot start with an indented `[` as that would be quite
            # confusing. For proper sections we leave it up to the section's parser to decide
            # whether that's allowed.
            if header_match := _CHECK_INDENTED_SECTION_HEADER_RE.match(section_contents):
                raise report.InputError(
                    header_match["indented_section_header"],
                    "unexpected `[`, remove the leading whitespace to start a new section",
                )

            yield ConfigSection(
                header="", name="", arguments="", contents=section_contents, index=index
            )
            index += 1
            continue

        name = header_match["name"] or ""
        arguments = header_match["arguments"] or ""

        if header_match["closing_bracket"] is None:
            raise report.InputError(
                header_match["header"], "section header is missing a closing `]`"
            )

        section_content = _ESCAPED_BRACKET.sub("", contents[header_match.end() : pos])

        header_start, _ = header_match.span("header")
        header_end, _ = header_match.span("closing_bracket")
        header_end += 1

        header = contents[header_start:header_end]

        yield ConfigSection(
            header=header, name=name, arguments=arguments, contents=section_content, index=index
        )
        index += 1


def split_into_commands(contents: str) -> Iterable[ConfigCommand]:
    """Split the contents of a section into individual commands."""

    pos = 0
    index = 0

    while pos < len(contents):
        match = _COMMAND_RE.match(contents, pos)
        assert match is not None
        name = match["name"]
        if name is None:
            if match["indented_section_header"] is not None:
                raise report.InputError(
                    match["indented_section_header"],
                    "unexpected `[`, remove the leading whitespace to start a new section",
                )
            break
        pos = match.end()
        yield ConfigCommand(
            index=index,
            name=name,
            arguments=(match["arguments"] or ""),
        )
        index += 1
