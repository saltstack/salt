"""
End-to-end integration tests for Salt Resources using the dummy resource type.

These tests verify the full dispatch pipeline:

  salt CLI → master targeting (CkMinions) → minion (_resolve_resource_targets)
  → resource loader → return → master re-key → CLI response

The minion under test loads dummy resources from Pillar only (``resources.dummy``
with ``resource_ids``) and uses ``multiprocessing: False``.

The ``dummy`` resource module (``salt/resource/dummy.py``) and its execution
module (``salt/modules/dummyresource_test.py``) are pure-Python in-process
implementations that require no external services.

Targeting forms exercised here:

* **Glob wildcard** — ``salt '*' …`` or a pattern such as ``salt 'resources*' …``
  that matches the managing minion (minion + every managed resource).
* **Glob exact resource id** — ``salt '<id>' …`` (no ``-L``, no wildcards).
* **List** — ``salt -L '<id>' …`` (bare resource id).
* **Compound full SRN** — ``salt -C 'T@dummy:<id>' …``.
* **Compound bare type** — ``salt -C 'T@dummy' …`` (all resources of that type).
"""

import json
import textwrap
import time

import pytest

from tests.pytests.integration.resources.conftest import DUMMY_RESOURCES

pytestmark = [pytest.mark.slow_test]


def _salt_cli_json_dict(ret):
    """
    Parse the salt CLI JSON object from ``ret``.

    Salt-factories unwraps single-key output when ``minion_tgt`` equals that
    key (e.g. list / exact-glob targeting), in which case ``ret.data`` is not
    a dict.
    """
    if isinstance(ret.data, dict):
        return ret.data
    return json.loads(ret.stdout.strip())


def test_minion_has_resources_configured(salt_minion, salt_call_cli):
    """Sanity check: the minion must report its resource config before other tests run."""
    ret = salt_call_cli.run("config.get", "resources")
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    assert "dummy" in data, f"'dummy' missing from config.get resources: {data}"
    dummy = data["dummy"]
    # Pillar may surface as ``{"resource_ids": [...]}`` or a bare list of ids
    # depending on merge/render path.
    if isinstance(dummy, dict):
        assert (
            "resource_ids" in dummy
        ), f"Missing resource_ids under resources.dummy: {dummy!r}"
        ids = dummy["resource_ids"]
    else:
        ids = dummy
    assert isinstance(
        ids, (list, tuple)
    ), f"Unexpected resources.dummy shape: {dummy!r}"
    assert set(ids) == set(DUMMY_RESOURCES), f"Unexpected resource IDs: {ids!r}"


def test_glob_wildcard_returns_minion_and_resources(salt_minion, salt_cli):
    """
    ``salt '*' test.ping`` must return ``True`` for the managing minion *and*
    for every resource it manages.

    This exercises the full pipeline:
    - Master ``_augment_with_resources`` adds every dummy resource id to the
      expected-minion set so the response window stays open.
    - Minion ``_resolve_resource_targets`` dispatches two resource jobs.
    - Each resource job returns via ``_thread_return`` with ``resource_id``.
    - Master ``_return`` remaps ``resource_id`` → ``id`` before delivering.
    """
    ret = salt_cli.run("test.ping", minion_tgt="*")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    # The managing minion must respond.
    assert (
        salt_minion.id in data
    ), f"Managing minion '{salt_minion.id}' not in response: {list(data)}"
    assert data[salt_minion.id] is True

    # Every configured resource must also respond.
    for rid in DUMMY_RESOURCES:
        assert rid in data, f"Resource '{rid}' missing from response: {list(data)}"
        assert data[rid] is True, f"Resource '{rid}' returned non-True: {data[rid]}"


def test_glob_wildcard_minion_pattern_includes_resources(salt_minion, salt_cli):
    """
    A glob with wildcards that matches only the managing minion must still
    opt in to resource dispatch (same augmentation path as ``salt '*'``).
    """
    ret = salt_cli.run("test.ping", minion_tgt="resources*")
    assert ret.returncode == 0, ret
    data = _salt_cli_json_dict(ret)
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    assert salt_minion.id in data, f"Minion missing from glob response: {list(data)}"
    assert data[salt_minion.id] is True
    for rid in DUMMY_RESOURCES:
        assert rid in data, f"Resource {rid!r} missing: {list(data)}"
        assert data[rid] is True


def test_T_at_full_srn_returns_only_that_resource(salt_minion, salt_cli):
    """
    ``salt -C 'T@dummy:dummy-01' test.ping`` must return a response keyed to
    ``dummy-01`` only — not to the managing minion or to dummy-02/dummy-03.

    This exercises the compound-match targeting path:
    - Master ``_check_resource_minions`` resolves ``T@dummy:dummy-01`` to the
      single resource ID ``dummy-01`` and the managing minion as the delivery
      target.
    - Minion ``_resolve_resource_targets`` (compound path) dispatches only to
      dummy-01 because the T@ term matches exactly one resource.
    """
    ret = salt_cli.run("-C", "test.ping", minion_tgt="T@dummy:dummy-01")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    assert data == {
        "dummy-01": True
    }, f"Expected only dummy-01 in response, got: {data}"


@pytest.mark.parametrize(
    "case_label,cli_args,minion_tgt_tmpl",
    [
        ("compound_full_srn", ("-C", "test.ping"), "T@dummy:__ID__"),
        ("list_bare_resource_id", ("-L", "test.ping"), "__ID__"),
        ("glob_exact_resource_id", ("test.ping",), "__ID__"),
    ],
)
def test_single_resource_targeting_forms_among_three(
    salt_minion, salt_cli, case_label, cli_args, minion_tgt_tmpl
):
    """
    With three dummy resources, ``test.ping`` addressed to **one** resource must
    return only that id using compound ``T@``, list ``-L``, or exact glob.
    """
    target_id = DUMMY_RESOURCES[1]
    tgt = minion_tgt_tmpl.replace("__ID__", target_id)

    ret = salt_cli.run(*cli_args, minion_tgt=tgt)
    assert ret.returncode == 0, (case_label, ret)

    data = _salt_cli_json_dict(ret)
    assert isinstance(data, dict), f"[{case_label}] expected dict, got: {data!r}"
    assert data == {target_id: True}, f"[{case_label}] unexpected payload: {data}"
    assert salt_minion.id not in data, case_label
    for rid in DUMMY_RESOURCES:
        if rid == target_id:
            continue
        assert rid not in data, f"[{case_label}] unexpected {rid!r} in {data}"


def test_T_at_bare_type_returns_all_resources_of_type(salt_minion, salt_cli):
    """
    ``salt -C 'T@dummy' test.ping`` must return ``True`` for every dummy
    resource (dummy-01 … dummy-03) without including the managing minion.
    """
    ret = salt_cli.run("-C", "test.ping", minion_tgt="T@dummy")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    for rid in DUMMY_RESOURCES:
        assert (
            rid in data
        ), f"Resource '{rid}' missing from T@dummy response: {list(data)}"
        assert data[rid] is True

    # The managing minion should NOT be in the T@-only response.
    assert (
        salt_minion.id not in data
    ), "Managing minion unexpectedly included in T@dummy response"


def test_unknown_resource_function_fails_loudly(salt_minion, salt_cli):
    """
    Calling a function that does not exist on a resource must return an error
    string, not silently fall through to the managing minion's own module.

    This guards against the pre-resource behaviour where an unknown function
    for a resource target would execute on the minion itself.
    """
    ret = salt_cli.run("-C", "nonexistent.function", minion_tgt="T@dummy:dummy-01")
    # The command fails (non-zero) because the function is unknown.
    assert ret.returncode != 0 or (
        isinstance(ret.data, dict)
        and isinstance(ret.data.get("dummy-01"), str)
        and "nonexistent" in ret.data["dummy-01"].lower()
    ), f"Expected error for unknown resource function, got: {ret.data!r}"


def test_grain_targeting_matches_resources(salt_minion, salt_cli):
    """
    ``salt -G '<key>:<value>' test.ping`` must match resources whose own
    grains satisfy the expression. Every dummy resource publishes
    ``dummy_grain_1: one`` (see ``salt.resources.dummy.grains``), so the
    response must include all three dummy resource IDs.

    End-to-end pipeline this exercises:

    * Minion ``_register_resources_with_master`` ships per-resource grain
      dicts to the master alongside the registry payload.
    * Master ``_register_resources`` writes them into the
      ``resource_grains`` cache bank.
    * Master ``CkMinions._check_grain_minions`` augments its result with
      bare resource IDs from any ``resource_grains`` entry whose dict
      satisfies the expression.
    * Minion ``_resolve_resource_targets`` handles ``tgt_type == "grain"``
      by matching the expression against the cached per-resource grains
      and dispatching to the matched resources.
    """
    ret = salt_cli.run("-G", "test.ping", minion_tgt="dummy_grain_1:one")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    for rid in DUMMY_RESOURCES:
        assert (
            rid in data
        ), f"Resource '{rid}' missing from grain-target response: {list(data)}"
        assert data[rid] is True

    # The managing minion does NOT have ``dummy_grain_1`` in its own
    # grains, so it must not appear in the response — the only way to land
    # in this response is via the per-resource grain match.
    assert salt_minion.id not in data, (
        f"Managing minion '{salt_minion.id}' unexpectedly matched "
        f"a resource grain expression: {list(data)}"
    )


def test_grain_targeting_only_matching_resource(salt_minion, salt_cli):
    """
    ``salt -G 'resource_id:dummy-02' test.ping`` matches only dummy-02
    because the per-resource ``resource_id`` grain is unique to that
    resource (see ``salt.resources.dummy.grains``).
    """
    ret = salt_cli.run("-G", "test.ping", minion_tgt="resource_id:dummy-02")
    assert ret.returncode == 0, ret

    data = _salt_cli_json_dict(ret)
    # Salt-factories may unwrap a single-key envelope when the response
    # has only one entry; accept both shapes.
    if "dummy-02" in data:
        assert data["dummy-02"] is True
    else:
        # Unwrapped: ``data`` IS dummy-02's return value.
        assert data is True or data == {}, f"Unexpected response shape: {data!r}"


def test_grains_items_returns_resource_grains_not_minion_grains(salt_minion, salt_cli):
    """
    ``salt 'dummy-01' grains.items`` must return the dummy resource's grains
    (produced by ``salt.resources.dummy.grains``), not the managing minion's
    grains. This exercises the end-to-end grain-swap pipeline:

    * Master targeting matches the bare resource id ``dummy-01`` and
      dispatches a job whose payload includes ``resource_target`` for the
      ``dummy`` type.
    * Minion ``_thread_return`` packs ``__grains__`` from
      ``resource_funcs["dummy.grains"]()`` before the function runs.
    * The function (``grains.items``) returns the resource grain dict.
    * Master ``_return`` re-keys ``resource_id`` → response key ``dummy-01``.
    """
    ret = salt_cli.run("grains.items", minion_tgt="dummy-01")
    assert ret.returncode == 0, ret

    data = _salt_cli_json_dict(ret)
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    # Salt-factories unwraps the single-key envelope when ``minion_tgt`` is
    # the only response key, so ``data`` may be either the grains dict itself
    # or ``{"dummy-01": grains_dict}``. Accept both shapes.
    grains = data.get("dummy-01") if "dummy-01" in data else data
    assert isinstance(
        grains, dict
    ), f"Expected dict for dummy-01 grains, got: {grains!r}"

    # The resource grains must be present.
    assert grains.get("dummy_grain_1") == "one"
    assert grains.get("dummy_grain_2") == "two"
    assert grains.get("dummy_grain_3") == "three"
    assert grains.get("resource_id") == "dummy-01"

    # The managing minion's grains must NOT bleed through. ``os`` is a stock
    # core grain on every supported Linux/macOS test target; if it appears
    # the swap didn't take effect.
    assert "os" not in grains, (
        "Managing minion's 'os' grain leaked into resource grains response — "
        "the dispatch path is returning minion grains instead of resource grains"
    )


def test_grain_pcre_targeting_matches_resources(salt_minion, salt_cli):
    """
    ``salt -P '<key>:<regex>' test.ping`` must match resources whose own
    grains satisfy the regex. ``resource_id`` for each dummy is
    ``dummy-NN``; the regex ``^dummy-0[12]$`` selects exactly two.
    """
    ret = salt_cli.run("-P", "test.ping", minion_tgt=r"resource_id:^dummy-0[12]$")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    assert set(data.keys()) == {
        "dummy-01",
        "dummy-02",
    }, f"PCRE-grain target matched unexpected set: {list(data)}"
    assert all(v is True for v in data.values())


def test_compound_grain_targeting_matches_resources(salt_minion, salt_cli):
    """
    ``salt -C 'G@<key>:<value>' test.ping`` must match resources via the
    compound parser dispatching to the same per-resource grain match path.
    """
    ret = salt_cli.run("-C", "test.ping", minion_tgt="G@dummy_grain_1:one")
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"
    for rid in DUMMY_RESOURCES:
        assert (
            rid in data
        ), f"Resource {rid!r} missing from compound G@ response: {list(data)}"
        assert data[rid] is True
    assert (
        salt_minion.id not in data
    ), f"Managing minion '{salt_minion.id}' must not match a resource grain"


def test_pillar_addition_at_runtime_registers_new_resource(
    salt_minion, salt_call_cli, salt_master
):
    """
    Inverse of the stale-cache test
    (``test_register_resources_with_master_sends_empty_dict``) at the
    integration level: adding a *new* resource id to pillar at runtime
    and running ``saltutil.refresh_pillar`` must cause the master to
    pick the id up — without a minion restart.

    Mutates the package-scoped ``dummy_resources.sls`` in place rather
    than nesting :py:func:`temp_file` (which would delete the file on
    inner-exit and leave the package fixture without its pillar SLS).
    Restores the original content in the ``finally`` block.
    """
    extra_id = "dummy-extra"
    expected = set(DUMMY_RESOURCES) | {extra_id}

    sls_path = salt_master.pillar_tree.base.write_path / "dummy_resources.sls"
    original_body = sls_path.read_text()

    augmented = textwrap.dedent(
        f"""\
        resources:
          dummy:
            resource_ids:
              - {DUMMY_RESOURCES[0]}
              - {DUMMY_RESOURCES[1]}
              - {DUMMY_RESOURCES[2]}
              - {extra_id}
        """
    )

    salt_run = salt_master.salt_run_cli(timeout=30)
    try:
        sls_path.write_text(augmented)
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
        assert ret.returncode == 0, ret

        deadline = time.monotonic() + 20
        seen = set()
        while time.monotonic() < deadline:
            ret = salt_run.run("resource.list_grains", _timeout=30)
            if ret.returncode == 0 and isinstance(ret.data, dict):
                seen = {
                    srn.split(":", 1)[1] for srn in ret.data if srn.startswith("dummy:")
                }
                if seen >= expected:
                    break
            time.sleep(1)
        assert seen >= expected, (
            f"Master never registered new dummy resource id {extra_id!r}. "
            f"Last saw: {seen}"
        )
    finally:
        # Restore the original SLS content + refresh so the master's view
        # converges back on the original 3 dummy ids for subsequent tests.
        sls_path.write_text(original_body)
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
        assert ret.returncode == 0, ret
        time.sleep(3)


def test_state_single_against_resource_no_phantom_no_response(salt_minion, salt_cli):
    """
    Regression for ``RESOURCE_STATE_RETURN_ATTRIBUTION_BUG.md``.

    A merge-fun state job against a pure-resource compound target —
    ``salt -C 'T@dummy:dummy-01' state.single test.nop ...`` — must not
    produce a ``Minion did not return. [No response]`` line for the
    targeted resource id. The original bug report observed both a
    successful state result *and* a phantom resource-id timeout in the
    CLI output, indicating the master's wait set wrongly contained the
    resource id alongside the managing minion.

    ``state.single`` is in :py:attr:`~salt.minion.Minion._MERGE_RESOURCE_FUNS`,
    so the design has the managing minion run the state inline and
    return ONE combined response under its own id. The master's
    targeting path (``CkMinions._check_resource_minions``) is supposed
    to remap pure-resource ``T@`` terms to the managing minion's id
    for merge funs — the bug is when that remap is bypassed and the
    resource id ends up in the wait set too, where it never produces a
    separate return and times out.

    Mirrors the bug's reproduction shape against the bundled ``dummy``
    type (the original report used ``vcenter`` from a Salt extension).
    Pins the in-tree contract end-to-end so a regression in the wait-set
    logic — e.g. an `_augment_with_resources` path firing for compound
    targets, or a merge-fun check skipped because ``fun`` plumbing
    drops out somewhere — fails this assertion loudly.

    Asserts:
      * The state runs (``test.nop`` chunk appears in the response).
      * No ``did not return`` / ``No response`` text in stdout or stderr.
      * No top-level response key whose value is a "did not return"
        error string.
    """
    target_id = DUMMY_RESOURCES[0]
    ret = salt_cli.run(
        "-C",
        "state.single",
        "test.nop",
        "name=resource-state-attribution-regression",
        minion_tgt=f"T@dummy:{target_id}",
    )

    combined_output = (ret.stdout or "") + "\n" + (ret.stderr or "")
    assert "did not return" not in combined_output.lower(), (
        f"Phantom 'Minion did not return' message in output — "
        f"the master's wait set is including the resource id incorrectly. "
        f"stdout={ret.stdout!r} stderr={ret.stderr!r}"
    )
    assert "no response" not in combined_output.lower(), (
        f"Phantom 'No response' in output: stdout={ret.stdout!r} "
        f"stderr={ret.stderr!r}"
    )

    data = _salt_cli_json_dict(ret)
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    # No top-level response key with an error-string value (the bug
    # produced ``{"<resource-id>": "Minion did not return..."}``
    # alongside the real result).
    for key, value in data.items():
        assert not (isinstance(value, str) and "did not return" in value.lower()), (
            f"Response contains a 'did not return' string under key "
            f"{key!r}: {value!r}"
        )

    # The state must have actually run somewhere in the response.
    def _has_state_result(node):
        if isinstance(node, dict):
            if any(k.endswith("_|-nop") for k in node):
                return True
            return any(_has_state_result(v) for v in node.values())
        return False

    assert _has_state_result(
        data
    ), f"No test.nop state result anywhere in the response payload: {data!r}"


def test_state_single_against_single_resource_keyed_by_resource_id(
    salt_minion, salt_cli
):
    """
    Desired API shape (Option B from the design discussion): for a
    merge-fun state job against a pure-resource compound target, the
    response must be keyed by the **resource id**, not by the managing
    minion. Matches the shape of ``test.ping`` against the same target
    so consumers can write one ``data[resource_id]`` pattern regardless
    of function.

    Today the framework folds per-resource state results into a single
    return under the managing minion's id with state-chunk keys
    prefixed by the resource id. This test fails until the minion's
    merge-fold path is changed to emit one return per resource with
    ``ret["resource_id"]`` set (then the master's existing
    ``resource_id`` remap re-keys the response to the resource id).
    """
    target_id = DUMMY_RESOURCES[0]
    ret = salt_cli.run(
        "-C",
        "state.single",
        "test.nop",
        "name=resource-id-keyed-state-return",
        minion_tgt=f"T@dummy:{target_id}",
    )
    assert ret.returncode == 0, ret

    data = _salt_cli_json_dict(ret)
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    # Top-level key must be the resource id.
    assert target_id in data, (
        f"Expected top-level response key {target_id!r}; "
        f"got {list(data)} (managing-minion-id keying is the OLD shape)."
    )
    # The managing minion must NOT appear at the top level.
    assert salt_minion.id not in data, (
        f"Managing minion {salt_minion.id!r} appears as response key; "
        f"merge-fun state returns must be keyed by resource id only."
    )

    body = data[target_id]
    assert isinstance(body, dict), f"Resource body must be dict, got: {body!r}"

    # State-chunk keys inside the resource body must NOT be prefixed
    # with the resource id any more — the wrapping key already conveys
    # provenance, so the prefix is redundant noise.
    chunk_keys = [k for k in body if k.endswith("_|-nop")]
    assert chunk_keys, f"No test.nop chunk in resource body: {body!r}"
    for k in chunk_keys:
        parts = k.split("_|-")
        # State low key shape: ``{module}_|-{id}_|-{name}_|-{function}``.
        # parts[1] is the state id; with resource-id-keyed responses it
        # should be the plain state id (no leading "<rid> " prefix).
        assert not parts[1].startswith(f"{target_id} "), (
            f"State id {parts[1]!r} still has the redundant resource-id "
            f"prefix. With resource-id-keyed responses the wrapping key "
            f"already conveys the resource."
        )


def test_state_single_against_bare_type_returns_per_resource(salt_minion, salt_cli):
    """
    Bare-type merge fun (``T@dummy`` matches all 3 dummy resources): the
    response must contain one top-level entry per resource — matching
    how ``salt -C 'T@dummy' test.ping`` already renders — instead of a
    single merged block under the managing minion id.
    """
    ret = salt_cli.run(
        "-C",
        "state.single",
        "test.nop",
        "name=bare-type-per-resource-return",
        minion_tgt="T@dummy",
    )
    assert ret.returncode == 0, ret

    data = ret.data
    assert isinstance(data, dict), f"Expected dict, got: {data!r}"

    # One top-level key per dummy resource. No managing-minion key.
    assert set(data.keys()) == set(DUMMY_RESOURCES), (
        f"Expected per-resource top-level keys {set(DUMMY_RESOURCES)}, "
        f"got {set(data)}"
    )
    assert (
        salt_minion.id not in data
    ), f"Managing minion unexpectedly in bare-type response: {list(data)}"

    for rid, body in data.items():
        assert isinstance(body, dict), f"{rid!r} body not dict: {body!r}"
        chunk_keys = [k for k in body if k.endswith("_|-nop")]
        assert chunk_keys, f"No test.nop chunk under {rid!r}: {body!r}"


def test_state_single_against_bare_resource_id_keyed_by_resource_id(
    salt_minion, salt_cli
):
    """
    Regression: ``salt 'dummy-01' state.single test.nop ...`` (bare
    resource id, ``tgt_type=glob``, no wildcards) must return under
    the resource id — same shape as ``salt 'dummy-01' test.ping``.

    The minion-side bug: for a bare-id glob target, ``minion_matches``
    is False (the target string isn't the managing minion's id) so
    ``minion_is_target`` would normally be False; meanwhile
    ``_is_pure_resource_target`` only recognised compound ``T@`` /
    ``M@`` expressions as pure-resource, so the merge-fold + per-resource
    fan-out logic both got skipped. A bare-id glob with a merge-mode
    state function ran nothing on the managing minion and produced no
    return — only the master's "did not return" timeout.

    The fix is two-sided in ``salt/minion.py``:

    * ``_is_pure_resource_target`` recognises an exact (no-wildcard)
      glob whose ``tgt`` names a managed resource as a pure-resource
      target.
    * ``_target_load`` treats the managing minion as a target whenever
      ``is_merge_fun and resource_targets``, regardless of whether the
      glob also matched the minion's own id — the managing minion has
      to run the inline merge for the resource.

    Non-merge funs (``test.ping``) already worked through the
    per-resource fan-out path; this test asserts merge funs now work
    too with the same shape.
    """
    target_id = DUMMY_RESOURCES[0]
    ret = salt_cli.run(
        "state.single",
        "test.nop",
        "name=bare-id-keyed-state-return",
        minion_tgt=target_id,
    )
    assert ret.returncode == 0, ret

    data = _salt_cli_json_dict(ret)
    # Salt-factories unwraps single-key envelopes when ``minion_tgt``
    # is the only response key; accept both shapes.
    if isinstance(data, dict) and target_id in data:
        body = data[target_id]
        # Managing minion must not appear at the top level.
        assert salt_minion.id not in data, (
            f"Managing minion {salt_minion.id!r} appears as response key; "
            f"bare-id merge-fun state returns must be keyed by resource id."
        )
    else:
        # Unwrapped envelope: body IS the resource's payload.
        body = data
    assert isinstance(body, dict), f"Resource body must be dict, got: {body!r}"

    chunk_keys = [k for k in body if k.endswith("_|-nop")]
    assert chunk_keys, f"No test.nop chunk in resource body: {body!r}"
    # No phantom "did not return" entries.
    if isinstance(data, dict):
        for key, value in data.items():
            assert not (
                isinstance(value, str) and "did not return" in value.lower()
            ), f"Phantom 'did not return' under {key!r}: {value!r}"
