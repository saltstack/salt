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
from collections import namedtuple

import pytest

# import salt.utils.user
import saltfactories
from saltfactories.utils.processes.salts import SaltMinion as SaltFactoriesMinion
from tests.support.helpers import random_string
from tests.support.runtests import RUNTIME_VARS

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)


PySaltCombo = namedtuple("PySaltCombo", ("python_version", "salt_version"))

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


class SaltMinion(SaltFactoriesMinion):
    def __init__(
        self,
        salt_version,
        python_version,
        docker_client,
        *args,
        artefacts_path=None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.salt_version = salt_version
        self.python_version = python_version
        self.docker_client = docker_client
        self.container_name = "salt-py{}-{}".format(python_version, salt_version)
        self.virtualenv_path = "/tmp/venv"
        self.artefacts_path = artefacts_path

    def start(self):
        minion_conf_d = os.path.join(self.config_dir, "minion.d")
        if not os.path.isdir(minion_conf_d):
            os.makedirs(minion_conf_d)
        extra = ""
        if self.salt_version.startswith(("2017.7.", "2018.3.", "2019.2.")):
            # We weren't pinning higher versions which we now know are problematic
            extra = "RUN pip install --ignore-installed --progress-bar=off -U "
            extra += '"pyzmq<17.1.0,>=2.2.0" "tornado<5.0,>=4.2.1" "msgpack>=0.5,!=0.5.5,<1.0.0"'
        dockerfile_contents = DOCKERFILE.format(
            from_container="saltstack/ci-centos-7",
            python_version=self.python_version,
            salt_version=self.salt_version,
            extra=extra,
            virtualenv_path=self.virtualenv_path,
        )
        log.warning("GENERATED Dockerfile:\n%s", dockerfile_contents)
        dockerfile_fh = io.BytesIO(dockerfile_contents.encode("utf-8"))
        self.image, logs = self.docker_client.images.build(
            fileobj=dockerfile_fh, tag=self.container_name, pull=True,
        )
        log.warning("Image %s built. Logs:\n%s", self.container_name, list(logs))
        root_dir = os.path.dirname(self.config["root_dir"])
        saltfactories_path = os.path.dirname(saltfactories.__file__)
        volumes = {
            root_dir: {"bind": root_dir, "mode": "z"},
            saltfactories_path: {"bind": saltfactories_path, "mode": "z"},
        }
        if self.artefacts_path:
            volumes[self.artefacts_path] = {"bind": "/artefacts", "mode": "z"}
        self.container = self.docker_client.containers.run(
            self.image.id,
            name=self.config["id"],
            detach=True,
            # auto_remove=True,
            stdin_open=True,
            volumes=volumes,
            # user=salt.utils.user.get_uid()
        )
        log.warning("CONTAINER 1: %s // %s", self.container, self.container.status)
        while True:
            container = self.docker_client.containers.get(self.container.id)
            log.warning("CONTAINER 2: %s // %s", container, container.status)
            if container.status == "running":
                self.container = container
                break
            import time

            time.sleep(1)
        log.warning(
            "CONTAINER 3: %s // %s // Logs:\n%s",
            self.container,
            self.container.status,
            self.container.logs(),
        )
        return super().start()

    def terminate(self):
        try:
            container = self.docker_client.containers.get(self.container.id)
            log.warning("Running Container Logs:\n%s", container.logs())
            if container.status == "running":
                container.remove(force=True)
                container.wait()
        except docker.errors.NotFound:
            pass
        return super().terminate()

    def get_script_path(self):
        return os.path.join(self.virtualenv_path, "bin", "salt-minion")

    def build_cmdline(self, *args, **kwargs):
        original_cmdline = super().build_cmdline(*args, **kwargs)
        if original_cmdline[0] == self.python_executable:
            original_cmdline[0] = "python{}".format(self.python_version)
        return ["docker", "exec", "-i", self.container.short_id] + original_cmdline


def _get_test_versions():
    test_versions = []
    for python_version in ("2", "3"):
        for salt_version in ("2017.7.8", "2018.3.5", "2019.2.4"):
            test_versions.append(PySaltCombo(python_version, salt_version))
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
):
    config_overrides = {"master": salt_master.config["interface"], "user": False}
    try:
        yield salt_factories.spawn_minion(
            request,
            minion_id,
            master_id=salt_master.config["id"],
            # config_defaults=config_defaults,
            config_overrides=config_overrides,
            daemon_class=SaltMinion,
            python_version=pysaltcombo.python_version,
            salt_version=pysaltcombo.salt_version,
            docker_client=docker_client,
            python_executable="python{}".format(pysaltcombo.python_version),
            artefacts_path=artefacts_path,
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
    # if minion_version.startswith("2017.7."):
    #    pytest.xfail("2017.7 is know for problematic unicode handling on state files")
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
    assert salt_minion.is_alive()
    ret = salt_cli.run("test.ping", minion_tgt=minion_id)
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_highstate(
    salt_cli, minion_id, salt_minion, package_name, populated_state_tree
):
    """
    Assert a state.highstate with a newer master runs properly on older minions.
    """
    assert salt_minion.is_alive()
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
    assert salt_minion.is_alive()
    ret = salt_cli.run("state.highstate", minion_tgt=minion_id, _timeout=240)
    assert ret.exitcode == 0, ret
    assert ret.json is not None
    assert isinstance(ret.json, dict), ret.json
    state_return = next(iter(ret.json.values()))
    assert package_name in state_return["changes"], state_return


@pytest.fixture
def cp_file_source(pysaltcombo):
    # if minion_version.startswith("2018.3."):
    #    pytest.xfail("2018.3 is know for unicode issues when copying files")
    source = pathlib.Path(RUNTIME_VARS.BASE_FILES) / "cheese"
    with pytest.helpers.temp_file(contents=source.read_text()) as temp_file:
        yield pathlib.Path(temp_file)


def test_cp(
    salt_cp_cli, minion_id, salt_minion, package_name, artefacts_path, cp_file_source
):
    """
    Assert proper behaviour for salt-cp with a newer master and older minions.
    """
    assert salt_minion.is_alive()
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
    assert salt_minion.is_alive()
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
