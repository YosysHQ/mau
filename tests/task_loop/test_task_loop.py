from __future__ import annotations

import pytest
import yosys_mau.task_loop as tl


def test_minimal_sync():
    did_run = False

    def main():
        nonlocal did_run
        did_run = True

    tl.run_task_loop(main)

    assert did_run


def test_minimal_async():
    did_run = False

    async def main():
        nonlocal did_run
        did_run = True

    tl.run_task_loop(main)

    assert did_run


def test_no_task_loop():
    with pytest.raises(tl.TaskLoopError):
        tl.current_task()

    with pytest.raises(tl.TaskLoopError):
        tl.root_task()


def test_no_task_loop_running():
    def main():
        def cleanup():
            tl.root_task()

        tl.current_task().on_cleanup = cleanup

    tl.run_task_loop(main)


def test_dependencies():
    order: list[int] = []

    def main():
        def on_task1():
            order.append(1)

        def on_task2():
            order.append(2)

        def on_task3():
            assert task2.is_done
            order.append(3)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task1.depends_on(task2)

        task3.depends_on(task1)

    tl.run_task_loop(main)

    assert order == [2, 1, 3]


def test_dependencies_failure():
    order: list[int] = []

    def main():
        def on_task1():
            order.append(1)
            raise RuntimeError()

        def on_task2():
            order.append(2)

        def on_task3():
            order.append(3)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task1.depends_on(task2)

        task3.depends_on(task1)

    with pytest.raises(tl.TaskFailed):
        tl.run_task_loop(main)

    assert order == [2, 1]


def test_dependencies_handled_failure():
    order: list[int] = []

    handled: list[BaseException] = []

    def main():
        def on_task1():
            order.append(1)
            raise RuntimeError()

        def on_task2():
            order.append(2)

        def on_task3():
            assert task1.is_aborted
            order.append(3)

        task1 = tl.Task(on_run=on_task1)
        task2 = tl.Task(on_run=on_task2)
        task3 = tl.Task(on_run=on_task3)

        task1.depends_on(task2)

        def handle_failure(exc: BaseException):
            handled.append(exc)

        task3.set_error_handler(task1, handle_failure)

        tl.current_task().set_error_handler(task1, handle_failure)

        task3.depends_on(task1)

    tl.run_task_loop(main)

    assert order == [2, 1, 3]
    assert len(handled) == 2
