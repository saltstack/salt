=================
Salt Event System
=================

Salt 0.9.10 introduced the Salt Event System. This system is used to fire
off events enabling third party applicaitons or external processes to react
to behavior within Salt.

The event system is comprised of a few compnents, the event sockets which
publish events, and the event librairy which can listen to events and send
events into the salt system.

Listening for Events
====================

The event system is accessed via the event librairy and can only be accessed
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

