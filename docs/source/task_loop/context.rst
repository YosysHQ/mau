Task Context Variables
======================

Contexts variables are used to automatically pass data from parent tasks to child tasks.
When reading a context variable, the value set by the first task--starting from the current task following parents up to the root task--is used.

.. automodule:: yosys_mau.task_loop.context

.. autofunction:: task_context

.. autoclass:: TaskContextDescriptor
   :members:

.. autoclass:: InlineContextVar
