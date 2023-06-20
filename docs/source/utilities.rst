Utilities
=========

Apart from the functionality dedicated for writing front-end applications, ``mau`` also contains some general utilities that are used internally but can also be useful for other purposes.

Sets With Stable Iteration Order
--------------------------------

.. py:module:: yosys_mau.stable_set

Starting with Python 3.7 the `dict` type guarantees a stable iteration order matching the insertion order.
Previously the iteration order was arbitrary and not even deterministic, making it very easy to write accidentally non-deterministic code.
The `set` type on the other hand still has an arbitrary iteration order.
To get the same advantages of the new `dict` implementation for code that works with sets, ``mau`` provides the `StableSet` type which is a drop-in replacement for `set` but internally implemented using the `dict` type, thus offering the same iteration order guarantees.


.. py:class:: StableSet

   Implements the same API as `set` and can be used as a drop-in replacement.
