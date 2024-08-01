"""
Tests for the Vault runner
"""

import logging
import shutil

import pytest

from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout_unless_on_windows(120),
]


@pytest.fixture(scope="class")
def pillar_state_tree(tmp_path_factory):
    _pillar_state_tree = tmp_path_factory.mktemp("pillar")
    try:
        yield _pillar_state_tree
    finally:
        shutil.rmtree(str(_pillar_state_tree), ignore_errors=True)


@pytest.fixture(scope="class")
def pillar_salt_master(salt_factories, pillar_state_tree):
    config_defaults = {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
        "ext_pillar": [{"vault": "path=does/not/matter"}],
        "sdbvault": {
            "driver": "vault",
        },
        "vault": {
            "auth": {"method": "token", "token": "testsecret"},
            "policies": [
                "salt_minion",
                "salt_minion_{minion}",
                "salt_role_{pillar[roles]}",
                "salt_unsafe_{grains[foo]}",
            ],
            "policies_cache_time": 0,
            "url": "http://127.0.0.1:8200",
        },
        "minion_data_cache": False,
    }
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "vault-policy-int-master-uncached",
        defaults=config_defaults,
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def pillar_caching_salt_master(salt_factories, pillar_state_tree):
    config_defaults = {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
        "vault": {
            "auth": {"method": "token", "token": "testsecret"},
            "policies": [
                "salt_minion",
                "salt_minion_{minion}",
                "salt_role_{pillar[roles]}",
                "salt_unsafe_{grains[foo]}",
            ],
            "policies_cache_time": 0,
            "url": "http://127.0.0.1:8200",
        },
        "minion_data_cache": True,
    }
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "vault-policy-int-master-cached",
        defaults=config_defaults,
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def pillar_salt_minion(pillar_salt_master):
    assert pillar_salt_master.is_running()
    factory = pillar_salt_master.salt_minion_daemon(
        "vault-policy-int-minion-uncached-1",
        defaults={"open_mode": True, "grains": {"foo": "bar"}},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def pillar_caching_salt_minion(pillar_caching_salt_master):
    assert pillar_caching_salt_master.is_running()
    factory = pillar_caching_salt_master.salt_minion_daemon(
        "vault-policy-int-minion-cached-1",
        defaults={"open_mode": True, "grains": {"foo": "bar"}},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def pillar_salt_run_cli(pillar_salt_master):
    return pillar_salt_master.salt_run_cli()


@pytest.fixture(scope="class")
def pillar_caching_salt_run_cli(pillar_caching_salt_master):
    return pillar_caching_salt_master.salt_run_cli()


@pytest.fixture(scope="class")
def pillar_salt_call_cli(pillar_salt_minion):
    return pillar_salt_minion.salt_call_cli()


@pytest.fixture(scope="class")
def pillar_caching_salt_call_cli(pillar_caching_salt_minion):
    return pillar_caching_salt_minion.salt_call_cli()


class TestVaultPillarPolicyTemplatesWithoutCache:
    @pytest.fixture(autouse=True)
    def pillar_policy_tree(
        self,
        pillar_salt_master,
        pillar_salt_minion,
    ):
        top_pillar_contents = """
        base:
          '{}':
            - roles
        """.format(
            pillar_salt_minion.id
        )
        roles_pillar_contents = """
        roles:
          - minion
          - web
        """
        top_file = pillar_salt_master.pillar_tree.base.temp_file(
            "top.sls", top_pillar_contents
        )
        roles_file = pillar_salt_master.pillar_tree.base.temp_file(
            "roles.sls", roles_pillar_contents
        )

        with top_file, roles_file:
            yield

    @pytest.fixture()
    def pillar_exe_loop(self, pillar_state_tree, pillar_salt_minion):
        top_file = """
        base:
          '{}':
            - roles
            - exe_loop
        """.format(
            pillar_salt_minion.id
        )
        exe_loop_pillar = r"""
        bar: {{ salt["vault.read_secret"]("does/not/matter") }}
        """
        top_tempfile = pytest.helpers.temp_file("top.sls", top_file, pillar_state_tree)
        exe_loop_tempfile = pytest.helpers.temp_file(
            "exe_loop.sls", exe_loop_pillar, pillar_state_tree
        )

        with top_tempfile, exe_loop_tempfile:
            yield

    @pytest.fixture()
    def pillar_sdb_loop(self, pillar_state_tree, pillar_salt_minion):
        top_file = """
        base:
          '{}':
            - roles
            - sdb_loop
        """.format(
            pillar_salt_minion.id
        )
        sdb_loop_pillar = r"""
        foo: {{ salt["sdb.get"]("sdb://sdbvault/does/not/matter/val") }}
        """
        top_tempfile = pytest.helpers.temp_file("top.sls", top_file, pillar_state_tree)
        sdb_loop_tempfile = pytest.helpers.temp_file(
            "sdb_loop.sls", sdb_loop_pillar, pillar_state_tree
        )

        with top_tempfile, sdb_loop_tempfile:
            yield

    @pytest.fixture(autouse=True)
    def minion_data_cache_absent(self, pillar_salt_run_cli, pillar_salt_minion):
        ret = pillar_salt_run_cli.run(
            "cache.flush", f"minions/{pillar_salt_minion.id}", "data"
        )
        assert ret.returncode == 0
        cached = pillar_salt_run_cli.run(
            "cache.fetch", f"minions/{pillar_salt_minion.id}", "data"
        )
        assert cached.returncode == 0
        assert not cached.data
        yield

    def test_show_policies(self, pillar_salt_run_cli, pillar_salt_minion):
        """
        Test that pillar data is refreshed correctly before rendering policies when necessary.
        This test includes the prevention of loop exceptions by the ext_pillar module
        This refresh does not include grains and pillar data targeted by these grains (unsafe anyways!).
        """
        ret = pillar_salt_run_cli.run(
            "vault.show_policies", pillar_salt_minion.id, expire=0
        )
        assert ret.data == [
            "salt_minion",
            f"salt_minion_{pillar_salt_minion.id}",
            "salt_role_minion",
            "salt_role_web",
        ]
        assert "Pillar render error: Failed to load ext_pillar vault" not in ret.stderr

    def test_show_policies_uncached_data_no_pillar_refresh(
        self, pillar_salt_run_cli, pillar_salt_minion
    ):
        """
        Test that the pillar is not refreshed when explicitly disabled
        """
        ret = pillar_salt_run_cli.run(
            "vault.show_policies", pillar_salt_minion.id, refresh_pillar=False, expire=0
        )
        assert ret.data == ["salt_minion", f"salt_minion_{pillar_salt_minion.id}"]

    @pytest.mark.skipif(
        FIPS_TESTRUN, reason="Signing with SHA1 not supported in FIPS mode."
    )
    def test_policy_compilation_prevents_loop_for_execution_module(
        self,
        pillar_salt_run_cli,
        pillar_salt_minion,
        pillar_exe_loop,
    ):
        """
        Test that the runner prevents a recursive cycle from happening
        """
        ret = pillar_salt_run_cli.run(
            "vault.show_policies", pillar_salt_minion.id, refresh_pillar=True, expire=0
        )
        assert ret.data == [
            "salt_minion",
            f"salt_minion_{pillar_salt_minion.id}",
            "salt_role_minion",
            "salt_role_web",
        ]
        assert "Pillar render error: Rendering SLS 'exe_loop' failed" in ret.stderr
        assert "Cyclic dependency detected while refreshing pillar" in ret.stderr

    @pytest.mark.skipif(
        FIPS_TESTRUN, reason="Signing with SHA1 not supported in FIPS mode."
    )
    def test_policy_compilation_prevents_loop_for_sdb_module(
        self,
        pillar_salt_run_cli,
        pillar_salt_minion,
        pillar_sdb_loop,
    ):
        """
        Test that the runner prevents a recursive cycle from happening
        """
        ret = pillar_salt_run_cli.run(
            "vault.show_policies", pillar_salt_minion.id, refresh_pillar=True, expire=0
        )
        assert ret.data == [
            "salt_minion",
            f"salt_minion_{pillar_salt_minion.id}",
            "salt_role_minion",
            "salt_role_web",
        ]
        assert "Pillar render error: Rendering SLS 'sdb_loop' failed" in ret.stderr
        assert "Cyclic dependency detected while refreshing pillar" in ret.stderr


class TestVaultPillarPolicyTemplatesWithCache:
    @pytest.fixture(autouse=True)
    def pillar_caching_policy_tree(
        self, pillar_caching_salt_master, pillar_caching_salt_minion
    ):
        top_pillar_contents = """
        base:
          '{}':
            - roles
        """.format(
            pillar_caching_salt_minion.id
        )
        roles_pillar_contents = """
        roles:
          - minion
          - web
        """
        top_file = pillar_caching_salt_master.pillar_tree.base.temp_file(
            "top.sls", top_pillar_contents
        )
        roles_file = pillar_caching_salt_master.pillar_tree.base.temp_file(
            "roles.sls", roles_pillar_contents
        )

        with top_file, roles_file:
            yield

    @pytest.fixture(autouse=True)
    def minion_data_cache_present(
        self,
        pillar_caching_salt_call_cli,
        pillar_caching_policy_tree,
    ):
        ret = pillar_caching_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True
        yield

    @pytest.fixture(autouse=True)
    def minion_data_cache_outdated(
        self,
        minion_data_cache_present,
        pillar_caching_salt_run_cli,
        pillar_caching_salt_master,
        pillar_caching_salt_minion,
    ):
        roles_pillar_new_contents = """
        roles:
          - minion
          - web
          - fresh
        """
        roles_file = pillar_caching_salt_master.pillar_tree.base.temp_file(
            "roles.sls", roles_pillar_new_contents
        )

        cached = pillar_caching_salt_run_cli.run(
            "cache.fetch", f"minions/{pillar_caching_salt_minion.id}", "data"
        )
        assert cached.returncode == 0
        assert cached.data
        assert "pillar" in cached.data
        assert "grains" in cached.data
        assert "roles" in cached.data["pillar"]
        assert ["minion", "web"] == cached.data["pillar"]["roles"]
        with roles_file:
            yield

    def test_show_policies_cached_data_no_pillar_refresh(
        self,
        pillar_caching_salt_run_cli,
        pillar_caching_salt_minion,
    ):
        """
        Test that pillar data from cache is used when it is available
        """
        ret = pillar_caching_salt_run_cli.run(
            "vault.show_policies", pillar_caching_salt_minion.id, expire=0
        )
        assert ret.data == [
            "salt_minion",
            f"salt_minion_{pillar_caching_salt_minion.id}",
            "salt_role_minion",
            "salt_role_web",
            "salt_unsafe_bar",
        ]

    def test_show_policies_refresh_pillar(
        self,
        pillar_caching_salt_run_cli,
        pillar_caching_salt_minion,
    ):
        """
        Test that pillar data is always refreshed when requested.
        """
        ret = pillar_caching_salt_run_cli.run(
            "vault.show_policies",
            pillar_caching_salt_minion.id,
            refresh_pillar=True,
            expire=0,
        )
        assert ret.data == [
            "salt_minion",
            f"salt_minion_{pillar_caching_salt_minion.id}",
            "salt_role_minion",
            "salt_role_web",
            "salt_role_fresh",
            "salt_unsafe_bar",
        ]
