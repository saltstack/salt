# -*- coding: utf-8 -*-
"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
    :codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.mine as mine
import salt.utils.mine
from salt.utils.odict import OrderedDict

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class FakeCache(object):
    def __init__(self):
        self.data = {}

    def store(self, bank, key, value):
        self.data[bank, key] = value
        return "FakeCache:StoreSuccess!"

    def fetch(self, bank, key):
        return self.data.get((bank, key), {})

    def debug(self):
        print(__name__ + ":FakeCache dump:\n" "{}".format(self.data))


class MineTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.mine
    """

    def setUp(self):
        self.kernel_ret = "Linux!"
        self.foo_ret = "baz"
        self.ip_ret = "2001:db8::1:3"
        self.cache = FakeCache()

    def setup_loader_modules(self):
        mock_match = MagicMock(return_value="webserver")
        return {
            mine: {
                "__salt__": {
                    "match.glob": mock_match,
                    "match.pcre": mock_match,
                    "match.list": mock_match,
                    "match.grain": mock_match,
                    "match.grain_pcre": mock_match,
                    "match.ipcidr": mock_match,
                    "match.compound": mock_match,
                    "match.pillar": mock_match,
                    "match.pillar_pcre": mock_match,
                    "data.get": lambda key: self.cache.fetch("minions/webserver", key),
                    "data.update": lambda key, value: self.cache.store(
                        "minions/webserver", key, value
                    ),
                }
            }
        }

    def test_get_local_empty(self):
        """
        Tests getting function data from the local mine that does not exist.
        """
        with patch.dict(mine.__opts__, {"file_client": "local", "id": "webserver"}):
            ret_classic = mine.get("*", "funky.doodle")
            ret_dict = mine.get("*", ["funky.doodle"])
        self.assertEqual(ret_classic, {})
        self.assertEqual(ret_dict, {})

    def test_get_local_classic(self):
        """
        Tests getting function data from the local mine that was stored without minion-side ACL.
        This verifies backwards compatible reads from a salt mine.
        """
        # Prefill minion cache with a non-ACL value
        self.cache.store("minions/webserver", "mine_cache", {"foobard": "barfood"})
        with patch.dict(mine.__opts__, {"file_client": "local", "id": "webserver"}):
            ret_classic = mine.get("*", "foobard")
            ret_dict = mine.get("*", ["foobard"])
        self.assertEqual(ret_classic, {"webserver": "barfood"})
        self.assertEqual(ret_dict, {"foobard": {"webserver": "barfood"}})

    def test_send_get_local(self):
        """
        Tests sending an item to the mine in the minion's local cache,
        and then immediately fetching it again (since tests are executed unordered).
        Also verify that the stored mine cache does not use ACL data structure
        without allow_tgt passed.
        """
        with patch.dict(
            mine.__opts__, {"file_client": "local", "id": "webserver"}
        ), patch.dict(
            mine.__salt__,
            {
                "network.ip_addrs": MagicMock(return_value=self.ip_ret),
                "foo.bar": MagicMock(return_value=self.foo_ret),
            },
        ):
            ret = mine.send("ip_addr", mine_function="network.ip_addrs")
            mine.send("foo.bar")
        self.assertEqual(ret, "FakeCache:StoreSuccess!")
        self.assertEqual(
            self.cache.fetch("minions/webserver", "mine_cache"),
            {"ip_addr": self.ip_ret, "foo.bar": self.foo_ret},
        )
        with patch.dict(mine.__opts__, {"file_client": "local", "id": "webserver"}):
            ret_single = mine.get("*", "ip_addr")
            ret_single_dict = mine.get("*", ["ip_addr"])
            ret_multi = mine.get("*", "ip_addr,foo.bar")
            ret_multi2 = mine.get("*", ["ip_addr", "foo.bar"])
        self.assertEqual(ret_single, {"webserver": self.ip_ret})
        self.assertEqual(ret_single_dict, {"ip_addr": {"webserver": self.ip_ret}})
        self.assertEqual(
            ret_multi,
            {
                "ip_addr": {"webserver": self.ip_ret},
                "foo.bar": {"webserver": self.foo_ret},
            },
        )
        self.assertEqual(ret_multi, ret_multi2)

    def test_send_get_acl_local(self):
        """
        Tests sending an item to the mine in the minion's local cache,
        including ACL information (useless when only working locally, but hey),
        and then immediately fetching it again (since tests are executed unordered).
        Also verify that the stored mine cache has the correct structure (with ACL)
        when using allow_tgt and no ACL without allow_tgt.
        """
        with patch.dict(
            mine.__opts__, {"file_client": "local", "id": "webserver"}
        ), patch.dict(
            mine.__salt__,
            {
                "network.ip_addrs": MagicMock(return_value=self.ip_ret),
                "foo.bar": MagicMock(return_value=self.foo_ret),
            },
        ):
            ret = mine.send(
                "ip_addr",
                mine_function="network.ip_addrs",
                allow_tgt="web*",
                allow_tgt_type="glob",
            )
            mine.send("foo.bar")
        self.assertEqual(ret, "FakeCache:StoreSuccess!")
        self.assertEqual(
            self.cache.fetch("minions/webserver", "mine_cache"),
            {
                "ip_addr": {
                    salt.utils.mine.MINE_ITEM_ACL_DATA: self.ip_ret,
                    salt.utils.mine.MINE_ITEM_ACL_ID: salt.utils.mine.MINE_ITEM_ACL_VERSION,
                    "allow_tgt": "web*",
                    "allow_tgt_type": "glob",
                },
                "foo.bar": self.foo_ret,
            },
        )
        with patch.dict(mine.__opts__, {"file_client": "local", "id": "webserver"}):
            ret_single = mine.get("*", "ip_addr")
        self.assertEqual(ret_single, {"webserver": self.ip_ret})

    def test_send_master(self):
        """
        Tests sending an item to the mine stored on the master.
        This is done by capturing the load that is sent to the master.
        """
        with patch.object(
            mine, "_mine_send", MagicMock(side_effect=lambda x, y: x)
        ), patch.dict(
            mine.__salt__, {"foo.bar": MagicMock(return_value=self.foo_ret)}
        ), patch.dict(
            mine.__opts__, {"file_client": "remote", "id": "foo"}
        ):
            ret = mine.send("foo.bar")
        self.assertEqual(
            ret,
            {
                "id": "foo",
                "cmd": "_mine",
                "data": {"foo.bar": self.foo_ret},
                "clear": False,
            },
        )

    def test_send_master_acl(self):
        """
        Tests sending an item to the mine stored on the master. Now with ACL.
        This is done by capturing the load that is sent to the master.
        """
        with patch.object(
            mine, "_mine_send", MagicMock(side_effect=lambda x, y: x)
        ), patch.dict(
            mine.__salt__, {"foo.bar": MagicMock(return_value=self.foo_ret)}
        ), patch.dict(
            mine.__opts__, {"file_client": "remote", "id": "foo"}
        ):
            ret = mine.send("foo.bar", allow_tgt="roles:web", allow_tgt_type="grains")
        self.assertEqual(
            ret,
            {
                "id": "foo",
                "cmd": "_mine",
                "data": {
                    "foo.bar": {
                        salt.utils.mine.MINE_ITEM_ACL_DATA: self.foo_ret,
                        salt.utils.mine.MINE_ITEM_ACL_ID: salt.utils.mine.MINE_ITEM_ACL_VERSION,
                        "allow_tgt": "roles:web",
                        "allow_tgt_type": "grains",
                    },
                },
                "clear": False,
            },
        )

    def test_get_master(self):
        """
        Tests loading a mine item from the mine stored on the master.
        """
        mock_load = {
            "tgt_type": "qux",
            "tgt": self.foo_ret,
            "cmd": "_mine_get",
            "fun": "foo.bar",
            "id": "foo",
        }
        with patch.object(
            mine, "_mine_get", MagicMock(return_value=mock_load)
        ), patch.dict(mine.__opts__, {"file_client": "remote", "id": "foo"}):
            # Verify the correct load
            self.assertEqual(mine.get("*", "foo.bar"), mock_load)

    def test_get_master_exclude_minion(self):
        """
        Tests the exclude_minion-parameter for mine.get
        """
        _mine_get_ret = OrderedDict([("webserver", "value")])
        with patch.object(
            mine, "_mine_get", MagicMock(return_value=_mine_get_ret)
        ), patch.dict(mine.__opts__, {"file_client": "remote", "id": "webserver"}):
            self.assertEqual(
                mine.get("*", "foo.bar", exclude_minion=False), {"webserver": "value"}
            )
            self.assertEqual(mine.get("*", "foo.bar", exclude_minion=True), {})

    def test_update_local(self):
        """
        Tests the ``update``-function on the minion's local cache.
        Updates mine functions from pillar+config only.
        """
        config_mine_functions = {
            "ip_addr": {"mine_function": "network.ip_addrs"},
            "network.ip_addrs": [],
            "kernel": [
                {"mine_function": "grains.get"},
                "kernel",
                {"allow_tgt": "web*"},
            ],
            "foo.bar": {"allow_tgt": "G@roles:webserver", "allow_tgt_type": "compound"},
        }
        with patch.dict(
            mine.__opts__, {"file_client": "local", "id": "webserver"}
        ), patch.dict(
            mine.__salt__,
            {
                "config.merge": MagicMock(return_value=config_mine_functions),
                "grains.get": lambda x: self.kernel_ret,
                "network.ip_addrs": MagicMock(return_value=self.ip_ret),
                "foo.bar": MagicMock(return_value=self.foo_ret),
            },
        ):
            ret = mine.update()
        self.assertEqual(ret, "FakeCache:StoreSuccess!")
        # Check if the mine entries have been stored properly in the FakeCache.
        self.assertEqual(
            self.cache.fetch("minions/webserver", "mine_cache"),
            {
                "ip_addr": self.ip_ret,
                "network.ip_addrs": self.ip_ret,
                "foo.bar": {
                    salt.utils.mine.MINE_ITEM_ACL_DATA: self.foo_ret,
                    salt.utils.mine.MINE_ITEM_ACL_ID: salt.utils.mine.MINE_ITEM_ACL_VERSION,
                    "allow_tgt": "G@roles:webserver",
                    "allow_tgt_type": "compound",
                },
                "kernel": {
                    salt.utils.mine.MINE_ITEM_ACL_DATA: self.kernel_ret,
                    salt.utils.mine.MINE_ITEM_ACL_ID: salt.utils.mine.MINE_ITEM_ACL_VERSION,
                    "allow_tgt": "web*",
                },
            },
        )

    def test_update_local_specific(self):
        """
        Tests the ``update``-function on the minion's local cache.
        Updates mine functions from kwargs only.
        """
        manual_mine_functions = {
            "ip_addr": {"mine_function": "network.ip_addrs"},
            "network.ip_addrs": [],
            "kernel": [
                {"mine_function": "grains.get"},
                "kernel",
                {"allow_tgt": "web*"},
            ],
            "foo.bar": {"allow_tgt": "G@roles:webserver", "allow_tgt_type": "compound"},
        }
        with patch.dict(
            mine.__opts__, {"file_client": "local", "id": "webserver"}
        ), patch.dict(
            mine.__salt__,
            {
                "config.merge": MagicMock(return_value={}),
                "grains.get": lambda x: "Linux!!",
                "network.ip_addrs": MagicMock(return_value=self.ip_ret),
                "foo.bar": MagicMock(return_value=self.foo_ret),
            },
        ):
            ret = mine.update(mine_functions=manual_mine_functions)
        self.assertEqual(ret, "FakeCache:StoreSuccess!")
        # Check if the mine entries have been stored properly in the FakeCache.
        self.assertEqual(
            self.cache.fetch("minions/webserver", "mine_cache"),
            {
                "ip_addr": self.ip_ret,
                "network.ip_addrs": self.ip_ret,
                "foo.bar": {
                    salt.utils.mine.MINE_ITEM_ACL_DATA: self.foo_ret,
                    salt.utils.mine.MINE_ITEM_ACL_ID: salt.utils.mine.MINE_ITEM_ACL_VERSION,
                    "allow_tgt": "G@roles:webserver",
                    "allow_tgt_type": "compound",
                },
                "kernel": {
                    salt.utils.mine.MINE_ITEM_ACL_DATA: "Linux!!",
                    salt.utils.mine.MINE_ITEM_ACL_ID: salt.utils.mine.MINE_ITEM_ACL_VERSION,
                    "allow_tgt": "web*",
                },
            },
        )

    def test_update_master(self):
        """
        Tests whether the ``update``-function sends the correct data to the master.
        """
        config_mine_functions = {
            "ip_addr": {"mine_function": "network.ip_addrs"},
            "network.ip_addrs": [],
            "kernel": [{"mine_function": "grains.get"}, "kernel"],
            "foo.bar": {},
        }
        mock_load = {
            "id": "webserver",
            "cmd": "_mine",
            "data": {
                "ip_addr": self.ip_ret,
                "network.ip_addrs": self.ip_ret,
                "foo.bar": self.foo_ret,
                "kernel": self.kernel_ret,
            },
            "clear": False,
        }
        with patch.object(
            mine, "_mine_send", MagicMock(side_effect=lambda x, y: x)
        ), patch.dict(
            mine.__opts__, {"file_client": "remote", "id": "webserver"}
        ), patch.dict(
            mine.__salt__,
            {
                "config.merge": MagicMock(return_value=config_mine_functions),
                "grains.get": lambda x: self.kernel_ret,
                "network.ip_addrs": MagicMock(return_value=self.ip_ret),
                "foo.bar": MagicMock(return_value=self.foo_ret),
            },
        ):
            # Verify the correct load
            self.assertEqual(mine.update(), mock_load)

    def test_delete_local(self):
        """
        Tests the ``delete``-function on the minion's local cache.
        """
        # Prefill minion cache with a non-ACL value
        self.cache.store("minions/webserver", "mine_cache", {"foobard": "barfood"})
        with patch.dict(mine.__opts__, {"file_client": "local", "id": "webserver"}):
            ret = mine.delete("foobard")
            self.assertEqual(self.cache.fetch("minions/webserver", "mine_cache"), {})

    def test_delete_master(self):
        """
        Tests whether the ``delete``-function sends the correct data to the master.
        """
        # Prefill minion cache with a non-ACL value
        self.cache.store("minions/webserver", "mine_cache", {"foobard": "barfood"})
        mock_load = {
            "cmd": "_mine_delete",
            "fun": "foobard",
            "id": "foo",
        }
        with patch.object(
            mine, "_mine_send", MagicMock(side_effect=lambda x, y: x)
        ), patch.dict(mine.__opts__, {"file_client": "remote", "id": "foo"}):
            # Verify the correct load
            self.assertEqual(mine.delete("foobard"), mock_load)

    def test_flush_local(self):
        """
        Tests the ``flush``-function on the minion's local cache.
        """
        # Prefill minion cache with a non-ACL value
        self.cache.store("minions/webserver", "mine_cache", {"foobard": "barfood"})
        with patch.dict(mine.__opts__, {"file_client": "local", "id": "webserver"}):
            ret = mine.flush()
            self.assertEqual(self.cache.fetch("minions/webserver", "mine_cache"), {})

    def test_flush_master(self):
        """
        Tests whether the ``flush``-function sends the correct data to the master.
        """
        mock_load = {"cmd": "_mine_flush", "id": "foo"}
        with patch.object(
            mine, "_mine_send", MagicMock(side_effect=lambda x, y: x)
        ), patch.dict(mine.__opts__, {"file_client": "remote", "id": "foo"}):
            # Verify the correct load
            self.assertEqual(mine.flush(), mock_load)

    def test_valid(self):
        """
        Tests the ``valid``-function.
        Note that mine functions defined as list are returned in dict format.
        Mine functions that do not exist in __salt__ are not returned.
        """
        config_mine_functions = {
            "network.ip_addrs": [],
            "kernel": [{"mine_function": "grains.get"}, "kernel"],
            "fubar": [{"mine_function": "does.not_exist"}],
        }
        with patch.dict(
            mine.__salt__,
            {
                "config.merge": MagicMock(return_value=config_mine_functions),
                "network.ip_addrs": lambda: True,
                "grains.get": lambda: True,
            },
        ):
            self.assertEqual(
                mine.valid(),
                {"network.ip_addrs": [], "kernel": {"grains.get": ["kernel"]}},
            )

    def test_get_docker(self):
        """
        Test for Get all mine data for 'docker.ps' and run an
        aggregation.
        """
        ps_response = {
            "localhost": {
                "host": {
                    "interfaces": {
                        "docker0": {
                            "hwaddr": "88:99:00:00:99:99",
                            "inet": [
                                {
                                    "address": "172.17.42.1",
                                    "broadcast": None,
                                    "label": "docker0",
                                    "netmask": "255.255.0.0",
                                }
                            ],
                            "inet6": [
                                {
                                    "address": "ffff::eeee:aaaa:bbbb:8888",
                                    "prefixlen": "64",
                                }
                            ],
                            "up": True,
                        },
                        "eth0": {
                            "hwaddr": "88:99:00:99:99:99",
                            "inet": [
                                {
                                    "address": "192.168.0.1",
                                    "broadcast": "192.168.0.255",
                                    "label": "eth0",
                                    "netmask": "255.255.255.0",
                                }
                            ],
                            "inet6": [
                                {
                                    "address": "ffff::aaaa:aaaa:bbbb:8888",
                                    "prefixlen": "64",
                                }
                            ],
                            "up": True,
                        },
                    }
                },
                "abcdefhjhi1234567899": {  # container Id
                    "Ports": [
                        {
                            "IP": "0.0.0.0",  # we bind on every interfaces
                            "PrivatePort": 80,
                            "PublicPort": 80,
                            "Type": "tcp",
                        }
                    ],
                    "Image": "image:latest",
                    "Info": {"Id": "abcdefhjhi1234567899"},
                },
            }
        }
        with patch.object(mine, "get", return_value=ps_response):
            ret = mine.get_docker()
            # Sort ifaces since that will change between py2 and py3
            ret["image:latest"]["ipv4"][80] = sorted(ret["image:latest"]["ipv4"][80])
            self.assertEqual(
                ret,
                {
                    "image:latest": {
                        "ipv4": {80: sorted(["172.17.42.1:80", "192.168.0.1:80"])}
                    }
                },
            )

    def test_get_docker_with_container_id(self):
        """
        Test for Get all mine data for 'docker.ps' and run an
        aggregation.
        """
        ps_response = {
            "localhost": {
                "host": {
                    "interfaces": {
                        "docker0": {
                            "hwaddr": "88:99:00:00:99:99",
                            "inet": [
                                {
                                    "address": "172.17.42.1",
                                    "broadcast": None,
                                    "label": "docker0",
                                    "netmask": "255.255.0.0",
                                }
                            ],
                            "inet6": [
                                {
                                    "address": "ffff::eeee:aaaa:bbbb:8888",
                                    "prefixlen": "64",
                                }
                            ],
                            "up": True,
                        },
                        "eth0": {
                            "hwaddr": "88:99:00:99:99:99",
                            "inet": [
                                {
                                    "address": "192.168.0.1",
                                    "broadcast": "192.168.0.255",
                                    "label": "eth0",
                                    "netmask": "255.255.255.0",
                                }
                            ],
                            "inet6": [
                                {
                                    "address": "ffff::aaaa:aaaa:bbbb:8888",
                                    "prefixlen": "64",
                                }
                            ],
                            "up": True,
                        },
                    }
                },
                "abcdefhjhi1234567899": {  # container Id
                    "Ports": [
                        {
                            "IP": "0.0.0.0",  # we bind on every interfaces
                            "PrivatePort": 80,
                            "PublicPort": 80,
                            "Type": "tcp",
                        }
                    ],
                    "Image": "image:latest",
                    "Info": {"Id": "abcdefhjhi1234567899"},
                },
            }
        }
        with patch.object(mine, "get", return_value=ps_response):
            ret = mine.get_docker(with_container_id=True)
            # Sort ifaces since that will change between py2 and py3
            ret["image:latest"]["ipv4"][80] = sorted(ret["image:latest"]["ipv4"][80])
            self.assertEqual(
                ret,
                {
                    "image:latest": {
                        "ipv4": {
                            80: sorted(
                                [
                                    ("172.17.42.1:80", "abcdefhjhi1234567899"),
                                    ("192.168.0.1:80", "abcdefhjhi1234567899"),
                                ]
                            )
                        }
                    }
                },
            )
