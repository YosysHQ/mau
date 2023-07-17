from __future__ import annotations

import os
import select
import signal
from typing import Any


def job_server_helper(
    server_read_fd: int, server_write_fd: int, request_fd: int, response_fd: int
) -> None:  # pragma: no cover (covered but not detected by coverage)
    """Helper process to handle blocking job server pipes."""

    def handle_sigusr1(*args: Any):
        # Since Python doesn't allow user code to handle EINTR anymore, we replace the
        # jobserver fd with an fd at EOF to interrupt a blocking read in a way that
        # cannot lose any read data
        r, w = os.pipe()
        os.close(w)
        os.dup2(r, server_read_fd)
        os.close(r)

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGUSR1, handle_sigusr1)
    pending = 0
    while True:
        try:
            new_pending = len(os.read(request_fd, 1024))
            if new_pending == 0:
                pending = 0
                break
            else:
                pending += new_pending
                continue
        except BlockingIOError:
            if pending == 0:
                select.select([request_fd], [], [])
                continue

        if pending > 0:
            try:
                # Depending on the make version (4.3 vs 4.2) this is blocking or
                # non-blocking. As this is an attribute of the pipe not the fd, we
                # cannot change it without affecting other processes. Older versions of
                # gnu make require this to be blocking, and produce errors if it is
                # non-blocking. Newer versions of gnu make set this non-blocking, both,
                # as client and as server. The documentation still says it is blocking.
                # This leaves us no choice but to handle both cases, which is the reason
                # we have this helper process in the first place.
                token = os.read(server_read_fd, 1)
            except BlockingIOError:
                select.select([server_read_fd], [], [])
                continue

            pending -= 1

            try:
                os.write(response_fd, token)
            except:
                os.write(server_write_fd, token)
                raise
    os.close(server_write_fd)


if __name__ == "__main__":  # pragma: no cover (covered but not detected by coverage)
    import sys

    assert len(sys.argv) == 5
    job_server_helper(*map(int, sys.argv[1:]))
