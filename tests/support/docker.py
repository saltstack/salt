# -*- coding: utf-8 -*-
"""
Common code used in Docker integration tests
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import functools
import random
import string

# Import 3rd-party libs
from salt._compat import ipaddress

# Import Salt libs
from salt.exceptions import CommandExecutionError
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


def random_name(prefix=""):
    ret = prefix
    for _ in range(8):
        ret += random.choice(string.ascii_lowercase)
    return ret


class Network(object):
    def __init__(self, name, **kwargs):
        self.kwargs = kwargs
        self.name = name
        try:
            self.net = ipaddress.ip_network(self.kwargs["subnet"])
            self._rand_indexes = random.sample(
                range(2, self.net.num_addresses - 1), self.net.num_addresses - 3
            )
            self.ip_arg = "ipv{0}_address".format(self.net.version)
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

    def arg_map(self, arg_name):
        return {
            "ipv4_address": "IPv4Address",
            "ipv6_address": "IPv6Address",
            "links": "Links",
            "aliases": "Aliases",
        }[arg_name]

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


class with_network(object):
    """
    Generate a network for the test. Information about the network will be
    passed to the wrapped function.
    """

    def __init__(self, **kwargs):
        self.create = kwargs.pop("create", False)
        self.network = Network(random_name(prefix="salt_net_"), **kwargs)
        if self.network.net is not None:
            if "enable_ipv6" not in kwargs:
                kwargs["enable_ipv6"] = self.network.net.version == 6
        self.kwargs = kwargs

    def __call__(self, func):
        self.func = func
        return functools.wraps(func)(
            # pylint: disable=W0108
            lambda testcase, *args, **kwargs: self.wrap(testcase, *args, **kwargs)
            # pylint: enable=W0108
        )

    def wrap(self, testcase, *args, **kwargs):
        if self.create:
            testcase.run_function(
                "docker.create_network", [self.network.name], **self.kwargs
            )
        try:
            return self.func(testcase, self.network, *args, **kwargs)
        finally:
            try:
                testcase.run_function(
                    "docker.disconnect_all_containers_from_network", [self.network.name]
                )
            except CommandExecutionError as exc:
                if "404" not in exc.__str__():
                    raise
            else:
                testcase.run_function("docker.remove_network", [self.network.name])
