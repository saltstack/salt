"""
    tests.e2e.compat.test_with_versions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test current salt master with older salt minions
"""
import io
import logging
import pathlib

import pytest
import salt.utils.platform
from saltfactories.daemons.container import SaltMinion
from saltfactories.utils import random_string
from tests.support.runtests import RUNTIME_VARS

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)


pytestmark = pytest.mark.skipif(
    salt.utils.platform.is_photonos() is True, reason="Skip on PhotonOS"
)


DOCKERFILE = """
FROM {from_container}
ENV LANG=en_US.UTF8

ENV VIRTUAL_ENV={virtualenv_path}

RUN virtualenv --python=python3 $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install salt~={salt_version}

CMD . $VIRTUAL_ENV/bin/activate
"""


def _get_test_versions_ids(value):
    return "SaltMinion~={}".format(value)


@pytest.fixture(
    params=("3002.0", "3003.0", "3004.0"), ids=_get_test_versions_ids, scope="module"
)
def compat_salt_version(request):
    return request.param


@pytest.fixture(scope="module")
def container_virtualenv_path():
    return "/tmp/venv"


@pytest.fixture(scope="module")
def minion_image_name(compat_salt_version):
    return "salt-{}".format(compat_salt_version)


@pytest.fixture(scope="module")
def minion_image(
    docker_client, compat_salt_version, container_virtualenv_path, minion_image_name
):
    dockerfile_contents = DOCKERFILE.format(
        from_container="saltstack/ci-centos-7",
        salt_version=compat_salt_version,
        virtualenv_path=container_virtualenv_path,
    )
    log.debug("GENERATED Dockerfile:\n%s", dockerfile_contents)
    dockerfile_fh = io.BytesIO(dockerfile_contents.encode("utf-8"))
    _, logs = docker_client.images.build(
        fileobj=dockerfile_fh,
        tag=minion_image_name,
        pull=True,
    )
    log.warning("Image %s built. Logs:\n%s", minion_image_name, list(logs))
    return minion_image_name


@pytest.fixture(scope="function")
def minion_id(compat_salt_version):
    return random_string(
        "salt-{}-".format(compat_salt_version),
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
    minion_image,
    host_docker_network_ip_address,
):
    config_overrides = {
        "master": salt_master.config["interface"],
        "user": False,
        "pytest-minion": {"log": {"host": host_docker_network_ip_address}},
        # We also want to scrutinize the key acceptance
        "open_mode": False,
    }
    factory = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        factory_class=SaltMinion,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        # SaltMinion kwargs
        name=minion_id,
        image=minion_image,
        docker_client=docker_client,
        start_timeout=120,
        container_run_kwargs={
            "volumes": {str(artifacts_path): {"bind": "/artifacts", "mode": "z"}}
        },
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="function")
def package_name():
    return "comps-extras"


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


def test_ping(salt_cli, salt_minion):
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.exitcode == 0, ret
    assert ret.json is True


@pytest.mark.usefixtures("populated_state_tree")
def test_highstate(salt_cli, salt_minion, package_name):
    """
    Assert a state.highstate with a newer master runs properly on older minions.
    """
    ret = salt_cli.run("state.highstate", minion_tgt=salt_minion.id, _timeout=300)
    assert ret.exitcode == 0, ret
    assert ret.json is not None
    assert isinstance(ret.json, dict), ret.json
    state_return = next(iter(ret.json.values()))
    assert package_name in state_return["changes"], state_return


@pytest.fixture
def cp_file_source():
    source = pathlib.Path(RUNTIME_VARS.BASE_FILES) / "cheese"
    contents = source.read_text().replace("ee", "æ")
    with pytest.helpers.temp_file(contents=contents) as temp_file:
        yield pathlib.Path(temp_file)


def test_cp(salt_cp_cli, salt_minion, artifacts_path, cp_file_source):
    """
    Assert proper behaviour for salt-cp with a newer master and older minions.
    """
    remote_path = "/artifacts/cheese"
    ret = salt_cp_cli.run(
        str(cp_file_source), remote_path, minion_tgt=salt_minion.id, _timeout=300
    )
    assert ret.exitcode == 0, ret
    assert ret.json is not None
    assert isinstance(ret.json, dict), ret.json
    assert ret.json == {remote_path: True}
    cp_file_dest = artifacts_path / "cheese"
    assert cp_file_source.read_text() == cp_file_dest.read_text()
