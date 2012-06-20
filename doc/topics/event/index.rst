=================
Salt Event System
=================

Salt 0.9.10 introduced the Salt Event System. This system is used to fire
off events enabling third party applications or external processes to react
to behavior within Salt.

The event system is comprised of a few components, the event sockets which
publish events, and the event library which can listen to events and send
events into the salt system.

Listening for Events
====================

The event system is accessed via the event library and can only be accessed
by the same system user that Salt is running as. To listen to events a
SaltEvent object needs to be created and then the get_event function needs to
be run. The SaltEvent object needs to know the location that the Salt unix
sockets are kept. In the configuration this is the ``sock_dir`` option. The
``sock_dir`` option defaults to "/tmp/.salt-unix" on most systems.

The following code will check for a single event:

.. code-block:: python

    import salt.utils.event

    event = salt.utils.event.MasterEvent('/tmp/.salt-unix')

    data = event.get_event()

Events will also use a "tag". A "tag" allows for events to be filtered. By
default all events will be returned, but if only authentication events are
desired, then pass the tag "auth". Also, the get_event method has a default
poll time assigned of 5 seconds, to change this time set the "wait" option.
This example will only listen for auth events and will wait for 10 seconds
instead of the default 5.

.. code-block:: python

    import salt.utils.event

    event = salt.utils.event.MasterEvent('/tmp/.salt-unix')

    data = event.get_event(wait=10, tag='auth')

Instead of looking for a single event, the iter_event method can be used to
make a generator which will continually yield salt events. The iter_event
method also accepts a tag, but not a wait time:

.. code-block:: python

    import salt.utils.event

    event = salt.utils.event.MasterEvent('/tmp/.salt-unix')

    for data in event.iter_event(tag='auth'):
        print(data)
