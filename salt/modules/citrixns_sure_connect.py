# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the sure-connect key.

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

__virtualname__ = 'sure_connect'


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

    return False, 'The sure_connect execution module can only be loaded for citrixns proxy minions.'


def add_scpolicy(name=None, url=None, rule=None, delay=None, maxconn=None, action=None, altcontentsvcname=None,
                 altcontentpath=None, save=False):
    '''
    Add a new scpolicy to the running configuration.

    name(str): Name for the policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Minimum length = 1 Maximum length = 31

    url(str): URL against which to match incoming client request. Maximum length = 127

    rule(str): Expression against which the traffic is evaluated.  Maximum length of a string literal in the expression is
        255 characters. A longer string can be split into smaller strings of up to 255 characters each, and the smaller
        strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements apply only to
        the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression in double
        quotation marks. * If the expression itself includes double quotation marks, escape the quotations by using the
        character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks. Maximum length = 1499

    delay(int): Delay threshold, in microseconds, for requests that match the policys URL or rule. If the delay statistics
        gathered for the matching request exceed the specified delay, SureConnect is triggered for that request. Minimum
        value = 1 Maximum value = 599999999

    maxconn(int): Maximum number of concurrent connections that can be open for requests that match the policys URL or rule.
        Minimum value = 1 Maximum value = 4294967294

    action(str): Action to be taken when the delay or maximum-connections threshold is reached. Available settings function
        as follows: ACS - Serve content from an alternative content service. NS - Serve alternative content from the
        NetScaler appliance. NO ACTION - Serve no alternative content. However, delay statistics are still collected for
        the configured URLs, and, if the Maximum Client Connections parameter is set, the number of connections is
        limited to the value specified by that parameter. (However, alternative content is not served even if the maxConn
        threshold is met). Possible values = ACS, NS, NOACTION

    altcontentsvcname(str): Name of the alternative content service to be used in the ACS action. Minimum length = 1 Maximum
        length = 127

    altcontentpath(str): Path to the alternative content service to be used in the ACS action. Minimum length = 1 Maximum
        length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' sure_connect.add_scpolicy <args>

    '''

    result = {}

    payload = {'scpolicy': {}}

    if name:
        payload['scpolicy']['name'] = name

    if url:
        payload['scpolicy']['url'] = url

    if rule:
        payload['scpolicy']['rule'] = rule

    if delay:
        payload['scpolicy']['delay'] = delay

    if maxconn:
        payload['scpolicy']['maxconn'] = maxconn

    if action:
        payload['scpolicy']['action'] = action

    if altcontentsvcname:
        payload['scpolicy']['altcontentsvcname'] = altcontentsvcname

    if altcontentpath:
        payload['scpolicy']['altcontentpath'] = altcontentpath

    execution = __proxy__['citrixns.post']('config/scpolicy', payload)

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


def get_scparameter():
    '''
    Show the running configuration for the scparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' sure_connect.get_scparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/scparameter'), 'scparameter')

    return response


def get_scpolicy(name=None, url=None, rule=None, delay=None, maxconn=None, action=None, altcontentsvcname=None,
                 altcontentpath=None):
    '''
    Show the running configuration for the scpolicy config key.

    name(str): Filters results that only match the name field.

    url(str): Filters results that only match the url field.

    rule(str): Filters results that only match the rule field.

    delay(int): Filters results that only match the delay field.

    maxconn(int): Filters results that only match the maxconn field.

    action(str): Filters results that only match the action field.

    altcontentsvcname(str): Filters results that only match the altcontentsvcname field.

    altcontentpath(str): Filters results that only match the altcontentpath field.

    CLI Example:

    .. code-block:: bash

    salt '*' sure_connect.get_scpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if url:
        search_filter.append(['url', url])

    if rule:
        search_filter.append(['rule', rule])

    if delay:
        search_filter.append(['delay', delay])

    if maxconn:
        search_filter.append(['maxconn', maxconn])

    if action:
        search_filter.append(['action', action])

    if altcontentsvcname:
        search_filter.append(['altcontentsvcname', altcontentsvcname])

    if altcontentpath:
        search_filter.append(['altcontentpath', altcontentpath])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/scpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'scpolicy')

    return response


def unset_scparameter(sessionlife=None, vsr=None, save=False):
    '''
    Unsets values from the scparameter configuration key.

    sessionlife(bool): Unsets the sessionlife value.

    vsr(bool): Unsets the vsr value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' sure_connect.unset_scparameter <args>

    '''

    result = {}

    payload = {'scparameter': {}}

    if sessionlife:
        payload['scparameter']['sessionlife'] = True

    if vsr:
        payload['scparameter']['vsr'] = True

    execution = __proxy__['citrixns.post']('config/scparameter?action=unset', payload)

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


def unset_scpolicy(name=None, url=None, rule=None, delay=None, maxconn=None, action=None, altcontentsvcname=None,
                   altcontentpath=None, save=False):
    '''
    Unsets values from the scpolicy configuration key.

    name(bool): Unsets the name value.

    url(bool): Unsets the url value.

    rule(bool): Unsets the rule value.

    delay(bool): Unsets the delay value.

    maxconn(bool): Unsets the maxconn value.

    action(bool): Unsets the action value.

    altcontentsvcname(bool): Unsets the altcontentsvcname value.

    altcontentpath(bool): Unsets the altcontentpath value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' sure_connect.unset_scpolicy <args>

    '''

    result = {}

    payload = {'scpolicy': {}}

    if name:
        payload['scpolicy']['name'] = True

    if url:
        payload['scpolicy']['url'] = True

    if rule:
        payload['scpolicy']['rule'] = True

    if delay:
        payload['scpolicy']['delay'] = True

    if maxconn:
        payload['scpolicy']['maxconn'] = True

    if action:
        payload['scpolicy']['action'] = True

    if altcontentsvcname:
        payload['scpolicy']['altcontentsvcname'] = True

    if altcontentpath:
        payload['scpolicy']['altcontentpath'] = True

    execution = __proxy__['citrixns.post']('config/scpolicy?action=unset', payload)

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


def update_scparameter(sessionlife=None, vsr=None, save=False):
    '''
    Update the running configuration for the scparameter config key.

    sessionlife(int): Time, in seconds, between the first time and the next time the SureConnect alternative content window
        is displayed. The alternative content window is displayed only once during a session for the same browser
        accessing a configured URL, so this parameter determines the length of a session. Default value: 300 Minimum
        value = 1 Maximum value = 4294967294

    vsr(str): File containing the customized response to be displayed when the ACTION in the SureConnect policy is set to NS.
        Default value: "DEFAULT" Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' sure_connect.update_scparameter <args>

    '''

    result = {}

    payload = {'scparameter': {}}

    if sessionlife:
        payload['scparameter']['sessionlife'] = sessionlife

    if vsr:
        payload['scparameter']['vsr'] = vsr

    execution = __proxy__['citrixns.put']('config/scparameter', payload)

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


def update_scpolicy(name=None, url=None, rule=None, delay=None, maxconn=None, action=None, altcontentsvcname=None,
                    altcontentpath=None, save=False):
    '''
    Update the running configuration for the scpolicy config key.

    name(str): Name for the policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Minimum length = 1 Maximum length = 31

    url(str): URL against which to match incoming client request. Maximum length = 127

    rule(str): Expression against which the traffic is evaluated.  Maximum length of a string literal in the expression is
        255 characters. A longer string can be split into smaller strings of up to 255 characters each, and the smaller
        strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements apply only to
        the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression in double
        quotation marks. * If the expression itself includes double quotation marks, escape the quotations by using the
        character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks. Maximum length = 1499

    delay(int): Delay threshold, in microseconds, for requests that match the policys URL or rule. If the delay statistics
        gathered for the matching request exceed the specified delay, SureConnect is triggered for that request. Minimum
        value = 1 Maximum value = 599999999

    maxconn(int): Maximum number of concurrent connections that can be open for requests that match the policys URL or rule.
        Minimum value = 1 Maximum value = 4294967294

    action(str): Action to be taken when the delay or maximum-connections threshold is reached. Available settings function
        as follows: ACS - Serve content from an alternative content service. NS - Serve alternative content from the
        NetScaler appliance. NO ACTION - Serve no alternative content. However, delay statistics are still collected for
        the configured URLs, and, if the Maximum Client Connections parameter is set, the number of connections is
        limited to the value specified by that parameter. (However, alternative content is not served even if the maxConn
        threshold is met). Possible values = ACS, NS, NOACTION

    altcontentsvcname(str): Name of the alternative content service to be used in the ACS action. Minimum length = 1 Maximum
        length = 127

    altcontentpath(str): Path to the alternative content service to be used in the ACS action. Minimum length = 1 Maximum
        length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' sure_connect.update_scpolicy <args>

    '''

    result = {}

    payload = {'scpolicy': {}}

    if name:
        payload['scpolicy']['name'] = name

    if url:
        payload['scpolicy']['url'] = url

    if rule:
        payload['scpolicy']['rule'] = rule

    if delay:
        payload['scpolicy']['delay'] = delay

    if maxconn:
        payload['scpolicy']['maxconn'] = maxconn

    if action:
        payload['scpolicy']['action'] = action

    if altcontentsvcname:
        payload['scpolicy']['altcontentsvcname'] = altcontentsvcname

    if altcontentpath:
        payload['scpolicy']['altcontentpath'] = altcontentpath

    execution = __proxy__['citrixns.put']('config/scpolicy', payload)

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
