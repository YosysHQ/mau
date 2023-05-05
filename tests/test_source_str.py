import tempfile
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import Optional, Union

import pytest
from hypothesis import given
from hypothesis import strategies as st
from yosys_mau.source_str import (
    SourceStr,
    _from_content,
    read_file,
    source_map,
)


def fake_source_str(
    content: str,
    path: Union[PathLike, str],
    user_path: Optional[Union[PathLike, str]] = None,
) -> SourceStr:
    return _from_content(Path(path), content, user_path=Path(user_path) if user_path else None)


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


@given(st.text(), st.booleans())
def test_splitlines(text, keepends):
    source_text = fake_source_str(text, "input-file")
    assert source_text.splitlines() == text.splitlines()


@given(st.text())
def test_split_whitespace(text):
    source_text = fake_source_str(text, "input-file")
    assert source_text.split() == text.split()


@given(st.text(), st.integers(0, 100))
def test_split_whitespace_maxsplit(text, maxsplit):
    source_text = fake_source_str(text, "input-file")
    assert source_text.split(maxsplit=maxsplit) == text.split(maxsplit=maxsplit)


@given(st.text(), st.text(min_size=1))
def test_split(text, sep):
    source_text = fake_source_str(text, "input-file")
    assert source_text.split(sep) == text.split(sep)


@given(st.text(), st.text(min_size=1), st.integers(0, 100))
def test_split_maxsplit(text, sep, maxsplit):
    source_text = fake_source_str(text, "input-file")
    assert source_text.split(sep, maxsplit) == text.split(sep, maxsplit)


@given(st.text())
def test_split_empty_sep(text):
    source_text = fake_source_str(text, "input-file")
    with pytest.raises(ValueError):
        source_text.split("")


@given(st.text())
def test_strip_whitespace(text):
    source_text = fake_source_str(text, "input-file")
    assert source_text.strip() == text.strip()


@given(st.text())
def test_lstrip_whitespace(text):
    source_text = fake_source_str(text, "input-file")
    assert source_text.lstrip() == text.lstrip()


@given(st.text())
def test_rstrip_whitespace(text):
    source_text = fake_source_str(text, "input-file")
    assert source_text.rstrip() == text.rstrip()


@given(st.text(), st.text(min_size=1))
def test_strip(text, alphabet):
    source_text = fake_source_str(text, "input-file")
    assert source_text.strip(alphabet) == text.strip(alphabet)


@given(st.text(), st.text(min_size=1))
def test_lstrip(text, alphabet):
    source_text = fake_source_str(text, "input-file")
    assert source_text.lstrip(alphabet) == text.lstrip(alphabet)


@given(st.text(), st.text(min_size=1))
def test_rstrip(text, alphabet):
    source_text = fake_source_str(text, "input-file")
    assert source_text.rstrip(alphabet) == text.rstrip(alphabet)


def test_source_map_to_str():
    source_a = fake_source_str("content_a", "file_a")
    source_b = fake_source_str("content_b", "file_b")
    source_c = fake_source_str("content\nc", "/absolute/file_c", "file_c")

    combined = source_a + source_b

    assert str(source_map(combined)) == "file_a:1:1-10,file_b:1:1-10"

    combined = "A = " + source_a + "; B = " + source_b + ";"

    assert str(source_map(combined)) == "....,file_a:1:1-10,..6..,file_b:1:1-10,."

    combined = source_a + "\nsomething else"

    assert str(source_map(combined)) == "file_a:1:1-10,..15.."

    combined = source_c + source_a
    assert str(source_map(combined)) == "file_c:1:1-2:2,file_a:1:1-10"

    combined = source_c + source_a
    assert repr(source_map(combined)) == "file_c(/absolute/file_c):1:1-2:2,file_a:1:1-10"
