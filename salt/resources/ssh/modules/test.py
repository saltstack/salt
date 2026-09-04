"""
Provide the ``test`` execution module for the ``ssh`` resource type.

Lives at ``salt/resources/ssh/modules/test.py`` — its location in the
per-type override directory means it is only discovered by the ssh
resource loader (via the per-type prepend in :func:`_module_dirs`), so
no ``__virtual__`` gate is needed.  The standard ``salt.modules.test``
module is hidden by directory-order priority for jobs dispatched to ssh
resources; managing-minion jobs continue to use the standard module.
"""

import logging

log = logging.getLogger(__name__)


def ping():
    """
    Return ``True`` if the targeted SSH resource is reachable.

    Delegates to :func:`salt.resources.ssh.ping` via ``__resource_funcs__``
    so the result reflects actual SSH connectivity to the remote host rather
    than the liveness of the managing minion.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@ssh:web-01' test.ping
        salt -C 'T@ssh'        test.ping
    """
    return __resource_funcs__["ssh.ping"]()  # pylint: disable=undefined-variable
