.. _reactor:

.. index:: ! Reactor, Salt Reactor
    seealso: Event; Reactor

==============
Reactor System
==============

Salt's Reactor system gives Salt the ability to trigger actions in response to
an event. It is a simple interface to watching Salt's event bus for event tags
that match a given pattern and then running one or more commands in response.

This system binds sls files to event tags on the master. These sls files then
define reactions. This means that the reactor system has two parts. First, the
reactor option needs to be set in the master configuration file.  The reactor
option allows for event tags to be associated with sls reaction files. Second,
these reaction files use highdata (like the state system) to define reactions
to be executed.

Event System
============

A basic understanding of the event system is required to understand reactors.
The event system is a local ZeroMQ PUB interface which fires salt events. This
event bus is an open system used for sending information notifying Salt and
other systems about operations.

The event system fires events with a very specific criteria. Every event has a
**tag**. Event tags allow for fast top-level filtering of events. In addition
to the tag, each event has a data structure. This data structure is a
dictionary, which contains information about the event.

.. _reactor-mapping-events:

Mapping Events to Reactor SLS Files
===================================

Reactor SLS files and event tags are associated in the master config file.
By default this is /etc/salt/master, or /etc/salt/master.d/reactor.conf.

.. versionadded:: 2014.7.0
    Added Reactor support for ``salt://`` file paths.

In the master config section 'reactor:' is a list of event tags to be matched
and each event tag has a list of reactor SLS files to be run.

.. code-block:: yaml

    reactor:                            # Master config section "reactor"

      - 'salt/minion/*/start':          # Match tag "salt/minion/*/start"
        - /srv/reactor/start.sls        # Things to do when a minion starts
        - /srv/reactor/monitor.sls      # Other things to do

      - 'salt/cloud/*/destroyed':       # Globs can be used to match tags
        - /srv/reactor/destroy/*.sls    # Globs can be used to match file names

      - 'myco/custom/event/tag':        # React to custom event tags
        - salt://reactor/mycustom.sls   # Reactor files can come from the salt fileserver

.. note::
    In the above example, ``salt://reactor/mycustom.sls`` refers to the
    ``base`` environment. To pull this file from a different environment, use
    the :ref:`querystring syntax <querystring-syntax>` (e.g.
    ``salt://reactor/mycustom.sls?saltenv=reactor``).

Reactor SLS files are similar to State and Pillar SLS files. They are by
default YAML + Jinja templates and are passed familiar context variables.
Click :ref:`here <reactor-jinja-context>` for more detailed information on the
variables available in Jinja templating.

Here is the SLS for a simple reaction:

.. code-block:: jinja

    {% if data['id'] == 'mysql1' %}
    highstate_run:
      local.state.apply:
        - tgt: mysql1
    {% endif %}

This simple reactor file uses Jinja to further refine the reaction to be made.
If the ``id`` in the event data is ``mysql1`` (in other words, if the name of
the minion is ``mysql1``) then the following reaction is defined.  The same
data structure and compiler used for the state system is used for the reactor
system. The only difference is that the data is matched up to the salt command
API and the runner system.  In this example, a command is published to the
``mysql1`` minion with a function of :py:func:`state.apply
<salt.modules.state.apply_>`, which performs a :ref:`highstate
<running-highstate>`. Similarly, a runner can be called:

.. code-block:: jinja

    {% if data['data']['custom_var'] == 'runit' %}
    call_runit_orch:
      runner.state.orchestrate:
        - args:
          - mods: orchestrate.runit
    {% endif %}

This example will execute the state.orchestrate runner and initiate an execution
of the ``runit`` orchestrator located at ``/srv/salt/orchestrate/runit.sls``.

Types of Reactions
==================

==============================  ==================================================================================
Name                            Description
==============================  ==================================================================================
:ref:`local <reactor-local>`    Runs a :ref:`remote-execution function <all-salt.modules>` on targeted minions
:ref:`runner <reactor-runner>`  Executes a :ref:`runner function <all-salt.runners>`
:ref:`wheel <reactor-wheel>`    Executes a :ref:`wheel function <all-salt.wheel>` on the master
:ref:`caller <reactor-caller>`  Runs a :ref:`remote-execution function <all-salt.modules>` on a masterless minion
==============================  ==================================================================================

.. note::
    The ``local`` and ``caller`` reaction types will likely be renamed in a
    future release. These reaction types were named after Salt's internal
    client interfaces, and are not intuitively named. Both ``local`` and
    ``caller`` will continue to work in Reactor SLS files, however.

Where to Put Reactor SLS Files
==============================

Reactor SLS files can come both from files local to the master, and from any of
backends enabled via the :conf_master:`fileserver_backend` config option. Files
placed in the Salt fileserver can be referenced using a ``salt://`` URL, just
like they can in State SLS files.

It is recommended to place reactor and orchestrator SLS files in their own
uniquely-named subdirectories such as ``orch/``, ``orchestrate/``, ``react/``,
``reactor/``, etc., to keep them organized.

.. _reactor-sls:

Writing Reactor SLS
===================

The different reaction types were developed separately and have historically
had different methods for passing arguments. For the 2017.7.2 release a new,
unified configuration schema has been introduced, which applies to all reaction
types.

The old config schema will continue to be supported, and there is no plan to
deprecate it at this time.

.. _reactor-local:

Local Reactions
---------------

A ``local`` reaction runs a :ref:`remote-execution function <all-salt.modules>`
on the targeted minions.

The old config schema required the positional and keyword arguments to be
manually separated by the user under ``arg`` and ``kwarg`` parameters. However,
this is not very user-friendly, as it forces the user to distinguish which type
of argument is which, and make sure that positional arguments are ordered
properly. Therefore, the new config schema is recommended if the master is
running a supported release.

The below two examples are equivalent:

+---------------------------------+-----------------------------+
| Supported in 2017.7.2 and later | Supported in all releases   |
+=================================+=============================+
| ::                              | ::                          |
|                                 |                             |
|   install_zsh:                  |   install_zsh:              |
|     local.state.single:         |     local.state.single:     |
|       - tgt: 'kernel:Linux'     |       - tgt: 'kernel:Linux' |
|       - tgt_type: grain         |       - tgt_type: grain     |
|       - args:                   |       - arg:                |
|         - fun: pkg.installed    |         - pkg.installed     |
|         - name: zsh             |         - zsh               |
|         - fromrepo: updates     |       - kwarg:              |
|                                 |           fromrepo: updates |
+---------------------------------+-----------------------------+

This reaction would be equivalent to running the following Salt command:

.. code-block:: bash

    salt -G 'kernel:Linux' state.single pkg.installed name=zsh fromrepo=updates

.. note::
    Any other parameters in the :py:meth:`LocalClient().cmd_async()
    <salt.client.LocalClient.cmd_async>` method can be passed at the same
    indentation level as ``tgt``.

.. note::
    ``tgt_type`` is only required when the target expression defined in ``tgt``
    uses a :ref:`target type <targeting>` other than a minion ID glob.

    The ``tgt_type`` argument was named ``expr_form`` in releases prior to
    2017.7.0.

.. _reactor-runner:

Runner Reactions
----------------

Runner reactions execute :ref:`runner functions <all-salt.runners>` locally on
the master.

The old config schema called for passing arguments to the reaction directly
under the name of the runner function. However, this can cause unpredictable
interactions with the Reactor system's internal arguments. It is also possible
to pass positional and keyword arguments under ``arg`` and ``kwarg`` like above
in :ref:`local reactions <reactor-local>`, but as noted above this is not very
user-friendly. Therefore, the new config schema is recommended if the master
is running a supported release.

.. note::
  State ids of reactors for runners and wheels should all be unique. They can
  overwrite each other when added to the async queue causing lost reactions.

The below two examples are equivalent:

+-------------------------------------------------+-------------------------------------------------+
| Supported in 2017.7.2 and later                 | Supported in all releases                       |
+=================================================+=================================================+
| ::                                              | ::                                              |
|                                                 |                                                 |
|   deploy_app:                                   |   deploy_app:                                   |
|     runner.state.orchestrate:                   |     runner.state.orchestrate:                   |
|       - args:                                   |       - mods: orchestrate.deploy_app            |
|         - mods: orchestrate.deploy_app          |       - kwarg:                                  |
|         - pillar:                               |           pillar:                               |
|             event_tag: {{ tag }}                |             event_tag: {{ tag }}                |
|             event_data: {{ data['data']|json }} |             event_data: {{ data['data']|json }} |
+-------------------------------------------------+-------------------------------------------------+

Assuming that the event tag is ``foo``, and the data passed to the event is
``{'bar': 'baz'}``, then this reaction is equivalent to running the following
Salt command:

.. code-block:: bash

    salt-run state.orchestrate mods=orchestrate.deploy_app pillar='{"event_tag": "foo", "event_data": {"bar": "baz"}}'

.. _reactor-wheel:

Wheel Reactions
---------------

Wheel reactions run :ref:`wheel functions <all-salt.wheel>` locally on the
master.

Like :ref:`runner reactions <reactor-runner>`, the old config schema called for
wheel reactions to have arguments passed directly under the name of the
:ref:`wheel function <all-salt.wheel>` (or in ``arg`` or ``kwarg`` parameters).

.. note::
  State ids of reactors for runners and wheels should all be unique. They can
  overwrite each other when added to the async queue causing lost reactions.

The below two examples are equivalent:

+-----------------------------------+---------------------------------+
| Supported in 2017.7.2 and later   | Supported in all releases       |
+===================================+=================================+
| ::                                | ::                              |
|                                   |                                 |
|   remove_key:                     |   remove_key:                   |
|     wheel.key.delete:             |     wheel.key.delete:           |
|       - args:                     |       - match: {{ data['id'] }} |
|         - match: {{ data['id'] }} |                                 |
+-----------------------------------+---------------------------------+

.. _reactor-caller:

Caller Reactions
----------------

Caller reactions run :ref:`remote-execution functions <all-salt.modules>` on a
minion daemon's Reactor system. To run a Reactor on the minion, it is necessary
to configure the :mod:`Reactor Engine <salt.engines.reactor>` in the minion
config file, and then setup your watched events in a ``reactor`` section in the
minion config file as well.

.. note:: Masterless Minions use this Reactor

    This is the only way to run the Reactor if you use masterless minions.

Both the old and new config schemas involve passing arguments under an ``args``
parameter. However, the old config schema only supports positional arguments.
Therefore, the new config schema is recommended if the masterless minion is
running a supported release.

The below two examples are equivalent:

+---------------------------------+---------------------------+
| Supported in 2017.7.2 and later | Supported in all releases |
+=================================+===========================+
| ::                              | ::                        |
|                                 |                           |
|   touch_file:                   |   touch_file:             |
|     caller.file.touch:          |     caller.file.touch:    |
|       - args:                   |       - args:             |
|         - name: /tmp/foo        |         - /tmp/foo        |
+---------------------------------+---------------------------+

This reaction is equivalent to running the following Salt command:

.. code-block:: bash

    salt-call file.touch name=/tmp/foo

Best Practices for Writing Reactor SLS Files
============================================

The Reactor works as follows:

1. The Salt Reactor watches Salt's event bus for new events.
2. Each event's tag is matched against the list of event tags configured under
   the :conf_master:`reactor` section in the Salt Master config.
3. The SLS files for any matches are rendered into a data structure that
   represents one or more function calls.
4. That data structure is given to a pool of worker threads for execution.

Matching and rendering Reactor SLS files is done sequentially in a single
process. For that reason, reactor SLS files should contain few individual
reactions (one, if at all possible). Also, keep in mind that reactions are
fired asynchronously (with the exception of :ref:`caller <reactor-caller>`) and
do *not* support :ref:`requisites <requisites>`.

Complex Jinja templating that calls out to slow :ref:`remote-execution
<all-salt.modules>` or :ref:`runner <all-salt.runners>` functions slows down
the rendering and causes other reactions to pile up behind the current one. The
worker pool is designed to handle complex and long-running processes like
:ref:`orchestration <orchestrate-runner>` jobs.

Therefore, when complex tasks are in order, :ref:`orchestration
<orchestrate-runner>` is a natural fit. Orchestration SLS files can be more
complex, and use requisites. Performing a complex task using orchestration lets
the Reactor system fire off the orchestration job and proceed with processing
other reactions.

.. _reactor-jinja-context:

Jinja Context
=============

Reactor SLS files only have access to a minimal Jinja context. ``grains`` and
``pillar`` are *not* available. The ``salt`` object is available for calling
:ref:`remote-execution <all-salt.modules>` or :ref:`runner <all-salt.runners>`
functions, but it should be used sparingly and only for quick tasks for the
reasons mentioned above.

In addition to the ``salt`` object, the following variables are available in
the Jinja context:

- ``tag`` - the tag from the event that triggered execution of the Reactor SLS
  file
- ``data`` - the event's data dictionary

The ``data`` dict will contain an ``id`` key containing the minion ID, if the
event was fired from a minion, and a ``data`` key containing the data passed to
the event.

Advanced State System Capabilities
==================================

Reactor SLS files, by design, do not support :ref:`requisites <requisites>`,
ordering, ``onlyif``/``unless`` conditionals and most other powerful constructs
from Salt's State system.

Complex Master-side operations are best performed by Salt's Orchestrate system
so using the Reactor to kick off an Orchestrate run is a very common pairing.

For example:

.. code-block:: jinja

    # /etc/salt/master.d/reactor.conf
    # A custom event containing: {"foo": "Foo!", "bar: "bar*", "baz": "Baz!"}
    reactor:
      - my/custom/event:
        - /srv/reactor/some_event.sls

.. code-block:: jinja

    # /srv/reactor/some_event.sls
    invoke_orchestrate_file:
      runner.state.orchestrate:
        - args:
            - mods: orchestrate.do_complex_thing
            - pillar:
                event_tag: {{ tag }}
                event_data: {{ data|json }}

.. code-block:: jinja

    # /srv/salt/orchestrate/do_complex_thing.sls
    {% set tag = salt['pillar.get']('event_tag') %}
    {% set data = salt['pillar.get']('event_data') %}

    # Pass data from the event to a custom runner function.
    # The function expects a 'foo' argument.
    do_first_thing:
      salt.runner:
        - name: custom_runner.custom_function
        - foo: {{ data.foo }}

    # Wait for the runner to finish then send an execution to minions.
    # Forward some data from the event down to the minion's state run.
    do_second_thing:
      salt.state:
        - tgt: {{ data.bar }}
        - sls:
          - do_thing_on_minion
        - kwarg:
            pillar:
              baz: {{ data.baz }}
        - require:
          - salt: do_first_thing

.. _beacons-and-reactors:

Beacons and Reactors
====================

An event initiated by a beacon, when it arrives at the master will be wrapped
inside a second event, such that the data object containing the beacon
information will be ``data['data']``, rather than ``data``.

For example, to access the ``id`` field of the beacon event in a reactor file,
you will need to reference ``{{ data['data']['id'] }}`` rather than ``{{
data['id'] }}`` as for events initiated directly on the event bus.

Similarly, the data dictionary attached to the event would be located in
``{{ data['data']['data'] }}`` instead of ``{{ data['data'] }}``.

See the :ref:`beacon documentation <beacon-example>` for examples.

Manually Firing an Event
========================

From the Master
---------------

Use the :py:func:`event.send <salt.runners.event.send>` runner:

.. code-block:: bash

    salt-run event.send foo '{orchestrate: refresh}'

From the Minion
---------------

To fire an event to the master from a minion, call :py:func:`event.send
<salt.modules.event.send>`:

.. code-block:: bash

    salt-call event.send foo '{orchestrate: refresh}'

To fire an event to the minion's local event bus, call :py:func:`event.fire
<salt.modules.event.fire>`:

.. code-block:: bash

    salt-call event.fire '{orchestrate: refresh}' foo

Referencing Data Passed in Events
---------------------------------

Assuming any of the above examples, any reactor SLS files triggered by watching
the event tag ``foo`` will execute with ``{{ data['data']['orchestrate'] }}``
equal to ``'refresh'``.

Getting Information About Events
================================

The best way to see exactly what events have been fired and what data is
available in each event is to use the :py:func:`state.event runner
<salt.runners.state.event>`.

.. seealso:: :ref:`Common Salt Events <event-master_events>`

Example usage:

.. code-block:: bash

    salt-run state.event pretty=True

Example output:

.. code-block:: text

    salt/job/20150213001905721678/new       {
        "_stamp": "2015-02-13T00:19:05.724583",
        "arg": [],
        "fun": "test.ping",
        "jid": "20150213001905721678",
        "minions": [
            "jerry"
        ],
        "tgt": "*",
        "tgt_type": "glob",
        "user": "root"
    }
    salt/job/20150213001910749506/ret/jerry {
        "_stamp": "2015-02-13T00:19:11.136730",
        "cmd": "_return",
        "fun": "saltutil.find_job",
        "fun_args": [
            "20150213001905721678"
        ],
        "id": "jerry",
        "jid": "20150213001910749506",
        "retcode": 0,
        "return": {},
        "success": true
    }

Debugging the Reactor
=====================

The best window into the Reactor is to run the master in the foreground with
debug logging enabled. The output will include when the master sees the event,
what the master does in response to that event, and it will also include the
rendered SLS file (or any errors generated while rendering the SLS file).

1.  Stop the master.
2.  Start the master manually:

    .. code-block:: bash

        salt-master -l debug

3.  Look for log entries in the form:

    .. code-block:: text

        [DEBUG   ] Gathering reactors for tag foo/bar
        [DEBUG   ] Compiling reactions for tag foo/bar
        [DEBUG   ] Rendered data from file: /path/to/the/reactor_file.sls:
        <... Rendered output appears here. ...>

    The rendered output is the result of the Jinja parsing and is a good way to
    view the result of referencing Jinja variables. If the result is empty then
    Jinja produced an empty result and the Reactor will ignore it.

Passing Event Data to Minions or Orchestration as Pillar
--------------------------------------------------------

An interesting trick to pass data from the Reactor SLS file to
:py:func:`state.apply <salt.modules.state.apply_>` is to pass it as inline
Pillar data since both functions take a keyword argument named ``pillar``.

The following example uses Salt's Reactor to listen for the event that is fired
when the key for a new minion is accepted on the master using ``salt-key``.

:file:`/etc/salt/master.d/reactor.conf`:

.. code-block:: yaml

    reactor:
      - 'salt/key':
        - /srv/salt/haproxy/react_new_minion.sls

The Reactor then fires a ::py:func:`state.apply <salt.modules.state.apply_>`
command targeted to the HAProxy servers and passes the ID of the new minion
from the event to the state file via inline Pillar.

:file:`/srv/salt/haproxy/react_new_minion.sls`:

.. code-block:: jinja

    {% if data['act'] == 'accept' and data['id'].startswith('web') %}
    add_new_minion_to_pool:
      local.state.apply:
        - tgt: 'haproxy*'
        - args:
          - mods: haproxy.refresh_pool
          - pillar:
              new_minion: {{ data['id'] }}
    {% endif %}

The above command is equivalent to the following command at the CLI:

.. code-block:: bash

    salt 'haproxy*' state.apply haproxy.refresh_pool pillar='{new_minion: minionid}'

This works with Orchestrate files as well:

.. code-block:: yaml

    call_some_orchestrate_file:
      runner.state.orchestrate:
        - args:
          - mods: orchestrate.some_orchestrate_file
          - pillar:
              stuff: things

Which is equivalent to the following command at the CLI:

.. code-block:: bash

    salt-run state.orchestrate orchestrate.some_orchestrate_file pillar='{stuff: things}'

Finally, that data is available in the state file using the normal Pillar
lookup syntax. The following example is grabbing web server names and IP
addresses from :ref:`Salt Mine <salt-mine>`. If this state is invoked from the
Reactor then the custom Pillar value from above will be available and the new
minion will be added to the pool but with the ``disabled`` flag so that HAProxy
won't yet direct traffic to it.

:file:`/srv/salt/haproxy/refresh_pool.sls`:

.. code-block:: jinja

    {% set new_minion = salt['pillar.get']('new_minion') %}

    listen web *:80
        balance source
        {% for server,ip in salt['mine.get']('web*', 'network.interfaces', ['eth0']).items() %}
        {% if server == new_minion %}
        server {{ server }} {{ ip }}:80 disabled
        {% else %}
        server {{ server }} {{ ip }}:80 check
        {% endif %}
        {% endfor %}

A Complete Example
==================

In this example, we're going to assume that we have a group of servers that
will come online at random and need to have keys automatically accepted. We'll
also add that we don't want all servers being automatically accepted. For this
example, we'll assume that all hosts that have an id that starts with 'ink'
will be automatically accepted and have :py:func:`state.apply
<salt.modules.state.apply_>` executed. On top of this, we're going to add that
a host coming up that was replaced (meaning a new key) will also be accepted.

Our master configuration will be rather simple. All minions that attempt to
authenticate will match the :strong:`tag` of :strong:`salt/auth`. When it comes
to the minion key being accepted, we get a more refined :strong:`tag` that
includes the minion id, which we can use for matching.

:file:`/etc/salt/master.d/reactor.conf`:

.. code-block:: yaml

    reactor:
      - 'salt/auth':
        - /srv/reactor/auth-pending.sls
      - 'salt/minion/ink*/start':
        - /srv/reactor/auth-complete.sls

In this SLS file, we say that if the key was rejected we will delete the key on
the master and then also tell the master to ssh in to the minion and tell it to
restart the minion, since a minion process will die if the key is rejected.

We also say that if the key is pending and the id starts with ink we will
accept the key. A minion that is waiting on a pending key will retry
authentication every ten seconds by default.

:file:`/srv/reactor/auth-pending.sls`:

.. code-block:: jinja

    {# Ink server failed to authenticate -- remove accepted key #}
    {% if not data['result'] and data['id'].startswith('ink') %}
    minion_remove:
      wheel.key.delete:
        - args:
          - match: {{ data['id'] }}
    minion_rejoin:
      local.cmd.run:
        - tgt: salt-master.domain.tld
        - args:
          - cmd: ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "{{ data['id'] }}" 'sleep 10 && /etc/init.d/salt-minion restart'
    {% endif %}

    {# Ink server is sending new key -- accept this key #}
    {% if 'act' in data and data['act'] == 'pend' and data['id'].startswith('ink') %}
    minion_add:
      wheel.key.accept:
        - args:
          - match: {{ data['id'] }}
    {% endif %}

No if statements are needed here because we already limited this action to just
Ink servers in the master configuration.

:file:`/srv/reactor/auth-complete.sls`:

.. code-block:: jinja

    {# When an Ink server connects, run state.apply. #}
    highstate_run:
      local.state.apply:
        - tgt: {{ data['id'] }}
        - ret: smtp

The above will also return the :ref:`highstate <running-highstate>` result data
using the `smtp_return` returner (use virtualname like when using from the
command line with `--return`).  The returner needs to be configured on the
minion for this to work.  See :mod:`salt.returners.smtp_return
<salt.returners.smtp_return>` documentation for that.

.. _minion-start-reactor:

Syncing Custom Types on Minion Start
====================================

Salt will sync all custom types (by running a :mod:`saltutil.sync_all
<salt.modules.saltutil.sync_all>`) on every :ref:`highstate
<running-highstate>`. However, there is a chicken-and-egg issue where, on the
initial :ref:`highstate <running-highstate>`, a minion will not yet have these
custom types synced when the top file is first compiled. This can be worked
around with a simple reactor which watches for ``salt/minion/*/start`` events,
which each minion fires when it first starts up and connects to the master.

On the master, create **/srv/reactor/sync_grains.sls** with the following
contents:

.. code-block:: jinja

    sync_grains:
      local.saltutil.sync_grains:
        - tgt: {{ data['id'] }}

And in the master config file, add the following reactor configuration:

.. code-block:: yaml

    reactor:
      - 'salt/minion/*/start':
        - /srv/reactor/sync_grains.sls

This will cause the master to instruct each minion to sync its custom grains
when it starts, making these grains available when the initial :ref:`highstate
<running-highstate>` is executed.

Other types can be synced by replacing ``local.saltutil.sync_grains`` with
``local.saltutil.sync_modules``, ``local.saltutil.sync_all``, or whatever else
suits the intended use case.

Also, if it is not desirable that *every* minion syncs on startup, the ``*``
can be replaced with a different glob to narrow down the set of minions which
will match that reactor (e.g. ``salt/minion/appsrv*/start``, which would only
match minion IDs beginning with ``appsrv``).


Reactor Tuning for Large-Scale Installations
============================================

The reactor uses a thread pool implementation that's contained inside
``salt.utils.process.ThreadPool``. It uses Python's stdlib Queue to enqueue
jobs which are picked up by standard Python threads. If the queue is full,
``False`` is simply returned by the firing method on the thread pool.

As such, there are a few things to say about the selection of proper values
for the reactor.

For situations where it is expected that many long-running jobs might be
executed by the reactor, ``reactor_worker_hwm`` should be increased or even
set to ``0`` to bound it only by available memory. If set to zero, a close eye
should be kept on memory consumption.

If many long-running jobs are expected and execution concurrency and
performance are a concern, you may also increase the value for
``reactor_worker_threads``. This will control the number of concurrent threads
which are pulling jobs from the queue and executing them. Obviously, this
bears a relationship to the speed at which the queue itself will fill up.
The price to pay for this value is that each thread will contain a copy of
Salt code needed to perform the requested action.
