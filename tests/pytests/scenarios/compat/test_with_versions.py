"""
    tests.e2e.compat.test_with_versions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test current salt master with older salt minions
"""

import logging
import pathlib

import pytest
from saltfactories.daemons.container import SaltMinion
from saltfactories.utils import random_string

import salt.utils.platform
from tests.conftest import FIPS_TESTRUN
from tests.support.runtests import RUNTIME_VARS

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker"),
    pytest.mark.skipif(
        salt.utils.platform.is_photonos() is True, reason="Skip on PhotonOS"
    ),
]


def _get_test_versions_ids(value):
    return f"SaltMinion~={value}"


@pytest.fixture(
    params=("3002", "3003", "3004"), ids=_get_test_versions_ids, scope="module"
)
def compat_salt_version(request):
    return request.param


@pytest.fixture(scope="module")
def minion_image_name(compat_salt_version):
    return f"salt-{compat_salt_version}"


@pytest.fixture(scope="function")
def minion_id(compat_salt_version):
    return random_string(
        f"salt-{compat_salt_version}-",
        uppercase=False,
    )


@pytest.fixture(scope="function")
def artifacts_path(minion_id, tmp_path):
    yield tmp_path / minion_id


@pytest.mark.skip_if_binaries_missing("docker")
@pytest.fixture(scope="function")
def salt_minion(
    minion_id,
    salt_master,
    docker_client,
    artifacts_path,
    compat_salt_version,
    host_docker_network_ip_address,
):
    config_overrides = {
        "master": salt_master.config["interface"],
        "user": False,
        "pytest-minion": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
        # We also want to scrutinize the key acceptance
        "open_mode": False,
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        factory_class=SaltMinion,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        # SaltMinion kwargs
        name=minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:{}".format(
            compat_salt_version
        ),
        docker_client=docker_client,
        start_timeout=120,
        pull_before_start=False,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "volumes": {
                str(artifacts_path): {
                    "bind": "/artifacts",
                    "mode": "z",
                },
            }
        },
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="function")
def package_name():
    return "figlet"


@pytest.fixture
def populated_state_tree(minion_id, package_name, state_tree):
    module_contents = """
    def get_test_package_name():
        return "{}"
    """.format(
        package_name
    )
    top_file_contents = """
    base:
        {}:
          - install-package
    """.format(
        minion_id
    )
    install_package_sls_contents = """
    state-entry-contém-unicode:
        pkg.installed:
          - name: {{ salt.pkgnames.get_test_package_name() }}
    """
    with pytest.helpers.temp_file(
        "_modules/pkgnames.py",
        module_contents,
        state_tree,
    ), pytest.helpers.temp_file(
        "top.sls", top_file_contents, state_tree
    ), pytest.helpers.temp_file(
        "install-package.sls",
        install_package_sls_contents,
        state_tree,
    ):
        # Run the test
        yield


@pytest.mark.skip_on_fips_enabled_platform
def test_ping(salt_cli, salt_minion):
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == 0, ret
    assert ret.data is True


@pytest.mark.skip_on_fips_enabled_platform
@pytest.mark.usefixtures("populated_state_tree")
def test_highstate(salt_cli, salt_minion, package_name):
    """
    Assert a state.highstate with a newer master runs properly on older minions.
    """
    ret = salt_cli.run("state.highstate", minion_tgt=salt_minion.id, _timeout=300)
    assert ret.returncode == 0, ret
    assert ret.data is not None
    assert isinstance(ret.data, dict), ret.data
    state_return = next(iter(ret.data.values()))
    assert package_name in state_return["changes"], state_return


@pytest.mark.skip_on_fips_enabled_platform
@pytest.fixture
def cp_file_source():
    source = pathlib.Path(RUNTIME_VARS.BASE_FILES) / "cheese"
    contents = source.read_text().replace("ee", "æ")
    with pytest.helpers.temp_file(contents=contents) as temp_file:
        yield pathlib.Path(temp_file)


@pytest.mark.skip_on_fips_enabled_platform
def test_cp(salt_cp_cli, salt_minion, artifacts_path, cp_file_source):
    """
    Assert proper behaviour for salt-cp with a newer master and older minions.
    """
    remote_path = "/artifacts/cheese"
    ret = salt_cp_cli.run(
        str(cp_file_source), remote_path, minion_tgt=salt_minion.id, _timeout=300
    )
    assert ret.returncode == 0, ret
    assert ret.data is not None
    assert isinstance(ret.data, dict), ret.data
    assert ret.data == {remote_path: True}
    cp_file_dest = artifacts_path / "cheese"
    assert cp_file_source.read_text() == cp_file_dest.read_text()
