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
:strong:`tag`. Event tags allow for fast top level filtering of events. In
addition to the tag, each event has a data structure. This data structure is a
dict, which contains information about the event.

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

Reactor sls files are similar to state and pillar sls files.  They are
by default yaml + Jinja templates and are passed familiar context variables.

They differ because of the addition of the ``tag`` and ``data`` variables.

- The ``tag`` variable is just the tag in the fired event.
- The ``data`` variable is the event's data dict.

Here is a simple reactor sls:

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
<salt.modules.state.apply_>`. Similarly, a runner can be called:

.. code-block:: jinja

    {% if data['data']['orchestrate'] == 'refresh' %}
    orchestrate_run:
      runner.state.orchestrate
    {% endif %}

This example will execute the state.orchestrate runner and initiate an
orchestrate execution.

The Goal of Writing Reactor SLS Files
=====================================

Reactor SLS files share the familiar syntax from Salt States but there are
important differences. The goal of a Reactor file is to process a Salt event as
quickly as possible and then to optionally start a **new** process in response.

1.  The Salt Reactor watches Salt's event bus for new events.
2.  The event tag is matched against the list of event tags under the
    ``reactor`` section in the Salt Master config.
3.  The SLS files for any matches are Rendered into a data structure that
    represents one or more function calls.
4.  That data structure is given to a pool of worker threads for execution.

Matching and rendering Reactor SLS files is done sequentially in a single
process. Complex Jinja that calls out to slow Execution or Runner modules slows
down the rendering and causes other reactions to pile up behind the current
one. The worker pool is designed to handle complex and long-running processes
such as Salt Orchestrate.

tl;dr: Rendering Reactor SLS files MUST be simple and quick. The new process
started by the worker threads can be long-running.

Jinja Context
-------------

Reactor files only have access to a minimal Jinja context. ``grains`` and
``pillar`` are not available. The ``salt`` object is available for calling
Runner and Execution modules but it should be used sparingly and only for quick
tasks for the reasons mentioned above.

Advanced State System Capabilities
----------------------------------

Reactor SLS files, by design, do not support Requisites, ordering,
``onlyif``/``unless`` conditionals and most other powerful constructs from
Salt's State system.

Complex Master-side operations are best performed by Salt's Orchestrate system
so using the Reactor to kick off an Orchestrate run is a very common pairing.

For example:

.. code-block:: jinja

    # /etc/salt/master.d/reactor.conf
    # A custom event containing: {"foo": "Foo!", "bar: "bar*", "baz": "Baz!"}
    reactor:
      - myco/custom/event:
        - /srv/reactor/some_event.sls

.. code-block:: jinja

    # /srv/reactor/some_event.sls
    invoke_orchestrate_file:
      runner.state.orchestrate:
        - mods: orch.do_complex_thing
        - pillar:
            event_tag: {{ tag }}
            event_data: {{ data | json() }}

.. code-block:: jinja

    # /srv/salt/orch/do_complex_thing.sls
    {% set tag = salt.pillar.get('event_tag') %}
    {% set data = salt.pillar.get('event_data') %}

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
        - pillar:
            baz: {{ data.baz }}
        - require:
          - salt: do_first_thing

.. _beacons-and-reactors:

Beacons and Reactors
--------------------

An event initiated by a beacon, when it arrives at the master will be wrapped
inside a second event, such that the data object containing the beacon
information will be ``data['data']``, rather than ``data``.

For example, to access the ``id`` field of the beacon event in a reactor file,
you will need to reference ``{{ data['data']['id'] }}`` rather than ``{{
data['id'] }}`` as for events initiated directly on the event bus.

See the :ref:`beacon documentation <beacon-example>` for examples.

Fire an event
=============

To fire an event from a minion call ``event.send``

.. code-block:: bash

    salt-call event.send 'foo' '{orchestrate: refresh}'

After this is called, any reactor sls files matching event tag ``foo`` will
execute with ``{{ data['data']['orchestrate'] }}`` equal to ``'refresh'``.

See :py:mod:`salt.modules.event` for more information.

Knowing what event is being fired
=================================

The best way to see exactly what events are fired and what data is available in
each event is to use the :py:func:`state.event runner
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

.. _reactor-structure:

Understanding the Structure of Reactor Formulas
===============================================

**I.e., when to use `arg` and `kwarg` and when to specify the function
arguments directly.**

While the reactor system uses the same basic data structure as the state
system, the functions that will be called using that data structure are
different functions than are called via Salt's state system. The Reactor can
call Runner modules using the `runner` prefix, Wheel modules using the `wheel`
prefix, and can also cause minions to run Execution modules using the `local`
prefix.

.. versionchanged:: 2014.7.0
    The ``cmd`` prefix was renamed to ``local`` for consistency with other
    parts of Salt. A backward-compatible alias was added for ``cmd``.

The Reactor runs on the master and calls functions that exist on the master. In
the case of Runner and Wheel functions the Reactor can just call those
functions directly since they exist on the master and are run on the master.

In the case of functions that exist on minions and are run on minions, the
Reactor still needs to call a function on the master in order to send the
necessary data to the minion so the minion can execute that function.

The Reactor calls functions exposed in :ref:`Salt's Python API documentation
<client-apis>`. and thus the structure of Reactor files very transparently
reflects the function signatures of those functions.

Calling Execution modules on Minions
------------------------------------

The Reactor sends commands down to minions in the exact same way Salt's CLI
interface does. It calls a function locally on the master that sends the name
of the function as well as a list of any arguments and a dictionary of any
keyword arguments that the minion should use to execute that function.

Specifically, the Reactor calls the async version of :py:meth:`this function
<salt.client.LocalClient.cmd>`. You can see that function has 'arg' and 'kwarg'
parameters which are both values that are sent down to the minion.

Executing remote commands maps to the :strong:`LocalClient` interface which is
used by the :strong:`salt` command. This interface more specifically maps to
the :strong:`cmd_async` method inside of the :strong:`LocalClient` class. This
means that the arguments passed are being passed to the :strong:`cmd_async`
method, not the remote method. A field starts with :strong:`local` to use the
:strong:`LocalClient` subsystem. The result is, to execute a remote command,
a reactor formula would look like this:

.. code-block:: yaml

    clean_tmp:
      local.cmd.run:
        - tgt: '*'
        - arg:
          - rm -rf /tmp/*

The ``arg`` option takes a list of arguments as they would be presented on the
command line, so the above declaration is the same as running this salt
command:

.. code-block:: bash

    salt '*' cmd.run 'rm -rf /tmp/*'

Use the ``expr_form`` argument to specify a matcher:

.. code-block:: yaml

    clean_tmp:
      local.cmd.run:
        - tgt: 'os:Ubuntu'
        - expr_form: grain
        - arg:
          - rm -rf /tmp/*


    clean_tmp:
      local.cmd.run:
        - tgt: 'G@roles:hbase_master'
        - expr_form: compound
        - arg:
          - rm -rf /tmp/*

.. note::
    An easy mistake to make here is to use ``tgt_type`` instead of
    ``expr_form``, since the job cache and events all refer to the targeting
    method as ``tgt_type``. As of the Nitrogen release of Salt, ``expr_form``
    will be deprecated in favor of using ``tgt_type``, to help with this
    confusion.

Any other parameters in the :py:meth:`LocalClient().cmd()
<salt.client.LocalClient.cmd>` method can be specified as well.

Executing Reactors from the Minion
----------------------------------

The minion can be setup to use the Reactor via a reactor engine.  This just
sets up and listens to the minions event bus, instead of to the masters.

The biggest difference is that you have to use the caller method on the
Reactor, which is the equivalent of salt-call, to run your commands.

:mod:`Reactor Engine setup <salt.engines.reactor>`

.. code-block:: yaml

    clean_tmp:
      caller.cmd.run:
        - arg:
          - rm -rf /tmp/*

.. note:: Masterless Minions use this Reactor

    This is the only way to run the Reactor if you use masterless minions.

Calling Runner modules and Wheel modules
----------------------------------------

Calling Runner modules and Wheel modules from the Reactor uses a more direct
syntax since the function is being executed locally instead of sending a
command to a remote system to be executed there. There are no 'arg' or 'kwarg'
parameters (unless the Runner function or Wheel function accepts a parameter
with either of those names.)

For example:

.. code-block:: yaml

    clear_the_grains_cache_for_all_minions:
      runner.cache.clear_grains

If the :py:func:`the runner takes arguments <salt.runners.cloud.profile>` then
they must be specified as keyword arguments.

.. code-block:: yaml

    spin_up_more_web_machines:
      runner.cloud.profile:
        - prof: centos_6
        - instances:
          - web11       # These VM names would be generated via Jinja in a
          - web12       # real-world example.

To determine the proper names for the arguments, check the documentation
or source code for the runner function you wish to call.

Passing event data to Minions or Orchestrate as Pillar
------------------------------------------------------

An interesting trick to pass data from the Reactor script to
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
        - arg:
          - haproxy.refresh_pool
        - kwarg:
            pillar:
              new_minion: {{ data['id'] }}
    {% endif %}

The above command is equivalent to the following command at the CLI:

.. code-block:: bash

    salt 'haproxy*' state.apply haproxy.refresh_pool pillar='{new_minion: minionid}'

This works with Orchestrate files as well:

.. code-block:: yaml

    call_some_orchestrate_file:
      runner.state.orchestrate:
        - mods: some_orchestrate_file
        - pillar:
            stuff: things

Which is equivalent to the following command at the CLI:

.. code-block:: bash

    salt-run state.orchestrate some_orchestrate_file pillar='{stuff: things}'

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

Our master configuration will be rather simple. All minions that attempte to
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

In this sls file, we say that if the key was rejected we will delete the key on
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
        - match: {{ data['id'] }}
    minion_rejoin:
      local.cmd.run:
        - tgt: salt-master.domain.tld
        - arg:
          - ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "{{ data['id'] }}" 'sleep 10 && /etc/init.d/salt-minion restart'
    {% endif %}

    {# Ink server is sending new key -- accept this key #}
    {% if 'act' in data and data['act'] == 'pend' and data['id'].startswith('ink') %}
    minion_add:
      wheel.key.accept:
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
around with a simple reactor which watches for ``minion_start`` events, which
each minion fires when it first starts up and connects to the master.

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
