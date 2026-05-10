"""
State module for the dummy resource type.

Lives under ``salt/states/`` like any other state module.  Demonstrates that
`.sls` files can target a specific dummy resource by id (e.g. ``T@dummy:dummy-01``)
without needing a special ``__resource_funcs__`` dunder: state modules use
plain ``__salt__`` and dispatch is handled by the per-resource execution
loader installed in :class:`salt.state.State` when ``opts["resource_type"]``
is set.

Loads only when the host loader has been built for the ``dummy`` resource
type; otherwise virtuals out so it never appears on the managing minion's
own state run.
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "dummy_test"


def __virtual__():
    if __opts__.get("resource_type") == "dummy":  # pylint: disable=undefined-variable
        return __virtualname__
    return (
        False,
        "dummyresource_test state: only loads in a dummy-resource-type loader.",
    )


def present(name, **kwargs):
    """
    Verify the targeted dummy resource is reachable.

    Calls :func:`test.ping` via ``__salt__``.  Because this state module is
    loaded through the per-resource execution loader, ``__salt__["test.ping"]``
    resolves to :func:`salt.modules.dummyresource_test.ping` rather than the
    managing minion's :func:`salt.modules.test.ping`.
    """
    pong = __salt__["test.ping"]()  # pylint: disable=undefined-variable
    return {
        "name": name,
        "result": bool(pong),
        "comment": f"dummy resource ping returned {pong!r}",
        "changes": {},
    }


def package_installed(name, version=None):
    """
    Ensure a "package" is installed on the targeted dummy resource.

    Idempotent: only installs if the requested package is missing or at a
    different version.  Uses :func:`salt.resource.dummy.package_list` /
    :func:`salt.resource.dummy.package_install` via the per-resource
    execution loader's ``__salt__``.
    """
    # pylint: disable=undefined-variable
    current = __salt__["pkg.list_pkgs"]() if "pkg.list_pkgs" in __salt__ else None
    # pylint: enable=undefined-variable
    if current is None:
        # Fall back to the resource's own package_list when the standard
        # pkg.list_pkgs interface is not implemented for dummy.
        current = __salt__["dummy.package_list"]()  # pylint: disable=undefined-variable

    desired = version or "1.0"
    if current.get(name) == desired:
        return {
            "name": name,
            "result": True,
            "comment": f"package {name} already at {desired}",
            "changes": {},
        }

    if __opts__.get("test"):  # pylint: disable=undefined-variable
        return {
            "name": name,
            "result": None,
            "comment": f"package {name} would be installed at {desired}",
            "changes": {name: {"old": current.get(name), "new": desired}},
        }

    result = __salt__["dummy.package_install"](  # pylint: disable=undefined-variable
        name, version=desired
    )
    return {
        "name": name,
        "result": True,
        "comment": f"package {name} installed at {desired}",
        "changes": {name: {"old": current.get(name), "new": result.get(name, desired)}},
    }
