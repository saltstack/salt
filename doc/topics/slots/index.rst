.. _slots-subsystem:

=====
Slots
=====

.. versionadded:: 2018.3.0
.. versionchanged:: 3000

.. note:: This functionality is under development and could be changed in the
    future releases

Many times it is useful to store the results of a command during the course of
an execution. Salt Slots are designed to allow you to store this information and
use it later during the :ref:`highstate <running-highstate>` or other job
execution.

Slots extend the state syntax and allows you to do things right before the
state function is executed. So you can make a decision in the last moment right
before a state is executed.

Execution functions
-------------------

.. note:: Using execution modules return data as a state values is a first step
    of Slots development. Other functionality is under development.

Slots allow you to use the return from a remote-execution function as an
argument value in states.

Slot syntax looks close to the simple python function call.

.. code-block:: text

    __slot__:salt:<module>.<function>(<args>, ..., <kwargs...>, ...)

For the 3000 release, this syntax has been updated to support parsing functions
which return dictionaries and for appending text to the slot result.

.. code-block:: text

    __slot__:salt:<module>.<function>(<args>..., <kwargs...>, ...).dictionary ~ append

There are some specifics in the syntax coming from the execution functions
nature and a desire to simplify the user experience. First one is that you
don't need to quote the strings passed to the slots functions. The second one
is that all arguments handled as strings.

Here is a simple example:

.. code-block:: yaml

    copy-some-file:
      file.copy:
        - name: __slot__:salt:test.echo(text=/tmp/some_file)
        - source: __slot__:salt:test.echo(/etc/hosts)

This will execute the :py:func:`test.echo <salt.modules.test.echo>` execution
functions right before calling the state. The functions in the example will
return `/tmp/some_file` and `/etc/hosts` strings that will be used as a target
and source arguments in the state function `file.copy`.

Here is an example of result parsing and appending:

.. code-block:: yaml

    file-in-user-home:
      file.copy:
        - name: __slot__:salt:user.info(someuser).home ~ /subdirectory
        - source: salt://somefile
