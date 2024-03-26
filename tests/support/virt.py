import logging
import sys
import time
import uuid

import attr
from pytestshellutils.utils import ports
from saltfactories.daemons.container import SaltMinion

from tests.conftest import CODE_DIR

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltVirtMinionContainerFactory(SaltMinion):

    host_uuid = attr.ib(default=attr.Factory(uuid.uuid4))
    ssh_port = attr.ib(
        default=attr.Factory(ports.get_unused_localhost_port), repr=False
    )
    sshd_port = attr.ib(default=attr.Factory(ports.get_unused_localhost_port))
    libvirt_tcp_port = attr.ib(
        default=attr.Factory(ports.get_unused_localhost_port), repr=False
    )
    libvirt_tls_port = attr.ib(
        default=attr.Factory(ports.get_unused_localhost_port), repr=False
    )

    uri = attr.ib(init=False)
    ssh_uri = attr.ib(init=False)
    tcp_uri = attr.ib(init=False)
    tls_uri = attr.ib(init=False)

    def __attrs_post_init__(self):
        self.uri = f"localhost:{self.sshd_port}"
        self.ssh_uri = f"qemu+ssh://{self.uri}/system"
        self.tcp_uri = f"qemu+tcp://localhost:{self.libvirt_tcp_port}/system"
        self.tls_uri = f"qemu+tls://127.0.0.1:{self.libvirt_tls_port}/system"

        if "environment" not in self.container_run_kwargs:
            self.container_run_kwargs["environment"] = {}
        self.container_run_kwargs["environment"].update(
            {
                "SSH_PORT": str(self.ssh_port),
                "SSHD_PORT": str(self.sshd_port),
                "LIBVIRT_TCP_PORT": str(self.libvirt_tcp_port),
                "LIBVIRT_TLS_PORT": str(self.libvirt_tls_port),
                "NO_START_MINION": "1",
                "HOST_UUID": self.host_uuid,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(CODE_DIR),
            }
        )
        super().__attrs_post_init__()
        if "volumes" not in self.container_run_kwargs:
            self.container_run_kwargs["volumes"] = {}
        self.container_run_kwargs["volumes"].update(
            {
                str(CODE_DIR): {"bind": "/salt", "mode": "z"},
            }
        )
        self.container_run_kwargs["working_dir"] = str(CODE_DIR)
        self.container_run_kwargs["network_mode"] = "host"
        self.container_run_kwargs["cap_add"] = ["ALL"]
        self.container_run_kwargs["privileged"] = True
        self.python_executable = "python3"
        self.container_start_check(self._check_script_path_exists)
        for port in (self.sshd_port, self.libvirt_tcp_port, self.libvirt_tls_port):
            self.check_ports[port] = port
        self.before_start(self._install_salt_in_container)

    def _check_script_path_exists(self, timeout_at):
        while time.time() <= timeout_at:
            # Once we're able to ls the salt-minion script it means the container
            # has salt installed
            ret = self.run("ls", "-lah", self.get_script_path())
            if ret.returncode == 0:
                break
            time.sleep(1)
        else:
            return False
        return True

    def _install_salt_in_container(self):
        ret = self.run("bash", "-c", "echo $SALT_PY_VERSION")
        assert ret.returncode == 0
        if not ret.stdout:
            log.warning(
                "The 'SALT_PY_VERSION' environment variable is not set on the container"
            )
            salt_py_version = 3
            ret = self.run(
                "python3",
                "-c",
                "import sys; sys.stderr.write('{}.{}'.format(*sys.version_info))",
            )
            assert ret.returncode == 0
            if not ret.stdout:
                requirements_py_version = "{}.{}".format(*sys.version_info)
            else:
                requirements_py_version = ret.stdout.strip()
        else:
            salt_py_version = requirements_py_version = ret.stdout.strip()

        self.python_executable = f"python{salt_py_version}"

        ret = self.run(
            self.python_executable,
            "-m",
            "pip",
            "install",
            f"--constraint=/salt/requirements/static/ci/py{requirements_py_version}/linux.txt",
            "/salt",
        )
        log.debug("Install Salt in the container: %s", ret)
        assert ret.returncode == 0
