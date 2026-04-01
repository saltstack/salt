"""
Provide the ``test`` execution module for the dummy resource type.

This is the resource analogue of ``salt/modules/dummyproxy_test.py``.

Because this module is loaded into an isolated per-type
:func:`salt.loader.resource_modules` loader (``opts["resource_type"]`` is
set to ``"dummy"`` for that loader), it takes priority over the standard
``salt/modules/test.py`` for all calls dispatched to dummy resources.

Unlike proxy Pattern B modules that must handle *two* contexts at call time
(resource vs. managing minion), this module is **only ever invoked for
resource jobs**: the managing minion's own jobs continue to use the standard
execution modules loaded in the regular ``self.functions`` loader.
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "test"


def __virtual__():
    """
    Load only when this loader is scoped to the ``dummy`` resource type.
    """
    if __opts__.get("resource_type") == "dummy":
        return __virtualname__
    return (
        False,
        "dummyresource_test: only loads in a dummy-resource-type loader.",
    )


def ping():
    """
    Return ``True`` if the targeted dummy resource is responsive.

    Delegates to :func:`salt.resource.dummy.ping` via ``__resource_funcs__``
    so the result reflects the actual state of the resource rather than the
    managing minion.

    CLI Example:

    .. code-block:: bash

        salt -C 'T@dummy:dummy-01' test.ping
    """
    return __resource_funcs__["dummy.ping"]()  # pylint: disable=undefined-variable
