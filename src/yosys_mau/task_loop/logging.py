from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass, field
from typing import IO, Any, Callable, Literal, NoReturn, overload

import click

from ._task import (
    TaskEvent,
    TaskFailed,
    TaskLoopError,
    TaskLoopInterrupted,
    current_task,
    current_task_or_none,
    root_task,
)
from .context import (
    TaskContextDict,
    task_context,
)

Level = Literal["debug", "info", "warning", "error"]

levels = ["debug", "info", "warning", "error"]

_level_order = {level: i for i, level in enumerate(levels)}


@dataclass
class LogEvent(TaskEvent):
    msg: str
    level: Level

    time: float = field(init=False)

    def __post_init__(self):
        super().__post_init__()
        self.time = time.time()


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


def default_time_formatter(t: float) -> str:
    tm = time.localtime(t)
    return f"{tm.tm_hour:02d}:{tm.tm_min:02d}:{tm.tm_sec:02d}"


def default_formatter(event: LogEvent):
    try:
        context = event.source[LogContext]
    except TaskLoopError:
        context = LogContext

    time_str = LogContext.time_format(event.time)
    parts: list[str] = []
    if context.app_name:
        parts.append(f"{click.style(context.app_name, fg='blue')} ")
    if time_str:
        parts.append(f"{click.style(time_str, fg='green')} ")
    if context.work_dir:
        parts.append(f"[{click.style(context.work_dir, fg='blue')}] ")
    if context.scope:
        parts.append(f"{click.style(context.scope, fg='magenta')}: ")

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
            formatted_lines.append(prefix + line)
    return "\n".join(formatted_lines)


@task_context
class LogContext:
    """Context variables to customize logging behavior.

    When the default formatter formats a log message, the values of the emitting task are used. This
    allows setting different values of `work_dir`, `scope`, etc. for different tasks.
    """

    app_name: str | None = None
    """The default formatter will prefix all log messages with this if set."""

    work_dir: str | None = None  # TODO eventually move this to a workdir handling module
    """Working directory to display as part of log messages."""

    scope: str | None = None
    """Scope prefix to display as part of log messages."""

    quiet: bool = False
    """Downgrade all info level messages to debug level messages.

    When set, the downgrading happens before the `LogEvent` is emitted.
    """

    level: Level = "info"
    """The minimum log level to display/log.
    
    Can be overridden for named destinations with `destination_levels`.

    This does not stop `LogEvent` of smaller levels to be emitted. It is only used to filter which
    messages to actually print/log. Hence, it does not affect any user installed `LogEvent`
    handlers."""

    log_format: Callable[[LogEvent], str] = default_formatter
    """The formatter used to format log messages.

    Note that unlike the preceding context variables, this is looked up by the log writing task, not
    the emitting task.
    """

    time_format: Callable[[float], str] = default_time_formatter
    """The formatter used by the default formatter to format the time of log messages.

    This is provided so it can be overridden with a fixed timestamp when running tests that check
    the log output.

    Like `log_format` this is looked up by the log writing task, not the emitting task.
    """

    destination_levels: TaskContextDict[str, Level] = TaskContextDict()
    """The minimum log level to display/log for named destinations.

    Like `log_format` this is looked up by the log writing task, not the emitting task.  If the
    current destination has no key:value pair in this dictionary, the `level` will be looked up by
    the task which emit the log.
    """


def log(*args: Any, level: Level = "info", cls: type[LogEvent] = LogEvent) -> LogEvent:
    """Produce log output.

    This is done by emitting a `LogEvent`.

    When the task loop is not running anymore or there is no current task, it will directly write to
    the log files registered with the root task.

    :param args: The message to log, will be converted to strings and joined with spaces.
    :param level: The log level, one of "debug", "info", "warning" or "error". Defaults to "info".
        To log at a different level you can also use `log_debug`, `log_warning` or `log_error`. Note
        that `log_error` will, by default, also raise an exception.
    :param cls: Customize the event class used. This allows user defined event handlers to only
        listen to specific types of log messages.
    :return: The emitted event.
    """
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


def log_debug(*args: Any, cls: type[LogEvent] = LogEvent) -> LogEvent:
    """Produce debug log output.

    This calls `log` with ``level="debug"``.
    """
    return log(*args, level="debug", cls=cls)


def log_warning(*args: Any, cls: type[LogEvent] = LogEvent) -> LogEvent:
    """Produce debug log output.

    This calls `log` with ``level="warning"``.
    """
    return log(*args, level="warning", cls=cls)


@overload
def log_error(
    *args: Any, cls: type[LogEvent] = LogEvent, raise_error: Literal[True] = True
) -> NoReturn: ...


@overload
def log_error(
    *args: Any, cls: type[LogEvent] = LogEvent, raise_error: Literal[False]
) -> LogEvent: ...


def log_error(*args: Any, cls: type[LogEvent] = LogEvent, raise_error: bool = True) -> LogEvent:
    """Produce error log output and optionally raise a `LoggedError`.

    This calls `log` with ``level="error"`` to produce the log output.

    :param raise_error: Whether to raise a `LoggedError` exception. Defaults to ``True``.
    """
    event = log(*args, level="error", cls=cls)

    if raise_error:
        raise LoggedError(event)

    return event


_already_logged: dict[int, tuple[BaseException, LoggedError]] = {}


@overload
def log_exception(exception: BaseException, raise_error: Literal[True] = True) -> NoReturn: ...


@overload
def log_exception(exception: BaseException, raise_error: Literal[False]) -> LoggedError: ...


def log_exception(exception: BaseException, raise_error: bool = True) -> LoggedError:
    """Produce error log output for an exception and optionally raise a `LoggedError`.

    If the exception was already logged, it will not be logged again. When raising a `LoggedError`,
    it will have the passed exception as cause, unless it already is a `LoggedError` in which case
    it will be re-raised directly.

    :param raise_error: Whether to raise a `LoggedError` exception. Defaults to ``True``.
    :return: The `LoggedError` exception that would be raised if ``raise_error`` were ``True``.
    """
    current = exception
    source = current_task_or_none()

    while isinstance(current, TaskFailed) and current.__cause__ is not None:
        source = current.task
        current = current.__cause__

    if isinstance(current, LoggedError):
        if raise_error:
            raise current
        return current

    try:
        found_key, found_value = _already_logged[id(current)]
        if found_key is current:
            if raise_error:
                raise found_value
            return found_value
    except KeyError:
        pass

    current_msg = str(current)

    if type(current).__module__ == "builtins":
        short_trace = traceback.format_tb(current.__traceback__, limit=-1)
        short_trace = "".join(short_trace)
        current_msg = f"{type(current).__name__}: {current_msg}\n{short_trace}"

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

    _already_logged[id(current)] = current, err

    if raise_error:
        raise err
    return err


_root_log_files: list[tuple[IO[Any] | None, bool, bool | None]] = []

_no_color = bool(os.getenv("NO_COLOR", ""))


def start_logging(
    file: IO[Any] | None = None,
    err: bool = False,
    color: bool | None = None,
    destination_label: str | None = None,
) -> None:
    """Start logging all log events reaching the current task.

    Can be called multiple times to log to multiple destinations.

    It is possible to stop logging by closing the file object passed to this function.

    :param file: The file to log to. Defaults to `sys.stdout` or `sys.stderr` depending on ``err``.
    :param err: Whether to log to `sys.stderr` instead of `sys.stdout`. Defaults to ``False``.
    :param color: Whether to use colors. Defaults to ``True`` for terminals and ``False`` otherwise.
        When the ``NO_COLOR`` environment variable is set, this will be ignored and no colors will
        be used.
    :param destination_label: Used to look up destination specific log level filtering.
        Used with `LogContext.destination_levels`.
    """
    if _no_color:
        color = False

    def log_handler(event: LogEvent):
        if file and file.closed:
            remove_log_handler()
            return
        emitter_default = event.source[LogContext].level
        if destination_label:
            destination_level = LogContext.destination_levels.get(
                destination_label, emitter_default
            )
        else:
            destination_level = emitter_default
        source_level = _level_order[destination_level]
        event_level = _level_order[event.level]
        if event_level < source_level:
            return
        formatted = LogContext.log_format(event)
        click.echo(formatted, file=file, err=err, color=color)

    remove_log_handler = current_task().sync_handle_events(LogEvent, log_handler)

    def interrupt_handler(event: TaskLoopInterrupted):
        if file and file.closed:
            remove_interrupt_handler()
            return
        click.secho("<Interrupted>", file=file, err=err, color=color, fg="yellow")

    remove_interrupt_handler = current_task().sync_handle_events(
        TaskLoopInterrupted, interrupt_handler
    )

    _root_log_files.append((file, err, color))


def start_debug_event_logging(
    file: IO[Any] | None = None,
    err: bool = False,
    color: bool | None = None,
    include_log: bool = False,
):
    if _no_color:
        color = False
    """Start logging all events reaching the current task.

    This will log all events, including debug events generated by the task loop itself as well as
    any events used internally by the application. This can be very verbose but also very useful for
    debugging.

    :param file: The file to log to. Defaults to `sys.stdout` or `sys.stderr` depending on `err`.
    :param err: Whether to log to `sys.stderr` instead of `sys.stdout`. Defaults to ``False``.
    :param color: Whether to use colors. Defaults to ``True`` for terminals and ``False`` otherwise.
        When the ``NO_COLOR`` environment variable is set, this will be ignored and no colors will
        be used.

    """

    def debug_event_log_handler(event: TaskEvent):
        if include_log or not isinstance(event, LogEvent):
            click.secho(repr(event), file=file, err=err, color=color, fg="cyan")

    current_task().sync_handle_events(TaskEvent, debug_event_log_handler)


def install_root_error_handler():
    """Installs a fallback error handler in the root task that logs an exception and re-raises it,
    aborting the root task and therefore the entire task loop.
    """

    def root_error_handler(error: BaseException):
        log_exception(error)

    task = current_task()
    assert task is root_task()
    task.set_error_handler(None, root_error_handler)
