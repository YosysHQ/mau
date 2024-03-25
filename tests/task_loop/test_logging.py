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
        tl.LogContext.dest_levels[None] = "warning"
        tl.LogContext.dest_levels[""] = "warning"
        tl.log("line 4")

        tl.LogContext.level = "error"
        tl.log_warning("line 5")
        tl.log_error("line 6", raise_error=False)

    tl.run_task_loop(main)

    trimmed_output = [int(x[-1]) for x in log_output.getvalue().splitlines()]
    assert trimmed_output == expected


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
