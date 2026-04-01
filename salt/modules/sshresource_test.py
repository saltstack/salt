"""
Provide the ``test`` execution module for the ``ssh`` resource type.

This is the SSH-resource analogue of ``salt/modules/dummyresource_test.py``.
It is loaded into the per-type execution-module loader when
``opts["resource_type"]`` is ``"ssh"``, causing it to shadow the standard
``salt.modules.test`` for all jobs dispatched to SSH resources.

The managing minion's own jobs continue to use the standard ``test`` module
loaded in the regular ``self.functions`` loader — this module is never
invoked for managing-minion jobs.
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "test"


def __virtual__():
    """
    Load only when this loader is scoped to the ``ssh`` resource type.
    """
    if __opts__.get("resource_type") == "ssh":  # pylint: disable=undefined-variable
        return __virtualname__
    return False, "sshresource_test: only loads in an ssh-resource-type loader."


def ping():
    """
    Return ``True`` if the targeted SSH resource is reachable.

    Delegates to :func:`salt.resource.ssh.ping` via ``__resource_funcs__``
    so the result reflects actual SSH connectivity to the remote host rather
    than the liveness of the managing minion.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:web-01' test.ping
        salt -C 'T@ssh'        test.ping
    """
    return __resource_funcs__["ssh.ping"]()  # pylint: disable=undefined-variable
