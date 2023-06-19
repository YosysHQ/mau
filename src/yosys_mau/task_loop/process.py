from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from . import job_server as job
from ._task import Task, TaskEvent


class ProcessTask(Task):
    command: list[str]
    cwd: os.PathLike[Any] | None

    __proc: asyncio.subprocess.Process | None
    __monitor_pipe: tuple[int, int] | None

    def __init__(
        self, command: list[str], cwd: os.PathLike[Any] | None = None, *, lease: bool = True
    ):
        super().__init__(lease=lease)
        self.name = command[0]
        self.command = command
        self.cwd = cwd
        self.__proc: asyncio.subprocess.Process | None = None

    async def on_run(self) -> None:
        # TODO check what to do on Windows
        subprocess_args = job.global_client().subprocess_args()
        wrapper = []

        if os.name == "posix":
            # On posix systems we use process groups to ensure that the spawned process cannot
            # accidentally leave any subprocesses behind even if we ourselves crash or are killed.

            # See preexec_wrapper.py for details.

            import fcntl
            import shutil

            absolute_path = shutil.which(self.command[0])

            if absolute_path is None:
                raise FileNotFoundError(f"No such file or directory: {self.command[0]!r}")

            self.__monitor_pipe = os.pipe()
            os.set_inheritable(self.__monitor_pipe[0], True)
            fcntl.fcntl(self.__monitor_pipe[1], fcntl.F_SETFD, fcntl.FD_CLOEXEC)

            wrapper = [
                sys.executable,
                "-m",
                f"{__package__}.preexec_wrapper",
                str(self.__monitor_pipe[0]),
                absolute_path,
            ]

            subprocess_args.setdefault("pass_fds", []).append(self.__monitor_pipe[0])

            repr_dict = dict(subprocess_args)
            repr_dict.pop("env", None)

        # TODO check what to do on Windows to ensure that we can terminate the whole process tree

        self.__proc = await asyncio.create_subprocess_exec(
            *wrapper,
            *self.command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
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
        self.__proc = None
        self.__cleanup()

        ExitEvent(returncode).emit()

        self.on_exit(returncode)

    def __cleanup(self) -> None:
        if self.__monitor_pipe:
            if self.__monitor_pipe:
                for fd in self.__monitor_pipe:
                    os.close(fd)
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
