Event Handling
==============

Events are used to pass data from child tasks to their parents or other tasks.
A task can emit events and other tasks can listen to these by installing an event handler or obtaining an async iterator of events.
In both cases the type of event listened to can be efficiently filtered.

.. currentmodule:: yosys_mau.task_loop

.. autoclass:: TaskEvent
   :members:

.. autoclass:: TaskEventStream
   :members:

Built-in Events
---------------

.. autoclass:: DebugEvent

.. autoclass:: TaskStateChange
   :show-inheritance:
   :members:

.. autoclass:: TaskLoopInterrupted
   :show-inheritance:
