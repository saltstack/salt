.. _event-system:

============
Event System
============

The Salt Event System is used to fire off events enabling third party
applications or external processes to react to behavior within Salt.
The event system uses a publish-subscribe pattern, otherwise know as pub/sub.

Event Bus
=========

The event system is comprised of a two primary components, which make up the
concept of an Event Bus:

- The event sockets, which publish events
- The event library, which can listen to events and send events into the salt system

Events are published onto the event bus and event bus subscribers listen for the
published events.

The event bus is used for both inter-process communication as well as network transport
in Salt. Inter-process communication is provided through UNIX domain sockets (UDX).

The Salt Master and each Salt Minion has their own event bus.

Event types
===========

.. toctree::
    :maxdepth: 2

    master_events

Listening for Events
====================

Salt's event system is used heavily within Salt and it is also written to
integrate heavily with existing tooling and scripts. There is a variety of
ways to consume it.

From the CLI
------------

The quickest way to watch the event bus is by calling the :py:func:`state.event
runner <salt.runners.state.event>`:

.. code-block:: bash

    salt-run state.event pretty=True

That runner is designed to interact with the event bus from external tools and
shell scripts. See the documentation for more examples.

Remotely via the REST API
-------------------------

Salt's event bus can be consumed
:py:class:`salt.netapi.rest_cherrypy.app.Events` as an HTTP stream from
external tools or services.

.. code-block:: bash

    curl -SsNk https://salt-api.example.com:8000/events?token=05A3

From Python
-----------

Python scripts can access the event bus only as the same system user that Salt
is running as.

The event system is accessed via the event library and can only be accessed
by the same system user that Salt is running as. To listen to events a
SaltEvent object needs to be created and then the get_event function needs to
be run. The SaltEvent object needs to know the location that the Salt Unix
sockets are kept. In the configuration this is the ``sock_dir`` option. The
``sock_dir`` option defaults to "/var/run/salt/master" on most systems.

The following code will check for a single event:

.. code-block:: python

    import salt.config
    import salt.utils.event

    opts = salt.config.client_config("/etc/salt/master")

    event = salt.utils.event.get_event(
        "master", sock_dir=opts["sock_dir"], transport=opts["transport"], opts=opts
    )

    data = event.get_event()

Events will also use a "tag". Tags allow for events to be filtered by prefix.
By default all events will be returned. If only authentication events are
desired, then pass the tag "salt/auth".

The ``get_event`` method has a default poll time assigned of 5 seconds. To
change this time set the "wait" option.

The following example will only listen for auth events and will wait for 10 seconds
instead of the default 5.

.. code-block:: python

    data = event.get_event(wait=10, tag="salt/auth")

To retrieve the tag as well as the event data, pass ``full=True``:

.. code-block:: python

    evdata = event.get_event(wait=10, tag="salt/job", full=True)

    tag, data = evdata["tag"], evdata["data"]


Instead of looking for a single event, the ``iter_events`` method can be used to
make a generator which will continually yield salt events.

The iter_events method also accepts a tag but not a wait time:

.. code-block:: python

    for data in event.iter_events(tag="salt/auth"):
        print(data)

And finally event tags can be globbed, such as they can be in the Reactor,
using the fnmatch library.

.. code-block:: python

    import fnmatch

    import salt.config
    import salt.utils.event

    opts = salt.config.client_config("/etc/salt/master")

    sevent = salt.utils.event.get_event(
        "master", sock_dir=opts["sock_dir"], transport=opts["transport"], opts=opts
    )

    while True:
        ret = sevent.get_event(full=True)
        if ret is None:
            continue

        if fnmatch.fnmatch(ret["tag"], "salt/job/*/ret/*"):
            do_something_with_job_return(ret["data"])

Firing Events
=============

It is possible to fire events on either the minion's local bus or to fire
events intended for the master.

To fire a local event from the minion on the command line call the
:py:func:`event.fire <salt.modules.event.fire>` execution function:

.. code-block:: bash

    salt-call event.fire '{"data": "message to be sent in the event"}' 'tag'

To fire an event to be sent up to the master from the minion call the
:py:func:`event.send <salt.modules.event.send>` execution function. Remember
YAML can be used at the CLI in function arguments:


.. code-block:: bash

    salt-call event.send 'myco/mytag/success' '{success: True, message: "It works!"}'

If a process is listening on the minion, it may be useful for a user on the
master to fire an event to it. An example of listening local events on
a minion on a non-Windows system:

.. code-block:: python

    # Job on minion
    import salt.utils.event

    opts = salt.config.minion_config("/etc/salt/minion")
    event = salt.utils.event.MinionEvent(opts)

    for evdata in event.iter_events(match_type="regex", tag="custom/.*"):
        # do your processing here...
        ...

And an example of listening local events on a Windows system:

.. code-block:: python

    # Job on minion
    import salt.utils.event

    opts = salt.config.minion_config(salt.minion.DEFAULT_MINION_OPTS)
    event = salt.utils.event.MinionEvent(opts)

    for evdata in event.iter_events(match_type="regex", tag="custom/.*"):
        # do your processing here...
        ...

.. code-block:: bash

    salt minionname event.fire '{"data": "message for the minion"}' 'customtag/african/unladen'


Firing Events from Python
=========================

From Salt execution modules
---------------------------

Events can be very useful when writing execution modules, in order to inform
various processes on the master when a certain task has taken place. This is
easily done using the normal cross-calling syntax:

.. code-block:: python

    # /srv/salt/_modules/my_custom_module.py


    def do_something():
        """
        Do something and fire an event to the master when finished

        CLI Example::

            salt '*' my_custom_module:do_something
        """
        # do something!
        __salt__["event.send"](
            "myco/my_custom_module/finished",
            {"finished": True, "message": "The something is finished!",},
        )

From Custom Python Scripts
--------------------------

Firing events from custom Python code is quite simple and mirrors how it is
done at the CLI:

.. code-block:: python

    import salt.client

    caller = salt.client.Caller()

    ret = caller.cmd(
        "event.send", "myco/event/success", {"success": True, "message": "It works!"}
    )

    if not ret:
        # the event could not be sent, process the error here
        ...
