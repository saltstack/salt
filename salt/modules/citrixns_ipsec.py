# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the ipsec key.

:codeauthor: :email:`Spencer Ervin <spencer_ervin@hotmail.com>`
:maturity:   new
:depends:    none
:platform:   unix


Configuration
=============
This module accepts connection configuration details either as
parameters, or as configuration settings in pillar as a Salt proxy.
Options passed into opts will be ignored if options are passed into pillar.

.. seealso::
    :prox:`Citrix Netscaler Proxy Module <salt.proxy.citrixns>`

About
=====
This execution module was designed to handle connections to a Citrix Netscaler. This module adds support to send
connections directly to the device through the rest API.

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils.platform
import salt.proxy.citrixns

log = logging.getLogger(__name__)

__virtualname__ = 'ipsec'


def __virtual__():
    '''
    Will load for the citrixns proxy minions.
    '''
    try:
        if salt.utils.platform.is_proxy() and \
           __opts__['proxy']['proxytype'] == 'citrixns':
            return __virtualname__
    except KeyError:
        pass

    return False, 'The ipsec execution module can only be loaded for citrixns proxy minions.'


def add_ipsecprofile(name=None, ikeversion=None, encalgo=None, hashalgo=None, lifetime=None, psk=None, publickey=None,
                     privatekey=None, peerpublickey=None, livenesscheckinterval=None, replaywindowsize=None,
                     ikeretryinterval=None, retransmissiontime=None, perfectforwardsecrecy=None, save=False):
    '''
    Add a new ipsecprofile to the running configuration.

    name(str): The name of the ipsec profile. Minimum length = 1 Maximum length = 32

    ikeversion(str): IKE Protocol Version. Possible values = V1, V2

    encalgo(list(str)): Type of encryption algorithm. Possible values = AES, 3DES

    hashalgo(list(str)): Type of hashing algorithm. Possible values = HMAC_SHA1, HMAC_SHA256, HMAC_SHA384, HMAC_SHA512,
        HMAC_MD5

    lifetime(int): Lifetime of IKE SA in seconds. Lifetime of IPSec SA will be (lifetime of IKE SA/8). Minimum value = 480
        Maximum value = 31536000

    psk(str): Pre shared key value.

    publickey(str): Public key file path.

    privatekey(str): Private key file path.

    peerpublickey(str): Peer public key file path.

    livenesscheckinterval(int): Number of seconds after which a notify payload is sent to check the liveliness of the peer.
        Additional retries are done as per retransmit interval setting. Zero value disables liveliness checks. Minimum
        value = 0 Maximum value = 64999

    replaywindowsize(int): IPSec Replay window size for the data traffic. Minimum value = 0 Maximum value = 16384

    ikeretryinterval(int): IKE retry interval for bringing up the connection. Minimum value = 60 Maximum value = 3600

    retransmissiontime(int): The interval in seconds to retry sending the IKE messages to peer, three consecutive attempts
        are done with doubled interval after every failure. Minimum value = 1 Maximum value = 99

    perfectforwardsecrecy(str): Enable/Disable PFS. Possible values = ENABLE, DISABLE

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsec.add_ipsecprofile <args>

    '''

    result = {}

    payload = {'ipsecprofile': {}}

    if name:
        payload['ipsecprofile']['name'] = name

    if ikeversion:
        payload['ipsecprofile']['ikeversion'] = ikeversion

    if encalgo:
        payload['ipsecprofile']['encalgo'] = encalgo

    if hashalgo:
        payload['ipsecprofile']['hashalgo'] = hashalgo

    if lifetime:
        payload['ipsecprofile']['lifetime'] = lifetime

    if psk:
        payload['ipsecprofile']['psk'] = psk

    if publickey:
        payload['ipsecprofile']['publickey'] = publickey

    if privatekey:
        payload['ipsecprofile']['privatekey'] = privatekey

    if peerpublickey:
        payload['ipsecprofile']['peerpublickey'] = peerpublickey

    if livenesscheckinterval:
        payload['ipsecprofile']['livenesscheckinterval'] = livenesscheckinterval

    if replaywindowsize:
        payload['ipsecprofile']['replaywindowsize'] = replaywindowsize

    if ikeretryinterval:
        payload['ipsecprofile']['ikeretryinterval'] = ikeretryinterval

    if retransmissiontime:
        payload['ipsecprofile']['retransmissiontime'] = retransmissiontime

    if perfectforwardsecrecy:
        payload['ipsecprofile']['perfectforwardsecrecy'] = perfectforwardsecrecy

    execution = __proxy__['citrixns.post']('config/ipsecprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_ipsecparameter():
    '''
    Show the running configuration for the ipsecparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsec.get_ipsecparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipsecparameter'), 'ipsecparameter')

    return response


def get_ipsecprofile(name=None, ikeversion=None, encalgo=None, hashalgo=None, lifetime=None, psk=None, publickey=None,
                     privatekey=None, peerpublickey=None, livenesscheckinterval=None, replaywindowsize=None,
                     ikeretryinterval=None, retransmissiontime=None, perfectforwardsecrecy=None):
    '''
    Show the running configuration for the ipsecprofile config key.

    name(str): Filters results that only match the name field.

    ikeversion(str): Filters results that only match the ikeversion field.

    encalgo(list(str)): Filters results that only match the encalgo field.

    hashalgo(list(str)): Filters results that only match the hashalgo field.

    lifetime(int): Filters results that only match the lifetime field.

    psk(str): Filters results that only match the psk field.

    publickey(str): Filters results that only match the publickey field.

    privatekey(str): Filters results that only match the privatekey field.

    peerpublickey(str): Filters results that only match the peerpublickey field.

    livenesscheckinterval(int): Filters results that only match the livenesscheckinterval field.

    replaywindowsize(int): Filters results that only match the replaywindowsize field.

    ikeretryinterval(int): Filters results that only match the ikeretryinterval field.

    retransmissiontime(int): Filters results that only match the retransmissiontime field.

    perfectforwardsecrecy(str): Filters results that only match the perfectforwardsecrecy field.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsec.get_ipsecprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ikeversion:
        search_filter.append(['ikeversion', ikeversion])

    if encalgo:
        search_filter.append(['encalgo', encalgo])

    if hashalgo:
        search_filter.append(['hashalgo', hashalgo])

    if lifetime:
        search_filter.append(['lifetime', lifetime])

    if psk:
        search_filter.append(['psk', psk])

    if publickey:
        search_filter.append(['publickey', publickey])

    if privatekey:
        search_filter.append(['privatekey', privatekey])

    if peerpublickey:
        search_filter.append(['peerpublickey', peerpublickey])

    if livenesscheckinterval:
        search_filter.append(['livenesscheckinterval', livenesscheckinterval])

    if replaywindowsize:
        search_filter.append(['replaywindowsize', replaywindowsize])

    if ikeretryinterval:
        search_filter.append(['ikeretryinterval', ikeretryinterval])

    if retransmissiontime:
        search_filter.append(['retransmissiontime', retransmissiontime])

    if perfectforwardsecrecy:
        search_filter.append(['perfectforwardsecrecy', perfectforwardsecrecy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipsecprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ipsecprofile')

    return response


def unset_ipsecparameter(ikeversion=None, encalgo=None, hashalgo=None, lifetime=None, livenesscheckinterval=None,
                         replaywindowsize=None, ikeretryinterval=None, perfectforwardsecrecy=None,
                         retransmissiontime=None, save=False):
    '''
    Unsets values from the ipsecparameter configuration key.

    ikeversion(bool): Unsets the ikeversion value.

    encalgo(bool): Unsets the encalgo value.

    hashalgo(bool): Unsets the hashalgo value.

    lifetime(bool): Unsets the lifetime value.

    livenesscheckinterval(bool): Unsets the livenesscheckinterval value.

    replaywindowsize(bool): Unsets the replaywindowsize value.

    ikeretryinterval(bool): Unsets the ikeretryinterval value.

    perfectforwardsecrecy(bool): Unsets the perfectforwardsecrecy value.

    retransmissiontime(bool): Unsets the retransmissiontime value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsec.unset_ipsecparameter <args>

    '''

    result = {}

    payload = {'ipsecparameter': {}}

    if ikeversion:
        payload['ipsecparameter']['ikeversion'] = True

    if encalgo:
        payload['ipsecparameter']['encalgo'] = True

    if hashalgo:
        payload['ipsecparameter']['hashalgo'] = True

    if lifetime:
        payload['ipsecparameter']['lifetime'] = True

    if livenesscheckinterval:
        payload['ipsecparameter']['livenesscheckinterval'] = True

    if replaywindowsize:
        payload['ipsecparameter']['replaywindowsize'] = True

    if ikeretryinterval:
        payload['ipsecparameter']['ikeretryinterval'] = True

    if perfectforwardsecrecy:
        payload['ipsecparameter']['perfectforwardsecrecy'] = True

    if retransmissiontime:
        payload['ipsecparameter']['retransmissiontime'] = True

    execution = __proxy__['citrixns.post']('config/ipsecparameter?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_ipsecparameter(ikeversion=None, encalgo=None, hashalgo=None, lifetime=None, livenesscheckinterval=None,
                          replaywindowsize=None, ikeretryinterval=None, perfectforwardsecrecy=None,
                          retransmissiontime=None, save=False):
    '''
    Update the running configuration for the ipsecparameter config key.

    ikeversion(str): IKE Protocol Version. Default value: V2 Possible values = V1, V2

    encalgo(list(str)): Type of encryption algorithm. Default value: AES Possible values = AES, 3DES

    hashalgo(list(str)): Type of hashing algorithm. Default value: HMAC_SHA256 Possible values = HMAC_SHA1, HMAC_SHA256,
        HMAC_SHA384, HMAC_SHA512, HMAC_MD5

    lifetime(int): Lifetime of IKE SA in seconds. Lifetime of IPSec SA will be (lifetime of IKE SA/8). Minimum value = 480
        Maximum value = 31536000

    livenesscheckinterval(int): Number of seconds after which a notify payload is sent to check the liveliness of the peer.
        Additional retries are done as per retransmit interval setting. Zero value disables liveliness checks. Minimum
        value = 0 Maximum value = 64999

    replaywindowsize(int): IPSec Replay window size for the data traffic. Minimum value = 0 Maximum value = 16384

    ikeretryinterval(int): IKE retry interval for bringing up the connection. Minimum value = 60 Maximum value = 3600

    perfectforwardsecrecy(str): Enable/Disable PFS. Default value: DISABLE Possible values = ENABLE, DISABLE

    retransmissiontime(int): The interval in seconds to retry sending the IKE messages to peer, three consecutive attempts
        are done with doubled interval after every failure, increases for every retransmit till 6 retransmits. Minimum
        value = 1 Maximum value = 99

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsec.update_ipsecparameter <args>

    '''

    result = {}

    payload = {'ipsecparameter': {}}

    if ikeversion:
        payload['ipsecparameter']['ikeversion'] = ikeversion

    if encalgo:
        payload['ipsecparameter']['encalgo'] = encalgo

    if hashalgo:
        payload['ipsecparameter']['hashalgo'] = hashalgo

    if lifetime:
        payload['ipsecparameter']['lifetime'] = lifetime

    if livenesscheckinterval:
        payload['ipsecparameter']['livenesscheckinterval'] = livenesscheckinterval

    if replaywindowsize:
        payload['ipsecparameter']['replaywindowsize'] = replaywindowsize

    if ikeretryinterval:
        payload['ipsecparameter']['ikeretryinterval'] = ikeretryinterval

    if perfectforwardsecrecy:
        payload['ipsecparameter']['perfectforwardsecrecy'] = perfectforwardsecrecy

    if retransmissiontime:
        payload['ipsecparameter']['retransmissiontime'] = retransmissiontime

    execution = __proxy__['citrixns.put']('config/ipsecparameter', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
