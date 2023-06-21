Running Subprocesses as Task
============================


.. automodule:: yosys_mau.task_loop.process

.. autoclass:: Process
   :show-inheritance:
   :members: __init__, on_exit

Context Variables
-----------------

.. autoclass:: ProcessContext

   .. autoattribute:: cwd
      :annotation: = os.getcwd()

Events
------

.. autoclass:: ProcessEvent
   :show-inheritance:

.. autoclass:: OutputEvent
   :show-inheritance:
   :members:

.. autoclass:: StdoutEvent
   :show-inheritance:

.. autoclass:: StderrEvent
   :show-inheritance:

.. autoclass:: ExitEvent
   :show-inheritance:
   :members:
