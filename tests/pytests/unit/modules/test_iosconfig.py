"""
Test the iosconfig Execution module.
"""

import textwrap

import pytest

import salt.modules.iosconfig as iosconfig
from salt.utils.odict import OrderedDict


@pytest.fixture
def running_config():
    return textwrap.dedent(
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


@pytest.fixture
def candidate_config():
    return textwrap.dedent(
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


@pytest.fixture
def merge_config():
    return textwrap.dedent(
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


@pytest.fixture
def configure_loader_modules():
    return {iosconfig: {}}


def test_tree(running_config):
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
    tree = iosconfig.tree(config=running_config)
    assert tree == running_config_tree


def test_clean(running_config):
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
    clean = iosconfig.clean(config=running_config)
    assert clean == clean_running_config


def test_merge_tree(running_config, merge_config):
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
        initial_config=running_config, merge_config=merge_config
    )
    assert merge_tree == expected_merge_tree


def test_merge_text(running_config, merge_config):
    expected_merge_text = textwrap.dedent(
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
        initial_config=running_config, merge_config=merge_config
    )
    assert merge_text == expected_merge_text


def test_merge_diff(running_config, merge_config):
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
        initial_config=running_config, merge_config=merge_config
    )
    assert diff.splitlines()[2:] == expected_diff.splitlines()


def test_diff_text(running_config, candidate_config):
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
        candidate_config=candidate_config, running_config=running_config
    )
    assert diff.splitlines()[2:] == expected_diff.splitlines()
