"""
Process-level markers describing how the current salt Python process was
invoked, populated by :mod:`salt.scripts` at CLI entry and consumed
downstream by code that needs to distinguish CLI-invocation from daemon
behavior.

The only current consumer is the ZMQ identity gate in
:mod:`salt.transport.zeromq`.  A salt CLI that runs from a master host
(e.g. ``salt '*' test.ping`` executed on the master) loads
``/etc/salt/master`` and therefore inherits ``__role=master`` in its
opts, indistinguishable from the master daemon itself.  Without a mark
set here the identity gate would leave that connection with libzmq's
default per-connection random routing-id, which the master's
``MWorkerQueue`` ROUTER accepts but never frees the underlying socket
FD for -- leaking one FD per CLI invocation.

Why not sniff ``sys.argv[0]``?  Entry-point wrappers and frozen binaries
rewrite argv; an explicit mark set once from the entry point is
unambiguous and easy to control in tests.
"""

_IS_CLI = False


def is_cli():
    """
    ``True`` iff the current process was invoked through a salt CLI
    entry point (``salt``, ``salt-call``, ``salt-cp``, ``salt-key``,
    ``salt-run``, ``salt-cloud``).  Daemon processes
    (``salt-master``, ``salt-minion``, ``salt-syndic``, ``salt-api``,
    ``salt-proxy``) return ``False``.
    """
    return _IS_CLI


def mark_as_cli():
    """
    Record that the current process is running as a salt CLI tool.
    Called from :mod:`salt.scripts` at the top of each CLI entry
    function.  Idempotent; safe to call more than once.
    """
    global _IS_CLI
    _IS_CLI = True
