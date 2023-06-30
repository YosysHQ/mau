from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import pytest
import yosys_mau.task_loop as tl
import yosys_mau.task_loop.job_server as job


def test_default():
    env = os.environ.copy()
    env["MAKEFLAGS"] = "-k"
    env["MAU_TEST_JOB_COUNT"] = "4"
    subprocess.check_call([sys.executable, __file__, outer_process.__name__], env=env)


def test_nonblocking():
    env = os.environ.copy()
    env["MAKEFLAGS"] = "-k"
    env["YOSYS_JOBSERVER"] = "nonblocking"
    env["MAU_TEST_JOB_COUNT"] = "4"
    subprocess.check_call([sys.executable, __file__, outer_process.__name__], env=env)


def test_nonblocking_helper():
    env = os.environ.copy()
    env["MAKEFLAGS"] = "-k"
    env["YOSYS_JOBSERVER"] = "nonblocking"
    env["YOSYS_JOBSERVER_FORCE_HELPER"] = "1"
    env["MAU_TEST_JOB_COUNT"] = "4"
    subprocess.check_call([sys.executable, __file__, outer_process.__name__], env=env)


def test_local():
    env = os.environ.copy()
    env["MAKEFLAGS"] = "-k"
    env["YOSYS_JOBSERVER"] = "local"
    env["MAU_TEST_JOB_COUNT"] = "4"
    subprocess.check_call([sys.executable, __file__, outer_process.__name__], env=env)


def test_fifo():
    env = os.environ.copy()
    env["MAKEFLAGS"] = "-k"
    env["YOSYS_JOBSERVER"] = "fifo"
    env["MAU_TEST_JOB_COUNT"] = "4"
    subprocess.check_call([sys.executable, __file__, outer_process.__name__], env=env)


def test_serial():
    env = os.environ.copy()
    env["MAKEFLAGS"] = "-k"
    env["MAU_TEST_JOB_COUNT"] = "1"
    subprocess.check_call([sys.executable, __file__, outer_process.__name__], env=env)


def test_bad_fd_syntax():
    env = os.environ.copy()
    env["MAKEFLAGS"] = "--jobserver-fds=unknown"
    env["MAU_TEST_JOB_COUNT"] = "4"
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_call([sys.executable, __file__, outer_process.__name__], env=env)


def test_nonexistent_fifo():
    env = os.environ.copy()
    env["MAKEFLAGS"] = "--jobserver-auth=fifo:/dev/null/nope"
    env["MAU_TEST_JOB_COUNT"] = "4"
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_call([sys.executable, __file__, outer_process.__name__], env=env)


def outer_process():
    client = job.Client(int(os.environ["MAU_TEST_JOB_COUNT"]))
    subprocess.check_call(
        [sys.executable, __file__, inner_process.__name__], **client.subprocess_args()
    )


def inner_process():
    job_count = int(os.environ["MAU_TEST_JOB_COUNT"])
    client = job.global_client(job_count)

    stats = [0, 0, 0]

    async def waiter_main():
        stats[0] += 1
        stats[1] = max(stats[1], stats[0])
        await asyncio.sleep(0.15)
        stats[0] -= 1
        stats[2] += 1

    def new_waiter(i: int):
        task = tl.Task(on_run=waiter_main, name=f"waiter{i}")
        task.use_lease = True
        return task

    def main():
        for i in range(10):
            new_waiter(i)

    tl.run_task_loop(main)

    assert stats[0] == 0
    assert stats[1] == job_count
    assert stats[2] == 10

    stats = [0, 0, 0]

    async def raw_waiter() -> None:
        lease = client.request_lease()
        await lease
        stats[0] += 1
        stats[1] = max(stats[1], stats[0])
        await asyncio.sleep(0.15)
        stats[0] -= 1
        stats[2] += 1
        del lease

    async def inner_async():
        tasks = [asyncio.create_task(raw_waiter()) for _ in range(10)]

        for task in tasks:
            await task

    asyncio.run(inner_async())

    assert stats[0] == 0
    assert stats[1] == job_count
    assert stats[2] == 10


if __name__ == "__main__":
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
