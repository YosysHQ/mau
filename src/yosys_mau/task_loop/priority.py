from __future__ import annotations

import asyncio
import dataclasses
import functools
import heapq
import weakref

from yosys_mau.stable_set import StableSet
from yosys_mau.task_loop.job_server import Lease

from . import context, job_server


@context.task_context
class JobPriorities:
    """Task context to configure how job server leases are scheduled across tasks."""

    scheduler: job_server.Scheduler
    """Active scheduler for obtaining job server leases."""

    priority: tuple[int, ...] = ()
    """Priority with which to request a job server lease when using the `PriorityScheduler`.

    The lexicographically largest priority is scheduled first.
    """


@dataclasses.dataclass(eq=False)
@functools.total_ordering
class _PriorityItem:
    priority: tuple[int, ...]
    seq: int
    lease: weakref.ReferenceType[Lease] = dataclasses.field(compare=False)

    def _key(self, padded_len: int):
        return self.priority + (0,) * (padded_len - len(self.priority)), self.seq

    def __le__(self, other: _PriorityItem):
        padded_len = max(len(self.priority), len(other.priority))
        return other._key(padded_len) <= self._key(padded_len)

    def __lt__(self, other: _PriorityItem):
        padded_len = max(len(self.priority), len(other.priority))
        return other._key(padded_len) < self._key(padded_len)

    def __eq__(self, other: object):
        if not isinstance(other, _PriorityItem):
            return NotImplemented
        padded_len = max(len(self.priority), len(other.priority))
        return other._key(padded_len) == self._key(padded_len)


class PriorityScheduler(job_server.Scheduler):
    """Scheduler for job server leases that uses a priority queue to schedule tasks.

    It uses the current `JobPriorities.priority` task context to determine the priority when
    requesting a lease.
    """

    def __init__(self, parent: job_server.Scheduler):
        self._parent: job_server.Scheduler = parent
        self._pending_leases: list[_PriorityItem] = []
        self._pending_parent_leases: StableSet[Lease] = StableSet()
        self._held_parent_leases: StableSet[Lease] = StableSet()
        self._counter = 0

    def __return_lease__(self) -> None:
        self._held_parent_leases.pop().return_lease()

    def request_lease(self) -> Lease:
        pending = Lease(self)
        priority = JobPriorities.priority
        self._counter += 1

        heapq.heappush(
            self._pending_leases, _PriorityItem(priority, self._counter, weakref.ref(pending))
        )

        parent_lease = self._parent.request_lease()
        self._pending_parent_leases.add(parent_lease)

        if parent_lease.ready:
            asyncio.get_event_loop().call_soon(self._acquired_parent_lease, parent_lease)
        else:
            parent_lease.add_ready_callback(lambda: self._acquired_parent_lease(parent_lease))

        return pending

    def _next_pending_request(self) -> Lease | None:
        while self._pending_leases:
            item = heapq.heappop(self._pending_leases)
            lease = item.lease()
            if lease is not None:
                return lease
        return None

    def _acquired_parent_lease(self, parent_lease: Lease):
        self._pending_parent_leases.remove(parent_lease)

        request_lease = self._next_pending_request()
        if request_lease is None:
            parent_lease.return_lease()
            return

        self._held_parent_leases.add(parent_lease)
        request_lease.__mark_as_ready__()
