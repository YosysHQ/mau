Task Loop
=========

The task loop provides common functionality for applications that perform several tasks that can run concurrently, have dependencies between them, can fail and handle failure of other tasks.

This page provides a general overview of the task loop and its concepts, see individual subpages for details:

.. toctree::
   :maxdepth: 1

   task
   event
   context
   logging
   process
   priority


.. rubric:: Task Hierarchy and Dependencies

When a task runs, it performs several actions and either ends successfully, fails or becomes cancelled or discarded (the latter is used as a term for automatic implicit cancellations).
A task can perform some of these actions on its own and it can also launch one or several child task to do so.

Every task--apart from the root task--has another task as parent task.
The root task is created automatically when starting the event loop and ends when the event loop ends.
Tasks that have the root task as parent are also referred to as top-level tasks.

A parent task waits for its children to complete successfully before it itself can do so.
In addition to that, arbitrary dependencies between tasks across the hierarchy can be declared to constrain the scheduling of tasks and to propagate errors.

When a task fails, e.g. when the the user code throws an uncought exception, its still running children are discarded and its parent task fails as do any tasks depending on the failing task.
Parent tasks and dependencies can install error handlers to override this behavior, i.e. to recover from a failing dependency or child.

.. rubric:: Current Task

Whenever Python code executes as part of the event loop, it executes in the context of a specific task, called the *current task*.
Many operations implicitly use the current task, e.g. creating a new task makes it a child of the current task.
When the event loop starts, the root task is the current task.

It is always possible to temporarily override the current task for a section of code.
Doing this does not affect concurrently executing code, as tracking the current task is implemented using Python's `contextvars` feature.

.. rubric:: Concurrency

By default, tasks run concurrently, respecting the implicit hierarchical dependency as well as explicitly declared dependencies.
Within a task, multiple Python async coroutines can also run concurrently, e.g. to interact with multiple child tasks simultaneously.
The task loop also integrates with the Make jobserver protocol which allows limiting the concurrent execution of computational tasks to the number of available cores.

.. rubric:: Communication

The task loop provides two dedicated mechanisms for communication between tasks: context variables and events.
In addition any other mechanism that integrates with Python's asyncio runtime can be used.

.. rubric:: Context Variables

Contexts variables are used to automatically pass data from parent tasks to child tasks.
When reading a context variable, the value set by the first task--starting from the current task following parents up to the root task--is used.
This is similar to environment variables with the difference that later updates are visible to already running child tasks for whch the context variable is not explicitly set.

.. rubric:: Events

Events are used to pass data from child tasks to their parents or other tasks.
A task can emit events and other tasks can listen to these by installing an event handler or obtaining an async iterator of events.
In both cases the type of event listened to can be efficiently filtered.

When listening to a task, events emitted by children of the listened to task are also received.
Each event carries a reference to the task that emitted it, which allows listeners to distinguish between events emitted by a task itself or by its children.

Among other things, installing an event handler on the root task is a useful way to generated linearly ordered logs of things that happen concurrently.
To aid debugging, tasks also automatically emit debug events corresponding to state changes, e.g. when a task starts or stops running.
