"""
Validate the virt module
"""

import logging
from numbers import Number
from xml.etree import ElementTree

import pytest

from tests.support.virt import SaltVirtMinionContainerFactory

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout_unless_on_windows(120),
    pytest.mark.skip_if_binaries_missing("docker"),
]


@pytest.fixture(scope="module")
def virt_minion_0_id():
    return "virt-minion-0"


@pytest.fixture(scope="module")
def virt_minion_1_id():
    return "virt-minion-1"


@pytest.fixture(scope="module")
def virt_minion_0(
    salt_master,
    virt_minion_0_id,
    virt_minion_1_id,
):
    config_defaults = {
        "id": virt_minion_0_id,
        "open_mode": True,
        "transport": salt_master.config["transport"],
    }
    config_overrides = {"user": "root"}
    factory = salt_master.salt_minion_daemon(
        virt_minion_0_id,
        name=virt_minion_0_id,
        image="ghcr.io/saltstack/salt-ci-containers/virt-minion",
        factory_class=SaltVirtMinionContainerFactory,
        defaults=config_defaults,
        overrides=config_overrides,
        container_run_kwargs={
            "extra_hosts": {
                virt_minion_0_id: "127.0.0.1",
                virt_minion_1_id: "127.0.0.1",
            },
            "cgroupns": "host",
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def virt_minion_1(
    salt_master,
    virt_minion_0_id,
    virt_minion_1_id,
):
    config_defaults = {
        "id": virt_minion_1_id,
        "open_mode": True,
        "transport": salt_master.config["transport"],
    }
    config_overrides = {"user": "root"}
    factory = salt_master.salt_minion_daemon(
        virt_minion_1_id,
        name=virt_minion_1_id,
        image="ghcr.io/saltstack/salt-ci-containers/virt-minion",
        factory_class=SaltVirtMinionContainerFactory,
        defaults=config_defaults,
        overrides=config_overrides,
        container_run_kwargs={
            "extra_hosts": {
                virt_minion_0_id: "127.0.0.1",
                virt_minion_1_id: "127.0.0.1",
            },
            "cgroupns": "host",
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def salt_cli(salt_master, virt_minion_0, virt_minion_1):
    return salt_master.salt_cli()


class TestVirtTest:
    """
    Test virt routines
    """

    cpu_models = [
        "none",
        "armv7l",
        "armv7b",
        "aarch64",
        "i686",
        "ppc64",
        "ppc64le",
        "riscv32",
        "riscv64",
        "s390",
        "s390x",
        "x86_64",
    ]

    def test_default_kvm_profile(self, salt_cli, virt_minion_0):
        """
        Test virt.get_profiles with the KVM profile
        """
        ret = salt_cli.run("virt.get_profiles", "kvm", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        profiles = ret.data
        assert isinstance(profiles, dict)
        nic = profiles["nic"]["default"][0]
        disk = profiles["disk"]["default"][0]

        assert nic["name"] == "eth0"
        assert nic["type"] == "bridge"
        assert nic["model"] == "virtio"
        assert nic["source"] == "br0"

        assert disk["name"] == "system"
        assert disk["model"] == "virtio"
        assert disk["size"] == 8192

    def test_default_vmware_profile(self, salt_cli, virt_minion_0):
        """
        Test virt.get_profiles with the VMware profile
        """
        ret = salt_cli.run("virt.get_profiles", "vmware", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        profiles = ret.data
        assert isinstance(profiles, dict)
        nic = profiles["nic"]["default"][0]
        disk = profiles["disk"]["default"][0]

        assert nic["name"] == "eth0"
        assert nic["type"] == "bridge"
        assert nic["model"] == "e1000"
        assert nic["source"] == "DEFAULT"

        assert disk["name"] == "system"
        assert disk["model"] == "scsi"
        assert disk["format"] == "vmdk"
        assert disk["size"] == 8192

    def test_default_xen_profile(self, salt_cli, virt_minion_0):
        """
        Test virt.get_profiles with the XEN profile
        """
        ret = salt_cli.run("virt.get_profiles", "xen", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        profiles = ret.data
        assert isinstance(profiles, dict)
        nic = profiles["nic"]["default"][0]
        disk = profiles["disk"]["default"][0]

        assert nic["name"] == "eth0"
        assert nic["type"] == "bridge"
        assert nic["model"] is None
        assert nic["source"] == "br0"

        assert disk["name"] == "system"
        assert disk["model"] == "xen"
        assert disk["size"] == 8192

    def test_default_bhyve_profile(self, salt_cli, virt_minion_0):
        """
        Test virt.get_profiles with the Bhyve profile
        """
        ret = salt_cli.run("virt.get_profiles", "bhyve", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        profiles = ret.data
        assert isinstance(profiles, dict)
        nic = profiles["nic"]["default"][0]
        disk = profiles["disk"]["default"][0]

        assert nic["name"] == "eth0"
        assert nic["type"] == "bridge"
        assert nic["model"] == "virtio"
        assert nic["source"] == "bridge0"

        assert disk["name"] == "system"
        assert disk["model"] == "virtio"
        assert disk["format"] == "raw"
        assert disk["sparse_volume"] is False
        assert disk["size"] == 8192

    def test_all_capabilities(self, salt_cli, virt_minion_0):
        """
        Test virt.all_capabilities
        """
        ret = salt_cli.run("virt.all_capabilities", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        caps = ret.data
        assert isinstance(caps, dict)
        assert isinstance(caps["host"]["host"]["uuid"], str)
        assert len(caps["host"]["host"]["uuid"]) == 36
        assert "qemu" in [domainCaps["domain"] for domainCaps in caps["domains"]]

    def test_capabilities(self, salt_cli, virt_minion_0):
        """
        Test virt.capabilities
        """
        ret = salt_cli.run("virt.capabilities", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        caps = ret.data
        assert isinstance(caps, dict)
        assert isinstance(caps["host"]["uuid"], str)
        assert len(caps["host"]["uuid"]) == 36
        assert len(caps["guests"]) >= 1
        assert caps["guests"][0]["os_type"] in ["hvm", "xen", "xenpvh", "exe"]

    def test_cpu_baseline(self, salt_cli, virt_minion_0, grains):
        """
        Test virt.cpu_baseline
        """
        if grains.get("osarch", "") != "x86_64":
            raise pytest.skip.Exception(
                f"Test is only meant to run on 'x86_64' architecture, not '{grains['osarch']}'",
                _use_item_location=True,
            )
        vendors = ["Intel", "ARM", "AMD"]
        ret = salt_cli.run(
            "virt.cpu_baseline", out="libvirt", minion_tgt=virt_minion_0.id
        )
        assert ret.returncode == 0, ret
        cpu_baseline = ret.data
        assert isinstance(cpu_baseline, str)
        cpu_baseline = ElementTree.fromstring(cpu_baseline)
        assert cpu_baseline.find("vendor").text in vendors

        ret = salt_cli.run("virt.cpu_baseline", out="salt", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        cpu_baseline = ret.data
        assert isinstance(cpu_baseline, dict)
        assert cpu_baseline["vendor"] in vendors

    def test_freemem(self, salt_cli, virt_minion_0):
        """
        Test virt.freemem
        """
        ret = salt_cli.run("virt.freemem", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        available_memory = ret.data
        assert isinstance(available_memory, Number)
        assert available_memory > 0

    def test_freecpu(self, salt_cli, virt_minion_0):
        """
        Test virt.freecpu
        """
        ret = salt_cli.run("virt.freecpu", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        available_cpus = ret.data
        assert isinstance(available_cpus, Number)
        assert available_cpus > 0

    def test_full_info(self, salt_cli, virt_minion_0):
        """
        Test virt.full_info
        """
        ret = salt_cli.run("virt.full_info", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        info = ret.data
        assert isinstance(info, dict)
        assert isinstance(info["vm_info"], dict)

        assert isinstance(info["freecpu"], Number)
        assert isinstance(info["freemem"], Number)
        assert info["freecpu"] > 0
        assert info["freemem"] > 0

        assert isinstance(info["node_info"], dict)
        assert isinstance(info["node_info"]["cpucores"], Number)
        assert isinstance(info["node_info"]["cpumhz"], Number)
        assert isinstance(info["node_info"]["cpus"], Number)
        assert isinstance(info["node_info"]["cputhreads"], Number)
        assert isinstance(info["node_info"]["numanodes"], Number)
        assert isinstance(info["node_info"]["phymemory"], Number)
        assert info["node_info"]["cpumodel"] in self.cpu_models

    def test_node_info(self, salt_cli, virt_minion_0):
        """
        Test virt.node_info
        """
        ret = salt_cli.run("virt.node_info", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        info = ret.data
        assert isinstance(info, dict)
        assert isinstance(info["cpucores"], Number)
        assert isinstance(info["cpumhz"], Number)
        assert isinstance(info["cpus"], Number)
        assert isinstance(info["cputhreads"], Number)
        assert isinstance(info["numanodes"], Number)
        assert isinstance(info["phymemory"], Number)
        assert isinstance(info["sockets"], Number)
        assert info["cpumodel"] in self.cpu_models


@pytest.fixture(scope="module")
def virt_domain():
    return "core-vm"


@pytest.fixture
def prep_virt(salt_cli, virt_minion_0, virt_minion_1, virt_domain, grains):
    if grains.get("osarch", "") != "x86_64":
        raise pytest.skip.Exception(
            f"Test is only meant to run on 'x86_64' architecture, not '{grains['osarch']}'",
            _use_item_location=True,
        )
    try:
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        for domain in domains:
            salt_cli.run("virt.stop", virt_domain, minion_tgt=virt_minion_0.id)
            salt_cli.run("virt.undefine", virt_domain, minion_tgt=virt_minion_0.id)
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        for domain in domains:
            salt_cli.run("virt.stop", virt_domain, minion_tgt=virt_minion_1.id)
            salt_cli.run("virt.undefine", virt_domain, minion_tgt=virt_minion_1.id)
        ret = salt_cli.run(
            "virt.define_xml_path",
            f"/{virt_domain}.xml",
            minion_tgt=virt_minion_0.id,
        )
        assert ret.returncode == 0, ret
        ret = salt_cli.run("virt.start", virt_domain, minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        # Run tests
        yield
    finally:
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        for domain in domains:
            salt_cli.run("virt.stop", virt_domain, minion_tgt=virt_minion_0.id)
            salt_cli.run("virt.undefine", virt_domain, minion_tgt=virt_minion_0.id)
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        for domain in domains:
            salt_cli.run("virt.stop", virt_domain, minion_tgt=virt_minion_1.id)
            salt_cli.run("virt.undefine", virt_domain, minion_tgt=virt_minion_1.id)


@pytest.mark.slow_test
@pytest.mark.skip_if_binaries_missing("docker")
class TestVirtMigrateTest:
    def test_define_xml_path(self, salt_cli, virt_minion_0, virt_domain, grains):
        """
        Define a new domain with virt.define_xml_path,
        verify that the new domain is shown with virt.list_domains,
        remove the domain with virt.undefine, and verifies that
        domain is no longer shown with virt.list_domains.
        """
        if grains.get("osarch", "") != "x86_64":
            raise pytest.skip.Exception(
                f"Test is only meant to run on 'x86_64' architecture, not '{grains['osarch']}'",
                _use_item_location=True,
            )
        ret = salt_cli.run(
            "virt.define_xml_path",
            f"/{virt_domain}.xml",
            minion_tgt=virt_minion_0.id,
        )
        assert ret.returncode == 0, ret
        result = ret.data
        assert isinstance(result, bool), result
        assert result is True, result

        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [virt_domain]

        ret = salt_cli.run("virt.undefine", virt_domain, minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        result = ret.data
        assert isinstance(result, bool)
        assert result is True

        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == []

    def test_ssh_migration(
        self, salt_cli, virt_minion_0, virt_minion_1, prep_virt, virt_domain
    ):
        """
        Test domain migration over SSH, TCP and TLS transport protocol
        """
        ret = salt_cli.run("virt.list_active_vms", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret

        ret = salt_cli.run("virt.list_active_vms", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        ret = salt_cli.run("virt.vm_info", virt_domain, minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret

        # Verify that the VM has been created
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [virt_domain]

        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == []

        ret = salt_cli.run(
            "virt.migrate",
            virt_domain,
            f"qemu+ssh://{virt_minion_1.uri}/system",
            minion_tgt=virt_minion_0.id,
        )
        assert ret.returncode == 0, ret
        result = ret.data
        assert isinstance(result, bool)
        assert result is True

        # Verify that the VM has been migrated
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [], "Failed to migrate VM"

        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [virt_domain], "Failed to migrate VM"

    def test_tcp_migration(
        self, salt_cli, virt_minion_0, virt_minion_1, prep_virt, virt_domain
    ):
        """
        Test domain migration over SSH, TCP and TLS transport protocol
        """
        # Verify that the VM has been created
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [virt_domain]

        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == []

        ret = salt_cli.run(
            "virt.migrate",
            virt_domain,
            virt_minion_1.tcp_uri,
            minion_tgt=virt_minion_0.id,
        )
        assert ret.returncode == 0, ret
        result = ret.data
        assert isinstance(result, bool)
        assert result is True

        # Verify that the VM has been migrated
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [], "Failed to migrate VM"

        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [virt_domain], "Failed to migrate VM"

    def test_tls_migration(
        self, salt_cli, virt_minion_0, virt_minion_1, prep_virt, virt_domain
    ):
        """
        Test domain migration over SSH, TCP and TLS transport protocol
        """
        # Verify that the VM has been created
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [virt_domain]

        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == []

        ret = salt_cli.run(
            "virt.migrate",
            virt_domain,
            virt_minion_1.tls_uri,
            minion_tgt=virt_minion_0.id,
        )
        assert ret.returncode == 0, ret
        result = ret.data
        assert isinstance(result, bool)
        assert result is True

        # Verify that the VM has been migrated
        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_0.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [], "Failed to migrate VM"

        ret = salt_cli.run("virt.list_domains", minion_tgt=virt_minion_1.id)
        assert ret.returncode == 0, ret
        domains = ret.data
        assert isinstance(domains, list)
        assert domains == [virt_domain], "Failed to migrate VM"
