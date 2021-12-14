"""
Test the iosconfig Execution module.
"""

import textwrap

import salt.modules.iosconfig as iosconfig

# Import Salt modules
from salt.utils.odict import OrderedDict
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class TestModulesIOSConfig(TestCase, LoaderModuleMockMixin):

    running_config = textwrap.dedent(
        """\
        interface GigabitEthernet1
         ip address dhcp
         negotiation auto
         no mop enabled
        !
        interface GigabitEthernet2
         ip address 172.20.0.1 255.255.255.0
         shutdown
         negotiation auto
        !
        interface GigabitEthernet3
         no ip address
         shutdown
         negotiation auto
        !"""
    )

    candidate_config = textwrap.dedent(
        """\
        interface GigabitEthernet1
         ip address dhcp
         negotiation auto
         no mop enabled
        !
        interface GigabitEthernet2
         no ip address
         shutdown
         negotiation auto
        !
        interface GigabitEthernet3
         no ip address
         negotiation auto
        !
        router bgp 65000
         bgp log-neighbor-changes
         neighbor 1.1.1.1 remote-as 12345
        !
        !"""
    )

    merge_config = textwrap.dedent(
        """\
        router bgp 65000
         bgp log-neighbor-changes
         neighbor 1.1.1.1 remote-as 12345
        !
        !
        virtual-service csr_mgmt
        !
        ip forward-protocol nd
        !"""
    )

    def setup_loader_modules(self):
        return {}

    def test_tree(self):
        running_config_tree = OrderedDict(
            [
                (
                    "interface GigabitEthernet1",
                    OrderedDict(
                        [
                            ("ip address dhcp", OrderedDict()),
                            ("negotiation auto", OrderedDict()),
                            ("no mop enabled", OrderedDict()),
                        ]
                    ),
                ),
                (
                    "interface GigabitEthernet2",
                    OrderedDict(
                        [
                            ("ip address 172.20.0.1 255.255.255.0", OrderedDict()),
                            ("shutdown", OrderedDict()),
                            ("negotiation auto", OrderedDict()),
                        ]
                    ),
                ),
                (
                    "interface GigabitEthernet3",
                    OrderedDict(
                        [
                            ("no ip address", OrderedDict()),
                            ("shutdown", OrderedDict()),
                            ("negotiation auto", OrderedDict()),
                        ]
                    ),
                ),
            ]
        )
        tree = iosconfig.tree(config=self.running_config)
        self.assertEqual(tree, running_config_tree)

    def test_clean(self):
        clean_running_config = textwrap.dedent(
            """\
            interface GigabitEthernet1
             ip address dhcp
             negotiation auto
             no mop enabled
            interface GigabitEthernet2
             ip address 172.20.0.1 255.255.255.0
             shutdown
             negotiation auto
            interface GigabitEthernet3
             no ip address
             shutdown
             negotiation auto
        """
        )
        clean = iosconfig.clean(config=self.running_config)
        self.assertEqual(clean, clean_running_config)

    def test_merge_tree(self):
        expected_merge_tree = OrderedDict(
            [
                (
                    "interface GigabitEthernet1",
                    OrderedDict(
                        [
                            ("ip address dhcp", OrderedDict()),
                            ("negotiation auto", OrderedDict()),
                            ("no mop enabled", OrderedDict()),
                        ]
                    ),
                ),
                (
                    "interface GigabitEthernet2",
                    OrderedDict(
                        [
                            ("ip address 172.20.0.1 255.255.255.0", OrderedDict()),
                            ("shutdown", OrderedDict()),
                            ("negotiation auto", OrderedDict()),
                        ]
                    ),
                ),
                (
                    "interface GigabitEthernet3",
                    OrderedDict(
                        [
                            ("no ip address", OrderedDict()),
                            ("shutdown", OrderedDict()),
                            ("negotiation auto", OrderedDict()),
                        ]
                    ),
                ),
                (
                    "router bgp 65000",
                    OrderedDict(
                        [
                            ("bgp log-neighbor-changes", OrderedDict()),
                            ("neighbor 1.1.1.1 remote-as 12345", OrderedDict()),
                        ]
                    ),
                ),
                ("virtual-service csr_mgmt", OrderedDict()),
                ("ip forward-protocol nd", OrderedDict()),
            ]
        )
        merge_tree = iosconfig.merge_tree(
            initial_config=self.running_config, merge_config=self.merge_config
        )
        self.assertEqual(merge_tree, expected_merge_tree)

    def test_merge_text(self):
        extected_merge_text = textwrap.dedent(
            """\
            interface GigabitEthernet1
             ip address dhcp
             negotiation auto
             no mop enabled
            interface GigabitEthernet2
             ip address 172.20.0.1 255.255.255.0
             shutdown
             negotiation auto
            interface GigabitEthernet3
             no ip address
             shutdown
             negotiation auto
            router bgp 65000
             bgp log-neighbor-changes
             neighbor 1.1.1.1 remote-as 12345
            virtual-service csr_mgmt
            ip forward-protocol nd
        """
        )
        merge_text = iosconfig.merge_text(
            initial_config=self.running_config, merge_config=self.merge_config
        )
        self.assertEqual(merge_text, extected_merge_text)

    def test_merge_diff(self):
        expected_diff = textwrap.dedent(
            """\
            @@ -10,3 +10,8 @@
              no ip address
              shutdown
              negotiation auto
            +router bgp 65000
            + bgp log-neighbor-changes
            + neighbor 1.1.1.1 remote-as 12345
            +virtual-service csr_mgmt
            +ip forward-protocol nd
        """
        )
        diff = iosconfig.merge_diff(
            initial_config=self.running_config, merge_config=self.merge_config
        )
        self.assertEqual(diff.splitlines()[2:], expected_diff.splitlines())

    def test_diff_text(self):
        expected_diff = textwrap.dedent(
            """\
            @@ -3,10 +3,12 @@
              negotiation auto
              no mop enabled
             interface GigabitEthernet2
            - ip address 172.20.0.1 255.255.255.0
            + no ip address
              shutdown
              negotiation auto
             interface GigabitEthernet3
              no ip address
            - shutdown
              negotiation auto
            +router bgp 65000
            + bgp log-neighbor-changes
            + neighbor 1.1.1.1 remote-as 12345
            """
        )
        diff = iosconfig.diff_text(
            candidate_config=self.candidate_config, running_config=self.running_config
        )
        self.assertEqual(diff.splitlines()[2:], expected_diff.splitlines())
