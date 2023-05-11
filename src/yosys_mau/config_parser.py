from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .source_str import re, report


@dataclass
class ConfigSection:
    """A single section within a config file."""

    name: str | None
    arguments: str
    contents: str


_SKIP_EMPTY_PREFIX_RE = re.compile(r"(\s*(#.*)?(\n|\Z))*")
_SECTION_HEADER_RE = re.compile(
    r"""
        (?P<header>
            ^\[(?!\[) [ \t]*
            (?P<name>\S+?) ([ \t]+
            (?P<arguments>.*?))?
            (?P<closing_bracket>  # the closing bracket is optional for error reporting
                \] [ \t]* ([#].*)?
            )?
        )
        (\n|\Z)
    """,
    re.VERBOSE | re.MULTILINE,
)
_SECTION_END_RE = re.compile(r"^\[(?!\[)|\Z", re.MULTILINE)

# We use lookahead below for improved source tracking
_ESCAPED_BRACKET = re.compile(r"^\[(?=\[)", re.MULTILINE)


def split_into_sections(contents: str) -> Iterable[ConfigSection]:
    """Split the contents of a config file into individual sections."""
    match = _SKIP_EMPTY_PREFIX_RE.match(contents)
    assert match is not None
    pos = match.end()

    while pos < len(contents):
        start_pos = pos

        end_of_section = _SECTION_END_RE.search(contents, pos + 1)
        assert end_of_section is not None
        pos = end_of_section.start()

        if not (header_match := _SECTION_HEADER_RE.match(contents, start_pos)):
            # sectionless content at the start of the file
            yield ConfigSection(name=None, arguments="", contents=contents[start_pos:pos])
            continue

        name = header_match["name"] or ""
        arguments = header_match["arguments"] or ""

        if header_match["closing_bracket"] is None:
            raise report.InputError(
                header_match["header"], "section header is missing a closing `]`"
            )

        section_content = _ESCAPED_BRACKET.sub("", contents[header_match.end() : pos])

        yield ConfigSection(
            name=name,
            arguments=arguments,
            contents=section_content,
        )
