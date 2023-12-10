.. _return-codes:

============
Return Codes
============

When the ``salt`` or ``salt-call`` CLI commands result in an error, the command
will exit with a return code of **1**. Error cases consist of the following:

1. Errors are encountered while running :ref:`States
   <configuration-management>`, or any state returns a ``False`` result

2. Any exception is raised

3. In the case of remote-execution functions, when the return data is a
   :ref:`Python dictionary <typesmapping>` with a key named either ``result``
   or ``success``, which has a value of ``False``

Retcode Passthrough
===================

In addition to the cases listed above, if a state or remote-execution function
sets a nonzero value in the ``retcode`` key of the :ref:`__context__
<dunder-context>` dictionary, the command will exit with a return code of
**1**. For those developing custom states and execution modules, using
``__context__['retcode']`` can be a useful way of signaling that an error has
occurred:

.. code-block:: python

    if something_went_wrong:
        __context__["retcode"] = 42

This is actually how states signal that they have failed. Different cases
result in different codes being set in the :ref:`__context__ <dunder-context>`
dictionary:

- **1** is set when any error is encountered in the state compiler (missing SLS
  file, etc.)

- **2** is set when any state returns a ``False`` result

- **5** is set when Pillar data fails to be compiled before running the
  state(s)

When the ``--retcode-passthrough`` flag is used with ``salt-call``, then
``salt-call`` will exit with whichever retcode was set in the :ref:`__context__
<dunder-context>` dictionary, rather than the default behavior which simply
exits with **1** for any error condition.
