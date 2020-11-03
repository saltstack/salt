.. _opts:

====================
Salt opts dictionary
====================

It is very common in the Salt codebase to see `opts` referred to in a number of
contexts.

For example, it can be seen as `__opts__` in certain cases, or simply as `opts`
as an argument to a function in others.

Simply put, this data structure is a dictionary of Salt's runtime configuration
information that's passed around in order for functions to know how Salt is configured.

When writing Python code to use specific parts of Salt, it may become necessary
to initialize a copy of `opts` from scratch in order to have it available for a
given function.

To do so, use the utility functions available in `salt.config`.

As an example, here is how one might generate and print an options dictionary
for a minion instance:

.. code-block:: python

    import salt.config

    opts = salt.config.minion_config("/etc/salt/minion")
    print(opts)

To generate and display `opts` for a master, the process is similar:

.. code-block:: python

    import salt.config

    opts = salt.config.master_config("/etc/salt/master")
    print(opts)
