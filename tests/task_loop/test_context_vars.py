from __future__ import annotations

import pytest
import yosys_mau.task_loop as tl
from yosys_mau.task_loop.context import TaskContextDict


def test_local_override_stays_local():
    order: list[int] = []

    @tl.task_context
    class SomeContext:
        some_var: int = 0

    def main():
        def on_task1():
            SomeContext.some_var = 1
            order.append(SomeContext.some_var)

        def on_task2():
            order.append(SomeContext.some_var)
            SomeContext.some_var = 2

        def on_task3():
            order.append(SomeContext.some_var)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task2.depends_on(task1)
        task3.depends_on(task2)

    tl.run_task_loop(main)

    assert order == [1, 0, 0]


def test_global_override():
    order: list[int] = []

    @tl.task_context
    class SomeContext:
        some_var: int = 0

    def main():
        def on_task1():
            with tl.root_task().as_current_task():
                SomeContext.some_var = 1
            order.append(SomeContext.some_var)

        def on_task2():
            order.append(SomeContext.some_var)
            with tl.root_task().as_current_task():
                SomeContext.some_var = 2

        def on_task3():
            order.append(SomeContext.some_var)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task2.depends_on(task1)
        task3.depends_on(task2)

    tl.run_task_loop(main)

    assert order == [1, 1, 2]


def test_global_override_context_proxy():
    order: list[int] = []

    @tl.task_context
    class SomeContext:
        some_var: int = 0

    def main():
        def on_task1():
            tl.root_task()[SomeContext].some_var = 1
            order.append(SomeContext.some_var)
            del tl.root_task()[SomeContext].some_var

        def on_task2():
            order.append(SomeContext.some_var)
            SomeContext.some_var = 3
            assert tl.root_task()[SomeContext].some_var == 0
            tl.root_task()[SomeContext].some_var = 2

        def on_task3():
            order.append(SomeContext.some_var)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task2.depends_on(task1)
        task3.depends_on(task2)

    tl.run_task_loop(main)

    assert order == [1, 0, 2]


def test_local_override_has_priority_over_global_override():
    order: list[int] = []

    @tl.task_context
    class SomeContext:
        some_var: int = 0

    def main():
        def on_task1():
            with tl.root_task().as_current_task():
                SomeContext.some_var = 1
            order.append(SomeContext.some_var)

        def on_task2():
            order.append(SomeContext.some_var)
            with tl.root_task().as_current_task():
                SomeContext.some_var = 2

        def on_task3():
            order.append(SomeContext.some_var)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        with task3.as_current_task():
            SomeContext.some_var = 3

        task2.depends_on(task1)
        task3.depends_on(task2)

    tl.run_task_loop(main)

    assert order == [1, 1, 3]


def test_no_default_value():
    order: list[int] = []

    @tl.task_context
    class SomeContext:
        some_var: int

    def main():
        def on_task1():
            SomeContext.some_var = 1
            order.append(SomeContext.some_var)

        def on_task2():
            with pytest.raises(AttributeError):
                order.append(SomeContext.some_var)

            with tl.root_task().as_current_task():
                SomeContext.some_var = 2

        def on_task3():
            order.append(SomeContext.some_var)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task2.depends_on(task1)
        task3.depends_on(task2)

    tl.run_task_loop(main)

    assert order == [1, 2]


def test_override_default():
    order: list[int] = []

    @tl.task_context
    class SomeContext:
        some_var: int = 0

    def main():
        def on_task1():
            SomeContext.some_var = 1
            order.append(SomeContext.some_var)

        def on_task2():
            order.append(SomeContext.some_var)
            SomeContext.some_var = 2

        def on_task3():
            order.append(SomeContext.some_var)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task2.depends_on(task1)
        task3.depends_on(task2)

    SomeContext.some_var = 3

    tl.run_task_loop(main)

    assert order == [1, 3, 3]


def test_TaskContextDict_with_default():
    @tl.task_context
    class SomeContext:
        some_var: TaskContextDict[str, str] = TaskContextDict()

    def main():
        # iterate default values
        for _, _ in SomeContext.some_var.items():
            pass

        # iterate non-default values
        SomeContext.some_var["a"] = "b"
        for _, _ in SomeContext.some_var.items():
            pass

        assert SomeContext.some_var["a"] == "b"

    tl.run_task_loop(main)


def test_override_TaskContextDict():
    order: list[dict[str, str]] = []

    @tl.task_context
    class SomeContext:
        some_var: TaskContextDict[str, str] = TaskContextDict()

    def main():
        def on_task1():
            SomeContext.some_var["a"] = "b"
            order.append(SomeContext.some_var.as_dict())

        def on_task2():
            order.append(SomeContext.some_var.as_dict())

            with tl.root_task().as_current_task():
                SomeContext.some_var["b"] = "d"

        def on_task3():
            order.append(SomeContext.some_var.as_dict())

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task2.depends_on(task1)
        task3.depends_on(task2)

    SomeContext.some_var["b"] = "c"

    tl.run_task_loop(main)

    assert order == [
        {"a": "b", "b": "c"},
        {"b": "c"},
        {"b": "d"},
    ]


def test_child_TaskContextDict():
    order: list[dict[str, str]] = []

    @tl.task_context
    class SomeContext:
        some_var: TaskContextDict[str, str] = TaskContextDict()

    def main():
        async def on_task1():
            SomeContext.some_var["a"] = "b"
            order.append(SomeContext.some_var.as_dict())
            t2 = tl.Task(on_run=on_task2)
            await t2.finished
            order.append(SomeContext.some_var.as_dict())

        def on_task2():
            SomeContext.some_var["b"] = "d"
            order.append(SomeContext.some_var.as_dict())

        tl.Task(on_run=on_task1)

    SomeContext.some_var["b"] = "c"

    tl.run_task_loop(main)

    assert order == [
        {"a": "b", "b": "c"},
        {"a": "b", "b": "d"},
        {"a": "b", "b": "c"},
    ]


# TODO tests
