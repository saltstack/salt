# -*- coding: utf-8 -*-
'''
Network NTP
===============

Configure NTP peers on the device via a salt proxy.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   linux

Dependencies
------------

- :doc:`napalm ntp management module (salt.modules.napalm_ntp) </ref/modules/all/salt.modules.napalm_ntp>`

.. versionadded: Carbon
'''

from __future__ import absolute_import

import logging
log = logging.getLogger(__name__)

# std lib
from netaddr import IPAddress
from netaddr.core import AddrFormatError

# third party libs
import dns.resolver

# ----------------------------------------------------------------------------------------------------------------------
# state properties
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    return 'netntp'

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _retrieve_ntp_peers():

    '''Retrieves configured NTP peers'''

    return __salt__['ntp.peers']()


def _check_peers(peers):

    '''Checks whether the input is a valid list of peers and transforms domain names into IP Addresses'''

    if not isinstance(peers, list):
        return False

    for peer in peers:
        if not isinstance(peer, str):
            return False

    ip_only_peers = list()
    for peer in peers:
        try:
            ip_only_peers.append(str(IPAddress(peer)))  # append the str value
        except AddrFormatError:
            # if not a valid IP Address
            dns_reply = list()
            try:
                # try to see if it is a valid NS
                dns_reply = dns.resolver.query(peer)
            except dns.resolver.NoAnswer:
                # no a valid DNS entry either
                continue
            for dns_ip in dns_reply:
                ip_only_peers.append(str(dns_ip))

    peers = ip_only_peers

    return True


def _set_ntp_peers(peers):

    '''Calls ntp.set_peers.'''

    return __salt__['ntp.set_peers'](*peers)


def _delete_ntp_peers(peers):

    '''Calls ntp.delete_peers.'''

    return __salt__['ntp.delete_peers'](*peers)

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def managed(name, peers=None):

    '''
    Updates the list of NTP peers on the devices as speified in the state SLS file.
    NTP peers not specified in this list will be removed and peers that are not configured will be set.


    SLS Example:

    .. code-block:: yaml

        netntp_example:
            netntp.managed:
                 - peers:
                    - 192.168.0.1
                    - 172.17.17.1
    '''

    result = False
    comment = ''
    changes = dict()

    ret = {
        'name': name,
        'changes': changes,
        'result': result,
        'comment': comment
    }

    if not _check_peers(peers):  # check and clean
        ret['comment'] = 'NTP peers must be a list of valid IP Addresses or Domain Names'
        return ret

    # ----- Retrieve existing NTP peers and determine peers to be added/removed --------------------------------------->

    ntp_peers_output = _retrieve_ntp_peers()  # contains only IP Addresses as dictionary keys

    if not ntp_peers_output.get('result'):
        ret['comment'] = 'Cannot retrieve NTP peers from the device: {reason}'.format(
            reason=ntp_peers_output.get('comment')
        )
        return ret

    configured_ntp_peers = set(ntp_peers_output.get('out', {}))
    desired_ntp_peers = set(peers)

    if configured_ntp_peers == desired_ntp_peers:
        ret.update({
            'comment': 'NTP peers already configured as needed.',
            'result': True
        })
        if __opts__['test'] is True:
            ret.update({
                'result': None
            })
        return ret

    peers_to_set = list(desired_ntp_peers - configured_ntp_peers)
    peers_to_delete = list(configured_ntp_peers - desired_ntp_peers)

    changes = {
        'added': peers_to_set,
        'removed': peers_to_delete
    }

    ret.update({
        'changes': changes
    })

    if __opts__['test'] is True:
        ret.update({
            'result': None,
            'comment': 'Testing mode: the device configuration was not changed!'
        })
        return ret

    # <---- Retrieve existing NTP peers and determine peers to be added/removed --------------------------------------->

    # ----- Call _set_ntp_peers and _delete_ntp_peers as needed ------------------------------------------------------->

    expected_config_change = False
    successfully_changed = True

    if peers_to_set:
        _set = _set_ntp_peers(peers_to_set)
        if _set.get('result'):
            expected_config_change = True
        else:  # something went wrong...
            successfully_changed = False
            comment += 'Cannot set NTP peers: {reason}'.format(
                reason=_set.get('comment')
            )

    if peers_to_delete:
        _removed = _delete_ntp_peers(peers_to_delete)
        if _removed.get('result'):
            expected_config_change = True
        else:  # something went wrong...
            successfully_changed = False
            comment += 'Cannot remove NTP peers: {reason}'.format(
                reason=_removed.get('comment')
            )

    # <---- Call _set_ntp_peers and _delete_ntp_peers as needed --------------------------------------------------------

    # ----- Try to commit changes ------------------------------------------------------------------------------------->

    if expected_config_change:
        config_result, config_comment = __salt__['net.config_control']()
        result = config_result and successfully_changed  # both must
        comment += config_comment

    # <---- Try to commit changes --------------------------------------------------------------------------------------

    ret.update({
        'result': result,
        'comment': comment
    })

    return ret
