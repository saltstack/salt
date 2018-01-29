# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the ssl-vpn key.

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

__virtualname__ = 'ssl_vpn'


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

    return False, 'The ssl_vpn execution module can only be loaded for citrixns proxy minions.'


def add_vpnalwaysonprofile(name=None, networkaccessonvpnfailure=None, clientcontrol=None, locationbasedvpn=None,
                           save=False):
    '''
    Add a new vpnalwaysonprofile to the running configuration.

    name(str): name of AlwaysON profile. Minimum length = 1

    networkaccessonvpnfailure(str): Option to block network traffic when tunnel is not established(and the config requires
        that tunnel be established). When set to onlyToGateway, the network traffic to and from the client (except
        Gateway IP) is blocked. When set to fullAccess, the network traffic is not blocked. Default value: fullAccess,
        Possible values = onlyToGateway, fullAccess

    clientcontrol(str): Allow/Deny user to log off and connect to another Gateway. Default value: DENY Possible values =
        ALLOW, DENY

    locationbasedvpn(str): Option to decide if tunnel should be established when in enterprise network. When locationBasedVPN
        is remote, client tries to detect if it is located in enterprise network or not and establishes the tunnel if not
        in enterprise network. Dns suffixes configured using -add dns suffix- are used to decide if the client is in the
        enterprise network or not. If the resolution of the DNS suffix results in private IP, client is said to be in
        enterprise network. When set to EveryWhere, the client skips the check to detect if it is on the enterprise
        network and tries to establish the tunnel. Default value: Remote Possible values = Remote, Everywhere

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnalwaysonprofile <args>

    '''

    result = {}

    payload = {'vpnalwaysonprofile': {}}

    if name:
        payload['vpnalwaysonprofile']['name'] = name

    if networkaccessonvpnfailure:
        payload['vpnalwaysonprofile']['networkaccessonvpnfailure'] = networkaccessonvpnfailure

    if clientcontrol:
        payload['vpnalwaysonprofile']['clientcontrol'] = clientcontrol

    if locationbasedvpn:
        payload['vpnalwaysonprofile']['locationbasedvpn'] = locationbasedvpn

    execution = __proxy__['citrixns.post']('config/vpnalwaysonprofile', payload)

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


def add_vpnclientlessaccesspolicy(name=None, rule=None, profilename=None, save=False):
    '''
    Add a new vpnclientlessaccesspolicy to the running configuration.

    name(str): Name of the new clientless access policy. Minimum length = 1

    rule(str): Expression, or name of a named expression, specifying the traffic that matches the policy. Can be written in
        either default or classic syntax.  Maximum length of a string literal in the expression is 255 characters. A
        longer string can be split into smaller strings of up to 255 characters each, and the smaller strings
        concatenated with the + operator. For example, you can create a 500-character string as follows: ";lt;string of
        255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler
        CLI: * If the expression includes one or more spaces, enclose the entire expression in double quotation marks. *
        If the expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    profilename(str): Name of the profile to invoke for the clientless access.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnclientlessaccesspolicy <args>

    '''

    result = {}

    payload = {'vpnclientlessaccesspolicy': {}}

    if name:
        payload['vpnclientlessaccesspolicy']['name'] = name

    if rule:
        payload['vpnclientlessaccesspolicy']['rule'] = rule

    if profilename:
        payload['vpnclientlessaccesspolicy']['profilename'] = profilename

    execution = __proxy__['citrixns.post']('config/vpnclientlessaccesspolicy', payload)

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


def add_vpnclientlessaccessprofile(profilename=None, urlrewritepolicylabel=None, javascriptrewritepolicylabel=None,
                                   reqhdrrewritepolicylabel=None, reshdrrewritepolicylabel=None,
                                   regexforfindingurlinjavascript=None, regexforfindingurlincss=None,
                                   regexforfindingurlinxcomponent=None, regexforfindingurlinxml=None,
                                   regexforfindingcustomurls=None, clientconsumedcookies=None,
                                   requirepersistentcookie=None, save=False):
    '''
    Add a new vpnclientlessaccessprofile to the running configuration.

    profilename(str): Name for the NetScaler Gateway clientless access profile. Must begin with an ASCII alphabetic or
        underscore (_) character, and must consist only of ASCII alphanumeric, underscore, hash (#), period (.), space,
        colon (:), at (@), equals (=), and hyphen (-) characters. Cannot be changed after the profile is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my profile" or my profile). Minimum length = 1

    urlrewritepolicylabel(str): Name of the configured URL rewrite policy label. If you do not specify a policy label name,
        then URLs are not rewritten. Minimum length = 1

    javascriptrewritepolicylabel(str): Name of the configured JavaScript rewrite policy label. If you do not specify a policy
        label name, then JAVA scripts are not rewritten. Minimum length = 1

    reqhdrrewritepolicylabel(str): Name of the configured Request rewrite policy label. If you do not specify a policy label
        name, then requests are not rewritten. Minimum length = 1

    reshdrrewritepolicylabel(str): Name of the configured Response rewrite policy label. Minimum length = 1

    regexforfindingurlinjavascript(str): Name of the pattern set that contains the regular expressions, which match the URL
        in Java script. Minimum length = 1

    regexforfindingurlincss(str): Name of the pattern set that contains the regular expressions, which match the URL in the
        CSS. Minimum length = 1

    regexforfindingurlinxcomponent(str): Name of the pattern set that contains the regular expressions, which match the URL
        in X Component. Minimum length = 1

    regexforfindingurlinxml(str): Name of the pattern set that contains the regular expressions, which match the URL in XML.
        Minimum length = 1

    regexforfindingcustomurls(str): Name of the pattern set that contains the regular expressions, which match the URLs in
        the custom content type other than HTML, CSS, XML, XCOMP, and JavaScript. The custom content type should be
        included in the patset ns_cvpn_custom_content_types. Minimum length = 1

    clientconsumedcookies(str): Specify the name of the pattern set containing the names of the cookies, which are allowed
        between the client and the server. If a pattern set is not specified, NetSCaler Gateway does not allow any
        cookies between the client and the server. A cookie that is not specified in the pattern set is handled by
        NetScaler Gateway on behalf of the client. Minimum length = 1

    requirepersistentcookie(str): Specify whether a persistent session cookie is set and accepted for clientless access. If
        this parameter is set to ON, COM objects, such as MSOffice, which are invoked by the browser can access the files
        using clientless access. Use caution because the persistent cookie is stored on the disk. Default value: OFF
        Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnclientlessaccessprofile <args>

    '''

    result = {}

    payload = {'vpnclientlessaccessprofile': {}}

    if profilename:
        payload['vpnclientlessaccessprofile']['profilename'] = profilename

    if urlrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['urlrewritepolicylabel'] = urlrewritepolicylabel

    if javascriptrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['javascriptrewritepolicylabel'] = javascriptrewritepolicylabel

    if reqhdrrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['reqhdrrewritepolicylabel'] = reqhdrrewritepolicylabel

    if reshdrrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['reshdrrewritepolicylabel'] = reshdrrewritepolicylabel

    if regexforfindingurlinjavascript:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinjavascript'] = regexforfindingurlinjavascript

    if regexforfindingurlincss:
        payload['vpnclientlessaccessprofile']['regexforfindingurlincss'] = regexforfindingurlincss

    if regexforfindingurlinxcomponent:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinxcomponent'] = regexforfindingurlinxcomponent

    if regexforfindingurlinxml:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinxml'] = regexforfindingurlinxml

    if regexforfindingcustomurls:
        payload['vpnclientlessaccessprofile']['regexforfindingcustomurls'] = regexforfindingcustomurls

    if clientconsumedcookies:
        payload['vpnclientlessaccessprofile']['clientconsumedcookies'] = clientconsumedcookies

    if requirepersistentcookie:
        payload['vpnclientlessaccessprofile']['requirepersistentcookie'] = requirepersistentcookie

    execution = __proxy__['citrixns.post']('config/vpnclientlessaccessprofile', payload)

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


def add_vpnepaprofile(name=None, filename=None, data=None, save=False):
    '''
    Add a new vpnepaprofile to the running configuration.

    name(str): name of device profile. Minimum length = 1

    filename(str): filename of the deviceprofile data xml. Minimum length = 1

    data(str): deviceprofile data xml. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnepaprofile <args>

    '''

    result = {}

    payload = {'vpnepaprofile': {}}

    if name:
        payload['vpnepaprofile']['name'] = name

    if filename:
        payload['vpnepaprofile']['filename'] = filename

    if data:
        payload['vpnepaprofile']['data'] = data

    execution = __proxy__['citrixns.post']('config/vpnepaprofile', payload)

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


def add_vpneula(name=None, save=False):
    '''
    Add a new vpneula to the running configuration.

    name(str): Name for the eula. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpneula <args>

    '''

    result = {}

    payload = {'vpneula': {}}

    if name:
        payload['vpneula']['name'] = name

    execution = __proxy__['citrixns.post']('config/vpneula', payload)

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


def add_vpnformssoaction(name=None, actionurl=None, userfield=None, passwdfield=None, ssosuccessrule=None,
                         namevaluepair=None, responsesize=None, nvtype=None, submitmethod=None, save=False):
    '''
    Add a new vpnformssoaction to the running configuration.

    name(str): Name for the form based single sign-on profile. Minimum length = 1

    actionurl(str): Root-relative URL to which the completed form is submitted. Minimum length = 1

    userfield(str): Name of the form field in which the user types in the user ID. Minimum length = 1

    passwdfield(str): Name of the form field in which the user types in the password. Minimum length = 1

    ssosuccessrule(str): Advanced expression that defines the criteria for SSO success. Expression such as checking for
        cookie in the response is a common example.

    namevaluepair(str): Other name-value pair attributes to send to the server, in addition to sending the user name and
        password. Value names are separated by an ampersand (;amp;), such as in name1=value1;amp;name2=value2.

    responsesize(int): Maximum number of bytes to allow in the response size. Specifies the number of bytes in the response
        to be parsed for extracting the forms. Default value: 8096

    nvtype(str): How to process the name-value pair. Available settings function as follows: * STATIC - The
        administrator-configured values are used. * DYNAMIC - The response is parsed, the form is extracted, and then
        submitted. Default value: DYNAMIC Possible values = STATIC, DYNAMIC

    submitmethod(str): HTTP method (GET or POST) used by the single sign-on form to send the logon credentials to the logon
        server. Default value: GET Possible values = GET, POST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnformssoaction <args>

    '''

    result = {}

    payload = {'vpnformssoaction': {}}

    if name:
        payload['vpnformssoaction']['name'] = name

    if actionurl:
        payload['vpnformssoaction']['actionurl'] = actionurl

    if userfield:
        payload['vpnformssoaction']['userfield'] = userfield

    if passwdfield:
        payload['vpnformssoaction']['passwdfield'] = passwdfield

    if ssosuccessrule:
        payload['vpnformssoaction']['ssosuccessrule'] = ssosuccessrule

    if namevaluepair:
        payload['vpnformssoaction']['namevaluepair'] = namevaluepair

    if responsesize:
        payload['vpnformssoaction']['responsesize'] = responsesize

    if nvtype:
        payload['vpnformssoaction']['nvtype'] = nvtype

    if submitmethod:
        payload['vpnformssoaction']['submitmethod'] = submitmethod

    execution = __proxy__['citrixns.post']('config/vpnformssoaction', payload)

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


def add_vpnglobal_appcontroller_binding(gotopriorityexpression=None, appcontroller=None, save=False):
    '''
    Add a new vpnglobal_appcontroller_binding to the running configuration.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    appcontroller(str): Configured App Controller server.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_appcontroller_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_appcontroller_binding': {}}

    if gotopriorityexpression:
        payload['vpnglobal_appcontroller_binding']['gotopriorityexpression'] = gotopriorityexpression

    if appcontroller:
        payload['vpnglobal_appcontroller_binding']['appcontroller'] = appcontroller

    execution = __proxy__['citrixns.post']('config/vpnglobal_appcontroller_binding', payload)

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


def add_vpnglobal_auditnslogpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None, secondary=None,
                                           groupextraction=None, save=False):
    '''
    Add a new vpnglobal_auditnslogpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_auditnslogpolicy_binding': {}}

    if priority:
        payload['vpnglobal_auditnslogpolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_auditnslogpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_auditnslogpolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_auditnslogpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_auditnslogpolicy_binding', payload)

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


def add_vpnglobal_auditsyslogpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None, secondary=None,
                                            groupextraction=None, save=False):
    '''
    Add a new vpnglobal_auditsyslogpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_auditsyslogpolicy_binding': {}}

    if priority:
        payload['vpnglobal_auditsyslogpolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_auditsyslogpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_auditsyslogpolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_auditsyslogpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_auditsyslogpolicy_binding', payload)

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


def add_vpnglobal_authenticationcertpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                   secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_authenticationcertpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_authenticationcertpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_authenticationcertpolicy_binding': {}}

    if priority:
        payload['vpnglobal_authenticationcertpolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_authenticationcertpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_authenticationcertpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_authenticationcertpolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_authenticationcertpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_authenticationcertpolicy_binding', payload)

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


def add_vpnglobal_authenticationldappolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                   secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_authenticationldappolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_authenticationldappolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_authenticationldappolicy_binding': {}}

    if priority:
        payload['vpnglobal_authenticationldappolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_authenticationldappolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_authenticationldappolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_authenticationldappolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_authenticationldappolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_authenticationldappolicy_binding', payload)

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


def add_vpnglobal_authenticationlocalpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                    secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_authenticationlocalpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_authenticationlocalpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_authenticationlocalpolicy_binding': {}}

    if priority:
        payload['vpnglobal_authenticationlocalpolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_authenticationlocalpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_authenticationlocalpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_authenticationlocalpolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_authenticationlocalpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_authenticationlocalpolicy_binding', payload)

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


def add_vpnglobal_authenticationnegotiatepolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                        secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_authenticationnegotiatepolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_authenticationnegotiatepolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_authenticationnegotiatepolicy_binding': {}}

    if priority:
        payload['vpnglobal_authenticationnegotiatepolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_authenticationnegotiatepolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_authenticationnegotiatepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_authenticationnegotiatepolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_authenticationnegotiatepolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_authenticationnegotiatepolicy_binding', payload)

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


def add_vpnglobal_authenticationpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                               secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_authenticationpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_authenticationpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_authenticationpolicy_binding': {}}

    if priority:
        payload['vpnglobal_authenticationpolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_authenticationpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_authenticationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_authenticationpolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_authenticationpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_authenticationpolicy_binding', payload)

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


def add_vpnglobal_authenticationradiuspolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                     secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_authenticationradiuspolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_authenticationradiuspolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_authenticationradiuspolicy_binding': {}}

    if priority:
        payload['vpnglobal_authenticationradiuspolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_authenticationradiuspolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_authenticationradiuspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_authenticationradiuspolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_authenticationradiuspolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_authenticationradiuspolicy_binding', payload)

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


def add_vpnglobal_authenticationsamlpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                   secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_authenticationsamlpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_authenticationsamlpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_authenticationsamlpolicy_binding': {}}

    if priority:
        payload['vpnglobal_authenticationsamlpolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_authenticationsamlpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_authenticationsamlpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_authenticationsamlpolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_authenticationsamlpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_authenticationsamlpolicy_binding', payload)

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


def add_vpnglobal_authenticationtacacspolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                     secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_authenticationtacacspolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_authenticationtacacspolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_authenticationtacacspolicy_binding': {}}

    if priority:
        payload['vpnglobal_authenticationtacacspolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_authenticationtacacspolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_authenticationtacacspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_authenticationtacacspolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_authenticationtacacspolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_authenticationtacacspolicy_binding', payload)

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


def add_vpnglobal_domain_binding(intranetdomain=None, gotopriorityexpression=None, save=False):
    '''
    Add a new vpnglobal_domain_binding to the running configuration.

    intranetdomain(str): The conflicting intranet domain name.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_domain_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_domain_binding': {}}

    if intranetdomain:
        payload['vpnglobal_domain_binding']['intranetdomain'] = intranetdomain

    if gotopriorityexpression:
        payload['vpnglobal_domain_binding']['gotopriorityexpression'] = gotopriorityexpression

    execution = __proxy__['citrixns.post']('config/vpnglobal_domain_binding', payload)

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


def add_vpnglobal_intranetip6_binding(intranetip6=None, gotopriorityexpression=None, numaddr=None, save=False):
    '''
    Add a new vpnglobal_intranetip6_binding to the running configuration.

    intranetip6(str): The intranet ip address or range.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    numaddr(int): The intranet ip address or ranges netmask.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_intranetip6_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_intranetip6_binding': {}}

    if intranetip6:
        payload['vpnglobal_intranetip6_binding']['intranetip6'] = intranetip6

    if gotopriorityexpression:
        payload['vpnglobal_intranetip6_binding']['gotopriorityexpression'] = gotopriorityexpression

    if numaddr:
        payload['vpnglobal_intranetip6_binding']['numaddr'] = numaddr

    execution = __proxy__['citrixns.post']('config/vpnglobal_intranetip6_binding', payload)

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


def add_vpnglobal_intranetip_binding(intranetip=None, gotopriorityexpression=None, netmask=None, save=False):
    '''
    Add a new vpnglobal_intranetip_binding to the running configuration.

    intranetip(str): The intranet ip address or range.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    netmask(str): The intranet ip address or ranges netmask.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_intranetip_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_intranetip_binding': {}}

    if intranetip:
        payload['vpnglobal_intranetip_binding']['intranetip'] = intranetip

    if gotopriorityexpression:
        payload['vpnglobal_intranetip_binding']['gotopriorityexpression'] = gotopriorityexpression

    if netmask:
        payload['vpnglobal_intranetip_binding']['netmask'] = netmask

    execution = __proxy__['citrixns.post']('config/vpnglobal_intranetip_binding', payload)

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


def add_vpnglobal_sharefileserver_binding(gotopriorityexpression=None, sharefile=None, save=False):
    '''
    Add a new vpnglobal_sharefileserver_binding to the running configuration.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    sharefile(str): Configured Sharefile server, in the format IP:PORT / FQDN:PORT.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_sharefileserver_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_sharefileserver_binding': {}}

    if gotopriorityexpression:
        payload['vpnglobal_sharefileserver_binding']['gotopriorityexpression'] = gotopriorityexpression

    if sharefile:
        payload['vpnglobal_sharefileserver_binding']['sharefile'] = sharefile

    execution = __proxy__['citrixns.post']('config/vpnglobal_sharefileserver_binding', payload)

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


def add_vpnglobal_staserver_binding(staserver=None, gotopriorityexpression=None, staaddresstype=None, save=False):
    '''
    Add a new vpnglobal_staserver_binding to the running configuration.

    staserver(str): Configured Secure Ticketing Authority (STA) server.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    staaddresstype(str): Type of the STA server address(ipv4/v6). Possible values = IPV4, IPV6

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_staserver_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_staserver_binding': {}}

    if staserver:
        payload['vpnglobal_staserver_binding']['staserver'] = staserver

    if gotopriorityexpression:
        payload['vpnglobal_staserver_binding']['gotopriorityexpression'] = gotopriorityexpression

    if staaddresstype:
        payload['vpnglobal_staserver_binding']['staaddresstype'] = staaddresstype

    execution = __proxy__['citrixns.post']('config/vpnglobal_staserver_binding', payload)

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


def add_vpnglobal_vpnclientlessaccesspolicy_binding(priority=None, globalbindtype=None, builtin=None, policyname=None,
                                                    gotopriorityexpression=None, secondary=None, ns_type=None,
                                                    groupextraction=None, save=False):
    '''
    Add a new vpnglobal_vpnclientlessaccesspolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    globalbindtype(str): . Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    ns_type(str): Bindpoint to which the policy is bound. Possible values = REQ_OVERRIDE, REQ_DEFAULT, RES_OVERRIDE,
        RES_DEFAULT

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_vpnclientlessaccesspolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_vpnclientlessaccesspolicy_binding': {}}

    if priority:
        payload['vpnglobal_vpnclientlessaccesspolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['vpnglobal_vpnclientlessaccesspolicy_binding']['globalbindtype'] = globalbindtype

    if builtin:
        payload['vpnglobal_vpnclientlessaccesspolicy_binding']['builtin'] = builtin

    if policyname:
        payload['vpnglobal_vpnclientlessaccesspolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_vpnclientlessaccesspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_vpnclientlessaccesspolicy_binding']['secondary'] = secondary

    if ns_type:
        payload['vpnglobal_vpnclientlessaccesspolicy_binding']['type'] = ns_type

    if groupextraction:
        payload['vpnglobal_vpnclientlessaccesspolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_vpnclientlessaccesspolicy_binding', payload)

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


def add_vpnglobal_vpneula_binding(eula=None, gotopriorityexpression=None, save=False):
    '''
    Add a new vpnglobal_vpneula_binding to the running configuration.

    eula(str): Name of the EULA bound to vpnglobal.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_vpneula_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_vpneula_binding': {}}

    if eula:
        payload['vpnglobal_vpneula_binding']['eula'] = eula

    if gotopriorityexpression:
        payload['vpnglobal_vpneula_binding']['gotopriorityexpression'] = gotopriorityexpression

    execution = __proxy__['citrixns.post']('config/vpnglobal_vpneula_binding', payload)

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


def add_vpnglobal_vpnintranetapplication_binding(gotopriorityexpression=None, intranetapplication=None, save=False):
    '''
    Add a new vpnglobal_vpnintranetapplication_binding to the running configuration.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    intranetapplication(str): The intranet vpn application.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_vpnintranetapplication_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_vpnintranetapplication_binding': {}}

    if gotopriorityexpression:
        payload['vpnglobal_vpnintranetapplication_binding']['gotopriorityexpression'] = gotopriorityexpression

    if intranetapplication:
        payload['vpnglobal_vpnintranetapplication_binding']['intranetapplication'] = intranetapplication

    execution = __proxy__['citrixns.post']('config/vpnglobal_vpnintranetapplication_binding', payload)

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


def add_vpnglobal_vpnnexthopserver_binding(gotopriorityexpression=None, nexthopserver=None, save=False):
    '''
    Add a new vpnglobal_vpnnexthopserver_binding to the running configuration.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    nexthopserver(str): The name of the next hop server bound to vpn global.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_vpnnexthopserver_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_vpnnexthopserver_binding': {}}

    if gotopriorityexpression:
        payload['vpnglobal_vpnnexthopserver_binding']['gotopriorityexpression'] = gotopriorityexpression

    if nexthopserver:
        payload['vpnglobal_vpnnexthopserver_binding']['nexthopserver'] = nexthopserver

    execution = __proxy__['citrixns.post']('config/vpnglobal_vpnnexthopserver_binding', payload)

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


def add_vpnglobal_vpnportaltheme_binding(gotopriorityexpression=None, portaltheme=None, save=False):
    '''
    Add a new vpnglobal_vpnportaltheme_binding to the running configuration.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    portaltheme(str): Name of the portal theme bound to vpnglobal.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_vpnportaltheme_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_vpnportaltheme_binding': {}}

    if gotopriorityexpression:
        payload['vpnglobal_vpnportaltheme_binding']['gotopriorityexpression'] = gotopriorityexpression

    if portaltheme:
        payload['vpnglobal_vpnportaltheme_binding']['portaltheme'] = portaltheme

    execution = __proxy__['citrixns.post']('config/vpnglobal_vpnportaltheme_binding', payload)

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


def add_vpnglobal_vpnsessionpolicy_binding(priority=None, builtin=None, policyname=None, gotopriorityexpression=None,
                                           secondary=None, groupextraction=None, save=False):
    '''
    Add a new vpnglobal_vpnsessionpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_vpnsessionpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_vpnsessionpolicy_binding': {}}

    if priority:
        payload['vpnglobal_vpnsessionpolicy_binding']['priority'] = priority

    if builtin:
        payload['vpnglobal_vpnsessionpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['vpnglobal_vpnsessionpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_vpnsessionpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_vpnsessionpolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_vpnsessionpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_vpnsessionpolicy_binding', payload)

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


def add_vpnglobal_vpntrafficpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None, secondary=None,
                                           groupextraction=None, save=False):
    '''
    Add a new vpnglobal_vpntrafficpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Maximum value for default syntax policies is 2147483647 and for classic policies is 64000. Minimum value = 0
        Maximum value = 2147483647

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    secondary(bool): Bind the authentication policy as the secondary policy to use in a two-factor configuration. A user must
        then authenticate not only to a primary authentication server but also to a secondary authentication server. User
        groups are aggregated across both authentication servers. The user name must be exactly the same on both
        authentication servers, but the authentication servers can require different passwords.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called it primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_vpntrafficpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_vpntrafficpolicy_binding': {}}

    if priority:
        payload['vpnglobal_vpntrafficpolicy_binding']['priority'] = priority

    if policyname:
        payload['vpnglobal_vpntrafficpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['vpnglobal_vpntrafficpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['vpnglobal_vpntrafficpolicy_binding']['secondary'] = secondary

    if groupextraction:
        payload['vpnglobal_vpntrafficpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/vpnglobal_vpntrafficpolicy_binding', payload)

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


def add_vpnglobal_vpnurl_binding(urlname=None, gotopriorityexpression=None, save=False):
    '''
    Add a new vpnglobal_vpnurl_binding to the running configuration.

    urlname(str): The intranet url.

    gotopriorityexpression(str): Applicable only to advance vpn session policy. An expression or other value specifying the
        priority of the next policy which will get evaluated if the current policy rule evaluates to TRUE.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnglobal_vpnurl_binding <args>

    '''

    result = {}

    payload = {'vpnglobal_vpnurl_binding': {}}

    if urlname:
        payload['vpnglobal_vpnurl_binding']['urlname'] = urlname

    if gotopriorityexpression:
        payload['vpnglobal_vpnurl_binding']['gotopriorityexpression'] = gotopriorityexpression

    execution = __proxy__['citrixns.post']('config/vpnglobal_vpnurl_binding', payload)

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


def add_vpnintranetapplication(intranetapplication=None, protocol=None, destip=None, netmask=None, iprange=None,
                               hostname=None, clientapplication=None, spoofiip=None, destport=None, interception=None,
                               srcip=None, srcport=None, save=False):
    '''
    Add a new vpnintranetapplication to the running configuration.

    intranetapplication(str): Name of the intranet application. Minimum length = 1 Maximum length = 31

    protocol(str): Protocol used by the intranet application. If protocol is set to BOTH, TCP and UDP traffic is allowed.
        Possible values = TCP, UDP, ANY

    destip(str): Destination IP address, IP range, or host name of the intranet application. This address is the server IP
        address. Minimum length = 1

    netmask(str): Destination subnet mask for the intranet application.

    iprange(str): If you have multiple servers in your network, such as web, email, and file shares, configure an intranet
        application that includes the IP range for all the network applications. This allows users to access all the
        intranet applications contained in the IP address range. Minimum length = 1

    hostname(str): Name of the host for which to configure interception. The names are resolved during interception when
        users log on with the NetScaler Gateway Plug-in. Minimum length = 1

    clientapplication(list(str)): Names of the client applications, such as PuTTY and Xshell. Minimum length = 1

    spoofiip(str): IP address that the intranet application will use to route the connection through the virtual adapter.
        Default value: ON Possible values = ON, OFF

    destport(str): Destination TCP or UDP port number for the intranet application. Use a hyphen to specify a range of port
        numbers, for example 90-95. Minimum length = 1

    interception(str): Interception mode for the intranet application or resource. Correct value depends on the type of
        client software used to make connections. If the interception mode is set to TRANSPARENT, users connect with the
        NetScaler Gateway Plug-in for Windows. With the PROXY setting, users connect with the NetScaler Gateway Plug-in
        for Java. Possible values = PROXY, TRANSPARENT

    srcip(str): Source IP address. Required if interception mode is set to PROXY. Default is the loopback address, 127.0.0.1.
        Minimum length = 1

    srcport(int): Source port for the application for which the NetScaler Gateway virtual server proxies the traffic. If
        users are connecting from a device that uses the NetScaler Gateway Plug-in for Java, applications must be
        configured manually by using the source IP address and TCP port values specified in the intranet application
        profile. If a port value is not set, the destination port value is used. Minimum value = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnintranetapplication <args>

    '''

    result = {}

    payload = {'vpnintranetapplication': {}}

    if intranetapplication:
        payload['vpnintranetapplication']['intranetapplication'] = intranetapplication

    if protocol:
        payload['vpnintranetapplication']['protocol'] = protocol

    if destip:
        payload['vpnintranetapplication']['destip'] = destip

    if netmask:
        payload['vpnintranetapplication']['netmask'] = netmask

    if iprange:
        payload['vpnintranetapplication']['iprange'] = iprange

    if hostname:
        payload['vpnintranetapplication']['hostname'] = hostname

    if clientapplication:
        payload['vpnintranetapplication']['clientapplication'] = clientapplication

    if spoofiip:
        payload['vpnintranetapplication']['spoofiip'] = spoofiip

    if destport:
        payload['vpnintranetapplication']['destport'] = destport

    if interception:
        payload['vpnintranetapplication']['interception'] = interception

    if srcip:
        payload['vpnintranetapplication']['srcip'] = srcip

    if srcport:
        payload['vpnintranetapplication']['srcport'] = srcport

    execution = __proxy__['citrixns.post']('config/vpnintranetapplication', payload)

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


def add_vpnnexthopserver(name=None, nexthopip=None, nexthopfqdn=None, resaddresstype=None, nexthopport=None, secure=None,
                         save=False):
    '''
    Add a new vpnnexthopserver to the running configuration.

    name(str): Name for the NetScaler Gateway appliance in the first DMZ. Minimum length = 1 Maximum length = 32

    nexthopip(str): IP address of the NetScaler Gateway proxy in the second DMZ.

    nexthopfqdn(str): FQDN of the NetScaler Gateway proxy in the second DMZ. Minimum length = 1

    resaddresstype(str): Address Type (IPV4/IPv6) of DNS name of nextHopServer FQDN. Minimum length = 1 Possible values =
        IPV4, IPV6

    nexthopport(int): Port number of the NetScaler Gateway proxy in the second DMZ. Minimum value = 1 Maximum value = 65535

    secure(str): Use of a secure port, such as 443, for the double-hop configuration. Default value: OFF Possible values =
        ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnnexthopserver <args>

    '''

    result = {}

    payload = {'vpnnexthopserver': {}}

    if name:
        payload['vpnnexthopserver']['name'] = name

    if nexthopip:
        payload['vpnnexthopserver']['nexthopip'] = nexthopip

    if nexthopfqdn:
        payload['vpnnexthopserver']['nexthopfqdn'] = nexthopfqdn

    if resaddresstype:
        payload['vpnnexthopserver']['resaddresstype'] = resaddresstype

    if nexthopport:
        payload['vpnnexthopserver']['nexthopport'] = nexthopport

    if secure:
        payload['vpnnexthopserver']['secure'] = secure

    execution = __proxy__['citrixns.post']('config/vpnnexthopserver', payload)

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


def add_vpnpcoipprofile(name=None, conserverurl=None, icvverification=None, sessionidletimeout=None, save=False):
    '''
    Add a new vpnpcoipprofile to the running configuration.

    name(str): name of PCoIP profile. Minimum length = 1

    conserverurl(str): Connection server URL.

    icvverification(str): ICV verification for PCOIP transport packets. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    sessionidletimeout(int): PCOIP Idle Session timeout. Default value: 180 Minimum value = 30 Maximum value = 240

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnpcoipprofile <args>

    '''

    result = {}

    payload = {'vpnpcoipprofile': {}}

    if name:
        payload['vpnpcoipprofile']['name'] = name

    if conserverurl:
        payload['vpnpcoipprofile']['conserverurl'] = conserverurl

    if icvverification:
        payload['vpnpcoipprofile']['icvverification'] = icvverification

    if sessionidletimeout:
        payload['vpnpcoipprofile']['sessionidletimeout'] = sessionidletimeout

    execution = __proxy__['citrixns.post']('config/vpnpcoipprofile', payload)

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


def add_vpnpcoipvserverprofile(name=None, logindomain=None, udpport=None, save=False):
    '''
    Add a new vpnpcoipvserverprofile to the running configuration.

    name(str): name of PCoIP vserver profile. Minimum length = 1

    logindomain(str): Login domain for PCoIP users.

    udpport(int): UDP port for PCoIP data traffic. Default value: 4172 Range 1 - 65535 * in CLI is represented as 65535 in
        NITRO API

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnpcoipvserverprofile <args>

    '''

    result = {}

    payload = {'vpnpcoipvserverprofile': {}}

    if name:
        payload['vpnpcoipvserverprofile']['name'] = name

    if logindomain:
        payload['vpnpcoipvserverprofile']['logindomain'] = logindomain

    if udpport:
        payload['vpnpcoipvserverprofile']['udpport'] = udpport

    execution = __proxy__['citrixns.post']('config/vpnpcoipvserverprofile', payload)

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


def add_vpnportaltheme(name=None, basetheme=None, save=False):
    '''
    Add a new vpnportaltheme to the running configuration.

    name(str): Name of the uitheme. Minimum length = 1

    basetheme(str): . Minimum length = 1 Possible values = Default, Greenbubble, X1, RfWebUI

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnportaltheme <args>

    '''

    result = {}

    payload = {'vpnportaltheme': {}}

    if name:
        payload['vpnportaltheme']['name'] = name

    if basetheme:
        payload['vpnportaltheme']['basetheme'] = basetheme

    execution = __proxy__['citrixns.post']('config/vpnportaltheme', payload)

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


def add_vpnsamlssoprofile(name=None, samlsigningcertname=None, assertionconsumerserviceurl=None, relaystaterule=None,
                          sendpassword=None, samlissuername=None, signaturealg=None, digestmethod=None, audience=None,
                          nameidformat=None, nameidexpr=None, attribute1=None, attribute1expr=None,
                          attribute1friendlyname=None, attribute1format=None, attribute2=None, attribute2expr=None,
                          attribute2friendlyname=None, attribute2format=None, attribute3=None, attribute3expr=None,
                          attribute3friendlyname=None, attribute3format=None, attribute4=None, attribute4expr=None,
                          attribute4friendlyname=None, attribute4format=None, attribute5=None, attribute5expr=None,
                          attribute5friendlyname=None, attribute5format=None, attribute6=None, attribute6expr=None,
                          attribute6friendlyname=None, attribute6format=None, attribute7=None, attribute7expr=None,
                          attribute7friendlyname=None, attribute7format=None, attribute8=None, attribute8expr=None,
                          attribute8friendlyname=None, attribute8format=None, attribute9=None, attribute9expr=None,
                          attribute9friendlyname=None, attribute9format=None, attribute10=None, attribute10expr=None,
                          attribute10friendlyname=None, attribute10format=None, attribute11=None, attribute11expr=None,
                          attribute11friendlyname=None, attribute11format=None, attribute12=None, attribute12expr=None,
                          attribute12friendlyname=None, attribute12format=None, attribute13=None, attribute13expr=None,
                          attribute13friendlyname=None, attribute13format=None, attribute14=None, attribute14expr=None,
                          attribute14friendlyname=None, attribute14format=None, attribute15=None, attribute15expr=None,
                          attribute15friendlyname=None, attribute15format=None, attribute16=None, attribute16expr=None,
                          attribute16friendlyname=None, attribute16format=None, encryptassertion=None,
                          samlspcertname=None, encryptionalgorithm=None, skewtime=None, save=False):
    '''
    Add a new vpnsamlssoprofile to the running configuration.

    name(str): Name for the new saml single sign-on profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an SSO action is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    samlsigningcertname(str): Name of the signing authority as given in the SAML servers SSL certificate. Minimum length = 1

    assertionconsumerserviceurl(str): URL to which the assertion is to be sent. Minimum length = 1

    relaystaterule(str): Expression to extract relaystate to be sent along with assertion. Evaluation of this expression
        should return TEXT content. This is typically a target url to which user is redirected after the recipient
        validates SAML token.

    sendpassword(str): Option to send password in assertion. Default value: OFF Possible values = ON, OFF

    samlissuername(str): The name to be used in requests sent from Netscaler to IdP to uniquely identify Netscaler. Minimum
        length = 1

    signaturealg(str): Algorithm to be used to sign/verify SAML transactions. Default value: RSA-SHA1 Possible values =
        RSA-SHA1, RSA-SHA256

    digestmethod(str): Algorithm to be used to compute/verify digest for SAML transactions. Default value: SHA1 Possible
        values = SHA1, SHA256

    audience(str): Audience for which assertion sent by IdP is applicable. This is typically entity name or url that
        represents ServiceProvider.

    nameidformat(str): Format of Name Identifier sent in Assertion. Default value: transient Possible values = Unspecified,
        emailAddress, X509SubjectName, WindowsDomainQualifiedName, kerberos, entity, persistent, transient

    nameidexpr(str): Expression that will be evaluated to obtain NameIdentifier to be sent in assertion. Maximum length =
        128

    attribute1(str): Name of attribute1 that needs to be sent in SAML Assertion.

    attribute1expr(str): Expression that will be evaluated to obtain attribute1s value to be sent in Assertion. Maximum
        length = 128

    attribute1friendlyname(str): User-Friendly Name of attribute1 that needs to be sent in SAML Assertion.

    attribute1format(str): Format of Attribute1 to be sent in Assertion. Possible values = URI, Basic

    attribute2(str): Name of attribute2 that needs to be sent in SAML Assertion.

    attribute2expr(str): Expression that will be evaluated to obtain attribute2s value to be sent in Assertion. Maximum
        length = 128

    attribute2friendlyname(str): User-Friendly Name of attribute2 that needs to be sent in SAML Assertion.

    attribute2format(str): Format of Attribute2 to be sent in Assertion. Possible values = URI, Basic

    attribute3(str): Name of attribute3 that needs to be sent in SAML Assertion.

    attribute3expr(str): Expression that will be evaluated to obtain attribute3s value to be sent in Assertion. Maximum
        length = 128

    attribute3friendlyname(str): User-Friendly Name of attribute3 that needs to be sent in SAML Assertion.

    attribute3format(str): Format of Attribute3 to be sent in Assertion. Possible values = URI, Basic

    attribute4(str): Name of attribute4 that needs to be sent in SAML Assertion.

    attribute4expr(str): Expression that will be evaluated to obtain attribute4s value to be sent in Assertion. Maximum
        length = 128

    attribute4friendlyname(str): User-Friendly Name of attribute4 that needs to be sent in SAML Assertion.

    attribute4format(str): Format of Attribute4 to be sent in Assertion. Possible values = URI, Basic

    attribute5(str): Name of attribute5 that needs to be sent in SAML Assertion.

    attribute5expr(str): Expression that will be evaluated to obtain attribute5s value to be sent in Assertion. Maximum
        length = 128

    attribute5friendlyname(str): User-Friendly Name of attribute5 that needs to be sent in SAML Assertion.

    attribute5format(str): Format of Attribute5 to be sent in Assertion. Possible values = URI, Basic

    attribute6(str): Name of attribute6 that needs to be sent in SAML Assertion.

    attribute6expr(str): Expression that will be evaluated to obtain attribute6s value to be sent in Assertion. Maximum
        length = 128

    attribute6friendlyname(str): User-Friendly Name of attribute6 that needs to be sent in SAML Assertion.

    attribute6format(str): Format of Attribute6 to be sent in Assertion. Possible values = URI, Basic

    attribute7(str): Name of attribute7 that needs to be sent in SAML Assertion.

    attribute7expr(str): Expression that will be evaluated to obtain attribute7s value to be sent in Assertion. Maximum
        length = 128

    attribute7friendlyname(str): User-Friendly Name of attribute7 that needs to be sent in SAML Assertion.

    attribute7format(str): Format of Attribute7 to be sent in Assertion. Possible values = URI, Basic

    attribute8(str): Name of attribute8 that needs to be sent in SAML Assertion.

    attribute8expr(str): Expression that will be evaluated to obtain attribute8s value to be sent in Assertion. Maximum
        length = 128

    attribute8friendlyname(str): User-Friendly Name of attribute8 that needs to be sent in SAML Assertion.

    attribute8format(str): Format of Attribute8 to be sent in Assertion. Possible values = URI, Basic

    attribute9(str): Name of attribute9 that needs to be sent in SAML Assertion.

    attribute9expr(str): Expression that will be evaluated to obtain attribute9s value to be sent in Assertion. Maximum
        length = 128

    attribute9friendlyname(str): User-Friendly Name of attribute9 that needs to be sent in SAML Assertion.

    attribute9format(str): Format of Attribute9 to be sent in Assertion. Possible values = URI, Basic

    attribute10(str): Name of attribute10 that needs to be sent in SAML Assertion.

    attribute10expr(str): Expression that will be evaluated to obtain attribute10s value to be sent in Assertion. Maximum
        length = 128

    attribute10friendlyname(str): User-Friendly Name of attribute10 that needs to be sent in SAML Assertion.

    attribute10format(str): Format of Attribute10 to be sent in Assertion. Possible values = URI, Basic

    attribute11(str): Name of attribute11 that needs to be sent in SAML Assertion.

    attribute11expr(str): Expression that will be evaluated to obtain attribute11s value to be sent in Assertion. Maximum
        length = 128

    attribute11friendlyname(str): User-Friendly Name of attribute11 that needs to be sent in SAML Assertion.

    attribute11format(str): Format of Attribute11 to be sent in Assertion. Possible values = URI, Basic

    attribute12(str): Name of attribute12 that needs to be sent in SAML Assertion.

    attribute12expr(str): Expression that will be evaluated to obtain attribute12s value to be sent in Assertion. Maximum
        length = 128

    attribute12friendlyname(str): User-Friendly Name of attribute12 that needs to be sent in SAML Assertion.

    attribute12format(str): Format of Attribute12 to be sent in Assertion. Possible values = URI, Basic

    attribute13(str): Name of attribute13 that needs to be sent in SAML Assertion.

    attribute13expr(str): Expression that will be evaluated to obtain attribute13s value to be sent in Assertion. Maximum
        length = 128

    attribute13friendlyname(str): User-Friendly Name of attribute13 that needs to be sent in SAML Assertion.

    attribute13format(str): Format of Attribute13 to be sent in Assertion. Possible values = URI, Basic

    attribute14(str): Name of attribute14 that needs to be sent in SAML Assertion.

    attribute14expr(str): Expression that will be evaluated to obtain attribute14s value to be sent in Assertion. Maximum
        length = 128

    attribute14friendlyname(str): User-Friendly Name of attribute14 that needs to be sent in SAML Assertion.

    attribute14format(str): Format of Attribute14 to be sent in Assertion. Possible values = URI, Basic

    attribute15(str): Name of attribute15 that needs to be sent in SAML Assertion.

    attribute15expr(str): Expression that will be evaluated to obtain attribute15s value to be sent in Assertion. Maximum
        length = 128

    attribute15friendlyname(str): User-Friendly Name of attribute15 that needs to be sent in SAML Assertion.

    attribute15format(str): Format of Attribute15 to be sent in Assertion. Possible values = URI, Basic

    attribute16(str): Name of attribute16 that needs to be sent in SAML Assertion.

    attribute16expr(str): Expression that will be evaluated to obtain attribute16s value to be sent in Assertion. Maximum
        length = 128

    attribute16friendlyname(str): User-Friendly Name of attribute16 that needs to be sent in SAML Assertion.

    attribute16format(str): Format of Attribute16 to be sent in Assertion. Possible values = URI, Basic

    encryptassertion(str): Option to encrypt assertion when Netscaler sends one. Default value: OFF Possible values = ON,
        OFF

    samlspcertname(str): Name of the SSL certificate of peer/receving party using which Assertion is encrypted. Minimum
        length = 1

    encryptionalgorithm(str): Algorithm to be used to encrypt SAML assertion. Default value: AES256 Possible values = DES3,
        AES128, AES192, AES256

    skewtime(int): This option specifies the number of minutes on either side of current time that the assertion would be
        valid. For example, if skewTime is 10, then assertion would be valid from (current time - 10) min to (current
        time + 10) min, ie 20min in all. Default value: 5

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnsamlssoprofile <args>

    '''

    result = {}

    payload = {'vpnsamlssoprofile': {}}

    if name:
        payload['vpnsamlssoprofile']['name'] = name

    if samlsigningcertname:
        payload['vpnsamlssoprofile']['samlsigningcertname'] = samlsigningcertname

    if assertionconsumerserviceurl:
        payload['vpnsamlssoprofile']['assertionconsumerserviceurl'] = assertionconsumerserviceurl

    if relaystaterule:
        payload['vpnsamlssoprofile']['relaystaterule'] = relaystaterule

    if sendpassword:
        payload['vpnsamlssoprofile']['sendpassword'] = sendpassword

    if samlissuername:
        payload['vpnsamlssoprofile']['samlissuername'] = samlissuername

    if signaturealg:
        payload['vpnsamlssoprofile']['signaturealg'] = signaturealg

    if digestmethod:
        payload['vpnsamlssoprofile']['digestmethod'] = digestmethod

    if audience:
        payload['vpnsamlssoprofile']['audience'] = audience

    if nameidformat:
        payload['vpnsamlssoprofile']['nameidformat'] = nameidformat

    if nameidexpr:
        payload['vpnsamlssoprofile']['nameidexpr'] = nameidexpr

    if attribute1:
        payload['vpnsamlssoprofile']['attribute1'] = attribute1

    if attribute1expr:
        payload['vpnsamlssoprofile']['attribute1expr'] = attribute1expr

    if attribute1friendlyname:
        payload['vpnsamlssoprofile']['attribute1friendlyname'] = attribute1friendlyname

    if attribute1format:
        payload['vpnsamlssoprofile']['attribute1format'] = attribute1format

    if attribute2:
        payload['vpnsamlssoprofile']['attribute2'] = attribute2

    if attribute2expr:
        payload['vpnsamlssoprofile']['attribute2expr'] = attribute2expr

    if attribute2friendlyname:
        payload['vpnsamlssoprofile']['attribute2friendlyname'] = attribute2friendlyname

    if attribute2format:
        payload['vpnsamlssoprofile']['attribute2format'] = attribute2format

    if attribute3:
        payload['vpnsamlssoprofile']['attribute3'] = attribute3

    if attribute3expr:
        payload['vpnsamlssoprofile']['attribute3expr'] = attribute3expr

    if attribute3friendlyname:
        payload['vpnsamlssoprofile']['attribute3friendlyname'] = attribute3friendlyname

    if attribute3format:
        payload['vpnsamlssoprofile']['attribute3format'] = attribute3format

    if attribute4:
        payload['vpnsamlssoprofile']['attribute4'] = attribute4

    if attribute4expr:
        payload['vpnsamlssoprofile']['attribute4expr'] = attribute4expr

    if attribute4friendlyname:
        payload['vpnsamlssoprofile']['attribute4friendlyname'] = attribute4friendlyname

    if attribute4format:
        payload['vpnsamlssoprofile']['attribute4format'] = attribute4format

    if attribute5:
        payload['vpnsamlssoprofile']['attribute5'] = attribute5

    if attribute5expr:
        payload['vpnsamlssoprofile']['attribute5expr'] = attribute5expr

    if attribute5friendlyname:
        payload['vpnsamlssoprofile']['attribute5friendlyname'] = attribute5friendlyname

    if attribute5format:
        payload['vpnsamlssoprofile']['attribute5format'] = attribute5format

    if attribute6:
        payload['vpnsamlssoprofile']['attribute6'] = attribute6

    if attribute6expr:
        payload['vpnsamlssoprofile']['attribute6expr'] = attribute6expr

    if attribute6friendlyname:
        payload['vpnsamlssoprofile']['attribute6friendlyname'] = attribute6friendlyname

    if attribute6format:
        payload['vpnsamlssoprofile']['attribute6format'] = attribute6format

    if attribute7:
        payload['vpnsamlssoprofile']['attribute7'] = attribute7

    if attribute7expr:
        payload['vpnsamlssoprofile']['attribute7expr'] = attribute7expr

    if attribute7friendlyname:
        payload['vpnsamlssoprofile']['attribute7friendlyname'] = attribute7friendlyname

    if attribute7format:
        payload['vpnsamlssoprofile']['attribute7format'] = attribute7format

    if attribute8:
        payload['vpnsamlssoprofile']['attribute8'] = attribute8

    if attribute8expr:
        payload['vpnsamlssoprofile']['attribute8expr'] = attribute8expr

    if attribute8friendlyname:
        payload['vpnsamlssoprofile']['attribute8friendlyname'] = attribute8friendlyname

    if attribute8format:
        payload['vpnsamlssoprofile']['attribute8format'] = attribute8format

    if attribute9:
        payload['vpnsamlssoprofile']['attribute9'] = attribute9

    if attribute9expr:
        payload['vpnsamlssoprofile']['attribute9expr'] = attribute9expr

    if attribute9friendlyname:
        payload['vpnsamlssoprofile']['attribute9friendlyname'] = attribute9friendlyname

    if attribute9format:
        payload['vpnsamlssoprofile']['attribute9format'] = attribute9format

    if attribute10:
        payload['vpnsamlssoprofile']['attribute10'] = attribute10

    if attribute10expr:
        payload['vpnsamlssoprofile']['attribute10expr'] = attribute10expr

    if attribute10friendlyname:
        payload['vpnsamlssoprofile']['attribute10friendlyname'] = attribute10friendlyname

    if attribute10format:
        payload['vpnsamlssoprofile']['attribute10format'] = attribute10format

    if attribute11:
        payload['vpnsamlssoprofile']['attribute11'] = attribute11

    if attribute11expr:
        payload['vpnsamlssoprofile']['attribute11expr'] = attribute11expr

    if attribute11friendlyname:
        payload['vpnsamlssoprofile']['attribute11friendlyname'] = attribute11friendlyname

    if attribute11format:
        payload['vpnsamlssoprofile']['attribute11format'] = attribute11format

    if attribute12:
        payload['vpnsamlssoprofile']['attribute12'] = attribute12

    if attribute12expr:
        payload['vpnsamlssoprofile']['attribute12expr'] = attribute12expr

    if attribute12friendlyname:
        payload['vpnsamlssoprofile']['attribute12friendlyname'] = attribute12friendlyname

    if attribute12format:
        payload['vpnsamlssoprofile']['attribute12format'] = attribute12format

    if attribute13:
        payload['vpnsamlssoprofile']['attribute13'] = attribute13

    if attribute13expr:
        payload['vpnsamlssoprofile']['attribute13expr'] = attribute13expr

    if attribute13friendlyname:
        payload['vpnsamlssoprofile']['attribute13friendlyname'] = attribute13friendlyname

    if attribute13format:
        payload['vpnsamlssoprofile']['attribute13format'] = attribute13format

    if attribute14:
        payload['vpnsamlssoprofile']['attribute14'] = attribute14

    if attribute14expr:
        payload['vpnsamlssoprofile']['attribute14expr'] = attribute14expr

    if attribute14friendlyname:
        payload['vpnsamlssoprofile']['attribute14friendlyname'] = attribute14friendlyname

    if attribute14format:
        payload['vpnsamlssoprofile']['attribute14format'] = attribute14format

    if attribute15:
        payload['vpnsamlssoprofile']['attribute15'] = attribute15

    if attribute15expr:
        payload['vpnsamlssoprofile']['attribute15expr'] = attribute15expr

    if attribute15friendlyname:
        payload['vpnsamlssoprofile']['attribute15friendlyname'] = attribute15friendlyname

    if attribute15format:
        payload['vpnsamlssoprofile']['attribute15format'] = attribute15format

    if attribute16:
        payload['vpnsamlssoprofile']['attribute16'] = attribute16

    if attribute16expr:
        payload['vpnsamlssoprofile']['attribute16expr'] = attribute16expr

    if attribute16friendlyname:
        payload['vpnsamlssoprofile']['attribute16friendlyname'] = attribute16friendlyname

    if attribute16format:
        payload['vpnsamlssoprofile']['attribute16format'] = attribute16format

    if encryptassertion:
        payload['vpnsamlssoprofile']['encryptassertion'] = encryptassertion

    if samlspcertname:
        payload['vpnsamlssoprofile']['samlspcertname'] = samlspcertname

    if encryptionalgorithm:
        payload['vpnsamlssoprofile']['encryptionalgorithm'] = encryptionalgorithm

    if skewtime:
        payload['vpnsamlssoprofile']['skewtime'] = skewtime

    execution = __proxy__['citrixns.post']('config/vpnsamlssoprofile', payload)

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


def add_vpnsessionaction(name=None, useraccounting=None, httpport=None, winsip=None, dnsvservername=None, splitdns=None,
                         sesstimeout=None, clientsecurity=None, clientsecuritygroup=None, clientsecuritymessage=None,
                         clientsecuritylog=None, splittunnel=None, locallanaccess=None, rfc1918=None, spoofiip=None,
                         killconnections=None, transparentinterception=None, windowsclienttype=None,
                         defaultauthorizationaction=None, authorizationgroup=None, smartgroup=None,
                         clientidletimeout=None, proxy=None, allprotocolproxy=None, httpproxy=None, ftpproxy=None,
                         socksproxy=None, gopherproxy=None, sslproxy=None, proxyexception=None, proxylocalbypass=None,
                         clientcleanupprompt=None, forcecleanup=None, clientoptions=None, clientconfiguration=None,
                         sso=None, ssocredential=None, windowsautologon=None, usemip=None, useiip=None, clientdebug=None,
                         loginscript=None, logoutscript=None, homepage=None, icaproxy=None, wihome=None,
                         wihomeaddresstype=None, citrixreceiverhome=None, wiportalmode=None, clientchoices=None,
                         epaclienttype=None, iipdnssuffix=None, forcedtimeout=None, forcedtimeoutwarning=None,
                         ntdomain=None, clientlessvpnmode=None, emailhome=None, clientlessmodeurlencoding=None,
                         clientlesspersistentcookie=None, allowedlogingroups=None, securebrowse=None, storefronturl=None,
                         sfgatewayauthtype=None, kcdaccount=None, rdpclientprofilename=None, windowspluginupgrade=None,
                         macpluginupgrade=None, linuxpluginupgrade=None, iconwithreceiver=None, alwaysonprofilename=None,
                         autoproxyurl=None, pcoipprofilename=None, save=False):
    '''
    Add a new vpnsessionaction to the running configuration.

    name(str): Name for the NetScaler Gateway profile (action). Must begin with an ASCII alphabetic or underscore (_)
        character, and must consist only of ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at
        (@), equals (=), and hyphen (-) characters. Cannot be changed after the profile is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    useraccounting(str): The name of the radiusPolicy to use for RADIUS user accounting info on the session.

    httpport(list(int)): Destination port numbers other than port 80, added as a comma-separated list. Traffic to these ports
        is processed as HTTP traffic, which allows functionality, such as HTTP authorization and single sign-on to a web
        application to work. Minimum value = 1

    winsip(str): WINS server IP address to add to NetScaler Gateway for name resolution.

    dnsvservername(str): Name of the DNS virtual server for the user session. Minimum length = 1

    splitdns(str): Route the DNS requests to the local DNS server configured on the user device, or NetScaler Gateway
        (remote), or both. Possible values = LOCAL, REMOTE, BOTH

    sesstimeout(int): Number of minutes after which the session times out. Minimum value = 1

    clientsecurity(str): Specify the client security check for the user device to permit a NetScaler Gateway session. The web
        address or IP address is not included in the expression for the client security check.

    clientsecuritygroup(str): The client security group that will be assigned on failure of the client security check. Users
        can in general be organized into Groups. In this case, the Client Security Group may have a more restrictive
        security policy. Minimum length = 1

    clientsecuritymessage(str): The client security message that will be displayed on failure of the client security check.
        Minimum length = 1 Maximum length = 127

    clientsecuritylog(str): Set the logging of client security checks. Possible values = ON, OFF

    splittunnel(str): Send, through the tunnel, traffic only for intranet applications that are defined in NetScaler Gateway.
        Route all other traffic directly to the Internet. The OFF setting routes all traffic through NetScaler Gateway.
        With the REVERSE setting, intranet applications define the network traffic that is not intercepted. All network
        traffic directed to internal IP addresses bypasses the VPN tunnel, while other traffic goes through NetScaler
        Gateway. Reverse split tunneling can be used to log all non-local LAN traffic. For example, if users have a home
        network and are logged on through the NetScaler Gateway Plug-in, network traffic destined to a printer or another
        device within the home network is not intercepted. Possible values = ON, OFF, REVERSE

    locallanaccess(str): Set local LAN access. If split tunneling is OFF, and you set local LAN access to ON, the local
        client can route traffic to its local interface. When the local area network switch is specified, this
        combination of switches is useful. The client can allow local LAN access to devices that commonly have
        non-routable addresses, such as local printers or local file servers. Possible values = ON, OFF

    rfc1918(str): As defined in the local area network, allow only the following local area network addresses to bypass the
        VPN tunnel when the local LAN access feature is enabled: * 10.*.*.*, * 172.16.*.*, * 192.168.*.*. Possible values
        = ON, OFF

    spoofiip(str): IP address that the intranet application uses to route the connection through the virtual adapter.
        Possible values = ON, OFF

    killconnections(str): Specify whether the NetScaler Gateway Plug-in should disconnect all preexisting connections, such
        as the connections existing before the user logged on to NetScaler Gateway, and prevent new incoming connections
        on the NetScaler Gateway Plug-in for Windows and MAC when the user is connected to NetScaler Gateway and split
        tunneling is disabled. Possible values = ON, OFF

    transparentinterception(str): Allow access to network resources by using a single IP address and subnet mask or a range
        of IP addresses. The OFF setting sets the mode to proxy, in which you configure destination and source IP
        addresses and port numbers. If you are using the NetScaler Gateway Plug-in for Windows, set this parameter to ON,
        in which the mode is set to transparent. If you are using the NetScaler Gateway Plug-in for Java, set this
        parameter to OFF. Possible values = ON, OFF

    windowsclienttype(str): Choose between two types of Windows Client\\ a) Application Agent - which always runs in the task
        bar as a standalone application and also has a supporting service which runs permanently when installed\\ b)
        Activex Control - ActiveX control run by Microsoft Internet Explorer. Possible values = AGENT, PLUGIN

    defaultauthorizationaction(str): Specify the network resources that users have access to when they log on to the internal
        network. The default setting for authorization is to deny access to all network resources. Citrix recommends
        using the default global setting and then creating authorization policies to define the network resources users
        can access. If you set the default authorization policy to DENY, you must explicitly authorize access to any
        network resource, which improves security. Possible values = ALLOW, DENY

    authorizationgroup(str): Comma-separated list of groups in which the user is placed when none of the groups that the user
        is a part of is configured on NetScaler Gateway. The authorization policy can be bound to these groups to control
        access to the resources. Minimum length = 1

    smartgroup(str): This is the default group that is chosen when the authentication succeeds in addition to extracted
        groups. Minimum length = 1 Maximum length = 64

    clientidletimeout(int): Time, in minutes, after which to time out the user session if NetScaler Gateway does not detect
        mouse or keyboard activity. Minimum value = 1 Maximum value = 9999

    proxy(str): Set options to apply proxy for accessing the internal resources. Available settings function as follows: *
        BROWSER - Proxy settings are configured only in Internet Explorer and Firefox browsers. * NS - Proxy settings are
        configured on the NetScaler appliance. * OFF - Proxy settings are not configured. Possible values = BROWSER, NS,
        OFF

    allprotocolproxy(str): IP address of the proxy server to use for all protocols supported by NetScaler Gateway. Minimum
        length = 1

    httpproxy(str): IP address of the proxy server to be used for HTTP access for all subsequent connections to the internal
        network. Minimum length = 1

    ftpproxy(str): IP address of the proxy server to be used for FTP access for all subsequent connections to the internal
        network. Minimum length = 1

    socksproxy(str): IP address of the proxy server to be used for SOCKS access for all subsequent connections to the
        internal network. Minimum length = 1

    gopherproxy(str): IP address of the proxy server to be used for GOPHER access for all subsequent connections to the
        internal network. Minimum length = 1

    sslproxy(str): IP address of the proxy server to be used for SSL access for all subsequent connections to the internal
        network. Minimum length = 1

    proxyexception(str): Proxy exception string that will be configured in the browser for bypassing the previously
        configured proxies. Allowed only if proxy type is Browser. Minimum length = 1

    proxylocalbypass(str): Bypass proxy server for local addresses option in Internet Explorer and Firefox proxy server
        settings. Possible values = ENABLED, DISABLED

    clientcleanupprompt(str): Prompt for client-side cache clean-up when a client-initiated session closes. Possible values =
        ON, OFF

    forcecleanup(list(str)): Force cache clean-up when the user closes a session. You can specify all, none, or any
        combination of the client-side items. Possible values = none, all, cookie, addressbar, plugin,
        filesystemapplication, application, applicationdata, clientcertificate, autocomplete, cache

    clientoptions(str): Display only the configured menu options when you select the "Configure NetScaler Gateway" option in
        the NetScaler Gateway Plug-in system tray icon for Windows. Possible values = none, all, services, filetransfer,
        configuration

    clientconfiguration(list(str)): Allow users to change client Debug logging level in Configuration tab of the NetScaler
        Gateway Plug-in for Windows. Possible values = none, trace

    sso(str): Set single sign-on (SSO) for the session. When the user accesses a server, the users logon credentials are
        passed to the server for authentication. Possible values = ON, OFF

    ssocredential(str): Specify whether to use the primary or secondary authentication credentials for single sign-on to the
        server. Possible values = PRIMARY, SECONDARY

    windowsautologon(str): Enable or disable the Windows Auto Logon for the session. If a VPN session is established after
        this setting is enabled, the user is automatically logged on by using Windows credentials after the system is
        restarted. Possible values = ON, OFF

    usemip(str): Enable or disable the use of a unique IP address alias, or a mapped IP address, as the client IP address for
        each client session. Allow NetScaler Gateway to use the mapped IP address as an intranet IP address when all
        other IP addresses are not available.  When IP pooling is configured and the mapped IP is used as an intranet IP
        address, the mapped IP address is used when an intranet IP address cannot be assigned. Possible values = NS, OFF

    useiip(str): Define IP address pool options. Available settings function as follows:  * SPILLOVER - When an address pool
        is configured and the mapped IP is used as an intranet IP address, the mapped IP address is used when an intranet
        IP address cannot be assigned.  * NOSPILLOVER - When intranet IP addresses are enabled and the mapped IP address
        is not used, the Transfer Login page appears for users who have used all available intranet IP addresses.  * OFF
        - Address pool is not configured. Possible values = NOSPILLOVER, SPILLOVER, OFF

    clientdebug(str): Set the trace level on NetScaler Gateway. Technical support technicians use these debug logs for
        in-depth debugging and troubleshooting purposes. Available settings function as follows:  * DEBUG - Detailed
        debug messages are collected and written into the specified file. * STATS - Application audit level error
        messages and debug statistic counters are written into the specified file.  * EVENTS - Application audit-level
        error messages are written into the specified file.  * OFF - Only critical events are logged into the Windows
        Application Log. Possible values = debug, stats, events, OFF

    loginscript(str): Path to the logon script that is run when a session is established. Separate multiple scripts by using
        comma. A "$" in the path signifies that the word following the "$" is an environment variable. Minimum length =
        1

    logoutscript(str): Path to the logout script. Separate multiple scripts by using comma. A "$" in the path signifies that
        the word following the "$" is an environment variable. Minimum length = 1

    homepage(str): Web address of the home page that appears when users log on. Otherwise, users receive the default home
        page for NetScaler Gateway, which is the Access Interface.

    icaproxy(str): Enable ICA proxy to configure secure Internet access to servers running Citrix XenApp or XenDesktop by
        using Citrix Receiver instead of the NetScaler Gateway Plug-in. Possible values = ON, OFF

    wihome(str): Web address of the Web Interface server, such as http://;lt;ipAddress;gt;/Citrix/XenApp, or Receiver for
        Web, which enumerates the virtualized resources, such as XenApp, XenDesktop, and cloud applications. This web
        address is used as the home page in ICA proxy mode.  If Client Choices is ON, you must configure this setting.
        Because the user can choose between FullClient and ICAProxy, the user may see a different home page. An Internet
        web site may appear if the user gets the FullClient option, or a Web Interface site if the user gets the ICAProxy
        option. If the setting is not configured, the XenApp option does not appear as a client choice.

    wihomeaddresstype(str): Type of the wihome address(IPV4/V6). Possible values = IPV4, IPV6

    citrixreceiverhome(str): Web address for the Citrix Receiver home page. Configure NetScaler Gateway so that when users
        log on to the appliance, the NetScaler Gateway Plug-in opens a web browser that allows single sign-on to the
        Citrix Receiver home page.

    wiportalmode(str): Layout on the Access Interface. The COMPACT value indicates the use of small icons. Possible values =
        NORMAL, COMPACT

    clientchoices(str): Provide users with multiple logon options. With client choices, users have the option of logging on
        by using the NetScaler Gateway Plug-in for Windows, NetScaler Gateway Plug-in for Java, the Web Interface, or
        clientless access from one location. Depending on how NetScaler Gateway is configured, users are presented with
        up to three icons for logon choices. The most common are the NetScaler Gateway Plug-in for Windows, Web
        Interface, and clientless access. Possible values = ON, OFF

    epaclienttype(str): Choose between two types of End point Windows Client a) Application Agent - which always runs in the
        task bar as a standalone application and also has a supporting service which runs permanently when installed b)
        Activex Control - ActiveX control run by Microsoft Internet Explorer. Possible values = AGENT, PLUGIN

    iipdnssuffix(str): An intranet IP DNS suffix. When a user logs on to NetScaler Gateway and is assigned an IP address, a
        DNS record for the user name and IP address combination is added to the NetScaler Gateway DNS cache. You can
        configure a DNS suffix to append to the user name when the DNS record is added to the cache. You can reach to the
        host from where the user is logged on by using the users name, which can be easier to remember than an IP
        address. When the user logs off from NetScaler Gateway, the record is removed from the DNS cache. Minimum length
        = 1

    forcedtimeout(int): Force a disconnection from the NetScaler Gateway Plug-in with NetScaler Gateway after a specified
        number of minutes. If the session closes, the user must log on again. Minimum value = 1 Maximum value = 65535

    forcedtimeoutwarning(int): Number of minutes to warn a user before the user session is disconnected. Minimum value = 1
        Maximum value = 255

    ntdomain(str): Single sign-on domain to use for single sign-on to applications in the internal network. This setting can
        be overwritten by the domain that users specify at the time of logon or by the domain that the authentication
        server returns. Minimum length = 1 Maximum length = 32

    clientlessvpnmode(str): Enable clientless access for web, XenApp or XenDesktop, and FileShare resources without
        installing the NetScaler Gateway Plug-in. Available settings function as follows:  * ON - Allow only clientless
        access.  * OFF - Allow clientless access after users log on with the NetScaler Gateway Plug-in.  * DISABLED - Do
        not allow clientless access. Possible values = ON, OFF, DISABLED

    emailhome(str): Web address for the web-based email, such as Outlook Web Access.

    clientlessmodeurlencoding(str): When clientless access is enabled, you can choose to encode the addresses of internal web
        applications or to leave the address as clear text. Available settings function as follows:  * OPAQUE - Use
        standard encoding mechanisms to make the domain and protocol part of the resource unclear to users.  * CLEAR - Do
        not encode the web address and make it visible to users.  * ENCRYPT - Allow the domain and protocol to be
        encrypted using a session key. When the web address is encrypted, the URL is different for each user session for
        the same web resource. If users bookmark the encoded web address, save it in the web browser and then log off,
        they cannot connect to the web address when they log on and use the bookmark. If users save the encrypted
        bookmark in the Access Interface during their session, the bookmark works each time the user logs on. Possible
        values = TRANSPARENT, OPAQUE, ENCRYPT

    clientlesspersistentcookie(str): State of persistent cookies in clientless access mode. Persistent cookies are required
        for accessing certain features of SharePoint, such as opening and editing Microsoft Word, Excel, and PowerPoint
        documents hosted on the SharePoint server. A persistent cookie remains on the user device and is sent with each
        HTTP request. NetScaler Gateway encrypts the persistent cookie before sending it to the plug-in on the user
        device, and refreshes the cookie periodically as long as the session exists. The cookie becomes stale if the
        session ends. Available settings function as follows:  * ALLOW - Enable persistent cookies. Users can open and
        edit Microsoft documents stored in SharePoint.  * DENY - Disable persistent cookies. Users cannot open and edit
        Microsoft documents stored in SharePoint.  * PROMPT - Prompt users to allow or deny persistent cookies during the
        session. Persistent cookies are not required for clientless access if users do not connect to SharePoint.
        Possible values = ALLOW, DENY, PROMPT

    allowedlogingroups(str): Specify groups that have permission to log on to NetScaler Gateway. Users who do not belong to
        this group or groups are denied access even if they have valid credentials. Minimum length = 1 Maximum length =
        511

    securebrowse(str): Allow users to connect through NetScaler Gateway to network resources from iOS and Android mobile
        devices with Citrix Receiver. Users do not need to establish a full VPN tunnel to access resources in the secure
        network. Possible values = ENABLED, DISABLED

    storefronturl(str): Web address for StoreFront to be used in this session for enumeration of resources from XenApp or
        XenDesktop. Minimum length = 1 Maximum length = 255

    sfgatewayauthtype(str): The authentication type configured for the NetScaler Gateway on StoreFront. Possible values =
        domain, RSA, domainAndRSA, SMS, smartCard, sfAuth, sfAuthAndRSA

    kcdaccount(str): The kcd account details to be used in SSO. Minimum length = 1 Maximum length = 32

    rdpclientprofilename(str): Name of the RDP profile associated with the vserver. Minimum length = 1 Maximum length = 31

    windowspluginupgrade(str): Option to set plugin upgrade behaviour for Win. Possible values = Always, Essential, Never

    macpluginupgrade(str): Option to set plugin upgrade behaviour for Mac. Possible values = Always, Essential, Never

    linuxpluginupgrade(str): Option to set plugin upgrade behaviour for Linux. Possible values = Always, Essential, Never

    iconwithreceiver(str): Option to decide whether to show plugin icon along with receiver. Possible values = ON, OFF

    alwaysonprofilename(str): Name of the AlwaysON profile associated with the session action. The builtin profile named none
        can be used to explicitly disable AlwaysON for the session action. Minimum length = 1 Maximum length = 31

    autoproxyurl(str): URL to auto proxy config file.

    pcoipprofilename(str): Name of the PCOIP profile associated with the session action. The builtin profile named none can
        be used to explicitly disable PCOIP for the session action. Minimum length = 1 Maximum length = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnsessionaction <args>

    '''

    result = {}

    payload = {'vpnsessionaction': {}}

    if name:
        payload['vpnsessionaction']['name'] = name

    if useraccounting:
        payload['vpnsessionaction']['useraccounting'] = useraccounting

    if httpport:
        payload['vpnsessionaction']['httpport'] = httpport

    if winsip:
        payload['vpnsessionaction']['winsip'] = winsip

    if dnsvservername:
        payload['vpnsessionaction']['dnsvservername'] = dnsvservername

    if splitdns:
        payload['vpnsessionaction']['splitdns'] = splitdns

    if sesstimeout:
        payload['vpnsessionaction']['sesstimeout'] = sesstimeout

    if clientsecurity:
        payload['vpnsessionaction']['clientsecurity'] = clientsecurity

    if clientsecuritygroup:
        payload['vpnsessionaction']['clientsecuritygroup'] = clientsecuritygroup

    if clientsecuritymessage:
        payload['vpnsessionaction']['clientsecuritymessage'] = clientsecuritymessage

    if clientsecuritylog:
        payload['vpnsessionaction']['clientsecuritylog'] = clientsecuritylog

    if splittunnel:
        payload['vpnsessionaction']['splittunnel'] = splittunnel

    if locallanaccess:
        payload['vpnsessionaction']['locallanaccess'] = locallanaccess

    if rfc1918:
        payload['vpnsessionaction']['rfc1918'] = rfc1918

    if spoofiip:
        payload['vpnsessionaction']['spoofiip'] = spoofiip

    if killconnections:
        payload['vpnsessionaction']['killconnections'] = killconnections

    if transparentinterception:
        payload['vpnsessionaction']['transparentinterception'] = transparentinterception

    if windowsclienttype:
        payload['vpnsessionaction']['windowsclienttype'] = windowsclienttype

    if defaultauthorizationaction:
        payload['vpnsessionaction']['defaultauthorizationaction'] = defaultauthorizationaction

    if authorizationgroup:
        payload['vpnsessionaction']['authorizationgroup'] = authorizationgroup

    if smartgroup:
        payload['vpnsessionaction']['smartgroup'] = smartgroup

    if clientidletimeout:
        payload['vpnsessionaction']['clientidletimeout'] = clientidletimeout

    if proxy:
        payload['vpnsessionaction']['proxy'] = proxy

    if allprotocolproxy:
        payload['vpnsessionaction']['allprotocolproxy'] = allprotocolproxy

    if httpproxy:
        payload['vpnsessionaction']['httpproxy'] = httpproxy

    if ftpproxy:
        payload['vpnsessionaction']['ftpproxy'] = ftpproxy

    if socksproxy:
        payload['vpnsessionaction']['socksproxy'] = socksproxy

    if gopherproxy:
        payload['vpnsessionaction']['gopherproxy'] = gopherproxy

    if sslproxy:
        payload['vpnsessionaction']['sslproxy'] = sslproxy

    if proxyexception:
        payload['vpnsessionaction']['proxyexception'] = proxyexception

    if proxylocalbypass:
        payload['vpnsessionaction']['proxylocalbypass'] = proxylocalbypass

    if clientcleanupprompt:
        payload['vpnsessionaction']['clientcleanupprompt'] = clientcleanupprompt

    if forcecleanup:
        payload['vpnsessionaction']['forcecleanup'] = forcecleanup

    if clientoptions:
        payload['vpnsessionaction']['clientoptions'] = clientoptions

    if clientconfiguration:
        payload['vpnsessionaction']['clientconfiguration'] = clientconfiguration

    if sso:
        payload['vpnsessionaction']['sso'] = sso

    if ssocredential:
        payload['vpnsessionaction']['ssocredential'] = ssocredential

    if windowsautologon:
        payload['vpnsessionaction']['windowsautologon'] = windowsautologon

    if usemip:
        payload['vpnsessionaction']['usemip'] = usemip

    if useiip:
        payload['vpnsessionaction']['useiip'] = useiip

    if clientdebug:
        payload['vpnsessionaction']['clientdebug'] = clientdebug

    if loginscript:
        payload['vpnsessionaction']['loginscript'] = loginscript

    if logoutscript:
        payload['vpnsessionaction']['logoutscript'] = logoutscript

    if homepage:
        payload['vpnsessionaction']['homepage'] = homepage

    if icaproxy:
        payload['vpnsessionaction']['icaproxy'] = icaproxy

    if wihome:
        payload['vpnsessionaction']['wihome'] = wihome

    if wihomeaddresstype:
        payload['vpnsessionaction']['wihomeaddresstype'] = wihomeaddresstype

    if citrixreceiverhome:
        payload['vpnsessionaction']['citrixreceiverhome'] = citrixreceiverhome

    if wiportalmode:
        payload['vpnsessionaction']['wiportalmode'] = wiportalmode

    if clientchoices:
        payload['vpnsessionaction']['clientchoices'] = clientchoices

    if epaclienttype:
        payload['vpnsessionaction']['epaclienttype'] = epaclienttype

    if iipdnssuffix:
        payload['vpnsessionaction']['iipdnssuffix'] = iipdnssuffix

    if forcedtimeout:
        payload['vpnsessionaction']['forcedtimeout'] = forcedtimeout

    if forcedtimeoutwarning:
        payload['vpnsessionaction']['forcedtimeoutwarning'] = forcedtimeoutwarning

    if ntdomain:
        payload['vpnsessionaction']['ntdomain'] = ntdomain

    if clientlessvpnmode:
        payload['vpnsessionaction']['clientlessvpnmode'] = clientlessvpnmode

    if emailhome:
        payload['vpnsessionaction']['emailhome'] = emailhome

    if clientlessmodeurlencoding:
        payload['vpnsessionaction']['clientlessmodeurlencoding'] = clientlessmodeurlencoding

    if clientlesspersistentcookie:
        payload['vpnsessionaction']['clientlesspersistentcookie'] = clientlesspersistentcookie

    if allowedlogingroups:
        payload['vpnsessionaction']['allowedlogingroups'] = allowedlogingroups

    if securebrowse:
        payload['vpnsessionaction']['securebrowse'] = securebrowse

    if storefronturl:
        payload['vpnsessionaction']['storefronturl'] = storefronturl

    if sfgatewayauthtype:
        payload['vpnsessionaction']['sfgatewayauthtype'] = sfgatewayauthtype

    if kcdaccount:
        payload['vpnsessionaction']['kcdaccount'] = kcdaccount

    if rdpclientprofilename:
        payload['vpnsessionaction']['rdpclientprofilename'] = rdpclientprofilename

    if windowspluginupgrade:
        payload['vpnsessionaction']['windowspluginupgrade'] = windowspluginupgrade

    if macpluginupgrade:
        payload['vpnsessionaction']['macpluginupgrade'] = macpluginupgrade

    if linuxpluginupgrade:
        payload['vpnsessionaction']['linuxpluginupgrade'] = linuxpluginupgrade

    if iconwithreceiver:
        payload['vpnsessionaction']['iconwithreceiver'] = iconwithreceiver

    if alwaysonprofilename:
        payload['vpnsessionaction']['alwaysonprofilename'] = alwaysonprofilename

    if autoproxyurl:
        payload['vpnsessionaction']['autoproxyurl'] = autoproxyurl

    if pcoipprofilename:
        payload['vpnsessionaction']['pcoipprofilename'] = pcoipprofilename

    execution = __proxy__['citrixns.post']('config/vpnsessionaction', payload)

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


def add_vpnsessionpolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new vpnsessionpolicy to the running configuration.

    name(str): Name for the new session policy that is applied after the user logs on to NetScaler Gateway. Minimum length =
        1

    rule(str): Expression, or name of a named expression, specifying the traffic that matches the policy. Can be written in
        either default or classic syntax.  Maximum length of a string literal in the expression is 255 characters. A
        longer string can be split into smaller strings of up to 255 characters each, and the smaller strings
        concatenated with the + operator. For example, you can create a 500-character string as follows: ";lt;string of
        255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler
        CLI: * If the expression includes one or more spaces, enclose the entire expression in double quotation marks. *
        If the expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Action to be applied by the new session policy if the rule criteria are met. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnsessionpolicy <args>

    '''

    result = {}

    payload = {'vpnsessionpolicy': {}}

    if name:
        payload['vpnsessionpolicy']['name'] = name

    if rule:
        payload['vpnsessionpolicy']['rule'] = rule

    if action:
        payload['vpnsessionpolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/vpnsessionpolicy', payload)

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


def add_vpntrafficaction(name=None, qual=None, apptimeout=None, sso=None, hdx=None, formssoaction=None, fta=None,
                         wanscaler=None, kcdaccount=None, samlssoprofile=None, proxy=None, userexpression=None,
                         passwdexpression=None, save=False):
    '''
    Add a new vpntrafficaction to the running configuration.

    name(str): Name for the traffic action. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after a traffic action is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my action" or my action). Minimum length = 1

    qual(str): Protocol, either HTTP or TCP, to be used with the action. Possible values = http, tcp

    apptimeout(int): Maximum amount of time, in minutes, a user can stay logged on to the web application. Minimum value = 1
        Maximum value = 715827

    sso(str): Provide single sign-on to the web application. Possible values = ON, OFF

    hdx(str): Provide hdx proxy to the ICA traffic. Possible values = ON, OFF

    formssoaction(str): Name of the form-based single sign-on profile. Form-based single sign-on allows users to log on one
        time to all protected applications in your network, instead of requiring them to log on separately to access each
        one.

    fta(str): Specify file type association, which is a list of file extensions that users are allowed to open. Possible
        values = ON, OFF

    wanscaler(str): Use the Repeater Plug-in to optimize network traffic. Possible values = ON, OFF

    kcdaccount(str): Kerberos constrained delegation account name. Default value: "Default" Minimum length = 1 Maximum length
        = 32

    samlssoprofile(str): Profile to be used for doing SAML SSO to remote relying party. Minimum length = 1

    proxy(str): IP address and Port of the proxy server to be used for HTTP access for this request. Minimum length = 1

    userexpression(str): expression that will be evaluated to obtain username for SingleSignOn. Maximum length = 256

    passwdexpression(str): expression that will be evaluated to obtain password for SingleSignOn. Maximum length = 256

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpntrafficaction <args>

    '''

    result = {}

    payload = {'vpntrafficaction': {}}

    if name:
        payload['vpntrafficaction']['name'] = name

    if qual:
        payload['vpntrafficaction']['qual'] = qual

    if apptimeout:
        payload['vpntrafficaction']['apptimeout'] = apptimeout

    if sso:
        payload['vpntrafficaction']['sso'] = sso

    if hdx:
        payload['vpntrafficaction']['hdx'] = hdx

    if formssoaction:
        payload['vpntrafficaction']['formssoaction'] = formssoaction

    if fta:
        payload['vpntrafficaction']['fta'] = fta

    if wanscaler:
        payload['vpntrafficaction']['wanscaler'] = wanscaler

    if kcdaccount:
        payload['vpntrafficaction']['kcdaccount'] = kcdaccount

    if samlssoprofile:
        payload['vpntrafficaction']['samlssoprofile'] = samlssoprofile

    if proxy:
        payload['vpntrafficaction']['proxy'] = proxy

    if userexpression:
        payload['vpntrafficaction']['userexpression'] = userexpression

    if passwdexpression:
        payload['vpntrafficaction']['passwdexpression'] = passwdexpression

    execution = __proxy__['citrixns.post']('config/vpntrafficaction', payload)

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


def add_vpntrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new vpntrafficpolicy to the running configuration.

    name(str): Name for the traffic policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the policy is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic or
        default syntax. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can
        be split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;" The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Action to apply to traffic that matches the policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpntrafficpolicy <args>

    '''

    result = {}

    payload = {'vpntrafficpolicy': {}}

    if name:
        payload['vpntrafficpolicy']['name'] = name

    if rule:
        payload['vpntrafficpolicy']['rule'] = rule

    if action:
        payload['vpntrafficpolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/vpntrafficpolicy', payload)

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


def add_vpnurl(urlname=None, linkname=None, actualurl=None, vservername=None, clientlessaccess=None, comment=None,
               iconurl=None, ssotype=None, applicationtype=None, samlssoprofile=None, save=False):
    '''
    Add a new vpnurl to the running configuration.

    urlname(str): Name of the bookmark link. Minimum length = 1

    linkname(str): Description of the bookmark link. The description appears in the Access Interface. Minimum length = 1

    actualurl(str): Web address for the bookmark link. Minimum length = 1

    vservername(str): Name of the associated LB/CS vserver.

    clientlessaccess(str): If clientless access to the resource hosting the link is allowed, also use clientless access for
        the bookmarked web address in the Secure Client Access based session. Allows single sign-on and other HTTP
        processing on NetScaler Gateway for HTTPS resources. Default value: OFF Possible values = ON, OFF

    comment(str): Any comments associated with the bookmark link.

    iconurl(str): URL to fetch icon file for displaying this resource.

    ssotype(str): Single sign on type for unified gateway. Possible values = unifiedgateway, selfauth, samlauth

    applicationtype(str): The type of application this VPN URL represents. Possible values are CVPN/SaaS/VPN. Possible values
        = CVPN, VPN, SaaS

    samlssoprofile(str): Profile to be used for doing SAML SSO.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnurl <args>

    '''

    result = {}

    payload = {'vpnurl': {}}

    if urlname:
        payload['vpnurl']['urlname'] = urlname

    if linkname:
        payload['vpnurl']['linkname'] = linkname

    if actualurl:
        payload['vpnurl']['actualurl'] = actualurl

    if vservername:
        payload['vpnurl']['vservername'] = vservername

    if clientlessaccess:
        payload['vpnurl']['clientlessaccess'] = clientlessaccess

    if comment:
        payload['vpnurl']['comment'] = comment

    if iconurl:
        payload['vpnurl']['iconurl'] = iconurl

    if ssotype:
        payload['vpnurl']['ssotype'] = ssotype

    if applicationtype:
        payload['vpnurl']['applicationtype'] = applicationtype

    if samlssoprofile:
        payload['vpnurl']['samlssoprofile'] = samlssoprofile

    execution = __proxy__['citrixns.post']('config/vpnurl', payload)

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


def add_vpnvserver(name=None, servicetype=None, ipv46=None, range=None, port=None, state=None, authentication=None,
                   doublehop=None, maxaaausers=None, icaonly=None, icaproxysessionmigration=None, dtls=None,
                   loginonce=None, advancedepa=None, devicecert=None, certkeynames=None, downstateflush=None,
                   listenpolicy=None, listenpriority=None, tcpprofilename=None, httpprofilename=None, comment=None,
                   appflowlog=None, icmpvsrresponse=None, rhistate=None, netprofile=None, cginfrahomepageredirect=None,
                   maxloginattempts=None, failedlogintimeout=None, l2conn=None, deploymenttype=None,
                   rdpserverprofilename=None, windowsepapluginupgrade=None, linuxepapluginupgrade=None,
                   macepapluginupgrade=None, logoutonsmartcardremoval=None, userdomains=None, authnprofile=None,
                   vserverfqdn=None, pcoipvserverprofilename=None, newname=None, save=False):
    '''
    Add a new vpnvserver to the running configuration.

    name(str): Name for the NetScaler Gateway virtual server. Must begin with an ASCII alphabetic or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Can be changed after the virtual server is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my server" or my server). Minimum length = 1

    servicetype(str): Protocol used by the NetScaler Gateway virtual server. Default value: SSL Possible values = SSL

    ipv46(str): IPv4 or IPv6 address of the NetScaler Gateway virtual server. Usually a public IP address. User devices send
        connection requests to this IP address. Minimum length = 1

    range(int): Range of NetScaler Gateway virtual server IP addresses. The consecutively numbered range of IP addresses
        begins with the address specified by the IP Address parameter.  In the configuration utility, select Network
        VServer to enter a range. Default value: 1 Minimum value = 1

    port(int): TCP port on which the virtual server listens. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    state(str): State of the virtual server. If the virtual server is disabled, requests are not processed. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    authentication(str): Require authentication for users connecting to NetScaler Gateway. Default value: ON Possible values
        = ON, OFF

    doublehop(str): Use the NetScaler Gateway appliance in a double-hop configuration. A double-hop deployment provides an
        extra layer of security for the internal network by using three firewalls to divide the DMZ into two stages. Such
        a deployment can have one appliance in the DMZ and one appliance in the secure network. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    maxaaausers(int): Maximum number of concurrent user sessions allowed on this virtual server. The actual number of users
        allowed to log on to this virtual server depends on the total number of user licenses.

    icaonly(str): - When set to ON, it implies Basic mode where the user can log on using either Citrix Receiver or a browser
        and get access to the published apps configured at the XenApp/XenDEsktop environment pointed out by the WIHome
        parameter. Users are not allowed to connect using the NetScaler Gateway Plug-in and end point scans cannot be
        configured. Number of users that can log in and access the apps are not limited by the license in this mode.   -
        When set to OFF, it implies Smart Access mode where the user can log on using either Citrix Receiver or a browser
        or a NetScaler Gateway Plug-in. The admin can configure end point scans to be run on the client systems and then
        use the results to control access to the published apps. In this mode, the client can connect to the gateway in
        other client modes namely VPN and CVPN. Number of users that can log in and access the resources are limited by
        the CCU licenses in this mode. Default value: OFF Possible values = ON, OFF

    icaproxysessionmigration(str): This option determines if an existing ICA Proxy session is transferred when the user logs
        on from another device. Default value: OFF Possible values = ON, OFF

    dtls(str): This option starts/stops the turn service on the vserver. Default value: OFF Possible values = ON, OFF

    loginonce(str): This option enables/disables seamless SSO for this Vserver. Default value: OFF Possible values = ON, OFF

    advancedepa(str): This option tells whether advanced EPA is enabled on this virtual server. Default value: OFF Possible
        values = ON, OFF

    devicecert(str): Indicates whether device certificate check as a part of EPA is on or off. Default value: OFF Possible
        values = ON, OFF

    certkeynames(str): Name of the certificate key that was bound to the corresponding SSL virtual server as the Certificate
        Authority for the device certificate. Minimum length = 1 Maximum length = 127

    downstateflush(str): Close existing connections when the virtual server is marked DOWN, which means the server might have
        timed out. Disconnecting existing connections frees resources and in certain cases speeds recovery of overloaded
        load balancing setups. Enable this setting on servers in which the connections can safely be closed when they are
        marked DOWN. Do not enable DOWN state flush on servers that must complete their transactions. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    listenpolicy(str): String specifying the listen policy for the NetScaler Gateway virtual server. Can be either a named
        expression or a default syntax expression. The NetScaler Gateway virtual server processes only the traffic for
        which the expression evaluates to true. Default value: "none"

    listenpriority(int): Integer specifying the priority of the listen policy. A higher number specifies a lower priority. If
        a request matches the listen policies of more than one virtual server, the virtual server whose listen policy has
        the highest priority (the lowest priority number) accepts the request. Default value: 101 Minimum value = 0
        Maximum value = 100

    tcpprofilename(str): Name of the TCP profile to assign to this virtual server. Minimum length = 1 Maximum length = 127

    httpprofilename(str): Name of the HTTP profile to assign to this virtual server. Default value:
        "nshttp_default_strict_validation" Minimum length = 1 Maximum length = 127

    comment(str): Any comments associated with the virtual server.

    appflowlog(str): Log AppFlow records that contain standard NetFlow or IPFIX information, such as time stamps for the
        beginning and end of a flow, packet count, and byte count. Also log records that contain application-level
        information, such as HTTP web addresses, HTTP request methods and response status codes, server response time,
        and latency. Default value: DISABLED Possible values = ENABLED, DISABLED

    icmpvsrresponse(str): Criterion for responding to PING requests sent to this virtual server. If this parameter is set to
        ACTIVE, respond only if the virtual server is available. With the PASSIVE setting, respond even if the virtual
        server is not available. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    rhistate(str): A host route is injected according to the setting on the virtual servers.  * If set to PASSIVE on all the
        virtual servers that share the IP address, the appliance always injects the hostroute.  * If set to ACTIVE on all
        the virtual servers that share the IP address, the appliance injects even if one virtual server is UP.  * If set
        to ACTIVE on some virtual servers and PASSIVE on the others, the appliance injects even if one virtual server set
        to ACTIVE is UP. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    netprofile(str): The name of the network profile. Minimum length = 1 Maximum length = 127

    cginfrahomepageredirect(str): When client requests ShareFile resources and NetScaler Gateway detects that the user is
        unauthenticated or the user session has expired, disabling this option takes the user to the originally requested
        ShareFile resource after authentication (instead of taking the user to the default VPN home page). Default value:
        ENABLED Possible values = ENABLED, DISABLED

    maxloginattempts(int): Maximum number of logon attempts. Minimum value = 1 Maximum value = 255

    failedlogintimeout(int): Number of minutes an account will be locked if user exceeds maximum permissible attempts.
        Minimum value = 1

    l2conn(str): Use Layer 2 parameters (channel number, MAC address, and VLAN ID) in addition to the 4-tuple (;lt;source
        IP;gt;:;lt;source port;gt;::;lt;destination IP;gt;:;lt;destination port;gt;) that is used to identify a
        connection. Allows multiple TCP and non-TCP connections with the same 4-tuple to coexist on the NetScaler
        appliance. Possible values = ON, OFF

    deploymenttype(str): . Default value: 5 Possible values = NONE, ICA_WEBINTERFACE, ICA_STOREFRONT, MOBILITY, WIONNS

    rdpserverprofilename(str): Name of the RDP server profile associated with the vserver. Minimum length = 1 Maximum length
        = 31

    windowsepapluginupgrade(str): Option to set plugin upgrade behaviour for Win. Possible values = Always, Essential, Never

    linuxepapluginupgrade(str): Option to set plugin upgrade behaviour for Linux. Possible values = Always, Essential, Never

    macepapluginupgrade(str): Option to set plugin upgrade behaviour for Mac. Possible values = Always, Essential, Never

    logoutonsmartcardremoval(str): Option to VPN plugin behavior when smartcard or its reader is removed. Default value: OFF
        Possible values = ON, OFF

    userdomains(str): List of user domains specified as comma seperated value.

    authnprofile(str): Authentication Profile entity on virtual server. This entity can be used to offload authentication to
        AAA vserver for multi-factor(nFactor) authentication.

    vserverfqdn(str): Fully qualified domain name for a VPN virtual server. This is used during StoreFront configuration
        generation.

    pcoipvserverprofilename(str): Name of the PCoIP vserver profile associated with the vserver. Minimum length = 1 Maximum
        length = 31

    newname(str): New name for the NetScaler Gateway virtual server. Must begin with an ASCII alphabetic or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters.   The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my server" or my
        server). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver <args>

    '''

    result = {}

    payload = {'vpnvserver': {}}

    if name:
        payload['vpnvserver']['name'] = name

    if servicetype:
        payload['vpnvserver']['servicetype'] = servicetype

    if ipv46:
        payload['vpnvserver']['ipv46'] = ipv46

    if range:
        payload['vpnvserver']['range'] = range

    if port:
        payload['vpnvserver']['port'] = port

    if state:
        payload['vpnvserver']['state'] = state

    if authentication:
        payload['vpnvserver']['authentication'] = authentication

    if doublehop:
        payload['vpnvserver']['doublehop'] = doublehop

    if maxaaausers:
        payload['vpnvserver']['maxaaausers'] = maxaaausers

    if icaonly:
        payload['vpnvserver']['icaonly'] = icaonly

    if icaproxysessionmigration:
        payload['vpnvserver']['icaproxysessionmigration'] = icaproxysessionmigration

    if dtls:
        payload['vpnvserver']['dtls'] = dtls

    if loginonce:
        payload['vpnvserver']['loginonce'] = loginonce

    if advancedepa:
        payload['vpnvserver']['advancedepa'] = advancedepa

    if devicecert:
        payload['vpnvserver']['devicecert'] = devicecert

    if certkeynames:
        payload['vpnvserver']['certkeynames'] = certkeynames

    if downstateflush:
        payload['vpnvserver']['downstateflush'] = downstateflush

    if listenpolicy:
        payload['vpnvserver']['listenpolicy'] = listenpolicy

    if listenpriority:
        payload['vpnvserver']['listenpriority'] = listenpriority

    if tcpprofilename:
        payload['vpnvserver']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['vpnvserver']['httpprofilename'] = httpprofilename

    if comment:
        payload['vpnvserver']['comment'] = comment

    if appflowlog:
        payload['vpnvserver']['appflowlog'] = appflowlog

    if icmpvsrresponse:
        payload['vpnvserver']['icmpvsrresponse'] = icmpvsrresponse

    if rhistate:
        payload['vpnvserver']['rhistate'] = rhistate

    if netprofile:
        payload['vpnvserver']['netprofile'] = netprofile

    if cginfrahomepageredirect:
        payload['vpnvserver']['cginfrahomepageredirect'] = cginfrahomepageredirect

    if maxloginattempts:
        payload['vpnvserver']['maxloginattempts'] = maxloginattempts

    if failedlogintimeout:
        payload['vpnvserver']['failedlogintimeout'] = failedlogintimeout

    if l2conn:
        payload['vpnvserver']['l2conn'] = l2conn

    if deploymenttype:
        payload['vpnvserver']['deploymenttype'] = deploymenttype

    if rdpserverprofilename:
        payload['vpnvserver']['rdpserverprofilename'] = rdpserverprofilename

    if windowsepapluginupgrade:
        payload['vpnvserver']['windowsepapluginupgrade'] = windowsepapluginupgrade

    if linuxepapluginupgrade:
        payload['vpnvserver']['linuxepapluginupgrade'] = linuxepapluginupgrade

    if macepapluginupgrade:
        payload['vpnvserver']['macepapluginupgrade'] = macepapluginupgrade

    if logoutonsmartcardremoval:
        payload['vpnvserver']['logoutonsmartcardremoval'] = logoutonsmartcardremoval

    if userdomains:
        payload['vpnvserver']['userdomains'] = userdomains

    if authnprofile:
        payload['vpnvserver']['authnprofile'] = authnprofile

    if vserverfqdn:
        payload['vpnvserver']['vserverfqdn'] = vserverfqdn

    if pcoipvserverprofilename:
        payload['vpnvserver']['pcoipvserverprofilename'] = pcoipvserverprofilename

    if newname:
        payload['vpnvserver']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/vpnvserver', payload)

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


def add_vpnvserver_aaapreauthenticationpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                      groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                      save=False):
    '''
    Add a new vpnvserver_aaapreauthenticationpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_aaapreauthenticationpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_aaapreauthenticationpolicy_binding': {}}

    if priority:
        payload['vpnvserver_aaapreauthenticationpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_aaapreauthenticationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_aaapreauthenticationpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_aaapreauthenticationpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_aaapreauthenticationpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_aaapreauthenticationpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_aaapreauthenticationpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_aaapreauthenticationpolicy_binding', payload)

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


def add_vpnvserver_appcontroller_binding(appcontroller=None, name=None, save=False):
    '''
    Add a new vpnvserver_appcontroller_binding to the running configuration.

    appcontroller(str): Configured App Controller server in XenMobile deployment.

    name(str): Name of the virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_appcontroller_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_appcontroller_binding': {}}

    if appcontroller:
        payload['vpnvserver_appcontroller_binding']['appcontroller'] = appcontroller

    if name:
        payload['vpnvserver_appcontroller_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/vpnvserver_appcontroller_binding', payload)

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


def add_vpnvserver_appflowpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                         name=None, secondary=None, bindpoint=None, save=False):
    '''
    Add a new vpnvserver_appflowpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST,
        OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_appflowpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_appflowpolicy_binding': {}}

    if priority:
        payload['vpnvserver_appflowpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_appflowpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_appflowpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_appflowpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_appflowpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_appflowpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_appflowpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_appflowpolicy_binding', payload)

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


def add_vpnvserver_auditnslogpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                            groupextraction=None, name=None, secondary=None, bindpoint=None,
                                            save=False):
    '''
    Add a new vpnvserver_auditnslogpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_auditnslogpolicy_binding': {}}

    if priority:
        payload['vpnvserver_auditnslogpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_auditnslogpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_auditnslogpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_auditnslogpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_auditnslogpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_auditnslogpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_auditnslogpolicy_binding', payload)

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


def add_vpnvserver_auditsyslogpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                             groupextraction=None, name=None, secondary=None, bindpoint=None,
                                             save=False):
    '''
    Add a new vpnvserver_auditsyslogpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_auditsyslogpolicy_binding': {}}

    if priority:
        payload['vpnvserver_auditsyslogpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_auditsyslogpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_auditsyslogpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_auditsyslogpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_auditsyslogpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_auditsyslogpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_auditsyslogpolicy_binding', payload)

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


def add_vpnvserver_authenticationcertpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                    groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                    save=False):
    '''
    Add a new vpnvserver_authenticationcertpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationcertpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationcertpolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationcertpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationcertpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationcertpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationcertpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationcertpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationcertpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationcertpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationcertpolicy_binding', payload)

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


def add_vpnvserver_authenticationdfapolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                   groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                   save=False):
    '''
    Add a new vpnvserver_authenticationdfapolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationdfapolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationdfapolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationdfapolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationdfapolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationdfapolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationdfapolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationdfapolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationdfapolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationdfapolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationdfapolicy_binding', payload)

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


def add_vpnvserver_authenticationldappolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                    groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                    save=False):
    '''
    Add a new vpnvserver_authenticationldappolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationldappolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationldappolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationldappolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationldappolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationldappolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationldappolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationldappolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationldappolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationldappolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationldappolicy_binding', payload)

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


def add_vpnvserver_authenticationlocalpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                     groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                     save=False):
    '''
    Add a new vpnvserver_authenticationlocalpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationlocalpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationlocalpolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationlocalpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationlocalpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationlocalpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationlocalpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationlocalpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationlocalpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationlocalpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationlocalpolicy_binding', payload)

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


def add_vpnvserver_authenticationloginschemapolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                           groupextraction=None, name=None, secondary=None,
                                                           bindpoint=None, save=False):
    '''
    Add a new vpnvserver_authenticationloginschemapolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationloginschemapolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationloginschemapolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationloginschemapolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationloginschemapolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationloginschemapolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationloginschemapolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationloginschemapolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationloginschemapolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationloginschemapolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationloginschemapolicy_binding', payload)

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


def add_vpnvserver_authenticationnegotiatepolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                         groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                         save=False):
    '''
    Add a new vpnvserver_authenticationnegotiatepolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationnegotiatepolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationnegotiatepolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationnegotiatepolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationnegotiatepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationnegotiatepolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationnegotiatepolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationnegotiatepolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationnegotiatepolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationnegotiatepolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationnegotiatepolicy_binding', payload)

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


def add_vpnvserver_authenticationpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                save=False):
    '''
    Add a new vpnvserver_authenticationpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationpolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationpolicy_binding', payload)

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


def add_vpnvserver_authenticationradiuspolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                      groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                      save=False):
    '''
    Add a new vpnvserver_authenticationradiuspolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationradiuspolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationradiuspolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationradiuspolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationradiuspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationradiuspolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationradiuspolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationradiuspolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationradiuspolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationradiuspolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationradiuspolicy_binding', payload)

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


def add_vpnvserver_authenticationsamlidppolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                       groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                       save=False):
    '''
    Add a new vpnvserver_authenticationsamlidppolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationsamlidppolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationsamlidppolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationsamlidppolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationsamlidppolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationsamlidppolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationsamlidppolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationsamlidppolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationsamlidppolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationsamlidppolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationsamlidppolicy_binding', payload)

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


def add_vpnvserver_authenticationsamlpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                    groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                    save=False):
    '''
    Add a new vpnvserver_authenticationsamlpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationsamlpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationsamlpolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationsamlpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationsamlpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationsamlpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationsamlpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationsamlpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationsamlpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationsamlpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationsamlpolicy_binding', payload)

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


def add_vpnvserver_authenticationtacacspolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                      groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                      save=False):
    '''
    Add a new vpnvserver_authenticationtacacspolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationtacacspolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationtacacspolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationtacacspolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationtacacspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationtacacspolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationtacacspolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationtacacspolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationtacacspolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationtacacspolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationtacacspolicy_binding', payload)

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


def add_vpnvserver_authenticationwebauthpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                       groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                       save=False):
    '''
    Add a new vpnvserver_authenticationwebauthpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_authenticationwebauthpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_authenticationwebauthpolicy_binding': {}}

    if priority:
        payload['vpnvserver_authenticationwebauthpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_authenticationwebauthpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_authenticationwebauthpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_authenticationwebauthpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_authenticationwebauthpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_authenticationwebauthpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_authenticationwebauthpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_authenticationwebauthpolicy_binding', payload)

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


def add_vpnvserver_cachepolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                       name=None, secondary=None, bindpoint=None, save=False):
    '''
    Add a new vpnvserver_cachepolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_cachepolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_cachepolicy_binding': {}}

    if priority:
        payload['vpnvserver_cachepolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_cachepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_cachepolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_cachepolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_cachepolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_cachepolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_cachepolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_cachepolicy_binding', payload)

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


def add_vpnvserver_cspolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                    name=None, secondary=None, bindpoint=None, save=False):
    '''
    Add a new vpnvserver_cspolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_cspolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_cspolicy_binding': {}}

    if priority:
        payload['vpnvserver_cspolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_cspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_cspolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_cspolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_cspolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_cspolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_cspolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_cspolicy_binding', payload)

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


def add_vpnvserver_feopolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                     name=None, secondary=None, bindpoint=None, save=False):
    '''
    Add a new vpnvserver_feopolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): Name of a policy to bind to the virtual server (for example, the name of an authentication, session, or
        endpoint analysis policy). Minimum length = 1

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST,
        OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_feopolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_feopolicy_binding': {}}

    if priority:
        payload['vpnvserver_feopolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_feopolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_feopolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_feopolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_feopolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_feopolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_feopolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_feopolicy_binding', payload)

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


def add_vpnvserver_icapolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                     name=None, secondary=None, bindpoint=None, save=False):
    '''
    Add a new vpnvserver_icapolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_icapolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_icapolicy_binding': {}}

    if priority:
        payload['vpnvserver_icapolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_icapolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_icapolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_icapolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_icapolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_icapolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_icapolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_icapolicy_binding', payload)

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


def add_vpnvserver_intranetip6_binding(intranetip6=None, numaddr=None, name=None, save=False):
    '''
    Add a new vpnvserver_intranetip6_binding to the running configuration.

    intranetip6(str): The network id for the range of intranet IP6 addresses or individual intranet ip to be bound to the
        vserver.

    numaddr(int): The number of ipv6 addresses.

    name(str): Name of the virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_intranetip6_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_intranetip6_binding': {}}

    if intranetip6:
        payload['vpnvserver_intranetip6_binding']['intranetip6'] = intranetip6

    if numaddr:
        payload['vpnvserver_intranetip6_binding']['numaddr'] = numaddr

    if name:
        payload['vpnvserver_intranetip6_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/vpnvserver_intranetip6_binding', payload)

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


def add_vpnvserver_intranetip_binding(name=None, intranetip=None, netmask=None, save=False):
    '''
    Add a new vpnvserver_intranetip_binding to the running configuration.

    name(str): Name of the virtual server. Minimum length = 1

    intranetip(str): The network ID for the range of intranet IP addresses or individual intranet IP addresses to be bound to
        the virtual server.

    netmask(str): The netmask of the intranet IP address or range.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_intranetip_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_intranetip_binding': {}}

    if name:
        payload['vpnvserver_intranetip_binding']['name'] = name

    if intranetip:
        payload['vpnvserver_intranetip_binding']['intranetip'] = intranetip

    if netmask:
        payload['vpnvserver_intranetip_binding']['netmask'] = netmask

    execution = __proxy__['citrixns.post']('config/vpnvserver_intranetip_binding', payload)

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


def add_vpnvserver_responderpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                           name=None, secondary=None, bindpoint=None, save=False):
    '''
    Add a new vpnvserver_responderpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_responderpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_responderpolicy_binding': {}}

    if priority:
        payload['vpnvserver_responderpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_responderpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_responderpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_responderpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_responderpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_responderpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_responderpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_responderpolicy_binding', payload)

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


def add_vpnvserver_rewritepolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                         name=None, secondary=None, bindpoint=None, save=False):
    '''
    Add a new vpnvserver_rewritepolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST,
        OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_rewritepolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_rewritepolicy_binding': {}}

    if priority:
        payload['vpnvserver_rewritepolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_rewritepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_rewritepolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_rewritepolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_rewritepolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_rewritepolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_rewritepolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_rewritepolicy_binding', payload)

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


def add_vpnvserver_sharefileserver_binding(name=None, sharefile=None, save=False):
    '''
    Add a new vpnvserver_sharefileserver_binding to the running configuration.

    name(str): Name of the virtual server. Minimum length = 1

    sharefile(str): Configured ShareFile server in XenMobile deployment. Format IP:PORT / FQDN:PORT.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_sharefileserver_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_sharefileserver_binding': {}}

    if name:
        payload['vpnvserver_sharefileserver_binding']['name'] = name

    if sharefile:
        payload['vpnvserver_sharefileserver_binding']['sharefile'] = sharefile

    execution = __proxy__['citrixns.post']('config/vpnvserver_sharefileserver_binding', payload)

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


def add_vpnvserver_staserver_binding(name=None, staaddresstype=None, staserver=None, save=False):
    '''
    Add a new vpnvserver_staserver_binding to the running configuration.

    name(str): Name of the virtual server. Minimum length = 1

    staaddresstype(str): Type of the STA server address(ipv4/v6). Possible values = IPV4, IPV6

    staserver(str): Configured Secure Ticketing Authority (STA) server.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_staserver_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_staserver_binding': {}}

    if name:
        payload['vpnvserver_staserver_binding']['name'] = name

    if staaddresstype:
        payload['vpnvserver_staserver_binding']['staaddresstype'] = staaddresstype

    if staserver:
        payload['vpnvserver_staserver_binding']['staserver'] = staserver

    execution = __proxy__['citrixns.post']('config/vpnvserver_staserver_binding', payload)

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


def add_vpnvserver_vpnclientlessaccesspolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                     groupextraction=None, name=None, secondary=None, bindpoint=None,
                                                     save=False):
    '''
    Add a new vpnvserver_vpnclientlessaccesspolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Next priority expression.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST,
        OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpnclientlessaccesspolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpnclientlessaccesspolicy_binding': {}}

    if priority:
        payload['vpnvserver_vpnclientlessaccesspolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_vpnclientlessaccesspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_vpnclientlessaccesspolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_vpnclientlessaccesspolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_vpnclientlessaccesspolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_vpnclientlessaccesspolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_vpnclientlessaccesspolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpnclientlessaccesspolicy_binding', payload)

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


def add_vpnvserver_vpnepaprofile_binding(name=None, epaprofile=None, epaprofileoptional=None, save=False):
    '''
    Add a new vpnvserver_vpnepaprofile_binding to the running configuration.

    name(str): Name of the virtual server. Minimum length = 1

    epaprofile(str): Advanced EPA profile to bind.

    epaprofileoptional(bool): Mark the EPA profile optional for preauthentication EPA profile. User would be shown a logon
        page even if the EPA profile fails to evaluate.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpnepaprofile_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpnepaprofile_binding': {}}

    if name:
        payload['vpnvserver_vpnepaprofile_binding']['name'] = name

    if epaprofile:
        payload['vpnvserver_vpnepaprofile_binding']['epaprofile'] = epaprofile

    if epaprofileoptional:
        payload['vpnvserver_vpnepaprofile_binding']['epaprofileoptional'] = epaprofileoptional

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpnepaprofile_binding', payload)

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


def add_vpnvserver_vpneula_binding(eula=None, name=None, save=False):
    '''
    Add a new vpnvserver_vpneula_binding to the running configuration.

    eula(str): Name of the EULA bound to VPN vserver.

    name(str): Name of the virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpneula_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpneula_binding': {}}

    if eula:
        payload['vpnvserver_vpneula_binding']['eula'] = eula

    if name:
        payload['vpnvserver_vpneula_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpneula_binding', payload)

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


def add_vpnvserver_vpnintranetapplication_binding(name=None, intranetapplication=None, save=False):
    '''
    Add a new vpnvserver_vpnintranetapplication_binding to the running configuration.

    name(str): Name of the virtual server. Minimum length = 1

    intranetapplication(str): The intranet VPN application.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpnintranetapplication_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpnintranetapplication_binding': {}}

    if name:
        payload['vpnvserver_vpnintranetapplication_binding']['name'] = name

    if intranetapplication:
        payload['vpnvserver_vpnintranetapplication_binding']['intranetapplication'] = intranetapplication

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpnintranetapplication_binding', payload)

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


def add_vpnvserver_vpnnexthopserver_binding(name=None, nexthopserver=None, save=False):
    '''
    Add a new vpnvserver_vpnnexthopserver_binding to the running configuration.

    name(str): Name of the virtual server. Minimum length = 1

    nexthopserver(str): The name of the next hop server bound to the VPN virtual server.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpnnexthopserver_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpnnexthopserver_binding': {}}

    if name:
        payload['vpnvserver_vpnnexthopserver_binding']['name'] = name

    if nexthopserver:
        payload['vpnvserver_vpnnexthopserver_binding']['nexthopserver'] = nexthopserver

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpnnexthopserver_binding', payload)

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


def add_vpnvserver_vpnportaltheme_binding(name=None, portaltheme=None, save=False):
    '''
    Add a new vpnvserver_vpnportaltheme_binding to the running configuration.

    name(str): Name of the virtual server. Minimum length = 1

    portaltheme(str): Name of the portal theme bound to VPN vserver.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpnportaltheme_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpnportaltheme_binding': {}}

    if name:
        payload['vpnvserver_vpnportaltheme_binding']['name'] = name

    if portaltheme:
        payload['vpnvserver_vpnportaltheme_binding']['portaltheme'] = portaltheme

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpnportaltheme_binding', payload)

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


def add_vpnvserver_vpnsessionpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                            groupextraction=None, name=None, secondary=None, bindpoint=None,
                                            save=False):
    '''
    Add a new vpnvserver_vpnsessionpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpnsessionpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpnsessionpolicy_binding': {}}

    if priority:
        payload['vpnvserver_vpnsessionpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_vpnsessionpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_vpnsessionpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_vpnsessionpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_vpnsessionpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_vpnsessionpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_vpnsessionpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpnsessionpolicy_binding', payload)

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


def add_vpnvserver_vpntrafficpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                            groupextraction=None, name=None, secondary=None, bindpoint=None,
                                            save=False):
    '''
    Add a new vpnvserver_vpntrafficpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the number, the higher the priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Applicable only to advance vpn session policy. Expression or other value specifying the next
        policy to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax or
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The name of the policy, if any, bound to the VPN virtual server.

    groupextraction(bool): Binds the authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    name(str): Name of the virtual server. Minimum length = 1

    secondary(bool): Binds the authentication policy as the secondary policy to use in a two-factor configuration. A user
        must then authenticate not only via a primary authentication method but also via a secondary authentication
        method. User groups are aggregated across both. The user name must be exactly the same for both authentication
        methods, but they can require different passwords.

    bindpoint(str): Bind point to which to bind the policy. Applies only to rewrite and cache policies. If you do not set
        this parameter, the policy is bound to REQ_DEFAULT or RES_DEFAULT, depending on whether the policy rule is a
        response-time or a request-time expression. Possible values = REQUEST, RESPONSE, ICA_REQUEST, OTHERTCP_REQUEST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpntrafficpolicy_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpntrafficpolicy_binding': {}}

    if priority:
        payload['vpnvserver_vpntrafficpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['vpnvserver_vpntrafficpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['vpnvserver_vpntrafficpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['vpnvserver_vpntrafficpolicy_binding']['groupextraction'] = groupextraction

    if name:
        payload['vpnvserver_vpntrafficpolicy_binding']['name'] = name

    if secondary:
        payload['vpnvserver_vpntrafficpolicy_binding']['secondary'] = secondary

    if bindpoint:
        payload['vpnvserver_vpntrafficpolicy_binding']['bindpoint'] = bindpoint

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpntrafficpolicy_binding', payload)

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


def add_vpnvserver_vpnurl_binding(urlname=None, name=None, save=False):
    '''
    Add a new vpnvserver_vpnurl_binding to the running configuration.

    urlname(str): The intranet URL.

    name(str): Name of the virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.add_vpnvserver_vpnurl_binding <args>

    '''

    result = {}

    payload = {'vpnvserver_vpnurl_binding': {}}

    if urlname:
        payload['vpnvserver_vpnurl_binding']['urlname'] = urlname

    if name:
        payload['vpnvserver_vpnurl_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/vpnvserver_vpnurl_binding', payload)

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


def disable_vpnvserver(name=None, save=False):
    '''
    Disables a vpnvserver matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.disable_vpnvserver name=foo

    '''

    result = {}

    payload = {'vpnvserver': {}}

    if name:
        payload['vpnvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/vpnvserver?action=disable', payload)

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


def enable_vpnvserver(name=None, save=False):
    '''
    Enables a vpnvserver matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.enable_vpnvserver name=foo

    '''

    result = {}

    payload = {'vpnvserver': {}}

    if name:
        payload['vpnvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/vpnvserver?action=enable', payload)

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


def get_vpnalwaysonprofile(name=None, networkaccessonvpnfailure=None, clientcontrol=None, locationbasedvpn=None):
    '''
    Show the running configuration for the vpnalwaysonprofile config key.

    name(str): Filters results that only match the name field.

    networkaccessonvpnfailure(str): Filters results that only match the networkaccessonvpnfailure field.

    clientcontrol(str): Filters results that only match the clientcontrol field.

    locationbasedvpn(str): Filters results that only match the locationbasedvpn field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnalwaysonprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if networkaccessonvpnfailure:
        search_filter.append(['networkaccessonvpnfailure', networkaccessonvpnfailure])

    if clientcontrol:
        search_filter.append(['clientcontrol', clientcontrol])

    if locationbasedvpn:
        search_filter.append(['locationbasedvpn', locationbasedvpn])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnalwaysonprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnalwaysonprofile')

    return response


def get_vpnclientlessaccesspolicy(name=None, rule=None, profilename=None):
    '''
    Show the running configuration for the vpnclientlessaccesspolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    profilename(str): Filters results that only match the profilename field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnclientlessaccesspolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if profilename:
        search_filter.append(['profilename', profilename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnclientlessaccesspolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnclientlessaccesspolicy')

    return response


def get_vpnclientlessaccesspolicy_binding():
    '''
    Show the running configuration for the vpnclientlessaccesspolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnclientlessaccesspolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnclientlessaccesspolicy_binding'), 'vpnclientlessaccesspolicy_binding')

    return response


def get_vpnclientlessaccesspolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the vpnclientlessaccesspolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnclientlessaccesspolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnclientlessaccesspolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnclientlessaccesspolicy_vpnglobal_binding')

    return response


def get_vpnclientlessaccesspolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the vpnclientlessaccesspolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnclientlessaccesspolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnclientlessaccesspolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnclientlessaccesspolicy_vpnvserver_binding')

    return response


def get_vpnclientlessaccessprofile(profilename=None, urlrewritepolicylabel=None, javascriptrewritepolicylabel=None,
                                   reqhdrrewritepolicylabel=None, reshdrrewritepolicylabel=None,
                                   regexforfindingurlinjavascript=None, regexforfindingurlincss=None,
                                   regexforfindingurlinxcomponent=None, regexforfindingurlinxml=None,
                                   regexforfindingcustomurls=None, clientconsumedcookies=None,
                                   requirepersistentcookie=None):
    '''
    Show the running configuration for the vpnclientlessaccessprofile config key.

    profilename(str): Filters results that only match the profilename field.

    urlrewritepolicylabel(str): Filters results that only match the urlrewritepolicylabel field.

    javascriptrewritepolicylabel(str): Filters results that only match the javascriptrewritepolicylabel field.

    reqhdrrewritepolicylabel(str): Filters results that only match the reqhdrrewritepolicylabel field.

    reshdrrewritepolicylabel(str): Filters results that only match the reshdrrewritepolicylabel field.

    regexforfindingurlinjavascript(str): Filters results that only match the regexforfindingurlinjavascript field.

    regexforfindingurlincss(str): Filters results that only match the regexforfindingurlincss field.

    regexforfindingurlinxcomponent(str): Filters results that only match the regexforfindingurlinxcomponent field.

    regexforfindingurlinxml(str): Filters results that only match the regexforfindingurlinxml field.

    regexforfindingcustomurls(str): Filters results that only match the regexforfindingcustomurls field.

    clientconsumedcookies(str): Filters results that only match the clientconsumedcookies field.

    requirepersistentcookie(str): Filters results that only match the requirepersistentcookie field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnclientlessaccessprofile

    '''

    search_filter = []

    if profilename:
        search_filter.append(['profilename', profilename])

    if urlrewritepolicylabel:
        search_filter.append(['urlrewritepolicylabel', urlrewritepolicylabel])

    if javascriptrewritepolicylabel:
        search_filter.append(['javascriptrewritepolicylabel', javascriptrewritepolicylabel])

    if reqhdrrewritepolicylabel:
        search_filter.append(['reqhdrrewritepolicylabel', reqhdrrewritepolicylabel])

    if reshdrrewritepolicylabel:
        search_filter.append(['reshdrrewritepolicylabel', reshdrrewritepolicylabel])

    if regexforfindingurlinjavascript:
        search_filter.append(['regexforfindingurlinjavascript', regexforfindingurlinjavascript])

    if regexforfindingurlincss:
        search_filter.append(['regexforfindingurlincss', regexforfindingurlincss])

    if regexforfindingurlinxcomponent:
        search_filter.append(['regexforfindingurlinxcomponent', regexforfindingurlinxcomponent])

    if regexforfindingurlinxml:
        search_filter.append(['regexforfindingurlinxml', regexforfindingurlinxml])

    if regexforfindingcustomurls:
        search_filter.append(['regexforfindingcustomurls', regexforfindingcustomurls])

    if clientconsumedcookies:
        search_filter.append(['clientconsumedcookies', clientconsumedcookies])

    if requirepersistentcookie:
        search_filter.append(['requirepersistentcookie', requirepersistentcookie])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnclientlessaccessprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnclientlessaccessprofile')

    return response


def get_vpnepaprofile(name=None, filename=None, data=None):
    '''
    Show the running configuration for the vpnepaprofile config key.

    name(str): Filters results that only match the name field.

    filename(str): Filters results that only match the filename field.

    data(str): Filters results that only match the data field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnepaprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if filename:
        search_filter.append(['filename', filename])

    if data:
        search_filter.append(['data', data])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnepaprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnepaprofile')

    return response


def get_vpneula(name=None):
    '''
    Show the running configuration for the vpneula config key.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpneula

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpneula{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpneula')

    return response


def get_vpnformssoaction(name=None, actionurl=None, userfield=None, passwdfield=None, ssosuccessrule=None,
                         namevaluepair=None, responsesize=None, nvtype=None, submitmethod=None):
    '''
    Show the running configuration for the vpnformssoaction config key.

    name(str): Filters results that only match the name field.

    actionurl(str): Filters results that only match the actionurl field.

    userfield(str): Filters results that only match the userfield field.

    passwdfield(str): Filters results that only match the passwdfield field.

    ssosuccessrule(str): Filters results that only match the ssosuccessrule field.

    namevaluepair(str): Filters results that only match the namevaluepair field.

    responsesize(int): Filters results that only match the responsesize field.

    nvtype(str): Filters results that only match the nvtype field.

    submitmethod(str): Filters results that only match the submitmethod field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnformssoaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if actionurl:
        search_filter.append(['actionurl', actionurl])

    if userfield:
        search_filter.append(['userfield', userfield])

    if passwdfield:
        search_filter.append(['passwdfield', passwdfield])

    if ssosuccessrule:
        search_filter.append(['ssosuccessrule', ssosuccessrule])

    if namevaluepair:
        search_filter.append(['namevaluepair', namevaluepair])

    if responsesize:
        search_filter.append(['responsesize', responsesize])

    if nvtype:
        search_filter.append(['nvtype', nvtype])

    if submitmethod:
        search_filter.append(['submitmethod', submitmethod])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnformssoaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnformssoaction')

    return response


def get_vpnglobal_appcontroller_binding(gotopriorityexpression=None, appcontroller=None):
    '''
    Show the running configuration for the vpnglobal_appcontroller_binding config key.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    appcontroller(str): Filters results that only match the appcontroller field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_appcontroller_binding

    '''

    search_filter = []

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if appcontroller:
        search_filter.append(['appcontroller', appcontroller])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_appcontroller_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_appcontroller_binding')

    return response


def get_vpnglobal_auditnslogpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None, secondary=None,
                                           groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_auditnslogpolicy_binding')

    return response


def get_vpnglobal_auditsyslogpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None, secondary=None,
                                            groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_auditsyslogpolicy_binding')

    return response


def get_vpnglobal_authenticationcertpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                   secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_authenticationcertpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_authenticationcertpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_authenticationcertpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_authenticationcertpolicy_binding')

    return response


def get_vpnglobal_authenticationldappolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                   secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_authenticationldappolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_authenticationldappolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_authenticationldappolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_authenticationldappolicy_binding')

    return response


def get_vpnglobal_authenticationlocalpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                    secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_authenticationlocalpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_authenticationlocalpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_authenticationlocalpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_authenticationlocalpolicy_binding')

    return response


def get_vpnglobal_authenticationnegotiatepolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                        secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_authenticationnegotiatepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_authenticationnegotiatepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_authenticationnegotiatepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_authenticationnegotiatepolicy_binding')

    return response


def get_vpnglobal_authenticationpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                               secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_authenticationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_authenticationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_authenticationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_authenticationpolicy_binding')

    return response


def get_vpnglobal_authenticationradiuspolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                     secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_authenticationradiuspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_authenticationradiuspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_authenticationradiuspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_authenticationradiuspolicy_binding')

    return response


def get_vpnglobal_authenticationsamlpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                   secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_authenticationsamlpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_authenticationsamlpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_authenticationsamlpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_authenticationsamlpolicy_binding')

    return response


def get_vpnglobal_authenticationtacacspolicy_binding(priority=None, policyname=None, gotopriorityexpression=None,
                                                     secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_authenticationtacacspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_authenticationtacacspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_authenticationtacacspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_authenticationtacacspolicy_binding')

    return response


def get_vpnglobal_binding():
    '''
    Show the running configuration for the vpnglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_binding'), 'vpnglobal_binding')

    return response


def get_vpnglobal_domain_binding(intranetdomain=None, gotopriorityexpression=None):
    '''
    Show the running configuration for the vpnglobal_domain_binding config key.

    intranetdomain(str): Filters results that only match the intranetdomain field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_domain_binding

    '''

    search_filter = []

    if intranetdomain:
        search_filter.append(['intranetdomain', intranetdomain])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_domain_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_domain_binding')

    return response


def get_vpnglobal_intranetip6_binding(intranetip6=None, gotopriorityexpression=None, numaddr=None):
    '''
    Show the running configuration for the vpnglobal_intranetip6_binding config key.

    intranetip6(str): Filters results that only match the intranetip6 field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    numaddr(int): Filters results that only match the numaddr field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_intranetip6_binding

    '''

    search_filter = []

    if intranetip6:
        search_filter.append(['intranetip6', intranetip6])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if numaddr:
        search_filter.append(['numaddr', numaddr])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_intranetip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_intranetip6_binding')

    return response


def get_vpnglobal_intranetip_binding(intranetip=None, gotopriorityexpression=None, netmask=None):
    '''
    Show the running configuration for the vpnglobal_intranetip_binding config key.

    intranetip(str): Filters results that only match the intranetip field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    netmask(str): Filters results that only match the netmask field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_intranetip_binding

    '''

    search_filter = []

    if intranetip:
        search_filter.append(['intranetip', intranetip])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if netmask:
        search_filter.append(['netmask', netmask])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_intranetip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_intranetip_binding')

    return response


def get_vpnglobal_sharefileserver_binding(gotopriorityexpression=None, sharefile=None):
    '''
    Show the running configuration for the vpnglobal_sharefileserver_binding config key.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    sharefile(str): Filters results that only match the sharefile field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_sharefileserver_binding

    '''

    search_filter = []

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if sharefile:
        search_filter.append(['sharefile', sharefile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_sharefileserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_sharefileserver_binding')

    return response


def get_vpnglobal_staserver_binding(staserver=None, gotopriorityexpression=None, staaddresstype=None):
    '''
    Show the running configuration for the vpnglobal_staserver_binding config key.

    staserver(str): Filters results that only match the staserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    staaddresstype(str): Filters results that only match the staaddresstype field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_staserver_binding

    '''

    search_filter = []

    if staserver:
        search_filter.append(['staserver', staserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if staaddresstype:
        search_filter.append(['staaddresstype', staaddresstype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_staserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_staserver_binding')

    return response


def get_vpnglobal_vpnclientlessaccesspolicy_binding(priority=None, globalbindtype=None, builtin=None, policyname=None,
                                                    gotopriorityexpression=None, secondary=None, ns_type=None,
                                                    groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_vpnclientlessaccesspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    ns_type(str): Filters results that only match the type field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_vpnclientlessaccesspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if ns_type:
        search_filter.append(['type', ns_type])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_vpnclientlessaccesspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_vpnclientlessaccesspolicy_binding')

    return response


def get_vpnglobal_vpneula_binding(eula=None, gotopriorityexpression=None):
    '''
    Show the running configuration for the vpnglobal_vpneula_binding config key.

    eula(str): Filters results that only match the eula field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_vpneula_binding

    '''

    search_filter = []

    if eula:
        search_filter.append(['eula', eula])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_vpneula_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_vpneula_binding')

    return response


def get_vpnglobal_vpnintranetapplication_binding(gotopriorityexpression=None, intranetapplication=None):
    '''
    Show the running configuration for the vpnglobal_vpnintranetapplication_binding config key.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    intranetapplication(str): Filters results that only match the intranetapplication field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_vpnintranetapplication_binding

    '''

    search_filter = []

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if intranetapplication:
        search_filter.append(['intranetapplication', intranetapplication])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_vpnintranetapplication_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_vpnintranetapplication_binding')

    return response


def get_vpnglobal_vpnnexthopserver_binding(gotopriorityexpression=None, nexthopserver=None):
    '''
    Show the running configuration for the vpnglobal_vpnnexthopserver_binding config key.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    nexthopserver(str): Filters results that only match the nexthopserver field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_vpnnexthopserver_binding

    '''

    search_filter = []

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if nexthopserver:
        search_filter.append(['nexthopserver', nexthopserver])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_vpnnexthopserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_vpnnexthopserver_binding')

    return response


def get_vpnglobal_vpnportaltheme_binding(gotopriorityexpression=None, portaltheme=None):
    '''
    Show the running configuration for the vpnglobal_vpnportaltheme_binding config key.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    portaltheme(str): Filters results that only match the portaltheme field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_vpnportaltheme_binding

    '''

    search_filter = []

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if portaltheme:
        search_filter.append(['portaltheme', portaltheme])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_vpnportaltheme_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_vpnportaltheme_binding')

    return response


def get_vpnglobal_vpnsessionpolicy_binding(priority=None, builtin=None, policyname=None, gotopriorityexpression=None,
                                           secondary=None, groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_vpnsessionpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_vpnsessionpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_vpnsessionpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_vpnsessionpolicy_binding')

    return response


def get_vpnglobal_vpntrafficpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None, secondary=None,
                                           groupextraction=None):
    '''
    Show the running configuration for the vpnglobal_vpntrafficpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_vpntrafficpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_vpntrafficpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_vpntrafficpolicy_binding')

    return response


def get_vpnglobal_vpnurl_binding(urlname=None, gotopriorityexpression=None):
    '''
    Show the running configuration for the vpnglobal_vpnurl_binding config key.

    urlname(str): Filters results that only match the urlname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnglobal_vpnurl_binding

    '''

    search_filter = []

    if urlname:
        search_filter.append(['urlname', urlname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnglobal_vpnurl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnglobal_vpnurl_binding')

    return response


def get_vpnicaconnection(username=None, transproto=None, nodeid=None):
    '''
    Show the running configuration for the vpnicaconnection config key.

    username(str): Filters results that only match the username field.

    transproto(str): Filters results that only match the transproto field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnicaconnection

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if transproto:
        search_filter.append(['transproto', transproto])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnicaconnection{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnicaconnection')

    return response


def get_vpnicadtlsconnection(username=None, nodeid=None):
    '''
    Show the running configuration for the vpnicadtlsconnection config key.

    username(str): Filters results that only match the username field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnicadtlsconnection

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnicadtlsconnection{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnicadtlsconnection')

    return response


def get_vpnintranetapplication(intranetapplication=None, protocol=None, destip=None, netmask=None, iprange=None,
                               hostname=None, clientapplication=None, spoofiip=None, destport=None, interception=None,
                               srcip=None, srcport=None):
    '''
    Show the running configuration for the vpnintranetapplication config key.

    intranetapplication(str): Filters results that only match the intranetapplication field.

    protocol(str): Filters results that only match the protocol field.

    destip(str): Filters results that only match the destip field.

    netmask(str): Filters results that only match the netmask field.

    iprange(str): Filters results that only match the iprange field.

    hostname(str): Filters results that only match the hostname field.

    clientapplication(list(str)): Filters results that only match the clientapplication field.

    spoofiip(str): Filters results that only match the spoofiip field.

    destport(str): Filters results that only match the destport field.

    interception(str): Filters results that only match the interception field.

    srcip(str): Filters results that only match the srcip field.

    srcport(int): Filters results that only match the srcport field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnintranetapplication

    '''

    search_filter = []

    if intranetapplication:
        search_filter.append(['intranetapplication', intranetapplication])

    if protocol:
        search_filter.append(['protocol', protocol])

    if destip:
        search_filter.append(['destip', destip])

    if netmask:
        search_filter.append(['netmask', netmask])

    if iprange:
        search_filter.append(['iprange', iprange])

    if hostname:
        search_filter.append(['hostname', hostname])

    if clientapplication:
        search_filter.append(['clientapplication', clientapplication])

    if spoofiip:
        search_filter.append(['spoofiip', spoofiip])

    if destport:
        search_filter.append(['destport', destport])

    if interception:
        search_filter.append(['interception', interception])

    if srcip:
        search_filter.append(['srcip', srcip])

    if srcport:
        search_filter.append(['srcport', srcport])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnintranetapplication{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnintranetapplication')

    return response


def get_vpnnexthopserver(name=None, nexthopip=None, nexthopfqdn=None, resaddresstype=None, nexthopport=None,
                         secure=None):
    '''
    Show the running configuration for the vpnnexthopserver config key.

    name(str): Filters results that only match the name field.

    nexthopip(str): Filters results that only match the nexthopip field.

    nexthopfqdn(str): Filters results that only match the nexthopfqdn field.

    resaddresstype(str): Filters results that only match the resaddresstype field.

    nexthopport(int): Filters results that only match the nexthopport field.

    secure(str): Filters results that only match the secure field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnnexthopserver

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if nexthopip:
        search_filter.append(['nexthopip', nexthopip])

    if nexthopfqdn:
        search_filter.append(['nexthopfqdn', nexthopfqdn])

    if resaddresstype:
        search_filter.append(['resaddresstype', resaddresstype])

    if nexthopport:
        search_filter.append(['nexthopport', nexthopport])

    if secure:
        search_filter.append(['secure', secure])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnnexthopserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnnexthopserver')

    return response


def get_vpnparameter():
    '''
    Show the running configuration for the vpnparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnparameter'), 'vpnparameter')

    return response


def get_vpnpcoipconnection(username=None, nodeid=None):
    '''
    Show the running configuration for the vpnpcoipconnection config key.

    username(str): Filters results that only match the username field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnpcoipconnection

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnpcoipconnection{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnpcoipconnection')

    return response


def get_vpnpcoipprofile(name=None, conserverurl=None, icvverification=None, sessionidletimeout=None):
    '''
    Show the running configuration for the vpnpcoipprofile config key.

    name(str): Filters results that only match the name field.

    conserverurl(str): Filters results that only match the conserverurl field.

    icvverification(str): Filters results that only match the icvverification field.

    sessionidletimeout(int): Filters results that only match the sessionidletimeout field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnpcoipprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if conserverurl:
        search_filter.append(['conserverurl', conserverurl])

    if icvverification:
        search_filter.append(['icvverification', icvverification])

    if sessionidletimeout:
        search_filter.append(['sessionidletimeout', sessionidletimeout])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnpcoipprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnpcoipprofile')

    return response


def get_vpnpcoipvserverprofile(name=None, logindomain=None, udpport=None):
    '''
    Show the running configuration for the vpnpcoipvserverprofile config key.

    name(str): Filters results that only match the name field.

    logindomain(str): Filters results that only match the logindomain field.

    udpport(int): Filters results that only match the udpport field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnpcoipvserverprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if logindomain:
        search_filter.append(['logindomain', logindomain])

    if udpport:
        search_filter.append(['udpport', udpport])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnpcoipvserverprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnpcoipvserverprofile')

    return response


def get_vpnportaltheme(name=None, basetheme=None):
    '''
    Show the running configuration for the vpnportaltheme config key.

    name(str): Filters results that only match the name field.

    basetheme(str): Filters results that only match the basetheme field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnportaltheme

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if basetheme:
        search_filter.append(['basetheme', basetheme])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnportaltheme{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnportaltheme')

    return response


def get_vpnsamlssoprofile(name=None, samlsigningcertname=None, assertionconsumerserviceurl=None, relaystaterule=None,
                          sendpassword=None, samlissuername=None, signaturealg=None, digestmethod=None, audience=None,
                          nameidformat=None, nameidexpr=None, attribute1=None, attribute1expr=None,
                          attribute1friendlyname=None, attribute1format=None, attribute2=None, attribute2expr=None,
                          attribute2friendlyname=None, attribute2format=None, attribute3=None, attribute3expr=None,
                          attribute3friendlyname=None, attribute3format=None, attribute4=None, attribute4expr=None,
                          attribute4friendlyname=None, attribute4format=None, attribute5=None, attribute5expr=None,
                          attribute5friendlyname=None, attribute5format=None, attribute6=None, attribute6expr=None,
                          attribute6friendlyname=None, attribute6format=None, attribute7=None, attribute7expr=None,
                          attribute7friendlyname=None, attribute7format=None, attribute8=None, attribute8expr=None,
                          attribute8friendlyname=None, attribute8format=None, attribute9=None, attribute9expr=None,
                          attribute9friendlyname=None, attribute9format=None, attribute10=None, attribute10expr=None,
                          attribute10friendlyname=None, attribute10format=None, attribute11=None, attribute11expr=None,
                          attribute11friendlyname=None, attribute11format=None, attribute12=None, attribute12expr=None,
                          attribute12friendlyname=None, attribute12format=None, attribute13=None, attribute13expr=None,
                          attribute13friendlyname=None, attribute13format=None, attribute14=None, attribute14expr=None,
                          attribute14friendlyname=None, attribute14format=None, attribute15=None, attribute15expr=None,
                          attribute15friendlyname=None, attribute15format=None, attribute16=None, attribute16expr=None,
                          attribute16friendlyname=None, attribute16format=None, encryptassertion=None,
                          samlspcertname=None, encryptionalgorithm=None, skewtime=None):
    '''
    Show the running configuration for the vpnsamlssoprofile config key.

    name(str): Filters results that only match the name field.

    samlsigningcertname(str): Filters results that only match the samlsigningcertname field.

    assertionconsumerserviceurl(str): Filters results that only match the assertionconsumerserviceurl field.

    relaystaterule(str): Filters results that only match the relaystaterule field.

    sendpassword(str): Filters results that only match the sendpassword field.

    samlissuername(str): Filters results that only match the samlissuername field.

    signaturealg(str): Filters results that only match the signaturealg field.

    digestmethod(str): Filters results that only match the digestmethod field.

    audience(str): Filters results that only match the audience field.

    nameidformat(str): Filters results that only match the nameidformat field.

    nameidexpr(str): Filters results that only match the nameidexpr field.

    attribute1(str): Filters results that only match the attribute1 field.

    attribute1expr(str): Filters results that only match the attribute1expr field.

    attribute1friendlyname(str): Filters results that only match the attribute1friendlyname field.

    attribute1format(str): Filters results that only match the attribute1format field.

    attribute2(str): Filters results that only match the attribute2 field.

    attribute2expr(str): Filters results that only match the attribute2expr field.

    attribute2friendlyname(str): Filters results that only match the attribute2friendlyname field.

    attribute2format(str): Filters results that only match the attribute2format field.

    attribute3(str): Filters results that only match the attribute3 field.

    attribute3expr(str): Filters results that only match the attribute3expr field.

    attribute3friendlyname(str): Filters results that only match the attribute3friendlyname field.

    attribute3format(str): Filters results that only match the attribute3format field.

    attribute4(str): Filters results that only match the attribute4 field.

    attribute4expr(str): Filters results that only match the attribute4expr field.

    attribute4friendlyname(str): Filters results that only match the attribute4friendlyname field.

    attribute4format(str): Filters results that only match the attribute4format field.

    attribute5(str): Filters results that only match the attribute5 field.

    attribute5expr(str): Filters results that only match the attribute5expr field.

    attribute5friendlyname(str): Filters results that only match the attribute5friendlyname field.

    attribute5format(str): Filters results that only match the attribute5format field.

    attribute6(str): Filters results that only match the attribute6 field.

    attribute6expr(str): Filters results that only match the attribute6expr field.

    attribute6friendlyname(str): Filters results that only match the attribute6friendlyname field.

    attribute6format(str): Filters results that only match the attribute6format field.

    attribute7(str): Filters results that only match the attribute7 field.

    attribute7expr(str): Filters results that only match the attribute7expr field.

    attribute7friendlyname(str): Filters results that only match the attribute7friendlyname field.

    attribute7format(str): Filters results that only match the attribute7format field.

    attribute8(str): Filters results that only match the attribute8 field.

    attribute8expr(str): Filters results that only match the attribute8expr field.

    attribute8friendlyname(str): Filters results that only match the attribute8friendlyname field.

    attribute8format(str): Filters results that only match the attribute8format field.

    attribute9(str): Filters results that only match the attribute9 field.

    attribute9expr(str): Filters results that only match the attribute9expr field.

    attribute9friendlyname(str): Filters results that only match the attribute9friendlyname field.

    attribute9format(str): Filters results that only match the attribute9format field.

    attribute10(str): Filters results that only match the attribute10 field.

    attribute10expr(str): Filters results that only match the attribute10expr field.

    attribute10friendlyname(str): Filters results that only match the attribute10friendlyname field.

    attribute10format(str): Filters results that only match the attribute10format field.

    attribute11(str): Filters results that only match the attribute11 field.

    attribute11expr(str): Filters results that only match the attribute11expr field.

    attribute11friendlyname(str): Filters results that only match the attribute11friendlyname field.

    attribute11format(str): Filters results that only match the attribute11format field.

    attribute12(str): Filters results that only match the attribute12 field.

    attribute12expr(str): Filters results that only match the attribute12expr field.

    attribute12friendlyname(str): Filters results that only match the attribute12friendlyname field.

    attribute12format(str): Filters results that only match the attribute12format field.

    attribute13(str): Filters results that only match the attribute13 field.

    attribute13expr(str): Filters results that only match the attribute13expr field.

    attribute13friendlyname(str): Filters results that only match the attribute13friendlyname field.

    attribute13format(str): Filters results that only match the attribute13format field.

    attribute14(str): Filters results that only match the attribute14 field.

    attribute14expr(str): Filters results that only match the attribute14expr field.

    attribute14friendlyname(str): Filters results that only match the attribute14friendlyname field.

    attribute14format(str): Filters results that only match the attribute14format field.

    attribute15(str): Filters results that only match the attribute15 field.

    attribute15expr(str): Filters results that only match the attribute15expr field.

    attribute15friendlyname(str): Filters results that only match the attribute15friendlyname field.

    attribute15format(str): Filters results that only match the attribute15format field.

    attribute16(str): Filters results that only match the attribute16 field.

    attribute16expr(str): Filters results that only match the attribute16expr field.

    attribute16friendlyname(str): Filters results that only match the attribute16friendlyname field.

    attribute16format(str): Filters results that only match the attribute16format field.

    encryptassertion(str): Filters results that only match the encryptassertion field.

    samlspcertname(str): Filters results that only match the samlspcertname field.

    encryptionalgorithm(str): Filters results that only match the encryptionalgorithm field.

    skewtime(int): Filters results that only match the skewtime field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsamlssoprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if samlsigningcertname:
        search_filter.append(['samlsigningcertname', samlsigningcertname])

    if assertionconsumerserviceurl:
        search_filter.append(['assertionconsumerserviceurl', assertionconsumerserviceurl])

    if relaystaterule:
        search_filter.append(['relaystaterule', relaystaterule])

    if sendpassword:
        search_filter.append(['sendpassword', sendpassword])

    if samlissuername:
        search_filter.append(['samlissuername', samlissuername])

    if signaturealg:
        search_filter.append(['signaturealg', signaturealg])

    if digestmethod:
        search_filter.append(['digestmethod', digestmethod])

    if audience:
        search_filter.append(['audience', audience])

    if nameidformat:
        search_filter.append(['nameidformat', nameidformat])

    if nameidexpr:
        search_filter.append(['nameidexpr', nameidexpr])

    if attribute1:
        search_filter.append(['attribute1', attribute1])

    if attribute1expr:
        search_filter.append(['attribute1expr', attribute1expr])

    if attribute1friendlyname:
        search_filter.append(['attribute1friendlyname', attribute1friendlyname])

    if attribute1format:
        search_filter.append(['attribute1format', attribute1format])

    if attribute2:
        search_filter.append(['attribute2', attribute2])

    if attribute2expr:
        search_filter.append(['attribute2expr', attribute2expr])

    if attribute2friendlyname:
        search_filter.append(['attribute2friendlyname', attribute2friendlyname])

    if attribute2format:
        search_filter.append(['attribute2format', attribute2format])

    if attribute3:
        search_filter.append(['attribute3', attribute3])

    if attribute3expr:
        search_filter.append(['attribute3expr', attribute3expr])

    if attribute3friendlyname:
        search_filter.append(['attribute3friendlyname', attribute3friendlyname])

    if attribute3format:
        search_filter.append(['attribute3format', attribute3format])

    if attribute4:
        search_filter.append(['attribute4', attribute4])

    if attribute4expr:
        search_filter.append(['attribute4expr', attribute4expr])

    if attribute4friendlyname:
        search_filter.append(['attribute4friendlyname', attribute4friendlyname])

    if attribute4format:
        search_filter.append(['attribute4format', attribute4format])

    if attribute5:
        search_filter.append(['attribute5', attribute5])

    if attribute5expr:
        search_filter.append(['attribute5expr', attribute5expr])

    if attribute5friendlyname:
        search_filter.append(['attribute5friendlyname', attribute5friendlyname])

    if attribute5format:
        search_filter.append(['attribute5format', attribute5format])

    if attribute6:
        search_filter.append(['attribute6', attribute6])

    if attribute6expr:
        search_filter.append(['attribute6expr', attribute6expr])

    if attribute6friendlyname:
        search_filter.append(['attribute6friendlyname', attribute6friendlyname])

    if attribute6format:
        search_filter.append(['attribute6format', attribute6format])

    if attribute7:
        search_filter.append(['attribute7', attribute7])

    if attribute7expr:
        search_filter.append(['attribute7expr', attribute7expr])

    if attribute7friendlyname:
        search_filter.append(['attribute7friendlyname', attribute7friendlyname])

    if attribute7format:
        search_filter.append(['attribute7format', attribute7format])

    if attribute8:
        search_filter.append(['attribute8', attribute8])

    if attribute8expr:
        search_filter.append(['attribute8expr', attribute8expr])

    if attribute8friendlyname:
        search_filter.append(['attribute8friendlyname', attribute8friendlyname])

    if attribute8format:
        search_filter.append(['attribute8format', attribute8format])

    if attribute9:
        search_filter.append(['attribute9', attribute9])

    if attribute9expr:
        search_filter.append(['attribute9expr', attribute9expr])

    if attribute9friendlyname:
        search_filter.append(['attribute9friendlyname', attribute9friendlyname])

    if attribute9format:
        search_filter.append(['attribute9format', attribute9format])

    if attribute10:
        search_filter.append(['attribute10', attribute10])

    if attribute10expr:
        search_filter.append(['attribute10expr', attribute10expr])

    if attribute10friendlyname:
        search_filter.append(['attribute10friendlyname', attribute10friendlyname])

    if attribute10format:
        search_filter.append(['attribute10format', attribute10format])

    if attribute11:
        search_filter.append(['attribute11', attribute11])

    if attribute11expr:
        search_filter.append(['attribute11expr', attribute11expr])

    if attribute11friendlyname:
        search_filter.append(['attribute11friendlyname', attribute11friendlyname])

    if attribute11format:
        search_filter.append(['attribute11format', attribute11format])

    if attribute12:
        search_filter.append(['attribute12', attribute12])

    if attribute12expr:
        search_filter.append(['attribute12expr', attribute12expr])

    if attribute12friendlyname:
        search_filter.append(['attribute12friendlyname', attribute12friendlyname])

    if attribute12format:
        search_filter.append(['attribute12format', attribute12format])

    if attribute13:
        search_filter.append(['attribute13', attribute13])

    if attribute13expr:
        search_filter.append(['attribute13expr', attribute13expr])

    if attribute13friendlyname:
        search_filter.append(['attribute13friendlyname', attribute13friendlyname])

    if attribute13format:
        search_filter.append(['attribute13format', attribute13format])

    if attribute14:
        search_filter.append(['attribute14', attribute14])

    if attribute14expr:
        search_filter.append(['attribute14expr', attribute14expr])

    if attribute14friendlyname:
        search_filter.append(['attribute14friendlyname', attribute14friendlyname])

    if attribute14format:
        search_filter.append(['attribute14format', attribute14format])

    if attribute15:
        search_filter.append(['attribute15', attribute15])

    if attribute15expr:
        search_filter.append(['attribute15expr', attribute15expr])

    if attribute15friendlyname:
        search_filter.append(['attribute15friendlyname', attribute15friendlyname])

    if attribute15format:
        search_filter.append(['attribute15format', attribute15format])

    if attribute16:
        search_filter.append(['attribute16', attribute16])

    if attribute16expr:
        search_filter.append(['attribute16expr', attribute16expr])

    if attribute16friendlyname:
        search_filter.append(['attribute16friendlyname', attribute16friendlyname])

    if attribute16format:
        search_filter.append(['attribute16format', attribute16format])

    if encryptassertion:
        search_filter.append(['encryptassertion', encryptassertion])

    if samlspcertname:
        search_filter.append(['samlspcertname', samlspcertname])

    if encryptionalgorithm:
        search_filter.append(['encryptionalgorithm', encryptionalgorithm])

    if skewtime:
        search_filter.append(['skewtime', skewtime])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsamlssoprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnsamlssoprofile')

    return response


def get_vpnsessionaction(name=None, useraccounting=None, httpport=None, winsip=None, dnsvservername=None, splitdns=None,
                         sesstimeout=None, clientsecurity=None, clientsecuritygroup=None, clientsecuritymessage=None,
                         clientsecuritylog=None, splittunnel=None, locallanaccess=None, rfc1918=None, spoofiip=None,
                         killconnections=None, transparentinterception=None, windowsclienttype=None,
                         defaultauthorizationaction=None, authorizationgroup=None, smartgroup=None,
                         clientidletimeout=None, proxy=None, allprotocolproxy=None, httpproxy=None, ftpproxy=None,
                         socksproxy=None, gopherproxy=None, sslproxy=None, proxyexception=None, proxylocalbypass=None,
                         clientcleanupprompt=None, forcecleanup=None, clientoptions=None, clientconfiguration=None,
                         sso=None, ssocredential=None, windowsautologon=None, usemip=None, useiip=None, clientdebug=None,
                         loginscript=None, logoutscript=None, homepage=None, icaproxy=None, wihome=None,
                         wihomeaddresstype=None, citrixreceiverhome=None, wiportalmode=None, clientchoices=None,
                         epaclienttype=None, iipdnssuffix=None, forcedtimeout=None, forcedtimeoutwarning=None,
                         ntdomain=None, clientlessvpnmode=None, emailhome=None, clientlessmodeurlencoding=None,
                         clientlesspersistentcookie=None, allowedlogingroups=None, securebrowse=None, storefronturl=None,
                         sfgatewayauthtype=None, kcdaccount=None, rdpclientprofilename=None, windowspluginupgrade=None,
                         macpluginupgrade=None, linuxpluginupgrade=None, iconwithreceiver=None, alwaysonprofilename=None,
                         autoproxyurl=None, pcoipprofilename=None):
    '''
    Show the running configuration for the vpnsessionaction config key.

    name(str): Filters results that only match the name field.

    useraccounting(str): Filters results that only match the useraccounting field.

    httpport(list(int)): Filters results that only match the httpport field.

    winsip(str): Filters results that only match the winsip field.

    dnsvservername(str): Filters results that only match the dnsvservername field.

    splitdns(str): Filters results that only match the splitdns field.

    sesstimeout(int): Filters results that only match the sesstimeout field.

    clientsecurity(str): Filters results that only match the clientsecurity field.

    clientsecuritygroup(str): Filters results that only match the clientsecuritygroup field.

    clientsecuritymessage(str): Filters results that only match the clientsecuritymessage field.

    clientsecuritylog(str): Filters results that only match the clientsecuritylog field.

    splittunnel(str): Filters results that only match the splittunnel field.

    locallanaccess(str): Filters results that only match the locallanaccess field.

    rfc1918(str): Filters results that only match the rfc1918 field.

    spoofiip(str): Filters results that only match the spoofiip field.

    killconnections(str): Filters results that only match the killconnections field.

    transparentinterception(str): Filters results that only match the transparentinterception field.

    windowsclienttype(str): Filters results that only match the windowsclienttype field.

    defaultauthorizationaction(str): Filters results that only match the defaultauthorizationaction field.

    authorizationgroup(str): Filters results that only match the authorizationgroup field.

    smartgroup(str): Filters results that only match the smartgroup field.

    clientidletimeout(int): Filters results that only match the clientidletimeout field.

    proxy(str): Filters results that only match the proxy field.

    allprotocolproxy(str): Filters results that only match the allprotocolproxy field.

    httpproxy(str): Filters results that only match the httpproxy field.

    ftpproxy(str): Filters results that only match the ftpproxy field.

    socksproxy(str): Filters results that only match the socksproxy field.

    gopherproxy(str): Filters results that only match the gopherproxy field.

    sslproxy(str): Filters results that only match the sslproxy field.

    proxyexception(str): Filters results that only match the proxyexception field.

    proxylocalbypass(str): Filters results that only match the proxylocalbypass field.

    clientcleanupprompt(str): Filters results that only match the clientcleanupprompt field.

    forcecleanup(list(str)): Filters results that only match the forcecleanup field.

    clientoptions(str): Filters results that only match the clientoptions field.

    clientconfiguration(list(str)): Filters results that only match the clientconfiguration field.

    sso(str): Filters results that only match the sso field.

    ssocredential(str): Filters results that only match the ssocredential field.

    windowsautologon(str): Filters results that only match the windowsautologon field.

    usemip(str): Filters results that only match the usemip field.

    useiip(str): Filters results that only match the useiip field.

    clientdebug(str): Filters results that only match the clientdebug field.

    loginscript(str): Filters results that only match the loginscript field.

    logoutscript(str): Filters results that only match the logoutscript field.

    homepage(str): Filters results that only match the homepage field.

    icaproxy(str): Filters results that only match the icaproxy field.

    wihome(str): Filters results that only match the wihome field.

    wihomeaddresstype(str): Filters results that only match the wihomeaddresstype field.

    citrixreceiverhome(str): Filters results that only match the citrixreceiverhome field.

    wiportalmode(str): Filters results that only match the wiportalmode field.

    clientchoices(str): Filters results that only match the clientchoices field.

    epaclienttype(str): Filters results that only match the epaclienttype field.

    iipdnssuffix(str): Filters results that only match the iipdnssuffix field.

    forcedtimeout(int): Filters results that only match the forcedtimeout field.

    forcedtimeoutwarning(int): Filters results that only match the forcedtimeoutwarning field.

    ntdomain(str): Filters results that only match the ntdomain field.

    clientlessvpnmode(str): Filters results that only match the clientlessvpnmode field.

    emailhome(str): Filters results that only match the emailhome field.

    clientlessmodeurlencoding(str): Filters results that only match the clientlessmodeurlencoding field.

    clientlesspersistentcookie(str): Filters results that only match the clientlesspersistentcookie field.

    allowedlogingroups(str): Filters results that only match the allowedlogingroups field.

    securebrowse(str): Filters results that only match the securebrowse field.

    storefronturl(str): Filters results that only match the storefronturl field.

    sfgatewayauthtype(str): Filters results that only match the sfgatewayauthtype field.

    kcdaccount(str): Filters results that only match the kcdaccount field.

    rdpclientprofilename(str): Filters results that only match the rdpclientprofilename field.

    windowspluginupgrade(str): Filters results that only match the windowspluginupgrade field.

    macpluginupgrade(str): Filters results that only match the macpluginupgrade field.

    linuxpluginupgrade(str): Filters results that only match the linuxpluginupgrade field.

    iconwithreceiver(str): Filters results that only match the iconwithreceiver field.

    alwaysonprofilename(str): Filters results that only match the alwaysonprofilename field.

    autoproxyurl(str): Filters results that only match the autoproxyurl field.

    pcoipprofilename(str): Filters results that only match the pcoipprofilename field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsessionaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if useraccounting:
        search_filter.append(['useraccounting', useraccounting])

    if httpport:
        search_filter.append(['httpport', httpport])

    if winsip:
        search_filter.append(['winsip', winsip])

    if dnsvservername:
        search_filter.append(['dnsvservername', dnsvservername])

    if splitdns:
        search_filter.append(['splitdns', splitdns])

    if sesstimeout:
        search_filter.append(['sesstimeout', sesstimeout])

    if clientsecurity:
        search_filter.append(['clientsecurity', clientsecurity])

    if clientsecuritygroup:
        search_filter.append(['clientsecuritygroup', clientsecuritygroup])

    if clientsecuritymessage:
        search_filter.append(['clientsecuritymessage', clientsecuritymessage])

    if clientsecuritylog:
        search_filter.append(['clientsecuritylog', clientsecuritylog])

    if splittunnel:
        search_filter.append(['splittunnel', splittunnel])

    if locallanaccess:
        search_filter.append(['locallanaccess', locallanaccess])

    if rfc1918:
        search_filter.append(['rfc1918', rfc1918])

    if spoofiip:
        search_filter.append(['spoofiip', spoofiip])

    if killconnections:
        search_filter.append(['killconnections', killconnections])

    if transparentinterception:
        search_filter.append(['transparentinterception', transparentinterception])

    if windowsclienttype:
        search_filter.append(['windowsclienttype', windowsclienttype])

    if defaultauthorizationaction:
        search_filter.append(['defaultauthorizationaction', defaultauthorizationaction])

    if authorizationgroup:
        search_filter.append(['authorizationgroup', authorizationgroup])

    if smartgroup:
        search_filter.append(['smartgroup', smartgroup])

    if clientidletimeout:
        search_filter.append(['clientidletimeout', clientidletimeout])

    if proxy:
        search_filter.append(['proxy', proxy])

    if allprotocolproxy:
        search_filter.append(['allprotocolproxy', allprotocolproxy])

    if httpproxy:
        search_filter.append(['httpproxy', httpproxy])

    if ftpproxy:
        search_filter.append(['ftpproxy', ftpproxy])

    if socksproxy:
        search_filter.append(['socksproxy', socksproxy])

    if gopherproxy:
        search_filter.append(['gopherproxy', gopherproxy])

    if sslproxy:
        search_filter.append(['sslproxy', sslproxy])

    if proxyexception:
        search_filter.append(['proxyexception', proxyexception])

    if proxylocalbypass:
        search_filter.append(['proxylocalbypass', proxylocalbypass])

    if clientcleanupprompt:
        search_filter.append(['clientcleanupprompt', clientcleanupprompt])

    if forcecleanup:
        search_filter.append(['forcecleanup', forcecleanup])

    if clientoptions:
        search_filter.append(['clientoptions', clientoptions])

    if clientconfiguration:
        search_filter.append(['clientconfiguration', clientconfiguration])

    if sso:
        search_filter.append(['sso', sso])

    if ssocredential:
        search_filter.append(['ssocredential', ssocredential])

    if windowsautologon:
        search_filter.append(['windowsautologon', windowsautologon])

    if usemip:
        search_filter.append(['usemip', usemip])

    if useiip:
        search_filter.append(['useiip', useiip])

    if clientdebug:
        search_filter.append(['clientdebug', clientdebug])

    if loginscript:
        search_filter.append(['loginscript', loginscript])

    if logoutscript:
        search_filter.append(['logoutscript', logoutscript])

    if homepage:
        search_filter.append(['homepage', homepage])

    if icaproxy:
        search_filter.append(['icaproxy', icaproxy])

    if wihome:
        search_filter.append(['wihome', wihome])

    if wihomeaddresstype:
        search_filter.append(['wihomeaddresstype', wihomeaddresstype])

    if citrixreceiverhome:
        search_filter.append(['citrixreceiverhome', citrixreceiverhome])

    if wiportalmode:
        search_filter.append(['wiportalmode', wiportalmode])

    if clientchoices:
        search_filter.append(['clientchoices', clientchoices])

    if epaclienttype:
        search_filter.append(['epaclienttype', epaclienttype])

    if iipdnssuffix:
        search_filter.append(['iipdnssuffix', iipdnssuffix])

    if forcedtimeout:
        search_filter.append(['forcedtimeout', forcedtimeout])

    if forcedtimeoutwarning:
        search_filter.append(['forcedtimeoutwarning', forcedtimeoutwarning])

    if ntdomain:
        search_filter.append(['ntdomain', ntdomain])

    if clientlessvpnmode:
        search_filter.append(['clientlessvpnmode', clientlessvpnmode])

    if emailhome:
        search_filter.append(['emailhome', emailhome])

    if clientlessmodeurlencoding:
        search_filter.append(['clientlessmodeurlencoding', clientlessmodeurlencoding])

    if clientlesspersistentcookie:
        search_filter.append(['clientlesspersistentcookie', clientlesspersistentcookie])

    if allowedlogingroups:
        search_filter.append(['allowedlogingroups', allowedlogingroups])

    if securebrowse:
        search_filter.append(['securebrowse', securebrowse])

    if storefronturl:
        search_filter.append(['storefronturl', storefronturl])

    if sfgatewayauthtype:
        search_filter.append(['sfgatewayauthtype', sfgatewayauthtype])

    if kcdaccount:
        search_filter.append(['kcdaccount', kcdaccount])

    if rdpclientprofilename:
        search_filter.append(['rdpclientprofilename', rdpclientprofilename])

    if windowspluginupgrade:
        search_filter.append(['windowspluginupgrade', windowspluginupgrade])

    if macpluginupgrade:
        search_filter.append(['macpluginupgrade', macpluginupgrade])

    if linuxpluginupgrade:
        search_filter.append(['linuxpluginupgrade', linuxpluginupgrade])

    if iconwithreceiver:
        search_filter.append(['iconwithreceiver', iconwithreceiver])

    if alwaysonprofilename:
        search_filter.append(['alwaysonprofilename', alwaysonprofilename])

    if autoproxyurl:
        search_filter.append(['autoproxyurl', autoproxyurl])

    if pcoipprofilename:
        search_filter.append(['pcoipprofilename', pcoipprofilename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsessionaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnsessionaction')

    return response


def get_vpnsessionpolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the vpnsessionpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsessionpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsessionpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnsessionpolicy')

    return response


def get_vpnsessionpolicy_aaagroup_binding(boundto=None, name=None):
    '''
    Show the running configuration for the vpnsessionpolicy_aaagroup_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsessionpolicy_aaagroup_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsessionpolicy_aaagroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnsessionpolicy_aaagroup_binding')

    return response


def get_vpnsessionpolicy_aaauser_binding(boundto=None, name=None):
    '''
    Show the running configuration for the vpnsessionpolicy_aaauser_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsessionpolicy_aaauser_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsessionpolicy_aaauser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnsessionpolicy_aaauser_binding')

    return response


def get_vpnsessionpolicy_binding():
    '''
    Show the running configuration for the vpnsessionpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsessionpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsessionpolicy_binding'), 'vpnsessionpolicy_binding')

    return response


def get_vpnsessionpolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the vpnsessionpolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsessionpolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsessionpolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnsessionpolicy_vpnglobal_binding')

    return response


def get_vpnsessionpolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the vpnsessionpolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsessionpolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsessionpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnsessionpolicy_vpnvserver_binding')

    return response


def get_vpnsfconfig(vserver=None):
    '''
    Show the running configuration for the vpnsfconfig config key.

    vserver(list(str)): Filters results that only match the vserver field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnsfconfig

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnsfconfig{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnsfconfig')

    return response


def get_vpnstoreinfo(url=None):
    '''
    Show the running configuration for the vpnstoreinfo config key.

    url(str): Filters results that only match the url field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnstoreinfo

    '''

    search_filter = []

    if url:
        search_filter.append(['url', url])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnstoreinfo{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnstoreinfo')

    return response


def get_vpntrafficaction(name=None, qual=None, apptimeout=None, sso=None, hdx=None, formssoaction=None, fta=None,
                         wanscaler=None, kcdaccount=None, samlssoprofile=None, proxy=None, userexpression=None,
                         passwdexpression=None):
    '''
    Show the running configuration for the vpntrafficaction config key.

    name(str): Filters results that only match the name field.

    qual(str): Filters results that only match the qual field.

    apptimeout(int): Filters results that only match the apptimeout field.

    sso(str): Filters results that only match the sso field.

    hdx(str): Filters results that only match the hdx field.

    formssoaction(str): Filters results that only match the formssoaction field.

    fta(str): Filters results that only match the fta field.

    wanscaler(str): Filters results that only match the wanscaler field.

    kcdaccount(str): Filters results that only match the kcdaccount field.

    samlssoprofile(str): Filters results that only match the samlssoprofile field.

    proxy(str): Filters results that only match the proxy field.

    userexpression(str): Filters results that only match the userexpression field.

    passwdexpression(str): Filters results that only match the passwdexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpntrafficaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if qual:
        search_filter.append(['qual', qual])

    if apptimeout:
        search_filter.append(['apptimeout', apptimeout])

    if sso:
        search_filter.append(['sso', sso])

    if hdx:
        search_filter.append(['hdx', hdx])

    if formssoaction:
        search_filter.append(['formssoaction', formssoaction])

    if fta:
        search_filter.append(['fta', fta])

    if wanscaler:
        search_filter.append(['wanscaler', wanscaler])

    if kcdaccount:
        search_filter.append(['kcdaccount', kcdaccount])

    if samlssoprofile:
        search_filter.append(['samlssoprofile', samlssoprofile])

    if proxy:
        search_filter.append(['proxy', proxy])

    if userexpression:
        search_filter.append(['userexpression', userexpression])

    if passwdexpression:
        search_filter.append(['passwdexpression', passwdexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpntrafficaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpntrafficaction')

    return response


def get_vpntrafficpolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the vpntrafficpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpntrafficpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpntrafficpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpntrafficpolicy')

    return response


def get_vpntrafficpolicy_aaagroup_binding(name=None, boundto=None):
    '''
    Show the running configuration for the vpntrafficpolicy_aaagroup_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpntrafficpolicy_aaagroup_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpntrafficpolicy_aaagroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpntrafficpolicy_aaagroup_binding')

    return response


def get_vpntrafficpolicy_aaauser_binding(name=None, boundto=None):
    '''
    Show the running configuration for the vpntrafficpolicy_aaauser_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpntrafficpolicy_aaauser_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpntrafficpolicy_aaauser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpntrafficpolicy_aaauser_binding')

    return response


def get_vpntrafficpolicy_binding():
    '''
    Show the running configuration for the vpntrafficpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpntrafficpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpntrafficpolicy_binding'), 'vpntrafficpolicy_binding')

    return response


def get_vpntrafficpolicy_vpnglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the vpntrafficpolicy_vpnglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpntrafficpolicy_vpnglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpntrafficpolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpntrafficpolicy_vpnglobal_binding')

    return response


def get_vpntrafficpolicy_vpnvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the vpntrafficpolicy_vpnvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpntrafficpolicy_vpnvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpntrafficpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpntrafficpolicy_vpnvserver_binding')

    return response


def get_vpnurl(urlname=None, linkname=None, actualurl=None, vservername=None, clientlessaccess=None, comment=None,
               iconurl=None, ssotype=None, applicationtype=None, samlssoprofile=None):
    '''
    Show the running configuration for the vpnurl config key.

    urlname(str): Filters results that only match the urlname field.

    linkname(str): Filters results that only match the linkname field.

    actualurl(str): Filters results that only match the actualurl field.

    vservername(str): Filters results that only match the vservername field.

    clientlessaccess(str): Filters results that only match the clientlessaccess field.

    comment(str): Filters results that only match the comment field.

    iconurl(str): Filters results that only match the iconurl field.

    ssotype(str): Filters results that only match the ssotype field.

    applicationtype(str): Filters results that only match the applicationtype field.

    samlssoprofile(str): Filters results that only match the samlssoprofile field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnurl

    '''

    search_filter = []

    if urlname:
        search_filter.append(['urlname', urlname])

    if linkname:
        search_filter.append(['linkname', linkname])

    if actualurl:
        search_filter.append(['actualurl', actualurl])

    if vservername:
        search_filter.append(['vservername', vservername])

    if clientlessaccess:
        search_filter.append(['clientlessaccess', clientlessaccess])

    if comment:
        search_filter.append(['comment', comment])

    if iconurl:
        search_filter.append(['iconurl', iconurl])

    if ssotype:
        search_filter.append(['ssotype', ssotype])

    if applicationtype:
        search_filter.append(['applicationtype', applicationtype])

    if samlssoprofile:
        search_filter.append(['samlssoprofile', samlssoprofile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnurl{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnurl')

    return response


def get_vpnvserver(name=None, servicetype=None, ipv46=None, range=None, port=None, state=None, authentication=None,
                   doublehop=None, maxaaausers=None, icaonly=None, icaproxysessionmigration=None, dtls=None,
                   loginonce=None, advancedepa=None, devicecert=None, certkeynames=None, downstateflush=None,
                   listenpolicy=None, listenpriority=None, tcpprofilename=None, httpprofilename=None, comment=None,
                   appflowlog=None, icmpvsrresponse=None, rhistate=None, netprofile=None, cginfrahomepageredirect=None,
                   maxloginattempts=None, failedlogintimeout=None, l2conn=None, deploymenttype=None,
                   rdpserverprofilename=None, windowsepapluginupgrade=None, linuxepapluginupgrade=None,
                   macepapluginupgrade=None, logoutonsmartcardremoval=None, userdomains=None, authnprofile=None,
                   vserverfqdn=None, pcoipvserverprofilename=None, newname=None):
    '''
    Show the running configuration for the vpnvserver config key.

    name(str): Filters results that only match the name field.

    servicetype(str): Filters results that only match the servicetype field.

    ipv46(str): Filters results that only match the ipv46 field.

    range(int): Filters results that only match the range field.

    port(int): Filters results that only match the port field.

    state(str): Filters results that only match the state field.

    authentication(str): Filters results that only match the authentication field.

    doublehop(str): Filters results that only match the doublehop field.

    maxaaausers(int): Filters results that only match the maxaaausers field.

    icaonly(str): Filters results that only match the icaonly field.

    icaproxysessionmigration(str): Filters results that only match the icaproxysessionmigration field.

    dtls(str): Filters results that only match the dtls field.

    loginonce(str): Filters results that only match the loginonce field.

    advancedepa(str): Filters results that only match the advancedepa field.

    devicecert(str): Filters results that only match the devicecert field.

    certkeynames(str): Filters results that only match the certkeynames field.

    downstateflush(str): Filters results that only match the downstateflush field.

    listenpolicy(str): Filters results that only match the listenpolicy field.

    listenpriority(int): Filters results that only match the listenpriority field.

    tcpprofilename(str): Filters results that only match the tcpprofilename field.

    httpprofilename(str): Filters results that only match the httpprofilename field.

    comment(str): Filters results that only match the comment field.

    appflowlog(str): Filters results that only match the appflowlog field.

    icmpvsrresponse(str): Filters results that only match the icmpvsrresponse field.

    rhistate(str): Filters results that only match the rhistate field.

    netprofile(str): Filters results that only match the netprofile field.

    cginfrahomepageredirect(str): Filters results that only match the cginfrahomepageredirect field.

    maxloginattempts(int): Filters results that only match the maxloginattempts field.

    failedlogintimeout(int): Filters results that only match the failedlogintimeout field.

    l2conn(str): Filters results that only match the l2conn field.

    deploymenttype(str): Filters results that only match the deploymenttype field.

    rdpserverprofilename(str): Filters results that only match the rdpserverprofilename field.

    windowsepapluginupgrade(str): Filters results that only match the windowsepapluginupgrade field.

    linuxepapluginupgrade(str): Filters results that only match the linuxepapluginupgrade field.

    macepapluginupgrade(str): Filters results that only match the macepapluginupgrade field.

    logoutonsmartcardremoval(str): Filters results that only match the logoutonsmartcardremoval field.

    userdomains(str): Filters results that only match the userdomains field.

    authnprofile(str): Filters results that only match the authnprofile field.

    vserverfqdn(str): Filters results that only match the vserverfqdn field.

    pcoipvserverprofilename(str): Filters results that only match the pcoipvserverprofilename field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if servicetype:
        search_filter.append(['servicetype', servicetype])

    if ipv46:
        search_filter.append(['ipv46', ipv46])

    if range:
        search_filter.append(['range', range])

    if port:
        search_filter.append(['port', port])

    if state:
        search_filter.append(['state', state])

    if authentication:
        search_filter.append(['authentication', authentication])

    if doublehop:
        search_filter.append(['doublehop', doublehop])

    if maxaaausers:
        search_filter.append(['maxaaausers', maxaaausers])

    if icaonly:
        search_filter.append(['icaonly', icaonly])

    if icaproxysessionmigration:
        search_filter.append(['icaproxysessionmigration', icaproxysessionmigration])

    if dtls:
        search_filter.append(['dtls', dtls])

    if loginonce:
        search_filter.append(['loginonce', loginonce])

    if advancedepa:
        search_filter.append(['advancedepa', advancedepa])

    if devicecert:
        search_filter.append(['devicecert', devicecert])

    if certkeynames:
        search_filter.append(['certkeynames', certkeynames])

    if downstateflush:
        search_filter.append(['downstateflush', downstateflush])

    if listenpolicy:
        search_filter.append(['listenpolicy', listenpolicy])

    if listenpriority:
        search_filter.append(['listenpriority', listenpriority])

    if tcpprofilename:
        search_filter.append(['tcpprofilename', tcpprofilename])

    if httpprofilename:
        search_filter.append(['httpprofilename', httpprofilename])

    if comment:
        search_filter.append(['comment', comment])

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if icmpvsrresponse:
        search_filter.append(['icmpvsrresponse', icmpvsrresponse])

    if rhistate:
        search_filter.append(['rhistate', rhistate])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    if cginfrahomepageredirect:
        search_filter.append(['cginfrahomepageredirect', cginfrahomepageredirect])

    if maxloginattempts:
        search_filter.append(['maxloginattempts', maxloginattempts])

    if failedlogintimeout:
        search_filter.append(['failedlogintimeout', failedlogintimeout])

    if l2conn:
        search_filter.append(['l2conn', l2conn])

    if deploymenttype:
        search_filter.append(['deploymenttype', deploymenttype])

    if rdpserverprofilename:
        search_filter.append(['rdpserverprofilename', rdpserverprofilename])

    if windowsepapluginupgrade:
        search_filter.append(['windowsepapluginupgrade', windowsepapluginupgrade])

    if linuxepapluginupgrade:
        search_filter.append(['linuxepapluginupgrade', linuxepapluginupgrade])

    if macepapluginupgrade:
        search_filter.append(['macepapluginupgrade', macepapluginupgrade])

    if logoutonsmartcardremoval:
        search_filter.append(['logoutonsmartcardremoval', logoutonsmartcardremoval])

    if userdomains:
        search_filter.append(['userdomains', userdomains])

    if authnprofile:
        search_filter.append(['authnprofile', authnprofile])

    if vserverfqdn:
        search_filter.append(['vserverfqdn', vserverfqdn])

    if pcoipvserverprofilename:
        search_filter.append(['pcoipvserverprofilename', pcoipvserverprofilename])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver')

    return response


def get_vpnvserver_aaapreauthenticationpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                      groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_aaapreauthenticationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_aaapreauthenticationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_aaapreauthenticationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_aaapreauthenticationpolicy_binding')

    return response


def get_vpnvserver_appcontroller_binding(appcontroller=None, name=None):
    '''
    Show the running configuration for the vpnvserver_appcontroller_binding config key.

    appcontroller(str): Filters results that only match the appcontroller field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_appcontroller_binding

    '''

    search_filter = []

    if appcontroller:
        search_filter.append(['appcontroller', appcontroller])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_appcontroller_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_appcontroller_binding')

    return response


def get_vpnvserver_appflowpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                         name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_appflowpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_appflowpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_appflowpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_appflowpolicy_binding')

    return response


def get_vpnvserver_auditnslogpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                            groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_auditnslogpolicy_binding')

    return response


def get_vpnvserver_auditsyslogpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                             groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_auditsyslogpolicy_binding')

    return response


def get_vpnvserver_authenticationcertpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                    groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationcertpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationcertpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationcertpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationcertpolicy_binding')

    return response


def get_vpnvserver_authenticationdfapolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                   groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationdfapolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationdfapolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationdfapolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationdfapolicy_binding')

    return response


def get_vpnvserver_authenticationldappolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                    groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationldappolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationldappolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationldappolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationldappolicy_binding')

    return response


def get_vpnvserver_authenticationlocalpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                     groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationlocalpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationlocalpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationlocalpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationlocalpolicy_binding')

    return response


def get_vpnvserver_authenticationloginschemapolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                           groupextraction=None, name=None, secondary=None,
                                                           bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationloginschemapolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationloginschemapolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationloginschemapolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationloginschemapolicy_binding')

    return response


def get_vpnvserver_authenticationnegotiatepolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                         groupextraction=None, name=None, secondary=None,
                                                         bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationnegotiatepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationnegotiatepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationnegotiatepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationnegotiatepolicy_binding')

    return response


def get_vpnvserver_authenticationpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationpolicy_binding')

    return response


def get_vpnvserver_authenticationradiuspolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                      groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationradiuspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationradiuspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationradiuspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationradiuspolicy_binding')

    return response


def get_vpnvserver_authenticationsamlidppolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                       groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationsamlidppolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationsamlidppolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationsamlidppolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationsamlidppolicy_binding')

    return response


def get_vpnvserver_authenticationsamlpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                    groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationsamlpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationsamlpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationsamlpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationsamlpolicy_binding')

    return response


def get_vpnvserver_authenticationtacacspolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                      groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationtacacspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationtacacspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationtacacspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationtacacspolicy_binding')

    return response


def get_vpnvserver_authenticationwebauthpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                       groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_authenticationwebauthpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_authenticationwebauthpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_authenticationwebauthpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_authenticationwebauthpolicy_binding')

    return response


def get_vpnvserver_binding():
    '''
    Show the running configuration for the vpnvserver_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_binding'), 'vpnvserver_binding')

    return response


def get_vpnvserver_cachepolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                       name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_cachepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_cachepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_cachepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_cachepolicy_binding')

    return response


def get_vpnvserver_cspolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                    name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_cspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_cspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_cspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_cspolicy_binding')

    return response


def get_vpnvserver_feopolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                     name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_feopolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_feopolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_feopolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_feopolicy_binding')

    return response


def get_vpnvserver_icapolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                     name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_icapolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_icapolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_icapolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_icapolicy_binding')

    return response


def get_vpnvserver_intranetip6_binding(intranetip6=None, numaddr=None, name=None):
    '''
    Show the running configuration for the vpnvserver_intranetip6_binding config key.

    intranetip6(str): Filters results that only match the intranetip6 field.

    numaddr(int): Filters results that only match the numaddr field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_intranetip6_binding

    '''

    search_filter = []

    if intranetip6:
        search_filter.append(['intranetip6', intranetip6])

    if numaddr:
        search_filter.append(['numaddr', numaddr])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_intranetip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_intranetip6_binding')

    return response


def get_vpnvserver_intranetip_binding(name=None, intranetip=None, netmask=None):
    '''
    Show the running configuration for the vpnvserver_intranetip_binding config key.

    name(str): Filters results that only match the name field.

    intranetip(str): Filters results that only match the intranetip field.

    netmask(str): Filters results that only match the netmask field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_intranetip_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if intranetip:
        search_filter.append(['intranetip', intranetip])

    if netmask:
        search_filter.append(['netmask', netmask])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_intranetip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_intranetip_binding')

    return response


def get_vpnvserver_responderpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                           name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_responderpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_responderpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_responderpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_responderpolicy_binding')

    return response


def get_vpnvserver_rewritepolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupextraction=None,
                                         name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_rewritepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_rewritepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_rewritepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_rewritepolicy_binding')

    return response


def get_vpnvserver_sharefileserver_binding(name=None, sharefile=None):
    '''
    Show the running configuration for the vpnvserver_sharefileserver_binding config key.

    name(str): Filters results that only match the name field.

    sharefile(str): Filters results that only match the sharefile field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_sharefileserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if sharefile:
        search_filter.append(['sharefile', sharefile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_sharefileserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_sharefileserver_binding')

    return response


def get_vpnvserver_staserver_binding(name=None, staaddresstype=None, staserver=None):
    '''
    Show the running configuration for the vpnvserver_staserver_binding config key.

    name(str): Filters results that only match the name field.

    staaddresstype(str): Filters results that only match the staaddresstype field.

    staserver(str): Filters results that only match the staserver field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_staserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if staaddresstype:
        search_filter.append(['staaddresstype', staaddresstype])

    if staserver:
        search_filter.append(['staserver', staserver])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_staserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_staserver_binding')

    return response


def get_vpnvserver_vpnclientlessaccesspolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                                     groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_vpnclientlessaccesspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpnclientlessaccesspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpnclientlessaccesspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpnclientlessaccesspolicy_binding')

    return response


def get_vpnvserver_vpnepaprofile_binding(name=None, epaprofile=None, epaprofileoptional=None):
    '''
    Show the running configuration for the vpnvserver_vpnepaprofile_binding config key.

    name(str): Filters results that only match the name field.

    epaprofile(str): Filters results that only match the epaprofile field.

    epaprofileoptional(bool): Filters results that only match the epaprofileoptional field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpnepaprofile_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if epaprofile:
        search_filter.append(['epaprofile', epaprofile])

    if epaprofileoptional:
        search_filter.append(['epaprofileoptional', epaprofileoptional])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpnepaprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpnepaprofile_binding')

    return response


def get_vpnvserver_vpneula_binding(eula=None, name=None):
    '''
    Show the running configuration for the vpnvserver_vpneula_binding config key.

    eula(str): Filters results that only match the eula field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpneula_binding

    '''

    search_filter = []

    if eula:
        search_filter.append(['eula', eula])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpneula_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpneula_binding')

    return response


def get_vpnvserver_vpnintranetapplication_binding(name=None, intranetapplication=None):
    '''
    Show the running configuration for the vpnvserver_vpnintranetapplication_binding config key.

    name(str): Filters results that only match the name field.

    intranetapplication(str): Filters results that only match the intranetapplication field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpnintranetapplication_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if intranetapplication:
        search_filter.append(['intranetapplication', intranetapplication])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpnintranetapplication_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpnintranetapplication_binding')

    return response


def get_vpnvserver_vpnnexthopserver_binding(name=None, nexthopserver=None):
    '''
    Show the running configuration for the vpnvserver_vpnnexthopserver_binding config key.

    name(str): Filters results that only match the name field.

    nexthopserver(str): Filters results that only match the nexthopserver field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpnnexthopserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if nexthopserver:
        search_filter.append(['nexthopserver', nexthopserver])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpnnexthopserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpnnexthopserver_binding')

    return response


def get_vpnvserver_vpnportaltheme_binding(name=None, portaltheme=None):
    '''
    Show the running configuration for the vpnvserver_vpnportaltheme_binding config key.

    name(str): Filters results that only match the name field.

    portaltheme(str): Filters results that only match the portaltheme field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpnportaltheme_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if portaltheme:
        search_filter.append(['portaltheme', portaltheme])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpnportaltheme_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpnportaltheme_binding')

    return response


def get_vpnvserver_vpnsessionpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                            groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_vpnsessionpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpnsessionpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpnsessionpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpnsessionpolicy_binding')

    return response


def get_vpnvserver_vpntrafficpolicy_binding(priority=None, gotopriorityexpression=None, policy=None,
                                            groupextraction=None, name=None, secondary=None, bindpoint=None):
    '''
    Show the running configuration for the vpnvserver_vpntrafficpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    name(str): Filters results that only match the name field.

    secondary(bool): Filters results that only match the secondary field.

    bindpoint(str): Filters results that only match the bindpoint field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpntrafficpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    if name:
        search_filter.append(['name', name])

    if secondary:
        search_filter.append(['secondary', secondary])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpntrafficpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpntrafficpolicy_binding')

    return response


def get_vpnvserver_vpnurl_binding(urlname=None, name=None):
    '''
    Show the running configuration for the vpnvserver_vpnurl_binding config key.

    urlname(str): Filters results that only match the urlname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.get_vpnvserver_vpnurl_binding

    '''

    search_filter = []

    if urlname:
        search_filter.append(['urlname', urlname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/vpnvserver_vpnurl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'vpnvserver_vpnurl_binding')

    return response


def unset_vpnalwaysonprofile(name=None, networkaccessonvpnfailure=None, clientcontrol=None, locationbasedvpn=None,
                             save=False):
    '''
    Unsets values from the vpnalwaysonprofile configuration key.

    name(bool): Unsets the name value.

    networkaccessonvpnfailure(bool): Unsets the networkaccessonvpnfailure value.

    clientcontrol(bool): Unsets the clientcontrol value.

    locationbasedvpn(bool): Unsets the locationbasedvpn value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnalwaysonprofile <args>

    '''

    result = {}

    payload = {'vpnalwaysonprofile': {}}

    if name:
        payload['vpnalwaysonprofile']['name'] = True

    if networkaccessonvpnfailure:
        payload['vpnalwaysonprofile']['networkaccessonvpnfailure'] = True

    if clientcontrol:
        payload['vpnalwaysonprofile']['clientcontrol'] = True

    if locationbasedvpn:
        payload['vpnalwaysonprofile']['locationbasedvpn'] = True

    execution = __proxy__['citrixns.post']('config/vpnalwaysonprofile?action=unset', payload)

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


def unset_vpnclientlessaccessprofile(profilename=None, urlrewritepolicylabel=None, javascriptrewritepolicylabel=None,
                                     reqhdrrewritepolicylabel=None, reshdrrewritepolicylabel=None,
                                     regexforfindingurlinjavascript=None, regexforfindingurlincss=None,
                                     regexforfindingurlinxcomponent=None, regexforfindingurlinxml=None,
                                     regexforfindingcustomurls=None, clientconsumedcookies=None,
                                     requirepersistentcookie=None, save=False):
    '''
    Unsets values from the vpnclientlessaccessprofile configuration key.

    profilename(bool): Unsets the profilename value.

    urlrewritepolicylabel(bool): Unsets the urlrewritepolicylabel value.

    javascriptrewritepolicylabel(bool): Unsets the javascriptrewritepolicylabel value.

    reqhdrrewritepolicylabel(bool): Unsets the reqhdrrewritepolicylabel value.

    reshdrrewritepolicylabel(bool): Unsets the reshdrrewritepolicylabel value.

    regexforfindingurlinjavascript(bool): Unsets the regexforfindingurlinjavascript value.

    regexforfindingurlincss(bool): Unsets the regexforfindingurlincss value.

    regexforfindingurlinxcomponent(bool): Unsets the regexforfindingurlinxcomponent value.

    regexforfindingurlinxml(bool): Unsets the regexforfindingurlinxml value.

    regexforfindingcustomurls(bool): Unsets the regexforfindingcustomurls value.

    clientconsumedcookies(bool): Unsets the clientconsumedcookies value.

    requirepersistentcookie(bool): Unsets the requirepersistentcookie value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnclientlessaccessprofile <args>

    '''

    result = {}

    payload = {'vpnclientlessaccessprofile': {}}

    if profilename:
        payload['vpnclientlessaccessprofile']['profilename'] = True

    if urlrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['urlrewritepolicylabel'] = True

    if javascriptrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['javascriptrewritepolicylabel'] = True

    if reqhdrrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['reqhdrrewritepolicylabel'] = True

    if reshdrrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['reshdrrewritepolicylabel'] = True

    if regexforfindingurlinjavascript:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinjavascript'] = True

    if regexforfindingurlincss:
        payload['vpnclientlessaccessprofile']['regexforfindingurlincss'] = True

    if regexforfindingurlinxcomponent:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinxcomponent'] = True

    if regexforfindingurlinxml:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinxml'] = True

    if regexforfindingcustomurls:
        payload['vpnclientlessaccessprofile']['regexforfindingcustomurls'] = True

    if clientconsumedcookies:
        payload['vpnclientlessaccessprofile']['clientconsumedcookies'] = True

    if requirepersistentcookie:
        payload['vpnclientlessaccessprofile']['requirepersistentcookie'] = True

    execution = __proxy__['citrixns.post']('config/vpnclientlessaccessprofile?action=unset', payload)

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


def unset_vpnformssoaction(name=None, actionurl=None, userfield=None, passwdfield=None, ssosuccessrule=None,
                           namevaluepair=None, responsesize=None, nvtype=None, submitmethod=None, save=False):
    '''
    Unsets values from the vpnformssoaction configuration key.

    name(bool): Unsets the name value.

    actionurl(bool): Unsets the actionurl value.

    userfield(bool): Unsets the userfield value.

    passwdfield(bool): Unsets the passwdfield value.

    ssosuccessrule(bool): Unsets the ssosuccessrule value.

    namevaluepair(bool): Unsets the namevaluepair value.

    responsesize(bool): Unsets the responsesize value.

    nvtype(bool): Unsets the nvtype value.

    submitmethod(bool): Unsets the submitmethod value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnformssoaction <args>

    '''

    result = {}

    payload = {'vpnformssoaction': {}}

    if name:
        payload['vpnformssoaction']['name'] = True

    if actionurl:
        payload['vpnformssoaction']['actionurl'] = True

    if userfield:
        payload['vpnformssoaction']['userfield'] = True

    if passwdfield:
        payload['vpnformssoaction']['passwdfield'] = True

    if ssosuccessrule:
        payload['vpnformssoaction']['ssosuccessrule'] = True

    if namevaluepair:
        payload['vpnformssoaction']['namevaluepair'] = True

    if responsesize:
        payload['vpnformssoaction']['responsesize'] = True

    if nvtype:
        payload['vpnformssoaction']['nvtype'] = True

    if submitmethod:
        payload['vpnformssoaction']['submitmethod'] = True

    execution = __proxy__['citrixns.post']('config/vpnformssoaction?action=unset', payload)

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


def unset_vpnparameter(httpport=None, winsip=None, dnsvservername=None, splitdns=None, icauseraccounting=None,
                       sesstimeout=None, clientsecurity=None, clientsecuritygroup=None, clientsecuritymessage=None,
                       clientsecuritylog=None, smartgroup=None, splittunnel=None, locallanaccess=None, rfc1918=None,
                       spoofiip=None, killconnections=None, transparentinterception=None, windowsclienttype=None,
                       defaultauthorizationaction=None, authorizationgroup=None, clientidletimeout=None, proxy=None,
                       allprotocolproxy=None, httpproxy=None, ftpproxy=None, socksproxy=None, gopherproxy=None,
                       sslproxy=None, proxyexception=None, proxylocalbypass=None, clientcleanupprompt=None,
                       forcecleanup=None, clientoptions=None, clientconfiguration=None, sso=None, ssocredential=None,
                       windowsautologon=None, usemip=None, useiip=None, clientdebug=None, loginscript=None,
                       logoutscript=None, homepage=None, icaproxy=None, wihome=None, wihomeaddresstype=None,
                       citrixreceiverhome=None, wiportalmode=None, clientchoices=None, epaclienttype=None,
                       iipdnssuffix=None, forcedtimeout=None, forcedtimeoutwarning=None, ntdomain=None,
                       clientlessvpnmode=None, clientlessmodeurlencoding=None, clientlesspersistentcookie=None,
                       emailhome=None, allowedlogingroups=None, encryptcsecexp=None, apptokentimeout=None,
                       mdxtokentimeout=None, uitheme=None, securebrowse=None, storefronturl=None, kcdaccount=None,
                       clientversions=None, rdpclientprofilename=None, windowspluginupgrade=None, macpluginupgrade=None,
                       linuxpluginupgrade=None, iconwithreceiver=None, userdomains=None, icasessiontimeout=None,
                       alwaysonprofilename=None, autoproxyurl=None, pcoipprofilename=None, save=False):
    '''
    Unsets values from the vpnparameter configuration key.

    httpport(bool): Unsets the httpport value.

    winsip(bool): Unsets the winsip value.

    dnsvservername(bool): Unsets the dnsvservername value.

    splitdns(bool): Unsets the splitdns value.

    icauseraccounting(bool): Unsets the icauseraccounting value.

    sesstimeout(bool): Unsets the sesstimeout value.

    clientsecurity(bool): Unsets the clientsecurity value.

    clientsecuritygroup(bool): Unsets the clientsecuritygroup value.

    clientsecuritymessage(bool): Unsets the clientsecuritymessage value.

    clientsecuritylog(bool): Unsets the clientsecuritylog value.

    smartgroup(bool): Unsets the smartgroup value.

    splittunnel(bool): Unsets the splittunnel value.

    locallanaccess(bool): Unsets the locallanaccess value.

    rfc1918(bool): Unsets the rfc1918 value.

    spoofiip(bool): Unsets the spoofiip value.

    killconnections(bool): Unsets the killconnections value.

    transparentinterception(bool): Unsets the transparentinterception value.

    windowsclienttype(bool): Unsets the windowsclienttype value.

    defaultauthorizationaction(bool): Unsets the defaultauthorizationaction value.

    authorizationgroup(bool): Unsets the authorizationgroup value.

    clientidletimeout(bool): Unsets the clientidletimeout value.

    proxy(bool): Unsets the proxy value.

    allprotocolproxy(bool): Unsets the allprotocolproxy value.

    httpproxy(bool): Unsets the httpproxy value.

    ftpproxy(bool): Unsets the ftpproxy value.

    socksproxy(bool): Unsets the socksproxy value.

    gopherproxy(bool): Unsets the gopherproxy value.

    sslproxy(bool): Unsets the sslproxy value.

    proxyexception(bool): Unsets the proxyexception value.

    proxylocalbypass(bool): Unsets the proxylocalbypass value.

    clientcleanupprompt(bool): Unsets the clientcleanupprompt value.

    forcecleanup(bool): Unsets the forcecleanup value.

    clientoptions(bool): Unsets the clientoptions value.

    clientconfiguration(bool): Unsets the clientconfiguration value.

    sso(bool): Unsets the sso value.

    ssocredential(bool): Unsets the ssocredential value.

    windowsautologon(bool): Unsets the windowsautologon value.

    usemip(bool): Unsets the usemip value.

    useiip(bool): Unsets the useiip value.

    clientdebug(bool): Unsets the clientdebug value.

    loginscript(bool): Unsets the loginscript value.

    logoutscript(bool): Unsets the logoutscript value.

    homepage(bool): Unsets the homepage value.

    icaproxy(bool): Unsets the icaproxy value.

    wihome(bool): Unsets the wihome value.

    wihomeaddresstype(bool): Unsets the wihomeaddresstype value.

    citrixreceiverhome(bool): Unsets the citrixreceiverhome value.

    wiportalmode(bool): Unsets the wiportalmode value.

    clientchoices(bool): Unsets the clientchoices value.

    epaclienttype(bool): Unsets the epaclienttype value.

    iipdnssuffix(bool): Unsets the iipdnssuffix value.

    forcedtimeout(bool): Unsets the forcedtimeout value.

    forcedtimeoutwarning(bool): Unsets the forcedtimeoutwarning value.

    ntdomain(bool): Unsets the ntdomain value.

    clientlessvpnmode(bool): Unsets the clientlessvpnmode value.

    clientlessmodeurlencoding(bool): Unsets the clientlessmodeurlencoding value.

    clientlesspersistentcookie(bool): Unsets the clientlesspersistentcookie value.

    emailhome(bool): Unsets the emailhome value.

    allowedlogingroups(bool): Unsets the allowedlogingroups value.

    encryptcsecexp(bool): Unsets the encryptcsecexp value.

    apptokentimeout(bool): Unsets the apptokentimeout value.

    mdxtokentimeout(bool): Unsets the mdxtokentimeout value.

    uitheme(bool): Unsets the uitheme value.

    securebrowse(bool): Unsets the securebrowse value.

    storefronturl(bool): Unsets the storefronturl value.

    kcdaccount(bool): Unsets the kcdaccount value.

    clientversions(bool): Unsets the clientversions value.

    rdpclientprofilename(bool): Unsets the rdpclientprofilename value.

    windowspluginupgrade(bool): Unsets the windowspluginupgrade value.

    macpluginupgrade(bool): Unsets the macpluginupgrade value.

    linuxpluginupgrade(bool): Unsets the linuxpluginupgrade value.

    iconwithreceiver(bool): Unsets the iconwithreceiver value.

    userdomains(bool): Unsets the userdomains value.

    icasessiontimeout(bool): Unsets the icasessiontimeout value.

    alwaysonprofilename(bool): Unsets the alwaysonprofilename value.

    autoproxyurl(bool): Unsets the autoproxyurl value.

    pcoipprofilename(bool): Unsets the pcoipprofilename value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnparameter <args>

    '''

    result = {}

    payload = {'vpnparameter': {}}

    if httpport:
        payload['vpnparameter']['httpport'] = True

    if winsip:
        payload['vpnparameter']['winsip'] = True

    if dnsvservername:
        payload['vpnparameter']['dnsvservername'] = True

    if splitdns:
        payload['vpnparameter']['splitdns'] = True

    if icauseraccounting:
        payload['vpnparameter']['icauseraccounting'] = True

    if sesstimeout:
        payload['vpnparameter']['sesstimeout'] = True

    if clientsecurity:
        payload['vpnparameter']['clientsecurity'] = True

    if clientsecuritygroup:
        payload['vpnparameter']['clientsecuritygroup'] = True

    if clientsecuritymessage:
        payload['vpnparameter']['clientsecuritymessage'] = True

    if clientsecuritylog:
        payload['vpnparameter']['clientsecuritylog'] = True

    if smartgroup:
        payload['vpnparameter']['smartgroup'] = True

    if splittunnel:
        payload['vpnparameter']['splittunnel'] = True

    if locallanaccess:
        payload['vpnparameter']['locallanaccess'] = True

    if rfc1918:
        payload['vpnparameter']['rfc1918'] = True

    if spoofiip:
        payload['vpnparameter']['spoofiip'] = True

    if killconnections:
        payload['vpnparameter']['killconnections'] = True

    if transparentinterception:
        payload['vpnparameter']['transparentinterception'] = True

    if windowsclienttype:
        payload['vpnparameter']['windowsclienttype'] = True

    if defaultauthorizationaction:
        payload['vpnparameter']['defaultauthorizationaction'] = True

    if authorizationgroup:
        payload['vpnparameter']['authorizationgroup'] = True

    if clientidletimeout:
        payload['vpnparameter']['clientidletimeout'] = True

    if proxy:
        payload['vpnparameter']['proxy'] = True

    if allprotocolproxy:
        payload['vpnparameter']['allprotocolproxy'] = True

    if httpproxy:
        payload['vpnparameter']['httpproxy'] = True

    if ftpproxy:
        payload['vpnparameter']['ftpproxy'] = True

    if socksproxy:
        payload['vpnparameter']['socksproxy'] = True

    if gopherproxy:
        payload['vpnparameter']['gopherproxy'] = True

    if sslproxy:
        payload['vpnparameter']['sslproxy'] = True

    if proxyexception:
        payload['vpnparameter']['proxyexception'] = True

    if proxylocalbypass:
        payload['vpnparameter']['proxylocalbypass'] = True

    if clientcleanupprompt:
        payload['vpnparameter']['clientcleanupprompt'] = True

    if forcecleanup:
        payload['vpnparameter']['forcecleanup'] = True

    if clientoptions:
        payload['vpnparameter']['clientoptions'] = True

    if clientconfiguration:
        payload['vpnparameter']['clientconfiguration'] = True

    if sso:
        payload['vpnparameter']['sso'] = True

    if ssocredential:
        payload['vpnparameter']['ssocredential'] = True

    if windowsautologon:
        payload['vpnparameter']['windowsautologon'] = True

    if usemip:
        payload['vpnparameter']['usemip'] = True

    if useiip:
        payload['vpnparameter']['useiip'] = True

    if clientdebug:
        payload['vpnparameter']['clientdebug'] = True

    if loginscript:
        payload['vpnparameter']['loginscript'] = True

    if logoutscript:
        payload['vpnparameter']['logoutscript'] = True

    if homepage:
        payload['vpnparameter']['homepage'] = True

    if icaproxy:
        payload['vpnparameter']['icaproxy'] = True

    if wihome:
        payload['vpnparameter']['wihome'] = True

    if wihomeaddresstype:
        payload['vpnparameter']['wihomeaddresstype'] = True

    if citrixreceiverhome:
        payload['vpnparameter']['citrixreceiverhome'] = True

    if wiportalmode:
        payload['vpnparameter']['wiportalmode'] = True

    if clientchoices:
        payload['vpnparameter']['clientchoices'] = True

    if epaclienttype:
        payload['vpnparameter']['epaclienttype'] = True

    if iipdnssuffix:
        payload['vpnparameter']['iipdnssuffix'] = True

    if forcedtimeout:
        payload['vpnparameter']['forcedtimeout'] = True

    if forcedtimeoutwarning:
        payload['vpnparameter']['forcedtimeoutwarning'] = True

    if ntdomain:
        payload['vpnparameter']['ntdomain'] = True

    if clientlessvpnmode:
        payload['vpnparameter']['clientlessvpnmode'] = True

    if clientlessmodeurlencoding:
        payload['vpnparameter']['clientlessmodeurlencoding'] = True

    if clientlesspersistentcookie:
        payload['vpnparameter']['clientlesspersistentcookie'] = True

    if emailhome:
        payload['vpnparameter']['emailhome'] = True

    if allowedlogingroups:
        payload['vpnparameter']['allowedlogingroups'] = True

    if encryptcsecexp:
        payload['vpnparameter']['encryptcsecexp'] = True

    if apptokentimeout:
        payload['vpnparameter']['apptokentimeout'] = True

    if mdxtokentimeout:
        payload['vpnparameter']['mdxtokentimeout'] = True

    if uitheme:
        payload['vpnparameter']['uitheme'] = True

    if securebrowse:
        payload['vpnparameter']['securebrowse'] = True

    if storefronturl:
        payload['vpnparameter']['storefronturl'] = True

    if kcdaccount:
        payload['vpnparameter']['kcdaccount'] = True

    if clientversions:
        payload['vpnparameter']['clientversions'] = True

    if rdpclientprofilename:
        payload['vpnparameter']['rdpclientprofilename'] = True

    if windowspluginupgrade:
        payload['vpnparameter']['windowspluginupgrade'] = True

    if macpluginupgrade:
        payload['vpnparameter']['macpluginupgrade'] = True

    if linuxpluginupgrade:
        payload['vpnparameter']['linuxpluginupgrade'] = True

    if iconwithreceiver:
        payload['vpnparameter']['iconwithreceiver'] = True

    if userdomains:
        payload['vpnparameter']['userdomains'] = True

    if icasessiontimeout:
        payload['vpnparameter']['icasessiontimeout'] = True

    if alwaysonprofilename:
        payload['vpnparameter']['alwaysonprofilename'] = True

    if autoproxyurl:
        payload['vpnparameter']['autoproxyurl'] = True

    if pcoipprofilename:
        payload['vpnparameter']['pcoipprofilename'] = True

    execution = __proxy__['citrixns.post']('config/vpnparameter?action=unset', payload)

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


def unset_vpnpcoipprofile(name=None, conserverurl=None, icvverification=None, sessionidletimeout=None, save=False):
    '''
    Unsets values from the vpnpcoipprofile configuration key.

    name(bool): Unsets the name value.

    conserverurl(bool): Unsets the conserverurl value.

    icvverification(bool): Unsets the icvverification value.

    sessionidletimeout(bool): Unsets the sessionidletimeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnpcoipprofile <args>

    '''

    result = {}

    payload = {'vpnpcoipprofile': {}}

    if name:
        payload['vpnpcoipprofile']['name'] = True

    if conserverurl:
        payload['vpnpcoipprofile']['conserverurl'] = True

    if icvverification:
        payload['vpnpcoipprofile']['icvverification'] = True

    if sessionidletimeout:
        payload['vpnpcoipprofile']['sessionidletimeout'] = True

    execution = __proxy__['citrixns.post']('config/vpnpcoipprofile?action=unset', payload)

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


def unset_vpnpcoipvserverprofile(name=None, logindomain=None, udpport=None, save=False):
    '''
    Unsets values from the vpnpcoipvserverprofile configuration key.

    name(bool): Unsets the name value.

    logindomain(bool): Unsets the logindomain value.

    udpport(bool): Unsets the udpport value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnpcoipvserverprofile <args>

    '''

    result = {}

    payload = {'vpnpcoipvserverprofile': {}}

    if name:
        payload['vpnpcoipvserverprofile']['name'] = True

    if logindomain:
        payload['vpnpcoipvserverprofile']['logindomain'] = True

    if udpport:
        payload['vpnpcoipvserverprofile']['udpport'] = True

    execution = __proxy__['citrixns.post']('config/vpnpcoipvserverprofile?action=unset', payload)

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


def unset_vpnsamlssoprofile(name=None, samlsigningcertname=None, assertionconsumerserviceurl=None, relaystaterule=None,
                            sendpassword=None, samlissuername=None, signaturealg=None, digestmethod=None, audience=None,
                            nameidformat=None, nameidexpr=None, attribute1=None, attribute1expr=None,
                            attribute1friendlyname=None, attribute1format=None, attribute2=None, attribute2expr=None,
                            attribute2friendlyname=None, attribute2format=None, attribute3=None, attribute3expr=None,
                            attribute3friendlyname=None, attribute3format=None, attribute4=None, attribute4expr=None,
                            attribute4friendlyname=None, attribute4format=None, attribute5=None, attribute5expr=None,
                            attribute5friendlyname=None, attribute5format=None, attribute6=None, attribute6expr=None,
                            attribute6friendlyname=None, attribute6format=None, attribute7=None, attribute7expr=None,
                            attribute7friendlyname=None, attribute7format=None, attribute8=None, attribute8expr=None,
                            attribute8friendlyname=None, attribute8format=None, attribute9=None, attribute9expr=None,
                            attribute9friendlyname=None, attribute9format=None, attribute10=None, attribute10expr=None,
                            attribute10friendlyname=None, attribute10format=None, attribute11=None, attribute11expr=None,
                            attribute11friendlyname=None, attribute11format=None, attribute12=None, attribute12expr=None,
                            attribute12friendlyname=None, attribute12format=None, attribute13=None, attribute13expr=None,
                            attribute13friendlyname=None, attribute13format=None, attribute14=None, attribute14expr=None,
                            attribute14friendlyname=None, attribute14format=None, attribute15=None, attribute15expr=None,
                            attribute15friendlyname=None, attribute15format=None, attribute16=None, attribute16expr=None,
                            attribute16friendlyname=None, attribute16format=None, encryptassertion=None,
                            samlspcertname=None, encryptionalgorithm=None, skewtime=None, save=False):
    '''
    Unsets values from the vpnsamlssoprofile configuration key.

    name(bool): Unsets the name value.

    samlsigningcertname(bool): Unsets the samlsigningcertname value.

    assertionconsumerserviceurl(bool): Unsets the assertionconsumerserviceurl value.

    relaystaterule(bool): Unsets the relaystaterule value.

    sendpassword(bool): Unsets the sendpassword value.

    samlissuername(bool): Unsets the samlissuername value.

    signaturealg(bool): Unsets the signaturealg value.

    digestmethod(bool): Unsets the digestmethod value.

    audience(bool): Unsets the audience value.

    nameidformat(bool): Unsets the nameidformat value.

    nameidexpr(bool): Unsets the nameidexpr value.

    attribute1(bool): Unsets the attribute1 value.

    attribute1expr(bool): Unsets the attribute1expr value.

    attribute1friendlyname(bool): Unsets the attribute1friendlyname value.

    attribute1format(bool): Unsets the attribute1format value.

    attribute2(bool): Unsets the attribute2 value.

    attribute2expr(bool): Unsets the attribute2expr value.

    attribute2friendlyname(bool): Unsets the attribute2friendlyname value.

    attribute2format(bool): Unsets the attribute2format value.

    attribute3(bool): Unsets the attribute3 value.

    attribute3expr(bool): Unsets the attribute3expr value.

    attribute3friendlyname(bool): Unsets the attribute3friendlyname value.

    attribute3format(bool): Unsets the attribute3format value.

    attribute4(bool): Unsets the attribute4 value.

    attribute4expr(bool): Unsets the attribute4expr value.

    attribute4friendlyname(bool): Unsets the attribute4friendlyname value.

    attribute4format(bool): Unsets the attribute4format value.

    attribute5(bool): Unsets the attribute5 value.

    attribute5expr(bool): Unsets the attribute5expr value.

    attribute5friendlyname(bool): Unsets the attribute5friendlyname value.

    attribute5format(bool): Unsets the attribute5format value.

    attribute6(bool): Unsets the attribute6 value.

    attribute6expr(bool): Unsets the attribute6expr value.

    attribute6friendlyname(bool): Unsets the attribute6friendlyname value.

    attribute6format(bool): Unsets the attribute6format value.

    attribute7(bool): Unsets the attribute7 value.

    attribute7expr(bool): Unsets the attribute7expr value.

    attribute7friendlyname(bool): Unsets the attribute7friendlyname value.

    attribute7format(bool): Unsets the attribute7format value.

    attribute8(bool): Unsets the attribute8 value.

    attribute8expr(bool): Unsets the attribute8expr value.

    attribute8friendlyname(bool): Unsets the attribute8friendlyname value.

    attribute8format(bool): Unsets the attribute8format value.

    attribute9(bool): Unsets the attribute9 value.

    attribute9expr(bool): Unsets the attribute9expr value.

    attribute9friendlyname(bool): Unsets the attribute9friendlyname value.

    attribute9format(bool): Unsets the attribute9format value.

    attribute10(bool): Unsets the attribute10 value.

    attribute10expr(bool): Unsets the attribute10expr value.

    attribute10friendlyname(bool): Unsets the attribute10friendlyname value.

    attribute10format(bool): Unsets the attribute10format value.

    attribute11(bool): Unsets the attribute11 value.

    attribute11expr(bool): Unsets the attribute11expr value.

    attribute11friendlyname(bool): Unsets the attribute11friendlyname value.

    attribute11format(bool): Unsets the attribute11format value.

    attribute12(bool): Unsets the attribute12 value.

    attribute12expr(bool): Unsets the attribute12expr value.

    attribute12friendlyname(bool): Unsets the attribute12friendlyname value.

    attribute12format(bool): Unsets the attribute12format value.

    attribute13(bool): Unsets the attribute13 value.

    attribute13expr(bool): Unsets the attribute13expr value.

    attribute13friendlyname(bool): Unsets the attribute13friendlyname value.

    attribute13format(bool): Unsets the attribute13format value.

    attribute14(bool): Unsets the attribute14 value.

    attribute14expr(bool): Unsets the attribute14expr value.

    attribute14friendlyname(bool): Unsets the attribute14friendlyname value.

    attribute14format(bool): Unsets the attribute14format value.

    attribute15(bool): Unsets the attribute15 value.

    attribute15expr(bool): Unsets the attribute15expr value.

    attribute15friendlyname(bool): Unsets the attribute15friendlyname value.

    attribute15format(bool): Unsets the attribute15format value.

    attribute16(bool): Unsets the attribute16 value.

    attribute16expr(bool): Unsets the attribute16expr value.

    attribute16friendlyname(bool): Unsets the attribute16friendlyname value.

    attribute16format(bool): Unsets the attribute16format value.

    encryptassertion(bool): Unsets the encryptassertion value.

    samlspcertname(bool): Unsets the samlspcertname value.

    encryptionalgorithm(bool): Unsets the encryptionalgorithm value.

    skewtime(bool): Unsets the skewtime value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnsamlssoprofile <args>

    '''

    result = {}

    payload = {'vpnsamlssoprofile': {}}

    if name:
        payload['vpnsamlssoprofile']['name'] = True

    if samlsigningcertname:
        payload['vpnsamlssoprofile']['samlsigningcertname'] = True

    if assertionconsumerserviceurl:
        payload['vpnsamlssoprofile']['assertionconsumerserviceurl'] = True

    if relaystaterule:
        payload['vpnsamlssoprofile']['relaystaterule'] = True

    if sendpassword:
        payload['vpnsamlssoprofile']['sendpassword'] = True

    if samlissuername:
        payload['vpnsamlssoprofile']['samlissuername'] = True

    if signaturealg:
        payload['vpnsamlssoprofile']['signaturealg'] = True

    if digestmethod:
        payload['vpnsamlssoprofile']['digestmethod'] = True

    if audience:
        payload['vpnsamlssoprofile']['audience'] = True

    if nameidformat:
        payload['vpnsamlssoprofile']['nameidformat'] = True

    if nameidexpr:
        payload['vpnsamlssoprofile']['nameidexpr'] = True

    if attribute1:
        payload['vpnsamlssoprofile']['attribute1'] = True

    if attribute1expr:
        payload['vpnsamlssoprofile']['attribute1expr'] = True

    if attribute1friendlyname:
        payload['vpnsamlssoprofile']['attribute1friendlyname'] = True

    if attribute1format:
        payload['vpnsamlssoprofile']['attribute1format'] = True

    if attribute2:
        payload['vpnsamlssoprofile']['attribute2'] = True

    if attribute2expr:
        payload['vpnsamlssoprofile']['attribute2expr'] = True

    if attribute2friendlyname:
        payload['vpnsamlssoprofile']['attribute2friendlyname'] = True

    if attribute2format:
        payload['vpnsamlssoprofile']['attribute2format'] = True

    if attribute3:
        payload['vpnsamlssoprofile']['attribute3'] = True

    if attribute3expr:
        payload['vpnsamlssoprofile']['attribute3expr'] = True

    if attribute3friendlyname:
        payload['vpnsamlssoprofile']['attribute3friendlyname'] = True

    if attribute3format:
        payload['vpnsamlssoprofile']['attribute3format'] = True

    if attribute4:
        payload['vpnsamlssoprofile']['attribute4'] = True

    if attribute4expr:
        payload['vpnsamlssoprofile']['attribute4expr'] = True

    if attribute4friendlyname:
        payload['vpnsamlssoprofile']['attribute4friendlyname'] = True

    if attribute4format:
        payload['vpnsamlssoprofile']['attribute4format'] = True

    if attribute5:
        payload['vpnsamlssoprofile']['attribute5'] = True

    if attribute5expr:
        payload['vpnsamlssoprofile']['attribute5expr'] = True

    if attribute5friendlyname:
        payload['vpnsamlssoprofile']['attribute5friendlyname'] = True

    if attribute5format:
        payload['vpnsamlssoprofile']['attribute5format'] = True

    if attribute6:
        payload['vpnsamlssoprofile']['attribute6'] = True

    if attribute6expr:
        payload['vpnsamlssoprofile']['attribute6expr'] = True

    if attribute6friendlyname:
        payload['vpnsamlssoprofile']['attribute6friendlyname'] = True

    if attribute6format:
        payload['vpnsamlssoprofile']['attribute6format'] = True

    if attribute7:
        payload['vpnsamlssoprofile']['attribute7'] = True

    if attribute7expr:
        payload['vpnsamlssoprofile']['attribute7expr'] = True

    if attribute7friendlyname:
        payload['vpnsamlssoprofile']['attribute7friendlyname'] = True

    if attribute7format:
        payload['vpnsamlssoprofile']['attribute7format'] = True

    if attribute8:
        payload['vpnsamlssoprofile']['attribute8'] = True

    if attribute8expr:
        payload['vpnsamlssoprofile']['attribute8expr'] = True

    if attribute8friendlyname:
        payload['vpnsamlssoprofile']['attribute8friendlyname'] = True

    if attribute8format:
        payload['vpnsamlssoprofile']['attribute8format'] = True

    if attribute9:
        payload['vpnsamlssoprofile']['attribute9'] = True

    if attribute9expr:
        payload['vpnsamlssoprofile']['attribute9expr'] = True

    if attribute9friendlyname:
        payload['vpnsamlssoprofile']['attribute9friendlyname'] = True

    if attribute9format:
        payload['vpnsamlssoprofile']['attribute9format'] = True

    if attribute10:
        payload['vpnsamlssoprofile']['attribute10'] = True

    if attribute10expr:
        payload['vpnsamlssoprofile']['attribute10expr'] = True

    if attribute10friendlyname:
        payload['vpnsamlssoprofile']['attribute10friendlyname'] = True

    if attribute10format:
        payload['vpnsamlssoprofile']['attribute10format'] = True

    if attribute11:
        payload['vpnsamlssoprofile']['attribute11'] = True

    if attribute11expr:
        payload['vpnsamlssoprofile']['attribute11expr'] = True

    if attribute11friendlyname:
        payload['vpnsamlssoprofile']['attribute11friendlyname'] = True

    if attribute11format:
        payload['vpnsamlssoprofile']['attribute11format'] = True

    if attribute12:
        payload['vpnsamlssoprofile']['attribute12'] = True

    if attribute12expr:
        payload['vpnsamlssoprofile']['attribute12expr'] = True

    if attribute12friendlyname:
        payload['vpnsamlssoprofile']['attribute12friendlyname'] = True

    if attribute12format:
        payload['vpnsamlssoprofile']['attribute12format'] = True

    if attribute13:
        payload['vpnsamlssoprofile']['attribute13'] = True

    if attribute13expr:
        payload['vpnsamlssoprofile']['attribute13expr'] = True

    if attribute13friendlyname:
        payload['vpnsamlssoprofile']['attribute13friendlyname'] = True

    if attribute13format:
        payload['vpnsamlssoprofile']['attribute13format'] = True

    if attribute14:
        payload['vpnsamlssoprofile']['attribute14'] = True

    if attribute14expr:
        payload['vpnsamlssoprofile']['attribute14expr'] = True

    if attribute14friendlyname:
        payload['vpnsamlssoprofile']['attribute14friendlyname'] = True

    if attribute14format:
        payload['vpnsamlssoprofile']['attribute14format'] = True

    if attribute15:
        payload['vpnsamlssoprofile']['attribute15'] = True

    if attribute15expr:
        payload['vpnsamlssoprofile']['attribute15expr'] = True

    if attribute15friendlyname:
        payload['vpnsamlssoprofile']['attribute15friendlyname'] = True

    if attribute15format:
        payload['vpnsamlssoprofile']['attribute15format'] = True

    if attribute16:
        payload['vpnsamlssoprofile']['attribute16'] = True

    if attribute16expr:
        payload['vpnsamlssoprofile']['attribute16expr'] = True

    if attribute16friendlyname:
        payload['vpnsamlssoprofile']['attribute16friendlyname'] = True

    if attribute16format:
        payload['vpnsamlssoprofile']['attribute16format'] = True

    if encryptassertion:
        payload['vpnsamlssoprofile']['encryptassertion'] = True

    if samlspcertname:
        payload['vpnsamlssoprofile']['samlspcertname'] = True

    if encryptionalgorithm:
        payload['vpnsamlssoprofile']['encryptionalgorithm'] = True

    if skewtime:
        payload['vpnsamlssoprofile']['skewtime'] = True

    execution = __proxy__['citrixns.post']('config/vpnsamlssoprofile?action=unset', payload)

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


def unset_vpnsessionaction(name=None, useraccounting=None, httpport=None, winsip=None, dnsvservername=None,
                           splitdns=None, sesstimeout=None, clientsecurity=None, clientsecuritygroup=None,
                           clientsecuritymessage=None, clientsecuritylog=None, splittunnel=None, locallanaccess=None,
                           rfc1918=None, spoofiip=None, killconnections=None, transparentinterception=None,
                           windowsclienttype=None, defaultauthorizationaction=None, authorizationgroup=None,
                           smartgroup=None, clientidletimeout=None, proxy=None, allprotocolproxy=None, httpproxy=None,
                           ftpproxy=None, socksproxy=None, gopherproxy=None, sslproxy=None, proxyexception=None,
                           proxylocalbypass=None, clientcleanupprompt=None, forcecleanup=None, clientoptions=None,
                           clientconfiguration=None, sso=None, ssocredential=None, windowsautologon=None, usemip=None,
                           useiip=None, clientdebug=None, loginscript=None, logoutscript=None, homepage=None,
                           icaproxy=None, wihome=None, wihomeaddresstype=None, citrixreceiverhome=None,
                           wiportalmode=None, clientchoices=None, epaclienttype=None, iipdnssuffix=None,
                           forcedtimeout=None, forcedtimeoutwarning=None, ntdomain=None, clientlessvpnmode=None,
                           emailhome=None, clientlessmodeurlencoding=None, clientlesspersistentcookie=None,
                           allowedlogingroups=None, securebrowse=None, storefronturl=None, sfgatewayauthtype=None,
                           kcdaccount=None, rdpclientprofilename=None, windowspluginupgrade=None, macpluginupgrade=None,
                           linuxpluginupgrade=None, iconwithreceiver=None, alwaysonprofilename=None, autoproxyurl=None,
                           pcoipprofilename=None, save=False):
    '''
    Unsets values from the vpnsessionaction configuration key.

    name(bool): Unsets the name value.

    useraccounting(bool): Unsets the useraccounting value.

    httpport(bool): Unsets the httpport value.

    winsip(bool): Unsets the winsip value.

    dnsvservername(bool): Unsets the dnsvservername value.

    splitdns(bool): Unsets the splitdns value.

    sesstimeout(bool): Unsets the sesstimeout value.

    clientsecurity(bool): Unsets the clientsecurity value.

    clientsecuritygroup(bool): Unsets the clientsecuritygroup value.

    clientsecuritymessage(bool): Unsets the clientsecuritymessage value.

    clientsecuritylog(bool): Unsets the clientsecuritylog value.

    splittunnel(bool): Unsets the splittunnel value.

    locallanaccess(bool): Unsets the locallanaccess value.

    rfc1918(bool): Unsets the rfc1918 value.

    spoofiip(bool): Unsets the spoofiip value.

    killconnections(bool): Unsets the killconnections value.

    transparentinterception(bool): Unsets the transparentinterception value.

    windowsclienttype(bool): Unsets the windowsclienttype value.

    defaultauthorizationaction(bool): Unsets the defaultauthorizationaction value.

    authorizationgroup(bool): Unsets the authorizationgroup value.

    smartgroup(bool): Unsets the smartgroup value.

    clientidletimeout(bool): Unsets the clientidletimeout value.

    proxy(bool): Unsets the proxy value.

    allprotocolproxy(bool): Unsets the allprotocolproxy value.

    httpproxy(bool): Unsets the httpproxy value.

    ftpproxy(bool): Unsets the ftpproxy value.

    socksproxy(bool): Unsets the socksproxy value.

    gopherproxy(bool): Unsets the gopherproxy value.

    sslproxy(bool): Unsets the sslproxy value.

    proxyexception(bool): Unsets the proxyexception value.

    proxylocalbypass(bool): Unsets the proxylocalbypass value.

    clientcleanupprompt(bool): Unsets the clientcleanupprompt value.

    forcecleanup(bool): Unsets the forcecleanup value.

    clientoptions(bool): Unsets the clientoptions value.

    clientconfiguration(bool): Unsets the clientconfiguration value.

    sso(bool): Unsets the sso value.

    ssocredential(bool): Unsets the ssocredential value.

    windowsautologon(bool): Unsets the windowsautologon value.

    usemip(bool): Unsets the usemip value.

    useiip(bool): Unsets the useiip value.

    clientdebug(bool): Unsets the clientdebug value.

    loginscript(bool): Unsets the loginscript value.

    logoutscript(bool): Unsets the logoutscript value.

    homepage(bool): Unsets the homepage value.

    icaproxy(bool): Unsets the icaproxy value.

    wihome(bool): Unsets the wihome value.

    wihomeaddresstype(bool): Unsets the wihomeaddresstype value.

    citrixreceiverhome(bool): Unsets the citrixreceiverhome value.

    wiportalmode(bool): Unsets the wiportalmode value.

    clientchoices(bool): Unsets the clientchoices value.

    epaclienttype(bool): Unsets the epaclienttype value.

    iipdnssuffix(bool): Unsets the iipdnssuffix value.

    forcedtimeout(bool): Unsets the forcedtimeout value.

    forcedtimeoutwarning(bool): Unsets the forcedtimeoutwarning value.

    ntdomain(bool): Unsets the ntdomain value.

    clientlessvpnmode(bool): Unsets the clientlessvpnmode value.

    emailhome(bool): Unsets the emailhome value.

    clientlessmodeurlencoding(bool): Unsets the clientlessmodeurlencoding value.

    clientlesspersistentcookie(bool): Unsets the clientlesspersistentcookie value.

    allowedlogingroups(bool): Unsets the allowedlogingroups value.

    securebrowse(bool): Unsets the securebrowse value.

    storefronturl(bool): Unsets the storefronturl value.

    sfgatewayauthtype(bool): Unsets the sfgatewayauthtype value.

    kcdaccount(bool): Unsets the kcdaccount value.

    rdpclientprofilename(bool): Unsets the rdpclientprofilename value.

    windowspluginupgrade(bool): Unsets the windowspluginupgrade value.

    macpluginupgrade(bool): Unsets the macpluginupgrade value.

    linuxpluginupgrade(bool): Unsets the linuxpluginupgrade value.

    iconwithreceiver(bool): Unsets the iconwithreceiver value.

    alwaysonprofilename(bool): Unsets the alwaysonprofilename value.

    autoproxyurl(bool): Unsets the autoproxyurl value.

    pcoipprofilename(bool): Unsets the pcoipprofilename value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnsessionaction <args>

    '''

    result = {}

    payload = {'vpnsessionaction': {}}

    if name:
        payload['vpnsessionaction']['name'] = True

    if useraccounting:
        payload['vpnsessionaction']['useraccounting'] = True

    if httpport:
        payload['vpnsessionaction']['httpport'] = True

    if winsip:
        payload['vpnsessionaction']['winsip'] = True

    if dnsvservername:
        payload['vpnsessionaction']['dnsvservername'] = True

    if splitdns:
        payload['vpnsessionaction']['splitdns'] = True

    if sesstimeout:
        payload['vpnsessionaction']['sesstimeout'] = True

    if clientsecurity:
        payload['vpnsessionaction']['clientsecurity'] = True

    if clientsecuritygroup:
        payload['vpnsessionaction']['clientsecuritygroup'] = True

    if clientsecuritymessage:
        payload['vpnsessionaction']['clientsecuritymessage'] = True

    if clientsecuritylog:
        payload['vpnsessionaction']['clientsecuritylog'] = True

    if splittunnel:
        payload['vpnsessionaction']['splittunnel'] = True

    if locallanaccess:
        payload['vpnsessionaction']['locallanaccess'] = True

    if rfc1918:
        payload['vpnsessionaction']['rfc1918'] = True

    if spoofiip:
        payload['vpnsessionaction']['spoofiip'] = True

    if killconnections:
        payload['vpnsessionaction']['killconnections'] = True

    if transparentinterception:
        payload['vpnsessionaction']['transparentinterception'] = True

    if windowsclienttype:
        payload['vpnsessionaction']['windowsclienttype'] = True

    if defaultauthorizationaction:
        payload['vpnsessionaction']['defaultauthorizationaction'] = True

    if authorizationgroup:
        payload['vpnsessionaction']['authorizationgroup'] = True

    if smartgroup:
        payload['vpnsessionaction']['smartgroup'] = True

    if clientidletimeout:
        payload['vpnsessionaction']['clientidletimeout'] = True

    if proxy:
        payload['vpnsessionaction']['proxy'] = True

    if allprotocolproxy:
        payload['vpnsessionaction']['allprotocolproxy'] = True

    if httpproxy:
        payload['vpnsessionaction']['httpproxy'] = True

    if ftpproxy:
        payload['vpnsessionaction']['ftpproxy'] = True

    if socksproxy:
        payload['vpnsessionaction']['socksproxy'] = True

    if gopherproxy:
        payload['vpnsessionaction']['gopherproxy'] = True

    if sslproxy:
        payload['vpnsessionaction']['sslproxy'] = True

    if proxyexception:
        payload['vpnsessionaction']['proxyexception'] = True

    if proxylocalbypass:
        payload['vpnsessionaction']['proxylocalbypass'] = True

    if clientcleanupprompt:
        payload['vpnsessionaction']['clientcleanupprompt'] = True

    if forcecleanup:
        payload['vpnsessionaction']['forcecleanup'] = True

    if clientoptions:
        payload['vpnsessionaction']['clientoptions'] = True

    if clientconfiguration:
        payload['vpnsessionaction']['clientconfiguration'] = True

    if sso:
        payload['vpnsessionaction']['sso'] = True

    if ssocredential:
        payload['vpnsessionaction']['ssocredential'] = True

    if windowsautologon:
        payload['vpnsessionaction']['windowsautologon'] = True

    if usemip:
        payload['vpnsessionaction']['usemip'] = True

    if useiip:
        payload['vpnsessionaction']['useiip'] = True

    if clientdebug:
        payload['vpnsessionaction']['clientdebug'] = True

    if loginscript:
        payload['vpnsessionaction']['loginscript'] = True

    if logoutscript:
        payload['vpnsessionaction']['logoutscript'] = True

    if homepage:
        payload['vpnsessionaction']['homepage'] = True

    if icaproxy:
        payload['vpnsessionaction']['icaproxy'] = True

    if wihome:
        payload['vpnsessionaction']['wihome'] = True

    if wihomeaddresstype:
        payload['vpnsessionaction']['wihomeaddresstype'] = True

    if citrixreceiverhome:
        payload['vpnsessionaction']['citrixreceiverhome'] = True

    if wiportalmode:
        payload['vpnsessionaction']['wiportalmode'] = True

    if clientchoices:
        payload['vpnsessionaction']['clientchoices'] = True

    if epaclienttype:
        payload['vpnsessionaction']['epaclienttype'] = True

    if iipdnssuffix:
        payload['vpnsessionaction']['iipdnssuffix'] = True

    if forcedtimeout:
        payload['vpnsessionaction']['forcedtimeout'] = True

    if forcedtimeoutwarning:
        payload['vpnsessionaction']['forcedtimeoutwarning'] = True

    if ntdomain:
        payload['vpnsessionaction']['ntdomain'] = True

    if clientlessvpnmode:
        payload['vpnsessionaction']['clientlessvpnmode'] = True

    if emailhome:
        payload['vpnsessionaction']['emailhome'] = True

    if clientlessmodeurlencoding:
        payload['vpnsessionaction']['clientlessmodeurlencoding'] = True

    if clientlesspersistentcookie:
        payload['vpnsessionaction']['clientlesspersistentcookie'] = True

    if allowedlogingroups:
        payload['vpnsessionaction']['allowedlogingroups'] = True

    if securebrowse:
        payload['vpnsessionaction']['securebrowse'] = True

    if storefronturl:
        payload['vpnsessionaction']['storefronturl'] = True

    if sfgatewayauthtype:
        payload['vpnsessionaction']['sfgatewayauthtype'] = True

    if kcdaccount:
        payload['vpnsessionaction']['kcdaccount'] = True

    if rdpclientprofilename:
        payload['vpnsessionaction']['rdpclientprofilename'] = True

    if windowspluginupgrade:
        payload['vpnsessionaction']['windowspluginupgrade'] = True

    if macpluginupgrade:
        payload['vpnsessionaction']['macpluginupgrade'] = True

    if linuxpluginupgrade:
        payload['vpnsessionaction']['linuxpluginupgrade'] = True

    if iconwithreceiver:
        payload['vpnsessionaction']['iconwithreceiver'] = True

    if alwaysonprofilename:
        payload['vpnsessionaction']['alwaysonprofilename'] = True

    if autoproxyurl:
        payload['vpnsessionaction']['autoproxyurl'] = True

    if pcoipprofilename:
        payload['vpnsessionaction']['pcoipprofilename'] = True

    execution = __proxy__['citrixns.post']('config/vpnsessionaction?action=unset', payload)

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


def unset_vpnsessionpolicy(name=None, rule=None, action=None, save=False):
    '''
    Unsets values from the vpnsessionpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnsessionpolicy <args>

    '''

    result = {}

    payload = {'vpnsessionpolicy': {}}

    if name:
        payload['vpnsessionpolicy']['name'] = True

    if rule:
        payload['vpnsessionpolicy']['rule'] = True

    if action:
        payload['vpnsessionpolicy']['action'] = True

    execution = __proxy__['citrixns.post']('config/vpnsessionpolicy?action=unset', payload)

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


def unset_vpntrafficaction(name=None, qual=None, apptimeout=None, sso=None, hdx=None, formssoaction=None, fta=None,
                           wanscaler=None, kcdaccount=None, samlssoprofile=None, proxy=None, userexpression=None,
                           passwdexpression=None, save=False):
    '''
    Unsets values from the vpntrafficaction configuration key.

    name(bool): Unsets the name value.

    qual(bool): Unsets the qual value.

    apptimeout(bool): Unsets the apptimeout value.

    sso(bool): Unsets the sso value.

    hdx(bool): Unsets the hdx value.

    formssoaction(bool): Unsets the formssoaction value.

    fta(bool): Unsets the fta value.

    wanscaler(bool): Unsets the wanscaler value.

    kcdaccount(bool): Unsets the kcdaccount value.

    samlssoprofile(bool): Unsets the samlssoprofile value.

    proxy(bool): Unsets the proxy value.

    userexpression(bool): Unsets the userexpression value.

    passwdexpression(bool): Unsets the passwdexpression value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpntrafficaction <args>

    '''

    result = {}

    payload = {'vpntrafficaction': {}}

    if name:
        payload['vpntrafficaction']['name'] = True

    if qual:
        payload['vpntrafficaction']['qual'] = True

    if apptimeout:
        payload['vpntrafficaction']['apptimeout'] = True

    if sso:
        payload['vpntrafficaction']['sso'] = True

    if hdx:
        payload['vpntrafficaction']['hdx'] = True

    if formssoaction:
        payload['vpntrafficaction']['formssoaction'] = True

    if fta:
        payload['vpntrafficaction']['fta'] = True

    if wanscaler:
        payload['vpntrafficaction']['wanscaler'] = True

    if kcdaccount:
        payload['vpntrafficaction']['kcdaccount'] = True

    if samlssoprofile:
        payload['vpntrafficaction']['samlssoprofile'] = True

    if proxy:
        payload['vpntrafficaction']['proxy'] = True

    if userexpression:
        payload['vpntrafficaction']['userexpression'] = True

    if passwdexpression:
        payload['vpntrafficaction']['passwdexpression'] = True

    execution = __proxy__['citrixns.post']('config/vpntrafficaction?action=unset', payload)

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


def unset_vpntrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Unsets values from the vpntrafficpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpntrafficpolicy <args>

    '''

    result = {}

    payload = {'vpntrafficpolicy': {}}

    if name:
        payload['vpntrafficpolicy']['name'] = True

    if rule:
        payload['vpntrafficpolicy']['rule'] = True

    if action:
        payload['vpntrafficpolicy']['action'] = True

    execution = __proxy__['citrixns.post']('config/vpntrafficpolicy?action=unset', payload)

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


def unset_vpnurl(urlname=None, linkname=None, actualurl=None, vservername=None, clientlessaccess=None, comment=None,
                 iconurl=None, ssotype=None, applicationtype=None, samlssoprofile=None, save=False):
    '''
    Unsets values from the vpnurl configuration key.

    urlname(bool): Unsets the urlname value.

    linkname(bool): Unsets the linkname value.

    actualurl(bool): Unsets the actualurl value.

    vservername(bool): Unsets the vservername value.

    clientlessaccess(bool): Unsets the clientlessaccess value.

    comment(bool): Unsets the comment value.

    iconurl(bool): Unsets the iconurl value.

    ssotype(bool): Unsets the ssotype value.

    applicationtype(bool): Unsets the applicationtype value.

    samlssoprofile(bool): Unsets the samlssoprofile value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnurl <args>

    '''

    result = {}

    payload = {'vpnurl': {}}

    if urlname:
        payload['vpnurl']['urlname'] = True

    if linkname:
        payload['vpnurl']['linkname'] = True

    if actualurl:
        payload['vpnurl']['actualurl'] = True

    if vservername:
        payload['vpnurl']['vservername'] = True

    if clientlessaccess:
        payload['vpnurl']['clientlessaccess'] = True

    if comment:
        payload['vpnurl']['comment'] = True

    if iconurl:
        payload['vpnurl']['iconurl'] = True

    if ssotype:
        payload['vpnurl']['ssotype'] = True

    if applicationtype:
        payload['vpnurl']['applicationtype'] = True

    if samlssoprofile:
        payload['vpnurl']['samlssoprofile'] = True

    execution = __proxy__['citrixns.post']('config/vpnurl?action=unset', payload)

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


def unset_vpnvserver(name=None, servicetype=None, ipv46=None, range=None, port=None, state=None, authentication=None,
                     doublehop=None, maxaaausers=None, icaonly=None, icaproxysessionmigration=None, dtls=None,
                     loginonce=None, advancedepa=None, devicecert=None, certkeynames=None, downstateflush=None,
                     listenpolicy=None, listenpriority=None, tcpprofilename=None, httpprofilename=None, comment=None,
                     appflowlog=None, icmpvsrresponse=None, rhistate=None, netprofile=None, cginfrahomepageredirect=None,
                     maxloginattempts=None, failedlogintimeout=None, l2conn=None, deploymenttype=None,
                     rdpserverprofilename=None, windowsepapluginupgrade=None, linuxepapluginupgrade=None,
                     macepapluginupgrade=None, logoutonsmartcardremoval=None, userdomains=None, authnprofile=None,
                     vserverfqdn=None, pcoipvserverprofilename=None, newname=None, save=False):
    '''
    Unsets values from the vpnvserver configuration key.

    name(bool): Unsets the name value.

    servicetype(bool): Unsets the servicetype value.

    ipv46(bool): Unsets the ipv46 value.

    range(bool): Unsets the range value.

    port(bool): Unsets the port value.

    state(bool): Unsets the state value.

    authentication(bool): Unsets the authentication value.

    doublehop(bool): Unsets the doublehop value.

    maxaaausers(bool): Unsets the maxaaausers value.

    icaonly(bool): Unsets the icaonly value.

    icaproxysessionmigration(bool): Unsets the icaproxysessionmigration value.

    dtls(bool): Unsets the dtls value.

    loginonce(bool): Unsets the loginonce value.

    advancedepa(bool): Unsets the advancedepa value.

    devicecert(bool): Unsets the devicecert value.

    certkeynames(bool): Unsets the certkeynames value.

    downstateflush(bool): Unsets the downstateflush value.

    listenpolicy(bool): Unsets the listenpolicy value.

    listenpriority(bool): Unsets the listenpriority value.

    tcpprofilename(bool): Unsets the tcpprofilename value.

    httpprofilename(bool): Unsets the httpprofilename value.

    comment(bool): Unsets the comment value.

    appflowlog(bool): Unsets the appflowlog value.

    icmpvsrresponse(bool): Unsets the icmpvsrresponse value.

    rhistate(bool): Unsets the rhistate value.

    netprofile(bool): Unsets the netprofile value.

    cginfrahomepageredirect(bool): Unsets the cginfrahomepageredirect value.

    maxloginattempts(bool): Unsets the maxloginattempts value.

    failedlogintimeout(bool): Unsets the failedlogintimeout value.

    l2conn(bool): Unsets the l2conn value.

    deploymenttype(bool): Unsets the deploymenttype value.

    rdpserverprofilename(bool): Unsets the rdpserverprofilename value.

    windowsepapluginupgrade(bool): Unsets the windowsepapluginupgrade value.

    linuxepapluginupgrade(bool): Unsets the linuxepapluginupgrade value.

    macepapluginupgrade(bool): Unsets the macepapluginupgrade value.

    logoutonsmartcardremoval(bool): Unsets the logoutonsmartcardremoval value.

    userdomains(bool): Unsets the userdomains value.

    authnprofile(bool): Unsets the authnprofile value.

    vserverfqdn(bool): Unsets the vserverfqdn value.

    pcoipvserverprofilename(bool): Unsets the pcoipvserverprofilename value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.unset_vpnvserver <args>

    '''

    result = {}

    payload = {'vpnvserver': {}}

    if name:
        payload['vpnvserver']['name'] = True

    if servicetype:
        payload['vpnvserver']['servicetype'] = True

    if ipv46:
        payload['vpnvserver']['ipv46'] = True

    if range:
        payload['vpnvserver']['range'] = True

    if port:
        payload['vpnvserver']['port'] = True

    if state:
        payload['vpnvserver']['state'] = True

    if authentication:
        payload['vpnvserver']['authentication'] = True

    if doublehop:
        payload['vpnvserver']['doublehop'] = True

    if maxaaausers:
        payload['vpnvserver']['maxaaausers'] = True

    if icaonly:
        payload['vpnvserver']['icaonly'] = True

    if icaproxysessionmigration:
        payload['vpnvserver']['icaproxysessionmigration'] = True

    if dtls:
        payload['vpnvserver']['dtls'] = True

    if loginonce:
        payload['vpnvserver']['loginonce'] = True

    if advancedepa:
        payload['vpnvserver']['advancedepa'] = True

    if devicecert:
        payload['vpnvserver']['devicecert'] = True

    if certkeynames:
        payload['vpnvserver']['certkeynames'] = True

    if downstateflush:
        payload['vpnvserver']['downstateflush'] = True

    if listenpolicy:
        payload['vpnvserver']['listenpolicy'] = True

    if listenpriority:
        payload['vpnvserver']['listenpriority'] = True

    if tcpprofilename:
        payload['vpnvserver']['tcpprofilename'] = True

    if httpprofilename:
        payload['vpnvserver']['httpprofilename'] = True

    if comment:
        payload['vpnvserver']['comment'] = True

    if appflowlog:
        payload['vpnvserver']['appflowlog'] = True

    if icmpvsrresponse:
        payload['vpnvserver']['icmpvsrresponse'] = True

    if rhistate:
        payload['vpnvserver']['rhistate'] = True

    if netprofile:
        payload['vpnvserver']['netprofile'] = True

    if cginfrahomepageredirect:
        payload['vpnvserver']['cginfrahomepageredirect'] = True

    if maxloginattempts:
        payload['vpnvserver']['maxloginattempts'] = True

    if failedlogintimeout:
        payload['vpnvserver']['failedlogintimeout'] = True

    if l2conn:
        payload['vpnvserver']['l2conn'] = True

    if deploymenttype:
        payload['vpnvserver']['deploymenttype'] = True

    if rdpserverprofilename:
        payload['vpnvserver']['rdpserverprofilename'] = True

    if windowsepapluginupgrade:
        payload['vpnvserver']['windowsepapluginupgrade'] = True

    if linuxepapluginupgrade:
        payload['vpnvserver']['linuxepapluginupgrade'] = True

    if macepapluginupgrade:
        payload['vpnvserver']['macepapluginupgrade'] = True

    if logoutonsmartcardremoval:
        payload['vpnvserver']['logoutonsmartcardremoval'] = True

    if userdomains:
        payload['vpnvserver']['userdomains'] = True

    if authnprofile:
        payload['vpnvserver']['authnprofile'] = True

    if vserverfqdn:
        payload['vpnvserver']['vserverfqdn'] = True

    if pcoipvserverprofilename:
        payload['vpnvserver']['pcoipvserverprofilename'] = True

    if newname:
        payload['vpnvserver']['newname'] = True

    execution = __proxy__['citrixns.post']('config/vpnvserver?action=unset', payload)

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


def update_vpnalwaysonprofile(name=None, networkaccessonvpnfailure=None, clientcontrol=None, locationbasedvpn=None,
                              save=False):
    '''
    Update the running configuration for the vpnalwaysonprofile config key.

    name(str): name of AlwaysON profile. Minimum length = 1

    networkaccessonvpnfailure(str): Option to block network traffic when tunnel is not established(and the config requires
        that tunnel be established). When set to onlyToGateway, the network traffic to and from the client (except
        Gateway IP) is blocked. When set to fullAccess, the network traffic is not blocked. Default value: fullAccess,
        Possible values = onlyToGateway, fullAccess

    clientcontrol(str): Allow/Deny user to log off and connect to another Gateway. Default value: DENY Possible values =
        ALLOW, DENY

    locationbasedvpn(str): Option to decide if tunnel should be established when in enterprise network. When locationBasedVPN
        is remote, client tries to detect if it is located in enterprise network or not and establishes the tunnel if not
        in enterprise network. Dns suffixes configured using -add dns suffix- are used to decide if the client is in the
        enterprise network or not. If the resolution of the DNS suffix results in private IP, client is said to be in
        enterprise network. When set to EveryWhere, the client skips the check to detect if it is on the enterprise
        network and tries to establish the tunnel. Default value: Remote Possible values = Remote, Everywhere

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnalwaysonprofile <args>

    '''

    result = {}

    payload = {'vpnalwaysonprofile': {}}

    if name:
        payload['vpnalwaysonprofile']['name'] = name

    if networkaccessonvpnfailure:
        payload['vpnalwaysonprofile']['networkaccessonvpnfailure'] = networkaccessonvpnfailure

    if clientcontrol:
        payload['vpnalwaysonprofile']['clientcontrol'] = clientcontrol

    if locationbasedvpn:
        payload['vpnalwaysonprofile']['locationbasedvpn'] = locationbasedvpn

    execution = __proxy__['citrixns.put']('config/vpnalwaysonprofile', payload)

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


def update_vpnclientlessaccesspolicy(name=None, rule=None, profilename=None, save=False):
    '''
    Update the running configuration for the vpnclientlessaccesspolicy config key.

    name(str): Name of the new clientless access policy. Minimum length = 1

    rule(str): Expression, or name of a named expression, specifying the traffic that matches the policy. Can be written in
        either default or classic syntax.  Maximum length of a string literal in the expression is 255 characters. A
        longer string can be split into smaller strings of up to 255 characters each, and the smaller strings
        concatenated with the + operator. For example, you can create a 500-character string as follows: ";lt;string of
        255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler
        CLI: * If the expression includes one or more spaces, enclose the entire expression in double quotation marks. *
        If the expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    profilename(str): Name of the profile to invoke for the clientless access.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnclientlessaccesspolicy <args>

    '''

    result = {}

    payload = {'vpnclientlessaccesspolicy': {}}

    if name:
        payload['vpnclientlessaccesspolicy']['name'] = name

    if rule:
        payload['vpnclientlessaccesspolicy']['rule'] = rule

    if profilename:
        payload['vpnclientlessaccesspolicy']['profilename'] = profilename

    execution = __proxy__['citrixns.put']('config/vpnclientlessaccesspolicy', payload)

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


def update_vpnclientlessaccessprofile(profilename=None, urlrewritepolicylabel=None, javascriptrewritepolicylabel=None,
                                      reqhdrrewritepolicylabel=None, reshdrrewritepolicylabel=None,
                                      regexforfindingurlinjavascript=None, regexforfindingurlincss=None,
                                      regexforfindingurlinxcomponent=None, regexforfindingurlinxml=None,
                                      regexforfindingcustomurls=None, clientconsumedcookies=None,
                                      requirepersistentcookie=None, save=False):
    '''
    Update the running configuration for the vpnclientlessaccessprofile config key.

    profilename(str): Name for the NetScaler Gateway clientless access profile. Must begin with an ASCII alphabetic or
        underscore (_) character, and must consist only of ASCII alphanumeric, underscore, hash (#), period (.), space,
        colon (:), at (@), equals (=), and hyphen (-) characters. Cannot be changed after the profile is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my profile" or my profile). Minimum length = 1

    urlrewritepolicylabel(str): Name of the configured URL rewrite policy label. If you do not specify a policy label name,
        then URLs are not rewritten. Minimum length = 1

    javascriptrewritepolicylabel(str): Name of the configured JavaScript rewrite policy label. If you do not specify a policy
        label name, then JAVA scripts are not rewritten. Minimum length = 1

    reqhdrrewritepolicylabel(str): Name of the configured Request rewrite policy label. If you do not specify a policy label
        name, then requests are not rewritten. Minimum length = 1

    reshdrrewritepolicylabel(str): Name of the configured Response rewrite policy label. Minimum length = 1

    regexforfindingurlinjavascript(str): Name of the pattern set that contains the regular expressions, which match the URL
        in Java script. Minimum length = 1

    regexforfindingurlincss(str): Name of the pattern set that contains the regular expressions, which match the URL in the
        CSS. Minimum length = 1

    regexforfindingurlinxcomponent(str): Name of the pattern set that contains the regular expressions, which match the URL
        in X Component. Minimum length = 1

    regexforfindingurlinxml(str): Name of the pattern set that contains the regular expressions, which match the URL in XML.
        Minimum length = 1

    regexforfindingcustomurls(str): Name of the pattern set that contains the regular expressions, which match the URLs in
        the custom content type other than HTML, CSS, XML, XCOMP, and JavaScript. The custom content type should be
        included in the patset ns_cvpn_custom_content_types. Minimum length = 1

    clientconsumedcookies(str): Specify the name of the pattern set containing the names of the cookies, which are allowed
        between the client and the server. If a pattern set is not specified, NetSCaler Gateway does not allow any
        cookies between the client and the server. A cookie that is not specified in the pattern set is handled by
        NetScaler Gateway on behalf of the client. Minimum length = 1

    requirepersistentcookie(str): Specify whether a persistent session cookie is set and accepted for clientless access. If
        this parameter is set to ON, COM objects, such as MSOffice, which are invoked by the browser can access the files
        using clientless access. Use caution because the persistent cookie is stored on the disk. Default value: OFF
        Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnclientlessaccessprofile <args>

    '''

    result = {}

    payload = {'vpnclientlessaccessprofile': {}}

    if profilename:
        payload['vpnclientlessaccessprofile']['profilename'] = profilename

    if urlrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['urlrewritepolicylabel'] = urlrewritepolicylabel

    if javascriptrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['javascriptrewritepolicylabel'] = javascriptrewritepolicylabel

    if reqhdrrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['reqhdrrewritepolicylabel'] = reqhdrrewritepolicylabel

    if reshdrrewritepolicylabel:
        payload['vpnclientlessaccessprofile']['reshdrrewritepolicylabel'] = reshdrrewritepolicylabel

    if regexforfindingurlinjavascript:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinjavascript'] = regexforfindingurlinjavascript

    if regexforfindingurlincss:
        payload['vpnclientlessaccessprofile']['regexforfindingurlincss'] = regexforfindingurlincss

    if regexforfindingurlinxcomponent:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinxcomponent'] = regexforfindingurlinxcomponent

    if regexforfindingurlinxml:
        payload['vpnclientlessaccessprofile']['regexforfindingurlinxml'] = regexforfindingurlinxml

    if regexforfindingcustomurls:
        payload['vpnclientlessaccessprofile']['regexforfindingcustomurls'] = regexforfindingcustomurls

    if clientconsumedcookies:
        payload['vpnclientlessaccessprofile']['clientconsumedcookies'] = clientconsumedcookies

    if requirepersistentcookie:
        payload['vpnclientlessaccessprofile']['requirepersistentcookie'] = requirepersistentcookie

    execution = __proxy__['citrixns.put']('config/vpnclientlessaccessprofile', payload)

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


def update_vpnformssoaction(name=None, actionurl=None, userfield=None, passwdfield=None, ssosuccessrule=None,
                            namevaluepair=None, responsesize=None, nvtype=None, submitmethod=None, save=False):
    '''
    Update the running configuration for the vpnformssoaction config key.

    name(str): Name for the form based single sign-on profile. Minimum length = 1

    actionurl(str): Root-relative URL to which the completed form is submitted. Minimum length = 1

    userfield(str): Name of the form field in which the user types in the user ID. Minimum length = 1

    passwdfield(str): Name of the form field in which the user types in the password. Minimum length = 1

    ssosuccessrule(str): Advanced expression that defines the criteria for SSO success. Expression such as checking for
        cookie in the response is a common example.

    namevaluepair(str): Other name-value pair attributes to send to the server, in addition to sending the user name and
        password. Value names are separated by an ampersand (;amp;), such as in name1=value1;amp;name2=value2.

    responsesize(int): Maximum number of bytes to allow in the response size. Specifies the number of bytes in the response
        to be parsed for extracting the forms. Default value: 8096

    nvtype(str): How to process the name-value pair. Available settings function as follows: * STATIC - The
        administrator-configured values are used. * DYNAMIC - The response is parsed, the form is extracted, and then
        submitted. Default value: DYNAMIC Possible values = STATIC, DYNAMIC

    submitmethod(str): HTTP method (GET or POST) used by the single sign-on form to send the logon credentials to the logon
        server. Default value: GET Possible values = GET, POST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnformssoaction <args>

    '''

    result = {}

    payload = {'vpnformssoaction': {}}

    if name:
        payload['vpnformssoaction']['name'] = name

    if actionurl:
        payload['vpnformssoaction']['actionurl'] = actionurl

    if userfield:
        payload['vpnformssoaction']['userfield'] = userfield

    if passwdfield:
        payload['vpnformssoaction']['passwdfield'] = passwdfield

    if ssosuccessrule:
        payload['vpnformssoaction']['ssosuccessrule'] = ssosuccessrule

    if namevaluepair:
        payload['vpnformssoaction']['namevaluepair'] = namevaluepair

    if responsesize:
        payload['vpnformssoaction']['responsesize'] = responsesize

    if nvtype:
        payload['vpnformssoaction']['nvtype'] = nvtype

    if submitmethod:
        payload['vpnformssoaction']['submitmethod'] = submitmethod

    execution = __proxy__['citrixns.put']('config/vpnformssoaction', payload)

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


def update_vpnparameter(httpport=None, winsip=None, dnsvservername=None, splitdns=None, icauseraccounting=None,
                        sesstimeout=None, clientsecurity=None, clientsecuritygroup=None, clientsecuritymessage=None,
                        clientsecuritylog=None, smartgroup=None, splittunnel=None, locallanaccess=None, rfc1918=None,
                        spoofiip=None, killconnections=None, transparentinterception=None, windowsclienttype=None,
                        defaultauthorizationaction=None, authorizationgroup=None, clientidletimeout=None, proxy=None,
                        allprotocolproxy=None, httpproxy=None, ftpproxy=None, socksproxy=None, gopherproxy=None,
                        sslproxy=None, proxyexception=None, proxylocalbypass=None, clientcleanupprompt=None,
                        forcecleanup=None, clientoptions=None, clientconfiguration=None, sso=None, ssocredential=None,
                        windowsautologon=None, usemip=None, useiip=None, clientdebug=None, loginscript=None,
                        logoutscript=None, homepage=None, icaproxy=None, wihome=None, wihomeaddresstype=None,
                        citrixreceiverhome=None, wiportalmode=None, clientchoices=None, epaclienttype=None,
                        iipdnssuffix=None, forcedtimeout=None, forcedtimeoutwarning=None, ntdomain=None,
                        clientlessvpnmode=None, clientlessmodeurlencoding=None, clientlesspersistentcookie=None,
                        emailhome=None, allowedlogingroups=None, encryptcsecexp=None, apptokentimeout=None,
                        mdxtokentimeout=None, uitheme=None, securebrowse=None, storefronturl=None, kcdaccount=None,
                        clientversions=None, rdpclientprofilename=None, windowspluginupgrade=None, macpluginupgrade=None,
                        linuxpluginupgrade=None, iconwithreceiver=None, userdomains=None, icasessiontimeout=None,
                        alwaysonprofilename=None, autoproxyurl=None, pcoipprofilename=None, save=False):
    '''
    Update the running configuration for the vpnparameter config key.

    httpport(list(int)): Destination port numbers other than port 80, added as a comma-separated list. Traffic to these ports
        is processed as HTTP traffic, which allows functionality, such as HTTP authorization and single sign-on to a web
        application to work. Minimum value = 1

    winsip(str): WINS server IP address to add to NetScaler Gateway for name resolution. Minimum length = 1

    dnsvservername(str): Name of the DNS virtual server for the user session. Minimum length = 1

    splitdns(str): Route the DNS requests to the local DNS server configured on the user device, or NetScaler Gateway
        (remote), or both. Possible values = LOCAL, REMOTE, BOTH

    icauseraccounting(str): The name of the radiusPolicy to use for RADIUS user accounting info on the session.

    sesstimeout(int): Number of minutes after which the session times out. Default value: 30 Minimum value = 1 Maximum value
        = 65535

    clientsecurity(str): Specify the client security check for the user device to permit a NetScaler Gateway session. The web
        address or IP address is not included in the expression for the client security check.

    clientsecuritygroup(str): The client security group that will be assigned on failure of the client security check. Users
        can in general be organized into Groups. In this case, the Client Security Group may have a more restrictive
        security policy. Minimum length = 1

    clientsecuritymessage(str): The client security message that will be displayed on failure of the client security check.
        Minimum length = 1 Maximum length = 127

    clientsecuritylog(str): Specifies whether or not to display all failed Client Security scans to the end user. Default
        value: OFF Possible values = ON, OFF

    smartgroup(str): This is the default group that is chosen when the authentication succeeds in addition to extracted
        groups. Minimum length = 1 Maximum length = 64

    splittunnel(str): Send, through the tunnel, traffic only for intranet applications that are defined in NetScaler Gateway.
        Route all other traffic directly to the Internet. The OFF setting routes all traffic through NetScaler Gateway.
        With the REVERSE setting, intranet applications define the network traffic that is not intercepted. All network
        traffic directed to internal IP addresses bypasses the VPN tunnel, while other traffic goes through NetScaler
        Gateway. Reverse split tunneling can be used to log all non-local LAN traffic. For example, if users have a home
        network and are logged on through the NetScaler Gateway Plug-in, network traffic destined to a printer or another
        device within the home network is not intercepted. Default value: OFF Possible values = ON, OFF, REVERSE

    locallanaccess(str): Set local LAN access. If split tunneling is OFF, and you set local LAN access to ON, the local
        client can route traffic to its local interface. When the local area network switch is specified, this
        combination of switches is useful. The client can allow local LAN access to devices that commonly have
        non-routable addresses, such as local printers or local file servers. Default value: OFF Possible values = ON,
        OFF

    rfc1918(str): As defined in the local area network, allow only the following local area network addresses to bypass the
        VPN tunnel when the local LAN access feature is enabled: * 10.*.*.*, * 172.16.*.*, * 192.168.*.*. Default value:
        OFF Possible values = ON, OFF

    spoofiip(str): Indicate whether or not the application requires IP spoofing, which routes the connection to the intranet
        application through the virtual adapter. Default value: ON Possible values = ON, OFF

    killconnections(str): Specify whether the NetScaler Gateway Plug-in should disconnect all preexisting connections, such
        as the connections existing before the user logged on to NetScaler Gateway, and prevent new incoming connections
        on the NetScaler Gateway Plug-in for Windows and MAC when the user is connected to NetScaler Gateway and split
        tunneling is disabled. Default value: OFF Possible values = ON, OFF

    transparentinterception(str): Allow access to network resources by using a single IP address and subnet mask or a range
        of IP addresses. The OFF setting sets the mode to proxy, in which you configure destination and source IP
        addresses and port numbers. If you are using the NetScaler Gateway Plug-in for Windows, set this parameter to ON,
        in which the mode is set to transparent. If you are using the NetScaler Gateway Plug-in for Java, set this
        parameter to OFF. Default value: OFF Possible values = ON, OFF

    windowsclienttype(str): The Windows client type. Choose between two types of Windows Client\\ a) Application Agent -
        which always runs in the task bar as a standalone application and also has a supporting service which runs
        permanently when installed\\ b) Activex Control - ActiveX control run by Microsoft Internet Explorer. Default
        value: AGENT Possible values = AGENT, PLUGIN

    defaultauthorizationaction(str): Specify the network resources that users have access to when they log on to the internal
        network. The default setting for authorization is to deny access to all network resources. Citrix recommends
        using the default global setting and then creating authorization policies to define the network resources users
        can access. If you set the default authorization policy to DENY, you must explicitly authorize access to any
        network resource, which improves security. Default value: DENY Possible values = ALLOW, DENY

    authorizationgroup(str): Comma-separated list of groups in which the user is placed when none of the groups that the user
        is a part of is configured on NetScaler Gateway. The authorization policy can be bound to these groups to control
        access to the resources. Minimum length = 1

    clientidletimeout(int): Time, in minutes, after which to time out the user session if NetScaler Gateway does not detect
        mouse or keyboard activity. Minimum value = 1 Maximum value = 9999

    proxy(str): Set options to apply proxy for accessing the internal resources. Available settings function as follows: *
        BROWSER - Proxy settings are configured only in Internet Explorer and Firefox browsers. * NS - Proxy settings are
        configured on the NetScaler appliance. * OFF - Proxy settings are not configured. Possible values = BROWSER, NS,
        OFF

    allprotocolproxy(str): IP address of the proxy server to use for all protocols supported by NetScaler Gateway. Minimum
        length = 1

    httpproxy(str): IP address of the proxy server to be used for HTTP access for all subsequent connections to the internal
        network. Minimum length = 1

    ftpproxy(str): IP address of the proxy server to be used for FTP access for all subsequent connections to the internal
        network. Minimum length = 1

    socksproxy(str): IP address of the proxy server to be used for SOCKS access for all subsequent connections to the
        internal network. Minimum length = 1

    gopherproxy(str): IP address of the proxy server to be used for GOPHER access for all subsequent connections to the
        internal network. Minimum length = 1

    sslproxy(str): IP address of the proxy server to be used for SSL access for all subsequent connections to the internal
        network. Minimum length = 1

    proxyexception(str): Proxy exception string that will be configured in the browser for bypassing the previously
        configured proxies. Allowed only if proxy type is Browser. Minimum length = 1

    proxylocalbypass(str): Bypass proxy server for local addresses option in Internet Explorer and Firefox proxy server
        settings. Default value: DISABLED Possible values = ENABLED, DISABLED

    clientcleanupprompt(str): Prompt for client-side cache clean-up when a client-initiated session closes. Default value: ON
        Possible values = ON, OFF

    forcecleanup(list(str)): Force cache clean-up when the user closes a session. You can specify all, none, or any
        combination of the client-side items. Possible values = none, all, cookie, addressbar, plugin,
        filesystemapplication, application, applicationdata, clientcertificate, autocomplete, cache

    clientoptions(list(str)): Display only the configured menu options when you select the "Configure NetScaler Gateway"
        option in the NetScaler Gateway Plug-ins system tray icon for Windows. Possible values = none, all, services,
        filetransfer, configuration

    clientconfiguration(list(str)): Allow users to change client Debug logging level in Configuration tab of the NetScaler
        Gateway Plug-in for Windows. Possible values = none, trace

    sso(str): Set single sign-on (SSO) for the session. When the user accesses a server, the users logon credentials are
        passed to the server for authentication. Default value: OFF Possible values = ON, OFF

    ssocredential(str): Specify whether to use the primary or secondary authentication credentials for single sign-on to the
        server. Default value: PRIMARY Possible values = PRIMARY, SECONDARY

    windowsautologon(str): Enable or disable the Windows Auto Logon for the session. If a VPN session is established after
        this setting is enabled, the user is automatically logged on by using Windows credentials after the system is
        restarted. Default value: OFF Possible values = ON, OFF

    usemip(str): Enable or disable the use of a unique IP address alias, or a mapped IP address, as the client IP address for
        each client session. Allow NetScaler Gateway to use the mapped IP address as an intranet IP address when all
        other IP addresses are not available.  When IP pooling is configured and the mapped IP is used as an intranet IP
        address, the mapped IP address is used when an intranet IP address cannot be assigned. Default value: NS Possible
        values = NS, OFF

    useiip(str): Define IP address pool options. Available settings function as follows:  * SPILLOVER - When an address pool
        is configured and the mapped IP is used as an intranet IP address, the mapped IP address is used when an intranet
        IP address cannot be assigned.  * NOSPILLOVER - When intranet IP addresses are enabled and the mapped IP address
        is not used, the Transfer Login page appears for users who have used all available intranet IP addresses.  * OFF
        - Address pool is not configured. Default value: NOSPILLOVER Possible values = NOSPILLOVER, SPILLOVER, OFF

    clientdebug(str): Set the trace level on NetScaler Gateway. Technical support technicians use these debug logs for
        in-depth debugging and troubleshooting purposes. Available settings function as follows:  * DEBUG - Detailed
        debug messages are collected and written into the specified file. * STATS - Application audit level error
        messages and debug statistic counters are written into the specified file.  * EVENTS - Application audit-level
        error messages are written into the specified file.  * OFF - Only critical events are logged into the Windows
        Application Log. Default value: OFF Possible values = debug, stats, events, OFF

    loginscript(str): Path to the logon script that is run when a session is established. Separate multiple scripts by using
        comma. A "$" in the path signifies that the word following the "$" is an environment variable. Minimum length =
        1

    logoutscript(str): Path to the logout script. Separate multiple scripts by using comma. A "$" in the path signifies that
        the word following the "$" is an environment variable. Minimum length = 1

    homepage(str): Web address of the home page that appears when users log on. Otherwise, users receive the default home
        page for NetScaler Gateway, which is the Access Interface.

    icaproxy(str): Enable ICA proxy to configure secure Internet access to servers running Citrix XenApp or XenDesktop by
        using Citrix Receiver instead of the NetScaler Gateway Plug-in. Default value: OFF Possible values = ON, OFF

    wihome(str): Web address of the Web Interface server, such as http://;lt;ipAddress;gt;/Citrix/XenApp, or Receiver for
        Web, which enumerates the virtualized resources, such as XenApp, XenDesktop, and cloud applications. This web
        address is used as the home page in ICA proxy mode.  If Client Choices is ON, you must configure this setting.
        Because the user can choose between FullClient and ICAProxy, the user may see a different home page. An Internet
        web site may appear if the user gets the FullClient option, or a Web Interface site if the user gets the ICAProxy
        option. If the setting is not configured, the XenApp option does not appear as a client choice.

    wihomeaddresstype(str): Type of the wihome address(IPV4/V6). Possible values = IPV4, IPV6

    citrixreceiverhome(str): Web address for the Citrix Receiver home page. Configure NetScaler Gateway so that when users
        log on to the appliance, the NetScaler Gateway Plug-in opens a web browser that allows single sign-on to the
        Citrix Receiver home page.

    wiportalmode(str): Layout on the Access Interface. The COMPACT value indicates the use of small icons. Possible values =
        NORMAL, COMPACT

    clientchoices(str): Provide users with multiple logon options. With client choices, users have the option of logging on
        by using the NetScaler Gateway Plug-in for Windows, NetScaler Gateway Plug-in for Java, the Web Interface, or
        clientless access from one location. Depending on how NetScaler Gateway is configured, users are presented with
        up to three icons for logon choices. The most common are the NetScaler Gateway Plug-in for Windows, Web
        Interface, and clientless access. Default value: OFF Possible values = ON, OFF

    epaclienttype(str): Choose between two types of End point Windows Client a) Application Agent - which always runs in the
        task bar as a standalone application and also has a supporting service which runs permanently when installed b)
        Activex Control - ActiveX control run by Microsoft Internet Explorer. Possible values = AGENT, PLUGIN

    iipdnssuffix(str): An intranet IP DNS suffix. When a user logs on to NetScaler Gateway and is assigned an IP address, a
        DNS record for the user name and IP address combination is added to the NetScaler Gateway DNS cache. You can
        configure a DNS suffix to append to the user name when the DNS record is added to the cache. You can reach to the
        host from where the user is logged on by using the users name, which can be easier to remember than an IP
        address. When the user logs off from NetScaler Gateway, the record is removed from the DNS cache. Minimum length
        = 1

    forcedtimeout(int): Force a disconnection from the NetScaler Gateway Plug-in with NetScaler Gateway after a specified
        number of minutes. If the session closes, the user must log on again. Minimum value = 1 Maximum value = 65535

    forcedtimeoutwarning(int): Number of minutes to warn a user before the user session is disconnected. Minimum value = 1
        Maximum value = 255

    ntdomain(str): Single sign-on domain to use for single sign-on to applications in the internal network. This setting can
        be overwritten by the domain that users specify at the time of logon or by the domain that the authentication
        server returns. Minimum length = 1 Maximum length = 32

    clientlessvpnmode(str): Enable clientless access for web, XenApp or XenDesktop, and FileShare resources without
        installing the NetScaler Gateway Plug-in. Available settings function as follows:  * ON - Allow only clientless
        access.  * OFF - Allow clientless access after users log on with the NetScaler Gateway Plug-in.  * DISABLED - Do
        not allow clientless access. Default value: OFF Possible values = ON, OFF, DISABLED

    clientlessmodeurlencoding(str): When clientless access is enabled, you can choose to encode the addresses of internal web
        applications or to leave the address as clear text. Available settings function as follows:  * OPAQUE - Use
        standard encoding mechanisms to make the domain and protocol part of the resource unclear to users.  *
        TRANSPARENT - Do not encode the web address and make it visible to users.  * ENCRYPT - Allow the domain and
        protocol to be encrypted using a session key. When the web address is encrypted, the URL is different for each
        user session for the same web resource. If users bookmark the encoded web address, save it in the web browser and
        then log off, they cannot connect to the web address when they log on and use the bookmark. If users save the
        encrypted bookmark in the Access Interface during their session, the bookmark works each time the user logs on.
        Default value: OPAQUE Possible values = TRANSPARENT, OPAQUE, ENCRYPT

    clientlesspersistentcookie(str): State of persistent cookies in clientless access mode. Persistent cookies are required
        for accessing certain features of SharePoint, such as opening and editing Microsoft Word, Excel, and PowerPoint
        documents hosted on the SharePoint server. A persistent cookie remains on the user device and is sent with each
        HTTP request. NetScaler Gateway encrypts the persistent cookie before sending it to the plug-in on the user
        device, and refreshes the cookie periodically as long as the session exists. The cookie becomes stale if the
        session ends. Available settings function as follows:  * ALLOW - Enable persistent cookies. Users can open and
        edit Microsoft documents stored in SharePoint.  * DENY - Disable persistent cookies. Users cannot open and edit
        Microsoft documents stored in SharePoint.  * PROMPT - Prompt users to allow or deny persistent cookies during the
        session. Persistent cookies are not required for clientless access if users do not connect to SharePoint. Default
        value: DENY Possible values = ALLOW, DENY, PROMPT

    emailhome(str): Web address for the web-based email, such as Outlook Web Access.

    allowedlogingroups(str): Specify groups that have permission to log on to NetScaler Gateway. Users who do not belong to
        this group or groups are denied access even if they have valid credentials. Minimum length = 1 Maximum length =
        511

    encryptcsecexp(str): Enable encryption of client security expressions. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    apptokentimeout(int): The timeout value in seconds for tokens to access XenMobile applications. Default value: 100
        Minimum value = 1 Maximum value = 255

    mdxtokentimeout(int): Validity of MDX Token in minutes. This token is used for mdx services to access backend and valid
        HEAD and GET request. Default value: 10 Minimum value = 1 Maximum value = 1440

    uitheme(str): Set VPN UI Theme to Green-Bubble, Caxton or Custom; default is Caxton. Possible values = DEFAULT,
        GREENBUBBLE, CUSTOM

    securebrowse(str): Allow users to connect through NetScaler Gateway to network resources from iOS and Android mobile
        devices with Citrix Receiver. Users do not need to establish a full VPN tunnel to access resources in the secure
        network. Default value: ENABLED Possible values = ENABLED, DISABLED

    storefronturl(str): Web address for StoreFront to be used in this session for enumeration of resources from XenApp or
        XenDesktop. Minimum length = 1 Maximum length = 255

    kcdaccount(str): The KCD account details to be used in SSO.

    clientversions(str): checkversion api. Minimum length = 1 Maximum length = 100

    rdpclientprofilename(str): Name of the RDP profile associated with the vserver. Minimum length = 1 Maximum length = 127

    windowspluginupgrade(str): Option to set plugin upgrade behaviour for Win. Default value: Always Possible values =
        Always, Essential, Never

    macpluginupgrade(str): Option to set plugin upgrade behaviour for Mac. Default value: Always Possible values = Always,
        Essential, Never

    linuxpluginupgrade(str): Option to set plugin upgrade behaviour for Linux. Default value: Always Possible values =
        Always, Essential, Never

    iconwithreceiver(str): Option to decide whether to show plugin icon along with receiver icon. Default value: OFF Possible
        values = ON, OFF

    userdomains(str): List of user domains specified as comma seperated value.

    icasessiontimeout(str): Enable or disable ica session timeout. If enabled and in case AAA session gets terminated, ICA
        connections associated with that will also get terminated. Default value: OFF Possible values = ON, OFF

    alwaysonprofilename(str): Name of the AlwaysON profile. The builtin profile named none can be used to explicitly disable
        AlwaysON. Minimum length = 1 Maximum length = 127

    autoproxyurl(str): URL to auto proxy config file.

    pcoipprofilename(str): Name of the PCOIP profile. Minimum length = 1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnparameter <args>

    '''

    result = {}

    payload = {'vpnparameter': {}}

    if httpport:
        payload['vpnparameter']['httpport'] = httpport

    if winsip:
        payload['vpnparameter']['winsip'] = winsip

    if dnsvservername:
        payload['vpnparameter']['dnsvservername'] = dnsvservername

    if splitdns:
        payload['vpnparameter']['splitdns'] = splitdns

    if icauseraccounting:
        payload['vpnparameter']['icauseraccounting'] = icauseraccounting

    if sesstimeout:
        payload['vpnparameter']['sesstimeout'] = sesstimeout

    if clientsecurity:
        payload['vpnparameter']['clientsecurity'] = clientsecurity

    if clientsecuritygroup:
        payload['vpnparameter']['clientsecuritygroup'] = clientsecuritygroup

    if clientsecuritymessage:
        payload['vpnparameter']['clientsecuritymessage'] = clientsecuritymessage

    if clientsecuritylog:
        payload['vpnparameter']['clientsecuritylog'] = clientsecuritylog

    if smartgroup:
        payload['vpnparameter']['smartgroup'] = smartgroup

    if splittunnel:
        payload['vpnparameter']['splittunnel'] = splittunnel

    if locallanaccess:
        payload['vpnparameter']['locallanaccess'] = locallanaccess

    if rfc1918:
        payload['vpnparameter']['rfc1918'] = rfc1918

    if spoofiip:
        payload['vpnparameter']['spoofiip'] = spoofiip

    if killconnections:
        payload['vpnparameter']['killconnections'] = killconnections

    if transparentinterception:
        payload['vpnparameter']['transparentinterception'] = transparentinterception

    if windowsclienttype:
        payload['vpnparameter']['windowsclienttype'] = windowsclienttype

    if defaultauthorizationaction:
        payload['vpnparameter']['defaultauthorizationaction'] = defaultauthorizationaction

    if authorizationgroup:
        payload['vpnparameter']['authorizationgroup'] = authorizationgroup

    if clientidletimeout:
        payload['vpnparameter']['clientidletimeout'] = clientidletimeout

    if proxy:
        payload['vpnparameter']['proxy'] = proxy

    if allprotocolproxy:
        payload['vpnparameter']['allprotocolproxy'] = allprotocolproxy

    if httpproxy:
        payload['vpnparameter']['httpproxy'] = httpproxy

    if ftpproxy:
        payload['vpnparameter']['ftpproxy'] = ftpproxy

    if socksproxy:
        payload['vpnparameter']['socksproxy'] = socksproxy

    if gopherproxy:
        payload['vpnparameter']['gopherproxy'] = gopherproxy

    if sslproxy:
        payload['vpnparameter']['sslproxy'] = sslproxy

    if proxyexception:
        payload['vpnparameter']['proxyexception'] = proxyexception

    if proxylocalbypass:
        payload['vpnparameter']['proxylocalbypass'] = proxylocalbypass

    if clientcleanupprompt:
        payload['vpnparameter']['clientcleanupprompt'] = clientcleanupprompt

    if forcecleanup:
        payload['vpnparameter']['forcecleanup'] = forcecleanup

    if clientoptions:
        payload['vpnparameter']['clientoptions'] = clientoptions

    if clientconfiguration:
        payload['vpnparameter']['clientconfiguration'] = clientconfiguration

    if sso:
        payload['vpnparameter']['sso'] = sso

    if ssocredential:
        payload['vpnparameter']['ssocredential'] = ssocredential

    if windowsautologon:
        payload['vpnparameter']['windowsautologon'] = windowsautologon

    if usemip:
        payload['vpnparameter']['usemip'] = usemip

    if useiip:
        payload['vpnparameter']['useiip'] = useiip

    if clientdebug:
        payload['vpnparameter']['clientdebug'] = clientdebug

    if loginscript:
        payload['vpnparameter']['loginscript'] = loginscript

    if logoutscript:
        payload['vpnparameter']['logoutscript'] = logoutscript

    if homepage:
        payload['vpnparameter']['homepage'] = homepage

    if icaproxy:
        payload['vpnparameter']['icaproxy'] = icaproxy

    if wihome:
        payload['vpnparameter']['wihome'] = wihome

    if wihomeaddresstype:
        payload['vpnparameter']['wihomeaddresstype'] = wihomeaddresstype

    if citrixreceiverhome:
        payload['vpnparameter']['citrixreceiverhome'] = citrixreceiverhome

    if wiportalmode:
        payload['vpnparameter']['wiportalmode'] = wiportalmode

    if clientchoices:
        payload['vpnparameter']['clientchoices'] = clientchoices

    if epaclienttype:
        payload['vpnparameter']['epaclienttype'] = epaclienttype

    if iipdnssuffix:
        payload['vpnparameter']['iipdnssuffix'] = iipdnssuffix

    if forcedtimeout:
        payload['vpnparameter']['forcedtimeout'] = forcedtimeout

    if forcedtimeoutwarning:
        payload['vpnparameter']['forcedtimeoutwarning'] = forcedtimeoutwarning

    if ntdomain:
        payload['vpnparameter']['ntdomain'] = ntdomain

    if clientlessvpnmode:
        payload['vpnparameter']['clientlessvpnmode'] = clientlessvpnmode

    if clientlessmodeurlencoding:
        payload['vpnparameter']['clientlessmodeurlencoding'] = clientlessmodeurlencoding

    if clientlesspersistentcookie:
        payload['vpnparameter']['clientlesspersistentcookie'] = clientlesspersistentcookie

    if emailhome:
        payload['vpnparameter']['emailhome'] = emailhome

    if allowedlogingroups:
        payload['vpnparameter']['allowedlogingroups'] = allowedlogingroups

    if encryptcsecexp:
        payload['vpnparameter']['encryptcsecexp'] = encryptcsecexp

    if apptokentimeout:
        payload['vpnparameter']['apptokentimeout'] = apptokentimeout

    if mdxtokentimeout:
        payload['vpnparameter']['mdxtokentimeout'] = mdxtokentimeout

    if uitheme:
        payload['vpnparameter']['uitheme'] = uitheme

    if securebrowse:
        payload['vpnparameter']['securebrowse'] = securebrowse

    if storefronturl:
        payload['vpnparameter']['storefronturl'] = storefronturl

    if kcdaccount:
        payload['vpnparameter']['kcdaccount'] = kcdaccount

    if clientversions:
        payload['vpnparameter']['clientversions'] = clientversions

    if rdpclientprofilename:
        payload['vpnparameter']['rdpclientprofilename'] = rdpclientprofilename

    if windowspluginupgrade:
        payload['vpnparameter']['windowspluginupgrade'] = windowspluginupgrade

    if macpluginupgrade:
        payload['vpnparameter']['macpluginupgrade'] = macpluginupgrade

    if linuxpluginupgrade:
        payload['vpnparameter']['linuxpluginupgrade'] = linuxpluginupgrade

    if iconwithreceiver:
        payload['vpnparameter']['iconwithreceiver'] = iconwithreceiver

    if userdomains:
        payload['vpnparameter']['userdomains'] = userdomains

    if icasessiontimeout:
        payload['vpnparameter']['icasessiontimeout'] = icasessiontimeout

    if alwaysonprofilename:
        payload['vpnparameter']['alwaysonprofilename'] = alwaysonprofilename

    if autoproxyurl:
        payload['vpnparameter']['autoproxyurl'] = autoproxyurl

    if pcoipprofilename:
        payload['vpnparameter']['pcoipprofilename'] = pcoipprofilename

    execution = __proxy__['citrixns.put']('config/vpnparameter', payload)

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


def update_vpnpcoipprofile(name=None, conserverurl=None, icvverification=None, sessionidletimeout=None, save=False):
    '''
    Update the running configuration for the vpnpcoipprofile config key.

    name(str): name of PCoIP profile. Minimum length = 1

    conserverurl(str): Connection server URL.

    icvverification(str): ICV verification for PCOIP transport packets. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    sessionidletimeout(int): PCOIP Idle Session timeout. Default value: 180 Minimum value = 30 Maximum value = 240

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnpcoipprofile <args>

    '''

    result = {}

    payload = {'vpnpcoipprofile': {}}

    if name:
        payload['vpnpcoipprofile']['name'] = name

    if conserverurl:
        payload['vpnpcoipprofile']['conserverurl'] = conserverurl

    if icvverification:
        payload['vpnpcoipprofile']['icvverification'] = icvverification

    if sessionidletimeout:
        payload['vpnpcoipprofile']['sessionidletimeout'] = sessionidletimeout

    execution = __proxy__['citrixns.put']('config/vpnpcoipprofile', payload)

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


def update_vpnpcoipvserverprofile(name=None, logindomain=None, udpport=None, save=False):
    '''
    Update the running configuration for the vpnpcoipvserverprofile config key.

    name(str): name of PCoIP vserver profile. Minimum length = 1

    logindomain(str): Login domain for PCoIP users.

    udpport(int): UDP port for PCoIP data traffic. Default value: 4172 Range 1 - 65535 * in CLI is represented as 65535 in
        NITRO API

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnpcoipvserverprofile <args>

    '''

    result = {}

    payload = {'vpnpcoipvserverprofile': {}}

    if name:
        payload['vpnpcoipvserverprofile']['name'] = name

    if logindomain:
        payload['vpnpcoipvserverprofile']['logindomain'] = logindomain

    if udpport:
        payload['vpnpcoipvserverprofile']['udpport'] = udpport

    execution = __proxy__['citrixns.put']('config/vpnpcoipvserverprofile', payload)

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


def update_vpnsamlssoprofile(name=None, samlsigningcertname=None, assertionconsumerserviceurl=None, relaystaterule=None,
                             sendpassword=None, samlissuername=None, signaturealg=None, digestmethod=None, audience=None,
                             nameidformat=None, nameidexpr=None, attribute1=None, attribute1expr=None,
                             attribute1friendlyname=None, attribute1format=None, attribute2=None, attribute2expr=None,
                             attribute2friendlyname=None, attribute2format=None, attribute3=None, attribute3expr=None,
                             attribute3friendlyname=None, attribute3format=None, attribute4=None, attribute4expr=None,
                             attribute4friendlyname=None, attribute4format=None, attribute5=None, attribute5expr=None,
                             attribute5friendlyname=None, attribute5format=None, attribute6=None, attribute6expr=None,
                             attribute6friendlyname=None, attribute6format=None, attribute7=None, attribute7expr=None,
                             attribute7friendlyname=None, attribute7format=None, attribute8=None, attribute8expr=None,
                             attribute8friendlyname=None, attribute8format=None, attribute9=None, attribute9expr=None,
                             attribute9friendlyname=None, attribute9format=None, attribute10=None, attribute10expr=None,
                             attribute10friendlyname=None, attribute10format=None, attribute11=None,
                             attribute11expr=None, attribute11friendlyname=None, attribute11format=None,
                             attribute12=None, attribute12expr=None, attribute12friendlyname=None,
                             attribute12format=None, attribute13=None, attribute13expr=None,
                             attribute13friendlyname=None, attribute13format=None, attribute14=None,
                             attribute14expr=None, attribute14friendlyname=None, attribute14format=None,
                             attribute15=None, attribute15expr=None, attribute15friendlyname=None,
                             attribute15format=None, attribute16=None, attribute16expr=None,
                             attribute16friendlyname=None, attribute16format=None, encryptassertion=None,
                             samlspcertname=None, encryptionalgorithm=None, skewtime=None, save=False):
    '''
    Update the running configuration for the vpnsamlssoprofile config key.

    name(str): Name for the new saml single sign-on profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an SSO action is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    samlsigningcertname(str): Name of the signing authority as given in the SAML servers SSL certificate. Minimum length = 1

    assertionconsumerserviceurl(str): URL to which the assertion is to be sent. Minimum length = 1

    relaystaterule(str): Expression to extract relaystate to be sent along with assertion. Evaluation of this expression
        should return TEXT content. This is typically a target url to which user is redirected after the recipient
        validates SAML token.

    sendpassword(str): Option to send password in assertion. Default value: OFF Possible values = ON, OFF

    samlissuername(str): The name to be used in requests sent from Netscaler to IdP to uniquely identify Netscaler. Minimum
        length = 1

    signaturealg(str): Algorithm to be used to sign/verify SAML transactions. Default value: RSA-SHA1 Possible values =
        RSA-SHA1, RSA-SHA256

    digestmethod(str): Algorithm to be used to compute/verify digest for SAML transactions. Default value: SHA1 Possible
        values = SHA1, SHA256

    audience(str): Audience for which assertion sent by IdP is applicable. This is typically entity name or url that
        represents ServiceProvider.

    nameidformat(str): Format of Name Identifier sent in Assertion. Default value: transient Possible values = Unspecified,
        emailAddress, X509SubjectName, WindowsDomainQualifiedName, kerberos, entity, persistent, transient

    nameidexpr(str): Expression that will be evaluated to obtain NameIdentifier to be sent in assertion. Maximum length =
        128

    attribute1(str): Name of attribute1 that needs to be sent in SAML Assertion.

    attribute1expr(str): Expression that will be evaluated to obtain attribute1s value to be sent in Assertion. Maximum
        length = 128

    attribute1friendlyname(str): User-Friendly Name of attribute1 that needs to be sent in SAML Assertion.

    attribute1format(str): Format of Attribute1 to be sent in Assertion. Possible values = URI, Basic

    attribute2(str): Name of attribute2 that needs to be sent in SAML Assertion.

    attribute2expr(str): Expression that will be evaluated to obtain attribute2s value to be sent in Assertion. Maximum
        length = 128

    attribute2friendlyname(str): User-Friendly Name of attribute2 that needs to be sent in SAML Assertion.

    attribute2format(str): Format of Attribute2 to be sent in Assertion. Possible values = URI, Basic

    attribute3(str): Name of attribute3 that needs to be sent in SAML Assertion.

    attribute3expr(str): Expression that will be evaluated to obtain attribute3s value to be sent in Assertion. Maximum
        length = 128

    attribute3friendlyname(str): User-Friendly Name of attribute3 that needs to be sent in SAML Assertion.

    attribute3format(str): Format of Attribute3 to be sent in Assertion. Possible values = URI, Basic

    attribute4(str): Name of attribute4 that needs to be sent in SAML Assertion.

    attribute4expr(str): Expression that will be evaluated to obtain attribute4s value to be sent in Assertion. Maximum
        length = 128

    attribute4friendlyname(str): User-Friendly Name of attribute4 that needs to be sent in SAML Assertion.

    attribute4format(str): Format of Attribute4 to be sent in Assertion. Possible values = URI, Basic

    attribute5(str): Name of attribute5 that needs to be sent in SAML Assertion.

    attribute5expr(str): Expression that will be evaluated to obtain attribute5s value to be sent in Assertion. Maximum
        length = 128

    attribute5friendlyname(str): User-Friendly Name of attribute5 that needs to be sent in SAML Assertion.

    attribute5format(str): Format of Attribute5 to be sent in Assertion. Possible values = URI, Basic

    attribute6(str): Name of attribute6 that needs to be sent in SAML Assertion.

    attribute6expr(str): Expression that will be evaluated to obtain attribute6s value to be sent in Assertion. Maximum
        length = 128

    attribute6friendlyname(str): User-Friendly Name of attribute6 that needs to be sent in SAML Assertion.

    attribute6format(str): Format of Attribute6 to be sent in Assertion. Possible values = URI, Basic

    attribute7(str): Name of attribute7 that needs to be sent in SAML Assertion.

    attribute7expr(str): Expression that will be evaluated to obtain attribute7s value to be sent in Assertion. Maximum
        length = 128

    attribute7friendlyname(str): User-Friendly Name of attribute7 that needs to be sent in SAML Assertion.

    attribute7format(str): Format of Attribute7 to be sent in Assertion. Possible values = URI, Basic

    attribute8(str): Name of attribute8 that needs to be sent in SAML Assertion.

    attribute8expr(str): Expression that will be evaluated to obtain attribute8s value to be sent in Assertion. Maximum
        length = 128

    attribute8friendlyname(str): User-Friendly Name of attribute8 that needs to be sent in SAML Assertion.

    attribute8format(str): Format of Attribute8 to be sent in Assertion. Possible values = URI, Basic

    attribute9(str): Name of attribute9 that needs to be sent in SAML Assertion.

    attribute9expr(str): Expression that will be evaluated to obtain attribute9s value to be sent in Assertion. Maximum
        length = 128

    attribute9friendlyname(str): User-Friendly Name of attribute9 that needs to be sent in SAML Assertion.

    attribute9format(str): Format of Attribute9 to be sent in Assertion. Possible values = URI, Basic

    attribute10(str): Name of attribute10 that needs to be sent in SAML Assertion.

    attribute10expr(str): Expression that will be evaluated to obtain attribute10s value to be sent in Assertion. Maximum
        length = 128

    attribute10friendlyname(str): User-Friendly Name of attribute10 that needs to be sent in SAML Assertion.

    attribute10format(str): Format of Attribute10 to be sent in Assertion. Possible values = URI, Basic

    attribute11(str): Name of attribute11 that needs to be sent in SAML Assertion.

    attribute11expr(str): Expression that will be evaluated to obtain attribute11s value to be sent in Assertion. Maximum
        length = 128

    attribute11friendlyname(str): User-Friendly Name of attribute11 that needs to be sent in SAML Assertion.

    attribute11format(str): Format of Attribute11 to be sent in Assertion. Possible values = URI, Basic

    attribute12(str): Name of attribute12 that needs to be sent in SAML Assertion.

    attribute12expr(str): Expression that will be evaluated to obtain attribute12s value to be sent in Assertion. Maximum
        length = 128

    attribute12friendlyname(str): User-Friendly Name of attribute12 that needs to be sent in SAML Assertion.

    attribute12format(str): Format of Attribute12 to be sent in Assertion. Possible values = URI, Basic

    attribute13(str): Name of attribute13 that needs to be sent in SAML Assertion.

    attribute13expr(str): Expression that will be evaluated to obtain attribute13s value to be sent in Assertion. Maximum
        length = 128

    attribute13friendlyname(str): User-Friendly Name of attribute13 that needs to be sent in SAML Assertion.

    attribute13format(str): Format of Attribute13 to be sent in Assertion. Possible values = URI, Basic

    attribute14(str): Name of attribute14 that needs to be sent in SAML Assertion.

    attribute14expr(str): Expression that will be evaluated to obtain attribute14s value to be sent in Assertion. Maximum
        length = 128

    attribute14friendlyname(str): User-Friendly Name of attribute14 that needs to be sent in SAML Assertion.

    attribute14format(str): Format of Attribute14 to be sent in Assertion. Possible values = URI, Basic

    attribute15(str): Name of attribute15 that needs to be sent in SAML Assertion.

    attribute15expr(str): Expression that will be evaluated to obtain attribute15s value to be sent in Assertion. Maximum
        length = 128

    attribute15friendlyname(str): User-Friendly Name of attribute15 that needs to be sent in SAML Assertion.

    attribute15format(str): Format of Attribute15 to be sent in Assertion. Possible values = URI, Basic

    attribute16(str): Name of attribute16 that needs to be sent in SAML Assertion.

    attribute16expr(str): Expression that will be evaluated to obtain attribute16s value to be sent in Assertion. Maximum
        length = 128

    attribute16friendlyname(str): User-Friendly Name of attribute16 that needs to be sent in SAML Assertion.

    attribute16format(str): Format of Attribute16 to be sent in Assertion. Possible values = URI, Basic

    encryptassertion(str): Option to encrypt assertion when Netscaler sends one. Default value: OFF Possible values = ON,
        OFF

    samlspcertname(str): Name of the SSL certificate of peer/receving party using which Assertion is encrypted. Minimum
        length = 1

    encryptionalgorithm(str): Algorithm to be used to encrypt SAML assertion. Default value: AES256 Possible values = DES3,
        AES128, AES192, AES256

    skewtime(int): This option specifies the number of minutes on either side of current time that the assertion would be
        valid. For example, if skewTime is 10, then assertion would be valid from (current time - 10) min to (current
        time + 10) min, ie 20min in all. Default value: 5

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnsamlssoprofile <args>

    '''

    result = {}

    payload = {'vpnsamlssoprofile': {}}

    if name:
        payload['vpnsamlssoprofile']['name'] = name

    if samlsigningcertname:
        payload['vpnsamlssoprofile']['samlsigningcertname'] = samlsigningcertname

    if assertionconsumerserviceurl:
        payload['vpnsamlssoprofile']['assertionconsumerserviceurl'] = assertionconsumerserviceurl

    if relaystaterule:
        payload['vpnsamlssoprofile']['relaystaterule'] = relaystaterule

    if sendpassword:
        payload['vpnsamlssoprofile']['sendpassword'] = sendpassword

    if samlissuername:
        payload['vpnsamlssoprofile']['samlissuername'] = samlissuername

    if signaturealg:
        payload['vpnsamlssoprofile']['signaturealg'] = signaturealg

    if digestmethod:
        payload['vpnsamlssoprofile']['digestmethod'] = digestmethod

    if audience:
        payload['vpnsamlssoprofile']['audience'] = audience

    if nameidformat:
        payload['vpnsamlssoprofile']['nameidformat'] = nameidformat

    if nameidexpr:
        payload['vpnsamlssoprofile']['nameidexpr'] = nameidexpr

    if attribute1:
        payload['vpnsamlssoprofile']['attribute1'] = attribute1

    if attribute1expr:
        payload['vpnsamlssoprofile']['attribute1expr'] = attribute1expr

    if attribute1friendlyname:
        payload['vpnsamlssoprofile']['attribute1friendlyname'] = attribute1friendlyname

    if attribute1format:
        payload['vpnsamlssoprofile']['attribute1format'] = attribute1format

    if attribute2:
        payload['vpnsamlssoprofile']['attribute2'] = attribute2

    if attribute2expr:
        payload['vpnsamlssoprofile']['attribute2expr'] = attribute2expr

    if attribute2friendlyname:
        payload['vpnsamlssoprofile']['attribute2friendlyname'] = attribute2friendlyname

    if attribute2format:
        payload['vpnsamlssoprofile']['attribute2format'] = attribute2format

    if attribute3:
        payload['vpnsamlssoprofile']['attribute3'] = attribute3

    if attribute3expr:
        payload['vpnsamlssoprofile']['attribute3expr'] = attribute3expr

    if attribute3friendlyname:
        payload['vpnsamlssoprofile']['attribute3friendlyname'] = attribute3friendlyname

    if attribute3format:
        payload['vpnsamlssoprofile']['attribute3format'] = attribute3format

    if attribute4:
        payload['vpnsamlssoprofile']['attribute4'] = attribute4

    if attribute4expr:
        payload['vpnsamlssoprofile']['attribute4expr'] = attribute4expr

    if attribute4friendlyname:
        payload['vpnsamlssoprofile']['attribute4friendlyname'] = attribute4friendlyname

    if attribute4format:
        payload['vpnsamlssoprofile']['attribute4format'] = attribute4format

    if attribute5:
        payload['vpnsamlssoprofile']['attribute5'] = attribute5

    if attribute5expr:
        payload['vpnsamlssoprofile']['attribute5expr'] = attribute5expr

    if attribute5friendlyname:
        payload['vpnsamlssoprofile']['attribute5friendlyname'] = attribute5friendlyname

    if attribute5format:
        payload['vpnsamlssoprofile']['attribute5format'] = attribute5format

    if attribute6:
        payload['vpnsamlssoprofile']['attribute6'] = attribute6

    if attribute6expr:
        payload['vpnsamlssoprofile']['attribute6expr'] = attribute6expr

    if attribute6friendlyname:
        payload['vpnsamlssoprofile']['attribute6friendlyname'] = attribute6friendlyname

    if attribute6format:
        payload['vpnsamlssoprofile']['attribute6format'] = attribute6format

    if attribute7:
        payload['vpnsamlssoprofile']['attribute7'] = attribute7

    if attribute7expr:
        payload['vpnsamlssoprofile']['attribute7expr'] = attribute7expr

    if attribute7friendlyname:
        payload['vpnsamlssoprofile']['attribute7friendlyname'] = attribute7friendlyname

    if attribute7format:
        payload['vpnsamlssoprofile']['attribute7format'] = attribute7format

    if attribute8:
        payload['vpnsamlssoprofile']['attribute8'] = attribute8

    if attribute8expr:
        payload['vpnsamlssoprofile']['attribute8expr'] = attribute8expr

    if attribute8friendlyname:
        payload['vpnsamlssoprofile']['attribute8friendlyname'] = attribute8friendlyname

    if attribute8format:
        payload['vpnsamlssoprofile']['attribute8format'] = attribute8format

    if attribute9:
        payload['vpnsamlssoprofile']['attribute9'] = attribute9

    if attribute9expr:
        payload['vpnsamlssoprofile']['attribute9expr'] = attribute9expr

    if attribute9friendlyname:
        payload['vpnsamlssoprofile']['attribute9friendlyname'] = attribute9friendlyname

    if attribute9format:
        payload['vpnsamlssoprofile']['attribute9format'] = attribute9format

    if attribute10:
        payload['vpnsamlssoprofile']['attribute10'] = attribute10

    if attribute10expr:
        payload['vpnsamlssoprofile']['attribute10expr'] = attribute10expr

    if attribute10friendlyname:
        payload['vpnsamlssoprofile']['attribute10friendlyname'] = attribute10friendlyname

    if attribute10format:
        payload['vpnsamlssoprofile']['attribute10format'] = attribute10format

    if attribute11:
        payload['vpnsamlssoprofile']['attribute11'] = attribute11

    if attribute11expr:
        payload['vpnsamlssoprofile']['attribute11expr'] = attribute11expr

    if attribute11friendlyname:
        payload['vpnsamlssoprofile']['attribute11friendlyname'] = attribute11friendlyname

    if attribute11format:
        payload['vpnsamlssoprofile']['attribute11format'] = attribute11format

    if attribute12:
        payload['vpnsamlssoprofile']['attribute12'] = attribute12

    if attribute12expr:
        payload['vpnsamlssoprofile']['attribute12expr'] = attribute12expr

    if attribute12friendlyname:
        payload['vpnsamlssoprofile']['attribute12friendlyname'] = attribute12friendlyname

    if attribute12format:
        payload['vpnsamlssoprofile']['attribute12format'] = attribute12format

    if attribute13:
        payload['vpnsamlssoprofile']['attribute13'] = attribute13

    if attribute13expr:
        payload['vpnsamlssoprofile']['attribute13expr'] = attribute13expr

    if attribute13friendlyname:
        payload['vpnsamlssoprofile']['attribute13friendlyname'] = attribute13friendlyname

    if attribute13format:
        payload['vpnsamlssoprofile']['attribute13format'] = attribute13format

    if attribute14:
        payload['vpnsamlssoprofile']['attribute14'] = attribute14

    if attribute14expr:
        payload['vpnsamlssoprofile']['attribute14expr'] = attribute14expr

    if attribute14friendlyname:
        payload['vpnsamlssoprofile']['attribute14friendlyname'] = attribute14friendlyname

    if attribute14format:
        payload['vpnsamlssoprofile']['attribute14format'] = attribute14format

    if attribute15:
        payload['vpnsamlssoprofile']['attribute15'] = attribute15

    if attribute15expr:
        payload['vpnsamlssoprofile']['attribute15expr'] = attribute15expr

    if attribute15friendlyname:
        payload['vpnsamlssoprofile']['attribute15friendlyname'] = attribute15friendlyname

    if attribute15format:
        payload['vpnsamlssoprofile']['attribute15format'] = attribute15format

    if attribute16:
        payload['vpnsamlssoprofile']['attribute16'] = attribute16

    if attribute16expr:
        payload['vpnsamlssoprofile']['attribute16expr'] = attribute16expr

    if attribute16friendlyname:
        payload['vpnsamlssoprofile']['attribute16friendlyname'] = attribute16friendlyname

    if attribute16format:
        payload['vpnsamlssoprofile']['attribute16format'] = attribute16format

    if encryptassertion:
        payload['vpnsamlssoprofile']['encryptassertion'] = encryptassertion

    if samlspcertname:
        payload['vpnsamlssoprofile']['samlspcertname'] = samlspcertname

    if encryptionalgorithm:
        payload['vpnsamlssoprofile']['encryptionalgorithm'] = encryptionalgorithm

    if skewtime:
        payload['vpnsamlssoprofile']['skewtime'] = skewtime

    execution = __proxy__['citrixns.put']('config/vpnsamlssoprofile', payload)

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


def update_vpnsessionaction(name=None, useraccounting=None, httpport=None, winsip=None, dnsvservername=None,
                            splitdns=None, sesstimeout=None, clientsecurity=None, clientsecuritygroup=None,
                            clientsecuritymessage=None, clientsecuritylog=None, splittunnel=None, locallanaccess=None,
                            rfc1918=None, spoofiip=None, killconnections=None, transparentinterception=None,
                            windowsclienttype=None, defaultauthorizationaction=None, authorizationgroup=None,
                            smartgroup=None, clientidletimeout=None, proxy=None, allprotocolproxy=None, httpproxy=None,
                            ftpproxy=None, socksproxy=None, gopherproxy=None, sslproxy=None, proxyexception=None,
                            proxylocalbypass=None, clientcleanupprompt=None, forcecleanup=None, clientoptions=None,
                            clientconfiguration=None, sso=None, ssocredential=None, windowsautologon=None, usemip=None,
                            useiip=None, clientdebug=None, loginscript=None, logoutscript=None, homepage=None,
                            icaproxy=None, wihome=None, wihomeaddresstype=None, citrixreceiverhome=None,
                            wiportalmode=None, clientchoices=None, epaclienttype=None, iipdnssuffix=None,
                            forcedtimeout=None, forcedtimeoutwarning=None, ntdomain=None, clientlessvpnmode=None,
                            emailhome=None, clientlessmodeurlencoding=None, clientlesspersistentcookie=None,
                            allowedlogingroups=None, securebrowse=None, storefronturl=None, sfgatewayauthtype=None,
                            kcdaccount=None, rdpclientprofilename=None, windowspluginupgrade=None, macpluginupgrade=None,
                            linuxpluginupgrade=None, iconwithreceiver=None, alwaysonprofilename=None, autoproxyurl=None,
                            pcoipprofilename=None, save=False):
    '''
    Update the running configuration for the vpnsessionaction config key.

    name(str): Name for the NetScaler Gateway profile (action). Must begin with an ASCII alphabetic or underscore (_)
        character, and must consist only of ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at
        (@), equals (=), and hyphen (-) characters. Cannot be changed after the profile is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    useraccounting(str): The name of the radiusPolicy to use for RADIUS user accounting info on the session.

    httpport(list(int)): Destination port numbers other than port 80, added as a comma-separated list. Traffic to these ports
        is processed as HTTP traffic, which allows functionality, such as HTTP authorization and single sign-on to a web
        application to work. Minimum value = 1

    winsip(str): WINS server IP address to add to NetScaler Gateway for name resolution.

    dnsvservername(str): Name of the DNS virtual server for the user session. Minimum length = 1

    splitdns(str): Route the DNS requests to the local DNS server configured on the user device, or NetScaler Gateway
        (remote), or both. Possible values = LOCAL, REMOTE, BOTH

    sesstimeout(int): Number of minutes after which the session times out. Minimum value = 1

    clientsecurity(str): Specify the client security check for the user device to permit a NetScaler Gateway session. The web
        address or IP address is not included in the expression for the client security check.

    clientsecuritygroup(str): The client security group that will be assigned on failure of the client security check. Users
        can in general be organized into Groups. In this case, the Client Security Group may have a more restrictive
        security policy. Minimum length = 1

    clientsecuritymessage(str): The client security message that will be displayed on failure of the client security check.
        Minimum length = 1 Maximum length = 127

    clientsecuritylog(str): Set the logging of client security checks. Possible values = ON, OFF

    splittunnel(str): Send, through the tunnel, traffic only for intranet applications that are defined in NetScaler Gateway.
        Route all other traffic directly to the Internet. The OFF setting routes all traffic through NetScaler Gateway.
        With the REVERSE setting, intranet applications define the network traffic that is not intercepted. All network
        traffic directed to internal IP addresses bypasses the VPN tunnel, while other traffic goes through NetScaler
        Gateway. Reverse split tunneling can be used to log all non-local LAN traffic. For example, if users have a home
        network and are logged on through the NetScaler Gateway Plug-in, network traffic destined to a printer or another
        device within the home network is not intercepted. Possible values = ON, OFF, REVERSE

    locallanaccess(str): Set local LAN access. If split tunneling is OFF, and you set local LAN access to ON, the local
        client can route traffic to its local interface. When the local area network switch is specified, this
        combination of switches is useful. The client can allow local LAN access to devices that commonly have
        non-routable addresses, such as local printers or local file servers. Possible values = ON, OFF

    rfc1918(str): As defined in the local area network, allow only the following local area network addresses to bypass the
        VPN tunnel when the local LAN access feature is enabled: * 10.*.*.*, * 172.16.*.*, * 192.168.*.*. Possible values
        = ON, OFF

    spoofiip(str): IP address that the intranet application uses to route the connection through the virtual adapter.
        Possible values = ON, OFF

    killconnections(str): Specify whether the NetScaler Gateway Plug-in should disconnect all preexisting connections, such
        as the connections existing before the user logged on to NetScaler Gateway, and prevent new incoming connections
        on the NetScaler Gateway Plug-in for Windows and MAC when the user is connected to NetScaler Gateway and split
        tunneling is disabled. Possible values = ON, OFF

    transparentinterception(str): Allow access to network resources by using a single IP address and subnet mask or a range
        of IP addresses. The OFF setting sets the mode to proxy, in which you configure destination and source IP
        addresses and port numbers. If you are using the NetScaler Gateway Plug-in for Windows, set this parameter to ON,
        in which the mode is set to transparent. If you are using the NetScaler Gateway Plug-in for Java, set this
        parameter to OFF. Possible values = ON, OFF

    windowsclienttype(str): Choose between two types of Windows Client\\ a) Application Agent - which always runs in the task
        bar as a standalone application and also has a supporting service which runs permanently when installed\\ b)
        Activex Control - ActiveX control run by Microsoft Internet Explorer. Possible values = AGENT, PLUGIN

    defaultauthorizationaction(str): Specify the network resources that users have access to when they log on to the internal
        network. The default setting for authorization is to deny access to all network resources. Citrix recommends
        using the default global setting and then creating authorization policies to define the network resources users
        can access. If you set the default authorization policy to DENY, you must explicitly authorize access to any
        network resource, which improves security. Possible values = ALLOW, DENY

    authorizationgroup(str): Comma-separated list of groups in which the user is placed when none of the groups that the user
        is a part of is configured on NetScaler Gateway. The authorization policy can be bound to these groups to control
        access to the resources. Minimum length = 1

    smartgroup(str): This is the default group that is chosen when the authentication succeeds in addition to extracted
        groups. Minimum length = 1 Maximum length = 64

    clientidletimeout(int): Time, in minutes, after which to time out the user session if NetScaler Gateway does not detect
        mouse or keyboard activity. Minimum value = 1 Maximum value = 9999

    proxy(str): Set options to apply proxy for accessing the internal resources. Available settings function as follows: *
        BROWSER - Proxy settings are configured only in Internet Explorer and Firefox browsers. * NS - Proxy settings are
        configured on the NetScaler appliance. * OFF - Proxy settings are not configured. Possible values = BROWSER, NS,
        OFF

    allprotocolproxy(str): IP address of the proxy server to use for all protocols supported by NetScaler Gateway. Minimum
        length = 1

    httpproxy(str): IP address of the proxy server to be used for HTTP access for all subsequent connections to the internal
        network. Minimum length = 1

    ftpproxy(str): IP address of the proxy server to be used for FTP access for all subsequent connections to the internal
        network. Minimum length = 1

    socksproxy(str): IP address of the proxy server to be used for SOCKS access for all subsequent connections to the
        internal network. Minimum length = 1

    gopherproxy(str): IP address of the proxy server to be used for GOPHER access for all subsequent connections to the
        internal network. Minimum length = 1

    sslproxy(str): IP address of the proxy server to be used for SSL access for all subsequent connections to the internal
        network. Minimum length = 1

    proxyexception(str): Proxy exception string that will be configured in the browser for bypassing the previously
        configured proxies. Allowed only if proxy type is Browser. Minimum length = 1

    proxylocalbypass(str): Bypass proxy server for local addresses option in Internet Explorer and Firefox proxy server
        settings. Possible values = ENABLED, DISABLED

    clientcleanupprompt(str): Prompt for client-side cache clean-up when a client-initiated session closes. Possible values =
        ON, OFF

    forcecleanup(list(str)): Force cache clean-up when the user closes a session. You can specify all, none, or any
        combination of the client-side items. Possible values = none, all, cookie, addressbar, plugin,
        filesystemapplication, application, applicationdata, clientcertificate, autocomplete, cache

    clientoptions(str): Display only the configured menu options when you select the "Configure NetScaler Gateway" option in
        the NetScaler Gateway Plug-in system tray icon for Windows. Possible values = none, all, services, filetransfer,
        configuration

    clientconfiguration(list(str)): Allow users to change client Debug logging level in Configuration tab of the NetScaler
        Gateway Plug-in for Windows. Possible values = none, trace

    sso(str): Set single sign-on (SSO) for the session. When the user accesses a server, the users logon credentials are
        passed to the server for authentication. Possible values = ON, OFF

    ssocredential(str): Specify whether to use the primary or secondary authentication credentials for single sign-on to the
        server. Possible values = PRIMARY, SECONDARY

    windowsautologon(str): Enable or disable the Windows Auto Logon for the session. If a VPN session is established after
        this setting is enabled, the user is automatically logged on by using Windows credentials after the system is
        restarted. Possible values = ON, OFF

    usemip(str): Enable or disable the use of a unique IP address alias, or a mapped IP address, as the client IP address for
        each client session. Allow NetScaler Gateway to use the mapped IP address as an intranet IP address when all
        other IP addresses are not available.  When IP pooling is configured and the mapped IP is used as an intranet IP
        address, the mapped IP address is used when an intranet IP address cannot be assigned. Possible values = NS, OFF

    useiip(str): Define IP address pool options. Available settings function as follows:  * SPILLOVER - When an address pool
        is configured and the mapped IP is used as an intranet IP address, the mapped IP address is used when an intranet
        IP address cannot be assigned.  * NOSPILLOVER - When intranet IP addresses are enabled and the mapped IP address
        is not used, the Transfer Login page appears for users who have used all available intranet IP addresses.  * OFF
        - Address pool is not configured. Possible values = NOSPILLOVER, SPILLOVER, OFF

    clientdebug(str): Set the trace level on NetScaler Gateway. Technical support technicians use these debug logs for
        in-depth debugging and troubleshooting purposes. Available settings function as follows:  * DEBUG - Detailed
        debug messages are collected and written into the specified file. * STATS - Application audit level error
        messages and debug statistic counters are written into the specified file.  * EVENTS - Application audit-level
        error messages are written into the specified file.  * OFF - Only critical events are logged into the Windows
        Application Log. Possible values = debug, stats, events, OFF

    loginscript(str): Path to the logon script that is run when a session is established. Separate multiple scripts by using
        comma. A "$" in the path signifies that the word following the "$" is an environment variable. Minimum length =
        1

    logoutscript(str): Path to the logout script. Separate multiple scripts by using comma. A "$" in the path signifies that
        the word following the "$" is an environment variable. Minimum length = 1

    homepage(str): Web address of the home page that appears when users log on. Otherwise, users receive the default home
        page for NetScaler Gateway, which is the Access Interface.

    icaproxy(str): Enable ICA proxy to configure secure Internet access to servers running Citrix XenApp or XenDesktop by
        using Citrix Receiver instead of the NetScaler Gateway Plug-in. Possible values = ON, OFF

    wihome(str): Web address of the Web Interface server, such as http://;lt;ipAddress;gt;/Citrix/XenApp, or Receiver for
        Web, which enumerates the virtualized resources, such as XenApp, XenDesktop, and cloud applications. This web
        address is used as the home page in ICA proxy mode.  If Client Choices is ON, you must configure this setting.
        Because the user can choose between FullClient and ICAProxy, the user may see a different home page. An Internet
        web site may appear if the user gets the FullClient option, or a Web Interface site if the user gets the ICAProxy
        option. If the setting is not configured, the XenApp option does not appear as a client choice.

    wihomeaddresstype(str): Type of the wihome address(IPV4/V6). Possible values = IPV4, IPV6

    citrixreceiverhome(str): Web address for the Citrix Receiver home page. Configure NetScaler Gateway so that when users
        log on to the appliance, the NetScaler Gateway Plug-in opens a web browser that allows single sign-on to the
        Citrix Receiver home page.

    wiportalmode(str): Layout on the Access Interface. The COMPACT value indicates the use of small icons. Possible values =
        NORMAL, COMPACT

    clientchoices(str): Provide users with multiple logon options. With client choices, users have the option of logging on
        by using the NetScaler Gateway Plug-in for Windows, NetScaler Gateway Plug-in for Java, the Web Interface, or
        clientless access from one location. Depending on how NetScaler Gateway is configured, users are presented with
        up to three icons for logon choices. The most common are the NetScaler Gateway Plug-in for Windows, Web
        Interface, and clientless access. Possible values = ON, OFF

    epaclienttype(str): Choose between two types of End point Windows Client a) Application Agent - which always runs in the
        task bar as a standalone application and also has a supporting service which runs permanently when installed b)
        Activex Control - ActiveX control run by Microsoft Internet Explorer. Possible values = AGENT, PLUGIN

    iipdnssuffix(str): An intranet IP DNS suffix. When a user logs on to NetScaler Gateway and is assigned an IP address, a
        DNS record for the user name and IP address combination is added to the NetScaler Gateway DNS cache. You can
        configure a DNS suffix to append to the user name when the DNS record is added to the cache. You can reach to the
        host from where the user is logged on by using the users name, which can be easier to remember than an IP
        address. When the user logs off from NetScaler Gateway, the record is removed from the DNS cache. Minimum length
        = 1

    forcedtimeout(int): Force a disconnection from the NetScaler Gateway Plug-in with NetScaler Gateway after a specified
        number of minutes. If the session closes, the user must log on again. Minimum value = 1 Maximum value = 65535

    forcedtimeoutwarning(int): Number of minutes to warn a user before the user session is disconnected. Minimum value = 1
        Maximum value = 255

    ntdomain(str): Single sign-on domain to use for single sign-on to applications in the internal network. This setting can
        be overwritten by the domain that users specify at the time of logon or by the domain that the authentication
        server returns. Minimum length = 1 Maximum length = 32

    clientlessvpnmode(str): Enable clientless access for web, XenApp or XenDesktop, and FileShare resources without
        installing the NetScaler Gateway Plug-in. Available settings function as follows:  * ON - Allow only clientless
        access.  * OFF - Allow clientless access after users log on with the NetScaler Gateway Plug-in.  * DISABLED - Do
        not allow clientless access. Possible values = ON, OFF, DISABLED

    emailhome(str): Web address for the web-based email, such as Outlook Web Access.

    clientlessmodeurlencoding(str): When clientless access is enabled, you can choose to encode the addresses of internal web
        applications or to leave the address as clear text. Available settings function as follows:  * OPAQUE - Use
        standard encoding mechanisms to make the domain and protocol part of the resource unclear to users.  * CLEAR - Do
        not encode the web address and make it visible to users.  * ENCRYPT - Allow the domain and protocol to be
        encrypted using a session key. When the web address is encrypted, the URL is different for each user session for
        the same web resource. If users bookmark the encoded web address, save it in the web browser and then log off,
        they cannot connect to the web address when they log on and use the bookmark. If users save the encrypted
        bookmark in the Access Interface during their session, the bookmark works each time the user logs on. Possible
        values = TRANSPARENT, OPAQUE, ENCRYPT

    clientlesspersistentcookie(str): State of persistent cookies in clientless access mode. Persistent cookies are required
        for accessing certain features of SharePoint, such as opening and editing Microsoft Word, Excel, and PowerPoint
        documents hosted on the SharePoint server. A persistent cookie remains on the user device and is sent with each
        HTTP request. NetScaler Gateway encrypts the persistent cookie before sending it to the plug-in on the user
        device, and refreshes the cookie periodically as long as the session exists. The cookie becomes stale if the
        session ends. Available settings function as follows:  * ALLOW - Enable persistent cookies. Users can open and
        edit Microsoft documents stored in SharePoint.  * DENY - Disable persistent cookies. Users cannot open and edit
        Microsoft documents stored in SharePoint.  * PROMPT - Prompt users to allow or deny persistent cookies during the
        session. Persistent cookies are not required for clientless access if users do not connect to SharePoint.
        Possible values = ALLOW, DENY, PROMPT

    allowedlogingroups(str): Specify groups that have permission to log on to NetScaler Gateway. Users who do not belong to
        this group or groups are denied access even if they have valid credentials. Minimum length = 1 Maximum length =
        511

    securebrowse(str): Allow users to connect through NetScaler Gateway to network resources from iOS and Android mobile
        devices with Citrix Receiver. Users do not need to establish a full VPN tunnel to access resources in the secure
        network. Possible values = ENABLED, DISABLED

    storefronturl(str): Web address for StoreFront to be used in this session for enumeration of resources from XenApp or
        XenDesktop. Minimum length = 1 Maximum length = 255

    sfgatewayauthtype(str): The authentication type configured for the NetScaler Gateway on StoreFront. Possible values =
        domain, RSA, domainAndRSA, SMS, smartCard, sfAuth, sfAuthAndRSA

    kcdaccount(str): The kcd account details to be used in SSO. Minimum length = 1 Maximum length = 32

    rdpclientprofilename(str): Name of the RDP profile associated with the vserver. Minimum length = 1 Maximum length = 31

    windowspluginupgrade(str): Option to set plugin upgrade behaviour for Win. Possible values = Always, Essential, Never

    macpluginupgrade(str): Option to set plugin upgrade behaviour for Mac. Possible values = Always, Essential, Never

    linuxpluginupgrade(str): Option to set plugin upgrade behaviour for Linux. Possible values = Always, Essential, Never

    iconwithreceiver(str): Option to decide whether to show plugin icon along with receiver. Possible values = ON, OFF

    alwaysonprofilename(str): Name of the AlwaysON profile associated with the session action. The builtin profile named none
        can be used to explicitly disable AlwaysON for the session action. Minimum length = 1 Maximum length = 31

    autoproxyurl(str): URL to auto proxy config file.

    pcoipprofilename(str): Name of the PCOIP profile associated with the session action. The builtin profile named none can
        be used to explicitly disable PCOIP for the session action. Minimum length = 1 Maximum length = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnsessionaction <args>

    '''

    result = {}

    payload = {'vpnsessionaction': {}}

    if name:
        payload['vpnsessionaction']['name'] = name

    if useraccounting:
        payload['vpnsessionaction']['useraccounting'] = useraccounting

    if httpport:
        payload['vpnsessionaction']['httpport'] = httpport

    if winsip:
        payload['vpnsessionaction']['winsip'] = winsip

    if dnsvservername:
        payload['vpnsessionaction']['dnsvservername'] = dnsvservername

    if splitdns:
        payload['vpnsessionaction']['splitdns'] = splitdns

    if sesstimeout:
        payload['vpnsessionaction']['sesstimeout'] = sesstimeout

    if clientsecurity:
        payload['vpnsessionaction']['clientsecurity'] = clientsecurity

    if clientsecuritygroup:
        payload['vpnsessionaction']['clientsecuritygroup'] = clientsecuritygroup

    if clientsecuritymessage:
        payload['vpnsessionaction']['clientsecuritymessage'] = clientsecuritymessage

    if clientsecuritylog:
        payload['vpnsessionaction']['clientsecuritylog'] = clientsecuritylog

    if splittunnel:
        payload['vpnsessionaction']['splittunnel'] = splittunnel

    if locallanaccess:
        payload['vpnsessionaction']['locallanaccess'] = locallanaccess

    if rfc1918:
        payload['vpnsessionaction']['rfc1918'] = rfc1918

    if spoofiip:
        payload['vpnsessionaction']['spoofiip'] = spoofiip

    if killconnections:
        payload['vpnsessionaction']['killconnections'] = killconnections

    if transparentinterception:
        payload['vpnsessionaction']['transparentinterception'] = transparentinterception

    if windowsclienttype:
        payload['vpnsessionaction']['windowsclienttype'] = windowsclienttype

    if defaultauthorizationaction:
        payload['vpnsessionaction']['defaultauthorizationaction'] = defaultauthorizationaction

    if authorizationgroup:
        payload['vpnsessionaction']['authorizationgroup'] = authorizationgroup

    if smartgroup:
        payload['vpnsessionaction']['smartgroup'] = smartgroup

    if clientidletimeout:
        payload['vpnsessionaction']['clientidletimeout'] = clientidletimeout

    if proxy:
        payload['vpnsessionaction']['proxy'] = proxy

    if allprotocolproxy:
        payload['vpnsessionaction']['allprotocolproxy'] = allprotocolproxy

    if httpproxy:
        payload['vpnsessionaction']['httpproxy'] = httpproxy

    if ftpproxy:
        payload['vpnsessionaction']['ftpproxy'] = ftpproxy

    if socksproxy:
        payload['vpnsessionaction']['socksproxy'] = socksproxy

    if gopherproxy:
        payload['vpnsessionaction']['gopherproxy'] = gopherproxy

    if sslproxy:
        payload['vpnsessionaction']['sslproxy'] = sslproxy

    if proxyexception:
        payload['vpnsessionaction']['proxyexception'] = proxyexception

    if proxylocalbypass:
        payload['vpnsessionaction']['proxylocalbypass'] = proxylocalbypass

    if clientcleanupprompt:
        payload['vpnsessionaction']['clientcleanupprompt'] = clientcleanupprompt

    if forcecleanup:
        payload['vpnsessionaction']['forcecleanup'] = forcecleanup

    if clientoptions:
        payload['vpnsessionaction']['clientoptions'] = clientoptions

    if clientconfiguration:
        payload['vpnsessionaction']['clientconfiguration'] = clientconfiguration

    if sso:
        payload['vpnsessionaction']['sso'] = sso

    if ssocredential:
        payload['vpnsessionaction']['ssocredential'] = ssocredential

    if windowsautologon:
        payload['vpnsessionaction']['windowsautologon'] = windowsautologon

    if usemip:
        payload['vpnsessionaction']['usemip'] = usemip

    if useiip:
        payload['vpnsessionaction']['useiip'] = useiip

    if clientdebug:
        payload['vpnsessionaction']['clientdebug'] = clientdebug

    if loginscript:
        payload['vpnsessionaction']['loginscript'] = loginscript

    if logoutscript:
        payload['vpnsessionaction']['logoutscript'] = logoutscript

    if homepage:
        payload['vpnsessionaction']['homepage'] = homepage

    if icaproxy:
        payload['vpnsessionaction']['icaproxy'] = icaproxy

    if wihome:
        payload['vpnsessionaction']['wihome'] = wihome

    if wihomeaddresstype:
        payload['vpnsessionaction']['wihomeaddresstype'] = wihomeaddresstype

    if citrixreceiverhome:
        payload['vpnsessionaction']['citrixreceiverhome'] = citrixreceiverhome

    if wiportalmode:
        payload['vpnsessionaction']['wiportalmode'] = wiportalmode

    if clientchoices:
        payload['vpnsessionaction']['clientchoices'] = clientchoices

    if epaclienttype:
        payload['vpnsessionaction']['epaclienttype'] = epaclienttype

    if iipdnssuffix:
        payload['vpnsessionaction']['iipdnssuffix'] = iipdnssuffix

    if forcedtimeout:
        payload['vpnsessionaction']['forcedtimeout'] = forcedtimeout

    if forcedtimeoutwarning:
        payload['vpnsessionaction']['forcedtimeoutwarning'] = forcedtimeoutwarning

    if ntdomain:
        payload['vpnsessionaction']['ntdomain'] = ntdomain

    if clientlessvpnmode:
        payload['vpnsessionaction']['clientlessvpnmode'] = clientlessvpnmode

    if emailhome:
        payload['vpnsessionaction']['emailhome'] = emailhome

    if clientlessmodeurlencoding:
        payload['vpnsessionaction']['clientlessmodeurlencoding'] = clientlessmodeurlencoding

    if clientlesspersistentcookie:
        payload['vpnsessionaction']['clientlesspersistentcookie'] = clientlesspersistentcookie

    if allowedlogingroups:
        payload['vpnsessionaction']['allowedlogingroups'] = allowedlogingroups

    if securebrowse:
        payload['vpnsessionaction']['securebrowse'] = securebrowse

    if storefronturl:
        payload['vpnsessionaction']['storefronturl'] = storefronturl

    if sfgatewayauthtype:
        payload['vpnsessionaction']['sfgatewayauthtype'] = sfgatewayauthtype

    if kcdaccount:
        payload['vpnsessionaction']['kcdaccount'] = kcdaccount

    if rdpclientprofilename:
        payload['vpnsessionaction']['rdpclientprofilename'] = rdpclientprofilename

    if windowspluginupgrade:
        payload['vpnsessionaction']['windowspluginupgrade'] = windowspluginupgrade

    if macpluginupgrade:
        payload['vpnsessionaction']['macpluginupgrade'] = macpluginupgrade

    if linuxpluginupgrade:
        payload['vpnsessionaction']['linuxpluginupgrade'] = linuxpluginupgrade

    if iconwithreceiver:
        payload['vpnsessionaction']['iconwithreceiver'] = iconwithreceiver

    if alwaysonprofilename:
        payload['vpnsessionaction']['alwaysonprofilename'] = alwaysonprofilename

    if autoproxyurl:
        payload['vpnsessionaction']['autoproxyurl'] = autoproxyurl

    if pcoipprofilename:
        payload['vpnsessionaction']['pcoipprofilename'] = pcoipprofilename

    execution = __proxy__['citrixns.put']('config/vpnsessionaction', payload)

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


def update_vpnsessionpolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the vpnsessionpolicy config key.

    name(str): Name for the new session policy that is applied after the user logs on to NetScaler Gateway. Minimum length =
        1

    rule(str): Expression, or name of a named expression, specifying the traffic that matches the policy. Can be written in
        either default or classic syntax.  Maximum length of a string literal in the expression is 255 characters. A
        longer string can be split into smaller strings of up to 255 characters each, and the smaller strings
        concatenated with the + operator. For example, you can create a 500-character string as follows: ";lt;string of
        255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler
        CLI: * If the expression includes one or more spaces, enclose the entire expression in double quotation marks. *
        If the expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Action to be applied by the new session policy if the rule criteria are met. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnsessionpolicy <args>

    '''

    result = {}

    payload = {'vpnsessionpolicy': {}}

    if name:
        payload['vpnsessionpolicy']['name'] = name

    if rule:
        payload['vpnsessionpolicy']['rule'] = rule

    if action:
        payload['vpnsessionpolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/vpnsessionpolicy', payload)

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


def update_vpntrafficaction(name=None, qual=None, apptimeout=None, sso=None, hdx=None, formssoaction=None, fta=None,
                            wanscaler=None, kcdaccount=None, samlssoprofile=None, proxy=None, userexpression=None,
                            passwdexpression=None, save=False):
    '''
    Update the running configuration for the vpntrafficaction config key.

    name(str): Name for the traffic action. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after a traffic action is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my action" or my action). Minimum length = 1

    qual(str): Protocol, either HTTP or TCP, to be used with the action. Possible values = http, tcp

    apptimeout(int): Maximum amount of time, in minutes, a user can stay logged on to the web application. Minimum value = 1
        Maximum value = 715827

    sso(str): Provide single sign-on to the web application. Possible values = ON, OFF

    hdx(str): Provide hdx proxy to the ICA traffic. Possible values = ON, OFF

    formssoaction(str): Name of the form-based single sign-on profile. Form-based single sign-on allows users to log on one
        time to all protected applications in your network, instead of requiring them to log on separately to access each
        one.

    fta(str): Specify file type association, which is a list of file extensions that users are allowed to open. Possible
        values = ON, OFF

    wanscaler(str): Use the Repeater Plug-in to optimize network traffic. Possible values = ON, OFF

    kcdaccount(str): Kerberos constrained delegation account name. Default value: "Default" Minimum length = 1 Maximum length
        = 32

    samlssoprofile(str): Profile to be used for doing SAML SSO to remote relying party. Minimum length = 1

    proxy(str): IP address and Port of the proxy server to be used for HTTP access for this request. Minimum length = 1

    userexpression(str): expression that will be evaluated to obtain username for SingleSignOn. Maximum length = 256

    passwdexpression(str): expression that will be evaluated to obtain password for SingleSignOn. Maximum length = 256

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpntrafficaction <args>

    '''

    result = {}

    payload = {'vpntrafficaction': {}}

    if name:
        payload['vpntrafficaction']['name'] = name

    if qual:
        payload['vpntrafficaction']['qual'] = qual

    if apptimeout:
        payload['vpntrafficaction']['apptimeout'] = apptimeout

    if sso:
        payload['vpntrafficaction']['sso'] = sso

    if hdx:
        payload['vpntrafficaction']['hdx'] = hdx

    if formssoaction:
        payload['vpntrafficaction']['formssoaction'] = formssoaction

    if fta:
        payload['vpntrafficaction']['fta'] = fta

    if wanscaler:
        payload['vpntrafficaction']['wanscaler'] = wanscaler

    if kcdaccount:
        payload['vpntrafficaction']['kcdaccount'] = kcdaccount

    if samlssoprofile:
        payload['vpntrafficaction']['samlssoprofile'] = samlssoprofile

    if proxy:
        payload['vpntrafficaction']['proxy'] = proxy

    if userexpression:
        payload['vpntrafficaction']['userexpression'] = userexpression

    if passwdexpression:
        payload['vpntrafficaction']['passwdexpression'] = passwdexpression

    execution = __proxy__['citrixns.put']('config/vpntrafficaction', payload)

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


def update_vpntrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the vpntrafficpolicy config key.

    name(str): Name for the traffic policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the policy is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic or
        default syntax. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can
        be split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;" The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Action to apply to traffic that matches the policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpntrafficpolicy <args>

    '''

    result = {}

    payload = {'vpntrafficpolicy': {}}

    if name:
        payload['vpntrafficpolicy']['name'] = name

    if rule:
        payload['vpntrafficpolicy']['rule'] = rule

    if action:
        payload['vpntrafficpolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/vpntrafficpolicy', payload)

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


def update_vpnurl(urlname=None, linkname=None, actualurl=None, vservername=None, clientlessaccess=None, comment=None,
                  iconurl=None, ssotype=None, applicationtype=None, samlssoprofile=None, save=False):
    '''
    Update the running configuration for the vpnurl config key.

    urlname(str): Name of the bookmark link. Minimum length = 1

    linkname(str): Description of the bookmark link. The description appears in the Access Interface. Minimum length = 1

    actualurl(str): Web address for the bookmark link. Minimum length = 1

    vservername(str): Name of the associated LB/CS vserver.

    clientlessaccess(str): If clientless access to the resource hosting the link is allowed, also use clientless access for
        the bookmarked web address in the Secure Client Access based session. Allows single sign-on and other HTTP
        processing on NetScaler Gateway for HTTPS resources. Default value: OFF Possible values = ON, OFF

    comment(str): Any comments associated with the bookmark link.

    iconurl(str): URL to fetch icon file for displaying this resource.

    ssotype(str): Single sign on type for unified gateway. Possible values = unifiedgateway, selfauth, samlauth

    applicationtype(str): The type of application this VPN URL represents. Possible values are CVPN/SaaS/VPN. Possible values
        = CVPN, VPN, SaaS

    samlssoprofile(str): Profile to be used for doing SAML SSO.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnurl <args>

    '''

    result = {}

    payload = {'vpnurl': {}}

    if urlname:
        payload['vpnurl']['urlname'] = urlname

    if linkname:
        payload['vpnurl']['linkname'] = linkname

    if actualurl:
        payload['vpnurl']['actualurl'] = actualurl

    if vservername:
        payload['vpnurl']['vservername'] = vservername

    if clientlessaccess:
        payload['vpnurl']['clientlessaccess'] = clientlessaccess

    if comment:
        payload['vpnurl']['comment'] = comment

    if iconurl:
        payload['vpnurl']['iconurl'] = iconurl

    if ssotype:
        payload['vpnurl']['ssotype'] = ssotype

    if applicationtype:
        payload['vpnurl']['applicationtype'] = applicationtype

    if samlssoprofile:
        payload['vpnurl']['samlssoprofile'] = samlssoprofile

    execution = __proxy__['citrixns.put']('config/vpnurl', payload)

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


def update_vpnvserver(name=None, servicetype=None, ipv46=None, range=None, port=None, state=None, authentication=None,
                      doublehop=None, maxaaausers=None, icaonly=None, icaproxysessionmigration=None, dtls=None,
                      loginonce=None, advancedepa=None, devicecert=None, certkeynames=None, downstateflush=None,
                      listenpolicy=None, listenpriority=None, tcpprofilename=None, httpprofilename=None, comment=None,
                      appflowlog=None, icmpvsrresponse=None, rhistate=None, netprofile=None,
                      cginfrahomepageredirect=None, maxloginattempts=None, failedlogintimeout=None, l2conn=None,
                      deploymenttype=None, rdpserverprofilename=None, windowsepapluginupgrade=None,
                      linuxepapluginupgrade=None, macepapluginupgrade=None, logoutonsmartcardremoval=None,
                      userdomains=None, authnprofile=None, vserverfqdn=None, pcoipvserverprofilename=None, newname=None,
                      save=False):
    '''
    Update the running configuration for the vpnvserver config key.

    name(str): Name for the NetScaler Gateway virtual server. Must begin with an ASCII alphabetic or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Can be changed after the virtual server is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my server" or my server). Minimum length = 1

    servicetype(str): Protocol used by the NetScaler Gateway virtual server. Default value: SSL Possible values = SSL

    ipv46(str): IPv4 or IPv6 address of the NetScaler Gateway virtual server. Usually a public IP address. User devices send
        connection requests to this IP address. Minimum length = 1

    range(int): Range of NetScaler Gateway virtual server IP addresses. The consecutively numbered range of IP addresses
        begins with the address specified by the IP Address parameter.  In the configuration utility, select Network
        VServer to enter a range. Default value: 1 Minimum value = 1

    port(int): TCP port on which the virtual server listens. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    state(str): State of the virtual server. If the virtual server is disabled, requests are not processed. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    authentication(str): Require authentication for users connecting to NetScaler Gateway. Default value: ON Possible values
        = ON, OFF

    doublehop(str): Use the NetScaler Gateway appliance in a double-hop configuration. A double-hop deployment provides an
        extra layer of security for the internal network by using three firewalls to divide the DMZ into two stages. Such
        a deployment can have one appliance in the DMZ and one appliance in the secure network. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    maxaaausers(int): Maximum number of concurrent user sessions allowed on this virtual server. The actual number of users
        allowed to log on to this virtual server depends on the total number of user licenses.

    icaonly(str): - When set to ON, it implies Basic mode where the user can log on using either Citrix Receiver or a browser
        and get access to the published apps configured at the XenApp/XenDEsktop environment pointed out by the WIHome
        parameter. Users are not allowed to connect using the NetScaler Gateway Plug-in and end point scans cannot be
        configured. Number of users that can log in and access the apps are not limited by the license in this mode.   -
        When set to OFF, it implies Smart Access mode where the user can log on using either Citrix Receiver or a browser
        or a NetScaler Gateway Plug-in. The admin can configure end point scans to be run on the client systems and then
        use the results to control access to the published apps. In this mode, the client can connect to the gateway in
        other client modes namely VPN and CVPN. Number of users that can log in and access the resources are limited by
        the CCU licenses in this mode. Default value: OFF Possible values = ON, OFF

    icaproxysessionmigration(str): This option determines if an existing ICA Proxy session is transferred when the user logs
        on from another device. Default value: OFF Possible values = ON, OFF

    dtls(str): This option starts/stops the turn service on the vserver. Default value: OFF Possible values = ON, OFF

    loginonce(str): This option enables/disables seamless SSO for this Vserver. Default value: OFF Possible values = ON, OFF

    advancedepa(str): This option tells whether advanced EPA is enabled on this virtual server. Default value: OFF Possible
        values = ON, OFF

    devicecert(str): Indicates whether device certificate check as a part of EPA is on or off. Default value: OFF Possible
        values = ON, OFF

    certkeynames(str): Name of the certificate key that was bound to the corresponding SSL virtual server as the Certificate
        Authority for the device certificate. Minimum length = 1 Maximum length = 127

    downstateflush(str): Close existing connections when the virtual server is marked DOWN, which means the server might have
        timed out. Disconnecting existing connections frees resources and in certain cases speeds recovery of overloaded
        load balancing setups. Enable this setting on servers in which the connections can safely be closed when they are
        marked DOWN. Do not enable DOWN state flush on servers that must complete their transactions. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    listenpolicy(str): String specifying the listen policy for the NetScaler Gateway virtual server. Can be either a named
        expression or a default syntax expression. The NetScaler Gateway virtual server processes only the traffic for
        which the expression evaluates to true. Default value: "none"

    listenpriority(int): Integer specifying the priority of the listen policy. A higher number specifies a lower priority. If
        a request matches the listen policies of more than one virtual server, the virtual server whose listen policy has
        the highest priority (the lowest priority number) accepts the request. Default value: 101 Minimum value = 0
        Maximum value = 100

    tcpprofilename(str): Name of the TCP profile to assign to this virtual server. Minimum length = 1 Maximum length = 127

    httpprofilename(str): Name of the HTTP profile to assign to this virtual server. Default value:
        "nshttp_default_strict_validation" Minimum length = 1 Maximum length = 127

    comment(str): Any comments associated with the virtual server.

    appflowlog(str): Log AppFlow records that contain standard NetFlow or IPFIX information, such as time stamps for the
        beginning and end of a flow, packet count, and byte count. Also log records that contain application-level
        information, such as HTTP web addresses, HTTP request methods and response status codes, server response time,
        and latency. Default value: DISABLED Possible values = ENABLED, DISABLED

    icmpvsrresponse(str): Criterion for responding to PING requests sent to this virtual server. If this parameter is set to
        ACTIVE, respond only if the virtual server is available. With the PASSIVE setting, respond even if the virtual
        server is not available. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    rhistate(str): A host route is injected according to the setting on the virtual servers.  * If set to PASSIVE on all the
        virtual servers that share the IP address, the appliance always injects the hostroute.  * If set to ACTIVE on all
        the virtual servers that share the IP address, the appliance injects even if one virtual server is UP.  * If set
        to ACTIVE on some virtual servers and PASSIVE on the others, the appliance injects even if one virtual server set
        to ACTIVE is UP. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    netprofile(str): The name of the network profile. Minimum length = 1 Maximum length = 127

    cginfrahomepageredirect(str): When client requests ShareFile resources and NetScaler Gateway detects that the user is
        unauthenticated or the user session has expired, disabling this option takes the user to the originally requested
        ShareFile resource after authentication (instead of taking the user to the default VPN home page). Default value:
        ENABLED Possible values = ENABLED, DISABLED

    maxloginattempts(int): Maximum number of logon attempts. Minimum value = 1 Maximum value = 255

    failedlogintimeout(int): Number of minutes an account will be locked if user exceeds maximum permissible attempts.
        Minimum value = 1

    l2conn(str): Use Layer 2 parameters (channel number, MAC address, and VLAN ID) in addition to the 4-tuple (;lt;source
        IP;gt;:;lt;source port;gt;::;lt;destination IP;gt;:;lt;destination port;gt;) that is used to identify a
        connection. Allows multiple TCP and non-TCP connections with the same 4-tuple to coexist on the NetScaler
        appliance. Possible values = ON, OFF

    deploymenttype(str): . Default value: 5 Possible values = NONE, ICA_WEBINTERFACE, ICA_STOREFRONT, MOBILITY, WIONNS

    rdpserverprofilename(str): Name of the RDP server profile associated with the vserver. Minimum length = 1 Maximum length
        = 31

    windowsepapluginupgrade(str): Option to set plugin upgrade behaviour for Win. Possible values = Always, Essential, Never

    linuxepapluginupgrade(str): Option to set plugin upgrade behaviour for Linux. Possible values = Always, Essential, Never

    macepapluginupgrade(str): Option to set plugin upgrade behaviour for Mac. Possible values = Always, Essential, Never

    logoutonsmartcardremoval(str): Option to VPN plugin behavior when smartcard or its reader is removed. Default value: OFF
        Possible values = ON, OFF

    userdomains(str): List of user domains specified as comma seperated value.

    authnprofile(str): Authentication Profile entity on virtual server. This entity can be used to offload authentication to
        AAA vserver for multi-factor(nFactor) authentication.

    vserverfqdn(str): Fully qualified domain name for a VPN virtual server. This is used during StoreFront configuration
        generation.

    pcoipvserverprofilename(str): Name of the PCoIP vserver profile associated with the vserver. Minimum length = 1 Maximum
        length = 31

    newname(str): New name for the NetScaler Gateway virtual server. Must begin with an ASCII alphabetic or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters.   The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my server" or my
        server). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl_vpn.update_vpnvserver <args>

    '''

    result = {}

    payload = {'vpnvserver': {}}

    if name:
        payload['vpnvserver']['name'] = name

    if servicetype:
        payload['vpnvserver']['servicetype'] = servicetype

    if ipv46:
        payload['vpnvserver']['ipv46'] = ipv46

    if range:
        payload['vpnvserver']['range'] = range

    if port:
        payload['vpnvserver']['port'] = port

    if state:
        payload['vpnvserver']['state'] = state

    if authentication:
        payload['vpnvserver']['authentication'] = authentication

    if doublehop:
        payload['vpnvserver']['doublehop'] = doublehop

    if maxaaausers:
        payload['vpnvserver']['maxaaausers'] = maxaaausers

    if icaonly:
        payload['vpnvserver']['icaonly'] = icaonly

    if icaproxysessionmigration:
        payload['vpnvserver']['icaproxysessionmigration'] = icaproxysessionmigration

    if dtls:
        payload['vpnvserver']['dtls'] = dtls

    if loginonce:
        payload['vpnvserver']['loginonce'] = loginonce

    if advancedepa:
        payload['vpnvserver']['advancedepa'] = advancedepa

    if devicecert:
        payload['vpnvserver']['devicecert'] = devicecert

    if certkeynames:
        payload['vpnvserver']['certkeynames'] = certkeynames

    if downstateflush:
        payload['vpnvserver']['downstateflush'] = downstateflush

    if listenpolicy:
        payload['vpnvserver']['listenpolicy'] = listenpolicy

    if listenpriority:
        payload['vpnvserver']['listenpriority'] = listenpriority

    if tcpprofilename:
        payload['vpnvserver']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['vpnvserver']['httpprofilename'] = httpprofilename

    if comment:
        payload['vpnvserver']['comment'] = comment

    if appflowlog:
        payload['vpnvserver']['appflowlog'] = appflowlog

    if icmpvsrresponse:
        payload['vpnvserver']['icmpvsrresponse'] = icmpvsrresponse

    if rhistate:
        payload['vpnvserver']['rhistate'] = rhistate

    if netprofile:
        payload['vpnvserver']['netprofile'] = netprofile

    if cginfrahomepageredirect:
        payload['vpnvserver']['cginfrahomepageredirect'] = cginfrahomepageredirect

    if maxloginattempts:
        payload['vpnvserver']['maxloginattempts'] = maxloginattempts

    if failedlogintimeout:
        payload['vpnvserver']['failedlogintimeout'] = failedlogintimeout

    if l2conn:
        payload['vpnvserver']['l2conn'] = l2conn

    if deploymenttype:
        payload['vpnvserver']['deploymenttype'] = deploymenttype

    if rdpserverprofilename:
        payload['vpnvserver']['rdpserverprofilename'] = rdpserverprofilename

    if windowsepapluginupgrade:
        payload['vpnvserver']['windowsepapluginupgrade'] = windowsepapluginupgrade

    if linuxepapluginupgrade:
        payload['vpnvserver']['linuxepapluginupgrade'] = linuxepapluginupgrade

    if macepapluginupgrade:
        payload['vpnvserver']['macepapluginupgrade'] = macepapluginupgrade

    if logoutonsmartcardremoval:
        payload['vpnvserver']['logoutonsmartcardremoval'] = logoutonsmartcardremoval

    if userdomains:
        payload['vpnvserver']['userdomains'] = userdomains

    if authnprofile:
        payload['vpnvserver']['authnprofile'] = authnprofile

    if vserverfqdn:
        payload['vpnvserver']['vserverfqdn'] = vserverfqdn

    if pcoipvserverprofilename:
        payload['vpnvserver']['pcoipvserverprofilename'] = pcoipvserverprofilename

    if newname:
        payload['vpnvserver']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/vpnvserver', payload)

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
