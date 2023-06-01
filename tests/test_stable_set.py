from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from yosys_mau.stable_set import StableSet


@given(st.lists(st.text(), min_size=1))
def test_stable(items: list[str]):
    as_set = set(items)
    as_stable_set = StableSet(items)
    assert set(as_stable_set) == as_set
    assert list(as_stable_set) == list({value: None for value in items})


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_union(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert as_stable_set_a | as_stable_set_b == as_set_a | as_set_b


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_intersection(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert as_stable_set_a & as_stable_set_b == as_set_a & as_set_b


@given(st.lists(st.integers()), st.lists(st.lists(st.integers())))
def test_intersection_many(items_a: list[str], items_b: list[list[str]]):
    as_set_a, as_sets_b = set(items_a), [set(items) for items in items_b]
    as_stable_set_a, as_stable_sets_b = StableSet(items_a), [StableSet(items) for items in items_b]
    assert as_stable_set_a.intersection(*as_stable_sets_b) == as_set_a.intersection(*as_sets_b)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_difference(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert as_stable_set_a - as_stable_set_b == as_set_a - as_set_b


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_symmetric_difference(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert as_stable_set_a ^ as_stable_set_b == as_set_a ^ as_set_b


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_eq(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert (as_stable_set_a == as_stable_set_b) == (as_set_a == as_set_b)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_issubset(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert (as_stable_set_a <= as_stable_set_b) == (as_set_a <= as_set_b)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_issubset_list(items_a: list[str], items_b: list[str]):
    as_set_a = set(items_a)
    as_stable_set_a = StableSet(items_a)
    assert as_set_a.issubset(items_b) == as_stable_set_a.issubset(items_b)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_issuperset(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert (as_stable_set_a >= as_stable_set_b) == (as_set_a >= as_set_b)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_strict_issubset(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert (as_stable_set_a < as_stable_set_b) == (as_set_a < as_set_b)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_strict_issuperset(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert (as_stable_set_a > as_stable_set_b) == (as_set_a > as_set_b)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_isdisjoint(items_a: list[str], items_b: list[str]):
    as_set_a, as_set_b = set(items_a), set(items_b)
    as_stable_set_a, as_stable_set_b = StableSet(items_a), StableSet(items_b)
    assert (as_stable_set_a.isdisjoint(as_stable_set_b)) == (as_set_a.isdisjoint(as_set_b))


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_update(items_a: list[str], items_b: list[str]):
    as_set_a = set(items_a)
    as_set_a |= set(items_b)
    as_stable_set_a = StableSet(items_a)
    as_stable_set_a |= StableSet(items_b)

    assert as_stable_set_a == as_set_a


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_intersection_update(items_a: list[str], items_b: list[str]):
    as_set_a = set(items_a)
    as_set_a &= set(items_b)
    as_stable_set_a = StableSet(items_a)
    as_stable_set_a &= StableSet(items_b)

    assert as_stable_set_a == as_set_a


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_difference_update(items_a: list[str], items_b: list[str]):
    as_set_a = set(items_a)
    as_set_a -= set(items_b)
    as_stable_set_a = StableSet(items_a)
    as_stable_set_a -= StableSet(items_b)

    assert as_stable_set_a == as_set_a


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_symmetric_difference_update(items_a: list[str], items_b: list[str]):
    as_set_a = set(items_a)
    as_set_a ^= set(items_b)
    as_stable_set_a = StableSet(items_a)
    as_stable_set_a ^= StableSet(items_b)

    assert as_stable_set_a == as_set_a
