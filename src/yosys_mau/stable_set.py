from __future__ import annotations

from typing import Collection, Container, Iterable, Iterator, Sized, TypeVar

from typing_extensions import Self

__all__ = ["StableSet"]

T = TypeVar("T")

# TODO add to API docs


class StableSet(Collection[T]):
    """A set with a deterministic and stable iteration order."""

    __slots__ = ("_inner",)

    _inner: dict[T, None]

    def __init__(self, iterable: Iterable[T] = ()) -> None:
        self._inner = {item: None for item in iterable}

    @staticmethod
    def _from_inner(inner: dict[T, None]) -> StableSet[T]:
        self: StableSet[T] = object.__new__(StableSet)
        self._inner = inner
        return self

    def copy(self) -> StableSet[T]:
        return self._from_inner(self._inner.copy())

    def __iter__(self) -> Iterator[T]:
        return iter(self._inner)

    def __bool__(self) -> bool:
        return bool(self._inner)

    def __len__(self) -> int:
        return len(self._inner)

    def __contains__(self, item: object) -> bool:
        return item in self._inner

    def __repr__(self) -> str:
        return f"{type(self).__name__}({list(self)!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, set):
            return set(self) == other
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        return self._inner == other._inner  # type: ignore

    def isdisjoint(self, other: Iterable[T]) -> bool:
        if isinstance(other, Sized) and isinstance(other, Container) and len(other) > len(self):
            return not any(value in other for value in self)

        return not any(value in self for value in other)

    def issubset(self, other: Collection[T]) -> bool:
        if isinstance(other, (list, tuple)) and len(other) * len(self) > 16:
            other = set(other)
        return all(value in other for value in self)

    def __le__(self, other: Self) -> bool:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        return self.issubset(other)

    def __lt__(self, other: Self) -> bool:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        return self.issubset(other) and self != other

    def issuperset(self, other: Collection[T]) -> bool:
        return all(value in self for value in other)

    def __ge__(self, other: Self) -> bool:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        return self.issuperset(other)

    def __gt__(self, other: Self) -> bool:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        return self.issuperset(other) and self != other

    def union(self, *others: Iterable[T]) -> StableSet[T]:
        """Return the union of this set and all others."""
        result = self.copy()
        result.update(*others)
        return result

    def __or__(self, other: Self) -> StableSet[T]:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        return self.union(other)

    def intersection(self, *others: Iterable[T]) -> StableSet[T]:
        """Return the intersection of this set and all others."""
        keep = set(self)
        keep.intersection_update(*others)
        return StableSet._from_inner({item: None for item in self if item in keep})

    def __and__(self, other: Self) -> StableSet[T]:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        if len(other) > len(self):
            return StableSet(value for value in self if value in other)
        return StableSet(value for value in other if value in self)

    def difference(self, *others: Iterable[T]) -> StableSet[T]:
        """Return the difference of this set and all others."""
        keep = set(self)
        keep.difference_update(*others)
        return StableSet._from_inner({item: None for item in self if item in keep})

    def __sub__(self, other: Self) -> StableSet[T]:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        return self.difference(other)

    def symmetric_difference(self, other: Iterable[T]) -> StableSet[T]:
        """Return the symmetric difference of this set and another."""
        if isinstance(other, StableSet) and len(other) > len(self):
            other, self = self, other
        result = self.copy()
        result.symmetric_difference_update(other)
        return result

    def __xor__(self, other: Self) -> StableSet[T]:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        return self.symmetric_difference(other)

    def add(self, item: T) -> None:
        """Add an element to the set."""
        self._inner[item] = None

    def remove(self, item: T) -> None:
        """Remove an element from the set.

        Raises a `KeyError` if the element is not present.
        """
        del self._inner[item]

    def discard(self, item: T) -> None:
        """Remove an element from the set if it is present."""
        self._inner.pop(item, None)

    def pop(self) -> T:
        """Remove and return an arbitrary element.

        Raises a `KeyError` if the set is empty.
        """
        item, _none = self._inner.popitem()
        return item

    def clear(self) -> None:
        """Remove all elements from the set."""
        self._inner.clear()

    def update(self, *others: Iterable[T]) -> None:
        """Update the set, adding elements from all others."""
        for other in others:
            for item in other:
                self._inner[item] = None

    def __ior__(self, other: Self) -> StableSet[T]:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        self.update(other)
        return self

    def intersection_update(self, *others: Iterable[T]) -> None:
        """Update the set, keeping only elements found in all others."""
        keep = set(self)
        keep.intersection_update(*others)
        self._inner = {item: None for item in self if item in keep}

    def __iand__(self, other: Self) -> StableSet[T]:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        self.intersection_update(other)
        return self

    def difference_update(self, *others: Iterable[T]) -> None:
        """Update the set, removing elements found in any other."""
        keep = set(self)
        keep.difference_update(*others)
        self._inner = {item: None for item in self if item in keep}

    def __isub__(self, other: Self) -> StableSet[T]:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        self.difference_update(other)
        return self

    def symmetric_difference_update(self, other: Iterable[T]) -> None:
        """Update the set, keeping only elements found in either set, but not in both."""
        for value in other:
            if value in self:
                self.remove(value)
            else:
                self.add(value)

    def __ixor__(self, other: Self) -> StableSet[T]:
        if not isinstance(other, StableSet):
            return NotImplemented  # pragma: no cover
        self.symmetric_difference_update(other)
        return self
