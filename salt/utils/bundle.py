import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

from salt.exceptions import SaltException
from salt.utils import yaml
from salt.utils.files import fopen

try:
    import docker

    HAS_BUNDLE = True
except ImportError:
    HAS_BUNDLE = False


WHEEL_PATH = None


def build_wheel():
    """ """
    global WHEEL_PATH
    if WHEEL_PATH is None:
        # TODO get right tar and build
        # WHEEL_PATH = glob.glob(os.path.join(SALT_DIR, "dist", "*.tar.gz"))[0]
        pass
    return "/home/ch44d/Desktop/salt/dist/salt-3005.1+1451.g8ef9b100c4.tar.gz"
    # return WHEEL_PATH


def _make_file(docker_dir, tag, file_name, data, mode="w"):
    Path(docker_dir, tag).mkdir(parents=True, exist_ok=True)
    with fopen(os.path.join(docker_dir, tag, file_name), mode=mode) as file:
        file.write(data)


def _copy_file(docker_dir, tag, file_path, file_name=None):
    Path(docker_dir, tag).mkdir(parents=True, exist_ok=True)
    if file_name is None:
        file_name = os.path.split(file_path)[1]
    dst_file_path = os.path.join(docker_dir, tag, file_name)
    shutil.copyfile(file_path, dst_file_path)


def build_image(
    docker_dir,
    tag,
    docker_from=None,
    master_config=None,
    minion_config=None,
    minion_name=None,
    port=None,
    state_files=None,
    salt_version=None,
    no_salt=False,
):
    """ """

    if not HAS_BUNDLE:
        raise SaltException("Bundle is not available!")

    if docker_from is None:
        docker_from = "python:3.8"
    docker_file = f"FROM {docker_from}\n" f"WORKDIR /salt\n"

    if no_salt is False:
        if salt_version is None:
            docker_file += f"COPY salt.tar.gz .\n"
            docker_file += f"RUN python3 -m pip install salt.tar.gz\n"
            _copy_file(docker_dir, tag, build_wheel(), "salt.tar.gz")
        else:
            docker_file += f"RUN python3 -m pip install salt=={salt_version}\n"

    if master_config is not None:
        if isinstance(master_config, dict):
            master_config = yaml.dump(master_config)
        _make_file(docker_dir, tag, "master", master_config)
        docker_file += "COPY master /etc/salt/master\n"

    if minion_config is not None:
        if isinstance(minion_config, dict):
            minion_config = yaml.dump(minion_config)
        _make_file(docker_dir, tag, "minion", minion_config)
        docker_file += "COPY minion /etc/salt/minion\n"

    if minion_name is not None:
        _make_file(docker_dir, tag, "minion_id", minion_name)
        docker_file += "COPY minion_id /etc/salt/minion_id\n"

    if port is None:
        port = ("4506",)

    for p in port:
        docker_file += f"EXPOSE {p}\n"

    if state_files is None:
        state_files = {}

    for state_name, data in state_files.items():
        if not isinstance(data, str):
            data = yaml.dump(data)
        state_name += ".sls"
        _make_file(docker_dir, tag, state_name, data)
        docker_file += f"COPY {state_name} /srv/salt/{state_name}\n"

    _make_file(docker_dir, tag, "Dockerfile", docker_file)

    env = docker.from_env()
    # build docker image
    env.images.build(path=str(Path(docker_dir, tag)), tag=tag)


class Bundle:
    def __init__(self, tag):
        if not HAS_BUNDLE:
            raise SaltException("Bundle is not available!")

        self._open = True
        env = docker.from_env()
        self._container = env.containers.run(
            tag, command="sleep 86400", network="host", detach=True
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):  # pylint: disable=no-dunder-del
        self.close()

    def close(self):
        if self._open:
            self._open = False
            try:
                self._container.kill()
            except docker.errors.APIError:
                pass

    def run(self, command, detach=False, encoding="utf-8"):
        ret = self._container.exec_run(command, detach=detach)
        if detach is True:
            return
        output = ret.output
        if encoding is not None:
            output = str(output, encoding)
        return output, ret.exit_code


class Bundles:
    def __init__(self, temp_dir=False):
        self._open = True
        self._bundles = {}
        self._temp_dir = None
        if temp_dir is True:
            self._temp_dir = TemporaryDirectory()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):  # pylint: disable=no-dunder-del
        self.close()

    def __contains__(self, item):
        return item in self._bundles

    def __getitem__(self, item):
        return self._bundles[item]

    def close(self):
        if self._open:
            self._open = False
            for _, bundle in self._bundles.items():
                bundle.close()
            if self._temp_dir is not None:
                self._temp_dir.cleanup()

    def temp_dir(self):
        if self._temp_dir is None:
            return None
        return self._temp_dir.name

    def add_bundle(self, name, bundle):
        if name in self._bundles:
            raise SaltException("Bundle name is all ready taken!")
        self._bundles[name] = bundle

    def bundles(self):
        return self._bundles


class PlayGround(Bundles):
    def __init__(
        self,
        docker_dir=None,
        tag_start=None,
        docker_from=None,
        master_config=None,
        master_minion_config=None,
        master_minion_name=None,
        minion_config=None,
        minion_name=None,
        minion_count=1,
        minion_configs=None,
        port=None,
        state_files=None,
        salt_version=None,
        start=True,
    ):
        # start master and minion
        super().__init__(docker_dir is None)
        if docker_dir is None:
            docker_dir = self.temp_dir()

        if tag_start is None:
            tag_start = ""
        else:
            tag_start += "-"

        if master_config is None:
            master_config = {"interface": "127.0.0.1"}

        master_tag = f"{tag_start}master"
        build_image(
            docker_dir,
            master_tag,
            docker_from,
            master_config,
            master_minion_config,
            master_minion_name,
            port,
            state_files,
            salt_version,
        )
        master = Bundle(master_tag)
        self.add_bundle(master_tag, master)

        minions = []
        if master_minion_config is not None:
            minions.append(master)

        if minion_config is not None and minion_configs is not None:
            raise SaltException("Can't have minion_config and minion_configs")

        if minion_config is None and minion_configs is None:
            minion_config = {"master": "127.0.0.1"}

        if minion_name is None:
            minion_name = "minion"

        if minion_config is not None:
            if minion_count == 1:
                minion_tag = f"{tag_start}minion"
                if minion_name is not None:
                    minion_tag = f"{tag_start}{minion_name}"
                build_image(
                    docker_dir,
                    minion_tag,
                    docker_from,
                    minion_config,
                    minion_config,
                    minion_name,
                    port,
                    state_files,
                    salt_version,
                )
                minion = Bundle(minion_tag)
                self.add_bundle(minion_name, minion)
                minions.append(minion)
            else:
                for i in range(1, minion_count + 1):
                    minion_tag = f"{tag_start}{minion_name}-{i}"
                    build_image(
                        docker_dir,
                        minion_tag,
                        docker_from,
                        minion_config,
                        minion_config,
                        f"{minion_name}-{i}",
                        port,
                        state_files,
                        salt_version,
                    )
                    minion = Bundle(minion_tag)
                    self.add_bundle(f"{minion_name}-{i}", minion)
                    minions.append(minion)
        else:
            raise NotImplementedError()

        if start:
            # start minions and masters
            master.run("salt-master", detach=True)
            for minion in minions:
                minion.run("salt-minion", detach=True)

            if minions:
                for _ in range(80):
                    master.run("salt-key -A -y")
                    output, _ = master.run("salt '*' test.ping --summary")
                    if (
                        f"minions returned: {len(minions)}" in output
                        and "minions with errors: 0" in output
                    ):
                        break
                    sleep(0.5)
                else:
                    raise TimeoutError()
