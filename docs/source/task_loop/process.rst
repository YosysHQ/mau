Running Subprocesses as Task
============================

In the mau task loop, subprocesses run as tasks.
The output of a subprocess is made available using events.
It's possible to launch subprocesses by creating instances of either `Process` or of a user defined subclass of `Process`.

.. automodule:: yosys_mau.task_loop.process

.. autoclass:: Process
   :show-inheritance:
   :members: __init__, on_exit, shell_command,
         stdin, write, close_stdin, log_output

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
