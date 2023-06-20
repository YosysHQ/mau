from __future__ import annotations

import asyncio
import os
import tempfile
import time
from typing import AsyncIterable

import pytest
import yosys_mau.task_loop as tl


def test_exit_event_success():
    did_run = False

    def main():
        true_proc = tl.ProcessTask(["true"])

        def on_exit_event(event: tl.process.ExitEvent):
            nonlocal did_run
            assert event.returncode == 0
            did_run = True

        true_proc.events(tl.process.ExitEvent).handle(on_exit_event)

    tl.TaskLoop(main)

    assert did_run


def test_exit_event_nonzero_returncode():
    did_run = False

    def main():
        false_proc = tl.ProcessTask(["false"])

        def on_exit_event(event: tl.process.ExitEvent):
            nonlocal did_run
            assert event.returncode != 0
            did_run = True

        # override the default returncode exit handler
        def on_exit_override(returncode: int):
            assert returncode != 0

        false_proc.on_exit = on_exit_override

        false_proc.events(tl.process.ExitEvent).handle(on_exit_event)

    tl.TaskLoop(main)

    assert did_run


def test_exit_event_failure():
    def main():
        tl.ProcessTask(["false"])

    with pytest.raises(tl.TaskFailed):
        tl.TaskLoop(main)


def test_output_events():
    output_lines: list[str] = []

    def main():
        proc = tl.ProcessTask(["echo", "-e", r"hello world\na second line"])

        async def handle_output(lines: AsyncIterable[tl.process.OutputEvent]):
            async for line_event in lines:
                output_lines.append(line_event.output)

        proc.events(tl.process.OutputEvent).process(handle_output)

    tl.TaskLoop(main)

    assert output_lines == ["hello world\n", "a second line\n"]


def test_termination():
    async def main():
        proc = tl.ProcessTask(["sleep", "10"])

        await asyncio.sleep(0.1)

        tl.current_task().set_error_handler(proc, lambda _: None)
        proc.cancel()

    before = time.time()
    tl.TaskLoop(main)
    after = time.time()

    assert after - before < 8


def test_cwd():
    output_lines: list[str] = []

    cwd = os.getcwd()

    assert tl.process.ProcessContext.cwd == cwd

    temp_dir = tempfile.TemporaryDirectory()
    temp_dir2 = tempfile.TemporaryDirectory()

    async def main():
        proc = tl.ProcessTask(["pwd"])

        async def handle_output(lines: AsyncIterable[tl.process.OutputEvent]):
            async for line_event in lines:
                output_lines.append(line_event.output)

        proc.events(tl.process.OutputEvent).process(handle_output)

        await proc.finished

        proc = tl.ProcessTask(["pwd"], cwd=temp_dir.name)
        proc.events(tl.process.OutputEvent).process(handle_output)

        await proc.finished

        tl.process.ProcessContext.cwd = temp_dir2.name

        proc = tl.ProcessTask(["pwd"])
        proc.events(tl.process.OutputEvent).process(handle_output)

        await proc.finished

    tl.TaskLoop(main)

    assert "".join(output_lines) == f"{cwd}\n{temp_dir.name}\n{temp_dir2.name}\n"

    temp_dir.cleanup()
    temp_dir2.cleanup()
