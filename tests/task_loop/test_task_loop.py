from __future__ import annotations

import asyncio
import re
import signal
import subprocess
import sys

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

    with pytest.raises(tl.TaskFailed, match=r"Task root failed") as exc_info:
        tl.run_task_loop(main)

    assert re.match(r"Top-level task .* failed", str(exc_info.value.__cause__))

    assert order == [2, 1]


def test_dependencies_cancellation():
    order: list[int] = []

    def main():
        async def on_task1():
            print("hah")
            await task4.finished
            print("huh")

        def on_task2():
            order.append(2)

        def on_task3():
            print("uhuh")
            order.append(3)

        async def on_task4():
            await task1.started
            order.append(1)
            task1.cancel()

        task1 = tl.Task(on_run=on_task1, name="task1")
        task2 = tl.Task(on_run=on_task2, name="task2")
        task3 = tl.Task(on_run=on_task3, name="task3")
        task4 = tl.Task(on_run=on_task4, name="task4")

        task1.depends_on(task2)

        task3.depends_on(task1)

        task1.handle_error(lambda exc: None)

    with pytest.raises(tl.TaskCancelled, match=r"Task root cancelled") as exc_info:
        tl.run_task_loop(main)

    assert re.match(r"Top-level task .* cancelled", str(exc_info.value.__cause__))

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


def test_sigint():
    process = subprocess.Popen(
        [sys.executable, __file__, inner_sigint.__name__],
        stdout=subprocess.PIPE,
    )

    assert process.stdout
    process.stdout.readline()

    process.send_signal(signal.SIGINT)

    ret = process.wait()
    process.stdout.close()

    assert ret == 4


def test_forced_sigint():
    process = subprocess.Popen(
        [sys.executable, __file__, inner_sigint.__name__],
        stdout=subprocess.PIPE,
    )

    assert process.stdout
    process.stdout.readline()

    process.send_signal(signal.SIGINT)
    process.send_signal(signal.SIGINT)

    ret = process.wait()
    process.stdout.close()

    assert ret == 4


def inner_sigint():
    retcode = [0]

    def main():
        async def on_task1():
            try:
                print("go", flush=True)
                await asyncio.sleep(60)
                retcode[0] |= 2
            finally:
                retcode[0] |= 4

        tl.Task(on_run=on_task1)

    try:
        tl.run_task_loop(main)
    finally:
        exit(retcode[0])


def inner_forced_sigint():
    retcode = [0]

    def main():
        tl.current_task().cancel = lambda: None

        async def on_task1():
            try:
                print("go", flush=True)
                await asyncio.sleep(60)
                retcode[0] |= 2
            finally:
                retcode[0] |= 4

        tl.Task(on_run=on_task1)

    try:
        tl.run_task_loop(main)
    finally:
        exit(retcode[0])


if __name__ == "__main__":
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
