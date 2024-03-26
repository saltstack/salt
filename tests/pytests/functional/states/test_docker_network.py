import functools
import logging
import random

import pytest
from saltfactories.utils import random_string

import salt.utils.files
import salt.utils.network
import salt.utils.path
from salt._compat import ipaddress
from salt.exceptions import CommandExecutionError

pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


IPV6_ENABLED = bool(salt.utils.network.ip_addrs6(include_loopback=True))


class Network:
    def __init__(self, name, **kwargs):
        self.kwargs = kwargs
        self.name = name
        try:
            self.net = ipaddress.ip_network(self.kwargs["subnet"])
            self._rand_indexes = random.sample(
                range(2, self.net.num_addresses - 1), self.net.num_addresses - 3
            )
            self.ip_arg = f"ipv{self.net.version}_address"
        except KeyError:
            # No explicit subnet passed
            self.net = self.ip_arg = None

    def __getitem__(self, index):
        try:
            return self.net[self._rand_indexes[index]].compressed
        except (TypeError, AttributeError):
            raise ValueError(
                "Indexing not supported for networks without a custom subnet"
            )

    @staticmethod
    def arg_map(arg_name):
        if arg_name == "ipv4_address":
            return "IPv4Address"
        if arg_name == "ipv6_address":
            return "IPv6Address"
        if arg_name == "links":
            return "Links"
        if arg_name == "aliases":
            return "Aliases"

    @property
    def subnet(self):
        try:
            return self.net.compressed
        except AttributeError:
            return None

    @property
    def gateway(self):
        try:
            return self.kwargs["gateway"]
        except KeyError:
            try:
                return self.net[1].compressed
            except (AttributeError, IndexError):
                return None


class CreateNetwork:
    """
    Generate a network for the test. Information about the network will be
    passed to the wrapped function.
    """

    def __init__(self, docker_module, **kwargs):
        self.docker_module = docker_module
        self.network = Network(random_string("salt_net_"), **kwargs)
        if self.network.net is not None:
            if "enable_ipv6" not in kwargs:
                kwargs["enable_ipv6"] = self.network.net.version == 6
        self.kwargs = kwargs

    def __enter__(self):
        return self.network

    def __exit__(self, *_):
        try:
            self.docker_module.disconnect_all_containers_from_network(self.network.name)
        except CommandExecutionError as exc:
            if "404" not in str(exc):
                raise exc from None
        else:
            self.docker_module.remove_network(self.network.name)
        self.network = None


@pytest.fixture(scope="module")
def container(salt_factories, state_tree):

    factory = salt_factories.get_container(
        random_string("docker-network-"),
        image_name="ghcr.io/saltstack/salt-ci-containers/busybox:musl",
        container_run_kwargs={
            "entrypoint": "tail -f /dev/null",
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )

    with factory.started():
        yield factory


@pytest.fixture
def docker(modules):
    return modules.docker


@pytest.fixture
def docker_network(states):
    return states.docker_network


@pytest.fixture
def network(docker):
    return functools.partial(CreateNetwork, docker)


@pytest.fixture
def existing_network(network, docker_network):
    with network() as net:
        ret = docker_network.present(name=net.name)
        assert ret.result is True
        assert ret.changes
        assert ret.changes == {"created": True}
        try:
            yield net
        finally:
            docker_network.absent(name=net.name)


@pytest.fixture
def existing_network_with_container(network, docker_network, container):
    with network() as net:
        ret = docker_network.present(name=net.name, containers=[container.name])
        assert ret.result is True
        assert ret.changes
        assert ret.changes == {"created": True, "connected": [container.name]}
        try:
            yield net
        finally:
            docker_network.absent(name=net.name)


def test_absent(docker_network, existing_network):
    ret = docker_network.absent(name=existing_network.name)
    assert ret.result is True
    assert ret.changes
    assert ret.changes == {"removed": True}
    assert ret.comment
    assert ret.comment == f"Removed network '{existing_network.name}'"


def test_absent_with_disconnected_container(
    docker_network, container, existing_network_with_container
):
    ret = docker_network.absent(name=existing_network_with_container.name)
    assert ret.result is True
    assert ret.changes
    assert ret.changes == {"removed": True, "disconnected": [container.name]}
    assert ret.comment == "Removed network '{}'".format(
        existing_network_with_container.name
    )


def test_absent_when_not_present(network, docker_network):
    with network() as net:
        ret = docker_network.absent(name=net.name)
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == f"Network '{net.name}' already absent"


def test_present(docker, network, docker_network):
    with network() as net:
        ret = docker_network.present(name=net.name)
        assert ret.result is True
        assert ret.changes
        assert ret.changes == {"created": True}
        assert ret.comment == f"Network '{net.name}' created"

        # Now check to see that the network actually exists. If it doesn't,
        # this next function call will raise an exception.
        docker.inspect_network(net.name)


def test_present_with_containers(network, docker, docker_network, container):
    with network() as net:
        ret = docker_network.present(name=net.name, containers=[container.name])
        assert ret.result is True
        assert ret.changes
        assert ret.changes == {"created": True, "connected": [container.name]}
        assert ret.comment == f"Network '{net.name}' created"

        # Now check to see that the network actually exists. If it doesn't,
        # this next function call will raise an exception.
        docker.inspect_network(net.name)


@pytest.mark.parametrize("reconnect", [True, False])
def test_present_with_reconnect(network, docker, docker_network, container, reconnect):
    """
    Test reconnecting with containers not passed to state
    """
    with network() as net:
        ret = docker_network.present(name=net.name, driver="bridge")
        assert ret.result is True
        assert ret.changes
        assert ret.changes == {"created": True}
        assert ret.comment == f"Network '{net.name}' created"

        # Connect the container
        docker.connect_container_to_network(container.name, net.name)

        # Change the driver to force the network to be replaced
        ret = docker_network.present(
            name=net.name, driver="macvlan", reconnect=reconnect
        )
        assert ret.result is True
        assert ret.changes
        assert ret.changes == {
            "recreated": True,
            "reconnected" if reconnect else "disconnected": [container.name],
            net.name: {
                "Driver": {
                    "old": "bridge",
                    "new": "macvlan",
                },
            },
        }
        assert ret.comment == "Network '{}' was replaced with updated config".format(
            net.name
        )


def test_present_internal(network, docker, docker_network):
    with network() as net:
        ret = docker_network.present(name=net.name, internal=True)
        assert ret.result is True
        net_info = docker.inspect_network(net.name)
        assert net_info["Internal"] is True


def test_present_labels(network, docker, docker_network):
    # Test a mix of different ways of specifying labels
    with network() as net:
        ret = docker_network.present(
            name=net.name,
            labels=["foo", "bar=baz", {"hello": "world"}],
        )
        assert ret.result is True
        net_info = docker.inspect_network(net.name)
        assert net_info["Labels"] == {"foo": "", "bar": "baz", "hello": "world"}


@pytest.mark.skipif(IPV6_ENABLED is False, reason="IPv6 not enabled")
def test_present_enable_ipv6(network, docker, docker_network):
    with network(subnet="10.247.197.96/27") as net1:
        with network(subnet="fe3f:2180:26:1::/123") as net2:
            ret = docker_network.present(
                name=net1.name,
                enable_ipv6=True,
                ipam_pools=[
                    {"subnet": net1.subnet},
                    {"subnet": net2.subnet},
                ],
            )
            assert ret.result is True
            net_info = docker.inspect_network(net1.name)
            assert net_info["EnableIPv6"] is True


def test_present_attachable(network, docker, docker_network, grains):
    if grains["os_family"] == "RedHat" and grains.get("osmajorrelease", 0) <= 7:
        pytest.skip("Cannot reliably manage attachable on RHEL <= 7")

    with network() as net:
        ret = docker_network.present(name=net.name, attachable=True)
        assert ret.result is True

        net_info = docker.inspect_network(net.name)
        assert net_info["Attachable"] is True


@pytest.mark.skipif(True, reason="Skip until we can set up docker swarm testing")
def test_present_scope(network, docker, docker_network):
    with network() as net:
        ret = docker_network.present(name=net.name, scope="global")
        assert ret.result is True

        net_info = docker.inspect_network(net.name)
        assert net_info["Scope"] == "global"


@pytest.mark.skipif(True, reason="Skip until we can set up docker swarm testing")
def test_present_ingress(network, docker, docker_network):
    with network() as net:
        ret = docker_network.present(name=net.name, ingress=True)
        assert ret.result is True

        net_info = docker.inspect_network(net.name)
        assert net_info["Ingress"] is True


def test_present_with_custom_ipv4(network, docker, docker_network):
    # First run will test passing the IPAM arguments individually
    with network(subnet="10.247.197.96/27") as net1, network(
        subnet="10.247.197.128/27"
    ) as net2:
        ret = docker_network.present(
            name=net1.name,
            subnet=net1.subnet,
            gateway=net1.gateway,
        )
        assert ret.result is True

        # Second run will pass them in the ipam_pools argument
        ret = docker_network.present(
            name=net1.name,  # We want to keep the same network name
            ipam_pools=[{"subnet": net2.subnet, "gateway": net2.gateway}],
        )
        assert ret.result is True

        # Docker requires there to be IPv4, even when only an IPv6 subnet was
        # provided. So, there will be both an IPv4 and IPv6 pool in the
        # configuration.
        expected = {
            "recreated": True,
            net1.name: {
                "IPAM": {
                    "Config": {
                        "old": [{"Subnet": net1.subnet, "Gateway": net1.gateway}],
                        "new": [{"Subnet": net2.subnet, "Gateway": net2.gateway}],
                    }
                }
            },
        }
        assert ret.changes
        assert ret.changes == expected
        assert ret.comment == "Network '{}' was replaced with updated config".format(
            net1.name
        )


@pytest.mark.skipif(IPV6_ENABLED is False, reason="IPv6 not enabled")
def test_present_with_custom_ipv6(network, docker, docker_network):
    with network(subnet="10.247.197.96/27") as ipv4_net, network(
        subnet="fe3f:2180:26:1::/123"
    ) as ipv6_net1, network(subnet="fe3f:2180:26:1::20/123") as ipv6_net2:
        ret = docker_network.present(
            name=ipv4_net.name,
            enable_ipv6=True,
            ipam_pools=[
                {"subnet": ipv4_net.subnet, "gateway": ipv4_net.gateway},
                {"subnet": ipv6_net1.subnet, "gateway": ipv6_net1.gateway},
            ],
        )
        assert ret.result is True

        ret = docker_network.present(
            name=ipv4_net.name,  # We want to keep the same network name
            enable_ipv6=True,
            ipam_pools=[
                {"subnet": ipv4_net.subnet, "gateway": ipv4_net.gateway},
                {"subnet": ipv6_net2.subnet, "gateway": ipv6_net2.gateway},
            ],
        )
        assert ret.result is True

        # Docker requires there to be IPv4, even when only an IPv6 subnet was
        # provided. So, there will be both an IPv4 and IPv6 pool in the
        # configuration.
        expected = {
            "recreated": True,
            ipv4_net.name: {
                "IPAM": {
                    "Config": {
                        "old": [
                            {"Subnet": ipv4_net.subnet, "Gateway": ipv4_net.gateway},
                            {"Subnet": ipv6_net1.subnet, "Gateway": ipv6_net1.gateway},
                        ],
                        "new": [
                            {"Subnet": ipv4_net.subnet, "Gateway": ipv4_net.gateway},
                            {"Subnet": ipv6_net2.subnet, "Gateway": ipv6_net2.gateway},
                        ],
                    }
                }
            },
        }
        assert ret.changes
        assert ret.changes == expected
        assert ret.comment == "Network '{}' was replaced with updated config".format(
            ipv4_net.name
        )


def test_bridge_dupname_update(network, docker, docker_network):
    # com.docker.network.bridge.name can not have names over 15 chars. so grab the last 8
    with network(subnet="10.247.197.96/27") as net:
        ret = docker_network.present(
            name=net.name,
            subnet=net.subnet,
            driver="bridge",
            driver_opts=[{"com.docker.network.bridge.name": net.name[-8:]}],
        )
        assert ret.result is True
        # Second run to make sure everything is still fine.
        ret = docker_network.present(
            name=net.name,
            subnet=net.subnet,
            driver="bridge",
            driver_opts=[{"com.docker.network.bridge.name": net.name[-8:]}],
        )
        assert ret.result is True
        assert not ret.changes
        assert (
            ret.comment
            == "Network '{}' already exists, and is configured as specified".format(
                net.name
            )
        )
