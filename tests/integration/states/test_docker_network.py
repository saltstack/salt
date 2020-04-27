# -*- coding: utf-8 -*-
"""
Integration tests for the docker_network states
"""
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import errno
import functools
import logging
import os
import subprocess
import tempfile

# Import Salt Libs
import salt.utils.files
import salt.utils.network
import salt.utils.path
from salt.exceptions import CommandExecutionError
from tests.support.case import ModuleCase
from tests.support.docker import random_name, with_network
from tests.support.helpers import destructiveTest, requires_system_grains
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


IMAGE_NAME = random_name(prefix="salt_busybox_")
IPV6_ENABLED = bool(salt.utils.network.ip_addrs6(include_loopback=True))


def network_name(func):
    """
    Generate a randomized name for a network and clean it up afterward
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        name = random_name(prefix="salt_net_")
        try:
            return func(self, name, *args, **kwargs)
        finally:
            self.run_function("docker.disconnect_all_containers_from_network", [name])
            try:
                self.run_function("docker.remove_network", [name])
            except CommandExecutionError as exc:
                if "No such network" not in exc.__str__():
                    raise

    return wrapper


def container_name(func):
    """
    Generate a randomized name for a container and clean it up afterward
    """

    def build_image():
        # Create temp dir
        image_build_rootdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        script_path = os.path.join(RUNTIME_VARS.BASE_FILES, "mkimage-busybox-static")
        cmd = [script_path, image_build_rootdir, IMAGE_NAME]
        log.debug("Running '%s' to build busybox image", " ".join(cmd))
        process = subprocess.Popen(
            cmd, close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        output = process.communicate()[0]
        log.debug("Output from mkimge-busybox-static:\n%s", output)

        if process.returncode != 0:
            raise Exception("Failed to build image")

        try:
            salt.utils.files.rm_rf(image_build_rootdir)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            self.run_function("docker.inspect_image", [IMAGE_NAME])
        except CommandExecutionError:
            pass
        else:
            build_image()

        name = random_name(prefix="salt_test_")
        self.run_function(
            "docker.create",
            name=name,
            image=IMAGE_NAME,
            command="sleep 600",
            start=True,
        )
        try:
            return func(self, name, *args, **kwargs)
        finally:
            try:
                self.run_function("docker.rm", [name], force=True)
            except CommandExecutionError as exc:
                if "No such container" not in exc.__str__():
                    raise

    return wrapper


@destructiveTest
@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
class DockerNetworkTestCase(ModuleCase, SaltReturnAssertsMixin):
    """
    Test docker_network states
    """

    @classmethod
    def tearDownClass(cls):
        """
        Remove test image if present. Note that this will run a docker rmi even
        if no test which required the image was run.
        """
        cmd = ["docker", "rmi", "--force", IMAGE_NAME]
        log.debug("Running '%s' to destroy busybox image", " ".join(cmd))
        process = subprocess.Popen(
            cmd, close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        output = process.communicate()[0]
        log.debug("Output from %s:\n%s", " ".join(cmd), output)

        if process.returncode != 0 and "No such image" not in output:
            raise Exception("Failed to destroy image")

    def run_state(self, function, **kwargs):
        ret = super(DockerNetworkTestCase, self).run_state(function, **kwargs)
        log.debug("ret = %s", ret)
        return ret

    @with_network(create=False)
    def test_absent(self, net):
        self.assertSaltTrueReturn(
            self.run_state("docker_network.present", name=net.name)
        )
        ret = self.run_state("docker_network.absent", name=net.name)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        self.assertEqual(ret["changes"], {"removed": True})
        self.assertEqual(ret["comment"], "Removed network '{0}'".format(net.name))

    @container_name
    @with_network(create=False)
    def test_absent_with_disconnected_container(self, net, container_name):
        self.assertSaltTrueReturn(
            self.run_state(
                "docker_network.present", name=net.name, containers=[container_name]
            )
        )
        ret = self.run_state("docker_network.absent", name=net.name)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        self.assertEqual(
            ret["changes"], {"removed": True, "disconnected": [container_name]}
        )
        self.assertEqual(ret["comment"], "Removed network '{0}'".format(net.name))

    @with_network(create=False)
    def test_absent_when_not_present(self, net):
        ret = self.run_state("docker_network.absent", name=net.name)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret["changes"], {})
        self.assertEqual(
            ret["comment"], "Network '{0}' already absent".format(net.name)
        )

    @with_network(create=False)
    def test_present(self, net):
        ret = self.run_state("docker_network.present", name=net.name)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        # Make sure the state return is what we expect
        self.assertEqual(ret["changes"], {"created": True})
        self.assertEqual(ret["comment"], "Network '{0}' created".format(net.name))

        # Now check to see that the network actually exists. If it doesn't,
        # this next function call will raise an exception.
        self.run_function("docker.inspect_network", [net.name])

    @container_name
    @with_network(create=False)
    def test_present_with_containers(self, net, container_name):
        ret = self.run_state(
            "docker_network.present", name=net.name, containers=[container_name]
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        self.assertEqual(
            ret["changes"], {"created": True, "connected": [container_name]}
        )
        self.assertEqual(ret["comment"], "Network '{0}' created".format(net.name))

        # Now check to see that the network actually exists. If it doesn't,
        # this next function call will raise an exception.
        self.run_function("docker.inspect_network", [net.name])

    def _test_present_reconnect(self, net, container_name, reconnect=True):
        ret = self.run_state("docker_network.present", name=net.name, driver="bridge")
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        self.assertEqual(ret["changes"], {"created": True})
        self.assertEqual(ret["comment"], "Network '{0}' created".format(net.name))

        # Connect the container
        self.run_function(
            "docker.connect_container_to_network", [container_name, net.name]
        )

        # Change the driver to force the network to be replaced
        ret = self.run_state(
            "docker_network.present",
            name=net.name,
            driver="macvlan",
            reconnect=reconnect,
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        self.assertEqual(
            ret["changes"],
            {
                "recreated": True,
                "reconnected" if reconnect else "disconnected": [container_name],
                net.name: {"Driver": {"old": "bridge", "new": "macvlan"}},
            },
        )
        self.assertEqual(
            ret["comment"],
            "Network '{0}' was replaced with updated config".format(net.name),
        )

    @container_name
    @with_network(create=False)
    def test_present_with_reconnect(self, net, container_name):
        """
        Test reconnecting with containers not passed to state
        """
        self._test_present_reconnect(net, container_name, reconnect=True)

    @container_name
    @with_network(create=False)
    def test_present_with_no_reconnect(self, net, container_name):
        """
        Test reconnecting with containers not passed to state
        """
        self._test_present_reconnect(net, container_name, reconnect=False)

    @with_network()
    def test_present_internal(self, net):
        self.assertSaltTrueReturn(
            self.run_state("docker_network.present", name=net.name, internal=True,)
        )
        net_info = self.run_function("docker.inspect_network", [net.name])
        self.assertIs(net_info["Internal"], True)

    @with_network()
    def test_present_labels(self, net):
        # Test a mix of different ways of specifying labels
        self.assertSaltTrueReturn(
            self.run_state(
                "docker_network.present",
                name=net.name,
                labels=["foo", "bar=baz", {"hello": "world"}],
            )
        )
        net_info = self.run_function("docker.inspect_network", [net.name])
        self.assertEqual(
            net_info["Labels"], {"foo": "", "bar": "baz", "hello": "world"},
        )

    @with_network(subnet="fe3f:2180:26:1::/123")
    @with_network(subnet="10.247.197.96/27")
    @skipIf(not IPV6_ENABLED, "IPv6 not enabled")
    def test_present_enable_ipv6(self, net1, net2):
        self.assertSaltTrueReturn(
            self.run_state(
                "docker_network.present",
                name=net1.name,
                enable_ipv6=True,
                ipam_pools=[{"subnet": net1.subnet}, {"subnet": net2.subnet}],
            )
        )
        net_info = self.run_function("docker.inspect_network", [net1.name])
        self.assertIs(net_info["EnableIPv6"], True)

    @requires_system_grains
    @with_network()
    def test_present_attachable(self, net, grains):
        if grains["os_family"] == "RedHat" and grains.get("osmajorrelease", 0) <= 7:
            self.skipTest("Cannot reliably manage attachable on RHEL <= 7")

        self.assertSaltTrueReturn(
            self.run_state("docker_network.present", name=net.name, attachable=True,)
        )
        net_info = self.run_function("docker.inspect_network", [net.name])
        self.assertIs(net_info["Attachable"], True)

    @skipIf(True, "Skip until we can set up docker swarm testing")
    @with_network()
    def test_present_scope(self, net):
        self.assertSaltTrueReturn(
            self.run_state("docker_network.present", name=net.name, scope="global",)
        )
        net_info = self.run_function("docker.inspect_network", [net.name])
        self.assertIs(net_info["Scope"], "global")

    @skipIf(True, "Skip until we can set up docker swarm testing")
    @with_network()
    def test_present_ingress(self, net):
        self.assertSaltTrueReturn(
            self.run_state("docker_network.present", name=net.name, ingress=True,)
        )
        net_info = self.run_function("docker.inspect_network", [net.name])
        self.assertIs(net_info["Ingress"], True)

    @with_network(subnet="10.247.197.128/27")
    @with_network(subnet="10.247.197.96/27")
    def test_present_with_custom_ipv4(self, net1, net2):
        # First run will test passing the IPAM arguments individually
        self.assertSaltTrueReturn(
            self.run_state(
                "docker_network.present",
                name=net1.name,
                subnet=net1.subnet,
                gateway=net1.gateway,
            )
        )
        # Second run will pass them in the ipam_pools argument
        ret = self.run_state(
            "docker_network.present",
            name=net1.name,  # We want to keep the same network name
            ipam_pools=[{"subnet": net2.subnet, "gateway": net2.gateway}],
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

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
        self.assertEqual(ret["changes"], expected)
        self.assertEqual(
            ret["comment"],
            "Network '{0}' was replaced with updated config".format(net1.name),
        )

    @with_network(subnet="fe3f:2180:26:1::20/123")
    @with_network(subnet="fe3f:2180:26:1::/123")
    @with_network(subnet="10.247.197.96/27")
    @skipIf(not IPV6_ENABLED, "IPv6 not enabled")
    def test_present_with_custom_ipv6(self, ipv4_net, ipv6_net1, ipv6_net2):
        self.assertSaltTrueReturn(
            self.run_state(
                "docker_network.present",
                name=ipv4_net.name,
                enable_ipv6=True,
                ipam_pools=[
                    {"subnet": ipv4_net.subnet, "gateway": ipv4_net.gateway},
                    {"subnet": ipv6_net1.subnet, "gateway": ipv6_net1.gateway},
                ],
            )
        )

        ret = self.run_state(
            "docker_network.present",
            name=ipv4_net.name,  # We want to keep the same network name
            enable_ipv6=True,
            ipam_pools=[
                {"subnet": ipv4_net.subnet, "gateway": ipv4_net.gateway},
                {"subnet": ipv6_net2.subnet, "gateway": ipv6_net2.gateway},
            ],
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

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
        self.assertEqual(ret["changes"], expected)
        self.assertEqual(
            ret["comment"],
            "Network '{0}' was replaced with updated config".format(ipv4_net.name),
        )
