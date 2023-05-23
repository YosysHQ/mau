from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import assume, given
from yosys_mau.config_parser import BoolValue, IntValue, StrValue
from yosys_mau.source_str.report import InputError


@given(st.integers())
def test_int_value(some_int: int):
    int_value = IntValue()
    assert int_value.parse(f"{some_int}") == some_int


def test_int_invalid():
    int_value = IntValue()
    with pytest.raises(InputError):
        int_value.parse("not_an_int")


@given(st.integers(max_value=-1))
def test_int_unexpected_negative(some_int: int):
    int_value = IntValue(min=0)
    with pytest.raises(InputError):
        int_value.parse(f"{some_int}")


@given(st.integers(max_value=0))
def test_int_unexpected_nonpositive(some_int: int):
    int_value = IntValue(min=1)
    with pytest.raises(InputError):
        int_value.parse(f"{some_int}")


@given(st.integers(), st.integers())
def test_int_too_small(a: int, b: int):
    assume(a != b)

    int_value = IntValue(min=max(a, b))
    with pytest.raises(InputError):
        int_value.parse(f"{min(a, b)}")


@given(st.integers(), st.integers())
def test_int_too_large(a: int, b: int):
    assume(a != b)

    int_value = IntValue(max=min(a, b))
    with pytest.raises(InputError):
        int_value.parse(f"{max(a, b)}")


@given(st.integers(), st.integers(), st.integers())
def test_int_below_range(a: int, b: int, c: int):
    a, b, c = sorted([a, b, c])
    assume(a < b)

    int_value = IntValue(min=b, max=c)
    with pytest.raises(InputError):
        int_value.parse(f"{a}")


@given(st.integers(), st.integers(), st.integers())
def test_int_above_range(a: int, b: int, c: int):
    a, b, c = sorted([a, b, c])
    assume(b < c)

    int_value = IntValue(min=a, max=b)
    with pytest.raises(InputError):
        int_value.parse(f"{c}")


@given(st.text())
def test_str_value(some_str: str):
    str_value = StrValue(allow_empty=True)
    assert str_value.parse(some_str) == some_str


def test_str_empty():
    str_value = StrValue()
    with pytest.raises(InputError):
        str_value.parse("")


def test_bool_value():
    bool_value = BoolValue()
    assert bool_value.parse("on") is True
    assert bool_value.parse("off") is False


def test_bool_invalid():
    bool_value = BoolValue()
    with pytest.raises(InputError):
        bool_value.parse("not_a_bool")
