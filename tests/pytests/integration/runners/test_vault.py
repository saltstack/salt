"""
Tests for the Vault runner
"""

import logging
import shutil

import pytest

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
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
            "auth": {"token": "testsecret"},
            "policies": [
                "salt_minion",
                "salt_minion_{minion}",
                "salt_role_{pillar[roles]}",
                "salt_unsafe_{grains[foo]}",
            ],
        },
        "minion_data_cache": False,
    }
    factory = salt_factories.salt_master_daemon(
        "vault-pillarpolicy-functional-master", defaults=config_defaults
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def pillar_caching_salt_master(salt_factories, pillar_state_tree):
    config_defaults = {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
        "ext_pillar": [{"vault": "path=does/not/matter"}],
        "sdbvault": {
            "driver": "vault",
        },
        "vault": {
            "auth": {"token": "testsecret"},
            "policies": [
                "salt_minion",
                "salt_minion_{minion}",
                "salt_role_{pillar[roles]}",
                "salt_unsafe_{grains[foo]}",
            ],
        },
        "minion_data_cache": True,
    }
    factory = salt_factories.salt_master_daemon(
        "vault-pillarpolicy-functional-master", defaults=config_defaults
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def pillar_salt_minion(pillar_salt_master):
    assert pillar_salt_master.is_running()
    factory = pillar_salt_master.salt_minion_daemon(
        "vault-pillarpolicy-functional-minion-1",
        defaults={"open_mode": True, "grains": {"foo": "bar"}},
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
        "vault-caching-functional-minion-1",
        defaults={"open_mode": True, "grains": {"foo": "bar"}},
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


@pytest.fixture()
def pillar_loop(pillar_state_tree, pillar_policy_tree, pillar_salt_minion):
    top_file = """
    base:
      '{}':
        - roles
        - sdb_loop
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


class TestVaultPillarPolicyTemplatesWithoutCache:
    @pytest.fixture()
    def pillar_policy_tree(
        self,
        pillar_salt_master,
        pillar_salt_minion,
    ):
        top_pillar_contents = """
        base:
          '{}':
            - roles
            - sdb_loop
        """.format(
            pillar_salt_minion.id
        )
        roles_pillar_contents = """
        roles:
          - minion
          - web
        """
        sdb_loop_pillar_contents = """
        foo: {{ salt["sdb.get"]("sdb://sdbvault/does/not/matter/val") }}
        """
        top_file = pillar_salt_master.pillar_tree.base.temp_file(
            "top.sls", top_pillar_contents
        )
        roles_file = pillar_salt_master.pillar_tree.base.temp_file(
            "roles.sls", roles_pillar_contents
        )
        sdb_loop_file = pillar_salt_master.pillar_tree.base.temp_file(
            "sdb_loop.sls", sdb_loop_pillar_contents
        )

        with top_file, roles_file, sdb_loop_file:
            yield

    @pytest.fixture()
    def minion_data_cache_absent(
        self, pillar_salt_run_cli, pillar_salt_minion, pillar_policy_tree
    ):
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

    def test_show_policies(
        self, pillar_salt_run_cli, pillar_salt_minion, minion_data_cache_absent
    ):
        """
        Test that pillar data is refreshed correctly before rendering policies when necessary.
        This test includes the prevention of loop exceptions by sdb/ext_pillar modules
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
        assert "Pillar render error: Rendering SLS 'sdb_loop' failed" not in ret.stderr

    def test_show_policies_uncached_data_no_pillar_refresh(
        self, pillar_salt_run_cli, pillar_salt_minion, minion_data_cache_absent
    ):
        """
        Test that pillar is not refreshed when explicitly disabled
        """
        ret = pillar_salt_run_cli.run(
            "vault.show_policies", pillar_salt_minion.id, refresh_pillar=False, expire=0
        )
        assert ret.data == ["salt_minion", f"salt_minion_{pillar_salt_minion.id}"]

    def test_policy_compilation_prevents_loop(
        self,
        pillar_salt_run_cli,
        pillar_salt_minion,
        pillar_loop,
        minion_data_cache_absent,
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


class TestVaultPillarPolicyTemplatesWithCache:
    @pytest.fixture()
    def pillar_caching_policy_tree(
        self, pillar_caching_salt_master, pillar_caching_salt_minion
    ):
        top_pillar_contents = """
        base:
          '{}':
            - roles
            - sdb_loop
        """.format(
            pillar_caching_salt_minion.id
        )
        roles_pillar_contents = """
        roles:
          - minion
          - web
        """
        sdb_loop_pillar_contents = """
        foo: {{ salt["sdb.get"]("sdb://sdbvault/does/not/matter/val") }}
        """
        top_file = pillar_caching_salt_master.pillar_tree.base.temp_file(
            "top.sls", top_pillar_contents
        )
        roles_file = pillar_caching_salt_master.pillar_tree.base.temp_file(
            "roles.sls", roles_pillar_contents
        )
        sdb_loop_file = pillar_caching_salt_master.pillar_tree.base.temp_file(
            "sdb_loop.sls", sdb_loop_pillar_contents
        )

        with top_file, roles_file, sdb_loop_file:
            yield

    @pytest.fixture()
    def minion_data_cache_present(
        self,
        pillar_caching_salt_call_cli,
        pillar_caching_policy_tree,
    ):
        ret = pillar_caching_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True
        yield

    @pytest.fixture()
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
        minion_data_cache_outdated,
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
        minion_data_cache_outdated,
    ):
        """
        Test that pillar data is always refreshed when requested.
        This test includes the prevention of loops by sdb/ext_pillar modules
        This refresh does not include grains and pillar data targeted by these grains (unsafe anyways!).
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
        assert "Pillar render error: Failed to load ext_pillar vault" not in ret.stderr
        assert "Pillar render error: Rendering SLS 'sdb_loop' failed" not in ret.stderr
