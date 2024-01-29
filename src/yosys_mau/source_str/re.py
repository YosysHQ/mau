# pyright: reportPrivateUsage = false
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    TypeVar,
    overload,
)

_T = TypeVar("_T")

_TEMPLATE_PART_RE = re.compile(
    r"""
        (?P<escape_free> [^\\]+) |
        \\ (
            g < (?P<group_name> [^>]* ) > |
            (?P<octal> 0[0-7]{0,2} | [1-6][0-7]{2}) |
            (?P<group_index> [1-9][0-9]* ) |
            (?P<single_character> . )
        )
    """,
    re.VERBOSE | re.DOTALL,
)


def compile(pattern: str, flags: int | re.RegexFlag = 0) -> Pattern:
    """Source tracking wrapper for :external:func:`re.compile`."""
    return Pattern(re.compile(pattern, flags))


def search(pattern: str, string: str, flags: int | re.RegexFlag = 0) -> Match | None:
    """Source tracking implementation of :external:func:`re.search`."""
    re.search
    return compile(pattern, flags).search(string)


def match(pattern: str, string: str, flags: int | re.RegexFlag = 0) -> Match | None:
    """Source tracking implementation of :external:func:`re.match`."""
    return compile(pattern, flags).match(string)


def fullmatch(pattern: str, string: str, flags: int | re.RegexFlag = 0) -> Match | None:
    """Source tracking implementation of :external:func:`re.fullmatch`."""
    return compile(pattern, flags).fullmatch(string)


def split(pattern: str, string: str, maxsplit: int = 0, flags: int | re.RegexFlag = 0) -> list[str]:
    """Source tracking implementation of :external:func:`re.split`."""
    return compile(pattern, flags).split(string, maxsplit)


def findall(pattern: str, string: str, flags: int | re.RegexFlag = 0) -> list[str]:
    """Source tracking implementation of :external:func:`re.findall`."""
    return compile(pattern, flags).findall(string)


def finditer(pattern: str, string: str, flags: int | re.RegexFlag = 0) -> Iterator[Match]:
    """Source tracking implementation of :external:func:`re.finditer`."""
    return compile(pattern, flags).finditer(string)


def sub(
    pattern: str,
    repl: str | Callable[[Match], str],
    string: str,
    count: int = 0,
    flags: int | re.RegexFlag = 0,
) -> str:
    """Source tracking implementation of :external:func:`re.sub`."""
    return compile(pattern, flags).sub(repl, string, count)


def subn(
    pattern: str,
    repl: str | Callable[[Match], str],
    string: str,
    count: int = 0,
    flags: int | re.RegexFlag = 0,
) -> tuple[str, int]:
    """Source tracking implementation of :extenral:func:`re.subn`."""
    return compile(pattern, flags).subn(repl, string, count)


escape = re.escape

purge = re.purge


@dataclass(frozen=True)
class Pattern:
    """Source tracking wrapper for :external:mod:`re` ``Pattern`` objects."""

    wrapped: re.Pattern[str]
    """The wrapped plain :external:mod:`re` ``Pattern`` object."""

    def search(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> Match | None:
        """Source tracking wrapper for :external:meth:`re.Pattern.search`."""
        match = self.wrapped.search(string, pos, endpos)
        return None if match is None else Match(match)

    def match(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> Match | None:
        """Source tracking wrapper for :external:meth:`re.Pattern.match`."""
        match = self.wrapped.match(string, pos, endpos)
        return None if match is None else Match(match)

    def fullmatch(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> Match | None:
        """Source tracking wrapper for :external:meth:`re.Pattern.fullmatch`."""
        match = self.wrapped.fullmatch(string, pos, endpos)
        return None if match is None else Match(match)

    def split(self, string: str, maxsplit: int = 0) -> list[str]:
        """Source tracking implementation of :external:meth:`re.Pattern.split`."""
        result: list[str] = []
        pos = 0
        for match in self.wrapped.finditer(string):
            result.append(string[pos : match.start()])
            pos = match.end()
            maxsplit -= 1
            if maxsplit == 0:
                break
        result.append(string[pos:])
        return result

    def findall(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> list[str]:
        """Source tracking implementation of :external:meth:`re.Pattern.findall`."""
        return [match._group(0) for match in self.finditer(string, pos, endpos)]

    def finditer(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> Iterator[Match]:
        """Source tracking wrapper for :external:meth:`re.Pattern.finditer`."""
        return map(Match, self.wrapped.finditer(string, pos, endpos))

    def sub(self, repl: str | Callable[[Match], str], string: str, count: int = 0) -> str:
        """Source tracking implementation of :external:meth:`re.Pattern.sub`."""
        return self.subn(repl, string, count)[0]

    def subn(
        self, repl: str | Callable[[Match], str], string: str, count: int = 0
    ) -> tuple[str, int]:
        """Source tracking implementation of :external:meth:`re.Pattern.subn`."""
        from . import concat

        if isinstance(repl, str):
            repl_str = repl
            repl_fn: Callable[[Match], str] = lambda match: match.expand(repl_str)  # noqa: E731
        else:
            repl_fn = repl

        counter = 0

        def generate() -> Iterable[str]:
            nonlocal counter

            pos = 0

            for match in self.finditer(string):
                counter += 1
                yield string[pos : match.start()]
                yield repl_fn(match)
                pos = match.end()

                if counter == count:
                    break

            yield string[pos:]

        return concat(generate()), counter

    @property
    def flags(self) -> int:
        """Forwards to :external:attr:`re.Pattern.flags`."""
        return self.wrapped.flags

    @property
    def groups(self) -> int:
        """Forwards to :external:attr:`re.Pattern.groups`."""
        return self.wrapped.groups

    @property
    def groupindex(self) -> Mapping[str, int]:
        """Forwards to :external:attr:`re.Pattern.groupindex`."""
        return self.wrapped.groupindex

    @property
    def pattern(self) -> str:
        """Forwards to :external:attr:`re.Pattern.pattern`."""
        return self.wrapped.pattern


@dataclass(frozen=True)
class Match:
    """Source tracking wrapper for :external:mod:`re` `Match` objects."""

    wrapped: re.Match[str]
    """The wrapped plain :external:mod:`re` Match object."""

    @property
    def pos(self) -> int:
        """Forwards to :external:attr:`re.Match.pos`."""
        return self.wrapped.pos

    @property
    def endpos(self) -> int:
        """Forwards to :external:attr:`re.Match.endpos`."""
        return self.wrapped.endpos

    @property
    def string(self) -> str:
        """Forwards to :external:attr:`re.Match.string`.

        Even though this forwards to the wrapped object, this will return a <project:#SourceStr>
        when used as match target.
        """
        return self.wrapped.string

    @property
    def lastindex(self) -> int | None:
        """Forwards to :external:attr:`re.Match.lastindex`."""
        return self.wrapped.lastindex

    @property
    def lastgroup(self) -> str | None:
        """Forwards to :external:attr:`re.Match.lastgroup`."""
        return self.wrapped.lastgroup

    @property
    def re(self) -> Pattern:
        """Source tracking wrapper for :external:attr:`re.Match.re`."""
        return Pattern(self.wrapped.re)

    def span(self, group: int | str = 0) -> tuple[int, int]:
        """Forwards to :external:meth:`re.Match.span`."""
        return self.wrapped.span(group)

    def start(self, group: int | str = 0) -> int:
        """Forwards to :external:meth:`re.Match.start`."""
        return self.wrapped.start(group)

    def end(self, group: int | str = 0) -> int:
        """Forwards to :external:meth:`re.Match.end`."""
        return self.wrapped.end(group)

    @overload
    def group(self, group: Literal[0] = 0, /) -> str: ...

    @overload
    def group(self, group: str | int, /) -> str | None: ...

    @overload
    def group(
        self,
        group1: str | int,
        group2: str | int,
        /,
        *groups: str | int,
    ) -> tuple[str | None, ...]: ...

    def group(self, *groups: str | int) -> str | tuple[str | None, ...] | None:
        """Source tracking wrapper for :external:meth:`re.Match.group`."""
        if not groups:
            return self._group(0)
        elif len(groups) == 1:
            return self._group(groups[0])
        return tuple(self._group(group) for group in groups)

    @overload
    def __getitem__(self, group: Literal[0]) -> str: ...

    @overload
    def __getitem__(self, group: int | str) -> str | None: ...

    def __getitem__(self, group: int | str) -> str | None:
        """Source tracking wrapper for :external:meth:`re.Match.__getitem__`."""
        group_str = self._group(group)
        return group_str

    @overload
    def _group(self, group: Literal[0], default: Any = None) -> str: ...

    @overload
    def _group(self, group: int | str, default: _T) -> str | _T: ...

    @overload
    def _group(self, group: int | str) -> str | None: ...

    def _group(self, group: int | str, default: Any = None) -> Any:
        if group == 0:
            return self.string[self.start() : self.end()]
        span = self.wrapped.span(group)
        if span == (-1, -1):
            return default
        return self.string[span[0] : span[1]]

    @overload
    def groups(self) -> tuple[str | None, ...]: ...

    @overload
    def groups(self, default: _T) -> tuple[str | _T, ...]: ...

    def groups(self, default: Any = None) -> tuple[Any, ...]:
        """Source tracking wrapper for :external:meth:`re.Match.groups`."""
        return tuple(self._group(group, default) for group in range(1, 1 + self.wrapped.re.groups))

    @overload
    def groupdict(self) -> dict[str, str | None]: ...

    @overload
    def groupdict(self, default: _T) -> dict[str, str | _T]: ...

    def groupdict(self, default: Any = None) -> dict[str, Any]:
        """Source tracking wrapper for :external:meth:`re.Match.groupdict`."""
        return {name: self._group(name, default) for name in self.wrapped.re.groupindex.keys()}

    def expand(self, template: str) -> str:
        """Source tracking implementation of :external:meth:`re.Match.expand`."""
        from . import concat

        if "\\" not in template:
            return template

        output: list[str] = []

        self.wrapped.expand(template)  # just to get the same error handling

        for match in _TEMPLATE_PART_RE.finditer(template):
            escape_free = match["escape_free"]
            if escape_free is not None:
                output.append(escape_free)
                continue
            octal = match["octal"]
            if octal is not None:
                output.append(chr(int(octal, 8)))
                continue
            group_name = match["group_name"]
            if group_name is not None:
                group = self.group(group_name)
                assert group is not None
                output.append(group)
                continue
            group_index = match["group_index"]
            if group_index is not None:
                group = self.group(int(group_index))
                assert group is not None
                output.append(group)
                continue
            output.append(self.wrapped.expand(match[0]))

        return concat(output)


A = re.A
ASCII = re.ASCII
DEBUG = re.DEBUG
I = re.I  # noqa: E741 -- need to copy the stdlib's naming
IGNORECASE = re.IGNORECASE
L = re.L
LOCALE = re.LOCALE
M = re.M
MULTILINE = re.MULTILINE
S = re.S
DOTALL = re.DOTALL
X = re.X
VERBOSE = re.VERBOSE
