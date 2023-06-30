from __future__ import annotations

import asyncio
import io

import pytest
import yosys_mau.task_loop as tl


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


def test_exception_logging():
    log_output = io.StringIO()

    def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        try:
            _unused = 1 / 0
        except BaseException as exc:
            tl.log_exception(exc, raise_error=False)

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "12:34:56 ERROR: division by zero",
    ]


def test_exception_logging_task_failure():
    log_output = io.StringIO()

    async def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        def failing_task():
            _unused = 1 / 0

        task = tl.Task(on_run=failing_task)

        def just_log(error: BaseException):
            tl.log_exception(error, raise_error=False)

        task.handle_error(just_log)

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "12:34:56 ERROR: division by zero",
    ]


def test_exception_logging_task_failure_dedup():
    log_output = io.StringIO()

    async def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        def failing_task():
            try:
                _unused = 1 / 0
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
        "12:34:56 ERROR: division by zero",
    ]


def test_exception_logging_task_failure_dedup_2():
    log_output = io.StringIO()

    async def main():
        tl.LogContext.time_format = fixed_time
        tl.logging.start_logging(file=log_output)

        def failing_task():
            try:
                _unused = 1 / 0
            except BaseException as exc:
                tl.log_exception(exc)

        task = tl.Task(on_run=failing_task)

        def just_log(error: BaseException):
            tl.log_exception(error, raise_error=False)

        task.handle_error(just_log)

    tl.run_task_loop(main)

    assert log_output.getvalue().splitlines() == [
        "12:34:56 ERROR: division by zero",
    ]
