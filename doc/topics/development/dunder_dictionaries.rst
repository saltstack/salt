===================
Dunder Dictionaries
===================

Salt provides several special "dunder" dictionaries as a convenience for Salt
development.  These include ``__opts__``, ``__context__``, ``__salt__``, and
others. This document will describe each dictionary and detail where they exist
and what information and/or functionality they provide.


__context__
-----------

``__context__`` exists in state modules and execution modules.

During a state run the ``__context__`` dictionary persists across all states
that are run and then is destroyed when the state ends.

When running an execution module ``__context__`` persists across all module
executions until the modules are refreshed; such as when ``saltutils.sync_all``
or ``state.highstate`` are executed.

A great place to see how to use ``__context__`` is in the cp.py module in
salt/modules/cp.py. The fileclient authenticates with the master when it is
instantiated and then is used to copy files to the minion. Rather than create a
new fileclient for each file that is to be copied down, one instance of the
fileclient is instantiated in the ``__context__`` dictionary and is reused for
each file. Here is an example from salt/modules/cp.py:

.. code-block:: python

    if not 'cp.fileclient' in __context__:
        __context__['cp.fileclient'] = salt.fileclient.get_file_client(__opts__)


.. note:: Because __context__ may or may not have been destroyed, always be
          sure to check for the existence of the key in __context__ and 
          generate the key before using it.
