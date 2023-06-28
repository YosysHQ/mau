from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yosys_mau

from . import job_server as job
from ._task import Task, TaskEvent
from .context import InlineContextVar, TaskContextDescriptor, task_context

if os.name == "posix":
    pass


class Cwd(TaskContextDescriptor["os.PathLike[Any] | str"]):
    @property
    def default(self) -> os.PathLike[Any] | str:
        return os.getcwd()

    @default.setter
    def default(self, value: os.PathLike[Any] | str) -> None:
        os.chdir(value)

    @default.deleter
    def default(self) -> None:
        raise AttributeError("Cannot delete cwd")


@task_context
class ProcessContext:
    """Task context variables for `Process` tasks."""

    cwd = Cwd()
    """The working directory for newly spawned processes.

    Note that `Process`'s constructor takes a snapshot of this value, so parent updates between the
    creation of the `Process` task and the actual start of the process are ignored.

    Changing the default value outside of a task loop changes the working directory using
    `os.chdir`.
    """


@dataclass
class _MonitorPipe:
    read: int | None
    write: int | None

    def __init__(self):
        self.read, self.write = os.pipe()

    def inherit_read(self) -> None:
        if self.read is not None:
            os.set_inheritable(self.read, True)
        if self.write is not None:
            os.set_inheritable(self.write, False)

    def inherit_write(self) -> None:
        if self.read is not None:
            os.set_inheritable(self.read, False)
        if self.write is not None:
            os.set_inheritable(self.write, True)

    def close_read(self) -> None:
        if self.read is not None:
            os.close(self.read)
            self.read = None

    def close_write(self) -> None:
        if self.write is not None:
            os.close(self.write)

    def __del__(self) -> None:
        self.close_read()
        self.close_write()


def _setup_preexec_wrapper() -> list[str]:
    candidates: list[Path] = []
    bin_candidates: list[Path] = []

    for path in yosys_mau.__path__:
        path = Path(path)
        if path.is_dir():
            build_dir = path.parent.parent / "build" / "lib" / "yosys_mau"
            if build_dir.is_dir():
                bin_candidates.append(build_dir)
            candidates.append(path)

    # If we have a native build of the C version, prefer that, it has almost no overhead
    for path in [*bin_candidates, *candidates]:
        native = path / "helpers" / "preexec_wrapper"
        if native.is_file():
            return [str(native)]

    # Prefer to execute the wrapper as a script without loading site packages (-S) to slightly
    # reduce the startup time
    for path in candidates:
        script = path / "helpers" / "preexec_wrapper.py"
        if script.is_file():
            return [sys.executable, "-S", str(script)]

    # We can always execute the wrapper by using `-m`, but that's the slowest option
    return [sys.executable, "-m", "yosys_mau.helpers.preexec_wrapper"]


_preexec_wrapper_command = _setup_preexec_wrapper()


class Process(Task):
    """A task that runs and supervises a subprocess."""

    command: list[str]

    __proc: asyncio.subprocess.Process | None
    __monitor_pipe: _MonitorPipe | None

    def __init__(self, command: list[str], cwd: os.PathLike[Any] | str | None = None):
        super().__init__()
        self.use_lease = True
        self.name = command[0]
        self.command = command

        self.__monitor_pipe = None

        if cwd is not None:
            self.cwd = cwd
        else:
            # Take a snapshot at the time of task creation
            self.cwd = self.cwd
        self.__proc: asyncio.subprocess.Process | None = None

    cwd: InlineContextVar[os.PathLike[Any] | str] = InlineContextVar(ProcessContext, "cwd")
    """
    Inlined context variable for the working directory for newly spawned processes. Accessing this
    is the same as accessing `ProcessContext.cwd` in the context of this `Process` task.
    """

    async def on_run(self) -> None:
        # TODO check what to do on Windows
        subprocess_args = job.global_client().subprocess_args()
        wrapper = []

        if os.name == "posix":
            # On posix systems we use process groups to ensure that the spawned process cannot
            # accidentally leave any subprocesses behind even if we ourselves crash or are killed.

            # See preexec_wrapper.py for details.

            absolute_path = shutil.which(self.command[0])

            if absolute_path is None:
                raise FileNotFoundError(f"No such file or directory: {self.command[0]!r}")

            self.__monitor_pipe = _MonitorPipe()
            self.__monitor_pipe.inherit_read()

            wrapper = [
                *_preexec_wrapper_command,
                str(self.__monitor_pipe.read),
                absolute_path,
            ]

            subprocess_args["pass_fds"] = (
                *subprocess_args.get("pass_fds", ()),
                self.__monitor_pipe.read,
            )

        # TODO check what to do on Windows to ensure that we can terminate the whole process tree

        self.__proc = await asyncio.create_subprocess_exec(
            *wrapper,
            *self.command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=ProcessContext.cwd,
            **subprocess_args,
        )

        stdout = self.__proc.stdout
        stderr = self.__proc.stderr

        assert stdout is not None
        assert stderr is not None

        async def read_stdout():
            while line := await stdout.readline():
                StdoutEvent(line.decode()).emit()

        read_stdout_handle = self.background(read_stdout, wait=True)

        async def read_stderr():
            while line := await stderr.readline():
                StderrEvent(line.decode()).emit()

        read_stderr_handle = self.background(read_stderr, wait=True)

        returncode = await self.__proc.wait()

        if self.__monitor_pipe:
            self.__monitor_pipe = None

        self.__proc = None

        await read_stdout_handle
        await read_stderr_handle

        ExitEvent(returncode).emit()

        self.on_exit(returncode)

    def __cleanup(self) -> None:
        if self.__monitor_pipe:
            self.__monitor_pipe = None
        elif self.__proc is not None:
            self.__proc.terminate()

    def on_cancel(self) -> None:
        self.__cleanup()

    def on_cleanup(self):
        self.__cleanup()

    def on_exit(self, returncode: int) -> None:
        """Called when the process exits.

        By default, this raises a `subprocess.CalledProcessError` if the process exited with a
        non-zero return code. Override this to change this behavior.
        """
        if returncode:
            raise subprocess.CalledProcessError(returncode, self.command)


class ProcessEvent(TaskEvent):
    """Base class for events emitted by `Process` tasks."""

    pass


@dataclass
class OutputEvent(ProcessEvent):
    """Base class for events containing output of a `Process`."""

    output: str
    """The output of the process.

    By default this is a single line of output, including trailing newlines.
    """


class StdoutEvent(OutputEvent):
    """Emitted when a `Process` writes to stdout."""

    pass


class StderrEvent(OutputEvent):
    """Emitted when a `Process` writes to stderr."""

    pass


@dataclass
class ExitEvent(ProcessEvent):
    """Emitted when a `Process` exits."""

    returncode: int
    """The return code of the process."""
