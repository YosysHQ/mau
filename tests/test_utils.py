from __future__ import annotations

import dataclasses
from typing import Any


def assert_dataclass_match(obj: Any, dataclass: type, **expected_values: dict[str, Any]):
    assert isinstance(obj, dataclass)
    all_fields = {field.name: getattr(obj, field.name) for field in dataclasses.fields(obj)}
    checked_fields = {field: all_fields[field] for field in expected_values if field in all_fields}
    assert checked_fields == expected_values


def assert_dataclass_list_match(
    objs: list[Any], dataclass: type, expected_values: list[dict[str, Any]]
):
    assert len(objs) == len(expected_values)
    for obj, expected in zip(objs, expected_values):
        dataclasses.asdict(obj)
        assert_dataclass_match(obj, dataclass, **expected)
        pass
