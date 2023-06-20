from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from . import job_server as job
from . import preexec_wrapper
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
    cwd = Cwd()


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


_preexec_wrapper_exe = [os.path.join(os.path.dirname(__file__), "preexec_wrapper")]
if not os.path.exists(_preexec_wrapper_exe[0]):
    _preexec_wrapper_exe = [sys.executable, preexec_wrapper.__file__]


class ProcessTask(Task):
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
                *_preexec_wrapper_exe,
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

        self.background(read_stdout, wait=True)

        async def read_stderr():
            while line := await stderr.readline():
                StderrEvent(line.decode()).emit()

        self.background(read_stderr, wait=True)

        returncode = await self.__proc.wait()

        if self.__monitor_pipe:
            self.__monitor_pipe = None

        self.__proc = None

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
        if returncode:
            raise subprocess.CalledProcessError(returncode, self.command)


class ProcessEvent(TaskEvent):
    pass


@dataclass
class OutputEvent(ProcessEvent):
    output: str


class StdoutEvent(OutputEvent):
    pass


class StderrEvent(OutputEvent):
    pass


@dataclass
class ExitEvent(ProcessEvent):
    returncode: int
