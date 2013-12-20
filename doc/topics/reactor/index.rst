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

In the master config section 'reactor:' is a list of event tags to be matched
and each event tag has a list of reactor SLS files to be run.

.. code-block:: yaml

    reactor:                           # Master config section "reactor"

      - 'salt/minion/*/start':                # Match tag "salt/minion/*/start"
        - /srv/reactor/start.sls       # Things to do when a minion starts
        - /srv/reactor/monitor.sls     # Other things to do

      - 'salt/cloud/*/destroyed':     # Globs can be used to matching tags
        - /srv/reactor/decommision.sls # Things to do when a server is removed


Reactor sls files are similar to state and pillar sls files.  They are
by default yaml + Jinja templates and are passed familar context variables.

They differ because of the addtion of the ``tag`` and ``data`` variables.

- The ``tag`` variable is just the tag in the fired event.
- The ``data`` variable is the event's data dict.

Here is a simple reactor sls:

.. code-block:: yaml

    {% if data['id'] == 'mysql1' %}
    highstate_run:
      cmd.state.highstate:
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

To fire an event from a minion call ``event.fire_master``

.. code-block:: bash

    salt-call event.fire_master '{"overstate": "refresh"}' 'foo'

After this is called, any reactor sls files matching event tag ``foo`` will 
execute with ``{{ data['data']['overstate'] }}`` equal to ``'refresh'``.

See :py:mod:`salt.modules.event` for more information.

Knowing what event is being fired
=================================

Knowing exactly which event is being fired and what data is has for use in the
sls files can be challenging. The easiest way to see exactly what's going on is
to use the :strong:`eventlisten.py` script. This script is not part of packages
but is part of the source.

If the master process is using the default socket, no additional options will be
required. Otherwise, you will need to specify the socket location.

Example usage:

.. code-block:: bash

    wget https://raw.github.com/saltstack/salt/develop/tests/eventlisten.py
    python eventlisten.py

    # OR
    python eventlisten.py --sock-dir /path/to/var/run/salt

Example output:

.. code-block:: text

    Event fired at Fri Dec 20 10:43:00 2013
    *************************
    Tag: salt/auth
    Data:
    {'_stamp': '2013-12-20_10:47:54.584699',
     'act': 'accept',
     'id': 'fuzzer.domain.tld',
     'pub': '-----BEGIN PUBLIC KEY-----\nMIICIDANBgk+TRIMMED+EMZ8CAQE=\n-----END PUBLIC KEY-----\n',
     'result': True}

    Event fired at Fri Dec 20 10:43:01 2013
    *************************
    Tag: salt/minion/fuzzer.domain.tld/start
    Data:
    {'_stamp': '2013-12-20_10:43:01.638387',
     'cmd': '_minion_event',
     'data': 'Minion fuzzer.domain.tld started at Fri Dec 20 10:43:01 2013',
     'id': 'fuzzer.domain.tld',
     'pretag': None,
     'tag': 'salt/minion/fuzzer.domain.tld/start'}

Understanding the Structure of Reactor Formulas
===============================================

While the reactor system uses the same data structure as the state system, this
data does not translate the same way to operations. In state files formula
information is mapped to the state functions, but in the reactor system
information is mapped to a number of available subsystems on the master. These
systems are the :strong:`LocalClient` and the :strong:`Runners`. The
:strong:`state declaration` field takes a reference to the function to call in
each interface. So to trigger a salt-run call the :strong:`state declaration`
field will start with :strong:`runner`, followed by the runner function to
call. This means that a call to what would be on the command line
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
method, not the remote method. A field starts with :strong:`cmd` to use the
:strong:`LocalClient` subsystem. The result is, to execute a remote command, 
a reactor fomular would look like this:

.. code-block:: yaml

    clean_tmp:
      cmd.cmd.run:
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
      cmd.cmd.run:
        - tgt: 'os:Ubuntu'
        - expr_form: grain
        - arg:
          - rm -rf /tmp/*


    clean_tmp:
      cmd.cmd.run:
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

Note, the Pillar data will need to be passed as a string since that is how it
is passed at the CLI. That string will be parsed as YAML on the minion (same as
how it works at the CLI).

:file:`/srv/salt/haproxy/react_new_minion.sls`:

.. code-block:: yaml

    {% if data['act'] == 'accept' and data['id'].startswith('web') %}
    add_new_minion_to_pool:
      cmd.state.sls:
        - tgt: 'haproxy*'
        - arg:
          - haproxy.refresh_pool
          - 'pillar={new_minion: {{ data['id'] }}}'
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

A complete example
==================

In this example, we're going to assume that we have a group of servers that
will come online at random and need to have keys automatically accepted. We'll
also add that we don't want all servers being automatically accepted. For this
example, we'll assume that all hosts that have an id that starts with 'ink'
will be automatically accepted and have state.highstate executed. On top of
thise, we're going to add that a host coming up that was replaced (meaning a new
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

We also say that if the key is pending and the id starts with ink we will accept
the key. A minion that is waiting on a pending key will retry authentication
authentication every ten second by default.

:file:`/srv/reactor/auth-pending.sls`:

.. code-block:: yaml

    {# Ink server faild to authenticate -- remove accepted key #}
    {% if not data['result'] and data['id'].startswith('ink') %}
    minion_remove:
      wheel.key.delete:
        - match: {{ data['id'] }}
    minion_rejoin:
      cmd.cmd.run:
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
      cmd.state.highstate:
        - tgt: {{ data['id'] }}
