"""
Scenario: ``salt '*'`` against an offline managing minion must report that minion
*and* each configured resource id (from cached pillar), not only the minion row.

This guards :func:`salt.client._iter_failed_missing_returns` pillar-cache expansion
used when the mmap registry no longer lists the minion.
"""

import os
import textwrap
import time
import types

import pytest

import salt.cache
import salt.defaults.exitcodes
import salt.utils.files
from tests.conftest import FIPS_TESTRUN

pytestmark = [pytest.mark.slow_test]

_OFFLINE_MINION_ID = "offline-res-cli-minion"
_OFFLINE_DUMMY_IDS = ("off-cli-r1", "off-cli-r2", "off-cli-r3")


def _skip_if_cli_script_wrong_tree(salt_cli, master):
    """
    ``saltfactories`` writes ``cli_salt.py`` under a shared ``/tmp/stsuite/scripts``.
    If another worktree ran first, ``CODE_DIR`` can point at the wrong tree and
    this scenario would exercise stock Salt instead of this checkout.
    """
    try:
        script_path = salt_cli.get_script_path()
    except (AttributeError, FileNotFoundError, OSError):
        return
    try:
        with salt.utils.files.fopen(script_path, "r", encoding="utf-8") as fh:
            head = fh.read(1200)
    except OSError:
        return
    code_dir = str(master.factories_manager.code_dir)
    if code_dir not in head:
        pytest.skip(
            "Generated cli_salt.py does not embed this worktree's code_dir "
            f"({code_dir!r} not found in {script_path!r}). Remove or regenerate "
            "/tmp/stsuite/scripts (or run pytest with a fresh tmp root) so the "
            "salt CLI subprocess loads the same sources as this test process."
        )


def _assert_target_reported_missing(data, key):
    assert key in data, f"Expected {key!r} in CLI data keys {sorted(data)!r}"
    val = data[key]
    if val is True:
        pytest.fail(f"Expected {key!r} to be missing/offline, got True")
    if isinstance(val, str):
        low = val.lower()
        assert "did not return" in low or "no response" in low, val
    elif isinstance(val, dict):
        out = val.get("out")
        if out == "no_return":
            return
        ret = val.get("ret", "")
        if isinstance(ret, str) and "did not return" in ret.lower():
            return
        pytest.fail(f"Unexpected dict shape for {key!r}: {val!r}")
    else:
        # e.g. False from some formatters
        pass


@pytest.fixture(scope="module")
def offline_cli_stack(request, salt_factories):
    """
    Dedicated master (``minion_data_cache: true``) + one minion with three dummy
    resource ids in pillar only.
    """
    config_overrides = {
        "interface": "127.0.0.1",
        "transport": request.config.getoption("--transport"),
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        # Required so ``_resource_ids_from_minion_pillar_cache`` can resolve
        # resource ids after the minion process is gone.
        "minion_data_cache": True,
    }
    master = salt_factories.salt_master_daemon(
        "offline-cli-exp-master",
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    top = textwrap.dedent(
        f"""
        base:
          '{_OFFLINE_MINION_ID}':
            - offline_dummy_resources
        """
    )
    pillar_sls = textwrap.dedent(
        f"""
        resources:
          dummy:
            resource_ids:
              - {_OFFLINE_DUMMY_IDS[0]}
              - {_OFFLINE_DUMMY_IDS[1]}
              - {_OFFLINE_DUMMY_IDS[2]}
        """
    )
    with master.started(start_timeout=120):
        top_tf = master.pillar_tree.base.temp_file("top.sls", top)
        sls_tf = master.pillar_tree.base.temp_file(
            "offline_dummy_resources.sls", pillar_sls
        )
        with top_tf, sls_tf:
            minion = master.salt_minion_daemon(
                _OFFLINE_MINION_ID,
                overrides={
                    "fips_mode": FIPS_TESTRUN,
                    "encryption_algorithm": (
                        "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
                    ),
                    "signing_algorithm": (
                        "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
                    ),
                    "multiprocessing": False,
                },
                extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            )
            # Do not register remove_stale_minion_key on after_terminate: that runs
            # in the same turn as minion.terminate() and would delete the accepted
            # key before the offline ``salt '*'`` assertion (master would match zero
            # minions). Remove the key after the yield teardown instead.
            with minion.started(start_timeout=120):
                call = minion.salt_call_cli()
                ret = call.run("saltutil.refresh_pillar", wait=True, _timeout=120)
                assert ret.returncode == 0, ret
                ret = call.run("saltutil.sync_all", _timeout=120)
                assert ret.returncode == 0, ret
                # refresh_pillar uses AsyncPillar and does not write the master's
                # minion pillar cache (PillarCache.store). pillar.items forces a
                # sync compile on the master so offline expansion can read
                # ``resources`` via ``_resource_ids_from_minion_pillar_cache``.
                ret = call.run("pillar.items", _timeout=120)
                assert ret.returncode == 0, ret
                pdata = ret.data
                if isinstance(pdata, dict) and _OFFLINE_MINION_ID in pdata:
                    inner = pdata.get(_OFFLINE_MINION_ID)
                    if isinstance(inner, dict):
                        pdata = inner
                assert isinstance(pdata, dict), ret
                assert "resources" in pdata, list(pdata.keys())
                # Ensure the master's minion pillar bank matches what the LocalClient
                # reads during offline expansion (normalize cachedir like the salt CLI).
                _cache_opts = dict(master.config)
                _cache_opts["cachedir"] = os.path.abspath(_cache_opts["cachedir"])
                salt.cache.factory(_cache_opts).store(
                    "pillar", _OFFLINE_MINION_ID, pdata
                )
                time.sleep(3)

                # Prime master cache (grains + pillar) while minion is alive.
                ret = master.salt_cli(timeout=90).run(
                    "test.ping", minion_tgt=_OFFLINE_MINION_ID, _timeout=120
                )
                assert ret.returncode == 0, ret

                salt_cli = master.salt_cli(timeout=90)
                yield types.SimpleNamespace(
                    master=master,
                    minion=minion,
                    salt_cli=salt_cli,
                )
                pytest.helpers.remove_stale_minion_key(master, minion.id)


def test_wildcard_ping_then_offline_lists_minion_and_each_resource(
    offline_cli_stack,
):
    stack = offline_cli_stack
    salt_cli = stack.salt_cli
    minion = stack.minion
    _skip_if_cli_script_wrong_tree(salt_cli, stack.master)

    # --- While minion is up: prove connectivity (glob may omit resource rows
    # until the registry is warm; pillar + minion_data_cache are what matter
    # for the offline expansion path).
    ret0 = salt_cli.run("test.ping", minion_tgt=minion.id, _timeout=120)
    assert ret0.returncode == 0, ret0
    assert ret0.data is True, ret0

    ret = salt_cli.run(
        "--timeout=25",
        "test.ping",
        minion_tgt="*",
        _timeout=120,
    )
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, dict), ret
    assert minion.id in data, list(data)
    assert data[minion.id] is True

    # --- Stop minion: same glob must surface minion + each resource as missing.
    minion.terminate()

    ret2 = salt_cli.run(
        "--timeout=25",
        "test.ping",
        minion_tgt="*",
        _timeout=120,
    )
    assert ret2.returncode == salt.defaults.exitcodes.EX_GENERIC, ret2
    data2 = ret2.data
    assert isinstance(data2, dict), ret2

    _assert_target_reported_missing(data2, minion.id)
    for rid in _OFFLINE_DUMMY_IDS:
        _assert_target_reported_missing(data2, rid)
