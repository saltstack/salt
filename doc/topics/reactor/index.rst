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
these reaction files use highdata to define reactions to be executed.

Event System
============

A basic understanding of the event system is required to understand reactors.
The event system is a local ZeroMQ PUB interface which fires salt events. This
event bus is an open system used for sending information notifying Salt and
other systems about operations.

The event system fires events with a very specific criteria. Every event has a
`tag` which is comprised of a maximum of 20 characters. Event tags allow for
fast top level filtering of events. In addition to the tag, an event has a data
structure. This data structure is a dict containing information about the
event.

Mapping Events to Reactor SLS Files
===================================

The event tag and data are both critical when working with the reactor system.
In the master configuration file under the reactor option, tags are associated
with lists of reactor sls files (globs can be used for matching):

.. code-block:: yaml

    reactor:
      - 'auth':
        - /srv/reactor/authreact1.sls
        - /srv/reactor/authreact2.sls
      - 'minion_start':
        - /srv/reactor/start.sls

When an event with a tag of auth is fired the reactor will catch the event and
render the two listed files. The rendered files are standard sls files, so by
default they are yaml + jinja. The jinja is packed with a few data structures
similar to state and pillar sls files. The data available is found in the `tag`
and `data` variables. The `tag` variable is just the tag in the fired event
and the `data` variable is the event's data dict. Here is a simple reactor sls:

.. code-block:: yaml

    {% if data['id'] == 'mysql1' %}
    highstate_run:
      cmd.state.highstate:
        - tgt: mysql1
    {% endif %}

This simple reactor file uses jinja to further refine the reaction to be made.
If the `id` in the event data is mysql1 (if the name of the minion is mysql1) then
the following reaction is defined. The same data structure and compiler used
for the state system is used for the reactor system. The only difference is that the
data is matched up to the salt command api and the runner system. In this
example a command is published to the mysql1 minion with a function of
state.highstate. Similarly, a runner can be called:

.. code-block:: yaml

    {% if data['data']['overstate'] == 'refresh' %}
    overstate_run:
      runner.state.overstate
    {% endif %}

This example will execute the state.overstate runner and initiate an overstate
execution.
