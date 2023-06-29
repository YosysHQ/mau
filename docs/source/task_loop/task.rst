Task Management
===============

.. automodule:: yosys_mau.task_loop


.. autofunction:: run_task_loop

.. autofunction:: current_task

.. autoclass:: Task
   :members:
   :special-members: __getitem__

   .. automethod:: __init__


Exceptions
----------

.. autoclass:: TaskLoopError
   :members:

.. autoclass:: TaskAborted
   :members:

.. autoclass:: TaskFailed
   :show-inheritance:

.. autoclass:: TaskCancelled
   :show-inheritance:

.. autoclass:: DependencyAborted
   :show-inheritance:

.. autoclass:: DependencyFailed
   :show-inheritance:

.. autoclass:: DependencyCancelled
   :show-inheritance:

.. autoclass:: ChildAborted
   :show-inheritance:

.. autoclass:: ChildFailed
   :show-inheritance:

.. autoclass:: ChildCancelled
   :show-inheritance:
