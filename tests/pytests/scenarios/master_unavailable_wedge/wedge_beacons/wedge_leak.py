# Copyright © 2026 Broadcom Inc. and/or its subsidiaries. All Rights Reserved.
"""
Test-only beacon that reproduces the deployment shape of.

Third-party beacons and engines that talk to the master by opening a
``zmq.Context`` (or ``salt.channel.client.AsyncReqChannel.factory``) and
letting the reference drop rely on Python GC to run
``Context.__del__``. Under pyzmq >= 24 that finalizer path chains
into ``destroy()`` -> ``socket.close()`` with the pyzmq default
``LINGER = -1``, and any queued undeliverable message makes
``socket.close()`` block in libzmq's ``zmq_ctx_term()``.

The minion's beacon dispatcher (``salt/minion.py`` ``setup_beacons`` ->
``handle_beacons``) is registered as a tornado ``PeriodicCallback`` on
the same ioloop that services publishes and channel replies -- i.e.
the MPM MainThread's ioloop. Anything a beacon leaks is therefore
finalized from a callback on that ioloop. This beacon does that leak
minimally: a bare ``zmq.Context()`` + REQ socket + queued send, then
returns. Refcount hits zero at return, ``Context.__del__`` fires
before the next scheduler tick, and MainThread wedges in
``zmq_ctx_term()`` for as long as the queued message cannot drain.
"""

import zmq

__virtualname__ = "wedge_leak"


def __virtual__():
    return __virtualname__


def validate(config):
    return True, "valid"


def beacon(config):
    """Leak a ``zmq.Context`` with a REQ socket that has one queued
    undeliverable message. Locals drop at return; ``Context.__del__``
    fires inside this callback on the minion's MPM ioloop.
    """
    master_uri = None
    for entry in config or []:
        if isinstance(entry, dict) and "master_uri" in entry:
            master_uri = entry["master_uri"]
            break
    if master_uri is None:
        master_uri = "tcp://127.0.0.1:1"

    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, -1)
    sock.setsockopt(zmq.SNDTIMEO, 0)
    sock.connect(master_uri)
    try:
        sock.send(b"queued-but-undeliverable", flags=zmq.NOBLOCK)
    except zmq.Again:
        pass
    # No sock.close(), no ctx.destroy(linger=0). Refs drop at return.
    return []
