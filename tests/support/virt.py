import time
import uuid

import attr
from saltfactories.daemons.container import SaltMinion
from saltfactories.utils import ports
from tests.support.runtests import RUNTIME_VARS


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
        self.uri = "localhost:{}".format(self.sshd_port)
        self.ssh_uri = "qemu+ssh://{}/system".format(self.uri)
        self.tcp_uri = "qemu+tcp://localhost:{}/system".format(self.libvirt_tcp_port)
        self.tls_uri = "qemu+tls://127.0.0.1:{}/system".format(self.libvirt_tls_port)

        # pylint: disable=access-member-before-definition
        if self.check_ports is None:
            self.check_ports = []
        # pylint: enable=access-member-before-definition
        self.check_ports.extend(
            [self.sshd_port, self.libvirt_tcp_port, self.libvirt_tls_port]
        )
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
            }
        )
        if "ports" not in self.container_run_kwargs:
            self.container_run_kwargs["ports"] = {}
        self.container_run_kwargs["ports"].update(
            {
                "{}/tcp".format(self.ssh_port): self.ssh_port,
                "{}/tcp".format(self.sshd_port): self.sshd_port,
                "{}/tcp".format(self.libvirt_tcp_port): self.libvirt_tcp_port,
                "{}/tcp".format(self.libvirt_tls_port): self.libvirt_tls_port,
            }
        )
        if "volumes" not in self.container_run_kwargs:
            self.container_run_kwargs["volumes"] = {}
        self.container_run_kwargs["volumes"].update(
            {
                RUNTIME_VARS.CODE_DIR: {"bind": "/salt", "mode": "z"},
                RUNTIME_VARS.CODE_DIR: {"bind": RUNTIME_VARS.CODE_DIR, "mode": "z"},
            }
        )
        self.container_run_kwargs["working_dir"] = RUNTIME_VARS.CODE_DIR
        self.container_run_kwargs["network_mode"] = "host"
        self.container_run_kwargs["cap_add"] = ["ALL"]
        self.container_run_kwargs["privileged"] = True
        super().__attrs_post_init__()
        self.python_executable = "python3"

    def _container_start_checks(self):
        # Once we're able to ls the salt-minion script it means the container
        # has salt installed
        ret = self.run("ls", "-lah", self.get_script_path())
        if ret.exitcode == 0:
            return True
        time.sleep(1)
        return False
