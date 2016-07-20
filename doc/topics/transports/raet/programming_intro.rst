.. _raet-programming:

=========================
Intro to RAET Programming
=========================

.. note::

    This page is still under construction

The first thing to cover is that RAET does not present a socket api, it
presents, and queueing api, all messages in RAET are made available to via
queues. This is the single most differentiating factor with RAET vs other
networking libraries, instead of making a socket, a stack is created.
Instead of calling send() or recv(), messages are placed on the stack to be
sent and messages that are received appear on the stack.

Different kinds of stacks are also available, currently two stacks exist,
the UDP stack, and the UXD stack. The UDP stack is used to communicate over
udp sockets, and the UXD stack is used to communicate over Unix Domain
Sockets.

The UDP stack runs a context for communicating over networks, while the
UXD stack has contexts for communicating between processes.

UDP Stack Messages
==================

To create a UDP stack in RAET, simply create the stack, manage the queues,
and process messages:

.. code-block:: python

    from salt.transport.road.raet import stacking
    from salt.transport.road.raet import estating

    udp_stack = stacking.StackUdp(ha=('127.0.0.1', 7870))
    r_estate = estating.Estate(stack=stack, name='foo', ha=('192.168.42.42', 7870))
    msg = {'hello': 'world'}
    udp_stack.transmit(msg, udp_stack.estates[r_estate.name])
    udp_stack.serviceAll()
