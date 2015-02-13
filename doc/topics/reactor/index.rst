.. _reactor:

.. index:: ! Reactor, Salt Reactor
    seealso: Event; Reactor

==============
Reactor System
==============

Salt version 0.11.0 introduced the reactor system. The premise behind the
reactor system is that with Salt's events and the ability to execute commands,
a logic engine could be put in place to allow events to trigger actions, or
more accurately, reactions.

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

      - 'salt/cloud/*/destroyed':       # Globs can be used to matching tags
        - /srv/reactor/destroy/*.sls    # Globs can be used to match file names

      - 'myco/custom/event/tag':        # React to custom event tags
        - salt://reactor/mycustom.sls   # Put reactor files under file_roots


Reactor sls files are similar to state and pillar sls files.  They are
by default yaml + Jinja templates and are passed familar context variables.

They differ because of the addition of the ``tag`` and ``data`` variables.

- The ``tag`` variable is just the tag in the fired event.
- The ``data`` variable is the event's data dict.

Here is a simple reactor sls:

.. code-block:: yaml

    {% if data['id'] == 'mysql1' %}
    highstate_run:
      local.state.highstate:
        - tgt: mysql1
    {% endif %}

This simple reactor file uses Jinja to further refine the reaction to be made.
If the ``id`` in the event data is ``mysql1`` (in other words, if the name of
the minion is ``mysql1``) then the following reaction is defined.  The same
data structure and compiler used for the state system is used for the reactor
system. The only difference is that the data is matched up to the salt command
API and the runner system.  In this example, a command is published to the
``mysql1`` minion with a function of ``state.highstate``. Similarly, a runner
can be called:

.. code-block:: yaml

    {% if data['data']['overstate'] == 'refresh' %}
    overstate_run:
      runner.state.over
    {% endif %}

This example will execute the state.overstate runner and initiate an overstate
execution.

Fire an event
=============

To fire an event from a minion call ``event.send``

.. code-block:: bash

    salt-call event.send 'foo' '{overstate: refresh}'

After this is called, any reactor sls files matching event tag ``foo`` will 
execute with ``{{ data['data']['overstate'] }}`` equal to ``'refresh'``.

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

Understanding the Structure of Reactor Formulas
===============================================

While the reactor system uses the same data structure as the state system, this
data does not translate the same way to function calls.

.. versionchanged:: 2014.7.0
    The ``cmd`` prefix was renamed to ``local`` for consistency with other
    parts of Salt. A backward-compatible alias was added for ``cmd``.

In state files the minion generates the data structure locally and uses that to
call local state functions. In the reactor system the master generates a data
structure that is used to call methods on one of Salt's client interfaces
described in :ref:`the Python API documentation <client-apis>`.

* :py:class:`~salt.client.LocalClient` is used to call Execution modules
  remotely on minions. (The :command:`salt` CLI program uses this also.)
* :py:class:`~salt.runner.RunnerClient` calls Runner modules locally on the
  master.
* :py:class:`~salt.wheel.WheelClient` calls Wheel modules locally on the
  master.

The :strong:`state declaration` field takes a reference to the function to call
in each interface. So to trigger a salt-run call the :strong:`state
declaration` field will start with :strong:`runner`, followed by the runner
function to call. This means that a call to what would be on the command line
:strong:`salt-run manage.up` will be :strong:`runner.manage.up`. An example of
this in a reactor formula would look like this:

.. code-block:: yaml

    manage_up:
      runner.manage.up

If the runner takes arguments then they can be specified as well:

.. code-block:: yaml

    overstate_dev_env:
      runner.state.over:
        - env: dev

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

An interesting trick to pass data from the Reactor script to
``state.highstate`` or ``state.sls`` is to pass it as inline Pillar data since
both functions take a keyword argument named ``pillar``.

The following example uses Salt's Reactor to listen for the event that is fired
when the key for a new minion is accepted on the master using ``salt-key``.

:file:`/etc/salt/master.d/reactor.conf`:

.. code-block:: yaml

    reactor:
      - 'salt/key':
        - /srv/salt/haproxy/react_new_minion.sls

The Reactor then fires a ``state.sls`` command targeted to the HAProxy servers
and passes the ID of the new minion from the event to the state file via inline
Pillar.

:file:`/srv/salt/haproxy/react_new_minion.sls`:

.. code-block:: yaml

    {% if data['act'] == 'accept' and data['id'].startswith('web') %}
    add_new_minion_to_pool:
      local.state.sls:
        - tgt: 'haproxy*'
        - arg:
          - haproxy.refresh_pool
        - kwarg:
            pillar:
              new_minion: {{ data['id'] }}
    {% endif %}

The above command is equivalent to the following command at the CLI:

.. code-block:: bash

    salt 'haproxy*' state.sls haproxy.refresh_pool 'pillar={new_minion: minionid}'

Finally, that data is available in the state file using the normal Pillar
lookup syntax. The following example is grabbing web server names and IP
addresses from :ref:`Salt Mine <salt-mine>`. If this state is invoked from the
Reactor then the custom Pillar value from above will be available and the new
minion will be added to the pool but with the ``disabled`` flag so that HAProxy
won't yet direct traffic to it.

:file:`/srv/salt/haproxy/refresh_pool.sls`:

.. code-block:: yaml

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
will be automatically accepted and have state.highstate executed. On top of
this, we're going to add that a host coming up that was replaced (meaning a new
key) will also be accepted.

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

.. code-block:: yaml

    {# Ink server faild to authenticate -- remove accepted key #}
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

.. code-block:: yaml

    {# When an Ink server connects, run state.highstate. #}
    highstate_run:
      local.state.highstate:
        - tgt: {{ data['id'] }}

.. _minion-start-reactor:

Syncing Custom Types on Minion Start
====================================

Salt will sync all custom types (by running a :mod:`saltutil.sync_all
<salt.modules.saltutil.sync_all>`) on every highstate. However, there is a
chicken-and-egg issue where, on the initial highstate, a minion will not yet
have these custom types synced when the top file is first compiled. This can be
worked around with a simple reactor which watches for ``minion_start`` events,
which each minion fires when it first starts up and connects to the master.

On the master, create **/srv/reactor/sync_grains.sls** with the following
contents:

.. code-block:: yaml

    sync_grains:
      local.saltutil.sync_grains:
        - tgt: {{ data['id'] }}

And in the master config file, add the following reactor configuration:

.. code-block:: yaml

    reactor:
      - 'minion_start':
        - /srv/reactor/sync_grains.sls

This will cause the master to instruct each minion to sync its custom grains
when it starts, making these grains available when the initial highstate is
executed.

Other types can be synced by replacing ``local.saltutil.sync_grains`` with
``local.saltutil.sync_modules``, ``local.saltutil.sync_all``, or whatever else
suits the intended use case.
