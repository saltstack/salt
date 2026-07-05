.. _pyobjects-renderer:

==================
Pyobjects Renderer
==================

The ``pyobjects`` renderer allows you to write Salt states using Python objects
instead of YAML. It provides a more programmatic way to define states.

Using ``module.run`` with Pyobjects
====================================

Salt 3005 introduced a new ``module.run`` syntax that expects the module
function name as a keyword argument. However, because module names contain
dots (e.g., ``shadow.lock_password``), you cannot directly use them as keyword
arguments in Python function calls. For example, the following will raise a
``SyntaxError``:

.. code-block:: python

    #!pyobjects

    user = ["susan"]
    Module.run("pyobject_shadow", shadow.lock_password=user)

This fails because ``shadow.lock_password`` is not a valid Python identifier.

Workaround
----------

To work around this, build a dictionary of keyword arguments and unpack it
with ``**``:

.. code-block:: python

    #!pyobjects

    lock_kwargs = {"shadow.lock_password": ["susan"]}
    Module.run("pyobject_shadow", **lock_kwargs)

This approach allows you to use any module function name, regardless of dots
or other special characters.

Example
-------

Here is a complete example using the ``shadow`` module:

.. code-block:: python

    #!pyobjects

    users = ["alice", "bob"]
    lock_kwargs = {"shadow.lock_password": users}
    Module.run("shadow_lock_password", **lock_kwargs)

This will lock the password for users ``alice`` and ``bob`` using the
``shadow.lock_password`` function.

For more details on the ``module.run`` state, see :ref:`module-run-state`.
