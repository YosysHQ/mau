"""Strings With Source Tracking

This module provides a string type {py:func}`SourceStr` which remembers the source it originates
from.
"""
from __future__ import annotations

import bisect
import dataclasses
import itertools
import re as stdlib_re
import typing
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Callable, Optional, Union

from typing_extensions import SupportsIndex

from . import re

_RE_NEWLINE = stdlib_re.compile(r"\n")
_RE_SPLITLINES = stdlib_re.compile(r"\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]")
_RE_WHITESPACE = stdlib_re.compile(r"\s+")


@dataclass(init=False, frozen=True, repr=False)
class SourceStr(str):
    """String type which remembers the source it originates from.

    A {py:class}`SourceStr` inherits from <inv:py#str> but has an additional attribute `source_map`
    to track the string's origin. When a `SourceStr` operation returns a new string, e.g. when you
    slice or concatenate strings, the resulting string will often be a `SourceStr` with the
    `source_map` attribute set accordingly.
    """

    source_map: SourceMap
    """The source map associated with this string.

    Prefer using {py:func}`source_map` to access this, unless you know for certain that your target
    string is a `SourceStr`.
    """

    # The str builtin is special so we override __new__ instead of __init__
    def __new__(cls, value: str, source_map: Optional[SourceMap] = None):
        """
        :param source_map: The source map to associate with the string. If not given, this actually
            returns a plain <inv:py#str>.

        """
        if source_map is None or not value:
            # Without a source map, we can just use the builtin str
            return value

        new = str.__new__(cls, value)

        assert len(value) == len(source_map)

        # This is a frozen dataclass (to match str's immutability), so we need to use
        # __setattr__ to initialize the fields
        object.__setattr__(new, "source_map", source_map)
        return new

    def __getitem__(self, key: SupportsIndex | slice) -> SourceStr:
        """Source tracking slicing.

        Not all slicing operations are source tracking, but `[start:stop]`, `[start:]`, `[:stop]`
        and `[:]` are.
        """
        return SourceStr(super().__getitem__(key), self.source_map[key])

    def __add__(self, other: str) -> SourceStr:
        """Source tracking concatenation."""
        return SourceStr(super().__add__(other), self.source_map + source_map(other))

    def __radd__(self, other: str) -> SourceStr:
        return SourceStr(other.__add__(self), source_map(other) + self.source_map)

    def __str__(self) -> SourceStr:
        return self

    def splitlines(self, keepends: bool = False) -> list[SourceStr]:
        """Source tracking implementation of <inv:py#str.splitlines>."""
        result = []
        pos = 0
        for match in _RE_SPLITLINES.finditer(self):
            result.append(self[pos : match.end() if keepends else match.start()])
            pos = match.end()
        if pos < len(self):
            result.append(self[pos:])
        return result

    def split(self, sep: str | None = None, maxsplit: int = -1) -> list[SourceStr]:
        """Source tracking implementation of <inv:py#str.split>."""
        if maxsplit == 0:
            if sep is None:
                stripped = self.lstrip()
                return [stripped] if stripped else []
            else:
                return [self]

        if sep is None:
            if maxsplit == 0:
                return [self.lstrip()]
            sep_re = _RE_WHITESPACE
        else:
            if not sep:
                raise ValueError("empty separator")
            sep_re = stdlib_re.compile(stdlib_re.escape(sep))

        result = []

        pos = 0

        for match in sep_re.finditer(self):
            if sep is None and match.start() == 0:
                # Skip leading whitespace
                pos = match.end()
                continue
            result.append(self[pos : match.start()])
            pos = match.end()
            if maxsplit >= 0 and len(result) == maxsplit:
                break

        if sep is not None or pos < len(self):
            result.append(self[pos:])

        return result

    def strip(self, chars: str | None = None) -> SourceStr:
        """Source tracking implementation of <inv:py#str.strip>."""
        chars_re = f"[{stdlib_re.escape(chars)}]" if chars is not None else r"\s"

        if rmatch := stdlib_re.search(f"{chars_re}+$", self):
            if lmatch := stdlib_re.match(f"{chars_re}+", self):
                return self[lmatch.end() : rmatch.start()]
            return self[: rmatch.start()]
        else:
            return self.lstrip(chars)

    def rstrip(self, chars: str | None = None) -> SourceStr:
        """Source tracking implementation of <inv:py#str.rstrip>."""
        chars_re = f"[{stdlib_re.escape(chars)}]" if chars is not None else r"\s"
        if match := stdlib_re.search(f"{chars_re}+$", self):
            return self[: match.start()]
        else:
            return self

    def lstrip(self, chars: str | None = None) -> SourceStr:
        """Source tracking implementation of <inv:py#str.lstrip>."""
        chars_re = f"[{stdlib_re.escape(chars)}]" if chars is not None else r"\s"
        if match := stdlib_re.match(f"{chars_re}+", self):
            return self[match.end() :]
        else:
            return self


def source_map(string: str) -> SourceMap:
    """The source map of a string."""

    if isinstance(string, SourceStr):
        return string.source_map
    else:
        return SourceMap(len=len(string), spans=())


def read_file(
    path: Union[PathLike, str],
    *,
    store_content: Optional[bool] = None,
    relative_to: Optional[PathLike] = None,
) -> SourceStr:
    """Read a file into a {py:class}`SourceStr` that track's its source.

    :param path: The path to the file to read.

    :param store_content: Whether to store the file's content in memory even when only parts of it
        are still referenced. By default only files below 1MiB are stored, but this option can force
        or prevent storing the content.

    :param relative_to: The path to resolve relative paths against. If not given, the current
        working directory is used.

    :returns: A {py:class}`SourceStr` that tracks the file's source.
    """
    user_path = Path(path)
    if relative_to is not None:
        relative_to = Path(relative_to)
        absolute_path = (relative_to / user_path).absolute()
    else:
        absolute_path = user_path.absolute()

    return _from_content(
        absolute_path,
        absolute_path.read_text(),
        store_content=store_content,
        user_path=user_path,
    )


def _from_content(
    absolute_path: Path,
    content: str,
    *,
    store_content: Optional[bool] = None,
    user_path: Optional[Path] = None,
) -> SourceStr:
    if user_path is None:
        user_path = absolute_path

    cached_content = content

    newlines = tuple(match.start() for match in _RE_NEWLINE.finditer(content))

    if not (store_content or (store_content is None and len(content) < 1024 * 1024)):
        cached_content = None

    source_file = SourceFile(
        user_path=user_path,
        absolute_path=absolute_path,
        newlines=newlines,
        content=cached_content,
    )

    span = SourceMapSpan(str_start=0, len=len(content), file=source_file, file_start=0)

    return SourceStr(content, SourceMap(len=len(content), spans=(span,)))


@dataclass(frozen=True, repr=False)
class SourceSpans:
    """A collection of source spans."""

    spans: tuple[SourceSpan, ...]
    """Each span covers a contiguous part of a source file.

    """

    def _str(self, to_str: Callable[[SourceSpan], str]) -> str:
        if self:
            return ",".join(map(to_str, self.spans))
        else:
            return "<unknown>"

    def __str__(self) -> str:
        return self._str(str)

    def __repr__(self) -> str:
        return self._str(repr)

    def close_gaps(self, max_gap=3) -> SourceSpans:
        """Sorts contained spans and merges almost adjacent spans.

        :param max_gap: The maximum gap between two spans that will be merged.
        :returns: A new {py:class}`SourceSpans` with sorted and merged spans.
        """
        spans = []
        file_order = {}
        for span in self.spans:
            file_order[span.file] = len(file_order)
        for span in sorted(self.spans, key=lambda span: (file_order[span.file], span.file_start)):
            if not spans:
                spans.append(span)
                continue
            last = spans[-1]
            if last.file == span.file and last.file_end + max_gap >= span.file_start:
                spans[-1] = dataclasses.replace(
                    last, len=max(last.len, span.file_end - last.file_start)
                )
        return SourceSpans(spans=tuple(spans))

    def __add__(self, other: SourceSpans) -> SourceSpans:
        """Concatenates two collections of source spans."""
        return SourceSpans(spans=self.spans + other.spans)

    def __bool__(self):
        return bool(self.spans)


@dataclass(frozen=True, repr=False)
class SourceMap(SourceSpans):
    """Maps string contents to their source files.

    It can map different spans of the string to different source files or different parts of the
    same source file.

    The SourceMapSpans are stored in string order, to allow for binary searches.
    """

    len: int
    """The length of the string."""

    spans: tuple[SourceMapSpan, ...]
    """Each span maps a contiguous part of the string to a part of a source file.

    They are stored in order, to allow for binary searches.
    """

    def __getitem__(self, key: SupportsIndex | slice) -> Optional[SourceMap]:
        if isinstance(key, slice) and (key.step is None or key.step == 1):
            start = self._index(key.start, 0)
            end = self._index(key.stop, None)
            return self._for_subslice(start, end)

    def __len__(self) -> int:
        return self.len

    @typing.overload
    def _index(self, index: Optional[int], default: int) -> int:
        ...

    @typing.overload
    def _index(self, index: Optional[int], default: None) -> None:
        ...

    def _index(self, index: Optional[int], default: Optional[int]) -> Optional[int]:
        if index is None:
            return default
        elif index < 0:
            return self.len + index
        else:
            return index

    def _for_subslice(self, start: int, end: Optional[int]) -> SourceMap:
        end_pos = self.len if end is None else end

        if start >= end_pos:
            return SourceMap(len=0, spans=())

        span_indices = range(self._bisect_starting_at(start), self._bisect_ending_at(end))

        output_spans = tuple(
            self.spans[i]._for_subslice_unchecked(start, end) for i in span_indices
        )

        return SourceMap(len=end_pos - start, spans=output_spans)

    def _bisect_starting_at(self, at: int) -> int:
        """Index of the first span that overlaps a subslice.

        :param at: The start of the subslice.
        :returns: The index of the first span that overlaps the subslice.
        """
        # FUTURE Python 3.10 use bisect.bisect_right with the new key parameter
        lo = 0
        hi = len(self.spans)
        while lo < hi:
            mid = (lo + hi) // 2
            if at < self.spans[mid].str_end:
                hi = mid
            else:
                lo = mid + 1
        return lo

    def _bisect_ending_at(self, at: Optional[int]) -> int:
        """Index after the last span that overlaps a subslice.

        :param at: The end of the subslice or `None` if it extends to the end of the string.
        :returns: The index of the last span that overlaps the subslice.
        """
        # FUTURE Python 3.10 use bisect.bisect_left with the new key parameter
        if at is None:
            return len(self.spans)
        lo = 0
        hi = len(self.spans)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.spans[mid].str_start < at:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def __add__(self, other: SourceMap) -> SourceMap:
        if not other.spans:
            return SourceMap(len=self.len + other.len, spans=self.spans)
        if self.spans and other.spans:
            self_last = self.spans[-1]
            other_first = other.spans[0]
            if (
                self_last.str_end == self.len
                and other_first.str_start == 0
                and self_last.file == other_first.file
                and self_last.file_end == other_first.file_start
            ):
                return SourceMap(
                    len=self.len + other.len,
                    spans=tuple(
                        itertools.chain(
                            self.spans[:-1],
                            (dataclasses.replace(self_last, len=self_last.len + other_first.len),),
                            (
                                dataclasses.replace(span, str_start=span.str_start + self.len)
                                for span in other.spans[1:]
                            ),
                        )
                    ),
                )

        return SourceMap(
            len=self.len + other.len,
            spans=tuple(
                itertools.chain(
                    self.spans,
                    (
                        dataclasses.replace(span, str_start=span.str_start + self.len)
                        for span in other.spans
                    ),
                )
            ),
        )

    @property
    def simple_span(self) -> bool:
        """Whether the source map is a single span that maps the entire string."""
        return (
            len(self.spans) == 1 and self.spans[0].str_start == 0 and self.spans[0].len == self.len
        )

    def _str(self, to_str: Callable[[SourceMapSpan], str]) -> str:
        if self.simple_span:
            return to_str(self.spans[0])
        else:
            out = []

            pos = 0

            for span in self.spans:
                if out:
                    out.append(",")
                if span.str_start > pos:
                    chars = span.str_start - pos
                    if chars > 4:
                        out.append(f"..{chars}..")
                    else:
                        out.append("." * chars)
                    out.append(",")
                out.append(to_str(span))
                pos = span.str_end
            if pos < self.len:
                if out:
                    out.append(",")
                chars = self.len - pos
                if chars > 4:
                    out.append(f"..{chars}..")
                else:
                    out.append("." * chars)
            return "".join(out)

    def __str__(self) -> str:
        return self._str(str)

    def __repr__(self) -> str:
        return self._str(repr)

    def detached(self) -> SourceSpans:
        """Returns the source spans of this source map, detached from their position in
        the string."""
        return SourceSpans(
            spans=tuple(
                SourceSpan(len=span.len, file_start=span.file_start, file=span.file)
                for span in self.spans
            ),
        )


@dataclass(frozen=True, repr=False)
class SourceFile:
    """A source file of a string.

    This stores the path to the file and optionally the file's content. The content can be used when
    printing error messages, to show the context of the error.
    """

    user_path: Path
    """The path to the file as given by the user."""

    absolute_path: Path
    """The absolute path to the file."""

    newlines: tuple[int, ...]
    """The indices of all newlines in the file."""

    content: Optional[str] = None
    """The content of the file.

    This is optional as we may not want to store huge files in memory.
    """

    def __str__(self) -> str:
        return f"{self.user_path}"

    def __repr__(self) -> str:
        if self.user_path == self.absolute_path:
            return f"{self.user_path}"
        else:
            return f"{self.user_path}({self.absolute_path})"

    def text_position(self, offset: int) -> tuple[int, int]:
        """Converts a str offset into the file to a line and column number.

        :param at: The offset in the file.
        :returns: A tuple of the line and column number, both starting at 1.
        """
        line = bisect.bisect_left(self.newlines, offset)
        preceding_newline = self.newlines[line - 1] if line > 0 else -1
        return line + 1, offset - preceding_newline


@dataclass(frozen=True, repr=False)
class SourceSpan:
    """A contiguous span within a source file.

    All offsets use Python's native string indexing, i.e. they count unicode codepoints.
    """

    len: int
    """Length of the span."""

    file_start: int
    """Start of the span in the source file."""

    file: SourceFile
    """The source file that contains the span."""

    @property
    def file_end(self) -> int:
        """End of the span in the source file."""
        return self.file_start + self.len

    def __str__(self) -> str:
        return self._str(str(self.file))

    def __repr__(self) -> str:
        return self._str(repr(self.file))

    def _str(self, filename):
        start_line, start_column = self.file.text_position(self.file_start)
        end_line, end_column = self.file.text_position(self.file_end)
        if start_line == end_line:
            return f"{filename}:{start_line}:{start_column}-{end_column}"
        else:
            return f"{filename}:{start_line}:{start_column}-{end_line}:{end_column}"


@dataclass(frozen=True, repr=False)
class SourceMapSpan(SourceSpan):
    """Maps a span of a string to a corresponding span of a source file.

    All offsets use Python's native string indexing, i.e. they count unicode codepoints.
    """

    str_start: int
    """Start of the span in the string."""

    @property
    def str_end(self) -> int:
        """End of the span in the string."""
        return self.str_start + self.len

    def _for_subslice_unchecked(self, start: int, end: Optional[int]) -> SourceMapSpan:
        """Part of the span that overlaps a given subslice of the string.

        This assumes that the span overlaps the subslice, use {py:meth}`_for_subslice` if that is
        not guaranteed.

        :param start: Start of the subslice.
        :param end: End of the subslice. If not present, the end of the string is used.
        :returns: The part of the span that overlaps the subslice.
        """

        str_start = self.str_start
        len = self.len
        file_start = self.file_start

        if start > self.str_start:
            shorten = start - self.str_start
            str_start = 0
            file_start += shorten
            len -= shorten

        if end is not None and start + len > end:
            shorten = start + len - end
            len -= shorten

        return SourceMapSpan(
            str_start=str_start,
            len=len,
            file_start=file_start,
            file=self.file,
        )
