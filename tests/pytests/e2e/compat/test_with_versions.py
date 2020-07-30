# -*- coding: utf-8 -*-
"""
    tests.e2e.compat.test_with_versions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test current salt master with older salt minions
"""
import io
import logging
import os
import pathlib

import attr
import pytest
from saltfactories.factories.daemons.docker import MinionDockerFactory
from tests.support.helpers import random_string
from tests.support.runtests import RUNTIME_VARS

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class PySaltCombo:
    python_version = attr.ib()
    salt_version = attr.ib()


DOCKERFILE = """
FROM {from_container}
ENV LANG=en_US.UTF8

ENV VIRTUAL_ENV={virtualenv_path}

RUN virtualenv --python=python{python_version} $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install salt=={salt_version}
{extra}

CMD . $VIRTUAL_ENV/bin/activate
"""


def _get_test_versions():
    test_versions = []
    for python_version in ("2", "3"):
        for salt_version in ("2017.7.8", "2018.3.5", "2019.2.4"):
            test_versions.append(
                PySaltCombo(python_version=python_version, salt_version=salt_version)
            )
    test_versions.append(PySaltCombo(python_version="3", salt_version="3000.1"))
    return test_versions


def _get_test_versions_ids(pysaltcombo):
    return "Py{}-SaltMinion=={}".format(
        pysaltcombo.python_version, pysaltcombo.salt_version
    )


@pytest.fixture(
    params=_get_test_versions(), ids=_get_test_versions_ids, scope="function"
)
def pysaltcombo(request):
    return request.param


@pytest.fixture(scope="function")
def container_virtualen_path():
    return "/tmp/venv"


@pytest.fixture(scope="function")
def minion_container_name(pysaltcombo):
    return "salt-py{}-{}".format(pysaltcombo.python_version, pysaltcombo.salt_version)


@pytest.fixture(scope="function")
def minion_container(
    docker_client, pysaltcombo, container_virtualen_path, minion_container_name
):
    extra = ""
    if pysaltcombo.salt_version.startswith(("2017.7.", "2018.3.", "2019.2.")):
        # We weren't pinning higher versions which we now know are problematic
        extra = "RUN pip install --ignore-installed --progress-bar=off -U "
        extra += (
            '"pyzmq<17.1.0,>=2.2.0" "tornado<5.0,>=4.2.1" "msgpack>=0.5,!=0.5.5,<1.0.0"'
        )
    dockerfile_contents = DOCKERFILE.format(
        from_container="saltstack/ci-centos-7",
        python_version=pysaltcombo.python_version,
        salt_version=pysaltcombo.salt_version,
        extra=extra,
        virtualenv_path=container_virtualen_path,
    )
    log.warning("GENERATED Dockerfile:\n%s", dockerfile_contents)
    dockerfile_fh = io.BytesIO(dockerfile_contents.encode("utf-8"))
    docker_image, logs = docker_client.images.build(
        fileobj=dockerfile_fh, tag=minion_container_name, pull=True,
    )
    log.warning("Image %s built. Logs:\n%s", minion_container_name, list(logs))
    return minion_container_name


@pytest.fixture(scope="function")
def minion_id(pysaltcombo):
    return random_string(
        "py{}-{}-".format(pysaltcombo.python_version, pysaltcombo.salt_version),
        uppercase=False,
    )


@pytest.fixture(scope="function")
def artefacts_path(minion_id):
    with pytest.helpers.temp_directory(minion_id) as temp_directory:
        yield temp_directory


@pytest.mark.skip_if_binaries_missing("docker")
@pytest.fixture(scope="function")
def salt_minion(
    request,
    salt_factories,
    pysaltcombo,
    minion_id,
    salt_master,
    docker_client,
    artefacts_path,
    container_virtualen_path,
    minion_container,
    host_docker_network_ip_address,
):
    config_overrides = {
        "master": salt_master.config["interface"],
        "user": False,
        "pytest-minion": {"log": {"host": host_docker_network_ip_address}},
    }
    try:
        yield salt_factories.spawn_minion(
            request,
            minion_id,
            master_id=salt_master.config["id"],
            # config_defaults=config_defaults,
            config_overrides=config_overrides,
            factory_class=MinionDockerFactory,
            docker_client=docker_client,
            image=minion_container,
            name=minion_id,
            start_timeout=120,
            container_run_kwargs={
                "volumes": {artefacts_path: {"bind": "/artefacts", "mode": "z"}}
            },
        )
    finally:
        minion_key_file = os.path.join(
            salt_master.config["pki_dir"], "minions", minion_id
        )
        log.debug("Minion %r KEY FILE: %s", minion_id, minion_key_file)
        if os.path.exists(minion_key_file):
            os.unlink(minion_key_file)


@pytest.fixture(scope="function")
def package_name():
    return "comps-extras"


@pytest.fixture
def populated_state_tree(minion_id, package_name):
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
    state-entry-does-not-contain-unicode:
        pkg.installed:
          - name: {{ salt.pkgnames.get_test_package_name() }}
    """
    with pytest.helpers.temp_file(
        name="pkgnames.py",
        directory=os.path.join(RUNTIME_VARS.TMP_BASEENV_STATE_TREE, "_modules"),
        contents=module_contents,
    ):
        with pytest.helpers.temp_state_file("top.sls", contents=top_file_contents):
            with pytest.helpers.temp_state_file(
                "install-package.sls", contents=install_package_sls_contents
            ):
                # Run the test
                yield


@pytest.fixture
def populated_state_tree_unicode(pysaltcombo, minion_id, package_name):
    if pysaltcombo.salt_version.startswith("2017.7."):
        pytest.xfail("2017.7 is know for problematic unicode handling on state files")
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
        name="pkgnames.py",
        directory=os.path.join(RUNTIME_VARS.TMP_BASEENV_STATE_TREE, "_modules"),
        contents=module_contents,
    ):
        with pytest.helpers.temp_state_file("top.sls", contents=top_file_contents):
            with pytest.helpers.temp_state_file(
                "install-package.sls", contents=install_package_sls_contents
            ):
                # Run the test
                yield


def test_ping(salt_cli, minion_id, salt_minion):
    assert salt_minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt=minion_id)
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_highstate(
    salt_cli, minion_id, salt_minion, package_name, populated_state_tree
):
    """
    Assert a state.highstate with a newer master runs properly on older minions.
    """
    assert salt_minion.is_running()
    ret = salt_cli.run("state.highstate", minion_tgt=minion_id, _timeout=240)
    assert ret.exitcode == 0, ret
    assert ret.json is not None
    assert isinstance(ret.json, dict), ret.json
    state_return = next(iter(ret.json.values()))
    assert package_name in state_return["changes"], state_return


def test_highstate_with_unicode(
    salt_cli,
    minion_id,
    salt_minion,
    package_name,
    populated_state_tree_unicode,
    pysaltcombo,
):
    """
    Assert a state.highstate with a newer master runs properly on older minions.
    The highstate tree additionally contains unicode chars to assert they're properly hanbled
    """
    assert salt_minion.is_running()
    ret = salt_cli.run("state.highstate", minion_tgt=minion_id, _timeout=240)
    assert ret.exitcode == 0, ret
    assert ret.json is not None
    assert isinstance(ret.json, dict), ret.json
    state_return = next(iter(ret.json.values()))
    assert package_name in state_return["changes"], state_return


@pytest.fixture
def cp_file_source(pysaltcombo):
    if pysaltcombo.salt_version.startswith("2018.3."):
        pytest.xfail("2018.3 is know for unicode issues when copying files")
    source = pathlib.Path(RUNTIME_VARS.BASE_FILES) / "cheese"
    with pytest.helpers.temp_file(contents=source.read_text()) as temp_file:
        yield pathlib.Path(temp_file)


def test_cp(
    salt_cp_cli, minion_id, salt_minion, package_name, artefacts_path, cp_file_source
):
    """
    Assert proper behaviour for salt-cp with a newer master and older minions.
    """
    assert salt_minion.is_running()
    remote_path = "/artefacts/cheese"
    ret = salt_cp_cli.run(
        str(cp_file_source), remote_path, minion_tgt=minion_id, _timeout=240
    )
    assert ret.exitcode == 0, ret
    assert ret.json is not None
    assert isinstance(ret.json, dict), ret.json
    assert ret.json == {remote_path: True}
    cp_file_dest = pathlib.Path(artefacts_path) / "cheese"
    assert cp_file_source.read_text() == cp_file_dest.read_text()


@pytest.fixture
def cp_file_source_unicode(pysaltcombo):
    source = pathlib.Path(RUNTIME_VARS.BASE_FILES) / "cheese"
    contents = source.read_text().replace("ee", "æ")
    with pytest.helpers.temp_file(contents=contents) as temp_file:
        yield pathlib.Path(temp_file)


def test_cp_unicode(
    salt_cp_cli,
    minion_id,
    salt_minion,
    package_name,
    artefacts_path,
    cp_file_source_unicode,
):
    """
    Assert proper behaviour for salt-cp with a newer master and older minions.
    """
    assert salt_minion.is_running()
    remote_path = "/artefacts/cheese"
    ret = salt_cp_cli.run(
        str(cp_file_source_unicode), remote_path, minion_tgt=minion_id, _timeout=240
    )
    assert ret.exitcode == 0, ret
    assert ret.json is not None
    assert isinstance(ret.json, dict), ret.json
    assert ret.json == {remote_path: True}
    cp_file_dest = pathlib.Path(artefacts_path) / "cheese"
    assert cp_file_source_unicode.read_text() == cp_file_dest.read_text()
