from __future__ import annotations

import typing
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from yosys_mau.source_str import report

if typing.TYPE_CHECKING:
    pass

T = TypeVar("T")


class ValueParser(Generic[T], metaclass=ABCMeta):
    """A parser for a single value."""

    def __init__(self) -> None:
        pass

    @abstractmethod
    def parse(self, input: str) -> T:
        """Parse a value."""
        ...


@dataclass
class IntValue(ValueParser[int]):
    """A parser for an integer value."""

    min: int | None = None
    """Minimum value (inclusive)."""

    max: int | None = None
    """Maximum value (inclusive)."""

    def parse(self, input: str) -> int:
        """Parse an integer value."""
        try:
            value = int(input)
        except ValueError:
            raise report.InputError(input, "expected an integer")
        in_range = (self.min is None or value >= self.min) and (
            self.max is None or value <= self.max
        )
        if not in_range:
            if self.max is None and self.min == 0:
                raise report.InputError(input, "expected a non-negative integer")
            elif self.max is None and self.min == 1:
                raise report.InputError(input, "expected a positive integer")
            elif self.max is None:
                raise report.InputError(input, f"expected an integer value not below {self.min}")
            elif self.min is None:
                raise report.InputError(input, f"expected an integer value not above {self.max}")
            else:
                raise report.InputError(
                    input, f"expected an integer value in {self.min}..{self.max}"
                )
        return value


@dataclass
class StrValue(ValueParser[str]):
    """A parser for a string value."""

    allow_empty: bool = False

    def parse(self, input: str) -> str:
        """Parse a string value."""
        if not self.allow_empty and not input:
            raise report.InputError(input, "expected a non-empty string")
        return input


class BoolValue(ValueParser[bool]):
    """A parser for a boolean value using ``"on"`` and ``"off"`` for ``True`` and ``False``."""

    def parse(self, input: str) -> bool:
        """Parse a boolean value."""
        if input == "on":
            return True
        elif input == "off":
            return False
        else:
            raise report.InputError(input, "expected `on` or `off`")
