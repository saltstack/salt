"""
NAPALM NTP
==========

Manages NTP on network devices.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`
- :mod:`NET basic features <salt.modules.napalm_network>`

.. seealso::
    :mod:`NTP peers management state <salt.states.netntp>`

.. versionadded:: 2016.11.0
"""

import logging

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

log = logging.getLogger(__file__)


# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = "ntp"
__proxyenabled__ = ["napalm"]
__virtual_aliases__ = ("napalm_ntp",)
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    """
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    """
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@proxy_napalm_wrap
def peers(**kwargs):  # pylint: disable=unused-argument
    """
    Returns a list the NTP peers configured on the network device.

    :return: configured NTP peers as list.

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.peers

    Example output:

    .. code-block:: python

        [
            '192.168.0.1',
            '172.17.17.1',
            '172.17.17.2',
            '2400:cb00:6:1024::c71b:840a'
        ]

    """

    ntp_peers = salt.utils.napalm.call(
        napalm_device, "get_ntp_peers", **{}  # pylint: disable=undefined-variable
    )

    if not ntp_peers.get("result"):
        return ntp_peers

    ntp_peers_list = list(ntp_peers.get("out", {}).keys())

    ntp_peers["out"] = ntp_peers_list

    return ntp_peers


@proxy_napalm_wrap
def servers(**kwargs):  # pylint: disable=unused-argument
    """
    Returns a list of the configured NTP servers on the device.

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.servers

    Example output:

    .. code-block:: python

        [
            '192.168.0.1',
            '172.17.17.1',
            '172.17.17.2',
            '2400:cb00:6:1024::c71b:840a'
        ]
    """

    ntp_servers = salt.utils.napalm.call(
        napalm_device, "get_ntp_servers", **{}  # pylint: disable=undefined-variable
    )

    if not ntp_servers.get("result"):
        return ntp_servers

    ntp_servers_list = list(ntp_servers.get("out", {}).keys())

    ntp_servers["out"] = ntp_servers_list

    return ntp_servers


@proxy_napalm_wrap
def stats(peer=None, **kwargs):  # pylint: disable=unused-argument
    """
    Returns a dictionary containing synchronization details of the NTP peers.

    :param peer: Returns only the details of a specific NTP peer.
    :return: a list of dictionaries, with the following keys:

        * remote
        * referenceid
        * synchronized
        * stratum
        * type
        * when
        * hostpoll
        * reachability
        * delay
        * offset
        * jitter

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.stats

    Example output:

    .. code-block:: python

        [
            {
                'remote'        : '188.114.101.4',
                'referenceid'   : '188.114.100.1',
                'synchronized'  : True,
                'stratum'       : 4,
                'type'          : '-',
                'when'          : '107',
                'hostpoll'      : 256,
                'reachability'  : 377,
                'delay'         : 164.228,
                'offset'        : -13.866,
                'jitter'        : 2.695
            }
        ]
    """

    proxy_output = salt.utils.napalm.call(
        napalm_device, "get_ntp_stats", **{}  # pylint: disable=undefined-variable
    )

    if not proxy_output.get("result"):
        return proxy_output

    ntp_peers = proxy_output.get("out")

    if peer:
        ntp_peers = [
            ntp_peer for ntp_peer in ntp_peers if ntp_peer.get("remote", "") == peer
        ]

    proxy_output.update({"out": ntp_peers})

    return proxy_output


@proxy_napalm_wrap
def set_peers(*peers, **options):
    """
    Configures a list of NTP peers on the device.

    :param peers: list of IP Addresses/Domain Names
    :param test (bool): discard loaded config. By default ``test`` is False
        (will not dicard the changes)
    :commit commit (bool): commit loaded config. By default ``commit`` is True
        (will commit the changes). Useful when the user does not want to commit
        after each change, but after a couple.

    By default this function will commit the config changes (if any). To load without committing, use the `commit`
    option. For dry run use the `test` argument.

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.set_peers 192.168.0.1 172.17.17.1 time.apple.com
        salt '*' ntp.set_peers 172.17.17.1 test=True  # only displays the diff
        salt '*' ntp.set_peers 192.168.0.1 commit=False  # preserves the changes, but does not commit
    """

    test = options.pop("test", False)
    commit = options.pop("commit", True)

    # pylint: disable=undefined-variable
    return __salt__["net.load_template"](
        "set_ntp_peers",
        peers=peers,
        test=test,
        commit=commit,
        inherit_napalm_device=napalm_device,
    )
    # pylint: enable=undefined-variable


@proxy_napalm_wrap
def set_servers(*servers, **options):
    """
    Configures a list of NTP servers on the device.

    :param servers: list of IP Addresses/Domain Names
    :param test (bool): discard loaded config. By default ``test`` is False
        (will not dicard the changes)
    :commit commit (bool): commit loaded config. By default ``commit`` is True
        (will commit the changes). Useful when the user does not want to commit
        after each change, but after a couple.

    By default this function will commit the config changes (if any). To load without committing, use the `commit`
    option. For dry run use the `test` argument.

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.set_servers 192.168.0.1 172.17.17.1 time.apple.com
        salt '*' ntp.set_servers 172.17.17.1 test=True  # only displays the diff
        salt '*' ntp.set_servers 192.168.0.1 commit=False  # preserves the changes, but does not commit
    """

    test = options.pop("test", False)
    commit = options.pop("commit", True)

    # pylint: disable=undefined-variable
    return __salt__["net.load_template"](
        "set_ntp_servers",
        servers=servers,
        test=test,
        commit=commit,
        inherit_napalm_device=napalm_device,
    )
    # pylint: enable=undefined-variable


@proxy_napalm_wrap
def delete_peers(*peers, **options):
    """
    Removes NTP peers configured on the device.

    :param peers: list of IP Addresses/Domain Names to be removed as NTP peers
    :param test (bool): discard loaded config. By default ``test`` is False
        (will not dicard the changes)
    :param commit (bool): commit loaded config. By default ``commit`` is True
        (will commit the changes). Useful when the user does not want to commit
        after each change, but after a couple.

    By default this function will commit the config changes (if any). To load
    without committing, use the ``commit`` option. For a dry run, use the
    ``test`` argument.

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.delete_peers 8.8.8.8 time.apple.com
        salt '*' ntp.delete_peers 172.17.17.1 test=True  # only displays the diff
        salt '*' ntp.delete_peers 192.168.0.1 commit=False  # preserves the changes, but does not commit
    """

    test = options.pop("test", False)
    commit = options.pop("commit", True)

    # pylint: disable=undefined-variable
    return __salt__["net.load_template"](
        "delete_ntp_peers",
        peers=peers,
        test=test,
        commit=commit,
        inherit_napalm_device=napalm_device,
    )
    # pylint: enable=undefined-variable


@proxy_napalm_wrap
def delete_servers(*servers, **options):
    """
    Removes NTP servers configured on the device.

    :param servers: list of IP Addresses/Domain Names to be removed as NTP
        servers
    :param test (bool): discard loaded config. By default ``test`` is False
        (will not dicard the changes)
    :param commit (bool): commit loaded config. By default ``commit`` is True
        (will commit the changes). Useful when the user does not want to commit
        after each change, but after a couple.

    By default this function will commit the config changes (if any). To load
    without committing, use the ``commit`` option. For dry run use the ``test``
    argument.

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.delete_servers 8.8.8.8 time.apple.com
        salt '*' ntp.delete_servers 172.17.17.1 test=True  # only displays the diff
        salt '*' ntp.delete_servers 192.168.0.1 commit=False  # preserves the changes, but does not commit
    """

    test = options.pop("test", False)
    commit = options.pop("commit", True)

    # pylint: disable=undefined-variable
    return __salt__["net.load_template"](
        "delete_ntp_servers",
        servers=servers,
        test=test,
        commit=commit,
        inherit_napalm_device=napalm_device,
    )
    # pylint: enable=undefined-variable
