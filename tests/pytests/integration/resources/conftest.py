"""
Integration test fixtures for Salt Resources.

Spins up a master and a minion whose dummy resources (dummy-01 … dummy-03) are
declared only in Pillar under ``resources:`` — not in the minion config file.
All tests in this package run against these two daemons.
"""

import textwrap
import time

import pytest

from tests.conftest import FIPS_TESTRUN

MINION_ID = "resources-minion"
MINION_ID_2 = "resources-minion-2"
MINION_ID_DYN = "resources-minion-dyn"

# Dummy resource IDs that the minion manages in every test in this package.
DUMMY_RESOURCES = ["dummy-01", "dummy-02", "dummy-03"]
# Disjoint resource set for the optional second minion. Tests that don't
# request ``salt_minion_2`` never see these.
DUMMY_RESOURCES_2 = ["dummy-04", "dummy-05"]


@pytest.fixture(scope="package")
def _shared_pillar_top(salt_master):
    """
    Single shared ``top.sls`` listing every minion id the test package
    may use. Each minion's pillar SLS file is provided by its own
    fixture (``pillar_tree_dummy_resources``, ``..._dynamic_resources``,
    etc.); if a minion's SLS doesn't exist (because its fixture wasn't
    requested in this session) the top.sls entry is inert — the minion
    is never started so its pillar is never compiled.

    Centralizing top.sls prevents multiple fixtures from clobbering
    each other via ``temp_file``: when one module-scoped fixture's
    temp_file exits it removes the top.sls; without this central
    fixture there is no replay to restore the package-level entries.
    """
    top_file = textwrap.dedent(
        f"""
        base:
          '{MINION_ID}':
            - dummy_resources
          '{MINION_ID_2}':
            - dummy_resources_2
          '{MINION_ID_DYN}':
            - dynamic_resources
          '{MINION_ID_CUSTOM_KEY}':
            - custom_key_resources
        """
    )
    with salt_master.pillar_tree.base.temp_file("top.sls", top_file):
        yield


@pytest.fixture(scope="package")
def pillar_tree_dummy_resources(salt_master, _shared_pillar_top):
    """
    Pillar SLS declaring ``resources.dummy.resource_ids`` for the
    primary and optional second dummy minions. Top.sls comes from
    :func:`_shared_pillar_top`.
    """
    pillar_sls = textwrap.dedent(
        """
        resources:
          dummy:
            resource_ids:
              - dummy-01
              - dummy-02
              - dummy-03
        """
    )
    pillar_sls_2 = textwrap.dedent(
        """
        resources:
          dummy:
            resource_ids:
              - dummy-04
              - dummy-05
        """
    )
    sls_tempfile = salt_master.pillar_tree.base.temp_file(
        "dummy_resources.sls", pillar_sls
    )
    sls_tempfile_2 = salt_master.pillar_tree.base.temp_file(
        "dummy_resources_2.sls", pillar_sls_2
    )
    with sls_tempfile, sls_tempfile_2:
        yield


@pytest.fixture(scope="package")
def salt_master(request, salt_factories):
    config_overrides = {
        "interface": "127.0.0.1",
        "transport": request.config.getoption("--transport"),
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "resources-master",
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="package")
def salt_minion(salt_master, pillar_tree_dummy_resources):
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        # Use threads (not processes) — this is the path our Race 1/Race 2 fixes
        # target and the most common deployment mode for resource-managing minions.
        "multiprocessing": False,
    }
    factory = salt_master.salt_minion_daemon(
        MINION_ID,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started(start_timeout=120):
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
        assert ret.returncode == 0, ret
        assert ret.data is True, ret
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        # The minion fires _register_resources_with_master() as a background
        # task on connect.  Waiting briefly ensures the master cache is
        # populated before tests run (typically completes in < 1 s, but the
        # sync_all above already takes several seconds so this is a safety net).
        time.sleep(3)
        yield factory


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    assert salt_master.is_running()
    return salt_master.salt_cli(timeout=60)


@pytest.fixture(scope="package")
def salt_call_cli(salt_minion):
    assert salt_minion.is_running()
    return salt_minion.salt_call_cli(timeout=60)


# ---------------------------------------------------------------------------
# Synthetic ``dynamic_test`` resource type
# ---------------------------------------------------------------------------
#
# A test-only resource type whose ``discover()`` reads its ids from a
# top-level pillar key (``_dynamic_test_ids``) — NOT from the standard
# ``resources:`` subtree. That gives us a way to exercise the
# "discover is the sole source of ids; pillar's resources subtree only
# enables the type" code path end-to-end. No shipping resource type does
# this today; dummy and ssh both re-read pillar's resources subtree.
#
# The type's source is injected into the master's file_roots via
# ``temp_file`` and synced down to the minion via
# ``saltutil.sync_resources``. Nothing lands in the source tree.

DYNAMIC_TEST_RTYPE = "dynamic_test"

DYNAMIC_TEST_SOURCE = '''\
"""
Test-only resource type whose ``discover()`` reads ids from a top-level
pillar key (``_dynamic_test_ids``) rather than the standard ``resources:``
subtree. Used by ``test_dynamic_discovery.py`` to exercise the
"discover is authoritative for ids" code path end-to-end.
"""

import logging

log = logging.getLogger(__name__)


def __virtual__():
    return True


def init(opts):
    __context__["dynamic_test"] = {"initialized": True}


def initialized():
    return __context__.get("dynamic_test", {}).get("initialized", False)


def discover(opts):
    """Return ids from the top-level ``_dynamic_test_ids`` pillar key.

    NOT from ``opts["pillar"]["resources"]["dynamic_test"]`` — this is
    the whole point of the type.
    """
    ids = opts.get("pillar", {}).get("_dynamic_test_ids", []) or []
    log.debug("dynamic_test discover() returning: %s", ids)
    return list(ids)


def grains():
    return {"dynamic_test_id": __resource__["id"]}


def ping():
    return True


def shutdown(opts):
    __context__.pop("dynamic_test", None)
'''


@pytest.fixture(scope="module")
def dynamic_test_type(salt_master):
    """
    Place the synthetic dynamic_test resource type in the master's
    file_roots under ``_resources/dynamic_test/__init__.py`` so a minion
    can pull it down with ``saltutil.sync_resources``.

    Module-scoped so the file is present for the whole minion lifetime.
    Tests don't mutate the type's body — only the ``_dynamic_test_ids``
    pillar key that the type's ``discover()`` reads.
    """
    with salt_master.state_tree.base.temp_file(
        "_resources/dynamic_test/__init__.py", DYNAMIC_TEST_SOURCE
    ) as path:
        yield path


def sync_resources_and_refresh(salt_call_cli, timeout=120):
    """Helper: sync resources and trigger re-discovery+re-registration.

    Used by tests that mutate the dynamic_test ids file or pillar and
    need the master to pick up the change.
    """
    ret = salt_call_cli.run("saltutil.sync_resources", _timeout=timeout)
    assert ret.returncode == 0, ret
    ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=timeout)
    assert ret.returncode == 0, ret
    # Allow the background _register_resources_with_master to land.
    time.sleep(3)


def _clear_minion_resource_registration(
    salt_master, salt_call_cli, sls_name, empty_body, timeout=60
):
    """
    Force a minion to send an empty resource registration to the master.

    Used in fixture teardown so a minion that's about to terminate
    doesn't leave stale ``resource_grains`` bank entries that confuse
    later tests' targeting. Writes a temp ``sls_name`` with an empty
    pillar body, runs ``saltutil.refresh_pillar`` on the minion so
    ``_discover_resources`` returns nothing, and waits briefly for
    ``_register_resources_with_master`` to land. Best-effort: failures
    are swallowed because the alternative is leaving a noisy traceback
    in the teardown of an otherwise green test.
    """
    try:
        with salt_master.pillar_tree.base.temp_file(sls_name, empty_body):
            salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=timeout)
            time.sleep(3)
    except Exception:  # pylint: disable=broad-except
        pass


@pytest.fixture(scope="module")
def pillar_tree_dynamic_resources(salt_master, _shared_pillar_top):
    """
    Pillar SLS for the dynamic_test minion: enables the
    ``dynamic_test`` resource type in the standard ``resources:`` tree
    (no ids declared there) and seeds ``_dynamic_test_ids`` at the top
    level — that's what ``dynamic_test.discover()`` reads.

    Top.sls comes from :func:`_shared_pillar_top`. Initial id list is
    empty; tests use ``write_dynamic_ids_pillar`` to rewrite the SLS
    and call ``saltutil.refresh_pillar``.
    """
    pillar_sls = textwrap.dedent(
        """
        resources:
          dynamic_test: {}
        _dynamic_test_ids: []
        """
    )
    with salt_master.pillar_tree.base.temp_file("dynamic_resources.sls", pillar_sls):
        yield


def write_dynamic_ids_pillar(salt_master, ids):
    """Return a temp_file context manager that swaps the dynamic_test
    pillar to declare ``_dynamic_test_ids: ids``. Caller owns the
    context (use with ``with ...``) so cleanup restores the prior
    contents."""
    body = textwrap.dedent(
        f"""
        resources:
          dynamic_test: {{}}
        _dynamic_test_ids: {list(ids)!r}
        """
    )
    return salt_master.pillar_tree.base.temp_file("dynamic_resources.sls", body)


MINION_ID_CUSTOM_KEY = "resources-minion-custom-key"
CUSTOM_PILLAR_KEY = "salt_resources"
CUSTOM_KEY_DUMMY_RESOURCES = ["custom-01", "custom-02"]


@pytest.fixture(scope="module")
def pillar_tree_custom_key_resources(salt_master, _shared_pillar_top):
    """
    Pillar SLS for the custom-key minion: declares dummy resources
    under a NON-default top-level key (``salt_resources``). Also adds
    an empty ``resources:`` block (the framework's default key) so we
    can assert the minion ignores the default when configured to use
    the alternate key.

    Top.sls comes from :func:`_shared_pillar_top`.
    """
    pillar_sls = textwrap.dedent(
        f"""
        resources: {{}}
        {CUSTOM_PILLAR_KEY}:
          dummy:
            resource_ids:
              - {CUSTOM_KEY_DUMMY_RESOURCES[0]}
              - {CUSTOM_KEY_DUMMY_RESOURCES[1]}
        """
    )
    with salt_master.pillar_tree.base.temp_file("custom_key_resources.sls", pillar_sls):
        yield


@pytest.fixture(scope="module")
def salt_minion_custom_pillar_key(salt_master, pillar_tree_custom_key_resources):
    """
    Minion whose ``resource_pillar_key`` is overridden to
    ``salt_resources``. Verifies discovery + registration + targeting
    work end-to-end against a non-default key.
    """
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        "multiprocessing": False,
        "resource_pillar_key": CUSTOM_PILLAR_KEY,
    }
    factory = salt_master.salt_minion_daemon(
        MINION_ID_CUSTOM_KEY,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started(start_timeout=240):
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
        assert ret.returncode == 0, ret
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        time.sleep(3)
        try:
            yield factory
        finally:
            # Clear the master's resource_grains bank of this minion's
            # entries BEFORE shutdown. Without this, the master keeps
            # ``dummy:custom-01`` / ``dummy:custom-02`` registered and
            # a later test querying ``-G dummy_grain_1:one`` will wait
            # for those (dead) resources to respond.
            _clear_minion_resource_registration(
                salt_master,
                salt_call_cli,
                "custom_key_resources.sls",
                f"resources: {{}}\n{CUSTOM_PILLAR_KEY}: {{}}\n",
            )


@pytest.fixture(scope="module")
def salt_minion_dynamic(salt_master, pillar_tree_dynamic_resources, dynamic_test_type):
    """A second minion configured for dynamic-discovery tests.

    Module-scoped — startup is expensive (~10s). Tests rotate the
    dynamic ids in pillar between runs and call
    ``sync_resources_and_refresh`` to propagate.
    """
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        "multiprocessing": False,
    }
    factory = salt_master.salt_minion_daemon(
        MINION_ID_DYN,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started(start_timeout=240):
        salt_call_cli = factory.salt_call_cli()
        # Pull the dynamic_test type down into the minion's extmods.
        ret = salt_call_cli.run("saltutil.sync_resources", _timeout=120)
        assert ret.returncode == 0, ret
        # Pillar refresh after sync so _discover_resources sees the new type.
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
        assert ret.returncode == 0, ret
        time.sleep(3)
        try:
            yield factory
        finally:
            # Same as the custom-key minion: clear master state of this
            # minion's dynamic_test resources before shutdown so later
            # tests don't see stale entries in the resource_grains bank.
            _clear_minion_resource_registration(
                salt_master,
                salt_call_cli,
                "dynamic_resources.sls",
                "resources: {}\n_dynamic_test_ids: []\n",
            )


@pytest.fixture(scope="module")
def salt_minion_2(salt_master, pillar_tree_dummy_resources):
    """
    Optional second minion managing :data:`DUMMY_RESOURCES_2`.

    Module-scoped so single-minion tests don't pay the bring-up cost.
    Tests requesting this fixture get a minion whose pillar maps
    ``dummy-04`` / ``dummy-05`` — disjoint from the package's primary
    minion — so multi-minion master state can be exercised end-to-end.
    """
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        "multiprocessing": False,
    }
    factory = salt_master.salt_minion_daemon(
        MINION_ID_2,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started(start_timeout=240):
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
        assert ret.returncode == 0, ret
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        # Same wait as ``salt_minion``: lets the background
        # ``_register_resources_with_master`` task land before tests run.
        time.sleep(3)
        yield factory
