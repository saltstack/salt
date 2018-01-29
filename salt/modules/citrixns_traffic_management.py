# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the traffic-management key.

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

__virtualname__ = 'traffic_management'


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

    return False, 'The traffic_management execution module can only be loaded for citrixns proxy minions.'


def add_tmformssoaction(name=None, actionurl=None, userfield=None, passwdfield=None, ssosuccessrule=None,
                        namevaluepair=None, responsesize=None, nvtype=None, submitmethod=None, save=False):
    '''
    Add a new tmformssoaction to the running configuration.

    name(str): Name for the new form-based single sign-on profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an SSO action is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    actionurl(str): URL to which the completed form is submitted. Minimum length = 1

    userfield(str): Name of the form field in which the user types in the user ID. Minimum length = 1

    passwdfield(str): Name of the form field in which the user types in the password. Minimum length = 1

    ssosuccessrule(str): Expression, that checks to see if single sign-on is successful.

    namevaluepair(str): Name-value pair attributes to send to the server in addition to sending the username and password.
        Value names are separated by an ampersand (;amp;) (for example, name1=value1;amp;name2=value2).

    responsesize(int): Number of bytes, in the response, to parse for extracting the forms. Default value: 8096

    nvtype(str): Type of processing of the name-value pair. If you specify STATIC, the values configured by the administrator
        are used. For DYNAMIC, the response is parsed, and the form is extracted and then submitted. Default value:
        DYNAMIC Possible values = STATIC, DYNAMIC

    submitmethod(str): HTTP method used by the single sign-on form to send the logon credentials to the logon server. Applies
        only to STATIC name-value type. Default value: GET Possible values = GET, POST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmformssoaction <args>

    '''

    result = {}

    payload = {'tmformssoaction': {}}

    if name:
        payload['tmformssoaction']['name'] = name

    if actionurl:
        payload['tmformssoaction']['actionurl'] = actionurl

    if userfield:
        payload['tmformssoaction']['userfield'] = userfield

    if passwdfield:
        payload['tmformssoaction']['passwdfield'] = passwdfield

    if ssosuccessrule:
        payload['tmformssoaction']['ssosuccessrule'] = ssosuccessrule

    if namevaluepair:
        payload['tmformssoaction']['namevaluepair'] = namevaluepair

    if responsesize:
        payload['tmformssoaction']['responsesize'] = responsesize

    if nvtype:
        payload['tmformssoaction']['nvtype'] = nvtype

    if submitmethod:
        payload['tmformssoaction']['submitmethod'] = submitmethod

    execution = __proxy__['citrixns.post']('config/tmformssoaction', payload)

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


def add_tmglobal_auditnslogpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None, save=False):
    '''
    Add a new tmglobal_auditnslogpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance tmsession policy. Expression or other value specifying the next
        policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a priority
        number that is numerically higher than the highest numbered priority, policy evaluation ends. An UNDEF event is
        triggered if: * The expression is invalid. * The expression evaluates to a priority number that is numerically
        lower than the current policys priority. * The expression evaluates to a priority number that is between the
        current policys priority number (say, 30) and the highest priority number (say, 100), but does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number increments by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmglobal_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'tmglobal_auditnslogpolicy_binding': {}}

    if priority:
        payload['tmglobal_auditnslogpolicy_binding']['priority'] = priority

    if policyname:
        payload['tmglobal_auditnslogpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['tmglobal_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    execution = __proxy__['citrixns.post']('config/tmglobal_auditnslogpolicy_binding', payload)

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


def add_tmglobal_auditsyslogpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None, save=False):
    '''
    Add a new tmglobal_auditsyslogpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance tmsession policy. Expression or other value specifying the next
        policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a priority
        number that is numerically higher than the highest numbered priority, policy evaluation ends. An UNDEF event is
        triggered if: * The expression is invalid. * The expression evaluates to a priority number that is numerically
        lower than the current policys priority. * The expression evaluates to a priority number that is between the
        current policys priority number (say, 30) and the highest priority number (say, 100), but does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number increments by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmglobal_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'tmglobal_auditsyslogpolicy_binding': {}}

    if priority:
        payload['tmglobal_auditsyslogpolicy_binding']['priority'] = priority

    if policyname:
        payload['tmglobal_auditsyslogpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['tmglobal_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    execution = __proxy__['citrixns.post']('config/tmglobal_auditsyslogpolicy_binding', payload)

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


def add_tmglobal_tmsessionpolicy_binding(priority=None, builtin=None, policyname=None, gotopriorityexpression=None,
                                         save=False):
    '''
    Add a new tmglobal_tmsessionpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmglobal_tmsessionpolicy_binding <args>

    '''

    result = {}

    payload = {'tmglobal_tmsessionpolicy_binding': {}}

    if priority:
        payload['tmglobal_tmsessionpolicy_binding']['priority'] = priority

    if builtin:
        payload['tmglobal_tmsessionpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['tmglobal_tmsessionpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['tmglobal_tmsessionpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    execution = __proxy__['citrixns.post']('config/tmglobal_tmsessionpolicy_binding', payload)

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


def add_tmglobal_tmtrafficpolicy_binding(priority=None, globalbindtype=None, policyname=None,
                                         gotopriorityexpression=None, ns_type=None, save=False):
    '''
    Add a new tmglobal_tmtrafficpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): The name of the policy.

    gotopriorityexpression(str): Applicable only to advance tmsession policy. Expression or other value specifying the next
        policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher priority number. * END - End policy evaluation. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a priority
        number that is numerically higher than the highest numbered priority, policy evaluation ends. An UNDEF event is
        triggered if: * The expression is invalid. * The expression evaluates to a priority number that is numerically
        lower than the current policys priority. * The expression evaluates to a priority number that is between the
        current policys priority number (say, 30) and the highest priority number (say, 100), but does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number increments by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    ns_type(str): Bindpoint to which the policy is bound. Possible values = REQ_OVERRIDE, REQ_DEFAULT, RES_OVERRIDE,
        RES_DEFAULT

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmglobal_tmtrafficpolicy_binding <args>

    '''

    result = {}

    payload = {'tmglobal_tmtrafficpolicy_binding': {}}

    if priority:
        payload['tmglobal_tmtrafficpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['tmglobal_tmtrafficpolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['tmglobal_tmtrafficpolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['tmglobal_tmtrafficpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if ns_type:
        payload['tmglobal_tmtrafficpolicy_binding']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/tmglobal_tmtrafficpolicy_binding', payload)

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


def add_tmsamlssoprofile(name=None, samlsigningcertname=None, assertionconsumerserviceurl=None, relaystaterule=None,
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
    Add a new tmsamlssoprofile to the running configuration.

    name(str): Name for the new saml single sign-on profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an SSO action is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    samlsigningcertname(str): Name of the SSL certificate that is used to Sign Assertion. Minimum length = 1

    assertionconsumerserviceurl(str): URL to which the assertion is to be sent. Minimum length = 1

    relaystaterule(str): Expression to extract relaystate to be sent along with assertion. Evaluation of this expression
        should return TEXT content. This is typically a targ et url to which user is redirected after the recipient
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

    salt '*' traffic_management.add_tmsamlssoprofile <args>

    '''

    result = {}

    payload = {'tmsamlssoprofile': {}}

    if name:
        payload['tmsamlssoprofile']['name'] = name

    if samlsigningcertname:
        payload['tmsamlssoprofile']['samlsigningcertname'] = samlsigningcertname

    if assertionconsumerserviceurl:
        payload['tmsamlssoprofile']['assertionconsumerserviceurl'] = assertionconsumerserviceurl

    if relaystaterule:
        payload['tmsamlssoprofile']['relaystaterule'] = relaystaterule

    if sendpassword:
        payload['tmsamlssoprofile']['sendpassword'] = sendpassword

    if samlissuername:
        payload['tmsamlssoprofile']['samlissuername'] = samlissuername

    if signaturealg:
        payload['tmsamlssoprofile']['signaturealg'] = signaturealg

    if digestmethod:
        payload['tmsamlssoprofile']['digestmethod'] = digestmethod

    if audience:
        payload['tmsamlssoprofile']['audience'] = audience

    if nameidformat:
        payload['tmsamlssoprofile']['nameidformat'] = nameidformat

    if nameidexpr:
        payload['tmsamlssoprofile']['nameidexpr'] = nameidexpr

    if attribute1:
        payload['tmsamlssoprofile']['attribute1'] = attribute1

    if attribute1expr:
        payload['tmsamlssoprofile']['attribute1expr'] = attribute1expr

    if attribute1friendlyname:
        payload['tmsamlssoprofile']['attribute1friendlyname'] = attribute1friendlyname

    if attribute1format:
        payload['tmsamlssoprofile']['attribute1format'] = attribute1format

    if attribute2:
        payload['tmsamlssoprofile']['attribute2'] = attribute2

    if attribute2expr:
        payload['tmsamlssoprofile']['attribute2expr'] = attribute2expr

    if attribute2friendlyname:
        payload['tmsamlssoprofile']['attribute2friendlyname'] = attribute2friendlyname

    if attribute2format:
        payload['tmsamlssoprofile']['attribute2format'] = attribute2format

    if attribute3:
        payload['tmsamlssoprofile']['attribute3'] = attribute3

    if attribute3expr:
        payload['tmsamlssoprofile']['attribute3expr'] = attribute3expr

    if attribute3friendlyname:
        payload['tmsamlssoprofile']['attribute3friendlyname'] = attribute3friendlyname

    if attribute3format:
        payload['tmsamlssoprofile']['attribute3format'] = attribute3format

    if attribute4:
        payload['tmsamlssoprofile']['attribute4'] = attribute4

    if attribute4expr:
        payload['tmsamlssoprofile']['attribute4expr'] = attribute4expr

    if attribute4friendlyname:
        payload['tmsamlssoprofile']['attribute4friendlyname'] = attribute4friendlyname

    if attribute4format:
        payload['tmsamlssoprofile']['attribute4format'] = attribute4format

    if attribute5:
        payload['tmsamlssoprofile']['attribute5'] = attribute5

    if attribute5expr:
        payload['tmsamlssoprofile']['attribute5expr'] = attribute5expr

    if attribute5friendlyname:
        payload['tmsamlssoprofile']['attribute5friendlyname'] = attribute5friendlyname

    if attribute5format:
        payload['tmsamlssoprofile']['attribute5format'] = attribute5format

    if attribute6:
        payload['tmsamlssoprofile']['attribute6'] = attribute6

    if attribute6expr:
        payload['tmsamlssoprofile']['attribute6expr'] = attribute6expr

    if attribute6friendlyname:
        payload['tmsamlssoprofile']['attribute6friendlyname'] = attribute6friendlyname

    if attribute6format:
        payload['tmsamlssoprofile']['attribute6format'] = attribute6format

    if attribute7:
        payload['tmsamlssoprofile']['attribute7'] = attribute7

    if attribute7expr:
        payload['tmsamlssoprofile']['attribute7expr'] = attribute7expr

    if attribute7friendlyname:
        payload['tmsamlssoprofile']['attribute7friendlyname'] = attribute7friendlyname

    if attribute7format:
        payload['tmsamlssoprofile']['attribute7format'] = attribute7format

    if attribute8:
        payload['tmsamlssoprofile']['attribute8'] = attribute8

    if attribute8expr:
        payload['tmsamlssoprofile']['attribute8expr'] = attribute8expr

    if attribute8friendlyname:
        payload['tmsamlssoprofile']['attribute8friendlyname'] = attribute8friendlyname

    if attribute8format:
        payload['tmsamlssoprofile']['attribute8format'] = attribute8format

    if attribute9:
        payload['tmsamlssoprofile']['attribute9'] = attribute9

    if attribute9expr:
        payload['tmsamlssoprofile']['attribute9expr'] = attribute9expr

    if attribute9friendlyname:
        payload['tmsamlssoprofile']['attribute9friendlyname'] = attribute9friendlyname

    if attribute9format:
        payload['tmsamlssoprofile']['attribute9format'] = attribute9format

    if attribute10:
        payload['tmsamlssoprofile']['attribute10'] = attribute10

    if attribute10expr:
        payload['tmsamlssoprofile']['attribute10expr'] = attribute10expr

    if attribute10friendlyname:
        payload['tmsamlssoprofile']['attribute10friendlyname'] = attribute10friendlyname

    if attribute10format:
        payload['tmsamlssoprofile']['attribute10format'] = attribute10format

    if attribute11:
        payload['tmsamlssoprofile']['attribute11'] = attribute11

    if attribute11expr:
        payload['tmsamlssoprofile']['attribute11expr'] = attribute11expr

    if attribute11friendlyname:
        payload['tmsamlssoprofile']['attribute11friendlyname'] = attribute11friendlyname

    if attribute11format:
        payload['tmsamlssoprofile']['attribute11format'] = attribute11format

    if attribute12:
        payload['tmsamlssoprofile']['attribute12'] = attribute12

    if attribute12expr:
        payload['tmsamlssoprofile']['attribute12expr'] = attribute12expr

    if attribute12friendlyname:
        payload['tmsamlssoprofile']['attribute12friendlyname'] = attribute12friendlyname

    if attribute12format:
        payload['tmsamlssoprofile']['attribute12format'] = attribute12format

    if attribute13:
        payload['tmsamlssoprofile']['attribute13'] = attribute13

    if attribute13expr:
        payload['tmsamlssoprofile']['attribute13expr'] = attribute13expr

    if attribute13friendlyname:
        payload['tmsamlssoprofile']['attribute13friendlyname'] = attribute13friendlyname

    if attribute13format:
        payload['tmsamlssoprofile']['attribute13format'] = attribute13format

    if attribute14:
        payload['tmsamlssoprofile']['attribute14'] = attribute14

    if attribute14expr:
        payload['tmsamlssoprofile']['attribute14expr'] = attribute14expr

    if attribute14friendlyname:
        payload['tmsamlssoprofile']['attribute14friendlyname'] = attribute14friendlyname

    if attribute14format:
        payload['tmsamlssoprofile']['attribute14format'] = attribute14format

    if attribute15:
        payload['tmsamlssoprofile']['attribute15'] = attribute15

    if attribute15expr:
        payload['tmsamlssoprofile']['attribute15expr'] = attribute15expr

    if attribute15friendlyname:
        payload['tmsamlssoprofile']['attribute15friendlyname'] = attribute15friendlyname

    if attribute15format:
        payload['tmsamlssoprofile']['attribute15format'] = attribute15format

    if attribute16:
        payload['tmsamlssoprofile']['attribute16'] = attribute16

    if attribute16expr:
        payload['tmsamlssoprofile']['attribute16expr'] = attribute16expr

    if attribute16friendlyname:
        payload['tmsamlssoprofile']['attribute16friendlyname'] = attribute16friendlyname

    if attribute16format:
        payload['tmsamlssoprofile']['attribute16format'] = attribute16format

    if encryptassertion:
        payload['tmsamlssoprofile']['encryptassertion'] = encryptassertion

    if samlspcertname:
        payload['tmsamlssoprofile']['samlspcertname'] = samlspcertname

    if encryptionalgorithm:
        payload['tmsamlssoprofile']['encryptionalgorithm'] = encryptionalgorithm

    if skewtime:
        payload['tmsamlssoprofile']['skewtime'] = skewtime

    execution = __proxy__['citrixns.post']('config/tmsamlssoprofile', payload)

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


def add_tmsessionaction(name=None, sesstimeout=None, defaultauthorizationaction=None, sso=None, ssocredential=None,
                        ssodomain=None, httponlycookie=None, kcdaccount=None, persistentcookie=None,
                        persistentcookievalidity=None, homepage=None, save=False):
    '''
    Add a new tmsessionaction to the running configuration.

    name(str): Name for the session action. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after a session action is created.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my action" or my action). Minimum length = 1

    sesstimeout(int): Session timeout, in minutes. If there is no traffic during the timeout period, the user is disconnected
        and must reauthenticate to access intranet resources. Minimum value = 1

    defaultauthorizationaction(str): Allow or deny access to content for which there is no specific authorization policy.
        Possible values = ALLOW, DENY

    sso(str): Use single sign-on (SSO) to log users on to all web applications automatically after they authenticate, or pass
        users to the web application logon page to authenticate to each application individually. Default value: OFF
        Possible values = ON, OFF

    ssocredential(str): Use the primary or secondary authentication credentials for single sign-on (SSO). Possible values =
        PRIMARY, SECONDARY

    ssodomain(str): Domain to use for single sign-on (SSO). Minimum length = 1 Maximum length = 32

    httponlycookie(str): Allow only an HTTP session cookie, in which case the cookie cannot be accessed by scripts. Possible
        values = YES, NO

    kcdaccount(str): Kerberos constrained delegation account name. Minimum length = 1 Maximum length = 32

    persistentcookie(str): Enable or disable persistent SSO cookies for the traffic management (TM) session. A persistent
        cookie remains on the user device and is sent with each HTTP request. The cookie becomes stale if the session
        ends. This setting is overwritten if a traffic action sets persistent cookie to OFF.  Note: If persistent cookie
        is enabled, make sure you set the persistent cookie validity. Possible values = ON, OFF

    persistentcookievalidity(int): Integer specifying the number of minutes for which the persistent cookie remains valid.
        Can be set only if the persistent cookie setting is enabled. Minimum value = 1

    homepage(str): Web address of the home page that a user is displayed when authentication vserver is bookmarked and used
        to login.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmsessionaction <args>

    '''

    result = {}

    payload = {'tmsessionaction': {}}

    if name:
        payload['tmsessionaction']['name'] = name

    if sesstimeout:
        payload['tmsessionaction']['sesstimeout'] = sesstimeout

    if defaultauthorizationaction:
        payload['tmsessionaction']['defaultauthorizationaction'] = defaultauthorizationaction

    if sso:
        payload['tmsessionaction']['sso'] = sso

    if ssocredential:
        payload['tmsessionaction']['ssocredential'] = ssocredential

    if ssodomain:
        payload['tmsessionaction']['ssodomain'] = ssodomain

    if httponlycookie:
        payload['tmsessionaction']['httponlycookie'] = httponlycookie

    if kcdaccount:
        payload['tmsessionaction']['kcdaccount'] = kcdaccount

    if persistentcookie:
        payload['tmsessionaction']['persistentcookie'] = persistentcookie

    if persistentcookievalidity:
        payload['tmsessionaction']['persistentcookievalidity'] = persistentcookievalidity

    if homepage:
        payload['tmsessionaction']['homepage'] = homepage

    execution = __proxy__['citrixns.post']('config/tmsessionaction', payload)

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


def add_tmsessionpolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new tmsessionpolicy to the running configuration.

    name(str): Name for the session policy. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters. Cannot be changed after a session policy is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, against which traffic is evaluated. Both classic and advance expressions are supported in default
        partition but only advance expressions in non-default partition. Maximum length of a string literal in the
        expression is 255 characters. A longer string can be split into smaller strings of up to 255 characters each, and
        the smaller strings concatenated with the + operator. For example, you can create a 500-character string as
        follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements
        apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression
        in double quotation marks. * If the expression itself includes double quotation marks, escape the quotations by
        using the \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case
        you do not have to escape the double quotation marks.

    action(str): Action to be applied to connections that match this policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmsessionpolicy <args>

    '''

    result = {}

    payload = {'tmsessionpolicy': {}}

    if name:
        payload['tmsessionpolicy']['name'] = name

    if rule:
        payload['tmsessionpolicy']['rule'] = rule

    if action:
        payload['tmsessionpolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/tmsessionpolicy', payload)

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


def add_tmtrafficaction(name=None, apptimeout=None, sso=None, formssoaction=None, persistentcookie=None,
                        initiatelogout=None, kcdaccount=None, samlssoprofile=None, forcedtimeout=None,
                        forcedtimeoutval=None, userexpression=None, passwdexpression=None, save=False):
    '''
    Add a new tmtrafficaction to the running configuration.

    name(str): Name for the traffic action. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after a traffic action is created.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my action" or my action). Minimum length = 1

    apptimeout(int): Time interval, in minutes, of user inactivity after which the connection is closed. Minimum value = 1
        Maximum value = 715827

    sso(str): Use single sign-on for the resource that the user is accessing now. Possible values = ON, OFF

    formssoaction(str): Name of the configured form-based single sign-on profile.

    persistentcookie(str): Use persistent cookies for the traffic session. A persistent cookie remains on the user device and
        is sent with each HTTP request. The cookie becomes stale if the session ends. Possible values = ON, OFF

    initiatelogout(str): Initiate logout for the traffic management (TM) session if the policy evaluates to true. The session
        is then terminated after two minutes. Possible values = ON, OFF

    kcdaccount(str): Kerberos constrained delegation account name. Default value: "None" Minimum length = 1 Maximum length =
        32

    samlssoprofile(str): Profile to be used for doing SAML SSO to remote relying party. Minimum length = 1

    forcedtimeout(str): Setting to start, stop or reset TM session force timer. Possible values = START, STOP, RESET

    forcedtimeoutval(int): Time interval, in minutes, for which force timer should be set.

    userexpression(str): expression that will be evaluated to obtain username for SingleSignOn. Maximum length = 256

    passwdexpression(str): expression that will be evaluated to obtain password for SingleSignOn. Maximum length = 256

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmtrafficaction <args>

    '''

    result = {}

    payload = {'tmtrafficaction': {}}

    if name:
        payload['tmtrafficaction']['name'] = name

    if apptimeout:
        payload['tmtrafficaction']['apptimeout'] = apptimeout

    if sso:
        payload['tmtrafficaction']['sso'] = sso

    if formssoaction:
        payload['tmtrafficaction']['formssoaction'] = formssoaction

    if persistentcookie:
        payload['tmtrafficaction']['persistentcookie'] = persistentcookie

    if initiatelogout:
        payload['tmtrafficaction']['initiatelogout'] = initiatelogout

    if kcdaccount:
        payload['tmtrafficaction']['kcdaccount'] = kcdaccount

    if samlssoprofile:
        payload['tmtrafficaction']['samlssoprofile'] = samlssoprofile

    if forcedtimeout:
        payload['tmtrafficaction']['forcedtimeout'] = forcedtimeout

    if forcedtimeoutval:
        payload['tmtrafficaction']['forcedtimeoutval'] = forcedtimeoutval

    if userexpression:
        payload['tmtrafficaction']['userexpression'] = userexpression

    if passwdexpression:
        payload['tmtrafficaction']['passwdexpression'] = passwdexpression

    execution = __proxy__['citrixns.post']('config/tmtrafficaction', payload)

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


def add_tmtrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new tmtrafficpolicy to the running configuration.

    name(str): Name for the traffic policy. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, against which traffic is evaluated. Written in the classic syntax. Maximum length of a string
        literal in the expression is 255 characters. A longer string can be split into smaller strings of up to 255
        characters each, and the smaller strings concatenated with the + operator. For example, you can create a
        500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The
        following requirements apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose
        the entire expression in double quotation marks. * If the expression itself includes double quotation marks,
        escape the quotations by using the \\ character.  * Alternatively, you can use single quotation marks to enclose
        the rule, in which case you do not have to escape the double quotation marks.

    action(str): Name of the action to apply to requests or connections that match this policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.add_tmtrafficpolicy <args>

    '''

    result = {}

    payload = {'tmtrafficpolicy': {}}

    if name:
        payload['tmtrafficpolicy']['name'] = name

    if rule:
        payload['tmtrafficpolicy']['rule'] = rule

    if action:
        payload['tmtrafficpolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/tmtrafficpolicy', payload)

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


def get_tmformssoaction(name=None, actionurl=None, userfield=None, passwdfield=None, ssosuccessrule=None,
                        namevaluepair=None, responsesize=None, nvtype=None, submitmethod=None):
    '''
    Show the running configuration for the tmformssoaction config key.

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

    salt '*' traffic_management.get_tmformssoaction

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
            __proxy__['citrixns.get']('config/tmformssoaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmformssoaction')

    return response


def get_tmglobal_auditnslogpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None):
    '''
    Show the running configuration for the tmglobal_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmglobal_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmglobal_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmglobal_auditnslogpolicy_binding')

    return response


def get_tmglobal_auditsyslogpolicy_binding(priority=None, policyname=None, gotopriorityexpression=None):
    '''
    Show the running configuration for the tmglobal_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmglobal_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmglobal_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmglobal_auditsyslogpolicy_binding')

    return response


def get_tmglobal_binding():
    '''
    Show the running configuration for the tmglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmglobal_binding'), 'tmglobal_binding')

    return response


def get_tmglobal_tmsessionpolicy_binding(priority=None, builtin=None, policyname=None, gotopriorityexpression=None):
    '''
    Show the running configuration for the tmglobal_tmsessionpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmglobal_tmsessionpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmglobal_tmsessionpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmglobal_tmsessionpolicy_binding')

    return response


def get_tmglobal_tmtrafficpolicy_binding(priority=None, globalbindtype=None, policyname=None,
                                         gotopriorityexpression=None, ns_type=None):
    '''
    Show the running configuration for the tmglobal_tmtrafficpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmglobal_tmtrafficpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if ns_type:
        search_filter.append(['type', ns_type])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmglobal_tmtrafficpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmglobal_tmtrafficpolicy_binding')

    return response


def get_tmsamlssoprofile(name=None, samlsigningcertname=None, assertionconsumerserviceurl=None, relaystaterule=None,
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
    Show the running configuration for the tmsamlssoprofile config key.

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

    salt '*' traffic_management.get_tmsamlssoprofile

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
            __proxy__['citrixns.get']('config/tmsamlssoprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmsamlssoprofile')

    return response


def get_tmsessionaction(name=None, sesstimeout=None, defaultauthorizationaction=None, sso=None, ssocredential=None,
                        ssodomain=None, httponlycookie=None, kcdaccount=None, persistentcookie=None,
                        persistentcookievalidity=None, homepage=None):
    '''
    Show the running configuration for the tmsessionaction config key.

    name(str): Filters results that only match the name field.

    sesstimeout(int): Filters results that only match the sesstimeout field.

    defaultauthorizationaction(str): Filters results that only match the defaultauthorizationaction field.

    sso(str): Filters results that only match the sso field.

    ssocredential(str): Filters results that only match the ssocredential field.

    ssodomain(str): Filters results that only match the ssodomain field.

    httponlycookie(str): Filters results that only match the httponlycookie field.

    kcdaccount(str): Filters results that only match the kcdaccount field.

    persistentcookie(str): Filters results that only match the persistentcookie field.

    persistentcookievalidity(int): Filters results that only match the persistentcookievalidity field.

    homepage(str): Filters results that only match the homepage field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmsessionaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if sesstimeout:
        search_filter.append(['sesstimeout', sesstimeout])

    if defaultauthorizationaction:
        search_filter.append(['defaultauthorizationaction', defaultauthorizationaction])

    if sso:
        search_filter.append(['sso', sso])

    if ssocredential:
        search_filter.append(['ssocredential', ssocredential])

    if ssodomain:
        search_filter.append(['ssodomain', ssodomain])

    if httponlycookie:
        search_filter.append(['httponlycookie', httponlycookie])

    if kcdaccount:
        search_filter.append(['kcdaccount', kcdaccount])

    if persistentcookie:
        search_filter.append(['persistentcookie', persistentcookie])

    if persistentcookievalidity:
        search_filter.append(['persistentcookievalidity', persistentcookievalidity])

    if homepage:
        search_filter.append(['homepage', homepage])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmsessionaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmsessionaction')

    return response


def get_tmsessionparameter():
    '''
    Show the running configuration for the tmsessionparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmsessionparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmsessionparameter'), 'tmsessionparameter')

    return response


def get_tmsessionpolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the tmsessionpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmsessionpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmsessionpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmsessionpolicy')

    return response


def get_tmsessionpolicy_aaagroup_binding(boundto=None, name=None):
    '''
    Show the running configuration for the tmsessionpolicy_aaagroup_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmsessionpolicy_aaagroup_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmsessionpolicy_aaagroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmsessionpolicy_aaagroup_binding')

    return response


def get_tmsessionpolicy_aaauser_binding(boundto=None, name=None):
    '''
    Show the running configuration for the tmsessionpolicy_aaauser_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmsessionpolicy_aaauser_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmsessionpolicy_aaauser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmsessionpolicy_aaauser_binding')

    return response


def get_tmsessionpolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the tmsessionpolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmsessionpolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmsessionpolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmsessionpolicy_authenticationvserver_binding')

    return response


def get_tmsessionpolicy_binding():
    '''
    Show the running configuration for the tmsessionpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmsessionpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmsessionpolicy_binding'), 'tmsessionpolicy_binding')

    return response


def get_tmsessionpolicy_tmglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the tmsessionpolicy_tmglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmsessionpolicy_tmglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmsessionpolicy_tmglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmsessionpolicy_tmglobal_binding')

    return response


def get_tmtrafficaction(name=None, apptimeout=None, sso=None, formssoaction=None, persistentcookie=None,
                        initiatelogout=None, kcdaccount=None, samlssoprofile=None, forcedtimeout=None,
                        forcedtimeoutval=None, userexpression=None, passwdexpression=None):
    '''
    Show the running configuration for the tmtrafficaction config key.

    name(str): Filters results that only match the name field.

    apptimeout(int): Filters results that only match the apptimeout field.

    sso(str): Filters results that only match the sso field.

    formssoaction(str): Filters results that only match the formssoaction field.

    persistentcookie(str): Filters results that only match the persistentcookie field.

    initiatelogout(str): Filters results that only match the initiatelogout field.

    kcdaccount(str): Filters results that only match the kcdaccount field.

    samlssoprofile(str): Filters results that only match the samlssoprofile field.

    forcedtimeout(str): Filters results that only match the forcedtimeout field.

    forcedtimeoutval(int): Filters results that only match the forcedtimeoutval field.

    userexpression(str): Filters results that only match the userexpression field.

    passwdexpression(str): Filters results that only match the passwdexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmtrafficaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if apptimeout:
        search_filter.append(['apptimeout', apptimeout])

    if sso:
        search_filter.append(['sso', sso])

    if formssoaction:
        search_filter.append(['formssoaction', formssoaction])

    if persistentcookie:
        search_filter.append(['persistentcookie', persistentcookie])

    if initiatelogout:
        search_filter.append(['initiatelogout', initiatelogout])

    if kcdaccount:
        search_filter.append(['kcdaccount', kcdaccount])

    if samlssoprofile:
        search_filter.append(['samlssoprofile', samlssoprofile])

    if forcedtimeout:
        search_filter.append(['forcedtimeout', forcedtimeout])

    if forcedtimeoutval:
        search_filter.append(['forcedtimeoutval', forcedtimeoutval])

    if userexpression:
        search_filter.append(['userexpression', userexpression])

    if passwdexpression:
        search_filter.append(['passwdexpression', passwdexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmtrafficaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmtrafficaction')

    return response


def get_tmtrafficpolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the tmtrafficpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmtrafficpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmtrafficpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmtrafficpolicy')

    return response


def get_tmtrafficpolicy_binding():
    '''
    Show the running configuration for the tmtrafficpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmtrafficpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmtrafficpolicy_binding'), 'tmtrafficpolicy_binding')

    return response


def get_tmtrafficpolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the tmtrafficpolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmtrafficpolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmtrafficpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmtrafficpolicy_csvserver_binding')

    return response


def get_tmtrafficpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the tmtrafficpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmtrafficpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmtrafficpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmtrafficpolicy_lbvserver_binding')

    return response


def get_tmtrafficpolicy_tmglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the tmtrafficpolicy_tmglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.get_tmtrafficpolicy_tmglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tmtrafficpolicy_tmglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tmtrafficpolicy_tmglobal_binding')

    return response


def unset_tmformssoaction(name=None, actionurl=None, userfield=None, passwdfield=None, ssosuccessrule=None,
                          namevaluepair=None, responsesize=None, nvtype=None, submitmethod=None, save=False):
    '''
    Unsets values from the tmformssoaction configuration key.

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

    salt '*' traffic_management.unset_tmformssoaction <args>

    '''

    result = {}

    payload = {'tmformssoaction': {}}

    if name:
        payload['tmformssoaction']['name'] = True

    if actionurl:
        payload['tmformssoaction']['actionurl'] = True

    if userfield:
        payload['tmformssoaction']['userfield'] = True

    if passwdfield:
        payload['tmformssoaction']['passwdfield'] = True

    if ssosuccessrule:
        payload['tmformssoaction']['ssosuccessrule'] = True

    if namevaluepair:
        payload['tmformssoaction']['namevaluepair'] = True

    if responsesize:
        payload['tmformssoaction']['responsesize'] = True

    if nvtype:
        payload['tmformssoaction']['nvtype'] = True

    if submitmethod:
        payload['tmformssoaction']['submitmethod'] = True

    execution = __proxy__['citrixns.post']('config/tmformssoaction?action=unset', payload)

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


def unset_tmsamlssoprofile(name=None, samlsigningcertname=None, assertionconsumerserviceurl=None, relaystaterule=None,
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
    Unsets values from the tmsamlssoprofile configuration key.

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

    salt '*' traffic_management.unset_tmsamlssoprofile <args>

    '''

    result = {}

    payload = {'tmsamlssoprofile': {}}

    if name:
        payload['tmsamlssoprofile']['name'] = True

    if samlsigningcertname:
        payload['tmsamlssoprofile']['samlsigningcertname'] = True

    if assertionconsumerserviceurl:
        payload['tmsamlssoprofile']['assertionconsumerserviceurl'] = True

    if relaystaterule:
        payload['tmsamlssoprofile']['relaystaterule'] = True

    if sendpassword:
        payload['tmsamlssoprofile']['sendpassword'] = True

    if samlissuername:
        payload['tmsamlssoprofile']['samlissuername'] = True

    if signaturealg:
        payload['tmsamlssoprofile']['signaturealg'] = True

    if digestmethod:
        payload['tmsamlssoprofile']['digestmethod'] = True

    if audience:
        payload['tmsamlssoprofile']['audience'] = True

    if nameidformat:
        payload['tmsamlssoprofile']['nameidformat'] = True

    if nameidexpr:
        payload['tmsamlssoprofile']['nameidexpr'] = True

    if attribute1:
        payload['tmsamlssoprofile']['attribute1'] = True

    if attribute1expr:
        payload['tmsamlssoprofile']['attribute1expr'] = True

    if attribute1friendlyname:
        payload['tmsamlssoprofile']['attribute1friendlyname'] = True

    if attribute1format:
        payload['tmsamlssoprofile']['attribute1format'] = True

    if attribute2:
        payload['tmsamlssoprofile']['attribute2'] = True

    if attribute2expr:
        payload['tmsamlssoprofile']['attribute2expr'] = True

    if attribute2friendlyname:
        payload['tmsamlssoprofile']['attribute2friendlyname'] = True

    if attribute2format:
        payload['tmsamlssoprofile']['attribute2format'] = True

    if attribute3:
        payload['tmsamlssoprofile']['attribute3'] = True

    if attribute3expr:
        payload['tmsamlssoprofile']['attribute3expr'] = True

    if attribute3friendlyname:
        payload['tmsamlssoprofile']['attribute3friendlyname'] = True

    if attribute3format:
        payload['tmsamlssoprofile']['attribute3format'] = True

    if attribute4:
        payload['tmsamlssoprofile']['attribute4'] = True

    if attribute4expr:
        payload['tmsamlssoprofile']['attribute4expr'] = True

    if attribute4friendlyname:
        payload['tmsamlssoprofile']['attribute4friendlyname'] = True

    if attribute4format:
        payload['tmsamlssoprofile']['attribute4format'] = True

    if attribute5:
        payload['tmsamlssoprofile']['attribute5'] = True

    if attribute5expr:
        payload['tmsamlssoprofile']['attribute5expr'] = True

    if attribute5friendlyname:
        payload['tmsamlssoprofile']['attribute5friendlyname'] = True

    if attribute5format:
        payload['tmsamlssoprofile']['attribute5format'] = True

    if attribute6:
        payload['tmsamlssoprofile']['attribute6'] = True

    if attribute6expr:
        payload['tmsamlssoprofile']['attribute6expr'] = True

    if attribute6friendlyname:
        payload['tmsamlssoprofile']['attribute6friendlyname'] = True

    if attribute6format:
        payload['tmsamlssoprofile']['attribute6format'] = True

    if attribute7:
        payload['tmsamlssoprofile']['attribute7'] = True

    if attribute7expr:
        payload['tmsamlssoprofile']['attribute7expr'] = True

    if attribute7friendlyname:
        payload['tmsamlssoprofile']['attribute7friendlyname'] = True

    if attribute7format:
        payload['tmsamlssoprofile']['attribute7format'] = True

    if attribute8:
        payload['tmsamlssoprofile']['attribute8'] = True

    if attribute8expr:
        payload['tmsamlssoprofile']['attribute8expr'] = True

    if attribute8friendlyname:
        payload['tmsamlssoprofile']['attribute8friendlyname'] = True

    if attribute8format:
        payload['tmsamlssoprofile']['attribute8format'] = True

    if attribute9:
        payload['tmsamlssoprofile']['attribute9'] = True

    if attribute9expr:
        payload['tmsamlssoprofile']['attribute9expr'] = True

    if attribute9friendlyname:
        payload['tmsamlssoprofile']['attribute9friendlyname'] = True

    if attribute9format:
        payload['tmsamlssoprofile']['attribute9format'] = True

    if attribute10:
        payload['tmsamlssoprofile']['attribute10'] = True

    if attribute10expr:
        payload['tmsamlssoprofile']['attribute10expr'] = True

    if attribute10friendlyname:
        payload['tmsamlssoprofile']['attribute10friendlyname'] = True

    if attribute10format:
        payload['tmsamlssoprofile']['attribute10format'] = True

    if attribute11:
        payload['tmsamlssoprofile']['attribute11'] = True

    if attribute11expr:
        payload['tmsamlssoprofile']['attribute11expr'] = True

    if attribute11friendlyname:
        payload['tmsamlssoprofile']['attribute11friendlyname'] = True

    if attribute11format:
        payload['tmsamlssoprofile']['attribute11format'] = True

    if attribute12:
        payload['tmsamlssoprofile']['attribute12'] = True

    if attribute12expr:
        payload['tmsamlssoprofile']['attribute12expr'] = True

    if attribute12friendlyname:
        payload['tmsamlssoprofile']['attribute12friendlyname'] = True

    if attribute12format:
        payload['tmsamlssoprofile']['attribute12format'] = True

    if attribute13:
        payload['tmsamlssoprofile']['attribute13'] = True

    if attribute13expr:
        payload['tmsamlssoprofile']['attribute13expr'] = True

    if attribute13friendlyname:
        payload['tmsamlssoprofile']['attribute13friendlyname'] = True

    if attribute13format:
        payload['tmsamlssoprofile']['attribute13format'] = True

    if attribute14:
        payload['tmsamlssoprofile']['attribute14'] = True

    if attribute14expr:
        payload['tmsamlssoprofile']['attribute14expr'] = True

    if attribute14friendlyname:
        payload['tmsamlssoprofile']['attribute14friendlyname'] = True

    if attribute14format:
        payload['tmsamlssoprofile']['attribute14format'] = True

    if attribute15:
        payload['tmsamlssoprofile']['attribute15'] = True

    if attribute15expr:
        payload['tmsamlssoprofile']['attribute15expr'] = True

    if attribute15friendlyname:
        payload['tmsamlssoprofile']['attribute15friendlyname'] = True

    if attribute15format:
        payload['tmsamlssoprofile']['attribute15format'] = True

    if attribute16:
        payload['tmsamlssoprofile']['attribute16'] = True

    if attribute16expr:
        payload['tmsamlssoprofile']['attribute16expr'] = True

    if attribute16friendlyname:
        payload['tmsamlssoprofile']['attribute16friendlyname'] = True

    if attribute16format:
        payload['tmsamlssoprofile']['attribute16format'] = True

    if encryptassertion:
        payload['tmsamlssoprofile']['encryptassertion'] = True

    if samlspcertname:
        payload['tmsamlssoprofile']['samlspcertname'] = True

    if encryptionalgorithm:
        payload['tmsamlssoprofile']['encryptionalgorithm'] = True

    if skewtime:
        payload['tmsamlssoprofile']['skewtime'] = True

    execution = __proxy__['citrixns.post']('config/tmsamlssoprofile?action=unset', payload)

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


def unset_tmsessionaction(name=None, sesstimeout=None, defaultauthorizationaction=None, sso=None, ssocredential=None,
                          ssodomain=None, httponlycookie=None, kcdaccount=None, persistentcookie=None,
                          persistentcookievalidity=None, homepage=None, save=False):
    '''
    Unsets values from the tmsessionaction configuration key.

    name(bool): Unsets the name value.

    sesstimeout(bool): Unsets the sesstimeout value.

    defaultauthorizationaction(bool): Unsets the defaultauthorizationaction value.

    sso(bool): Unsets the sso value.

    ssocredential(bool): Unsets the ssocredential value.

    ssodomain(bool): Unsets the ssodomain value.

    httponlycookie(bool): Unsets the httponlycookie value.

    kcdaccount(bool): Unsets the kcdaccount value.

    persistentcookie(bool): Unsets the persistentcookie value.

    persistentcookievalidity(bool): Unsets the persistentcookievalidity value.

    homepage(bool): Unsets the homepage value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.unset_tmsessionaction <args>

    '''

    result = {}

    payload = {'tmsessionaction': {}}

    if name:
        payload['tmsessionaction']['name'] = True

    if sesstimeout:
        payload['tmsessionaction']['sesstimeout'] = True

    if defaultauthorizationaction:
        payload['tmsessionaction']['defaultauthorizationaction'] = True

    if sso:
        payload['tmsessionaction']['sso'] = True

    if ssocredential:
        payload['tmsessionaction']['ssocredential'] = True

    if ssodomain:
        payload['tmsessionaction']['ssodomain'] = True

    if httponlycookie:
        payload['tmsessionaction']['httponlycookie'] = True

    if kcdaccount:
        payload['tmsessionaction']['kcdaccount'] = True

    if persistentcookie:
        payload['tmsessionaction']['persistentcookie'] = True

    if persistentcookievalidity:
        payload['tmsessionaction']['persistentcookievalidity'] = True

    if homepage:
        payload['tmsessionaction']['homepage'] = True

    execution = __proxy__['citrixns.post']('config/tmsessionaction?action=unset', payload)

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


def unset_tmsessionparameter(sesstimeout=None, defaultauthorizationaction=None, sso=None, ssocredential=None,
                             ssodomain=None, kcdaccount=None, httponlycookie=None, persistentcookie=None,
                             persistentcookievalidity=None, homepage=None, save=False):
    '''
    Unsets values from the tmsessionparameter configuration key.

    sesstimeout(bool): Unsets the sesstimeout value.

    defaultauthorizationaction(bool): Unsets the defaultauthorizationaction value.

    sso(bool): Unsets the sso value.

    ssocredential(bool): Unsets the ssocredential value.

    ssodomain(bool): Unsets the ssodomain value.

    kcdaccount(bool): Unsets the kcdaccount value.

    httponlycookie(bool): Unsets the httponlycookie value.

    persistentcookie(bool): Unsets the persistentcookie value.

    persistentcookievalidity(bool): Unsets the persistentcookievalidity value.

    homepage(bool): Unsets the homepage value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.unset_tmsessionparameter <args>

    '''

    result = {}

    payload = {'tmsessionparameter': {}}

    if sesstimeout:
        payload['tmsessionparameter']['sesstimeout'] = True

    if defaultauthorizationaction:
        payload['tmsessionparameter']['defaultauthorizationaction'] = True

    if sso:
        payload['tmsessionparameter']['sso'] = True

    if ssocredential:
        payload['tmsessionparameter']['ssocredential'] = True

    if ssodomain:
        payload['tmsessionparameter']['ssodomain'] = True

    if kcdaccount:
        payload['tmsessionparameter']['kcdaccount'] = True

    if httponlycookie:
        payload['tmsessionparameter']['httponlycookie'] = True

    if persistentcookie:
        payload['tmsessionparameter']['persistentcookie'] = True

    if persistentcookievalidity:
        payload['tmsessionparameter']['persistentcookievalidity'] = True

    if homepage:
        payload['tmsessionparameter']['homepage'] = True

    execution = __proxy__['citrixns.post']('config/tmsessionparameter?action=unset', payload)

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


def unset_tmsessionpolicy(name=None, rule=None, action=None, save=False):
    '''
    Unsets values from the tmsessionpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.unset_tmsessionpolicy <args>

    '''

    result = {}

    payload = {'tmsessionpolicy': {}}

    if name:
        payload['tmsessionpolicy']['name'] = True

    if rule:
        payload['tmsessionpolicy']['rule'] = True

    if action:
        payload['tmsessionpolicy']['action'] = True

    execution = __proxy__['citrixns.post']('config/tmsessionpolicy?action=unset', payload)

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


def unset_tmtrafficaction(name=None, apptimeout=None, sso=None, formssoaction=None, persistentcookie=None,
                          initiatelogout=None, kcdaccount=None, samlssoprofile=None, forcedtimeout=None,
                          forcedtimeoutval=None, userexpression=None, passwdexpression=None, save=False):
    '''
    Unsets values from the tmtrafficaction configuration key.

    name(bool): Unsets the name value.

    apptimeout(bool): Unsets the apptimeout value.

    sso(bool): Unsets the sso value.

    formssoaction(bool): Unsets the formssoaction value.

    persistentcookie(bool): Unsets the persistentcookie value.

    initiatelogout(bool): Unsets the initiatelogout value.

    kcdaccount(bool): Unsets the kcdaccount value.

    samlssoprofile(bool): Unsets the samlssoprofile value.

    forcedtimeout(bool): Unsets the forcedtimeout value.

    forcedtimeoutval(bool): Unsets the forcedtimeoutval value.

    userexpression(bool): Unsets the userexpression value.

    passwdexpression(bool): Unsets the passwdexpression value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.unset_tmtrafficaction <args>

    '''

    result = {}

    payload = {'tmtrafficaction': {}}

    if name:
        payload['tmtrafficaction']['name'] = True

    if apptimeout:
        payload['tmtrafficaction']['apptimeout'] = True

    if sso:
        payload['tmtrafficaction']['sso'] = True

    if formssoaction:
        payload['tmtrafficaction']['formssoaction'] = True

    if persistentcookie:
        payload['tmtrafficaction']['persistentcookie'] = True

    if initiatelogout:
        payload['tmtrafficaction']['initiatelogout'] = True

    if kcdaccount:
        payload['tmtrafficaction']['kcdaccount'] = True

    if samlssoprofile:
        payload['tmtrafficaction']['samlssoprofile'] = True

    if forcedtimeout:
        payload['tmtrafficaction']['forcedtimeout'] = True

    if forcedtimeoutval:
        payload['tmtrafficaction']['forcedtimeoutval'] = True

    if userexpression:
        payload['tmtrafficaction']['userexpression'] = True

    if passwdexpression:
        payload['tmtrafficaction']['passwdexpression'] = True

    execution = __proxy__['citrixns.post']('config/tmtrafficaction?action=unset', payload)

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


def unset_tmtrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Unsets values from the tmtrafficpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.unset_tmtrafficpolicy <args>

    '''

    result = {}

    payload = {'tmtrafficpolicy': {}}

    if name:
        payload['tmtrafficpolicy']['name'] = True

    if rule:
        payload['tmtrafficpolicy']['rule'] = True

    if action:
        payload['tmtrafficpolicy']['action'] = True

    execution = __proxy__['citrixns.post']('config/tmtrafficpolicy?action=unset', payload)

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


def update_tmformssoaction(name=None, actionurl=None, userfield=None, passwdfield=None, ssosuccessrule=None,
                           namevaluepair=None, responsesize=None, nvtype=None, submitmethod=None, save=False):
    '''
    Update the running configuration for the tmformssoaction config key.

    name(str): Name for the new form-based single sign-on profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an SSO action is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    actionurl(str): URL to which the completed form is submitted. Minimum length = 1

    userfield(str): Name of the form field in which the user types in the user ID. Minimum length = 1

    passwdfield(str): Name of the form field in which the user types in the password. Minimum length = 1

    ssosuccessrule(str): Expression, that checks to see if single sign-on is successful.

    namevaluepair(str): Name-value pair attributes to send to the server in addition to sending the username and password.
        Value names are separated by an ampersand (;amp;) (for example, name1=value1;amp;name2=value2).

    responsesize(int): Number of bytes, in the response, to parse for extracting the forms. Default value: 8096

    nvtype(str): Type of processing of the name-value pair. If you specify STATIC, the values configured by the administrator
        are used. For DYNAMIC, the response is parsed, and the form is extracted and then submitted. Default value:
        DYNAMIC Possible values = STATIC, DYNAMIC

    submitmethod(str): HTTP method used by the single sign-on form to send the logon credentials to the logon server. Applies
        only to STATIC name-value type. Default value: GET Possible values = GET, POST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.update_tmformssoaction <args>

    '''

    result = {}

    payload = {'tmformssoaction': {}}

    if name:
        payload['tmformssoaction']['name'] = name

    if actionurl:
        payload['tmformssoaction']['actionurl'] = actionurl

    if userfield:
        payload['tmformssoaction']['userfield'] = userfield

    if passwdfield:
        payload['tmformssoaction']['passwdfield'] = passwdfield

    if ssosuccessrule:
        payload['tmformssoaction']['ssosuccessrule'] = ssosuccessrule

    if namevaluepair:
        payload['tmformssoaction']['namevaluepair'] = namevaluepair

    if responsesize:
        payload['tmformssoaction']['responsesize'] = responsesize

    if nvtype:
        payload['tmformssoaction']['nvtype'] = nvtype

    if submitmethod:
        payload['tmformssoaction']['submitmethod'] = submitmethod

    execution = __proxy__['citrixns.put']('config/tmformssoaction', payload)

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


def update_tmsamlssoprofile(name=None, samlsigningcertname=None, assertionconsumerserviceurl=None, relaystaterule=None,
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
    Update the running configuration for the tmsamlssoprofile config key.

    name(str): Name for the new saml single sign-on profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an SSO action is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    samlsigningcertname(str): Name of the SSL certificate that is used to Sign Assertion. Minimum length = 1

    assertionconsumerserviceurl(str): URL to which the assertion is to be sent. Minimum length = 1

    relaystaterule(str): Expression to extract relaystate to be sent along with assertion. Evaluation of this expression
        should return TEXT content. This is typically a targ et url to which user is redirected after the recipient
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

    salt '*' traffic_management.update_tmsamlssoprofile <args>

    '''

    result = {}

    payload = {'tmsamlssoprofile': {}}

    if name:
        payload['tmsamlssoprofile']['name'] = name

    if samlsigningcertname:
        payload['tmsamlssoprofile']['samlsigningcertname'] = samlsigningcertname

    if assertionconsumerserviceurl:
        payload['tmsamlssoprofile']['assertionconsumerserviceurl'] = assertionconsumerserviceurl

    if relaystaterule:
        payload['tmsamlssoprofile']['relaystaterule'] = relaystaterule

    if sendpassword:
        payload['tmsamlssoprofile']['sendpassword'] = sendpassword

    if samlissuername:
        payload['tmsamlssoprofile']['samlissuername'] = samlissuername

    if signaturealg:
        payload['tmsamlssoprofile']['signaturealg'] = signaturealg

    if digestmethod:
        payload['tmsamlssoprofile']['digestmethod'] = digestmethod

    if audience:
        payload['tmsamlssoprofile']['audience'] = audience

    if nameidformat:
        payload['tmsamlssoprofile']['nameidformat'] = nameidformat

    if nameidexpr:
        payload['tmsamlssoprofile']['nameidexpr'] = nameidexpr

    if attribute1:
        payload['tmsamlssoprofile']['attribute1'] = attribute1

    if attribute1expr:
        payload['tmsamlssoprofile']['attribute1expr'] = attribute1expr

    if attribute1friendlyname:
        payload['tmsamlssoprofile']['attribute1friendlyname'] = attribute1friendlyname

    if attribute1format:
        payload['tmsamlssoprofile']['attribute1format'] = attribute1format

    if attribute2:
        payload['tmsamlssoprofile']['attribute2'] = attribute2

    if attribute2expr:
        payload['tmsamlssoprofile']['attribute2expr'] = attribute2expr

    if attribute2friendlyname:
        payload['tmsamlssoprofile']['attribute2friendlyname'] = attribute2friendlyname

    if attribute2format:
        payload['tmsamlssoprofile']['attribute2format'] = attribute2format

    if attribute3:
        payload['tmsamlssoprofile']['attribute3'] = attribute3

    if attribute3expr:
        payload['tmsamlssoprofile']['attribute3expr'] = attribute3expr

    if attribute3friendlyname:
        payload['tmsamlssoprofile']['attribute3friendlyname'] = attribute3friendlyname

    if attribute3format:
        payload['tmsamlssoprofile']['attribute3format'] = attribute3format

    if attribute4:
        payload['tmsamlssoprofile']['attribute4'] = attribute4

    if attribute4expr:
        payload['tmsamlssoprofile']['attribute4expr'] = attribute4expr

    if attribute4friendlyname:
        payload['tmsamlssoprofile']['attribute4friendlyname'] = attribute4friendlyname

    if attribute4format:
        payload['tmsamlssoprofile']['attribute4format'] = attribute4format

    if attribute5:
        payload['tmsamlssoprofile']['attribute5'] = attribute5

    if attribute5expr:
        payload['tmsamlssoprofile']['attribute5expr'] = attribute5expr

    if attribute5friendlyname:
        payload['tmsamlssoprofile']['attribute5friendlyname'] = attribute5friendlyname

    if attribute5format:
        payload['tmsamlssoprofile']['attribute5format'] = attribute5format

    if attribute6:
        payload['tmsamlssoprofile']['attribute6'] = attribute6

    if attribute6expr:
        payload['tmsamlssoprofile']['attribute6expr'] = attribute6expr

    if attribute6friendlyname:
        payload['tmsamlssoprofile']['attribute6friendlyname'] = attribute6friendlyname

    if attribute6format:
        payload['tmsamlssoprofile']['attribute6format'] = attribute6format

    if attribute7:
        payload['tmsamlssoprofile']['attribute7'] = attribute7

    if attribute7expr:
        payload['tmsamlssoprofile']['attribute7expr'] = attribute7expr

    if attribute7friendlyname:
        payload['tmsamlssoprofile']['attribute7friendlyname'] = attribute7friendlyname

    if attribute7format:
        payload['tmsamlssoprofile']['attribute7format'] = attribute7format

    if attribute8:
        payload['tmsamlssoprofile']['attribute8'] = attribute8

    if attribute8expr:
        payload['tmsamlssoprofile']['attribute8expr'] = attribute8expr

    if attribute8friendlyname:
        payload['tmsamlssoprofile']['attribute8friendlyname'] = attribute8friendlyname

    if attribute8format:
        payload['tmsamlssoprofile']['attribute8format'] = attribute8format

    if attribute9:
        payload['tmsamlssoprofile']['attribute9'] = attribute9

    if attribute9expr:
        payload['tmsamlssoprofile']['attribute9expr'] = attribute9expr

    if attribute9friendlyname:
        payload['tmsamlssoprofile']['attribute9friendlyname'] = attribute9friendlyname

    if attribute9format:
        payload['tmsamlssoprofile']['attribute9format'] = attribute9format

    if attribute10:
        payload['tmsamlssoprofile']['attribute10'] = attribute10

    if attribute10expr:
        payload['tmsamlssoprofile']['attribute10expr'] = attribute10expr

    if attribute10friendlyname:
        payload['tmsamlssoprofile']['attribute10friendlyname'] = attribute10friendlyname

    if attribute10format:
        payload['tmsamlssoprofile']['attribute10format'] = attribute10format

    if attribute11:
        payload['tmsamlssoprofile']['attribute11'] = attribute11

    if attribute11expr:
        payload['tmsamlssoprofile']['attribute11expr'] = attribute11expr

    if attribute11friendlyname:
        payload['tmsamlssoprofile']['attribute11friendlyname'] = attribute11friendlyname

    if attribute11format:
        payload['tmsamlssoprofile']['attribute11format'] = attribute11format

    if attribute12:
        payload['tmsamlssoprofile']['attribute12'] = attribute12

    if attribute12expr:
        payload['tmsamlssoprofile']['attribute12expr'] = attribute12expr

    if attribute12friendlyname:
        payload['tmsamlssoprofile']['attribute12friendlyname'] = attribute12friendlyname

    if attribute12format:
        payload['tmsamlssoprofile']['attribute12format'] = attribute12format

    if attribute13:
        payload['tmsamlssoprofile']['attribute13'] = attribute13

    if attribute13expr:
        payload['tmsamlssoprofile']['attribute13expr'] = attribute13expr

    if attribute13friendlyname:
        payload['tmsamlssoprofile']['attribute13friendlyname'] = attribute13friendlyname

    if attribute13format:
        payload['tmsamlssoprofile']['attribute13format'] = attribute13format

    if attribute14:
        payload['tmsamlssoprofile']['attribute14'] = attribute14

    if attribute14expr:
        payload['tmsamlssoprofile']['attribute14expr'] = attribute14expr

    if attribute14friendlyname:
        payload['tmsamlssoprofile']['attribute14friendlyname'] = attribute14friendlyname

    if attribute14format:
        payload['tmsamlssoprofile']['attribute14format'] = attribute14format

    if attribute15:
        payload['tmsamlssoprofile']['attribute15'] = attribute15

    if attribute15expr:
        payload['tmsamlssoprofile']['attribute15expr'] = attribute15expr

    if attribute15friendlyname:
        payload['tmsamlssoprofile']['attribute15friendlyname'] = attribute15friendlyname

    if attribute15format:
        payload['tmsamlssoprofile']['attribute15format'] = attribute15format

    if attribute16:
        payload['tmsamlssoprofile']['attribute16'] = attribute16

    if attribute16expr:
        payload['tmsamlssoprofile']['attribute16expr'] = attribute16expr

    if attribute16friendlyname:
        payload['tmsamlssoprofile']['attribute16friendlyname'] = attribute16friendlyname

    if attribute16format:
        payload['tmsamlssoprofile']['attribute16format'] = attribute16format

    if encryptassertion:
        payload['tmsamlssoprofile']['encryptassertion'] = encryptassertion

    if samlspcertname:
        payload['tmsamlssoprofile']['samlspcertname'] = samlspcertname

    if encryptionalgorithm:
        payload['tmsamlssoprofile']['encryptionalgorithm'] = encryptionalgorithm

    if skewtime:
        payload['tmsamlssoprofile']['skewtime'] = skewtime

    execution = __proxy__['citrixns.put']('config/tmsamlssoprofile', payload)

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


def update_tmsessionaction(name=None, sesstimeout=None, defaultauthorizationaction=None, sso=None, ssocredential=None,
                           ssodomain=None, httponlycookie=None, kcdaccount=None, persistentcookie=None,
                           persistentcookievalidity=None, homepage=None, save=False):
    '''
    Update the running configuration for the tmsessionaction config key.

    name(str): Name for the session action. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after a session action is created.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my action" or my action). Minimum length = 1

    sesstimeout(int): Session timeout, in minutes. If there is no traffic during the timeout period, the user is disconnected
        and must reauthenticate to access intranet resources. Minimum value = 1

    defaultauthorizationaction(str): Allow or deny access to content for which there is no specific authorization policy.
        Possible values = ALLOW, DENY

    sso(str): Use single sign-on (SSO) to log users on to all web applications automatically after they authenticate, or pass
        users to the web application logon page to authenticate to each application individually. Default value: OFF
        Possible values = ON, OFF

    ssocredential(str): Use the primary or secondary authentication credentials for single sign-on (SSO). Possible values =
        PRIMARY, SECONDARY

    ssodomain(str): Domain to use for single sign-on (SSO). Minimum length = 1 Maximum length = 32

    httponlycookie(str): Allow only an HTTP session cookie, in which case the cookie cannot be accessed by scripts. Possible
        values = YES, NO

    kcdaccount(str): Kerberos constrained delegation account name. Minimum length = 1 Maximum length = 32

    persistentcookie(str): Enable or disable persistent SSO cookies for the traffic management (TM) session. A persistent
        cookie remains on the user device and is sent with each HTTP request. The cookie becomes stale if the session
        ends. This setting is overwritten if a traffic action sets persistent cookie to OFF.  Note: If persistent cookie
        is enabled, make sure you set the persistent cookie validity. Possible values = ON, OFF

    persistentcookievalidity(int): Integer specifying the number of minutes for which the persistent cookie remains valid.
        Can be set only if the persistent cookie setting is enabled. Minimum value = 1

    homepage(str): Web address of the home page that a user is displayed when authentication vserver is bookmarked and used
        to login.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.update_tmsessionaction <args>

    '''

    result = {}

    payload = {'tmsessionaction': {}}

    if name:
        payload['tmsessionaction']['name'] = name

    if sesstimeout:
        payload['tmsessionaction']['sesstimeout'] = sesstimeout

    if defaultauthorizationaction:
        payload['tmsessionaction']['defaultauthorizationaction'] = defaultauthorizationaction

    if sso:
        payload['tmsessionaction']['sso'] = sso

    if ssocredential:
        payload['tmsessionaction']['ssocredential'] = ssocredential

    if ssodomain:
        payload['tmsessionaction']['ssodomain'] = ssodomain

    if httponlycookie:
        payload['tmsessionaction']['httponlycookie'] = httponlycookie

    if kcdaccount:
        payload['tmsessionaction']['kcdaccount'] = kcdaccount

    if persistentcookie:
        payload['tmsessionaction']['persistentcookie'] = persistentcookie

    if persistentcookievalidity:
        payload['tmsessionaction']['persistentcookievalidity'] = persistentcookievalidity

    if homepage:
        payload['tmsessionaction']['homepage'] = homepage

    execution = __proxy__['citrixns.put']('config/tmsessionaction', payload)

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


def update_tmsessionparameter(sesstimeout=None, defaultauthorizationaction=None, sso=None, ssocredential=None,
                              ssodomain=None, kcdaccount=None, httponlycookie=None, persistentcookie=None,
                              persistentcookievalidity=None, homepage=None, save=False):
    '''
    Update the running configuration for the tmsessionparameter config key.

    sesstimeout(int): Session timeout, in minutes. If there is no traffic during the timeout period, the user is disconnected
        and must reauthenticate to access the intranet resources. Default value: 30 Minimum value = 1

    defaultauthorizationaction(str): Allow or deny access to content for which there is no specific authorization policy.
        Default value: ALLOW Possible values = ALLOW, DENY

    sso(str): Log users on to all web applications automatically after they authenticate, or pass users to the web
        application logon page to authenticate for each application. Default value: OFF Possible values = ON, OFF

    ssocredential(str): Use primary or secondary authentication credentials for single sign-on. Default value: PRIMARY
        Possible values = PRIMARY, SECONDARY

    ssodomain(str): Domain to use for single sign-on. Minimum length = 1 Maximum length = 32

    kcdaccount(str): Kerberos constrained delegation account name. Minimum length = 1 Maximum length = 32

    httponlycookie(str): Allow only an HTTP session cookie, in which case the cookie cannot be accessed by scripts. Default
        value: YES Possible values = YES, NO

    persistentcookie(str): Use persistent SSO cookies for the traffic session. A persistent cookie remains on the user device
        and is sent with each HTTP request. The cookie becomes stale if the session ends. Default value: OFF Possible
        values = ON, OFF

    persistentcookievalidity(int): Integer specifying the number of minutes for which the persistent cookie remains valid.
        Can be set only if the persistence cookie setting is enabled. Minimum value = 1

    homepage(str): Web address of the home page that a user is displayed when authentication vserver is bookmarked and used
        to login. Default value: "None"

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.update_tmsessionparameter <args>

    '''

    result = {}

    payload = {'tmsessionparameter': {}}

    if sesstimeout:
        payload['tmsessionparameter']['sesstimeout'] = sesstimeout

    if defaultauthorizationaction:
        payload['tmsessionparameter']['defaultauthorizationaction'] = defaultauthorizationaction

    if sso:
        payload['tmsessionparameter']['sso'] = sso

    if ssocredential:
        payload['tmsessionparameter']['ssocredential'] = ssocredential

    if ssodomain:
        payload['tmsessionparameter']['ssodomain'] = ssodomain

    if kcdaccount:
        payload['tmsessionparameter']['kcdaccount'] = kcdaccount

    if httponlycookie:
        payload['tmsessionparameter']['httponlycookie'] = httponlycookie

    if persistentcookie:
        payload['tmsessionparameter']['persistentcookie'] = persistentcookie

    if persistentcookievalidity:
        payload['tmsessionparameter']['persistentcookievalidity'] = persistentcookievalidity

    if homepage:
        payload['tmsessionparameter']['homepage'] = homepage

    execution = __proxy__['citrixns.put']('config/tmsessionparameter', payload)

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


def update_tmsessionpolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the tmsessionpolicy config key.

    name(str): Name for the session policy. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters. Cannot be changed after a session policy is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, against which traffic is evaluated. Both classic and advance expressions are supported in default
        partition but only advance expressions in non-default partition. Maximum length of a string literal in the
        expression is 255 characters. A longer string can be split into smaller strings of up to 255 characters each, and
        the smaller strings concatenated with the + operator. For example, you can create a 500-character string as
        follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements
        apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression
        in double quotation marks. * If the expression itself includes double quotation marks, escape the quotations by
        using the \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case
        you do not have to escape the double quotation marks.

    action(str): Action to be applied to connections that match this policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.update_tmsessionpolicy <args>

    '''

    result = {}

    payload = {'tmsessionpolicy': {}}

    if name:
        payload['tmsessionpolicy']['name'] = name

    if rule:
        payload['tmsessionpolicy']['rule'] = rule

    if action:
        payload['tmsessionpolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/tmsessionpolicy', payload)

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


def update_tmtrafficaction(name=None, apptimeout=None, sso=None, formssoaction=None, persistentcookie=None,
                           initiatelogout=None, kcdaccount=None, samlssoprofile=None, forcedtimeout=None,
                           forcedtimeoutval=None, userexpression=None, passwdexpression=None, save=False):
    '''
    Update the running configuration for the tmtrafficaction config key.

    name(str): Name for the traffic action. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after a traffic action is created.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my action" or my action). Minimum length = 1

    apptimeout(int): Time interval, in minutes, of user inactivity after which the connection is closed. Minimum value = 1
        Maximum value = 715827

    sso(str): Use single sign-on for the resource that the user is accessing now. Possible values = ON, OFF

    formssoaction(str): Name of the configured form-based single sign-on profile.

    persistentcookie(str): Use persistent cookies for the traffic session. A persistent cookie remains on the user device and
        is sent with each HTTP request. The cookie becomes stale if the session ends. Possible values = ON, OFF

    initiatelogout(str): Initiate logout for the traffic management (TM) session if the policy evaluates to true. The session
        is then terminated after two minutes. Possible values = ON, OFF

    kcdaccount(str): Kerberos constrained delegation account name. Default value: "None" Minimum length = 1 Maximum length =
        32

    samlssoprofile(str): Profile to be used for doing SAML SSO to remote relying party. Minimum length = 1

    forcedtimeout(str): Setting to start, stop or reset TM session force timer. Possible values = START, STOP, RESET

    forcedtimeoutval(int): Time interval, in minutes, for which force timer should be set.

    userexpression(str): expression that will be evaluated to obtain username for SingleSignOn. Maximum length = 256

    passwdexpression(str): expression that will be evaluated to obtain password for SingleSignOn. Maximum length = 256

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.update_tmtrafficaction <args>

    '''

    result = {}

    payload = {'tmtrafficaction': {}}

    if name:
        payload['tmtrafficaction']['name'] = name

    if apptimeout:
        payload['tmtrafficaction']['apptimeout'] = apptimeout

    if sso:
        payload['tmtrafficaction']['sso'] = sso

    if formssoaction:
        payload['tmtrafficaction']['formssoaction'] = formssoaction

    if persistentcookie:
        payload['tmtrafficaction']['persistentcookie'] = persistentcookie

    if initiatelogout:
        payload['tmtrafficaction']['initiatelogout'] = initiatelogout

    if kcdaccount:
        payload['tmtrafficaction']['kcdaccount'] = kcdaccount

    if samlssoprofile:
        payload['tmtrafficaction']['samlssoprofile'] = samlssoprofile

    if forcedtimeout:
        payload['tmtrafficaction']['forcedtimeout'] = forcedtimeout

    if forcedtimeoutval:
        payload['tmtrafficaction']['forcedtimeoutval'] = forcedtimeoutval

    if userexpression:
        payload['tmtrafficaction']['userexpression'] = userexpression

    if passwdexpression:
        payload['tmtrafficaction']['passwdexpression'] = passwdexpression

    execution = __proxy__['citrixns.put']('config/tmtrafficaction', payload)

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


def update_tmtrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the tmtrafficpolicy config key.

    name(str): Name for the traffic policy. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, against which traffic is evaluated. Written in the classic syntax. Maximum length of a string
        literal in the expression is 255 characters. A longer string can be split into smaller strings of up to 255
        characters each, and the smaller strings concatenated with the + operator. For example, you can create a
        500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The
        following requirements apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose
        the entire expression in double quotation marks. * If the expression itself includes double quotation marks,
        escape the quotations by using the \\ character.  * Alternatively, you can use single quotation marks to enclose
        the rule, in which case you do not have to escape the double quotation marks.

    action(str): Name of the action to apply to requests or connections that match this policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' traffic_management.update_tmtrafficpolicy <args>

    '''

    result = {}

    payload = {'tmtrafficpolicy': {}}

    if name:
        payload['tmtrafficpolicy']['name'] = name

    if rule:
        payload['tmtrafficpolicy']['rule'] = rule

    if action:
        payload['tmtrafficpolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/tmtrafficpolicy', payload)

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
