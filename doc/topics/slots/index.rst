.. _slots-subsystem:

=====
Slots
=====

.. versionadded:: Oxygen

.. note:: This functionality is under development and could be changed in the
    future releases

Many times it is useful to store the results of a command during the course of
an execution. Salt Slots is designed to allow to store this information and use
it later during the highstate or other job execution.

Slots extends the state syntax and allows to do things right before the state
function be executed. So you can make a decision in the last moment right before
a state is executed.

Execution functions
-------------------

.. note:: Using execution modules return data as a state values is a first step
    of Slots development. Other functionality is under development.

Slots allow to use minion execution module return as an argument value in
states.

Slot syntax looks close to the simple python function call.

.. code-block::

    __slot__:salt:<module>.<function>(<args>, ..., <kwargs...>, ...)


Simple example is here:

.. code-block:: yaml

    copy-some-file:
      file.copy:
        - name: __slot__:salt:test.echo(text=/tmp/some_file)
        - source: __slot__:salt:test.echo(/etc/hosts)

This will execute the `test.echo` execution functions right before calling the
state. The functions in the example will return `/tmp/some_file` and
`/etc/hosts` strings that will be used as a target and source arguments in the
state function `file.copy`.
