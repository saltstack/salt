# -*- coding: utf-8 -*-
'''
Network NTP
===========

.. versionadded: 2016.11.0

Manage the configuration of NTP peers and servers on the network devices through the NAPALM proxy.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- Requires netaddr_ to be installed: `pip install netaddr` to check if IP
  Addresses are correctly specified
- Requires dnspython_ to be installed: `pip install dnspython` to resolve the
  nameserver entities (in case the user does not configure the peers/servers
  using their IP addresses)
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`
- :mod:`NTP operational and configuration management module <salt.modules.napalm_ntp>`

.. _netaddr: https://pythonhosted.org/netaddr/
.. _dnspython: http://www.dnspython.org/
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import 3rd-party libs
from salt.ext import six

# import NAPALM utils
import salt.utils.napalm

try:
    from netaddr import IPAddress
    from netaddr.core import AddrFormatError
    HAS_NETADDR = True
except ImportError:
    HAS_NETADDR = False

try:
    import dns.resolver
    HAS_DNSRESOLVER = True
except ImportError:
    HAS_DNSRESOLVER = False

# ----------------------------------------------------------------------------------------------------------------------
# state properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'netntp'

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _default_ret(name):

    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': ''
    }
    return ret


def _retrieve_ntp_peers():

    '''Retrieves configured NTP peers'''

    return __salt__['ntp.peers']()


def _retrieve_ntp_servers():

    '''Retrieves configured NTP servers'''

    return __salt__['ntp.servers']()


def _check(peers):

    '''Checks whether the input is a valid list of peers and transforms domain names into IP Addresses'''

    if not isinstance(peers, list):
        return False

    for peer in peers:
        if not isinstance(peer, six.string_types):
            return False

    if not HAS_NETADDR:  # if does not have this lib installed, will simply try to load what user specified
        # if the addresses are not correctly specified, will trow error when loading the actual config
        return True

    ip_only_peers = []
    for peer in peers:
        try:
            ip_only_peers.append(six.text_type(IPAddress(peer)))  # append the str value
        except AddrFormatError:
            # if not a valid IP Address
            # will try to see if it is a nameserver and resolve it
            if not HAS_DNSRESOLVER:
                continue  # without the dns resolver cannot populate the list of NTP entities based on their nameserver
                # so we'll move on
            dns_reply = []
            try:
                # try to see if it is a valid NS
                dns_reply = dns.resolver.query(peer)
            except dns.resolver.NoAnswer:
                # no a valid DNS entry either
                return False
            for dns_ip in dns_reply:
                ip_only_peers.append(six.text_type(dns_ip))

    peers = ip_only_peers

    return True


def _clean(lst):

    return [elem for elem in lst if elem]


def _set_ntp_peers(peers):

    '''Calls ntp.set_peers.'''

    return __salt__['ntp.set_peers'](*peers, commit=False)


def _set_ntp_servers(servers):

    '''Calls ntp.set_servers.'''

    return __salt__['ntp.set_servers'](*servers, commit=False)


def _delete_ntp_peers(peers):

    '''Calls ntp.delete_peers.'''

    return __salt__['ntp.delete_peers'](*peers, commit=False)


def _delete_ntp_servers(servers):

    '''Calls ntp.delete_servers.'''

    return __salt__['ntp.delete_servers'](*servers, commit=False)


def _exec_fun(name, *kargs):

    if name in list(globals().keys()):
        return globals().get(name)(*kargs)

    return None


def _check_diff_and_configure(fun_name, peers_servers, name='peers'):

    _ret = _default_ret(fun_name)

    _options = ['peers', 'servers']

    if name not in _options:
        return _ret

    _retrieve_fun = '_retrieve_ntp_{what}'.format(what=name)
    ntp_list_output = _exec_fun(_retrieve_fun)  # contains only IP Addresses as dictionary keys

    if ntp_list_output.get('result', False) is False:
        _ret['comment'] = 'Cannot retrieve NTP {what} from the device: {reason}'.format(
            what=name,
            reason=ntp_list_output.get('comment')
        )
        return _ret

    configured_ntp_list = set(ntp_list_output.get('out', {}))
    desired_ntp_list = set(peers_servers)

    if configured_ntp_list == desired_ntp_list:
        _ret.update({
            'comment': 'NTP {what} already configured as needed.'.format(
                what=name
            ),
            'result': True
        })
        return _ret

    list_to_set = list(desired_ntp_list - configured_ntp_list)
    list_to_delete = list(configured_ntp_list - desired_ntp_list)

    list_to_set = _clean(list_to_set)
    list_to_delete = _clean(list_to_delete)

    changes = {}
    if list_to_set:
        changes['added'] = list_to_set
    if list_to_delete:
        changes['removed'] = list_to_delete

    _ret.update({
        'changes': changes
    })

    if __opts__['test'] is True:
        _ret.update({
            'result': None,
            'comment': 'Testing mode: configuration was not changed!'
        })
        return _ret

    # <---- Retrieve existing NTP peers and determine peers to be added/removed --------------------------------------->

    # ----- Call _set_ntp_peers and _delete_ntp_peers as needed ------------------------------------------------------->

    expected_config_change = False
    successfully_changed = True

    comment = ''

    if list_to_set:
        _set_fun = '_set_ntp_{what}'.format(what=name)
        _set = _exec_fun(_set_fun, list_to_set)
        if _set.get('result'):
            expected_config_change = True
        else:  # something went wrong...
            successfully_changed = False
            comment += 'Cannot set NTP {what}: {reason}'.format(
                what=name,
                reason=_set.get('comment')
            )

    if list_to_delete:
        _delete_fun = '_delete_ntp_{what}'.format(what=name)
        _removed = _exec_fun(_delete_fun, list_to_delete)
        if _removed.get('result'):
            expected_config_change = True
        else:  # something went wrong...
            successfully_changed = False
            comment += 'Cannot remove NTP {what}: {reason}'.format(
                what=name,
                reason=_removed.get('comment')
            )

    _ret.update({
        'successfully_changed': successfully_changed,
        'expected_config_change': expected_config_change,
        'comment': comment
    })

    return _ret


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def managed(name, peers=None, servers=None):

    '''
    Manages the configuration of NTP peers and servers on the device, as specified in the state SLS file.
    NTP entities not specified in these lists will be removed whilst entities not configured on the device will be set.

    SLS Example:

    .. code-block:: yaml

        netntp_example:
            netntp.managed:
                 - peers:
                    - 192.168.0.1
                    - 172.17.17.1
                 - servers:
                    - 24.124.0.251
                    - 138.236.128.36

    Output example:

    .. code-block:: python

        {
            'edge01.nrt04': {
                'netntp_|-netntp_example_|-netntp_example_|-managed': {
                    'comment': 'NTP servers already configured as needed.',
                    'name': 'netntp_example',
                    'start_time': '12:45:24.056659',
                    'duration': 2938.857,
                    'changes': {
                        'peers': {
                            'removed': [
                                '192.168.0.2',
                                '192.168.0.3'
                            ],
                            'added': [
                                '192.168.0.1',
                                '172.17.17.1'
                            ]
                        }
                    },
                    'result': None
                }
            }
        }
    '''

    ret = _default_ret(name)
    result = ret.get('result', False)
    comment = ret.get('comment', '')
    changes = ret.get('changes', {})

    if not(isinstance(peers, list) or isinstance(servers, list)):  # none of the is a list
        return ret  # just exit

    if isinstance(peers, list) and not _check(peers):  # check and clean peers
        ret['comment'] = 'NTP peers must be a list of valid IP Addresses or Domain Names'
        return ret

    if isinstance(servers, list) and not _check(servers):  # check and clean servers
        ret['comment'] = 'NTP servers must be a list of valid IP Addresses or Domain Names'
        return ret

    # ----- Retrieve existing NTP peers and determine peers to be added/removed --------------------------------------->

    successfully_changed = True
    expected_config_change = False

    if isinstance(peers, list):
        _peers_ret = _check_diff_and_configure(name, peers, name='peers')
        expected_config_change = _peers_ret.get('expected_config_change', False)
        successfully_changed = _peers_ret.get('successfully_changed', True)
        result = result and _peers_ret.get('result', False)
        comment += ('\n' + _peers_ret.get('comment', ''))
        _changed_peers = _peers_ret.get('changes', {})
        if _changed_peers:
            changes['peers'] = _changed_peers
    if isinstance(servers, list):
        _servers_ret = _check_diff_and_configure(name, servers, name='servers')
        expected_config_change = expected_config_change or _servers_ret.get('expected_config_change', False)
        successfully_changed = successfully_changed and _servers_ret.get('successfully_changed', True)
        result = result and _servers_ret.get('result', False)
        comment += ('\n' + _servers_ret.get('comment', ''))
        _changed_servers = _servers_ret.get('changes', {})
        if _changed_servers:
            changes['servers'] = _changed_servers

    ret.update({
        'changes': changes
    })

    if not (changes or expected_config_change):
        ret.update({
            'result': True,
            'comment': 'Device configured properly.'
        })
        return ret

    if __opts__['test'] is True:
        ret.update({
            'result': None,
            'comment': 'This is in testing mode, the device configuration was not changed!'
        })
        return ret

    # <---- Call _set_ntp_peers and _delete_ntp_peers as needed --------------------------------------------------------

    # ----- Try to commit changes ------------------------------------------------------------------------------------->

    if expected_config_change:  # commit only in case there's something to update
        config_result, config_comment = __salt__['net.config_control']()
        result = config_result and successfully_changed
        comment += config_comment

    # <---- Try to commit changes --------------------------------------------------------------------------------------

    ret.update({
        'result': result,
        'comment': comment
    })

    return ret
