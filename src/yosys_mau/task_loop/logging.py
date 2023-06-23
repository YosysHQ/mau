from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import IO, Any, Callable, Literal

import click

from ._task import (
    TaskEvent,
    TaskFailed,
    TaskLoopError,
    current_task,
    current_task_or_none,
    root_task,
)
from .context import task_context

Level = Literal["debug", "info", "warning", "error"]


@dataclass
class LogEvent(TaskEvent):
    msg: str
    level: Level

    workdir: str | None = field(init=False)
    scope: str | None = field(init=False)

    time: float = field(init=False)

    def __post_init__(self):
        super().__post_init__()
        self.time = time.time()
        self.workdir = LogContext.workdir
        self.scope = LogContext.scope


class LoggedError(Exception):
    event: LogEvent

    def __init__(self, event: LogEvent):
        self.event = event


@dataclass
class Backtrace(TaskEvent):
    exception: BaseException

    def __repr__(self):
        backtrace = "".join(
            traceback.format_exception(None, self.exception, self.exception.__traceback__)
        )

        return f"{self.source}: exception:\n{click.style(backtrace, fg='red')}"


def default_formatter(event: LogEvent):
    tm = time.localtime(event.time)
    time_str = f"{tm.tm_hour:02d}:{tm.tm_min:02d}:{tm.tm_sec:02d}"
    parts: list[str] = []
    if LogContext.app_name:
        parts.append(f"{click.style(LogContext.app_name, fg='blue')} ")
    parts.append(f"{click.style(time_str, fg='green')} ")
    if event.workdir:
        parts.append(f"[{click.style(event.workdir, fg='blue')}] ")
    if event.scope:
        parts.append(f"{click.style(event.scope, fg='magenta')}: ")

    prefix = "".join(parts)

    formatted_lines: list[str] = []

    for line in event.msg.splitlines():
        if event.level == "debug":
            formatted_lines.append(prefix + click.style(f"DEBUG: {line}", fg="cyan"))
        elif event.level == "warning":
            formatted_lines.append(prefix + click.style(f"WARNING: {line}", fg="yellow"))
        elif event.level == "error":
            formatted_lines.append(prefix + click.style(f"ERROR: {line}", fg="red"))
        else:
            formatted_lines.append(prefix + event.msg)
    return "\n".join(formatted_lines)


@task_context
class LogContext:
    app_name: str | None = None
    log_format: Callable[[LogEvent], str] = default_formatter
    workdir: str | None = None  # TODO eventually move this to a workdir handling module
    scope: str | None = None
    quiet: bool = False


def log(*args: Any, level: Level = "info", cls: type[LogEvent] = LogEvent) -> LogEvent:
    msg = " ".join(str(arg) for arg in args)

    if LogContext.quiet and level == "info":
        level = "debug"

    event = cls(msg=msg, level=level)

    try:
        event.emit()
    except TaskLoopError:
        for file, err, color in _root_log_files:
            formatted = LogContext.log_format(event)
            click.echo(formatted, file=file, err=err, color=color)

    return event


def log_warning(*args: Any, cls: type[LogEvent] = LogEvent) -> LogEvent:
    return log(*args, level="warning", cls=cls)


def log_error(*args: Any, cls: type[LogEvent] = LogEvent, raise_error: bool = True) -> LogEvent:
    event = log(*args, level="error", cls=cls)

    if raise_error:
        raise LoggedError(event)

    return event


def log_exception(exception: BaseException, raise_error: bool = True) -> LoggedError:
    current = exception
    source = current_task_or_none()

    while isinstance(current, TaskFailed) and current.__cause__ is not None:
        source = current.task
        current = current.__cause__

    if isinstance(current, LoggedError):
        return current

    current_msg = str(current)

    if current.__traceback__:
        if source:
            with source.as_current_task():
                Backtrace(current).emit()

    if source:
        with source.as_current_task():
            err = LoggedError(log_error(current_msg, raise_error=False))
    else:
        err = LoggedError(log_error(current_msg, raise_error=False))

    err.__cause__ = exception
    if raise_error:
        raise err
    return err


_root_log_files: list[tuple[IO[Any] | None, bool, bool | None]] = []


def start_logging(
    file: IO[Any] | None = None, err: bool = False, color: bool | None = None
) -> None:
    def log_handler(event: LogEvent):
        formatted = LogContext.log_format(event)
        click.echo(formatted, file=file, err=err, color=color)

    current_task().sync_handle_events(LogEvent, log_handler)

    _root_log_files.append((file, err, color))


def start_debug_event_logging(
    file: IO[Any] | None = None,
    err: bool = False,
    color: bool | None = None,
    include_log: bool = False,
):
    def debug_event_log_handler(event: TaskEvent):
        if include_log or not isinstance(event, LogEvent):
            click.secho(repr(event), file=file, err=err, color=color, fg="cyan")

    current_task().sync_handle_events(TaskEvent, debug_event_log_handler)


def root_error_handler(error: BaseException):
    raise log_exception(error)


def install_root_error_handler():
    task = current_task()
    assert task is root_task()
    task.set_error_handler(None, root_error_handler)
