"""
Integration tests for the docker_container states
"""

import logging
import os
import random
import shutil
import subprocess

import attr
import pytest
from saltfactories.utils import random_string

import salt.utils.files
import salt.utils.network
import salt.utils.path
from salt._compat import ipaddress
from salt.exceptions import CommandExecutionError
from salt.modules.config import DEFAULTS as _config_defaults
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_freebsd(reason="No Docker on FreeBSD available"),
    pytest.mark.skip_if_binaries_missing("busybox", reason="Busybox not installed"),
    pytest.mark.skip_if_binaries_missing(
        "docker", "dockerd", reason="Docker not installed"
    ),
    pytest.mark.timeout_unless_on_windows(240),
]

IPV6_ENABLED = bool(salt.utils.network.ip_addrs6(include_loopback=True))


@attr.s(slots=True)
class Network:

    docker_exec_mod = attr.ib(repr=False)
    subnet = attr.ib()
    name = attr.ib()
    net = attr.ib(init=False)
    gateway = attr.ib()
    enable_ipv6 = attr.ib()
    ip_arg = attr.ib(init=False)
    _rand_indexes = attr.ib(init=False)

    @name.default
    def _name(self):
        return random_string("salt-network-", uppercase=False)

    @net.default
    def _net(self):
        return ipaddress.ip_network(self.subnet)

    @_rand_indexes.default
    def __rand_indexes(self):
        return random.sample(
            range(2, self.net.num_addresses - 1), self.net.num_addresses - 3
        )

    @ip_arg.default
    def _ip_arg(self):
        return f"ipv{self.net.version}_address"

    @enable_ipv6.default
    def _enable_ipv6(self):
        return self.net.version == 6

    @staticmethod
    def arg_map(arg_name):
        nwmap = {
            "ipv4_address": "IPv4Address",
            "ipv6_address": "IPv6Address",
            "links": "Links",
            "aliases": "Aliases",
        }
        return nwmap[arg_name]

    @property
    def compressed_subnet(self):
        if self.net:
            return self.net.compressed

    @gateway.default
    def _gateway(self):
        return self.net[1].compressed

    def __getitem__(self, index):
        try:
            return self.net[self._rand_indexes[index]].compressed
        except (TypeError, AttributeError):
            raise ValueError(
                "Indexing not supported for networks without a custom subnet"
            )

    def __enter__(self):
        self.docker_exec_mod.create_network(
            self.name,
            subnet=self.compressed_subnet,
            gateway=self.gateway,
            enable_ipv6=self.enable_ipv6,
        )
        return self

    def __exit__(self, *_):
        try:
            self.docker_exec_mod.disconnect_all_containers_from_network(self.name)
        except CommandExecutionError as exc:
            if "404" not in str(exc):
                raise
        self.docker_exec_mod.remove_network(self.name)


@attr.s(slots=True)
class Networks:
    docker_exec_mod = attr.ib(repr=False)
    nets = attr.ib(default=attr.Factory(list))

    def add(self, subnet):
        network = Network(docker_exec_mod=self.docker_exec_mod, subnet=subnet)
        self.nets.append(network)
        return network

    def __enter__(self):
        for net in self.nets:
            net.__enter__()
        return self

    def __exit__(self, *_):
        for net in self.nets:
            net.__exit__()


@pytest.fixture
def network(modules):
    def _network(**kwargs):
        return Network(docker_exec_mod=modules.docker, **kwargs)

    return _network


@pytest.fixture
def networks(modules):
    return Networks(docker_exec_mod=modules.docker)


@pytest.fixture
def container_name(modules):
    """
    Generate a randomized name for a container and clean it up afterward
    """
    _container_name = random_string("salt-docker-container-test-", uppercase=False)
    try:
        yield _container_name
    finally:
        try:
            modules.docker.rm(_container_name, force=True)
        except CommandExecutionError as exc:
            if "No such container" not in str(exc):
                raise


@pytest.fixture
def docker_container(states):
    return states.docker_container


@pytest.fixture(scope="module")
def image(tmp_path_factory):
    if not salt.utils.path.which("docker"):
        # Somehow the above skip_if_binaries_missing marker for docker
        # only get's evaluated after this fixture?!?
        pytest.skip("The `docker` binary is not available")
    container_build_dir = tmp_path_factory.mktemp("busybox")
    image_name = random_string("salt-busybox-", uppercase=False)

    script_path = os.path.join(RUNTIME_VARS.BASE_FILES, "mkimage-busybox-static")
    cmd = [script_path, str(container_build_dir), image_name]
    log.debug("Running '%s' to build busybox image", " ".join(cmd))
    process = subprocess.run(
        cmd,
        close_fds=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    log.debug("Output from mkimge-busybox-static:\n%s", process.stdout)
    if process.returncode != 0:
        raise Exception(
            "Failed to build image. Output from mkimge-busybox-static:\n{}".format(
                process.stdout
            )
        )

    shutil.rmtree(str(container_build_dir))

    try:
        yield image_name
    finally:
        cmd = ["docker", "rmi", "--force", image_name]
        log.debug("Running '%s' to destroy busybox image", " ".join(cmd))
        process = subprocess.run(
            cmd,
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log.debug("Output from %s:\n%s", " ".join(cmd), process.stdout)

        if process.returncode != 0:
            raise Exception("Failed to destroy image")


@pytest.mark.slow_test
def test_running_with_no_predefined_volume(
    docker_container, container_name, image, tmp_path, modules
):
    """
    This tests that a container created using the docker_container.running
    state, with binds defined, will also create the corresponding volumes
    if they aren't pre-defined in the image.
    """
    ret = docker_container.running(
        name=container_name,
        image=image,
        binds=f"{tmp_path}:/foo",
        shutdown_timeout=1,
    )
    assert ret.result is True
    # Now check to ensure that the container has volumes to match the
    # binds that we used when creating it.
    ret = modules.docker.inspect_container(container_name)
    assert "/foo" in ret["Config"]["Volumes"]


@pytest.mark.slow_test
def test_running_with_no_predefined_ports(
    docker_container, container_name, image, modules, subtests
):
    """
    This tests that a container created using the docker_container.running
    state, with port_bindings defined, will also configure the
    corresponding ports if they aren't pre-defined in the image.
    """
    ret = docker_container.running(
        name=container_name,
        image=image,
        port_bindings="14505-14506:24505-24506,2123:2123/udp,8080",
        shutdown_timeout=1,
    )
    assert ret.result is True
    # Now check to ensure that the container has ports to match the
    # port_bindings that we used when creating it.
    expected_ports = ("8080/tcp", "2123/udp")
    ret = modules.docker.inspect_container(container_name)
    for x in expected_ports:
        with subtests.test(port=x):
            assert x in ret["NetworkSettings"]["Ports"]


@pytest.mark.slow_test
def test_running_updated_image_id(docker_container, container_name, image, modules):
    """
    This tests the case of an image being changed after the container is
    created. The next time the state is run, the container should be
    replaced because the image ID is now different.
    """
    # Create and start a container
    ret = docker_container.running(name=container_name, image=image, shutdown_timeout=1)
    assert ret.result is True
    # Get the container's info
    c_info = modules.docker.inspect_container(container_name)
    c_name, c_id = (c_info[x] for x in ("Name", "Id"))
    # Alter the filesystem inside the container
    assert modules.docker.retcode(container_name, "touch /.salttest") == 0
    # Commit the changes and overwrite the test class' image
    modules.docker.commit(c_id, image)
    # Re-run the state
    ret = docker_container.running(name=container_name, image=image, shutdown_timeout=1)
    assert ret.result is True
    # Check to make sure that the container was replaced
    assert "container_id" in ret.changes
    # Check to make sure that the image is in the changes dict, since
    # it should have changed
    assert "image" in ret.changes
    # Check that the comment in the state return states that
    # container's image has changed
    assert "Container has a new image" in ret.comment


@pytest.mark.slow_test
def test_running_start_false_without_replace(
    docker_container, container_name, image, modules
):
    """
    Test that we do not start a container which is stopped, when it is not
    being replaced.
    """
    # Create a container
    ret = docker_container.running(name=container_name, image=image, shutdown_timeout=1)
    assert ret.result is True
    # Stop the container
    modules.docker.stop(container_name, force=True)
    # Re-run the state with start=False
    ret = docker_container.running(
        name=container_name,
        image=image,
        start=False,
        shutdown_timeout=1,
    )
    assert ret.result is True
    # Check to make sure that the container was not replaced
    assert "container_id" not in ret.changes
    # Check to make sure that the state is not the changes dict, since
    # it should not have changed
    assert "state" not in ret.changes


@pytest.mark.slow_test
def test_running_no_changes_hostname_network(
    docker_container, container_name, image, network
):
    """
    Test that changes are not detected when a hostname is specified for a container
    on a custom network
    """
    with network(subnet="10.247.197.96/27") as net:
        # Create a container
        kwargs = {
            "name": container_name,
            "image": image,
            "shutdown_timeout": 1,
            "network_mode": net.name,
            "networks": [net.name],
            "hostname": "foo",
        }
        ret = docker_container.running(**kwargs)
        assert ret.result is True

        ret = docker_container.running(**kwargs)
        assert ret.result is True
        # Should be no changes
        assert not ret.changes


@pytest.mark.slow_test
def test_running_start_false_with_replace(
    docker_container, container_name, image, modules
):
    """
    Test that we do start a container which was previously stopped, even
    though start=False, because the container was replaced.
    """
    # Create a container
    ret = docker_container.running(name=container_name, image=image, shutdown_timeout=1)
    assert ret.result is True
    # Stop the container
    modules.docker.stop(container_name, force=True)
    # Re-run the state with start=False but also change the command to
    # trigger the container being replaced.
    ret = docker_container.running(
        name=container_name,
        image=image,
        command="sleep 600",
        start=False,
        shutdown_timeout=1,
    )
    assert ret.result is True
    # Check to make sure that the container was not replaced
    assert "container_id" in ret.changes
    # Check to make sure that the state is not the changes dict, since
    # it should not have changed
    assert "state" not in ret.changes


@pytest.mark.slow_test
def test_running_start_true(docker_container, container_name, image, modules):
    """
    This tests that we *do* start a container that is stopped, when the
    "start" argument is set to True.
    """
    # Create a container
    ret = docker_container.running(name=container_name, image=image, shutdown_timeout=1)
    assert ret.result is True
    # Stop the container
    modules.docker.stop(container_name, force=True)
    # Re-run the state with start=True
    ret = docker_container.running(
        name=container_name,
        image=image,
        start=True,
        shutdown_timeout=1,
    )
    assert ret.result is True
    # Check to make sure that the container was not replaced
    assert "container_id" not in ret.changes
    # Check to make sure that the state is in the changes dict, since
    # it should have changed
    assert "state" in ret.changes
    # Check that the comment in the state return states that
    # container's state has changed
    assert "State changed from 'stopped' to 'running'" in ret.comment


def test_running_with_invalid_input(docker_container, container_name, image):
    """
    This tests that the input tranlation code identifies invalid input and
    includes information about that invalid argument in the state return.
    """
    # Try to create a container with invalid input
    ret = docker_container.running(
        name=container_name,
        image=image,
        ulimits="nofile:2048",
        shutdown_timeout=1,
    )
    assert ret.result is False
    # Check to make sure that the container was not created
    assert "container_id" not in ret.changes
    # Check that the error message about the invalid argument is
    # included in the comment for the state
    assert (
        "Ulimit definition 'nofile:2048' is not in the format"
        " type=soft_limit[:hard_limit]" in ret.comment
    )


def test_running_with_argument_collision(docker_container, container_name, image):
    """
    this tests that the input tranlation code identifies an argument
    collision (API args and their aliases being simultaneously used) and
    includes information about them in the state return.
    """
    # try to create a container with invalid input
    ret = docker_container.running(
        name=container_name,
        image=image,
        ulimits="nofile=2048",
        ulimit="nofile=1024:2048",
        shutdown_timeout=1,
    )
    assert ret.result is False
    # Check to make sure that the container was not created
    assert "container_id" not in ret.changes
    # Check that the error message about the collision is included in
    # the comment for the state
    assert "'ulimit' is an alias for 'ulimits'" in ret.comment


@pytest.mark.slow_test
def test_running_with_ignore_collisions(
    docker_container, container_name, image, modules
):
    """
    This tests that the input tranlation code identifies an argument
    collision (API args and their aliases being simultaneously used)
    includes information about them in the state return.
    """
    # try to create a container with invalid input
    ret = docker_container.running(
        name=container_name,
        image=image,
        ignore_collisions=True,
        ulimits="nofile=2048",
        ulimit="nofile=1024:2048",
        shutdown_timeout=1,
    )
    assert ret.result is True
    # Check to make sure that the container was created
    assert "container_id" in ret.changes
    # Check that the value from the API argument was one that was used
    # to create the container
    c_info = modules.docker.inspect_container(container_name)
    actual = c_info["HostConfig"]["Ulimits"]
    expected = [{"Name": "nofile", "Soft": 2048, "Hard": 2048}]
    assert actual == expected


@pytest.mark.slow_test
def test_running_with_removed_argument(
    docker_container, container_name, image, modules
):
    """
    This tests that removing an argument from a created container will
    be detected and result in the container being replaced.

    It also tests that we revert back to the value from the image. This
    way, when the "command" argument is removed, we confirm that we are
    reverting back to the image's command.
    """
    # Create the container
    ret = docker_container.running(
        name=container_name,
        image=image,
        command="sleep 600",
        shutdown_timeout=1,
    )
    assert ret.result is True
    # Run the state again with the "command" argument removed
    ret = docker_container.running(name=container_name, image=image, shutdown_timeout=1)
    assert ret.result is True
    # Now check to ensure that the changes include the command
    # reverting back to the image's command.
    image_info = modules.docker.inspect_image(image)
    assert (
        ret.changes["container"]["Config"]["Cmd"]["new"] == image_info["Config"]["Cmd"]
    )


@pytest.mark.slow_test
def test_running_with_port_bindings(docker_container, container_name, image, modules):
    """
    This tests that the ports which are being bound are also exposed, even
    when not explicitly configured. This test will create a container with
    only some of the ports exposed, including some which aren't even bound.
    The resulting containers exposed ports should contain all of the ports
    defined in the "ports" argument, as well as each of the ports which are
    being bound.
    """
    # Create the container
    ret = docker_container.running(
        name=container_name,
        image=image,
        command="sleep 600",
        shutdown_timeout=1,
        port_bindings=[1234, "1235-1236", "2234/udp", "2235-2236/udp"],
        ports=[1235, "2235/udp", 9999],
    )
    assert ret.result is True

    # Check the created container's port bindings and exposed ports. The
    # port bindings should only contain the ports defined in the
    # port_bindings argument, while the exposed ports should also contain
    # the extra port (9999/tcp) which was included in the ports argument.
    cinfo = modules.docker.inspect_container(container_name)
    ports = ["1234/tcp", "1235/tcp", "1236/tcp", "2234/udp", "2235/udp", "2236/udp"]
    assert sorted(cinfo["HostConfig"]["PortBindings"]) == ports
    assert sorted(cinfo["Config"]["ExposedPorts"]) == ports + ["9999/tcp"]


@pytest.mark.slow_test
def test_absent_with_stopped_container(
    docker_container, container_name, image, modules
):
    """
    This tests the docker_container.absent state on a stopped container
    """
    # Create the container
    modules.docker.create(image, name=container_name)
    # Remove the container
    ret = docker_container.absent(
        name=container_name,
    )
    assert ret.result is True
    # Check that we have a removed container ID in the changes dict
    assert "removed" in ret.changes

    # Run the state again to confirm it changes nothing
    ret = docker_container.absent(
        name=container_name,
    )
    assert ret.result is True
    # Nothing should have changed
    assert ret.changes == {}
    # Ensure that the comment field says the container does not exist
    assert ret.comment == f"Container '{container_name}' does not exist"


@pytest.mark.slow_test
def test_absent_with_running_container(docker_container, container_name, image):
    """
    This tests the docker_container.absent state and
    """
    # Create the container
    ret = docker_container.running(
        name=container_name,
        image=image,
        command="sleep 600",
        shutdown_timeout=1,
    )
    assert ret.result is True

    # Try to remove the container. This should fail because force=True
    # is needed to remove a container that is running.
    ret = docker_container.absent(
        name=container_name,
    )
    assert ret.result is False
    # Nothing should have changed
    assert ret.changes == {}
    # Ensure that the comment states that force=True is required
    assert (
        ret.comment == "Container is running, set force to True to forcibly remove it"
    )

    # Try again with force=True. This should succeed.
    ret = docker_container.absent(
        name=container_name,
        force=True,
    )
    assert ret.result is True
    # Check that we have a removed container ID in the changes dict
    assert "removed" in ret.changes
    # The comment should mention that the container was removed
    assert ret.comment == f"Forcibly removed container '{container_name}'"


@pytest.mark.slow_test
def test_running_image_name(docker_container, container_name, image, modules):
    """
    Ensure that we create the container using the image name instead of ID
    """
    ret = docker_container.running(name=container_name, image=image, shutdown_timeout=1)
    assert ret.result is True
    ret = modules.docker.inspect_container(container_name)
    assert ret["Config"]["Image"] == image


@pytest.mark.slow_test
def test_env_with_running_container(docker_container, container_name, image, modules):
    """
    docker_container.running environnment part. Testing issue 39838.
    """
    ret = docker_container.running(
        name=container_name,
        image=image,
        env="VAR1=value1,VAR2=value2,VAR3=value3",
        shutdown_timeout=1,
    )
    assert ret.result is True
    ret = modules.docker.inspect_container(container_name)
    assert "VAR1=value1" in ret["Config"]["Env"]
    assert "VAR2=value2" in ret["Config"]["Env"]
    assert "VAR3=value3" in ret["Config"]["Env"]
    ret = docker_container.running(
        name=container_name,
        image=image,
        env="VAR1=value1,VAR2=value2",
        shutdown_timeout=1,
    )
    assert ret.result is True
    ret = modules.docker.inspect_container(container_name)
    assert "VAR1=value1" in ret["Config"]["Env"]
    assert "VAR2=value2" in ret["Config"]["Env"]
    assert "VAR3=value3" not in ret["Config"]["Env"]


@pytest.mark.slow_test
def test_static_ip_one_network(
    docker_container, container_name, image, modules, network
):
    """
    Ensure that if a network is created and specified as network_mode, that is the only network, and
    the static IP is applied.
    """
    with network(subnet="10.247.197.96/27") as net:
        requested_ip = "10.247.197.100"
        kwargs = {
            "name": container_name,
            "image": image,
            "network_mode": net.name,
            "networks": [{net.name: [{"ipv4_address": requested_ip}]}],
            "shutdown_timeout": 1,
        }
        # Create a container
        ret = docker_container.running(**kwargs)
        assert ret.result is True

        inspect_result = modules.docker.inspect_container(container_name)
        connected_networks = inspect_result["NetworkSettings"]["Networks"]

        assert list(connected_networks.keys()) == [net.name]
        assert inspect_result["HostConfig"]["NetworkMode"] == net.name
        assert connected_networks[net.name]["IPAMConfig"]["IPv4Address"] == requested_ip


def _test_running(docker_container, container_name, image, modules, *nets):
    """
    DRY function for testing static IPs
    """


@pytest.mark.slow_test
@pytest.mark.parametrize(
    "subnets",
    [
        (dict(subnet="10.247.197.96/27"),),
        (dict(subnet="10.247.197.128/27"), dict(subnet="10.247.197.96/27")),
        (dict(subnet="fe3f:2180:26:1::/123"),),
        (dict(subnet="fe3f:2180:26:1::20/123"), dict(subnet="fe3f:2180:26:1::/123")),
        (dict(subnet="fe3f:2180:26:1::/123"), dict(subnet="10.247.197.96/27")),
    ],
)
def test_running_networks(
    docker_container, container_name, image, subnets, networks, modules
):

    netdefs = []
    for subnet in subnets:
        network = networks.add(**subnet)
        if network.enable_ipv6 and IPV6_ENABLED is False:
            pytest.skip("IPv6 not enabled")

        netdefs.append({network.name: [{network.ip_arg: network[0]}]})

    with networks:

        kwargs = {
            "name": container_name,
            "image": image,
            "networks": netdefs,
            "shutdown_timeout": 1,
        }
        # Create a container
        ret = docker_container.running(**kwargs)
        assert ret.result is True

        inspect_result = modules.docker.inspect_container(container_name)
        connected_networks = inspect_result["NetworkSettings"]["Networks"]

        # Check that the correct IP was set
        try:
            for net in networks.nets:
                assert (
                    connected_networks[net.name]["IPAMConfig"][net.arg_map(net.ip_arg)]
                    == net[0]
                )
        except KeyError:
            # Fail with a meaningful error
            msg = "Container does not have the expected network config for network {}".format(
                net.name
            )
            log.error(msg)
            log.error("Connected networks: %s", connected_networks)
            pytest.fail(f"{msg}. See log for more information.")

        # Check that container continued running and didn't immediately exit
        assert inspect_result["State"]["Running"]

        # Update the SLS configuration to use the second random IP so that we
        # can test updating a container's network configuration without
        # replacing the container.
        for idx, net in enumerate(networks.nets):
            kwargs["networks"][idx][net.name][0][net.ip_arg] = net[1]
        ret = docker_container.running(**kwargs)
        assert ret.result is True

        expected = {"container": {"Networks": {}}}
        for net in networks.nets:
            expected["container"]["Networks"][net.name] = {
                "IPAMConfig": {
                    "old": {net.arg_map(net.ip_arg): net[0]},
                    "new": {net.arg_map(net.ip_arg): net[1]},
                }
            }
        assert ret.changes == expected

        expected = [f"Container '{container_name}' is already configured as specified."]
        expected.extend(
            [
                f"Reconnected to network '{x.name}' with updated configuration."
                for x in sorted(networks.nets, key=lambda y: y.name)
            ]
        )
        expected = " ".join(expected)
        assert ret.comment == expected

        # Update the SLS configuration to remove the last network
        kwargs["networks"].pop(-1)
        ret = docker_container.running(**kwargs)
        assert ret.result is True

        expected = {
            "container": {
                "Networks": {
                    networks.nets[-1].name: {
                        "IPAMConfig": {
                            "old": {
                                networks.nets[-1].arg_map(
                                    networks.nets[-1].ip_arg
                                ): networks.nets[-1][1]
                            },
                            "new": None,
                        }
                    }
                }
            }
        }
        assert ret.changes == expected

        expected = (
            "Container '{}' is already configured as specified. Disconnected "
            "from network '{}'.".format(container_name, networks.nets[-1].name)
        )
        assert ret.comment == expected

        # Update the SLS configuration to add back the last network, only use
        # an automatic IP instead of static IP.
        kwargs["networks"].append(networks.nets[-1].name)
        ret = docker_container.running(**kwargs)
        assert ret.result is True

        # Get the automatic IP by inspecting the container, and use it to build
        # the expected changes.
        container_netinfo = (
            modules.docker.inspect_container(container_name)
            .get("NetworkSettings", {})
            .get("Networks", {})[networks.nets[-1].name]
        )
        autoip_keys = _config_defaults["docker.compare_container_networks"]["automatic"]
        autoip_config = {
            x: y for x, y in container_netinfo.items() if x in autoip_keys and y
        }

        expected = {"container": {"Networks": {networks.nets[-1].name: {}}}}
        for key, val in autoip_config.items():
            expected["container"]["Networks"][networks.nets[-1].name][key] = {
                "old": None,
                "new": val,
            }
        assert ret.changes == expected

        expected = (
            "Container '{}' is already configured as specified. Connected "
            "to network '{}'.".format(container_name, networks.nets[-1].name)
        )
        assert ret.comment == expected

        # Update the SLS configuration to remove the last network
        kwargs["networks"].pop(-1)
        ret = docker_container.running(**kwargs)
        assert ret.result is True

        expected = {"container": {"Networks": {networks.nets[-1].name: {}}}}
        for key, val in autoip_config.items():
            expected["container"]["Networks"][networks.nets[-1].name][key] = {
                "old": val,
                "new": None,
            }
        assert ret.changes == expected

        expected = (
            "Container '{}' is already configured as specified. Disconnected "
            "from network '{}'.".format(container_name, networks.nets[-1].name)
        )
        assert ret.comment == expected


def test_running_explicit_networks(
    docker_container, container_name, image, modules, network
):
    """
    Ensure that if we use an explicit network configuration, we remove any
    default networks not specified (e.g. the default "bridge" network).
    """
    with network(subnet="10.247.197.96/27") as net:
        # Create a container with no specific network configuration. The only
        # networks connected will be the default ones.
        ret = docker_container.running(
            name=container_name,
            image=image,
            shutdown_timeout=1,
        )
        assert ret.result is True

        inspect_result = modules.docker.inspect_container(container_name)
        # Get the default network names
        default_networks = list(inspect_result["NetworkSettings"]["Networks"])

        # Re-run the state with an explicit network configuration. All of the
        # default networks should be disconnected.
        ret = docker_container.running(
            name=container_name,
            image=image,
            networks=[net.name],
            shutdown_timeout=1,
        )
        assert ret.result is True
        net_changes = ret.changes["container"]["Networks"]

        assert (
            f"Container '{container_name}' is already configured as specified."
            in ret.comment
        )

        updated_networks = modules.docker.inspect_container(container_name)[
            "NetworkSettings"
        ]["Networks"]

        for default_network in default_networks:
            assert f"Disconnected from network '{default_network}'." in ret.comment
            assert default_network in net_changes
            # We've tested that the state return is correct, but let's be extra
            # paranoid and check the actual connected networks.
            assert default_network not in updated_networks

        assert f"Connected to network '{net.name}'." in ret.comment


def test_run_with_onlyif(docker_container, container_name, image, modules):
    """
    Test docker_container.run with onlyif. The container should not run
    (and the state should return a True result) if the onlyif has a nonzero
    return code, but if the onlyif has a zero return code the container
    should run.
    If all items are True, the state should run
    """
    # Order should not matter
    test_cmds = (
        "/bin/false",  # single false
        ["/bin/true", "/bin/false"],  # false is last
        ["/bin/false", "/bin/true"],  # false is first
    )
    for cmd in test_cmds:
        log.debug("Trying %s", cmd)
        ret = docker_container.run(
            name=container_name,
            image=image,
            command="whoami",
            onlyif=cmd,
        )
        try:
            assert ret.result is True
            assert not ret.changes
            assert ret.comment.startswith("onlyif condition is false")
        except AssertionError:
            modules.docker.rm(container_name, force=True)
            raise

    for cmd in ("/bin/true", ["/bin/true", "ls /"]):
        log.debug("Trying %s", cmd)
        ret = docker_container.run(
            name=container_name,
            image=image,
            command="whoami",
            onlyif=cmd,
        )
        assert ret.result is True
        assert ret.changes["Logs"] == "root\n"
        assert ret.comment == "Container ran and exited with a return code of 0"
        modules.docker.rm(container_name, force=True)


def test_run_with_unless(docker_container, container_name, image, modules):
    """
    Test docker_container.run with unless. The container should not run
    (and the state should return a True result) if the unless has a zero
    return code, but if the unless has a nonzero return code the container
    should run.
    If any item is False, the state should run
    """
    # Test a single item and a list
    for cmd in ("/bin/true", ["/bin/true", "/bin/true"]):
        log.debug("Trying %s", cmd)
        ret = docker_container.run(
            name=container_name,
            image=image,
            command="whoami",
            unless=cmd,
        )
        try:
            assert ret.result is True
            assert not ret.changes
            assert ret.comment == "unless condition is true"
        except AssertionError:
            modules.docker.rm(container_name, force=True)
            raise

    # Order should not matter
    test_cmds = (
        "/bin/false",  # single false
        ["/bin/true", "/bin/false"],  # false is last
        ["/bin/false", "/bin/true"],  # false is first
    )
    for cmd in test_cmds:
        log.debug("Trying %s", cmd)
        ret = docker_container.run(
            name=container_name,
            image=image,
            command="whoami",
            unless=cmd,
        )
        assert ret.result is True
        assert ret.changes["Logs"] == "root\n"
        assert ret.comment == "Container ran and exited with a return code of 0"
        modules.docker.rm(container_name, force=True)


def test_run_with_creates(
    docker_container, container_name, image, tmp_path, subtests, modules
):
    """
    Test docker_container.run with creates. The container should not run
    (and the state should return a True result) if all of the files exist,
    but if if any of the files do not exist the container should run.
    """

    bad_file = str(tmp_path / "file-that-does-not-exist")
    good_file1 = tmp_path / "good1"
    good_file1.touch()
    good_file1 = str(good_file1)
    good_file2 = tmp_path / "good2"
    good_file2.touch()
    good_file2 = str(good_file2)

    with subtests.test(path=good_file1):
        try:
            log.debug("Trying %s", good_file1)
            ret = docker_container.run(
                name=container_name,
                image=image,
                command="whoami",
                creates=good_file1,
            )
            assert ret.result is True
            assert not ret.changes
            assert ret.comment == f"{good_file1} exists"
        finally:
            try:
                modules.docker.rm(container_name, force=True)
            except CommandExecutionError as exc:
                if "No such container" not in str(exc):
                    raise

    path = [good_file1, good_file2]
    with subtests.test(path=path):
        try:
            log.debug("Trying %s", path)
            ret = docker_container.run(
                name=container_name,
                image=image,
                command="whoami",
                creates=path,
            )
            assert ret.result is True
            assert not ret.changes
            assert ret.comment == "All files in creates exist"
        finally:
            try:
                modules.docker.rm(container_name, force=True)
            except CommandExecutionError as exc:
                if "No such container" not in str(exc):
                    raise

    for path in (bad_file, [good_file1, bad_file]):
        with subtests.test(path=path):
            try:
                log.debug("Trying %s", path)
                ret = docker_container.run(
                    name=container_name,
                    image=image,
                    command="whoami",
                    creates=path,
                )
                assert ret.result is True
                assert ret.changes["Logs"] == "root\n"
                assert ret.comment == "Container ran and exited with a return code of 0"
            finally:
                try:
                    modules.docker.rm(container_name, force=True)
                except CommandExecutionError as exc:
                    if "No such container" not in str(exc):
                        raise


def test_run_replace(docker_container, container_name, image):
    """
    Test the replace and force arguments to make sure they work properly
    """
    # Run once to create the container
    ret = docker_container.run(name=container_name, image=image, command="whoami")
    assert ret.result is True
    assert ret.changes["Logs"] == "root\n"
    assert ret.comment == "Container ran and exited with a return code of 0"

    # Run again with replace=False, this should fail
    ret = docker_container.run(
        name=container_name,
        image=image,
        command="whoami",
        replace=False,
    )
    assert ret.result is False
    assert not ret.changes
    assert ret.comment == (
        "Encountered error running container: Container '{}' exists. "
        "Run with replace=True to remove the existing container"
    ).format(container_name)

    # Run again with replace=True, this should proceed and there should be
    # a "Replaces" key in the changes dict to show that a container was
    # replaced.
    ret = docker_container.run(
        name=container_name,
        image=image,
        command="whoami",
        replace=True,
    )
    assert ret.result is True
    assert ret.changes["Logs"] == "root\n"
    assert "Replaces" in ret.changes
    assert ret.comment == "Container ran and exited with a return code of 0"


def test_run_force(docker_container, container_name, image):
    """
    Test the replace and force arguments to make sure they work properly
    """
    # Start up a container that will stay running
    ret = docker_container.running(name=container_name, image=image)
    assert ret.result is True

    # Run again with replace=True, this should fail because the container
    # is still running
    ret = docker_container.run(
        name=container_name,
        image=image,
        command="whoami",
        replace=True,
        force=False,
    )
    assert ret.result is False
    assert not ret.changes
    assert ret.comment == (
        "Encountered error running container: Container '{}' exists and is running. Run"
        " with replace=True and force=True to force removal of the existing container."
    ).format(container_name)

    # Run again with replace=True and force=True, this should proceed and
    # there should be a "Replaces" key in the changes dict to show that a
    # container was replaced.
    ret = docker_container.run(
        name=container_name,
        image=image,
        command="whoami",
        replace=True,
        force=True,
    )
    assert ret.result is True
    assert ret.changes["Logs"] == "root\n"
    assert "Replaces" in ret.changes
    assert ret.comment == "Container ran and exited with a return code of 0"


def test_run_failhard(docker_container, container_name, image, modules):
    """
    Test to make sure that we fail a state when the container exits with
    nonzero status if failhard is set to True, and that we don't when it is
    set to False.

    NOTE: We can't use RUNTIME_VARS.SHELL_FALSE_PATH here because the image
    we build on-the-fly here is based on busybox and does not include
    /usr/bin/false. Therefore, when the host machine running the tests
    has /usr/bin/false, it will not exist in the container and the Docker
    Engine API will cause an exception to be raised.
    """
    ret = docker_container.run(
        name=container_name,
        image=image,
        command="/bin/false",
        failhard=True,
    )
    assert ret.result is False
    assert ret.changes["Logs"] == ""
    assert ret.comment.startswith("Container ran and exited with a return code of")
    modules.docker.rm(container_name, force=True)

    ret = docker_container.run(
        name=container_name,
        image=image,
        command="/bin/false",
        failhard=False,
    )
    assert ret.result is True
    assert ret.changes["Logs"] == ""
    assert ret.comment.startswith("Container ran and exited with a return code of")
    modules.docker.rm(container_name, force=True)


def test_run_bg(docker_container, container_name, image, modules):
    """
    Test to make sure that if the container is run in the background, we do
    not include an ExitCode or Logs key in the return. Then check the logs
    for the container to ensure that it ran as expected.
    """
    ret = docker_container.run(
        name=container_name,
        image=image,
        command='sh -c "sleep 5 && whoami"',
        bg=True,
    )
    assert ret.result is True
    assert "Logs" not in ret.changes
    assert "ExitCode" not in ret.changes
    assert ret.comment == "Container was run in the background"

    # Now check the logs. The expectation is that the above asserts
    # completed during the 5-second sleep.
    assert modules.docker.logs(container_name, follow=True) == "root\n"
