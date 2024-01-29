from __future__ import annotations

import asyncio
import atexit
import os
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import typing
import warnings
import weakref

if os.name == "posix":
    import fcntl


inherited_job_count: int | None = None
inherited_job_server_fds: tuple[int, int] | None = None
inherited_job_server_pass_fds: tuple[int, ...] = ()
inherited_job_server_present: bool | None = None
inherited_job_server_supported: bool = False
inherited_other_makeflags: list[str]


def process_job_server_environment() -> None:
    """Process the environment looking for a make job server. This should be called
    early (when only inherited fds are present) to reliably detect whether the job server
    specified in the environment is accessible."""
    global inherited_job_count
    global inherited_job_server_fds
    global inherited_job_server_present
    global inherited_job_server_supported
    global inherited_other_makeflags
    global inherited_job_server_pass_fds

    inherited_job_server_present = False
    inherited_other_makeflags = []

    for flag in shlex.split(os.environ.get("MAKEFLAGS", "")):
        if flag.startswith("-j"):
            if flag == "-j":
                inherited_job_count = 0
            else:
                try:
                    inherited_job_count = int(flag[2:])
                except ValueError:
                    pass
        elif flag.startswith("--jobserver-auth=") or flag.startswith("--jobserver-fds="):
            inherited_job_server_present = True
            if os.name == "posix":
                arg = flag.split("=", 1)[1]
                if arg.startswith("fifo:"):
                    inherited_job_server_supported = True
                    try:
                        fd = os.open(arg[5:], os.O_RDWR)
                    except FileNotFoundError:
                        inherited_other_makeflags.append(flag)
                        continue
                    else:
                        inherited_job_server_fds = fd, fd
                else:
                    arg = arg.split(",")
                    try:
                        job_server_fds = int(arg[0]), int(arg[1])
                    except ValueError:
                        inherited_other_makeflags.append(flag)
                        continue

                    inherited_job_server_supported = True

                    inherited_job_server_pass_fds = tuple(sorted(set(job_server_fds)))

                    try:
                        for fd in job_server_fds:
                            fcntl.fcntl(fd, fcntl.F_GETFD)
                    except OSError:
                        inherited_other_makeflags.append(flag)
                        continue

                    inherited_job_server_fds = job_server_fds
        else:
            inherited_other_makeflags.append(flag)


class Scheduler(typing.Protocol):
    def __return_lease__(self) -> None: ...

    def request_lease(self) -> Lease: ...


class Lease:
    def __init__(self, scheduler: Scheduler):
        self._scheduler = scheduler
        self._is_ready = False
        self._is_done = False

        self._future: None | asyncio.Future[None] = None

    def return_lease(self) -> None:
        if self._is_ready and not self._is_done:
            self._scheduler.__return_lease__()

        self._is_done = True

    def __await__(self) -> typing.Generator[typing.Any, typing.Any, typing.Any]:
        if self._is_ready:
            return
        if self._future is None:
            self._future = asyncio.Future()

        yield from self._future.__await__()

    def __repr__(self):  # pragma: no cover (debug only)
        return f"is_ready={self._is_ready} is_done={self._is_done}"

    def __del__(self):
        self.return_lease()

    def __mark_as_ready__(self) -> None:
        assert not self._is_ready
        self._is_ready = True

        if self._future is not None and not self._future.done():
            self._future.set_result(None)

    @property
    def ready(self) -> bool:
        return self._is_ready

    @property
    def done(self) -> bool:
        return self._is_done

    def add_ready_callback(self, callback: typing.Callable[[], None]) -> None:
        if self._is_ready:
            callback()
        if self._future is None:
            self._future = asyncio.Future()
            self._future.add_done_callback(lambda _: callback())


class Server:
    job_count: int
    have_pipe: bool
    read_fd: int
    write_fd: int
    makeflags: list[str]
    tmpdir: tempfile.TemporaryDirectory[typing.Any]

    def __init__(self, job_count: int):
        assert job_count >= 1
        # TODO support unlimited parallelism?
        self.job_count = job_count
        if job_count == 1:
            self.have_pipe = False
            self.makeflags = []
        elif job_count > 1:
            self.have_pipe = True
            if os.getenv("YOSYS_JOBSERVER") == "fifo":
                self.tmpdir = tempfile.TemporaryDirectory()
                path = f"{self.tmpdir.name}/fifo"
                os.mkfifo(path)
                self.read_fd = self.write_fd = os.open(path, os.O_RDWR)
                os.write(self.write_fd, b"*" * (job_count - 1))
                self.makeflags = [
                    f"-j{job_count}",
                    f"--jobserver-auth=fifo:{path}",
                ]
            else:
                self.read_fd, self.write_fd = os.pipe()
                if os.getenv("YOSYS_JOBSERVER") == "nonblocking":
                    os.set_blocking(self.read_fd, False)
                os.write(self.write_fd, b"*" * (job_count - 1))
                self.makeflags = [
                    f"-j{job_count}",
                    f"--jobserver-auth={self.read_fd},{self.write_fd}",
                    f"--jobserver-fds={self.read_fd},{self.write_fd}",
                ]

    def subprocess_args(self, env: dict[str, str] | None = None) -> dict[str, typing.Any]:
        if env is None:
            env = os.environ.copy()
        else:
            env = env.copy()
        env["MAKEFLAGS"] = shlex.join([*inherited_other_makeflags, *self.makeflags])
        if self.have_pipe:
            return {"pass_fds": [self.read_fd, self.write_fd], "env": env}
        else:
            return {"env": env}


class Client:
    def __init__(self, fallback_job_count: int | None = None):
        self._job_count = None

        self._read_fd: int
        self._write_fd: int
        self._have_pipe: bool = False
        self._helper_process = None

        self._local_slots = 1
        self._acquired_slots: list[bytes] = []
        self._pending_leases: list[weakref.ReferenceType[Lease]] = []

        self._registered_with_asyncio = None
        self._poll_fd: int

        self._job_server: Server | None = None

        if inherited_job_server_present is None:
            process_job_server_environment()

        have_job_server = inherited_job_server_present

        if have_job_server and not inherited_job_server_supported:
            # There are even more incompatible variants of the make job server on
            # windows, none of them are supported for now.
            warnings.warn(
                "Found unsupported job server type in MAKEFLAGS, disabling parallel execution.",
                RuntimeWarning,
            )
            have_job_server = False
            fallback_job_count = 1

        if have_job_server and inherited_job_server_fds is None:
            warnings.warn(
                "Could not connect to job server found in MAKEFLAGS, disabling parallel execution.",
                RuntimeWarning,
            )
            have_job_server = False
            fallback_job_count = 1

        if have_job_server:
            job_count = inherited_job_count
        elif fallback_job_count is not None:
            job_count = fallback_job_count
        elif inherited_job_count is not None and inherited_job_count > 0:
            job_count = inherited_job_count
        else:
            try:
                job_count = len(os.sched_getaffinity(0))
            except AttributeError:
                job_count = os.cpu_count()

        if job_count is None or job_count < 1:
            job_count = 1

        if os.getenv("YOSYS_JOBSERVER") == "local":
            self._local_slots = job_count
        elif have_job_server:
            assert inherited_job_server_fds is not None
            self._read_fd, self._write_fd = inherited_job_server_fds
            self._have_pipe = True
        elif os.name == "nt":
            # On Windows, without a job server, use only local slots
            self._local_slots = job_count
        else:
            assert job_count is not None
            self._job_server = Server(job_count)
            if self._job_server.have_pipe:
                self._have_pipe = True
                self._read_fd = self._job_server.read_fd
                self._write_fd = self._job_server.write_fd

        self._job_count = job_count

        if self._have_pipe:
            if os.get_blocking(self._read_fd) or os.getenv("YOSYS_JOBSERVER_FORCE_HELPER"):
                from . import job_server_helper

                request_read_fd, self.request_write_fd = os.pipe()
                self.response_read_fd, response_write_fd = os.pipe()
                os.set_blocking(self.response_read_fd, False)
                os.set_blocking(request_read_fd, False)

                pass_fds = [self._read_fd, self._write_fd, request_read_fd, response_write_fd]

                self._helper_process = subprocess.Popen(
                    [
                        sys.executable,
                        job_server_helper.__file__,
                        *map(str, pass_fds),
                    ],
                    stdin=subprocess.DEVNULL,
                    pass_fds=pass_fds,
                )

                os.close(request_read_fd)
                os.close(response_write_fd)

                self._poll_fd = self.response_read_fd
                atexit.register(self._atexit_blocking)
            else:
                self._poll_fd = self._read_fd
                atexit.register(self._atexit_nonblocking)

    def _atexit_nonblocking(self) -> None:
        assert self._have_pipe
        while self._acquired_slots:
            os.write(self._write_fd, self._acquired_slots.pop())

    def _atexit_blocking(self) -> None:
        assert self._have_pipe
        # Return all slot tokens we are currently holding
        while self._acquired_slots:
            os.write(self._write_fd, self._acquired_slots.pop())

        if self._helper_process:
            # Closing the request pipe singals the helper that we want to exit
            os.close(self.request_write_fd)

            # Additionally we send a signal to interrupt a blocking read within the helper
            self._helper_process.send_signal(signal.SIGUSR1)

            # The helper might have been in the process of sending us some tokens, which
            # we still need to return
            while True:
                try:
                    token = os.read(self.response_read_fd, 1)
                except BlockingIOError:
                    select.select([self.response_read_fd], [], [])
                    continue
                if not token:
                    break
                os.write(self._write_fd, token)
            os.close(self.response_read_fd)

            # Wait for the helper to exit, should be immediate at this point
            self._helper_process.wait()

    def request_lease(self) -> Lease:
        pending = Lease(self)

        if self._local_slots > 0:
            self._local_slots -= 1
            pending.__mark_as_ready__()
        else:
            self._pending_leases.append(weakref.ref(pending))
            if self._helper_process:
                os.write(self.request_write_fd, b"!")
            self._register_poll()

        return pending

    def _register_poll(self):
        loop = asyncio.get_running_loop()
        if self._registered_with_asyncio is not loop and hasattr(self, "_poll_fd"):
            self._registered_with_asyncio = loop
            loop.add_reader(self._poll_fd, self.poll)

    def _unregister_poll(self):
        if self._registered_with_asyncio:
            loop = self._registered_with_asyncio
            self._registered_with_asyncio = None
            loop.remove_reader(self._poll_fd)

    def __return_lease__(self):
        if self._acquired_slots:
            os.write(self._write_fd, self._acquired_slots.pop())
            return

        if self._activate_pending_lease():
            return

        self._local_slots += 1

    def _activate_pending_lease(self) -> bool:
        while self._pending_leases:
            pending = self._pending_leases.pop(0)()
            if pending is None:
                continue
            pending.__mark_as_ready__()
            return True
        return False

    def _has_pending_leases(self) -> bool:
        while self._pending_leases and not self._pending_leases[-1]():
            self._pending_leases.pop()
        return bool(self._pending_leases)

    def poll(self) -> None:
        if not (self._helper_process or self._has_pending_leases()):
            self._unregister_poll()
            return

        while self._helper_process or self._has_pending_leases():
            try:
                token = os.read(self._poll_fd, 1)
            except BlockingIOError:
                break
            if not token:
                self._unregister_poll()
                raise RuntimeError("job server is gone")

            self._got_token(token)

    def _got_token(self, token: bytes) -> None:
        self._acquired_slots.append(token)

        if self._activate_pending_lease():
            return

        self.__return_lease__()

    def subprocess_args(self, env: dict[str, str] | None = None) -> dict[str, typing.Any]:
        if self._job_server:
            return self._job_server.subprocess_args(env)
        else:
            args: dict[str, typing.Any] = dict(pass_fds=inherited_job_server_pass_fds)
            if env is not None:
                args["env"] = env
            return args


_global_client_instance: Client | None = None


def global_client(fallback_job_count: int | None = None) -> Client:
    global _global_client_instance
    if _global_client_instance is None:
        _global_client_instance = Client(fallback_job_count)
    return _global_client_instance
