"""
End-to-end integration tests for the deny-by-default surface of
:func:`salt.loader.resource_modules` (issue #69881).

The per-resource execution loader must expose ONLY modules discovered
under ``resources/<rtype>/modules/`` overlay directories, plus the
``__minion__`` escape hatch.  Targeting a resource with a stock salt
execution module (``cmd.run``, ``grains.setval``, ``file.remove``, …)
must surface the "not supported for resource type" rejection at the
minion — never silently execute on the managing minion.

Runs against the real minion/master fixtures in :mod:`conftest`; the
``dummy`` resource type ships per-type ``test.py`` override only, so
these calls exercise the deny-by-default path for every other slot.
"""

import pytest

pytestmark = [pytest.mark.slow_test]


@pytest.mark.parametrize(
    "fun,args",
    [
        # ``cmd.run`` is the most dangerous stock leak — the reporter's
        # PoC ran ``cmd.run 'hostname; id; pwd'`` and got managing-minion
        # host identity attributed to the resource id.
        ("cmd.run", ["echo strict-resource-loader-canary"]),
        # ``grains.setval`` writes to the managing minion's grains file
        # (``/etc/salt/grains``) — silent misattribution + persistent
        # state mutation.
        ("grains.setval", ["strict_probe", "resource-leak"]),
        # ``file.remove`` is a destructive filesystem op on the managing
        # minion.  Just try to remove a benign path; the point is the
        # dispatch never reaches the function.
        ("file.remove", ["/tmp/strict-loader-nonexistent-canary"]),
        # ``sys.list_functions`` used to leak the full stock surface —
        # ~1300 functions — via the resource loader.  After the fix it's
        # rejected too (types that want introspection ship an override).
        ("sys.list_functions", []),
    ],
)
def test_stock_module_rejected_on_resource_target(salt_minion, salt_cli, fun, args):
    """
    ``salt <resource-id> <stock.fun> …`` returns the "not supported for
    resource type" rejection instead of silently executing on the
    managing minion.

    Regression guard for #69881.  Before the fix, the resource loader
    included every stock salt/modules/ file, so the dispatch happily
    ran the function in the managing minion process while attributing
    the return to the resource id.
    """
    ret = salt_cli.run(fun, *args, minion_tgt="dummy-01")
    # ret.data may be either the bare string (single-target) or a dict.
    if isinstance(ret.data, dict):
        payload = ret.data.get("dummy-01", ret.data)
    else:
        payload = ret.data
    assert isinstance(payload, str), (fun, ret.data)
    assert "not supported for resource type 'dummy'" in payload, (fun, payload)
    # Sanity: the response is keyed to the resource id, not the minion id.
    assert salt_minion.id not in (ret.data or {}), (fun, ret.data)


def test_per_type_override_reachable_on_resource_target(salt_minion, salt_cli):
    """
    Positive case: ``test.ping`` IS shipped as a per-type override at
    ``salt/resources/dummy/modules/test.py``, so it MUST be reachable
    on a dummy resource target.  Without this test, a regression that
    over-restricts the loader (e.g. drops every layer including the
    in-tree overlay) would still pass the deny-by-default tests above.
    """
    ret = salt_cli.run("test.ping", minion_tgt="dummy-01")
    assert ret.returncode == 0, ret
    if isinstance(ret.data, dict):
        payload = ret.data.get("dummy-01", ret.data)
    else:
        payload = ret.data
    assert payload is True, ret.data


def test_grains_setval_does_not_touch_managing_minion(
    salt_minion, salt_cli, salt_call_cli
):
    """
    ``salt <rid> grains.setval …`` used to write to the managing
    minion's persistent grains file.  Assert the grain the operator
    tried to set is NOT present in the managing minion's grains after
    the dispatch is rejected — the resource-loader guard is the only
    thing preventing the write, so any regression would show up here.
    """
    grain_key = "strict_loader_persistent_probe"
    grain_val = "resource-leak-must-not-persist"

    ret = salt_cli.run("grains.setval", grain_key, grain_val, minion_tgt="dummy-01")
    # The rejection may come back with a non-zero rc; either way the
    # write must not have happened.
    payload = ret.data
    if isinstance(payload, dict):
        payload = payload.get("dummy-01", payload)
    assert isinstance(payload, str), payload
    assert "not supported for resource type 'dummy'" in payload, payload

    # Verify the managing minion's grains do NOT carry the probe.
    grains_ret = salt_call_cli.run("grains.get", grain_key)
    assert grains_ret.returncode == 0, grains_ret
    # ``grains.get`` returns an empty string for a missing key.
    assert grains_ret.data in ("", None), (
        f"managing minion's grains carry {grain_key}={grains_ret.data!r} "
        "— the resource-loader guard leaked and grains.setval ran on the "
        "managing minion."
    )
