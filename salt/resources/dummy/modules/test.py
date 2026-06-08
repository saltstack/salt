"""
Provide the ``test`` execution module for the dummy resource type.

Lives at ``salt/resources/dummy/modules/test.py`` — its location in the
per-type override directory makes it visible only to the dummy resource
loader (via the per-type prepend in :func:`_module_dirs`), so no
``__virtual__`` gate is needed.  Standard ``salt.modules.test`` is
shadowed by directory-order priority for jobs dispatched to dummy
resources; managing-minion jobs continue to use the standard module.
"""

import logging

log = logging.getLogger(__name__)


def ping():
    """
    Return ``True`` if the targeted dummy resource is responsive.

    Delegates to :func:`salt.resources.dummy.ping` via ``__resource_funcs__``
    so the result reflects the actual state of the resource rather than the
    managing minion.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@dummy:dummy-01' test.ping
    """
    return __resource_funcs__["dummy.ping"]()  # pylint: disable=undefined-variable
