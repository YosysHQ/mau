from __future__ import annotations

import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from yosys_mau.source_str import (
    from_content,
    read_file,
    source_map,
)
from yosys_mau.source_str import (
    re as source_re,
)


@contextmanager
def with_temp_file(content: str):
    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(content)
        f.flush()

        yield Path(f.name)


EXAMPLE_FILE_CONTENT = """\
This is an example file.
It has multiple lines.
More than two, in fact.
"""


def test_line_spans():
    with with_temp_file(EXAMPLE_FILE_CONTENT) as path:
        content = read_file(path.name, relative_to=path.parent)

        assert content == EXAMPLE_FILE_CONTENT
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            assert str(source_map(line)) == f"{path.name}:{i}:1-{len(line) + 1}"


def test_source_map_to_str():
    source_a = from_content("content_a", "file_a")
    source_b = from_content("content_b", "file_b")
    source_c = from_content("content\nc", "file_c", relative_to="/absolute")
    source_d = from_content("content_d", "/file_d")

    combined = source_a + source_b

    assert str(source_map(combined)) == "file_a:1:1-10,file_b:1:1-10"

    combined = "A = " + source_a + "; B = " + source_b + ";"

    assert str(source_map(combined)) == "....,file_a:1:1-10,..6..,file_b:1:1-10,."

    combined = source_a + "\nsomething else"

    assert str(source_map(combined)) == "file_a:1:1-10,..15.."

    combined = source_c + source_a
    assert str(source_map(combined)) == "file_c:1:1-2:2,file_a:1:1-10"

    combined = source_c + source_d
    assert repr(source_map(combined)) == "file_c(/absolute/file_c):1:1-2:2,/file_d:1:1-10"


@given(st.text(), st.booleans())
def test_splitlines(text: str, keepends: bool):
    source_text = from_content(text, "input-file")
    assert source_text.splitlines() == text.splitlines()


@given(st.text())
def test_split_whitespace(text: str):
    source_text = from_content(text, "input-file")
    assert source_text.split() == text.split()


@given(st.text(), st.integers(0, 100))
def test_split_whitespace_maxsplit(text: str, maxsplit: int):
    source_text = from_content(text, "input-file")
    assert source_text.split(maxsplit=maxsplit) == text.split(maxsplit=maxsplit)


@given(st.text(), st.text(min_size=1))
def test_split(text: str, sep: str):
    source_text = from_content(text, "input-file")
    assert source_text.split(sep) == text.split(sep)


@given(st.text(), st.text(min_size=1), st.integers(0, 100))
def test_split_maxsplit(text: str, sep: str, maxsplit: int):
    source_text = from_content(text, "input-file")
    assert source_text.split(sep, maxsplit) == text.split(sep, maxsplit)


@given(st.text())
def test_split_empty_sep(text: str):
    source_text = from_content(text, "input-file")
    with pytest.raises(ValueError):
        source_text.split("")


@given(st.text())
def test_strip_whitespace(text: str):
    source_text = from_content(text, "input-file")
    assert source_text.strip() == text.strip()


@given(st.text())
def test_lstrip_whitespace(text: str):
    source_text = from_content(text, "input-file")
    assert source_text.lstrip() == text.lstrip()


@given(st.text())
def test_rstrip_whitespace(text: str):
    source_text = from_content(text, "input-file")
    assert source_text.rstrip() == text.rstrip()


@given(st.text(), st.text(min_size=1))
def test_strip(text: str, alphabet: str):
    source_text = from_content(text, "input-file")
    assert source_text.strip(alphabet) == text.strip(alphabet)


@given(st.text(), st.text(min_size=1))
def test_lstrip(text: str, alphabet: str):
    source_text = from_content(text, "input-file")
    assert source_text.lstrip(alphabet) == text.lstrip(alphabet)


@given(st.text(), st.text(min_size=1))
def test_rstrip(text: str, alphabet: str):
    source_text = from_content(text, "input-file")
    assert source_text.rstrip(alphabet) == text.rstrip(alphabet)


@given(st.text(), st.text(min_size=1), st.text(), st.integers(-1, 10))
def test_replace(text: str, old: str, new: str, count: int):
    source_text = from_content(text, "input-file")
    assert source_text.replace(old, new, count) == text.replace(old, new, count)


def check_re_match(source_match: source_re.Match | None, match: re.Match[str] | None):
    if match is None:
        assert source_match is None
        return
    assert source_match is not None
    all_groups = [*range(1 + match.re.groups), *match.re.groupindex.keys()]
    assert source_match.group() == match.group()
    assert source_match.group(*all_groups) == match.group(*all_groups)
    assert source_match.groups() == match.groups()
    for i in all_groups:
        assert source_match.span(i) == match.span(i)
        assert source_match.group(i) == match.group(i)
        assert source_match[i] == match[i]
    assert source_match.groupdict() == match.groupdict()
    assert source_match.pos == match.pos
    assert source_match.endpos == match.endpos
    assert source_match.lastindex == match.lastindex
    assert source_match.lastgroup == match.lastgroup

    try:
        match.group("not-present")
    except IndexError:
        with pytest.raises(IndexError):
            source_match.group("not-present")


@given(st.text(), st.lists(st.text(), min_size=1))
def test_re_search(text: str, words: list[str]):
    source_text = from_content(text, "input-file")
    regex = "|".join(re.escape(word) for word in words)
    check_re_match(source_re.search(regex, source_text), re.search(regex, text))


@given(st.text(), st.lists(st.text(), min_size=1))
def test_re_match(text: str, words: list[str]):
    source_text = from_content(text, "input-file")
    regex = "|".join(re.escape(word) for word in words)
    check_re_match(source_re.match(regex, source_text), re.match(regex, text))


@given(st.text(), st.lists(st.text(), min_size=1))
def test_re_fullmatch(text: str, words: list[str]):
    source_text = from_content(text, "input-file")
    regex = "|".join(re.escape(word) for word in words)
    check_re_match(source_re.fullmatch(regex, source_text), re.fullmatch(regex, text))


@given(st.text(), st.lists(st.text(), min_size=1), st.integers(0, 10))
def test_re_split(text: str, words: list[str], maxsplit: int):
    source_text = from_content(text, "input-file")
    regex = "|".join(re.escape(word) for word in words)
    assert source_re.split(regex, source_text, maxsplit) == re.split(regex, text, maxsplit)


@given(st.text(), st.lists(st.text(), min_size=1))
def test_re_findall(text: str, words: list[str]):
    source_text = from_content(text, "input-file")
    regex = "|".join(re.escape(word) for word in words)
    assert source_re.findall(regex, source_text) == re.findall(regex, text)


@given(st.text(), st.lists(st.text(), min_size=1), st.integers(0, 100), st.integers(0, 100))
def test_re_findall_pos(text: str, words: list[str], pos: int, endpos: int):
    source_text = from_content(text, "input-file")
    regex = "|".join(re.escape(word) for word in words)
    source_pattern = source_re.compile(regex)
    pattern = re.compile(regex)
    assert source_pattern.findall(source_text, pos, endpos) == pattern.findall(text, pos, endpos)


@given(
    st.text(),
    st.lists(st.text(), min_size=1),
    st.sets(st.text(alphabet="abc", min_size=1, max_size=10)),
)
def test_re_finditer(text: str, words: list[str], named_groups: set[str]):
    source_text = from_content(text, "input-file")
    regex = "|".join(
        [f"({re.escape(word)})" for word in words]
        + [f"(?P<{name}>{name})" for name in named_groups]
    )

    source_matches = list(source_re.finditer(regex, source_text))
    matches = list(re.finditer(regex, text))

    assert len(source_matches) == len(matches)
    for source_match, match in zip(source_matches, matches):
        check_re_match(source_match, match)


@given(
    st.text(),
    st.lists(st.text(), min_size=1),
    st.sets(st.text(alphabet="abc", min_size=1, max_size=10)),
    st.integers(0, 100),
    st.integers(0, 100),
)
def test_re_finditer_pos(
    text: str, words: list[str], named_groups: set[str], pos: int, endpos: int
):
    source_text = from_content(text, "input-file")
    regex = "|".join(
        [f"({re.escape(word)})" for word in words]
        + [f"(?P<{name}>{name})" for name in named_groups]
    )
    source_pattern = source_re.compile(regex)
    pattern = re.compile(regex)

    source_matches = list(source_pattern.finditer(source_text, pos, endpos))
    matches = list(pattern.finditer(text, pos, endpos))

    assert len(source_matches) == len(matches)
    for source_match, match in zip(source_matches, matches):
        check_re_match(source_match, match)


@given(st.text(alphabet="\\gab<>0123456789"))
def test_re_expand(template: str):
    text = "foo"
    source_text = from_content(text, "input-file")

    match = re.match("foo", text)
    source_match = source_re.match("foo", source_text)

    assert match is not None
    assert source_match is not None

    try:
        expected = True, match.expand(template)
    except Exception as e:
        expected = False, str(e)

    try:
        obtained = True, source_match.expand(template)
    except Exception as e:
        obtained = False, str(e)

    assert expected == obtained


@given(st.text(), st.lists(st.text(), min_size=1), st.text(), st.integers(0, 10))
def test_re_subn(text: str, words: str, repl: str, count: int):
    source_text = from_content(text, "input-file")
    regex = "|".join(re.escape(word) for word in words)

    def repl_fn(match: re.Match[str] | source_re.Match) -> str:
        return repl + match[0] + repl

    assert source_re.subn(regex, repl_fn, source_text, count) == re.subn(
        regex, repl_fn, text, count
    )
