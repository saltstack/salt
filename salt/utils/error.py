"""
Utilities to enable exception reraising across the master commands

"""

import builtins

import salt.exceptions
import salt.utils.event


def raise_error(name=None, args=None, message=""):
    """
    Raise an exception with __name__ from name, args from args
    If args is None Otherwise message from message\
    If name is empty then use "Exception"
    """
    name = name or "Exception"
    if hasattr(salt.exceptions, name):
        ex = getattr(salt.exceptions, name)
    elif hasattr(builtins, name):
        ex = getattr(builtins, name)
    else:
        name = "SaltException"
        ex = getattr(salt.exceptions, name)
    if args is not None:
        raise ex(*args)
    else:
        raise ex(message)


def pack_exception(exc):
    if hasattr(exc, "pack"):
        packed_exception = exc.pack()
    else:
        packed_exception = {"message": exc.__unicode__(), "args": exc.args}
    return packed_exception


def fire_exception(exc, opts, job=None, node="minion"):
    """
    Fire raw exception across the event bus
    """
    if job is None:
        job = {}
    # Context-manage the SaltEvent so ``destroy()`` closes both pusher
    # and subscriber synchronously on the way out.  Without the ``with``
    # block, cleanup ran only when GC eventually invoked
    # ``SaltEvent.__del__`` and each finalisation emitted the three-warning
    # triad from the underlying transport chain
    # (``unclosed publish server``, ``unclosed publisher client``,
    # ``unclosed SyncWrapper for _TCPPubServerPublisher``).  See #70175.
    with salt.utils.event.SaltEvent(node, opts=opts, listen=False) as event:
        event.fire_event(pack_exception(exc), "_salt_error")
