"""
Tests for the Vault runner
"""

import logging
import os
import shutil
from pathlib import Path

import pytest
from saltfactories.utils import random_string

import salt.utils.files

# pylint: disable=unused-import
from tests.support.pytest.vault import (
    vault_container_version,
    vault_delete_secret,
    vault_environ,
    vault_write_secret,
)

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
    pytest.mark.usefixtures("vault_container_version"),
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
def pillar_salt_master(salt_factories, pillar_state_tree, vault_port):
    config_defaults = {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
        "ext_pillar": [{"vault": "path=secret/path/foo"}],
        "sdbvault": {
            "driver": "vault",
        },
        "vault": {
            "auth": {"token": "testsecret"},
            "issue": {
                "token": {
                    "params": {
                        # otherwise the tests might fail because of
                        # cached tokens (should not, because by default,
                        # the cache is valid for one session only)
                        "num_uses": 1,
                    },
                },
            },
            "policies": {
                "assign": [
                    "salt_minion",
                    "salt_minion_{minion}",
                    "salt_role_{pillar[roles]}",
                    "salt_unsafe_{grains[foo]}",
                    "extpillar_this_should_always_be_absent_{pillar[vault_sourced]}",
                    "sdb_this_should_always_be_absent_{pillar[vault_sourced_sdb]}",
                    "exe_this_should_always_be_absent_{pillar[vault_sourced_exe]}",
                ],
                "cache_time": 0,
            },
            "server": {
                "url": f"http://127.0.0.1:{vault_port}",
            },
        },
        "minion_data_cache": False,
    }
    factory = salt_factories.salt_master_daemon(
        "vault-policy-int-master-uncached", defaults=config_defaults
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def pillar_caching_salt_master(salt_factories, pillar_state_tree, vault_port):
    config_defaults = {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
        "ext_pillar": [{"vault": "path=secret/path/foo"}],
        "vault": {
            "auth": {"token": "testsecret"},
            "issue": {
                "token": {
                    "params": {
                        # otherwise the tests might fail because of
                        # cached tokens
                        "num_uses": 1,
                    },
                },
            },
            "policies": {
                "assign": [
                    "salt_minion",
                    "salt_minion_{minion}",
                    "salt_role_{pillar[roles]}",
                    "salt_unsafe_{grains[foo]}",
                    "extpillar_this_will_not_always_be_absent_{pillar[vault_sourced]}",
                ],
                "cache_time": 0,
            },
            "server": {
                "url": f"http://127.0.0.1:{vault_port}",
            },
        },
        "minion_data_cache": True,
    }
    factory = salt_factories.salt_master_daemon(
        "vault-policy-int-master-cached", defaults=config_defaults
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def pillar_salt_minion(pillar_salt_master):
    assert pillar_salt_master.is_running()
    factory = pillar_salt_master.salt_minion_daemon(
        "vault-policy-int-minion-uncached-1",
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
        "vault-policy-int-minion-cached-1",
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


@pytest.fixture(scope="class")
def vault_pillar_values_policy(vault_container_version):
    vault_write_secret("secret/path/foo", vault_sourced="fail")
    try:
        yield
    finally:
        vault_delete_secret("secret/path/foo")


@pytest.mark.usefixtures("vault_pillar_values_policy")
@pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
class TestVaultPillarPolicyTemplatesWithoutCache:
    @pytest.fixture(autouse=True)
    def pillar_policy_tree(
        self,
        pillar_salt_master,
        pillar_salt_minion,
    ):
        top_pillar_contents = f"""
        base:
          '{pillar_salt_minion.id}':
            - roles
        """
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

    @pytest.fixture
    def pillar_exe_loop(self, pillar_state_tree, pillar_salt_minion):
        top_file = f"""
        base:
          '{pillar_salt_minion.id}':
            - roles
            - exe_loop
        """
        exe_loop_pillar = r"""
        vault_sourced_exe: {{ salt["vault.read_secret"]("secret/path/foo", "vault_sourced") }}
        """
        top_tempfile = pytest.helpers.temp_file("top.sls", top_file, pillar_state_tree)
        exe_loop_tempfile = pytest.helpers.temp_file(
            "exe_loop.sls", exe_loop_pillar, pillar_state_tree
        )

        with top_tempfile, exe_loop_tempfile:
            yield

    @pytest.fixture
    def pillar_sdb_loop(self, pillar_state_tree, pillar_salt_minion):
        top_file = f"""
        base:
          '{pillar_salt_minion.id}':
            - roles
            - sdb_loop
        """
        sdb_loop_pillar = r"""
        vault_sourced_sdb: {{ salt["sdb.get"]("sdb://sdbvault/secret/path/foo/vault_sourced") }}
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

    @pytest.mark.usefixtures("pillar_exe_loop")
    def test_policy_compilation_prevents_loop_for_execution_module(
        self,
        pillar_salt_run_cli,
        pillar_salt_minion,
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
        assert "RecursionError" not in ret.stderr

    @pytest.mark.usefixtures("pillar_sdb_loop")
    def test_policy_compilation_prevents_loop_for_sdb_module(
        self,
        pillar_salt_run_cli,
        pillar_salt_minion,
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
        assert "RecursionError" not in ret.stderr


@pytest.mark.usefixtures("vault_pillar_values_policy")
@pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
class TestVaultPillarPolicyTemplatesWithCache:
    @pytest.fixture(autouse=True)
    def pillar_caching_policy_tree(
        self, pillar_caching_salt_master, pillar_caching_salt_minion
    ):
        top_pillar_contents = f"""
        base:
          '{pillar_caching_salt_minion.id}':
            - roles
        """
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
        assert cached.data["pillar"]["roles"] == ["minion", "web"]
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
            "extpillar_this_will_not_always_be_absent_fail",
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


# The tests above use different fixtures because I could not
# make them behave as expected otherwise.


@pytest.fixture(scope="class")
def vault_salt_master(
    salt_factories, pillar_state_tree, vault_port, vault_master_config
):
    factory = salt_factories.salt_master_daemon(
        "vault-master", defaults=vault_master_config
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def vault_salt_minion(vault_salt_master):
    assert vault_salt_master.is_running()
    factory = vault_salt_master.salt_minion_daemon(
        random_string("vault-minion", uppercase=False),
        defaults={"open_mode": True, "grains": {}},
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def overriding_vault_salt_minion(vault_salt_master, issue_overrides):
    assert vault_salt_master.is_running()
    factory = vault_salt_master.salt_minion_daemon(
        random_string("vault-minion", uppercase=False),
        defaults={"open_mode": True, "grains": {}},
        overrides={"vault": {"issue_params": issue_overrides}},
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def vault_salt_run_cli(vault_salt_master):
    return vault_salt_master.salt_run_cli()


@pytest.fixture(scope="class")
def vault_salt_call_cli(vault_salt_minion):
    return vault_salt_minion.salt_call_cli()


@pytest.fixture(scope="class")
def pillar_roles_tree(
    vault_salt_master,
    vault_salt_minion,
):
    top_pillar_contents = f"""
    base:
      '{vault_salt_minion.id}':
        - roles
    """
    roles_pillar_contents = """
    roles:
      - dev
      - web
    # this is for entity metadata since lists are cumbersome at best
    role: foo
    """
    top_file = vault_salt_master.pillar_tree.base.temp_file(
        "top.sls", top_pillar_contents
    )
    roles_file = vault_salt_master.pillar_tree.base.temp_file(
        "roles.sls", roles_pillar_contents
    )

    with top_file, roles_file:
        yield


@pytest.fixture(scope="class")
def vault_pillar_values_approle(vault_salt_minion):
    vault_write_secret(
        f"salt/minions/{vault_salt_minion.id}", minion_id_acl_template="worked"
    )
    vault_write_secret("salt/roles/foo", pillar_role_acl_template="worked")
    try:
        yield
    finally:
        vault_delete_secret(f"salt/minions/{vault_salt_minion.id}")
        vault_delete_secret("salt/roles/foo")


@pytest.fixture(scope="class")
def vault_testing_values(vault_container_version):
    vault_write_secret("secret/path/foo", success="yeehaaw")
    try:
        yield
    finally:
        vault_delete_secret("secret/path/foo")


@pytest.fixture
def minion_conn_cachedir(vault_salt_call_cli):
    ret = vault_salt_call_cli.run("config.get", "cachedir")
    assert ret.returncode == 0
    assert ret.data
    cachedir = Path(ret.data) / "vault" / "connection"
    if not cachedir.exists():
        cachedir.mkdir(parents=True)
    yield cachedir


@pytest.fixture
def missing_auth_cache(minion_conn_cachedir):
    token_cachefile = minion_conn_cachedir / "session" / "__token.p"
    secret_id_cachefile = minion_conn_cachedir / "secret_id.p"
    for file in [secret_id_cachefile, token_cachefile]:
        if file.exists():
            file.unlink()
    yield


@pytest.fixture(scope="class")
def minion_data_cache_present(
    vault_salt_call_cli,
    vault_salt_minion,
    pillar_roles_tree,
    vault_salt_run_cli,
):
    ret = vault_salt_run_cli.run("pillar.show_top", minion=vault_salt_minion.id)
    assert ret.returncode == 0
    assert ret.data
    ret = vault_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
    assert ret.returncode == 0
    assert ret.data is True
    ret = vault_salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    assert "role" in ret.data
    assert "roles" in ret.data
    yield


@pytest.fixture
def conn_cache_absent(minion_conn_cachedir):
    shutil.rmtree(minion_conn_cachedir)
    assert not minion_conn_cachedir.exists()
    yield


@pytest.fixture(scope="class")
def approles_synced(
    vault_salt_run_cli,
    minion_data_cache_present,
    vault_salt_minion,
):
    ret = vault_salt_run_cli.run("vault.sync_approles", vault_salt_minion.id)
    assert ret.returncode == 0
    assert ret.data is True
    ret = vault_salt_run_cli.run("vault.list_approles")
    assert ret.returncode == 0
    assert vault_salt_minion.id in ret.data
    yield


@pytest.fixture(scope="class")
def entities_synced(
    vault_salt_run_cli,
    minion_data_cache_present,
    vault_salt_minion,
):
    ret = vault_salt_run_cli.run("vault.sync_entities", vault_salt_minion.id)
    assert ret.returncode == 0
    assert ret.data is True
    ret = vault_salt_run_cli.run("vault.list_approles")
    assert ret.returncode == 0
    assert vault_salt_minion.id in ret.data
    ret = vault_salt_run_cli.run("vault.list_entities")
    assert ret.returncode == 0
    assert f"salt_minion_{vault_salt_minion.id}" in ret.data
    ret = vault_salt_run_cli.run("vault.show_entity", vault_salt_minion.id)
    assert ret.returncode == 0
    assert ret.data == {"minion-id": vault_salt_minion.id, "role": "foo"}
    yield


@pytest.mark.usefixtures(
    "vault_pillar_values_approle",
    "vault_testing_values",
    "pillar_roles_tree",
    "minion_data_cache_present",
)
@pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
class TestAppRoleIssuance:
    @pytest.fixture(scope="class")
    def vault_master_config(self, pillar_state_tree, vault_port):
        return {
            "pillar_roots": {"base": [str(pillar_state_tree)]},
            "open_mode": True,
            # ensure approles/entities are generated during pillar rendering
            "ext_pillar": [
                {"vault": "path=salt/minions/{minion}"},
                {"vault": "path=salt/roles/{pillar[role]}"},
            ],
            "peer_run": {
                ".*": [
                    "vault.get_config",
                    # for test_auth_method_switch_does_not_break_minion_auth
                    "vault.generate_new_token",
                    "vault.generate_secret_id",
                ],
            },
            "vault": {
                "auth": {"token": "testsecret"},
                "cache": {
                    "backend": "file",
                },
                "issue": {
                    "allow_minion_override_params": True,
                    "type": "approle",
                    "approle": {
                        "params": {
                            "secret_id_num_uses": 0,
                            "secret_id_ttl": 1800,
                            "token_explicit_max_ttl": 1800,
                            "token_num_uses": 0,
                        }
                    },
                },
                "metadata": {
                    "entity": {
                        "minion-id": "{minion}",
                        "role": "{pillar[role]}",
                    },
                },
                "policies": {
                    "assign": [
                        "salt_minion",
                        "salt_minion_{minion}",
                        "salt_role_{pillar[roles]}",
                    ],
                },
                "server": {
                    "url": f"http://127.0.0.1:{vault_port}",
                },
            },
        }

    @pytest.fixture(scope="class")
    def issue_overrides(self):
        return {
            "token_explicit_max_ttl": 1337,
            "token_num_uses": 42,
            "secret_id_num_uses": 3,
            "secret_id_ttl": 1338,
        }

    @pytest.fixture
    def cache_auth_outdated(self, missing_auth_cache, minion_conn_cachedir, vault_port):
        vault_url = f"http://127.0.0.1:{vault_port}"
        config_data = b"\xdf\x00\x00\x00\x03\xa4auth\xdf\x00\x00\x00\x04\xadapprole_mount\xa7approle\xacapprole_name\xbavault-approle-int-minion-1\xa6method\xa5token\xa9secret_id\xc0\xa5cache\xdf\x00\x00\x00\x03\xa7backend\xa4disk\xa6config\xcd\x0e\x10\xa6secret\xa3ttl\xa6server\xdf\x00\x00\x00\x03\xa9namespace\xc0\xa6verify\xc0\xa3url"
        config_data += (len(vault_url) + 160).to_bytes(1, "big") + vault_url.encode()
        config_cachefile = minion_conn_cachedir / "config.p"
        with salt.utils.files.fopen(config_cachefile, "wb") as f:
            f.write(config_data)
        try:
            yield
        finally:
            if config_cachefile.exists():
                config_cachefile.unlink()

    @pytest.fixture
    def cache_server_outdated(self, missing_auth_cache, minion_conn_cachedir):
        config_data = b"\xdf\x00\x00\x00\x03\xa4auth\xdf\x00\x00\x00\x05\xadapprole_mount\xa7approle\xacapprole_name\xbavault-approle-int-minion-1\xa6method\xa7approle\xa7role_id\xactest-role-id\xa9secret_id\xc3\xa5cache\xdf\x00\x00\x00\x03\xa7backend\xa4disk\xa6config\xcd\x0e\x10\xa6secret\xa3ttl\xa6server\xdf\x00\x00\x00\x03\xa9namespace\xc0\xa6verify\xc0\xa3url\xb2http://127.0.0.1:8"
        config_cachefile = minion_conn_cachedir / "config.p"
        with salt.utils.files.fopen(config_cachefile, "wb") as f:
            f.write(config_data)
        try:
            yield
        finally:
            if config_cachefile.exists():
                config_cachefile.unlink()

    @pytest.mark.usefixtures("conn_cache_absent")
    def test_minion_can_authenticate(self, vault_salt_call_cli):
        """
        Test that the minion can run queries against Vault.
        The master impersonating the minion is already tested in the fixture setup
        (ext_pillar).
        """
        ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("success") == "yeehaaw"

    @pytest.mark.usefixtures("entities_synced")
    def test_minion_pillar_is_populated_as_expected(self, vault_salt_call_cli):
        """
        Test that ext_pillar pillar-templated paths are resolved as expectd
        (and that the ACL policy templates work on the Vault side).
        """
        ret = vault_salt_call_cli.run("pillar.items")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("minion_id_acl_template") == "worked"
        assert ret.data.get("pillar_role_acl_template") == "worked"

    @pytest.mark.usefixtures("approles_synced")
    @pytest.mark.usefixtures("conn_cache_absent")
    def test_minion_token_policies_are_assigned_as_expected(
        self, vault_salt_call_cli, vault_salt_minion
    ):
        """
        Test that issued tokens have the expected policies.
        """
        ret = vault_salt_call_cli.run("vault.query", "GET", "auth/token/lookup-self")
        assert ret.returncode == 0
        assert ret.data
        assert set(ret.data["data"]["policies"]) == {
            "default",
            "salt_minion",
            f"salt_minion_{vault_salt_minion.id}",
            "salt_role_dev",
            "salt_role_web",
        }

    @pytest.mark.usefixtures("cache_auth_outdated")
    def test_auth_method_switch_does_not_break_minion_auth(
        self, vault_salt_call_cli, caplog
    ):
        """
        Test that after a master configuration switch from another authentication method,
        minions with cached configuration flush it and request a new one.
        """
        ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("success") == "yeehaaw"
        assert "Master returned error and requested cache expiration" in caplog.text

    @pytest.mark.usefixtures("cache_server_outdated")
    def test_server_switch_does_not_break_minion_auth(
        self, vault_salt_call_cli, caplog
    ):
        """
        Test that after a master configuration switch to another server URL,
        minions with cached configuration detect the mismatch and request a
        new configuration.
        """
        ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("success") == "yeehaaw"
        assert "Mismatch of cached and reported server data detected" in caplog.text

    @pytest.mark.parametrize("ckey", ["config", "__token", "secret_id"])
    def test_cache_is_used_on_the_minion(
        self, ckey, vault_salt_call_cli, minion_conn_cachedir
    ):
        """
        Test that remote configuration, tokens acquired by authenticating with an AppRole
        and issued secret IDs are written to cache.
        """
        cache = minion_conn_cachedir
        if ckey == "__token":
            cache = cache / "session"
            if not cache.exists():
                cache.mkdir()
        if f"{ckey}.p" not in os.listdir(cache):
            ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
            assert ret.returncode == 0
        assert f"{ckey}.p" in os.listdir(cache)

    @pytest.mark.parametrize("ckey", ["config", "__token", "secret_id"])
    def test_cache_is_used_on_the_impersonating_master(
        self, ckey, vault_salt_run_cli, vault_salt_minion
    ):
        """
        Test that remote configuration, tokens acquired by authenticating with an AppRole
        and issued secret IDs are written to cache when a master is impersonating
        a minion during pillar rendering.
        """
        cbank = f"minions/{vault_salt_minion.id}/vault/connection"
        if ckey == "__token":
            cbank += "/session"
        ret = vault_salt_run_cli.run("cache.list", cbank)
        assert ret.returncode == 0
        assert ret.data
        assert ckey in ret.data

    def test_cache_is_used_for_master_token_information(self, vault_salt_run_cli):
        """
        Test that a locally configured token is cached, including meta information.
        """
        ret = vault_salt_run_cli.run("cache.list", "vault/connection/session")
        assert ret.returncode == 0
        assert ret.data
        assert "__token" in ret.data

    @pytest.mark.usefixtures("approles_synced")
    def test_issue_param_overrides_work(
        self, overriding_vault_salt_minion, issue_overrides, vault_salt_run_cli
    ):
        """
        Test that minion overrides of issue params work for AppRoles.
        """
        ret = overriding_vault_salt_minion.salt_call_cli().run(
            "vault.query", "GET", "auth/token/lookup-self"
        )
        assert ret.returncode == 0
        assert ret.data
        ret = vault_salt_run_cli.run(
            "vault.show_approle", overriding_vault_salt_minion.id
        )
        assert ret.returncode == 0
        assert ret.data
        for val in [
            "token_explicit_max_ttl",
            "token_num_uses",
            "secret_id_num_uses",
            "secret_id_ttl",
        ]:
            assert ret.data[val] == issue_overrides[val]

    def test_impersonating_master_does_not_override_issue_param_overrides(
        self, overriding_vault_salt_minion, vault_salt_run_cli, issue_overrides
    ):
        """
        Test that rendering the pillar does not remove issue param overrides
        requested by a minion
        """
        # ensure the minion requests a new configuration
        ret = overriding_vault_salt_minion.salt_call_cli().run(
            "vault.clear_token_cache"
        )
        assert ret.returncode == 0
        # check that the overrides are applied
        ret = overriding_vault_salt_minion.salt_call_cli().run(
            "vault.query", "GET", "auth/token/lookup-self"
        )
        assert ret.returncode == 0
        assert ret.data
        assert (
            ret.data["data"]["explicit_max_ttl"]
            == issue_overrides["token_explicit_max_ttl"]
        )
        # ensure the master does not have cached authentication
        ret = vault_salt_run_cli.run("vault.clear_cache")
        assert ret.returncode == 0
        ret = vault_salt_run_cli.run(
            "pillar.show_pillar", overriding_vault_salt_minion.id
        )
        assert ret.returncode == 0
        # check that issue overrides are still present
        ret = vault_salt_run_cli.run(
            "vault.show_approle", overriding_vault_salt_minion.id
        )
        assert ret.returncode == 0
        assert ret.data
        assert (
            ret.data["token_explicit_max_ttl"]
            == issue_overrides["token_explicit_max_ttl"]
        )


@pytest.mark.usefixtures(
    "vault_testing_values", "pillar_roles_tree", "minion_data_cache_present"
)
class TestTokenIssuance:
    @pytest.fixture(scope="class")
    def vault_master_config(self, pillar_state_tree, vault_port):
        return {
            "pillar_roots": {"base": [str(pillar_state_tree)]},
            "open_mode": True,
            "ext_pillar": [{"vault": "path=secret/path/foo"}],
            "peer_run": {
                ".*": [
                    "vault.get_config",
                    "vault.generate_new_token",
                    # for test_auth_method_switch_does_not_break_minion_auth
                    "vault.generate_secret_id",
                ],
            },
            "vault": {
                "auth": {"token": "testsecret"},
                "cache": {
                    "backend": "file",
                },
                "issue": {
                    "type": "token",
                    "token": {
                        "params": {
                            "num_uses": 0,
                        }
                    },
                },
                "policies": {
                    "assign": [
                        "salt_minion",
                        "salt_minion_{minion}",
                        "salt_role_{pillar[roles]}",
                    ],
                    "cache_time": 0,
                },
                "server": {
                    "url": f"http://127.0.0.1:{vault_port}",
                },
            },
            "minion_data_cache": True,
        }

    @pytest.fixture
    def cache_auth_outdated(self, missing_auth_cache, minion_conn_cachedir, vault_port):
        vault_url = f"http://127.0.0.1:{vault_port}"
        config_data = b"\xdf\x00\x00\x00\x03\xa4auth\xdf\x00\x00\x00\x05\xadapprole_mount\xa7approle\xacapprole_name\xbavault-approle-int-minion-1\xa6method\xa7approle\xa7role_id\xactest-role-id\xa9secret_id\xc3\xa5cache\xdf\x00\x00\x00\x03\xa7backend\xa4disk\xa6config\xcd\x0e\x10\xa6secret\xa3ttl\xa6server\xdf\x00\x00\x00\x03\xa9namespace\xc0\xa6verify\xc0\xa3url"
        config_data += (len(vault_url) + 160).to_bytes(1, "big") + vault_url.encode()
        config_cachefile = minion_conn_cachedir / "config.p"
        with salt.utils.files.fopen(config_cachefile, "wb") as f:
            f.write(config_data)
        try:
            yield
        finally:
            if config_cachefile.exists():
                config_cachefile.unlink()

    @pytest.fixture(scope="class")
    def issue_overrides(self):
        # only explicit_max_ttl and num_uses are respected, the rest is for testing purposes
        return {
            "explicit_max_ttl": 1337,
            "num_uses": 42,
            "secret_id_num_uses": 3,
            "secret_id_ttl": 1338,
            "irrelevant_setting": "abc",
        }

    @pytest.mark.usefixtures("conn_cache_absent")
    @pytest.mark.parametrize(
        "vault_container_version", ["0.9.6", "1.3.1", "latest"], indirect=True
    )
    def test_minion_can_authenticate(self, vault_salt_call_cli):
        """
        Test that the minion can run queries against Vault.
        The master impersonating the minion is already tested in the fixture setup
        (ext_pillar).
        """
        ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("success") == "yeehaaw"

    @pytest.mark.usefixtures("conn_cache_absent")
    @pytest.mark.parametrize(
        "vault_container_version", ["0.9.6", "1.3.1", "latest"], indirect=True
    )
    def test_minion_token_policies_are_assigned_as_expected(
        self, vault_salt_call_cli, vault_salt_minion
    ):
        """
        Test that issued tokens have the expected policies.
        """
        ret = vault_salt_call_cli.run("vault.query", "GET", "auth/token/lookup-self")
        assert ret.returncode == 0
        assert ret.data
        assert set(ret.data["data"]["policies"]) == {
            "default",
            "salt_minion",
            f"salt_minion_{vault_salt_minion.id}",
            "salt_role_dev",
            "salt_role_web",
        }

    @pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
    @pytest.mark.usefixtures("cache_auth_outdated")
    def test_auth_method_switch_does_not_break_minion_auth(
        self, vault_salt_call_cli, caplog
    ):
        """
        Test that after a master configuration switch from another authentication method,
        minions with cached configuration flush it and request a new one.
        """
        ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("success") == "yeehaaw"
        assert "Master returned error and requested cache expiration" in caplog.text

    @pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
    @pytest.mark.parametrize("ckey", ["config", "__token"])
    def test_cache_is_used_on_the_minion(
        self, ckey, vault_salt_call_cli, minion_conn_cachedir
    ):
        """
        Test that remote configuration and tokens are written to cache.
        """
        cache = minion_conn_cachedir
        if ckey == "__token":
            cache = cache / "session"
            if not cache.exists():
                cache.mkdir()
        if f"{ckey}.p" not in os.listdir(cache):
            ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
            assert ret.returncode == 0
        assert f"{ckey}.p" in os.listdir(cache)

    @pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
    @pytest.mark.parametrize("ckey", ["config", "__token"])
    def test_cache_is_used_on_the_impersonating_master(
        self, ckey, vault_salt_run_cli, vault_salt_minion
    ):
        """
        Test that remote configuration and tokens are written to cache when a
        master is impersonating a minion during pillar rendering.
        """
        cbank = f"minions/{vault_salt_minion.id}/vault/connection"
        if ckey == "__token":
            cbank += "/session"
        ret = vault_salt_run_cli.run("cache.list", cbank)
        assert ret.returncode == 0
        assert ret.data
        assert ckey in ret.data

    @pytest.mark.usefixtures("conn_cache_absent")
    @pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
    def test_issue_param_overrides_require_setting(self, overriding_vault_salt_minion):
        """
        Test that minion overrides of issue params are not set by default
        and require setting ``issue:allow_minion_override_params``.
        """
        ret = overriding_vault_salt_minion.salt_call_cli().run(
            "vault.query", "GET", "auth/token/lookup-self"
        )
        assert ret.returncode == 0
        assert ret.data
        assert ret.data["data"]["explicit_max_ttl"] != 1337
        assert ret.data["data"]["num_uses"] != 41  # one use is consumed by the lookup


@pytest.mark.usefixtures("vault_testing_values")
@pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
class TestAppRoleIssuanceWithoutSecretId:
    @pytest.fixture(scope="class")
    def vault_master_config(self, vault_port):
        return {
            "open_mode": True,
            "peer_run": {
                ".*": [
                    "vault.get_config",
                    "vault.generate_secret_id",
                ],
            },
            "vault": {
                "auth": {"token": "testsecret"},
                "cache": {
                    "backend": "file",
                },
                "issue": {
                    "type": "approle",
                    "approle": {
                        "params": {
                            "bind_secret_id": False,
                            # "at least one constraint should be enabled on the role"
                            # this should be quite secure :)
                            "token_bound_cidrs": "0.0.0.0/0",
                            "token_explicit_max_ttl": 1800,
                            "token_num_uses": 0,
                        }
                    },
                },
                "policies": {
                    "assign": {
                        "salt_minion",
                        "salt_minion_{minion}",
                    },
                },
                "server": {
                    "url": f"http://127.0.0.1:{vault_port}",
                },
            },
        }

    @pytest.mark.usefixtures("conn_cache_absent")
    def test_minion_can_authenticate(self, vault_salt_call_cli, caplog):
        """
        Test that the minion can run queries against Vault.
        The master impersonating the minion is already tested in the fixture setup
        (ext_pillar).
        """
        ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("success") == "yeehaaw"
        assert "Minion AppRole does not require a secret ID" not in caplog.text


@pytest.mark.usefixtures("vault_testing_values")
@pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
class TestOldConfigSyntax:
    @pytest.fixture(scope="class")
    def vault_master_config(self, pillar_state_tree, vault_port):
        return {
            "pillar_roots": {"base": [str(pillar_state_tree)]},
            "open_mode": True,
            "peer_run": {
                ".*": [
                    "vault.generate_token",
                ],
            },
            "vault": {
                "auth": {
                    "allow_minion_override": True,
                    "token": "testsecret",
                    "token_backend": "file",
                    "ttl": 90,
                    "uses": 3,
                },
                "policies": [
                    "salt_minion",
                    "salt_minion_{minion}",
                ],
                "url": f"http://127.0.0.1:{vault_port}",
            },
            "minion_data_cache": True,
        }

    @pytest.fixture(scope="class")
    def overriding_vault_salt_minion(self, vault_salt_master):
        assert vault_salt_master.is_running()
        factory = vault_salt_master.salt_minion_daemon(
            random_string("vault-minion", uppercase=False),
            defaults={"open_mode": True, "grains": {}},
            overrides={"vault": {"auth": {"uses": 5, "ttl": 180}}},
        )
        with factory.started():
            # Sync All
            salt_call_cli = factory.salt_call_cli()
            ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
            assert ret.returncode == 0, ret
            yield factory

    @pytest.mark.usefixtures("conn_cache_absent")
    def test_minion_can_authenticate(self, vault_salt_call_cli, caplog):
        """
        Test that the minion can authenticate, even if the master peer_run
        configuration has not been updated.
        """
        ret = vault_salt_call_cli.run("vault.read_secret", "secret/path/foo")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("success") == "yeehaaw"
        assert (
            "does the peer runner publish configuration include `vault.get_config`"
            in caplog.text
        )
        assert "Peer runner return was empty." not in caplog.text
        assert "Falling back to vault.generate_token." in caplog.text
        assert (
            "Detected minion fallback to old vault.generate_token peer run function"
            in caplog.text
        )

    @pytest.mark.usefixtures("conn_cache_absent")
    def test_token_is_configured_as_expected(
        self, vault_salt_call_cli, vault_salt_minion
    ):
        """
        Test that issued tokens have the expected parameters.
        """
        ret = vault_salt_call_cli.run("vault.query", "GET", "auth/token/lookup-self")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data["data"]["explicit_max_ttl"] == 90
        assert ret.data["data"]["num_uses"] == 2  # one use is consumed by the lookup
        assert set(ret.data["data"]["policies"]) == {
            "default",
            "salt_minion",
            f"salt_minion_{vault_salt_minion.id}",
        }

    @pytest.mark.usefixtures("conn_cache_absent")
    def test_issue_param_overrides_work(self, overriding_vault_salt_minion):
        """
        Test that minion overrides of issue params work for the old configuration.
        """
        ret = overriding_vault_salt_minion.salt_call_cli().run(
            "vault.query", "GET", "auth/token/lookup-self"
        )
        assert ret.returncode == 0
        assert ret.data
        assert ret.data["data"]["explicit_max_ttl"] == 180
        assert ret.data["data"]["num_uses"] == 4  # one use is consumed by the lookup


@pytest.mark.usefixtures("vault_testing_values")
class TestMinionLocal:
    @pytest.fixture(scope="class")
    def vault_master_config(self):
        return {"open_mode": True}

    @pytest.fixture(scope="class")
    def vault_salt_minion(self, vault_salt_master, vault_port):
        assert vault_salt_master.is_running()
        factory = vault_salt_master.salt_minion_daemon(
            random_string("vault-minion", uppercase=False),
            defaults={
                "open_mode": True,
                "vault": {
                    "auth": {"token": "testsecret"},
                    "cache": {
                        "backend": "file",
                    },
                    "server": {
                        "url": f"http://127.0.0.1:{vault_port}",
                    },
                },
                "grains": {},
            },
        )
        with factory.started():
            # Sync All
            salt_call_cli = factory.salt_call_cli()
            ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
            assert ret.returncode == 0, ret
            yield factory

    def test_minion_can_authenticate(self, vault_salt_call_cli):
        """
        Test that salt-call --local works with the Vault module.
        Issue #58580
        """
        ret = vault_salt_call_cli.run("--local", "vault.read_secret", "secret/path/foo")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data.get("success") == "yeehaaw"
