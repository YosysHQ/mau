from __future__ import annotations

import pytest
import yosys_mau.task_loop as tl


def test_local_override_stays_local():
    order: list[int] = []

    class SomeContext(tl.TaskContext):
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

    tl.TaskLoop(main)

    assert order == [1, 0, 0]


def test_global_override():
    order: list[int] = []

    class SomeContext(tl.TaskContext):
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

    tl.TaskLoop(main)

    assert order == [1, 1, 2]


def test_local_override_has_priority_over_global_override():
    order: list[int] = []

    class SomeContext(tl.TaskContext):
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

    tl.TaskLoop(main)

    assert order == [1, 1, 3]


def test_no_default_value():
    order: list[int] = []

    class SomeContext(tl.TaskContext):
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

    tl.TaskLoop(main)

    assert order == [1, 2]


def test_override_default():
    order: list[int] = []

    class SomeContext(tl.TaskContext):
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

    tl.TaskLoop(main)

    assert order == [1, 3, 3]


# TODO tests
