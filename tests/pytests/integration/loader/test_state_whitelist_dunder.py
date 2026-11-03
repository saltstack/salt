"""
Integration tests for the ``whitelist_modules`` propagation into the
state loader and the Jinja attribute-style escape hatch closure.

Sister to :mod:`tests.pytests.integration.loader.test_module_whitelist_dunder`,
which already covers the exec-module ``__salt__`` composition path.  This
module exercises:

  * Trusted shipped state modules composing with non-whitelisted execution
    modules internally (``file.managed`` -> ``__salt__['file.source_list']``).
  * The ``salt.states.module.run`` escape hatch staying gated.
  * Jinja attribute-style access (``{{ salt.cmd.run('id') }}``) being
    blocked at render time.
"""

import pytest

from tests.conftest import FIPS_TESTRUN


@pytest.fixture
def whitelisted_minion(salt_master):
    """
    A minion whose ``whitelist_modules`` allows the minimum needed to
    render and execute an SLS but excludes ``cmd`` -- the canonical
    escape target.  ``file`` IS on the whitelist so ``file.managed`` can
    be *declared* in an SLS; the point of the tests below is that its
    *internal* ``__salt__['file.source_list']`` lookup still works even
    though ``salt.modules.file`` (the exec module) has plenty of members
    that other minions might not want on the wire.
    """
    # Note: ``file`` is *not* on the whitelist.  The state loader lookup
    # (which uses ``self.states`` -- a separate LazyLoader without
    # whitelist filtering) can still find ``file.managed`` because state
    # modules are not the same loader as exec modules.  The bug we're
    # closing is the state's *internal* ``__salt__['file.source_list']``
    # lookup, which used to hit the wire-filtered exec loader and
    # KeyError; with the two-loader propagation, ``__salt__`` inside
    # state modules is the unfiltered inner dunder.
    minion = salt_master.salt_minion_daemon(
        "test-state-whitelist-dunder-minion",
        overrides={
            "whitelist_modules": [
                "test",
                "saltutil",
                "state",
                "config",
                "grains",
                "pillar",
                "slsutil",
                # ``module`` state -> tested that its dispatch stays
                # wire-filtered.
                "module",
            ],
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with minion.started():
        yield minion


# ---------------------------------------------------------------------------
# Trusted state-module internal composition
# ---------------------------------------------------------------------------


def test_file_managed_reaches_nonwhitelisted_exec_module(
    salt_cli, salt_master, whitelisted_minion, tmp_path
):
    """
    ``file.managed`` internally calls ``__salt__['file.source_list']``.
    Under ``whitelist_modules`` set as above, that lookup would raise
    ``KeyError`` under the pre-fix single-loader model (the wire-filtered
    loader has no ``file.source_list`` entry once ``file`` is only
    partially exposed).  With the two-loader propagation into the state
    loader, ``__salt__`` on state modules is the unfiltered inner loader
    and the state runs cleanly end-to-end.
    """
    target = tmp_path / "marker"
    sls = f"""
create_marker:
  file.managed:
    - name: {target}
    - contents: 'ok'
    - makedirs: True
"""
    ret = salt_cli.run("state.template_str", sls, minion_tgt=whitelisted_minion.id)
    assert isinstance(ret.data, dict), ret.stdout
    (chunk_id,) = list(ret.data.keys())
    assert ret.data[chunk_id]["result"] is True, ret.data[chunk_id]
    assert target.is_file()
    assert target.read_text().rstrip() == "ok"


# ---------------------------------------------------------------------------
# ``module.run`` escape hatch closure
# ---------------------------------------------------------------------------


def test_module_run_of_nonwhitelisted_exec_module_is_denied(
    salt_cli, whitelisted_minion
):
    """
    ``module.run: cmd.run: ...`` must be reported as an unavailable
    function.  ``salt.states.module.run`` dispatches SLS-supplied names
    through ``__wire_salt__`` (the whitelist-filtered loader) even though
    the surrounding state module has an unfiltered ``__salt__``, so the
    escape hatch stays closed.
    """
    sls = """
try_escape:
  module.run:
    - cmd.run:
      - name: 'echo pwned'
"""
    ret = salt_cli.run("state.template_str", sls, minion_tgt=whitelisted_minion.id)
    assert isinstance(ret.data, dict), ret.stdout
    (chunk_id,) = list(ret.data.keys())
    chunk = ret.data[chunk_id]
    assert chunk["result"] is False
    assert "cmd.run" in chunk["comment"] or "Unavailable" in chunk["comment"]


# ---------------------------------------------------------------------------
# Jinja attribute-style escape hatch closure
# ---------------------------------------------------------------------------


def test_jinja_attribute_style_nonwhitelisted_render_fails(
    salt_cli, whitelisted_minion
):
    """
    ``{{ salt.cmd.run(...) }}`` (attribute style, dotted-module) used to
    bypass ``whitelist_modules`` -- ``LazyLoader.__getattr__`` skipped
    the gate that ``__getitem__`` enforced via ``_load``.  Rendering the
    template must now fail at compile time with an ``UndefinedError`` /
    ``no attribute 'cmd'`` error.
    """
    template = (
        "{% set r = salt.cmd.run('id') %}\n"
        "probe:\n"
        "  test.nop:\n"
        "    - name: {{ r }}\n"
    )
    ret = salt_cli.run("state.template_str", template, minion_tgt=whitelisted_minion.id)
    text = str(ret.data or ret.stdout)
    assert "cmd" in text
    assert "UndefinedError" in text or "no attribute" in text or "not found" in text


def test_state_apply_without_config_on_whitelist(
    salt_cli, salt_master, whitelisted_minion, tmp_path
):
    """
    VCOPS-90587 round 3: ``state.compile_high_data`` reads
    ``config.option('state_aggregate')`` via the state engine.  Under a
    whitelist that omits ``config`` (the shipped minion's config module),
    the pre-round-3 code KeyError'd at compile time and every state
    apply reverted to all-ERROR.  ``_trusted_functions`` routes the read
    through the unfiltered inner exec loader so the compile succeeds
    even without ``config`` on the wire whitelist.

    The ``whitelisted_minion`` fixture already excludes ``config``; if
    this test passes end-to-end, the trusted-internal path is intact.
    """
    target = tmp_path / "state-apply-marker"
    sls = f"""
create_via_state_apply:
  file.managed:
    - name: {target}
    - contents: 'state-apply-ok'
    - makedirs: True
"""
    ret = salt_cli.run("state.template_str", sls, minion_tgt=whitelisted_minion.id)
    assert isinstance(ret.data, dict), ret.stdout
    (chunk_id,) = list(ret.data.keys())
    assert ret.data[chunk_id]["result"] is True, ret.data[chunk_id]
    assert target.is_file()


def test_wire_dispatch_of_nonwhitelisted_is_denied(salt_cli, whitelisted_minion):
    """
    VCOPS-90587 round 3: even though salt-core internal composition now
    routes through ``_trusted_functions`` (unfiltered), direct wire
    dispatch of a non-whitelisted module must still be denied.  Proves
    the trusted-internal channel didn't punch a hole in the wire
    boundary.  ``network`` is not on the fixture's whitelist.
    """
    ret = salt_cli.run(
        "network.interfaces", minion_tgt=whitelisted_minion.id, _timeout=15
    )
    data = str(ret.data or "")
    assert "not available" in data or "did not return" in data


def test_jinja_attribute_style_whitelisted_still_renders(salt_cli, whitelisted_minion):
    """
    Sanity: ``{{ salt.grains.get('id') }}`` (attribute style, whitelisted)
    must keep rendering.  The attribute-style gate is by-name, so a
    whitelisted module still resolves via ``LoadedMod`` and its
    per-function ``__getattr__`` (which itself dispatches through
    ``__getitem__`` -> the whitelist-permitted ``_load`` path).
    """
    template = (
        "{% set r = salt.grains.get('id') %}\n"
        "probe:\n"
        "  test.nop:\n"
        "    - name: {{ r }}\n"
    )
    ret = salt_cli.run("state.template_str", template, minion_tgt=whitelisted_minion.id)
    assert isinstance(ret.data, dict), ret.stdout
    (chunk_id,) = list(ret.data.keys())
    assert ret.data[chunk_id]["result"] is True
    assert ret.data[chunk_id]["name"] == whitelisted_minion.id
