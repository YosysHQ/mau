from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any, Iterator, Literal, Mapping, Optional, TypeVar, Union, overload

_T = TypeVar("_T")


def compile(pattern: str, flags: Union[int, re.RegexFlag] = 0) -> Pattern:
    """Source tracking wrapper for <inv:py#re.compile>."""
    return Pattern(re.compile(pattern, flags))


def search(pattern: str, string: str, flags: Union[int, re.RegexFlag] = 0) -> Optional[Match]:
    """Source tracking implementation of <inv:py#re.search>."""
    re.search
    return compile(pattern, flags).search(string)


def match(pattern: str, string: str, flags: Union[int, re.RegexFlag] = 0) -> Optional[Match]:
    """Source tracking implementation of <inv:py#re.match>."""
    return compile(pattern, flags).match(string)


def fullmatch(pattern: str, string: str, flags: Union[int, re.RegexFlag] = 0) -> Optional[Match]:
    """Source tracking implementation of <inv:py#re.fullmatch>."""
    return compile(pattern, flags).fullmatch(string)


def split(
    pattern: str, string: str, maxsplit: int = 0, flags: Union[int, re.RegexFlag] = 0
) -> list[str]:
    """Source tracking implementation of <inv:py#re.split>."""
    return compile(pattern, flags).split(string, maxsplit)


def findall(pattern: str, string: str, flags: Union[int, re.RegexFlag] = 0) -> list[str]:
    """Source tracking implementation of <inv:py#re.findall>."""
    return compile(pattern, flags).findall(string)


def finditer(pattern: str, string: str, flags: Union[int, re.RegexFlag] = 0) -> Iterator[Match]:
    """Source tracking implementation of <inv:py#re.finditer>."""
    return compile(pattern, flags).finditer(string)


# TODO sub
# TODO subn

escape = re.escape

purge = re.purge


@dataclass(frozen=True)
class Pattern:
    """Source tracking wrapper for <inv:py#re> `Pattern` objects."""

    wrapped: re.Pattern[str]
    """The wrapped plain <inv:py#re> `Pattern` object."""

    def search(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> Optional[Match]:
        """Source tracking wrapper for <inv:py#re.Pattern.search>."""
        match = self.wrapped.search(string, pos, endpos)
        return None if match is None else Match(match)

    def match(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> Optional[Match]:
        """Source tracking wrapper for <inv:py#re.Pattern.match>."""
        match = self.wrapped.match(string, pos, endpos)
        return None if match is None else Match(match)

    def fullmatch(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> Optional[Match]:
        """Source tracking wrapper for <inv:py#re.Pattern.fullmatch>."""
        match = self.wrapped.fullmatch(string, pos, endpos)
        return None if match is None else Match(match)

    def split(self, string: str, maxsplit: int = 0) -> list[str]:
        """Source tracking implementation of <inv:py#re.Pattern.split>."""
        result = []
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
        """Source tracking implementation of <inv:py#re.Pattern.findall>."""
        return [match._group(0) for match in self.finditer(string, pos, endpos)]

    def finditer(self, string: str, pos: int = 0, endpos: int = sys.maxsize) -> Iterator[Match]:
        """Source tracking wrapper for <inv:py#re.Pattern.finditer>."""
        return map(Match, self.wrapped.finditer(string, pos, endpos))

    # TODO sub

    # TODO subn

    @property
    def flags(self) -> int:
        """Forwards to <inv:py#re.Pattern.flags>."""
        return self.wrapped.flags

    @property
    def groups(self) -> int:
        """Forwards to <inv:py#re.Pattern.groups>."""
        return self.wrapped.groups

    @property
    def groupindex(self) -> Mapping[str, int]:
        """Forwards to <inv:py#re.Pattern.groupindex>."""
        return self.wrapped.groupindex

    @property
    def pattern(self) -> str:
        """Forwards to <inv:py#re.Pattern.pattern>."""
        return self.wrapped.pattern


@dataclass(frozen=True)
class Match:
    """Source tracking wrapper for <inv:py#re> `Match` objects."""

    wrapped: re.Match[str]
    """The wrapped plain <inv:py#re> Match object."""

    @property
    def pos(self) -> int:
        """Forwards to <inv:py#re.Match.pos>."""
        return self.wrapped.pos

    @property
    def endpos(self) -> int:
        """Forwards to <inv:py#re.Match.endpos>."""
        return self.wrapped.endpos

    @property
    def string(self) -> str:
        """Forwards to <inv:py#re.Match.string>.

        Even though this forwards to the wrapped object, this will return a <project:#SourceStr>
        when used as match target.
        """
        return self.wrapped.string

    @property
    def lastindex(self) -> Optional[int]:
        """Forwards to <inv:py#re.Match.lastindex>."""
        return self.wrapped.lastindex

    @property
    def lastgroup(self) -> Optional[str]:
        """Forwards to <inv:py#re.Match.lastgroup>."""
        return self.wrapped.lastgroup

    @property
    def re(self) -> Pattern:
        """Source tracking wrapper for <inv:py#re.Match.re>."""
        return Pattern(self.wrapped.re)

    def span(self, group: Union[int, str] = 0) -> tuple[int, int]:
        """Forwards to <inv:py#re.Match.span>."""
        return self.wrapped.span(group)

    def start(self, group: Union[int, str] = 0) -> int:
        """Forwards to <inv:py#re.Match.start>."""
        return self.wrapped.start(group)

    def end(self, group: Union[int, str] = 0) -> int:
        """Forwards to <inv:py#re.Match.end>."""
        return self.wrapped.end(group)

    @overload
    def group(self, group: Literal[0] = 0, /) -> str:
        ...

    @overload
    def group(self, group: str | int, /) -> Optional[str]:
        ...

    @overload
    def group(
        self,
        group1: str | int,
        group2: str | int,
        /,
        *groups: str | int,
    ) -> tuple[Optional[str], ...]:
        ...

    def group(self, *groups: str | int) -> Union[Optional[str], tuple[Optional[str], ...]]:
        """Source tracking wrapper for <inv:py#re.Match.group>."""
        if not groups:
            return self._group(0)
        elif len(groups) == 1:
            return self._group(groups[0])
        return tuple(self._group(group) for group in groups)

    def __getitem__(self, group: Union[int, str]) -> Optional[str]:
        """Source tracking wrapper for <inv:py#re.Match.__getitem__>."""
        group_str = self._group(group)
        return group_str

    @overload
    def _group(self, group: Literal[0], default: Any = None) -> str:
        ...

    @overload
    def _group(self, group: Union[int, str], default: _T) -> Union[str, _T]:
        ...

    @overload
    def _group(self, group: Union[int, str]) -> Optional[str]:
        ...

    def _group(self, group: Union[int, str], default: Any = None) -> Any:
        if group == 0:
            return self.string[self.start() : self.end()]
        span = self.wrapped.span(group)
        if span == (-1, -1):
            return default
        return self.string[span[0] : span[1]]

    @overload
    def groups(self) -> tuple[Optional[str], ...]:
        ...

    @overload
    def groups(self, default: _T) -> tuple[Union[str, _T], ...]:
        ...

    def groups(self, default: Any = None) -> tuple[Any, ...]:
        """Source tracking wrapper for <inv:py#re.Match.groups>."""
        return tuple(self._group(group, default) for group in range(1, 1 + self.wrapped.re.groups))

    @overload
    def groupdict(self) -> dict[str, Optional[str]]:
        ...

    @overload
    def groupdict(self, default: _T) -> dict[str, Union[str, _T]]:
        ...

    def groupdict(self, default: Any = None) -> dict[str, Any]:
        """Source tracking wrapper for <inv:py#re.Match.groupdict>."""
        return {name: self._group(name, default) for name in self.wrapped.re.groupindex.keys()}

    # TODO expand


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
