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

Runnable example
----------------

The following SLS is fully runnable on any minion. It uses ``test.echo`` to
return a string and ``grains.get`` to return a value from grains, then uses the
returned values as state arguments. Because slot evaluation happens just before
the state function is called, the values are resolved at run time rather than
compile time.

.. code-block:: yaml

    # /srv/salt/slots-example.sls

    write-os-marker:
      file.managed:
        - name: __slot__:salt:test.echo(/tmp/os_marker)
        - contents: __slot__:salt:grains.get(os) ~ "\n"
        - makedirs: True

Applying ``state.apply slots-example`` writes ``/tmp/os_marker`` containing the
value of the ``os`` grain followed by a newline. The same SLS works on every
minion regardless of the grain value because the slot is resolved per minion.

Result parsing with ``.dictionary``
-----------------------------------

When the called execution function returns a dictionary, append
``.<key>`` to drill into the result. Nested keys can be chained with ``.``:

.. code-block:: yaml

    write-home-marker:
      file.managed:
        - name: __slot__:salt:user.info(root).home ~ "/marker"
        - contents: managed by salt
        - makedirs: True

In this example ``user.info`` returns a dictionary and the slot resolves to the
value of the ``home`` key, with the literal string ``/marker`` appended via the
``~`` operator.

Limitations
-----------

* Only execution module functions are supported. The slot syntax must start with
  ``__slot__:salt:``.
* Arguments are not quoted and are always treated as strings. To pass a literal
  value containing commas or parentheses, use a keyword argument instead.
* If the function call cannot be parsed or the function name is unknown, the
  literal slot string is preserved unchanged and a warning is logged.
* If the parsed return is not a string, attempting to append text via ``~`` is
  ignored and an error is logged.
