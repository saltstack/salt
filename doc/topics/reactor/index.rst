==============
Reactor System
==============

Salt version 0.11.0 introduced the reactor system. The premise behind the
reactor system is that with Salt's events and the ability to execute commands a
logic engine could be put in place to allow events to trigger actions, or more
accurately, reactions. 

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
:strong:`tag` which is comprised of a maximum of 20 characters. Event tags
allow for fast top level filtering of events. In addition to the tag, an event
has a data structure. This data structure is a dict containing information
about the event.

Mapping Events to Reactor SLS Files
===================================

The event tag and data are both critical when working with the reactor system.
In the master configuration file under the reactor option, tags are associated
with lists of reactor sls formulas (globs can be used for matching):

.. code-block:: yaml

    reactor:
      - 'auth':
        - /srv/reactor/authreact1.sls
        - /srv/reactor/authreact2.sls
      - 'minion_start':
        - /srv/reactor/start.sls

When an event with a tag of auth is fired the reactor will catch the event and
render the two listed files. The rendered files are standard sls files, so by
default they are yaml + Jinja. The Jinja is packed with a few data structures
similar to state and pillar sls files. The data available is found in the
``tag`` and ``data`` variables. The ``tag`` variable is just the tag in the
fired event and the ``data`` variable is the event's data dict. Here is a
simple reactor sls:

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
API and the runner system.  In this example a command is published to the
mysql1 minion with a function of ``state.highstate``. Similarly, a runner can
be called:

.. code-block:: yaml

    {% if data['data']['overstate'] == 'refresh' %}
    overstate_run:
      runner.state.over
    {% endif %}

This example will execute the state.overstate runner and initiate an overstate
execution.

Understanding the Structure of Reactor Formulas
===============================================

While the reactor system uses the same data structure as the state system, this
data does not translate the same way to operations. In state formulas
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
method, not the remote method. The field starts with :strong:`cmd` to use the
:strong:`LocalClient` subsystem. The result is that to execute a remote command
it looks like this:

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
