from __future__ import annotations

import abc
from typing import Any, Generic, TypeVar
from weakref import WeakKeyDictionary

from ._task import Task, TaskLoopError, current_task

T = TypeVar("T")

MISSING = object()


class ContextData:
    instance: ContextData

    data: WeakKeyDictionary[Task, dict[tuple[TaskContextMeta, str], Any]]

    def __init__(self) -> None:
        self.data = WeakKeyDictionary()

    def _task_data(self, task: Task) -> Any:
        try:
            data = self.data[task]
        except KeyError:
            data = self.data[task] = {}
        return data

    def get(self, task: Task, context: TaskContextMeta, attr: str, default: Any = MISSING) -> Any:
        cursor: Task | None = task
        while cursor:
            try:
                return self._task_data(cursor)[context, attr]
            except KeyError:
                cursor = cursor.parent

        if default is not MISSING:
            return default

        raise AttributeError(f"Context attribute {attr!r} not set for {task} or any parent")

    def set(self, task: Task, context: TaskContextMeta, attr: str, value: Any) -> None:
        self._task_data(task)[context, attr] = value

    def delete(self, task: Task, context: TaskContextMeta, attr: str) -> None:
        try:
            self._task_data(task).pop((context, attr))
        except KeyError:
            raise AttributeError(f"Context attribute {attr!r} not set for task {task}") from None


ContextData.instance = ContextData()


def current_task_or_none() -> Task | None:
    try:
        return current_task()
    except TaskLoopError:
        return None


class TaskContextMeta(type):
    def __getattribute__(self, name: str) -> Any:
        plain = object.__getattribute__(self, "__dict__").get(name, MISSING)
        plain_type = type(plain)
        if hasattr(plain_type, "__get__") or hasattr(plain_type, "__set__"):
            if isinstance(plain, TaskContextDescriptor):
                return plain.__getctxattr__(current_task_or_none(), self)
            return super().__getattribute__(name)
        try:
            task = current_task()
        except TaskLoopError:
            if plain is not MISSING:
                return plain
        else:
            return ContextData.instance.get(task, self, name, plain)
        raise AttributeError(f"Context attribute {name!r} not set")

    def __setattr__(self, name: str, value: Any) -> None:
        plain = object.__getattribute__(self, "__dict__").get(name, MISSING)
        plain_type = type(plain)
        if hasattr(plain_type, "__get__") or hasattr(plain_type, "__set__"):
            if isinstance(plain, TaskContextDescriptor):
                plain.__setctxattr__(current_task_or_none(), self, value)
                return
            super().__setattr__(name, value)
            return
        try:
            task = current_task()
        except TaskLoopError:
            super().__setattr__(name, value)
            return
        else:
            ContextData.instance.set(task, self, name, value)

    def __delattr__(self, name: str) -> None:
        plain = object.__getattribute__(self, "__dict__").get(name, MISSING)
        plain_type = type(plain)
        if hasattr(plain_type, "__get__") or hasattr(plain_type, "__set__"):
            if isinstance(plain, TaskContextDescriptor):
                plain.__delctxattr__(current_task_or_none(), self)
                return
            super().__delattr__(name)
            return
        try:
            task = current_task()
        except TaskLoopError:
            super().__delattr__(name)
            return
        else:
            ContextData.instance.delete(task, self, name)


class TaskContext(metaclass=TaskContextMeta):
    def __new__(cls):
        raise TypeError("TaskContext is not instantiable")


class TaskContextDescriptor(abc.ABC, Generic[T]):
    def __get__(self, instance: Any, owner: type) -> T:
        if instance is not None:
            raise AttributeError("TaskContextDescriptor is not accessible on instances")
        return self.__getctxattr__(current_task_or_none(), owner)

    @abc.abstractmethod
    def __getctxattr__(self, task: Task | None, context_type: type) -> Any:
        ...

    def __setctxattr__(self, task: Task | None, context_type: type, value: Any) -> None:
        raise AttributeError("TaskContextDescriptor is read-only")

    def __delctxattr__(self, task: Task | None, context_type: type) -> None:
        raise AttributeError("TaskContextDescriptor is not deletable")
