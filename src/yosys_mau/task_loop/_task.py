from __future__ import annotations

import asyncio
import dataclasses
import functools
import gc
import inspect
import signal
import typing
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from itertools import count
from typing import Any, Awaitable, Callable, Iterator, Literal

from typing_extensions import ParamSpec, Self

from yosys_mau.stable_set import StableSet

from . import job_server as job

T = typing.TypeVar("T")
T_TaskEvent = typing.TypeVar("T_TaskEvent", bound="TaskEvent")
Args = ParamSpec("Args")

_current_task: ContextVar[Task] = ContextVar(f"{__name__}._current_task")


@contextmanager
def set_current_task(task: Task) -> typing.Iterator[None]:
    token = _current_task.set(task)
    try:
        yield
    finally:
        _current_task.reset(token)


class TaskLoopError(RuntimeError):
    pass


def current_task() -> Task:
    try:
        return _current_task.get()
    except LookupError:
        raise TaskLoopError("no task is currently active") from None


def root_task() -> RootTask:
    return task_loop().root_task


def background(fn: Callable[[], Awaitable[None]], *, wait: bool = False) -> None:
    current_task().background(fn, wait=wait)


TaskState = Literal[
    "preparing", "pending", "running", "waiting", "done", "cancelled", "discarded", "failed"
]


def as_awaitable(fn: Callable[Args, T | Awaitable[T]]) -> Callable[Args, Awaitable[T]]:
    def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> Awaitable[T]:
        result = fn(*args, **kwargs)
        if not isinstance(result, Awaitable):

            async def wrapper() -> T:
                return result

            return wrapper()
        return result  # type: ignore

    return wrapper


global_task_loop: TaskLoop | None = None


def task_loop() -> TaskLoop:
    global global_task_loop
    if global_task_loop is None:
        raise TaskLoopError("no global task loop has been installed")
    return global_task_loop


class TaskLoop:
    root_task: RootTask
    task_eq_ids: Iterator[int]

    def __init__(
        self,
        inner: Callable[[], None | Awaitable[None]],
        *,
        handle_sigint: bool = True,
    ) -> None:
        global global_task_loop
        if global_task_loop is not None:
            raise TaskLoopError("a task loop is already installed")
        global_task_loop = self

        async def wrapper():
            if handle_sigint:
                asyncio.get_event_loop().add_signal_handler(signal.SIGINT, self._handle_sigint)
            job.global_client()  # early setup of the job server client

            RootTask(on_run=inner)
            self.root_task.name = "root"

            await self.root_task.finished

            # Some __del__ implementations in the stdlib expect the event loop to be still running
            # and cause ignored exception warnings when they are cycle collected after the event
            # loop exited. Manually triggering a cycle collection fixes this.
            gc.collect()

        try:
            asyncio.run(wrapper())
        finally:
            global_task_loop = None

    def cancel(self) -> None:
        if self.root_task:
            self.root_task.cancel()

    def _handle_sigint(self) -> None:
        self.cancel()


class Task:
    __name: str
    __parent: Task | None
    __children: StableSet[Task]
    __child_names: set[str]

    __dependencies: StableSet[Task]
    __pending_dependencies: dict[Task, Callable[..., Any]]
    __pending_children: dict[Task, Callable[..., Any]]

    __reverse_dependencies: StableSet[Task]

    __error_handlers: dict[Task | None, Callable[[BaseException], Awaitable[None] | None]]

    __state: TaskState

    __aio_main_task: asyncio.Task[None]
    __aio_background_tasks: StableSet[asyncio.Task[None]]
    __aio_wait_background_tasks: StableSet[asyncio.Task[None]]

    __started: asyncio.Future[None]
    __finished: asyncio.Future[None]

    __event_cursors: dict[type, asyncio.Future[TaskEventCursor[Any]]]

    __use_lease: bool
    __lease: job.Lease | None

    discard: bool

    @property
    def use_lease(self) -> bool:
        return self.__use_lease

    @use_lease.setter
    def use_lease(self, use_lease: bool) -> None:
        if use_lease and not self.__use_lease:
            assert (
                self.__state == "preparing"
            ), "cannot change lease usage after the task is prepared"
        self.__use_lease = use_lease
        if not use_lease:
            self.__lease = None

    @property
    def parent(self) -> Task | None:
        return self.__parent

    @property
    def state(self) -> TaskState:
        return self.__state

    @property
    def name(self) -> str:
        return self.__name

    @name.setter
    def name(self, name: str) -> None:
        assert name
        if self.parent is None:
            self.__name = name
            return

        if self.__name:
            self.parent.__child_names.remove(self.__name)

        if name not in self.parent.__child_names:
            self.__name = name
            self.parent.__child_names.add(name)
            return

        for i in count(1):
            if (unique_name := f"{name}#{i}") not in self.parent.__child_names:
                self.__name = unique_name
                self.parent.__child_names.add(unique_name)
                break

    @property
    def path(self) -> str:
        if self.parent and self.parent.parent:
            return f"{self.parent.path}.{self.name}"
        return self.name

    def __str__(self) -> str:
        return self.path

    def __init__(
        self,
        on_run: Callable[[Self], Awaitable[None] | None]
        | Callable[[], Awaitable[None] | None]
        | None = None,
        *,
        on_prepare: Callable[[Self], Awaitable[None] | None]
        | Callable[[], Awaitable[None] | None]
        | None = None,
        lease: bool = False,
    ):
        if on_run is not None:
            if inspect.signature(on_run).parameters:
                on_run = functools.partial(on_run, self)
            self.on_run = as_awaitable(on_run)  # type: ignore
        if on_prepare is not None:
            if inspect.signature(on_prepare).parameters:
                on_prepare = functools.partial(on_prepare, self)
            self.on_prepare = as_awaitable(on_prepare)  # type: ignore

        self.__name = ""
        self.__state = "preparing"
        self.__children = StableSet()
        self.__child_names = set()
        self.__dependencies = StableSet()
        self.__pending_dependencies = {}
        self.__pending_children = {}
        self.__reverse_dependencies = StableSet()
        self.__error_handlers = {}
        self.__started = asyncio.Future()
        self.__finished = asyncio.Future()
        self.__use_lease = lease
        self.__lease = None
        self.__cleaned_up = False
        self.__aio_background_tasks = StableSet()
        self.__aio_wait_background_tasks = StableSet()
        self.__event_cursors = {}

        self.discard = True

        if isinstance(self, RootTask):
            self.__parent = None
            loop = task_loop()
            assert not hasattr(loop, "root_task")
            task_loop().root_task = self
        else:
            self.__parent = current_task()

            assert (
                self.__parent.state == "running"
            ), "cannot create child tasks before the parent task is running"
            # TODO allow this but make children block for their parent having started

            self.__parent.__add_child(self)

        self.name = self.__class__.__name__

        self.__aio_main_task = asyncio.create_task(self.__task_main())

    def __change_state(self, new_state: TaskState) -> None:
        if self.__state == new_state:
            return
        old_state, self.__state = self.__state, new_state
        if self.__parent:
            with self.as_current_task():
                TaskStateChange(old_state, new_state).emit()

    def depends_on(self, task: Task) -> None:
        assert self.state in (
            "preparing",
            "pending",
        ), "cannot add dependencies after task has started"
        self.__dependencies.add(task)
        if task.state in ("preparing", "pending", "running"):
            callback: Callable[[Any], None] = lambda _: self.__dependency_finished(task)
            task.__finished.add_done_callback(callback)
            self.__pending_dependencies[task] = callback
            task.__reverse_dependencies.add(self)

    def set_error_handler(
        self, task: Task | None, handler: Callable[[BaseException], Awaitable[None] | None]
    ) -> None:
        self.__error_handlers[task] = handler

    def __add_child(self, task: Task) -> None:
        assert self.state == "running", "children can only be added to a running tasks"
        self.__children.add(task)
        if task.state in ("preparing", "pending", "running"):
            callback: Callable[[Any], None] = lambda _: self.__child_finished(task)
            task.__finished.add_done_callback(callback)
            self.__pending_children[task] = callback

    def __dependency_finished(self, task: Task) -> None:
        self.__pending_dependencies.pop(task)
        self.__propagate_failure(task, wrap=(DependencyFailed, DependencyCancelled))
        self.__check_start()

    def __child_finished(self, task: Task) -> None:
        self.__pending_children.pop(task)
        self.__propagate_failure(task, wrap=(ChildTaskFailed, ChildTaskCancelled))
        self.__check_finish()

    def __check_start(self) -> None:
        if self.state != "pending":
            return
        if self.__pending_dependencies:
            self.__lease = None
            return
        if self.__use_lease:
            # TODO wrap the raw lease in some logic that prefers passing leases within the hierarchy
            # before returning them to the job server
            if self.__lease is None:
                self.__lease = job.global_client().request_lease()
            if not self.__lease.ready:
                self.__lease.add_ready_callback(self.__check_start)
                return
        self.__started.set_result(None)

    def __check_finish(self) -> None:
        if self.state != "waiting":
            return
        if self.__pending_children:
            return
        if self.__aio_wait_background_tasks:
            return
        self.__cleanup()
        self.__finished.set_result(None)

    def __propagate_failure(
        self,
        task: Task,
        exception: BaseException | None = None,
        *,
        wrap: tuple[Callable[[Task], BaseException], Callable[[Task], BaseException]] | None = None,
    ) -> None:
        if exception is None:
            try:
                exception = task.__finished.exception()
            except asyncio.CancelledError as exc:
                exception = exc

            if exception is None:
                return

        if wrap:
            wrap_failed, wrap_cancelled = wrap

            if isinstance(exception, asyncio.CancelledError):
                exc = wrap_cancelled(task)
            else:
                exc = wrap_failed(task)
                exc.__cause__ = exception
            exception = exc

        if handler := self.__error_handlers.get(task):
            self.background(lambda: handler(exception), wait=True, error_handler=True)
            return

        if handler := self.__error_handlers.get(None):
            self.background(lambda: handler(exception), wait=True, error_handler=True)
            return

        if isinstance(exception, asyncio.CancelledError):
            self.cancel()
        else:
            self.__failed(exception)

    async def __task_main(self) -> None:
        __prev_task = _current_task.set(self)
        try:
            TaskStateChange(None, self.__state).emit()
            await self.on_prepare()
            self.__change_state("pending")
            self.__check_start()
            await self.started
            self.__change_state("running")
            await self.on_run()
            self.__lease = None
            self.__change_state("waiting")
            self.__check_finish()
            await self.finished
            self.__change_state("done")
        except Exception as exc:
            self.__propagate_failure(self, exc)
        finally:
            _current_task.reset(__prev_task)
            self.__cleanup()

    def __cleanup(self):
        if self.__cleaned_up:
            return
        self.__cleaned_up = True
        self.on_cleanup()
        for task, callback in self.__pending_children.items():
            task.__finished.remove_done_callback(callback)

        for task, callback in self.__pending_dependencies.items():
            task.__finished.remove_done_callback(callback)
            task.__reverse_dependencies.remove(self)
            if not task.__reverse_dependencies and task.discard:
                asyncio.get_event_loop().call_soon(lambda: task.__cancel(discard=True))

        for aio_task in self.__aio_background_tasks:
            aio_task.cancel()

        for aio_task in self.__aio_wait_background_tasks:
            aio_task.cancel()

        for cursor in self.__event_cursors.values():
            cursor.cancel()

    def __failed(self, exc: BaseException | None) -> None:
        if exc is None or self.has_finished:
            return
        self.__lease = None
        if not self.__started.done():
            self.__started.set_exception(exc)
            self.__started.exception()
        if not self.__finished.done():
            self.__finished.set_exception(exc)
            self.__finished.exception()
        self.__change_state("failed")

        for child in self.__children:
            child.__cancel(discard=True)

    async def on_prepare(self) -> None:
        pass

    async def on_run(self) -> None:
        pass

    @property
    async def started(self) -> None:
        # TODO should this wrap exceptions?
        await asyncio.shield(self.__started)

    @property
    async def finished(self) -> None:
        # TODO should this wrap exceptions?
        await asyncio.shield(self.__finished)

    @property
    def has_finished(self) -> bool:
        return self.__state in ("done", "cancelled", "discarded", "failed")

    def cancel(self) -> None:
        self.__cancel(discard=False)

    def __cancel(self, discard: bool = False) -> None:
        if self.has_finished:
            return
        self.__aio_main_task.cancel()
        self.__lease = None
        if not self.__started.done():
            self.__started.cancel()
        if not self.__finished.done():
            self.__finished.cancel()

        self.__change_state("discarded" if discard else "cancelled")

        for child in self.__children:
            child.__cancel(discard=discard)

        self.on_cancel()

    def on_cancel(self):
        pass

    def on_cleanup(self):
        pass

    def background(
        self,
        target: Callable[[], Awaitable[None] | None],
        *,
        wait: bool = False,
        error_handler: bool = False,
    ) -> asyncio.Task[None]:
        assert error_handler or self.state in (
            "running",
            "waiting",
        ), "background handlers can only be created for running or waiting tasks"
        target_coroutine = as_awaitable(target)

        aio_task = None

        if error_handler and self.has_finished:
            wait = False

        async def wrapper():
            nonlocal aio_task
            __prev_task = _current_task.set(self)
            try:
                await target_coroutine()
            except asyncio.CancelledError:
                pass
            except BaseException as e:
                self.__failed(e)
            finally:
                _current_task.reset(__prev_task)
                if aio_task is not None:
                    if wait:
                        self.__aio_wait_background_tasks.remove(aio_task)
                        self.__check_finish()
                    else:
                        self.__aio_background_tasks.discard(aio_task)

        aio_task = asyncio.create_task(wrapper())

        if error_handler and self.has_finished:
            return aio_task

        if wait:
            self.__aio_wait_background_tasks.add(aio_task)
        else:
            self.__aio_background_tasks.add(aio_task)

        return aio_task

    def __emit_event__(self, event: TaskEvent) -> None:
        assert event.source is self

        current = self

        while current is not None:
            for mro_item in type(event).mro():
                cursor = current.__event_cursors.get(mro_item)
                if cursor is None:
                    continue

                next_cursor: asyncio.Future[TaskEventCursor[Any]] = asyncio.Future()
                cursor.set_result(TaskEventCursor(event, next_cursor))
                current.__event_cursors[mro_item] = next_cursor

            current = current.__parent

    def events(
        self, event_type: type[T_TaskEvent], where: Callable[[T_TaskEvent], bool] | None = None
    ) -> TaskEventStream[T_TaskEvent]:
        if event_type not in self.__event_cursors:
            self.__event_cursors[event_type] = asyncio.Future()
        cursor = self.__event_cursors[event_type]
        return TaskEventStream(cursor, where or (lambda _: True))

    def as_current_task(self) -> typing.ContextManager[None]:
        return set_current_task(self)


class RootTask(Task):
    pass


class TaskFailed(Exception):
    def __init__(self, task: Task):
        self.task = task

    def __str__(self) -> str:
        return f"Task {self.task} failed"


class DependencyFailed(TaskFailed):
    def __str__(self) -> str:
        return f"Dependency {self.task} failed"


class DependencyCancelled(DependencyFailed, asyncio.CancelledError):
    def __str__(self) -> str:
        return f"Dependency {self.task} cancelled"


class ChildTaskFailed(TaskFailed):
    def __str__(self) -> str:
        if self.task.parent and self.task.parent.parent:
            return f"Child task {self.task} failed"
        else:
            return f"Task {self.task} failed"


class ChildTaskCancelled(ChildTaskFailed, asyncio.CancelledError):
    def __str__(self) -> str:
        if self.task.parent and self.task.parent.parent:
            return f"Child task {self.task} cancelled"
        else:
            return f"Task {self.task} cancelled"


@dataclass
class TaskEvent:
    def __post_init__(self) -> None:
        self.__source = current_task()

    def __init_subclass__(cls) -> None:
        # This is a hack that prevents dataclasses from adding a __repr__ method without requiring
        # the ``repr=false`` argument to `dataclass`.
        cls.__repr__ = cls.__repr__

    def __repr__(self):
        out: list[str] = []
        for field in dataclasses.fields(self):
            out.append(f"{field.name}={getattr(self, field.name)!r}")
        return f"{self.source}: {self.__class__.__qualname__}({', '.join(out)})"

    @property
    def source(self) -> Task:
        return self.__source

    def emit(self) -> None:
        self.source.__emit_event__(self)


@dataclass
class TaskEventCursor(typing.Generic[T_TaskEvent]):
    event: T_TaskEvent
    tail: asyncio.Future[TaskEventCursor[T_TaskEvent]]


class TaskEventStream(typing.AsyncIterator[T_TaskEvent]):
    __cursor: asyncio.Future[TaskEventCursor[T_TaskEvent]]
    __where: Callable[[T_TaskEvent], bool]

    def __init__(
        self,
        cursor: asyncio.Future[TaskEventCursor[T_TaskEvent]],
        where: Callable[[T_TaskEvent], bool],
    ):
        self.__cursor = cursor
        self.__where = where

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> T_TaskEvent:
        while True:
            try:
                cursor = await self.__cursor
            except asyncio.CancelledError:
                raise StopAsyncIteration
            result = cursor.event
            self.__cursor = cursor.tail
            if self.__where(result):
                return result

    def process(
        self,
        handler: Callable[[Self], Awaitable[None]],
        *,
        wait: bool = False,
    ) -> None:
        background(lambda: handler(self), wait=wait)

    def handle(self, handler: Callable[[T_TaskEvent], Awaitable[None] | None]) -> None:
        handler = as_awaitable(handler)

        async def stream_handler():
            async for event in self:
                await handler(event)

        background(stream_handler, wait=False)


class DebugEvent(TaskEvent):
    pass


@dataclass(repr=False)
class TaskStateChange(DebugEvent):
    previous_state: TaskState | None
    state: TaskState

    def __repr__(self) -> str:
        return f"{self.source}: {self.previous_state} -> {self.state}"
