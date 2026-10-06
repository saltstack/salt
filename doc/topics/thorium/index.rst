.. _thorium-reactor:

=======================
Thorium Complex Reactor
=======================

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
using the ``thorium_roots`` setting in the ``master`` configuration file.

This would explicitly set the roots to the default:

.. code-block:: yaml

    thorium_roots:
      base:
        - /srv/thorium

Example ``thorium_roots`` configuration:

.. code-block:: yaml

    thorium_roots:
      base:
        - /etc/salt/thorium

It is also possible to use gitfs with Thorium,
using the ``thoriumenv`` or ``thorium_top`` settings.

Example using ``thorium_top``:

.. code-block:: yaml

    thorium_top: salt://thorium/top.sls
    gitfs_provider: pygit2

    gitfs_remotes:
      - git@github.com:user/repo.git:
        - name: salt-backend
        - root: salt
        - base: master
      - git@github.com:user/repo.git:
        - name: thorium-backend
        - root: thorium
        - base: master
        - mountpoint: salt://thorium

.. note::

    When using this method don't forget to prepend the mountpoint to files served by this repo,
    for example ``top.sls``:

    .. code-block:: yaml

        base:
          '*':
            - thorium.key_clean

Example using ``thoriumenv``:

.. code-block:: yaml

    thoriumenv: thorium
    gitfs_provider: pygit2

    gitfs_remotes:
      - git@github.com:user/repo.git:
        - name: salt-backend
        - root: salt
        - base: master
      - git@github.com:user/repo.git:
        - name: thorium-backend
        - root: thorium
        - saltenv:
          - thorium:
            - ref: master

.. note::

    When using this method all state will run under the defined environment,
    for example ``top.sls``:

    .. code-block:: yaml

        thorium:
          '*':
            - key_clean

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

    statreg:
      status.reg

    keydel:
      key.timeout:
        - delete: 60
        - require:
          - status: statreg

There are two stanzas in this formula, whose IDs are ``statreg`` and
``keydel``. The first stanza, ``statreg``, tells Thorium to keep track of
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
in the ``statreg`` codeblock has been successfully called first.


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
register. This works especially well with ``reg.set``, which stores scalar
values in a ``set()``:

.. code-block:: yaml

    foo:
      reg.set:
        - add: bar
        - match: my/custom/event
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

When you are working with a ``list`` register, the ``len_*`` functions are
often more useful than the scalar comparisons:

* ``len_gt``: Check whether the register contains more than the given number of entries
* ``len_gte``: Check whether the register contains at least the given number of entries
* ``len_lt``: Check whether the register contains fewer than the given number of entries
* ``len_lte``: Check whether the register contains at most the given number of entries
* ``len_eq``: Check whether the register contains exactly the given number of entries
* ``len_ne``: Check whether the register contains anything other than the given number of entries

There is also a function called ``check.event`` which does not examine the
register. Instead, it looks directly at an event as it is coming in on the
event bus, and returns ``True`` if that event's tag matches. For example:

.. code-block:: yaml

        salt/foo/*/bar:
          check.event

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.version
            - require:
              - check: salt/foo/*/bar

This formula will look for an event whose tag is ``salt/foo/<anything>/bar`` and
if it comes in, issue a ``test.version`` to all minions.


Register Persistence
--------------------
It is possible to persist the register data to disk when a master is stopped
gracefully, and reload it from disk when the master starts up again. This
functionality is provided by the returner subsystem, and is enabled whenever
any returner containing a ``load_reg`` and a ``save_reg`` function is used.

The built-in ``local_cache`` returner implements these hooks, so a simple way
to persist the register is:

.. code-block:: yaml

    register_returner: local_cache


Concrete Thorium Patterns
=========================
The API reference explains each Thorium module in isolation, but Thorium
becomes much easier to understand when you think in terms of small pipelines:

#. collect interesting events into a register
#. evaluate that register or the current event batch
#. trigger a local, runner, or wheel action

The examples below are designed to show those patterns directly.


Trigger After Several Matching Events
-------------------------------------
One of Thorium's most useful patterns is reacting only after several related
events have occurred. This avoids reacting to every transient event
individually.

The following example stores the most recent deployment failures in a register
and only fires once at least three failures have been seen:

.. code-block:: yaml

    deploy_failures:
      reg.list:
        - add:
          - id
          - reason
        - match: acme/deploy/failed
        - stamp: True
        - prune: 10

    enough_failures:
      check.len_gte:
        - name: deploy_failures
        - value: 3

    notify_ops:
      runner.cmd:
        - func: manage.up
        - require:
          - check: enough_failures

Thorium is doing three different jobs here:

* ``reg.list`` collects the event payload fields you care about.
* ``check.len_gte`` turns that historical context into a gate.
* ``runner.cmd`` hands off to a master-side runner only when the gate is open.

This is the general shape you want whenever you need "do something after N
events", "act on bursts", or "only react if the issue keeps happening".


Compute a Rolling Average Before Acting
---------------------------------------
Thorium is not limited to one-off event matching. The combination of
``reg.list`` and ``calc.*`` can treat recent events as a sliding data set.

The following example stores load samples from custom events and only triggers
an orchestration run when the mean of the last five samples is at least ``4``:

.. code-block:: yaml

    load_samples:
      reg.list:
        - add:
          - load
          - minion
        - match: acme/telemetry/load
        - stamp: True
        - prune: 20

    sustained_high_load:
      calc.mean:
        - name: load_samples
        - num: 5
        - ref: load
        - minimum: 4

    scale_out:
      runner.cmd:
        - func: state.orchestrate
        - mods: orch.scale_out
        - require:
          - calc: sustained_high_load

This pattern is useful when you want to react to trends instead of single
samples. The register keeps the recent window, and ``calc.mean`` computes the
decision value at runtime.


Throttle Reactions With ``timer.hold``
--------------------------------------
Once a check starts returning ``True``, it will continue to do so until the
register changes. In practice you often want a cooldown so that the same action
is not launched on every Thorium loop.

``timer.hold`` provides that flow-control primitive:

.. code-block:: yaml

    service_failures:
      reg.list:
        - add:
          - id
          - service
        - match: acme/service/down
        - prune: 20

    repeated_failures:
      check.len_gte:
        - name: service_failures
        - value: 3

    cooldown:
      timer.hold:
        - seconds: 900
        - require:
          - check: repeated_failures

    restart_service:
      local.cmd:
        - tgt: 'G@roles:web'
        - tgt_type: compound
        - func: service.restart
        - arg:
          - nginx
        - require:
          - timer: cooldown

The timer state remains ``False`` until the hold period has elapsed, and then
briefly returns ``True`` so the dependent action can run. This makes it a good
fit for rate limiting, cooldowns, and periodic rechecks.


Choose The Right Action Wrapper
-------------------------------
Thorium can react in three different places, and the right choice depends on
where the work needs to happen:

* ``local.cmd`` runs an execution module on one or more minions.
* ``runner.cmd`` launches a runner on the master.
* ``wheel.cmd`` launches a wheel command for master maintenance tasks.

These wrappers all fit naturally behind the same gate:

.. code-block:: yaml

    important_event:
      check.event

    verify_minions:
      local.cmd:
        - name: verify_minions
        - tgt: '*'
        - func: test.ping
        - require:
          - check: important_event

    orchestrate_response:
      runner.cmd:
        - func: state.orchestrate
        - mods: orch.respond
        - require:
          - check: important_event

    reject_old_key:
      wheel.cmd:
        - fun: key.reject
        - match: legacy-minion
        - require:
          - check: important_event

If the reaction is "do something on minions", use ``local.cmd``. If the
reaction is "start a master-side workflow", use ``runner.cmd``. If the
reaction is "modify master metadata or PKI state", use ``wheel.cmd``.


Inspect And Persist The Register
--------------------------------
Thorium is much easier to debug when you can inspect the register directly.
This is especially helpful when you are first developing a formula.

The following example saves a register snapshot to disk every time it changes:

.. code-block:: yaml

    tracked_ids:
      reg.set:
        - add: id
        - match: acme/custom/event

    tracked_ids_snapshot:
      file.save:
        - name: /tmp/tracked_ids.json
        - filter: True
        - require:
          - reg: tracked_ids

``filter: True`` is important when the register contains types such as
``set()`` that are not JSON-serializable by default.

This pattern is useful for:

* confirming that your event tag glob is matching what you expect
* inspecting the exact register shape before adding checks or calculations
* keeping a lightweight audit trail during Thorium development


Expanded Health Automation Example
----------------------------------
The built-in ``status`` and ``key`` modules are often the first place people
encounter Thorium, but they are also a good example of multi-step automation.

The following formula tracks status beacon events, snapshots the status
register, and rejects keys for minions that have not checked in recently:

.. code-block:: yaml

    status_register:
      status.reg

    status_snapshot:
      file.save:
        - name: status_snapshot
        - require:
          - status: status_register

    reject_stale_keys:
      key.timeout:
        - reject: 300
        - require:
          - status: status_register

``status.reg`` listens for ``salt/beacon/*/status/*`` events and stores the
latest payload and receive time for each minion. ``key.timeout`` then compares
those timestamps to the current accepted key list and deletes or rejects keys
that have gone silent.

This pattern shows that Thorium is more than an event trigger. It can maintain
state across many events, compare that state to master data, and then take a
master-side action when the aggregate picture warrants it.
