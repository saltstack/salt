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

Example Usage
-------------

In Salt, slots are a powerful feature that allows you to populate information
dynamically within your Salt states. One of the best use cases for slots is when
you need to reference data that is created or modified during the course of a
Salt run.

Consider the following example, where we aim to add a user named 'foobar' to a
group named 'known_users' with specific user and group IDs. To achieve this, we
utilize slots to retrieve the group ID of 'known_users' as it is created or
modified during the Salt run.

.. code-block:: yaml

    add_group_known_users:
      group.present:
        - name: known_users

    add_user:
      user.present:
        - name: foobar
        - uid: 600
        - gid: __slot__:salt:group.info("known_users").gid
        - require:
          - group: add_group_known_users

In this example, the ``add_group_known_users`` state ensures the presence of the
'known_users' group. Then, within the ``add_user`` state, we use the slot
``__slot__:salt:group.info("known_users").gid`` to dynamically retrieve the
group ID of 'known_users,' which may have been modified during the execution of
the previous state. This approach ensures that our user 'foobar' is associated
with the correct group, even if the group information changes during the Salt
run.

Slots offer a flexible way to work with changing data and dynamically populate
your Salt states, making your configurations adaptable and robust.

Execution module returns as file contents or data
-------------------------------------------------

The following examples demonstrate how to use execution module returns as file
contents or data in Salt states. These examples show how to incorporate the
output of execution functions into file contents or data in the `file.managed`
and `file.serialize` states.

Content from execution modules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use the results of execution modules directly as file contents in Salt
states. This can be useful for dynamically generating file content based on the
output of execution functions.

**Example 1: Using `test.echo` Output as File Content**

The following Salt state uses the `test.echo` execution function to generate the
text "hello world." This output is then used as the content of the file
`/tmp/things.txt`:

.. code-block:: yaml

    content-from-slots:
      file.managed:
        - name: /tmp/things.txt
        - contents: __slot__:salt:test.echo("hello world")

**Example 2: Using Multiple `test.echo` Outputs as Appended Content**

In this example, two `test.echo` execution functions are used to generate
"hello" and "world" strings. These strings are then joined by newline characters
and then used as the content of the file `/tmp/things.txt`:

.. code-block:: yaml

    content-from-multiple-slots:
      file.managed:
        - name: /tmp/things.txt
        - contents:
          - __slot__:salt:test.echo("hello")
          - __slot__:salt:test.echo("world")

Serializing data from execution modules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also serialize data obtained from execution modules and write it to
files using Salt states. This allows you to capture and store structured data
for later use.

**Example: Serializing `grains.items()` Output to JSON**

In this example, the `grains.items()` execution function retrieves system
information. The obtained data is then serialized into JSON format and saved to
the file `/tmp/grains.json`:

.. code-block:: yaml

    serialize-dataset-from-slots:
      file.serialize:
        - name: /tmp/grains.json
        - serializer: json
        - dataset: __slot__:salt:grains.items()

These examples showcase how to leverage Salt's flexibility to use execution
module returns as file contents or serialized data in your Salt states, allowing
for dynamic and customized configurations.
