from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass

import pytest
import yosys_mau.task_loop as tl


class CustomException(Exception):
    pass


def raise_exception():
    raise CustomException("error message")


def fixed_time(t: float) -> str:
    return "12:34:56"


def test_simple_logging():
    log_output = io.StringIO()

    def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)
        tl.log("Hello, world!")

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == ["12:34:56 Hello, world!"]


def test_log_info():
    log_output = io.StringIO()

    def main():
        tl.LogContext.time_format = fixed_time
        tl.LogContext.app_name = "MAU"
        tl.logging.start_logging(file=log_output)

        tl.log("line 1")
        tl.LogContext.work_dir = "work_dir"
        tl.log("line 2")
        tl.LogContext.scope = "scope"
        tl.log("line 3")
        del tl.LogContext.work_dir
        tl.log("line 4")

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "MAU 12:34:56 line 1",
        "MAU 12:34:56 [work_dir] line 2",
        "MAU 12:34:56 [work_dir] scope: line 3",
        "MAU 12:34:56 scope: line 4",
    ]


def test_log_info_child_tasks():
    log_output = io.StringIO()

    async def main():
        tl.LogContext.time_format = fixed_time
        tl.LogContext.app_name = "MAU"
        tl.logging.start_logging(file=log_output)

        sync_event = asyncio.Event()

        async def run_task1():
            tl.LogContext.work_dir = "work_dir"

            task2 = tl.Task(on_run=run_task2)
            tl.log("line 1 from task 1")

            await task2.started

            tl.log("line 2 from task 1")

            sync_event.set()

            await task2.finished

            tl.log("line 3 from task 1")

        async def run_task2():
            tl.LogContext.scope = "scope"
            tl.log("line 1 from task 2")

            await sync_event.wait()
            tl.log("line 2 from task 2")

        task1 = tl.Task(on_run=run_task1)

        tl.log("line 1 from root task")

        await task1.finished

        tl.log("line 2 from root task")

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "MAU 12:34:56 line 1 from root task",
        "MAU 12:34:56 [work_dir] line 1 from task 1",
        "MAU 12:34:56 [work_dir] scope: line 1 from task 2",
        "MAU 12:34:56 [work_dir] line 2 from task 1",
        "MAU 12:34:56 [work_dir] scope: line 2 from task 2",
        "MAU 12:34:56 [work_dir] line 3 from task 1",
        "MAU 12:34:56 line 2 from root task",
    ]


def test_log_levels():
    log_output = io.StringIO()

    def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        tl.log("info")
        tl.log_debug("debug")
        tl.log_warning("warning")
        tl.log_error("error (not raised)", raise_error=False)
        tl.log_error("error (raised)", raise_error=True)
        tl.log("not reached")

    with pytest.raises(tl.TaskFailed) as exc_info:
        tl.run_task_loop(main)

    assert isinstance(exc_info.value.__cause__, tl.logging.LoggedError)

    assert log_output.getvalue().splitlines() == [
        "12:34:56 info",
        "12:34:56 WARNING: warning",
        "12:34:56 ERROR: error (not raised)",
        "12:34:56 ERROR: error (raised)",
    ]


@pytest.mark.parametrize(
    "label,expected",
    [
        ("default", [2, 3, 4, 6]),
        ("debug", [1, 2, 3, 4, 5, 6]),
        ("info", [2, 4, 5, 6]),
        ("warning", [5, 6]),
        ("error", [6]),
        ("varied", [1, 2, 4, 6]),
    ],
)
def test_log_destinations(label: str, expected: list[str]):
    log_output = io.StringIO()

    def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output, destination_label=label)

        # tl.LogContext.level = "info" # implied
        tl.LogContext.dest_levels["info"] = "info"
        tl.LogContext.dest_levels["debug"] = "debug"
        tl.LogContext.dest_levels["warning"] = "warning"
        tl.LogContext.dest_levels["error"] = "error"

        tl.LogContext.dest_levels["varied"] = "debug"
        tl.log_debug("line 1")
        tl.log("line 2")

        tl.LogContext.level = "debug"
        tl.LogContext.dest_levels["varied"] = "warning"
        tl.log_debug("line 3")

        del tl.LogContext.dest_levels["varied"]
        tl.LogContext.dest_levels[None] = "warning"  # type:ignore
        tl.LogContext.dest_levels[""] = "warning"
        tl.log("line 4")

        tl.LogContext.level = "error"
        tl.log_warning("line 5")
        tl.log_error("line 6", raise_error=False)

    tl.run_task_loop(main)

    trimmed_output = [int(x[-1]) for x in log_output.getvalue().splitlines()]
    assert trimmed_output == expected


@pytest.mark.parametrize("task", ["root", "task1", "task2"])
@pytest.mark.parametrize("label", ["debug", "info", "warning", "mixed1", "mixed2"])
def test_nested_destinations(task: str, label: str):
    log_output = io.StringIO()

    async def main():
        tl.LogContext.time_format = fixed_time
        tl.LogContext.scope = "?root?"
        if task == "root":
            tl.logging.start_logging(file=log_output, destination_label=label)
            tl.LogContext.dest_levels["mixed1"] = "warning"

        tl.LogContext.dest_levels["debug"] = "debug"
        tl.LogContext.dest_levels["info"] = "info"
        tl.LogContext.dest_levels["warning"] = "warning"
        tl.LogContext.dest_levels["error"] = "error"
        tl.LogContext.dest_levels["source"] = "warning"

        tl.log("line 0")
        sync_event = asyncio.Event()

        async def run_task1():
            tl.LogContext.scope = "?root?task1?"
            if task == "task1":
                tl.logging.start_logging(file=log_output, destination_label=label)
                tl.LogContext.dest_levels["mixed1"] = "info"

            tl.LogContext.dest_levels["mixed2"] = "debug" if task == "root" else "info"

            task2 = tl.Task(on_run=run_task2)
            tl.log("line 2")

            await task2.started

            tl.log_debug("line 4")

            sync_event.set()

            await task2.finished

            tl.log("line 6")

        async def run_task2():
            tl.LogContext.scope = "?root?task1?task2?"
            if task == "task2":
                tl.logging.start_logging(file=log_output, destination_label=label)
                tl.LogContext.dest_levels["mixed1"] = "debug"

            tl.LogContext.dest_levels["mixed2"] = "debug" if task == "task1" else "error"

            tl.log_debug("line 3")

            await sync_event.wait()
            tl.log_warning("line 5")

        task1 = tl.Task(on_run=run_task1)

        tl.log("line 1")

        await task1.finished

        tl.log("line 7")

    tl.run_task_loop(main)

    reference_list = [
        "12:34:56 ?root?: line 0",
        "12:34:56 ?root?: line 1",
        "12:34:56 ?root?task1?: line 2",
        "12:34:56 ?root?task1?task2?: DEBUG: line 3",
        "12:34:56 ?root?task1?: DEBUG: line 4",
        "12:34:56 ?root?task1?task2?: WARNING: line 5",
        "12:34:56 ?root?task1?: line 6",
        "12:34:56 ?root?: line 7",
    ]

    label_map: dict[str, list[int]] = {
        "debug": [0, 1, 2, 3, 4, 5, 6, 7],
        "info": [0, 1, 2, 5, 6, 7],
        "warning": [5],
    }

    if label in label_map:
        filtered_list = [x for i, x in enumerate(reference_list) if i in label_map[label]]
        expected = [x for x in filtered_list if task in x.split("?")]
    else:
        # potentially unintuitive, but destination levels come from the emitter not the logger
        if label == "mixed1":
            task_map: dict[str, list[int]] = {
                "root": [5],
                "task1": [2, 5, 6],
                "task2": [3, 5],
            }
        elif label == "mixed2":
            task_map: dict[str, list[int]] = {
                "root": [0, 1, 2, 4, 6, 7],
                "task1": [2, 3, 5, 6],
                "task2": [],
            }
        else:
            assert False, f"unknown label {label}"
        expected = [x for i, x in enumerate(reference_list) if i in task_map[task]]

    print(log_output.getvalue())
    assert log_output.getvalue().splitlines() == expected


def test_exception_logging():
    log_output = io.StringIO()

    def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        try:
            raise_exception()
        except BaseException as exc:
            tl.log_exception(exc, raise_error=False)

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "12:34:56 ERROR: error message",
    ]


def test_exception_logging_task_failure():
    log_output = io.StringIO()

    async def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        def failing_task():
            raise_exception()

        task = tl.Task(on_run=failing_task)

        def just_log(error: BaseException):
            tl.log_exception(error, raise_error=False)

        task.handle_error(just_log)

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "12:34:56 ERROR: error message",
    ]


def test_exception_logging_task_failure_dedup():
    log_output = io.StringIO()

    async def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        def failing_task():
            try:
                raise_exception()
            except BaseException as exc:
                tl.log_exception(exc, raise_error=False)
                tl.log_exception(exc, raise_error=False)
                raise

        task = tl.Task(on_run=failing_task)

        def just_log(error: BaseException):
            tl.log_exception(error, raise_error=False)

        task.handle_error(just_log)

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "12:34:56 ERROR: error message",
    ]


def test_exception_logging_task_failure_dedup_2():
    log_output = io.StringIO()

    async def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        def failing_task():
            try:
                raise_exception()
            except BaseException as exc:
                tl.log_exception(exc)

        task = tl.Task(on_run=failing_task)

        def just_log(error: BaseException):
            tl.log_exception(error, raise_error=False)

        task.handle_error(just_log)

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "12:34:56 ERROR: error message",
    ]


def test_debug_event_log():
    log_output = io.StringIO()

    @dataclass
    class ExampleEvent(tl.DebugEvent):
        value: int

    ExampleEvent.__qualname__ = "ExampleEvent"

    def main():
        tl.logging.start_debug_event_logging(file=log_output)

        tl.Task(on_run=lambda: ExampleEvent(1).emit(), name="task")

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "task: None -> preparing",
        "task: preparing -> pending",
        "task: pending -> running",
        "task: ExampleEvent(value=1)",
        "task: running -> waiting",
        "task: waiting -> done",
    ]
