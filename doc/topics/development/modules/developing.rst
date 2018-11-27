======================
Developing New Modules
======================

Interactive Debugging
=====================

Sometimes debugging with ``print()`` and extra logs sprinkled everywhere is not
the best strategy.

IPython is a helpful debug tool that has an interactive python environment
which can be embedded in python programs.

First the system will require IPython to be installed.

.. code-block:: bash

    # Debian
    apt-get install ipython

    # Arch Linux
    pacman -Syu ipython2

    # RHEL/CentOS (via EPEL)
    yum install python-ipython


Now, in the troubling python module, add the following line at a location where
the debugger should be started:

.. code-block:: python

    test = 'test123'
    import IPython; IPython.embed_kernel()

After running a Salt command that hits that line, the following will show up in
the log file:

.. code-block:: text

    [CRITICAL] To connect another client to this kernel, use:
    [IPKernelApp] --existing kernel-31271.json

Now on the system that invoked ``embed_kernel``, run the following command from
a shell:

.. code-block:: bash

    # NOTE: use ipython2 instead of ipython for Arch Linux
    ipython console --existing

This provides a console that has access to all the vars and functions, and even
supports tab-completion.

.. code-block:: python

    print(test)
    test123

To exit IPython and continue running Salt, press ``Ctrl-d`` to logout.
