# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the cloud key.

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

__virtualname__ = 'cloud'


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

    return False, 'The cloud execution module can only be loaded for citrixns proxy minions.'


def get_cloudparameter():
    '''
    Show the running configuration for the cloudparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' cloud.get_cloudparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cloudparameter'), 'cloudparameter')

    return response


def unset_cloudparameter(controllerfqdn=None, controllerport=None, instanceid=None, customerid=None,
                         resourcelocation=None, verifyurl=None, save=False):
    '''
    Unsets values from the cloudparameter configuration key.

    controllerfqdn(bool): Unsets the controllerfqdn value.

    controllerport(bool): Unsets the controllerport value.

    instanceid(bool): Unsets the instanceid value.

    customerid(bool): Unsets the customerid value.

    resourcelocation(bool): Unsets the resourcelocation value.

    verifyurl(bool): Unsets the verifyurl value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cloud.unset_cloudparameter <args>

    '''

    result = {}

    payload = {'cloudparameter': {}}

    if controllerfqdn:
        payload['cloudparameter']['controllerfqdn'] = True

    if controllerport:
        payload['cloudparameter']['controllerport'] = True

    if instanceid:
        payload['cloudparameter']['instanceid'] = True

    if customerid:
        payload['cloudparameter']['customerid'] = True

    if resourcelocation:
        payload['cloudparameter']['resourcelocation'] = True

    if verifyurl:
        payload['cloudparameter']['verifyurl'] = True

    execution = __proxy__['citrixns.post']('config/cloudparameter?action=unset', payload)

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


def update_cloudparameter(controllerfqdn=None, controllerport=None, instanceid=None, customerid=None,
                          resourcelocation=None, verifyurl=None, save=False):
    '''
    Update the running configuration for the cloudparameter config key.

    controllerfqdn(str): FQDN of the controller to which the Netscaler SDProxy Connects. Minimum length = 1

    controllerport(int): Port number of the controller to which the Netscaler SDProxy connects. Minimum value = 1 Range 1 -
        65535 * in CLI is represented as 65535 in NITRO API

    instanceid(str): Instance ID of the customer provided by Trust. Minimum length = 1

    customerid(str): Customer ID of the citrix cloud customer. Minimum length = 1

    resourcelocation(str): Resource Location of the customer provided by Trust. Minimum length = 1

    verifyurl(str): Verify url will be fetched from the trust service and consumed by GUI to login to the cloud.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cloud.update_cloudparameter <args>

    '''

    result = {}

    payload = {'cloudparameter': {}}

    if controllerfqdn:
        payload['cloudparameter']['controllerfqdn'] = controllerfqdn

    if controllerport:
        payload['cloudparameter']['controllerport'] = controllerport

    if instanceid:
        payload['cloudparameter']['instanceid'] = instanceid

    if customerid:
        payload['cloudparameter']['customerid'] = customerid

    if resourcelocation:
        payload['cloudparameter']['resourcelocation'] = resourcelocation

    if verifyurl:
        payload['cloudparameter']['verifyurl'] = verifyurl

    execution = __proxy__['citrixns.put']('config/cloudparameter', payload)

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
