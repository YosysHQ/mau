from __future__ import annotations

from typing import Any, Generic, TypeVar
from weakref import WeakKeyDictionary

from ._task import Task, current_task_or_none

T = TypeVar("T")


class _MISSING_TYPE:
    pass


MISSING = _MISSING_TYPE()


class TaskContextDescriptor(Generic[T]):
    __data: WeakKeyDictionary[Task, T]
    __default: T
    __owner: Any
    __name: str | None

    def __init__(self, default: T | _MISSING_TYPE = MISSING) -> None:
        self.__data = WeakKeyDictionary()
        if default is not MISSING:
            self.default = default  # type: ignore
        self.__owner = None
        self.__name = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.__owner = owner
        self.__name = name

    def __attr_name(self) -> str:
        if self.__name is None:
            return repr(self)
        else:
            return f"{self.__owner.__qualname__}.{self.__name}"

    def __get__(self, instance: Any, owner: type) -> T:
        cursor = current_task_or_none()
        while cursor is not None:
            try:
                return self.__data[cursor]
            except KeyError:
                cursor = cursor.parent
        try:
            return self.default
        except AttributeError:
            raise AttributeError(f"Context variable {self.__attr_name()} not set") from None

    def __set__(self, instance: Any, value: T) -> None:
        task = current_task_or_none()
        if task is None:
            self.default = value
        else:
            self.__data[task] = value

    def __delete__(self, instance: Any) -> None:
        task = current_task_or_none()
        if task is None:
            try:
                del self.default
            except KeyError:
                raise AttributeError(
                    f"Context variable {self.__attr_name()} not set for the current task"
                ) from None
        else:
            del self.__data[task]

    @property
    def default(self) -> T:
        return self.__default

    @default.setter
    def default(self, value: T) -> None:
        self.__default = value

    @default.deleter
    def default(self) -> None:
        del self.__default


class InlineContextVar(Generic[T]):
    def __init__(self, context: Any, name: str):
        self.__context = context
        self.__name = name

    def __get__(self, instance: Any, owner: type) -> T:
        with instance.as_current_task():
            return getattr(self.__context, self.__name)

    def __set__(self, instance: Any, value: T) -> None:
        with instance.as_current_task():
            setattr(self.__context, self.__name, value)

    def __delete__(self, instance: Any) -> None:
        with instance.as_current_task():
            delattr(self.__context, self.__name)


def task_context_class(cls: type[T]) -> type[T]:
    for name in getattr(cls, "__annotations__", ()):
        try:
            default_or_descriptor = cls.__dict__[name]
        except KeyError:
            setattr(cls, name, TaskContextDescriptor())
        else:
            if not hasattr(default_or_descriptor, "__get__"):
                setattr(cls, name, TaskContextDescriptor(default_or_descriptor))
    return cls


def task_context(cls: type[T]) -> T:
    return task_context_class(cls)()
