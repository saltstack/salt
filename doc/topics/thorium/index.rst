.. _thorium-reactor:

=======================
Thorium Complex Reactor
=======================

.. note::

    Thorium is a provisional feature of Salt and is subject to change
    and removal if the feature proves to not be a viable solution.

.. note::

    Thorium was added to Salt as an experimental feature in the 2016.3.0
    release, as of 2016.3.0 this feature is considered experimental, no
    guarantees are made for support of any kind yet.


The original Salt Reactor is based on the idea of listening for a specific
event and then reacting to it. This model comes with many logical limitations,
for instance it is very difficult (and hacky) to fire a reaction based on
aggregate data or based on multiple events.

The Thorium reactor is intended to alleviate this problem in a very elegant way.
Instead of using extensive jinja routines or complex python sls files the
aggregation of data and the determination of what should run becomes isolated
to the sls data logic, makes the definitions much cleaner.


Starting the Thorium Engine
===========================

To enable the thorium engine add the following configuration to the engines
section of your Salt Master or Minion configuration file and restart the daemon:

.. code-block:: yaml

    engines:
      - thorium: {}


Thorium Modules
===============
Because of its specialized nature, Thorium uses its own set of modules. However,
many of these modules are designed to wrap the more commonly-used Salt
subsystems. These modules are:

* local: Execution modules
* runner: Runner modules
* wheel: Wheel modules

There are other modules that ship with Thorium as well. Some of these will be
highlighted later in this document.


Writing Thorium Formulas
========================
Like some other Salt subsystems, Thorium uses its own directory structure. The
default location for this structure is ``/srv/thorium/``, but it can be changed
using the ``thorium_roots_dir`` setting in the ``master`` configuration file.


The Thorium top.sls File
------------------------
Thorium uses its own ``top.sls`` file, which follows the same convention as is
found in ``/srv/salt/``:

.. code-block:: yaml

    <srv>:
      <target>:
        - <formula 1>
        - <formula 2>
        - <etc...>

For instance, a ``top.sls`` using a standard ``base`` environment and a single
Thorium formula called ``key_clean``, would look like:

.. code-block:: yaml

    base:
      '*':
        - key_clean

Take note that the target in a Thorium ``top.sls`` is not used; it only exists
to follow the same convention as other ``top.sls`` files. Leave this set to
``'*'`` in your own Thorium ``top.sls``.

Thorium Formula Files
---------------------
Thorium SLS files are processed by the same state compiler that processes Salt
state files. This means that features like requisites, templates, and so on are
available.

Let's take a look at an example, and then discuss each component of it. This
formula uses Thorium to detect when a minion has disappeared and then deletes
the key from the master when the minion has been gone for 60 seconds:

.. code-block:: yaml

    startreg:
      status.reg

    keydel:
      key.timeout:
        - delete: 60
        - require:
          - status: startreg

There are two stanzas in this formula, whose IDs are ``startreg`` and
``keydel``. The first stanza, ``startreg``, tells Thorium to keep track of
minion status beacons in its *register*. We'll talk more about the register in
a moment.

The second stanza, ``keydel``, is the one that does the real work. It uses the
``key`` module to apply an expiration (using the ``timeout`` function) to a
minion. Because ``delete`` is set to ``60``, this is a 60 second expiration. If
a minion does not check in at least once every 60 seconds, its key will be
deleted from the master. This particular function also allows you to use
``reject`` instead of ``delete``, allowing for a minion to be rejected instead
of deleted if it does not check in within the specified time period.

There is also a ``require`` requisite in this stanza. It states that the
``key.timeout`` function will not be called unless the ``status.reg`` function
in the ``startreg`` codeblock has been successfully called first.


Thorium Links to Beacons
------------------------
The above example was added in the 2016.11.0 release of Salt and makes use of the
``status`` beacon also added in the 2016.11.0 release. For the above Thorium state
to function properly you will also need to enable the ``status`` beacon in the
``minion`` configuration file:

.. code-block:: yaml

    beacons:
      status:
        - interval: 10

This will cause the minion to use the status beacon to check in with the master
every 10 seconds.


The Thorium Register
====================
In order to keep track of information, Thorium uses an in-memory register (or
rather, collection of registers) on the master. These registers are only
populated when told to by a formula, and they normally will be erased when the
master is restarted. It is possible to persist the registers to disk, but we'll
get to that in a moment.

The example above uses ``status.reg`` to populate a register for you, which is
automatically used by the ``key.timeout`` function. However, you can set your
own register values as well, using the ``reg`` module.

Because Thorium watches the event bus, the ``reg`` module is designed to look
for user-specified tags, and then extract data from the payload of events that
match those tags. For instance, the following stanza will look for an event
with a tag of ``my/custom/event``:

.. code-block:: yaml

    foo:
      reg.list:
        - add: bar
        - match: my/custom/event

When such an event is found, the data found in the payload dictionary key of
``bar`` will be stored in a register called ``foo``. This register will store
that data in a ``list``. You may also use ``reg.set`` to add data to a ``set()``
instead.

If you would like to see a copy of the register as it is stored in memory, you
can use the ``file.save`` function:

.. code-block:: yaml

    myreg:
      file.save

In this case, each time the register is updated, a copy will be saved in JSON
format at ``/var/cache/salt/master/thorium/saves/myreg``. If you would like to
see when particular events are added to a list-type register, you may add a
``stamp`` option to ``reg.list`` (but not ``reg.set``). With the above two
stanzas put together, this would look like:

.. code-block:: yaml

    foo:
      reg.list:
        - add: bar
        - match: my/custom/event
        - stamp: True

    myreg:
      file.save

If you would like to only keep a certain number of the most recent register
entries, you may also add a ``prune`` option to ``reg.list`` (but not
``reg.set``):

.. code-block:: yaml

    foo:
      reg.list:
        - add: bar
        - match: my/custom/event
        - stamp: True
        - prune: 50

This example will only keep the 50 most recent entries in the ``foo`` register.

Using Register Data
-------------------
Putting data in a register is useless if you don't do anything with it. The
``check`` module is designed to examine register data and determine whether it
matches the given parameters. For instance, the ``check.contains`` function
will return ``True`` if the given ``value`` is contained in the specified
register:

.. code-block:: yaml

    foo:
      reg.list:
        - add: bar
        - match: my/custom/event
        - stamp: True
        - prune: 50
      check.contains:
        - value: somedata

Used with a ``require`` requisite, we can call one of the wrapper modules and
perform an operation. For example:

.. code-block:: yaml

    shell_test:
      local.cmd:
        - tgt: dufresne
        - func: cmd.run
        - arg:
          - echo 'thorium success' > /tmp/thorium.txt
        - require:
          - check: foo

This stanza will only run if the ``check.contains`` function under the ``foo``
ID returns true (meaning the match was found).

There are a number of other functions in the ``check`` module which use
different means of comparing values:

* ``gt``: Check whether the register entry is greater than the given value
* ``gte``: Check whether the register entry is greater than or equal to the given value
* ``lt``: Check whether the register entry is less than the given value
* ``lte``: Check whether the register entry is less than or equal to the given value
* ``eq``: Check whether the register entry is equal to the given value
* ``ne``: Check whether the register entry is not equal to the given value

There is also a function called ``check.event`` which does not examine the
register. Instead, it looks directly at an event as it is coming in on the
event bus, and returns ``True`` if that event's tag matches. For example:

.. code-block:: yaml

        salt/foo/*/bar:
          check.event

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: salt/foo/*/bar

This formula will look for an event whose tag is ``salt/foo/<anything>/bar`` and
if it comes in, issue a ``test.ping`` to all minions.


Register Persistence
--------------------
It is possible to persist the register data to disk when a master is stopped
gracefully, and reload it from disk when the master starts up again. This
functionality is provided by the returner subsystem, and is enabled whenever
any returner containing a ``load_reg`` and a ``save_reg`` function is used.
