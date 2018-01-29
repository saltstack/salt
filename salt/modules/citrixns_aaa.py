# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the aaa key.

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

__virtualname__ = 'aaa'


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

    return False, 'The aaa execution module can only be loaded for citrixns proxy minions.'


def add_aaaglobal_aaapreauthenticationpolicy_binding(priority=None, policy=None, builtin=None, save=False):
    '''
    Add a new aaaglobal_aaapreauthenticationpolicy_binding to the running configuration.

    priority(int): Priority of the bound policy.

    policy(str): Name of the policy to be unbound. Minimum length = 1

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaaglobal_aaapreauthenticationpolicy_binding <args>

    '''

    result = {}

    payload = {'aaaglobal_aaapreauthenticationpolicy_binding': {}}

    if priority:
        payload['aaaglobal_aaapreauthenticationpolicy_binding']['priority'] = priority

    if policy:
        payload['aaaglobal_aaapreauthenticationpolicy_binding']['policy'] = policy

    if builtin:
        payload['aaaglobal_aaapreauthenticationpolicy_binding']['builtin'] = builtin

    execution = __proxy__['citrixns.post']('config/aaaglobal_aaapreauthenticationpolicy_binding', payload)

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


def add_aaaglobal_authenticationnegotiateaction_binding(windowsprofile=None, save=False):
    '''
    Add a new aaaglobal_authenticationnegotiateaction_binding to the running configuration.

    windowsprofile(str): Name of the negotiate profile to be bound. Minimum length = 1 Maximum length = 32

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaaglobal_authenticationnegotiateaction_binding <args>

    '''

    result = {}

    payload = {'aaaglobal_authenticationnegotiateaction_binding': {}}

    if windowsprofile:
        payload['aaaglobal_authenticationnegotiateaction_binding']['windowsprofile'] = windowsprofile

    execution = __proxy__['citrixns.post']('config/aaaglobal_authenticationnegotiateaction_binding', payload)

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


def add_aaagroup(groupname=None, weight=None, loggedin=None, save=False):
    '''
    Add a new aaagroup to the running configuration.

    groupname(str): Name for the group. Must begin with a letter, number, or the underscore character (_), and must consist
        only of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the group is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my aaa group" or my aaa group). Minimum length = 1

    weight(int): Weight of this group with respect to other configured aaa groups (lower the number higher the weight).
        Default value: 0 Minimum value = 0 Maximum value = 65535

    loggedin(bool): Display only the group members who are currently logged in.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup <args>

    '''

    result = {}

    payload = {'aaagroup': {}}

    if groupname:
        payload['aaagroup']['groupname'] = groupname

    if weight:
        payload['aaagroup']['weight'] = weight

    if loggedin:
        payload['aaagroup']['loggedin'] = loggedin

    execution = __proxy__['citrixns.post']('config/aaagroup', payload)

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


def add_aaagroup_aaauser_binding(gotopriorityexpression=None, username=None, groupname=None, save=False):
    '''
    Add a new aaagroup_aaauser_binding to the running configuration.

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    username(str): The user name.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_aaauser_binding <args>

    '''

    result = {}

    payload = {'aaagroup_aaauser_binding': {}}

    if gotopriorityexpression:
        payload['aaagroup_aaauser_binding']['gotopriorityexpression'] = gotopriorityexpression

    if username:
        payload['aaagroup_aaauser_binding']['username'] = username

    if groupname:
        payload['aaagroup_aaauser_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_aaauser_binding', payload)

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


def add_aaagroup_auditnslogpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None,
                                          save=False):
    '''
    Add a new aaagroup_auditnslogpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The policy name.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'aaagroup_auditnslogpolicy_binding': {}}

    if priority:
        payload['aaagroup_auditnslogpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['aaagroup_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaagroup_auditnslogpolicy_binding']['policy'] = policy

    if groupname:
        payload['aaagroup_auditnslogpolicy_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_auditnslogpolicy_binding', payload)

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


def add_aaagroup_auditsyslogpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None,
                                           save=False):
    '''
    Add a new aaagroup_auditsyslogpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The policy name.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'aaagroup_auditsyslogpolicy_binding': {}}

    if priority:
        payload['aaagroup_auditsyslogpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['aaagroup_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaagroup_auditsyslogpolicy_binding']['policy'] = policy

    if groupname:
        payload['aaagroup_auditsyslogpolicy_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_auditsyslogpolicy_binding', payload)

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


def add_aaagroup_authorizationpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None,
                                             save=False):
    '''
    Add a new aaagroup_authorizationpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policy(str): The policy name.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_authorizationpolicy_binding <args>

    '''

    result = {}

    payload = {'aaagroup_authorizationpolicy_binding': {}}

    if priority:
        payload['aaagroup_authorizationpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['aaagroup_authorizationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaagroup_authorizationpolicy_binding']['policy'] = policy

    if groupname:
        payload['aaagroup_authorizationpolicy_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_authorizationpolicy_binding', payload)

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


def add_aaagroup_intranetip6_binding(intranetip6=None, gotopriorityexpression=None, numaddr=None, groupname=None,
                                     save=False):
    '''
    Add a new aaagroup_intranetip6_binding to the running configuration.

    intranetip6(str): The Intranet IP6(s) bound to the group.

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    numaddr(int): Numbers of ipv6 address bound starting with intranetip6.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_intranetip6_binding <args>

    '''

    result = {}

    payload = {'aaagroup_intranetip6_binding': {}}

    if intranetip6:
        payload['aaagroup_intranetip6_binding']['intranetip6'] = intranetip6

    if gotopriorityexpression:
        payload['aaagroup_intranetip6_binding']['gotopriorityexpression'] = gotopriorityexpression

    if numaddr:
        payload['aaagroup_intranetip6_binding']['numaddr'] = numaddr

    if groupname:
        payload['aaagroup_intranetip6_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_intranetip6_binding', payload)

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


def add_aaagroup_intranetip_binding(gotopriorityexpression=None, intranetip=None, groupname=None, netmask=None,
                                    save=False):
    '''
    Add a new aaagroup_intranetip_binding to the running configuration.

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    intranetip(str): The Intranet IP(s) bound to the group.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    netmask(str): The netmask for the Intranet IP.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_intranetip_binding <args>

    '''

    result = {}

    payload = {'aaagroup_intranetip_binding': {}}

    if gotopriorityexpression:
        payload['aaagroup_intranetip_binding']['gotopriorityexpression'] = gotopriorityexpression

    if intranetip:
        payload['aaagroup_intranetip_binding']['intranetip'] = intranetip

    if groupname:
        payload['aaagroup_intranetip_binding']['groupname'] = groupname

    if netmask:
        payload['aaagroup_intranetip_binding']['netmask'] = netmask

    execution = __proxy__['citrixns.post']('config/aaagroup_intranetip_binding', payload)

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


def add_aaagroup_tmsessionpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None,
                                         save=False):
    '''
    Add a new aaagroup_tmsessionpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policy(str): The policy name.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_tmsessionpolicy_binding <args>

    '''

    result = {}

    payload = {'aaagroup_tmsessionpolicy_binding': {}}

    if priority:
        payload['aaagroup_tmsessionpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['aaagroup_tmsessionpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaagroup_tmsessionpolicy_binding']['policy'] = policy

    if groupname:
        payload['aaagroup_tmsessionpolicy_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_tmsessionpolicy_binding', payload)

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


def add_aaagroup_vpnintranetapplication_binding(gotopriorityexpression=None, groupname=None, intranetapplication=None,
                                                save=False):
    '''
    Add a new aaagroup_vpnintranetapplication_binding to the running configuration.

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    intranetapplication(str): Bind the group to the specified intranet VPN application.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_vpnintranetapplication_binding <args>

    '''

    result = {}

    payload = {'aaagroup_vpnintranetapplication_binding': {}}

    if gotopriorityexpression:
        payload['aaagroup_vpnintranetapplication_binding']['gotopriorityexpression'] = gotopriorityexpression

    if groupname:
        payload['aaagroup_vpnintranetapplication_binding']['groupname'] = groupname

    if intranetapplication:
        payload['aaagroup_vpnintranetapplication_binding']['intranetapplication'] = intranetapplication

    execution = __proxy__['citrixns.post']('config/aaagroup_vpnintranetapplication_binding', payload)

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


def add_aaagroup_vpnsessionpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None,
                                          save=False):
    '''
    Add a new aaagroup_vpnsessionpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policy(str): The policy name.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_vpnsessionpolicy_binding <args>

    '''

    result = {}

    payload = {'aaagroup_vpnsessionpolicy_binding': {}}

    if priority:
        payload['aaagroup_vpnsessionpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['aaagroup_vpnsessionpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaagroup_vpnsessionpolicy_binding']['policy'] = policy

    if groupname:
        payload['aaagroup_vpnsessionpolicy_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_vpnsessionpolicy_binding', payload)

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


def add_aaagroup_vpntrafficpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None,
                                          save=False):
    '''
    Add a new aaagroup_vpntrafficpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies is 64000. Minimum value = 0 Maximum value = 2147483647

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The policy name.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_vpntrafficpolicy_binding <args>

    '''

    result = {}

    payload = {'aaagroup_vpntrafficpolicy_binding': {}}

    if priority:
        payload['aaagroup_vpntrafficpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['aaagroup_vpntrafficpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaagroup_vpntrafficpolicy_binding']['policy'] = policy

    if groupname:
        payload['aaagroup_vpntrafficpolicy_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_vpntrafficpolicy_binding', payload)

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


def add_aaagroup_vpnurl_binding(urlname=None, gotopriorityexpression=None, groupname=None, save=False):
    '''
    Add a new aaagroup_vpnurl_binding to the running configuration.

    urlname(str): The intranet url.

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    groupname(str): Name of the group that you are binding. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaagroup_vpnurl_binding <args>

    '''

    result = {}

    payload = {'aaagroup_vpnurl_binding': {}}

    if urlname:
        payload['aaagroup_vpnurl_binding']['urlname'] = urlname

    if gotopriorityexpression:
        payload['aaagroup_vpnurl_binding']['gotopriorityexpression'] = gotopriorityexpression

    if groupname:
        payload['aaagroup_vpnurl_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/aaagroup_vpnurl_binding', payload)

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


def add_aaakcdaccount(kcdaccount=None, keytab=None, realmstr=None, delegateduser=None, kcdpassword=None, usercert=None,
                      cacert=None, userrealm=None, enterpriserealm=None, servicespn=None, save=False):
    '''
    Add a new aaakcdaccount to the running configuration.

    kcdaccount(str): The name of the KCD account. Minimum length = 1

    keytab(str): The path to the keytab file. If specified other parameters in this command need not be given.

    realmstr(str): Kerberos Realm.

    delegateduser(str): Username that can perform kerberos constrained delegation.

    kcdpassword(str): Password for Delegated User.

    usercert(str): SSL Cert (including private key) for Delegated User.

    cacert(str): CA Cert for UserCert or when doing PKINIT backchannel.

    userrealm(str): Realm of the user.

    enterpriserealm(str): Enterprise Realm of the user. This should be given only in certain KDC deployments where KDC
        expects Enterprise username instead of Principal Name.

    servicespn(str): Service SPN. When specified, this will be used to fetch kerberos tickets. If not specified, Netscaler
        will construct SPN using service fqdn.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaakcdaccount <args>

    '''

    result = {}

    payload = {'aaakcdaccount': {}}

    if kcdaccount:
        payload['aaakcdaccount']['kcdaccount'] = kcdaccount

    if keytab:
        payload['aaakcdaccount']['keytab'] = keytab

    if realmstr:
        payload['aaakcdaccount']['realmstr'] = realmstr

    if delegateduser:
        payload['aaakcdaccount']['delegateduser'] = delegateduser

    if kcdpassword:
        payload['aaakcdaccount']['kcdpassword'] = kcdpassword

    if usercert:
        payload['aaakcdaccount']['usercert'] = usercert

    if cacert:
        payload['aaakcdaccount']['cacert'] = cacert

    if userrealm:
        payload['aaakcdaccount']['userrealm'] = userrealm

    if enterpriserealm:
        payload['aaakcdaccount']['enterpriserealm'] = enterpriserealm

    if servicespn:
        payload['aaakcdaccount']['servicespn'] = servicespn

    execution = __proxy__['citrixns.post']('config/aaakcdaccount', payload)

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


def add_aaapreauthenticationaction(name=None, preauthenticationaction=None, killprocess=None, deletefiles=None,
                                   defaultepagroup=None, save=False):
    '''
    Add a new aaapreauthenticationaction to the running configuration.

    name(str): Name for the preauthentication action. Must begin with a letter, number, or the underscore character (_), and
        must consist only of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after preauthentication action is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my aaa action" or my aaa action). Minimum length = 1

    preauthenticationaction(str): Allow or deny logon after endpoint analysis (EPA) results. Possible values = ALLOW, DENY

    killprocess(str): String specifying the name of a process to be terminated by the endpoint analysis (EPA) tool.

    deletefiles(str): String specifying the path(s) and name(s) of the files to be deleted by the endpoint analysis (EPA)
        tool.

    defaultepagroup(str): This is the default group that is chosen when the EPA check succeeds. Maximum length = 64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaapreauthenticationaction <args>

    '''

    result = {}

    payload = {'aaapreauthenticationaction': {}}

    if name:
        payload['aaapreauthenticationaction']['name'] = name

    if preauthenticationaction:
        payload['aaapreauthenticationaction']['preauthenticationaction'] = preauthenticationaction

    if killprocess:
        payload['aaapreauthenticationaction']['killprocess'] = killprocess

    if deletefiles:
        payload['aaapreauthenticationaction']['deletefiles'] = deletefiles

    if defaultepagroup:
        payload['aaapreauthenticationaction']['defaultepagroup'] = defaultepagroup

    execution = __proxy__['citrixns.post']('config/aaapreauthenticationaction', payload)

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


def add_aaapreauthenticationpolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Add a new aaapreauthenticationpolicy to the running configuration.

    name(str): Name for the preauthentication policy. Must begin with a letter, number, or the underscore character (_), and
        must consist only of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals
        (=), colon (:), and underscore characters. Cannot be changed after the preauthentication policy is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, defining connections that match the policy.

    reqaction(str): Name of the action that the policy is to invoke when a connection matches the policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaapreauthenticationpolicy <args>

    '''

    result = {}

    payload = {'aaapreauthenticationpolicy': {}}

    if name:
        payload['aaapreauthenticationpolicy']['name'] = name

    if rule:
        payload['aaapreauthenticationpolicy']['rule'] = rule

    if reqaction:
        payload['aaapreauthenticationpolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.post']('config/aaapreauthenticationpolicy', payload)

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


def add_aaauser(username=None, password=None, loggedin=None, save=False):
    '''
    Add a new aaauser to the running configuration.

    username(str): Name for the user. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the user is added.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my aaa user" or "my aaa user"). Minimum length = 1

    password(str): Password with which the user logs on. Required for any user account that does not exist on an external
        authentication server.  If you are not using an external authentication server, all user accounts must have a
        password. If you are using an external authentication server, you must provide a password for local user accounts
        that do not exist on the authentication server. Minimum length = 1

    loggedin(bool): Show whether the user is logged in or not.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser <args>

    '''

    result = {}

    payload = {'aaauser': {}}

    if username:
        payload['aaauser']['username'] = username

    if password:
        payload['aaauser']['password'] = password

    if loggedin:
        payload['aaauser']['loggedin'] = loggedin

    execution = __proxy__['citrixns.post']('config/aaauser', payload)

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


def add_aaauser_auditnslogpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None,
                                         save=False):
    '''
    Add a new aaauser_auditnslogpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies max priority is 64000. . Minimum value = 0 Maximum value = 2147483647

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The policy Name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'aaauser_auditnslogpolicy_binding': {}}

    if priority:
        payload['aaauser_auditnslogpolicy_binding']['priority'] = priority

    if username:
        payload['aaauser_auditnslogpolicy_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaauser_auditnslogpolicy_binding']['policy'] = policy

    execution = __proxy__['citrixns.post']('config/aaauser_auditnslogpolicy_binding', payload)

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


def add_aaauser_auditsyslogpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None,
                                          save=False):
    '''
    Add a new aaauser_auditsyslogpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies max priority is 64000. . Minimum value = 0 Maximum value = 2147483647

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The policy Name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'aaauser_auditsyslogpolicy_binding': {}}

    if priority:
        payload['aaauser_auditsyslogpolicy_binding']['priority'] = priority

    if username:
        payload['aaauser_auditsyslogpolicy_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaauser_auditsyslogpolicy_binding']['policy'] = policy

    execution = __proxy__['citrixns.post']('config/aaauser_auditsyslogpolicy_binding', payload)

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


def add_aaauser_authorizationpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None,
                                            save=False):
    '''
    Add a new aaauser_authorizationpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies max priority is 64000. . Minimum value = 0 Maximum value = 2147483647

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policy(str): The policy Name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_authorizationpolicy_binding <args>

    '''

    result = {}

    payload = {'aaauser_authorizationpolicy_binding': {}}

    if priority:
        payload['aaauser_authorizationpolicy_binding']['priority'] = priority

    if username:
        payload['aaauser_authorizationpolicy_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_authorizationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaauser_authorizationpolicy_binding']['policy'] = policy

    execution = __proxy__['citrixns.post']('config/aaauser_authorizationpolicy_binding', payload)

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


def add_aaauser_intranetip6_binding(intranetip6=None, username=None, gotopriorityexpression=None, numaddr=None,
                                    save=False):
    '''
    Add a new aaauser_intranetip6_binding to the running configuration.

    intranetip6(str): The Intranet IP6 bound to the user.

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    numaddr(int): Numbers of ipv6 address bound starting with intranetip6.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_intranetip6_binding <args>

    '''

    result = {}

    payload = {'aaauser_intranetip6_binding': {}}

    if intranetip6:
        payload['aaauser_intranetip6_binding']['intranetip6'] = intranetip6

    if username:
        payload['aaauser_intranetip6_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_intranetip6_binding']['gotopriorityexpression'] = gotopriorityexpression

    if numaddr:
        payload['aaauser_intranetip6_binding']['numaddr'] = numaddr

    execution = __proxy__['citrixns.post']('config/aaauser_intranetip6_binding', payload)

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


def add_aaauser_intranetip_binding(intranetip=None, username=None, gotopriorityexpression=None, netmask=None,
                                   save=False):
    '''
    Add a new aaauser_intranetip_binding to the running configuration.

    intranetip(str): The Intranet IP bound to the user.

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    netmask(str): The netmask for the Intranet IP.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_intranetip_binding <args>

    '''

    result = {}

    payload = {'aaauser_intranetip_binding': {}}

    if intranetip:
        payload['aaauser_intranetip_binding']['intranetip'] = intranetip

    if username:
        payload['aaauser_intranetip_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_intranetip_binding']['gotopriorityexpression'] = gotopriorityexpression

    if netmask:
        payload['aaauser_intranetip_binding']['netmask'] = netmask

    execution = __proxy__['citrixns.post']('config/aaauser_intranetip_binding', payload)

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


def add_aaauser_tmsessionpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None,
                                        save=False):
    '''
    Add a new aaauser_tmsessionpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies max priority is 64000. . Minimum value = 0 Maximum value = 2147483647

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policy(str): The policy Name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_tmsessionpolicy_binding <args>

    '''

    result = {}

    payload = {'aaauser_tmsessionpolicy_binding': {}}

    if priority:
        payload['aaauser_tmsessionpolicy_binding']['priority'] = priority

    if username:
        payload['aaauser_tmsessionpolicy_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_tmsessionpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaauser_tmsessionpolicy_binding']['policy'] = policy

    execution = __proxy__['citrixns.post']('config/aaauser_tmsessionpolicy_binding', payload)

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


def add_aaauser_vpnintranetapplication_binding(username=None, gotopriorityexpression=None, intranetapplication=None,
                                               save=False):
    '''
    Add a new aaauser_vpnintranetapplication_binding to the running configuration.

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    intranetapplication(str): Name of the intranet VPN application to which the policy applies.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_vpnintranetapplication_binding <args>

    '''

    result = {}

    payload = {'aaauser_vpnintranetapplication_binding': {}}

    if username:
        payload['aaauser_vpnintranetapplication_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_vpnintranetapplication_binding']['gotopriorityexpression'] = gotopriorityexpression

    if intranetapplication:
        payload['aaauser_vpnintranetapplication_binding']['intranetapplication'] = intranetapplication

    execution = __proxy__['citrixns.post']('config/aaauser_vpnintranetapplication_binding', payload)

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


def add_aaauser_vpnsessionpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None,
                                         save=False):
    '''
    Add a new aaauser_vpnsessionpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies max priority is 64000. . Minimum value = 0 Maximum value = 2147483647

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policy(str): The policy Name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_vpnsessionpolicy_binding <args>

    '''

    result = {}

    payload = {'aaauser_vpnsessionpolicy_binding': {}}

    if priority:
        payload['aaauser_vpnsessionpolicy_binding']['priority'] = priority

    if username:
        payload['aaauser_vpnsessionpolicy_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_vpnsessionpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaauser_vpnsessionpolicy_binding']['policy'] = policy

    execution = __proxy__['citrixns.post']('config/aaauser_vpnsessionpolicy_binding', payload)

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


def add_aaauser_vpntrafficpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None,
                                         save=False):
    '''
    Add a new aaauser_vpntrafficpolicy_binding to the running configuration.

    priority(int): Integer specifying the priority of the policy. A lower number indicates a higher priority. Policies are
        evaluated in the order of their priority numbers. Maximum value for default syntax policies is 2147483647 and for
        classic policies max priority is 64000. . Minimum value = 0 Maximum value = 2147483647

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    policy(str): The policy Name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_vpntrafficpolicy_binding <args>

    '''

    result = {}

    payload = {'aaauser_vpntrafficpolicy_binding': {}}

    if priority:
        payload['aaauser_vpntrafficpolicy_binding']['priority'] = priority

    if username:
        payload['aaauser_vpntrafficpolicy_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_vpntrafficpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['aaauser_vpntrafficpolicy_binding']['policy'] = policy

    execution = __proxy__['citrixns.post']('config/aaauser_vpntrafficpolicy_binding', payload)

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


def add_aaauser_vpnurl_binding(urlname=None, username=None, gotopriorityexpression=None, save=False):
    '''
    Add a new aaauser_vpnurl_binding to the running configuration.

    urlname(str): The intranet url.

    username(str): User account to which to bind the policy. Minimum length = 1

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is numerically lower than the
        current policys priority. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.add_aaauser_vpnurl_binding <args>

    '''

    result = {}

    payload = {'aaauser_vpnurl_binding': {}}

    if urlname:
        payload['aaauser_vpnurl_binding']['urlname'] = urlname

    if username:
        payload['aaauser_vpnurl_binding']['username'] = username

    if gotopriorityexpression:
        payload['aaauser_vpnurl_binding']['gotopriorityexpression'] = gotopriorityexpression

    execution = __proxy__['citrixns.post']('config/aaauser_vpnurl_binding', payload)

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


def get_aaacertparams():
    '''
    Show the running configuration for the aaacertparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaacertparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaacertparams'), 'aaacertparams')

    return response


def get_aaaglobal_aaapreauthenticationpolicy_binding(priority=None, policy=None, builtin=None):
    '''
    Show the running configuration for the aaaglobal_aaapreauthenticationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policy(str): Filters results that only match the policy field.

    builtin(list(str)): Filters results that only match the builtin field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaaglobal_aaapreauthenticationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policy:
        search_filter.append(['policy', policy])

    if builtin:
        search_filter.append(['builtin', builtin])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaaglobal_aaapreauthenticationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaaglobal_aaapreauthenticationpolicy_binding')

    return response


def get_aaaglobal_authenticationnegotiateaction_binding(windowsprofile=None):
    '''
    Show the running configuration for the aaaglobal_authenticationnegotiateaction_binding config key.

    windowsprofile(str): Filters results that only match the windowsprofile field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaaglobal_authenticationnegotiateaction_binding

    '''

    search_filter = []

    if windowsprofile:
        search_filter.append(['windowsprofile', windowsprofile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaaglobal_authenticationnegotiateaction_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaaglobal_authenticationnegotiateaction_binding')

    return response


def get_aaaglobal_binding():
    '''
    Show the running configuration for the aaaglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaaglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaaglobal_binding'), 'aaaglobal_binding')

    return response


def get_aaagroup(groupname=None, weight=None, loggedin=None):
    '''
    Show the running configuration for the aaagroup config key.

    groupname(str): Filters results that only match the groupname field.

    weight(int): Filters results that only match the weight field.

    loggedin(bool): Filters results that only match the loggedin field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup

    '''

    search_filter = []

    if groupname:
        search_filter.append(['groupname', groupname])

    if weight:
        search_filter.append(['weight', weight])

    if loggedin:
        search_filter.append(['loggedin', loggedin])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup')

    return response


def get_aaagroup_aaauser_binding(gotopriorityexpression=None, username=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_aaauser_binding config key.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    username(str): Filters results that only match the username field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_aaauser_binding

    '''

    search_filter = []

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if username:
        search_filter.append(['username', username])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_aaauser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_aaauser_binding')

    return response


def get_aaagroup_auditnslogpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_auditnslogpolicy_binding')

    return response


def get_aaagroup_auditsyslogpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_auditsyslogpolicy_binding')

    return response


def get_aaagroup_authorizationpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_authorizationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_authorizationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_authorizationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_authorizationpolicy_binding')

    return response


def get_aaagroup_binding():
    '''
    Show the running configuration for the aaagroup_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_binding'), 'aaagroup_binding')

    return response


def get_aaagroup_intranetip6_binding(intranetip6=None, gotopriorityexpression=None, numaddr=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_intranetip6_binding config key.

    intranetip6(str): Filters results that only match the intranetip6 field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    numaddr(int): Filters results that only match the numaddr field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_intranetip6_binding

    '''

    search_filter = []

    if intranetip6:
        search_filter.append(['intranetip6', intranetip6])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if numaddr:
        search_filter.append(['numaddr', numaddr])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_intranetip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_intranetip6_binding')

    return response


def get_aaagroup_intranetip_binding(gotopriorityexpression=None, intranetip=None, groupname=None, netmask=None):
    '''
    Show the running configuration for the aaagroup_intranetip_binding config key.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    intranetip(str): Filters results that only match the intranetip field.

    groupname(str): Filters results that only match the groupname field.

    netmask(str): Filters results that only match the netmask field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_intranetip_binding

    '''

    search_filter = []

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if intranetip:
        search_filter.append(['intranetip', intranetip])

    if groupname:
        search_filter.append(['groupname', groupname])

    if netmask:
        search_filter.append(['netmask', netmask])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_intranetip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_intranetip_binding')

    return response


def get_aaagroup_tmsessionpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_tmsessionpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_tmsessionpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_tmsessionpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_tmsessionpolicy_binding')

    return response


def get_aaagroup_vpnintranetapplication_binding(gotopriorityexpression=None, groupname=None, intranetapplication=None):
    '''
    Show the running configuration for the aaagroup_vpnintranetapplication_binding config key.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    groupname(str): Filters results that only match the groupname field.

    intranetapplication(str): Filters results that only match the intranetapplication field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_vpnintranetapplication_binding

    '''

    search_filter = []

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if groupname:
        search_filter.append(['groupname', groupname])

    if intranetapplication:
        search_filter.append(['intranetapplication', intranetapplication])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_vpnintranetapplication_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_vpnintranetapplication_binding')

    return response


def get_aaagroup_vpnsessionpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_vpnsessionpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_vpnsessionpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_vpnsessionpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_vpnsessionpolicy_binding')

    return response


def get_aaagroup_vpntrafficpolicy_binding(priority=None, gotopriorityexpression=None, policy=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_vpntrafficpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_vpntrafficpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_vpntrafficpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_vpntrafficpolicy_binding')

    return response


def get_aaagroup_vpnurl_binding(urlname=None, gotopriorityexpression=None, groupname=None):
    '''
    Show the running configuration for the aaagroup_vpnurl_binding config key.

    urlname(str): Filters results that only match the urlname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaagroup_vpnurl_binding

    '''

    search_filter = []

    if urlname:
        search_filter.append(['urlname', urlname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaagroup_vpnurl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaagroup_vpnurl_binding')

    return response


def get_aaakcdaccount(kcdaccount=None, keytab=None, realmstr=None, delegateduser=None, kcdpassword=None, usercert=None,
                      cacert=None, userrealm=None, enterpriserealm=None, servicespn=None):
    '''
    Show the running configuration for the aaakcdaccount config key.

    kcdaccount(str): Filters results that only match the kcdaccount field.

    keytab(str): Filters results that only match the keytab field.

    realmstr(str): Filters results that only match the realmstr field.

    delegateduser(str): Filters results that only match the delegateduser field.

    kcdpassword(str): Filters results that only match the kcdpassword field.

    usercert(str): Filters results that only match the usercert field.

    cacert(str): Filters results that only match the cacert field.

    userrealm(str): Filters results that only match the userrealm field.

    enterpriserealm(str): Filters results that only match the enterpriserealm field.

    servicespn(str): Filters results that only match the servicespn field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaakcdaccount

    '''

    search_filter = []

    if kcdaccount:
        search_filter.append(['kcdaccount', kcdaccount])

    if keytab:
        search_filter.append(['keytab', keytab])

    if realmstr:
        search_filter.append(['realmstr', realmstr])

    if delegateduser:
        search_filter.append(['delegateduser', delegateduser])

    if kcdpassword:
        search_filter.append(['kcdpassword', kcdpassword])

    if usercert:
        search_filter.append(['usercert', usercert])

    if cacert:
        search_filter.append(['cacert', cacert])

    if userrealm:
        search_filter.append(['userrealm', userrealm])

    if enterpriserealm:
        search_filter.append(['enterpriserealm', enterpriserealm])

    if servicespn:
        search_filter.append(['servicespn', servicespn])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaakcdaccount{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaakcdaccount')

    return response


def get_aaaldapparams():
    '''
    Show the running configuration for the aaaldapparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaaldapparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaaldapparams'), 'aaaldapparams')

    return response


def get_aaaparameter():
    '''
    Show the running configuration for the aaaparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaaparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaaparameter'), 'aaaparameter')

    return response


def get_aaapreauthenticationaction(name=None, preauthenticationaction=None, killprocess=None, deletefiles=None,
                                   defaultepagroup=None):
    '''
    Show the running configuration for the aaapreauthenticationaction config key.

    name(str): Filters results that only match the name field.

    preauthenticationaction(str): Filters results that only match the preauthenticationaction field.

    killprocess(str): Filters results that only match the killprocess field.

    deletefiles(str): Filters results that only match the deletefiles field.

    defaultepagroup(str): Filters results that only match the defaultepagroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaapreauthenticationaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if preauthenticationaction:
        search_filter.append(['preauthenticationaction', preauthenticationaction])

    if killprocess:
        search_filter.append(['killprocess', killprocess])

    if deletefiles:
        search_filter.append(['deletefiles', deletefiles])

    if defaultepagroup:
        search_filter.append(['defaultepagroup', defaultepagroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaapreauthenticationaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaapreauthenticationaction')

    return response


def get_aaapreauthenticationparameter():
    '''
    Show the running configuration for the aaapreauthenticationparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaapreauthenticationparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaapreauthenticationparameter'), 'aaapreauthenticationparameter')

    return response


def get_aaapreauthenticationpolicy(name=None, rule=None, reqaction=None):
    '''
    Show the running configuration for the aaapreauthenticationpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaapreauthenticationpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaapreauthenticationpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaapreauthenticationpolicy')

    return response


def get_aaapreauthenticationpolicy_aaaglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the aaapreauthenticationpolicy_aaaglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaapreauthenticationpolicy_aaaglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaapreauthenticationpolicy_aaaglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaapreauthenticationpolicy_aaaglobal_binding')

    return response


def get_aaapreauthenticationpolicy_binding():
    '''
    Show the running configuration for the aaapreauthenticationpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaapreauthenticationpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaapreauthenticationpolicy_binding'), 'aaapreauthenticationpolicy_binding')

    return response


def get_aaapreauthenticationpolicy_vpnvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the aaapreauthenticationpolicy_vpnvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaapreauthenticationpolicy_vpnvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaapreauthenticationpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaapreauthenticationpolicy_vpnvserver_binding')

    return response


def get_aaaradiusparams():
    '''
    Show the running configuration for the aaaradiusparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaaradiusparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaaradiusparams'), 'aaaradiusparams')

    return response


def get_aaasession(username=None, groupname=None, iip=None, netmask=None, nodeid=None):
    '''
    Show the running configuration for the aaasession config key.

    username(str): Filters results that only match the username field.

    groupname(str): Filters results that only match the groupname field.

    iip(str): Filters results that only match the iip field.

    netmask(str): Filters results that only match the netmask field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaasession

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if groupname:
        search_filter.append(['groupname', groupname])

    if iip:
        search_filter.append(['iip', iip])

    if netmask:
        search_filter.append(['netmask', netmask])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaasession{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaasession')

    return response


def get_aaatacacsparams():
    '''
    Show the running configuration for the aaatacacsparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaatacacsparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaatacacsparams'), 'aaatacacsparams')

    return response


def get_aaauser(username=None, password=None, loggedin=None):
    '''
    Show the running configuration for the aaauser config key.

    username(str): Filters results that only match the username field.

    password(str): Filters results that only match the password field.

    loggedin(bool): Filters results that only match the loggedin field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if password:
        search_filter.append(['password', password])

    if loggedin:
        search_filter.append(['loggedin', loggedin])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser')

    return response


def get_aaauser_aaagroup_binding(username=None, groupname=None, gotopriorityexpression=None):
    '''
    Show the running configuration for the aaauser_aaagroup_binding config key.

    username(str): Filters results that only match the username field.

    groupname(str): Filters results that only match the groupname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_aaagroup_binding

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if groupname:
        search_filter.append(['groupname', groupname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_aaagroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_aaagroup_binding')

    return response


def get_aaauser_auditnslogpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None):
    '''
    Show the running configuration for the aaauser_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_auditnslogpolicy_binding')

    return response


def get_aaauser_auditsyslogpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None):
    '''
    Show the running configuration for the aaauser_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_auditsyslogpolicy_binding')

    return response


def get_aaauser_authorizationpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None):
    '''
    Show the running configuration for the aaauser_authorizationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_authorizationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_authorizationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_authorizationpolicy_binding')

    return response


def get_aaauser_binding():
    '''
    Show the running configuration for the aaauser_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_binding'), 'aaauser_binding')

    return response


def get_aaauser_intranetip6_binding(intranetip6=None, username=None, gotopriorityexpression=None, numaddr=None):
    '''
    Show the running configuration for the aaauser_intranetip6_binding config key.

    intranetip6(str): Filters results that only match the intranetip6 field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    numaddr(int): Filters results that only match the numaddr field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_intranetip6_binding

    '''

    search_filter = []

    if intranetip6:
        search_filter.append(['intranetip6', intranetip6])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if numaddr:
        search_filter.append(['numaddr', numaddr])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_intranetip6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_intranetip6_binding')

    return response


def get_aaauser_intranetip_binding(intranetip=None, username=None, gotopriorityexpression=None, netmask=None):
    '''
    Show the running configuration for the aaauser_intranetip_binding config key.

    intranetip(str): Filters results that only match the intranetip field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    netmask(str): Filters results that only match the netmask field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_intranetip_binding

    '''

    search_filter = []

    if intranetip:
        search_filter.append(['intranetip', intranetip])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if netmask:
        search_filter.append(['netmask', netmask])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_intranetip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_intranetip_binding')

    return response


def get_aaauser_tmsessionpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None):
    '''
    Show the running configuration for the aaauser_tmsessionpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_tmsessionpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_tmsessionpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_tmsessionpolicy_binding')

    return response


def get_aaauser_vpnintranetapplication_binding(username=None, gotopriorityexpression=None, intranetapplication=None):
    '''
    Show the running configuration for the aaauser_vpnintranetapplication_binding config key.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    intranetapplication(str): Filters results that only match the intranetapplication field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_vpnintranetapplication_binding

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if intranetapplication:
        search_filter.append(['intranetapplication', intranetapplication])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_vpnintranetapplication_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_vpnintranetapplication_binding')

    return response


def get_aaauser_vpnsessionpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None):
    '''
    Show the running configuration for the aaauser_vpnsessionpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_vpnsessionpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_vpnsessionpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_vpnsessionpolicy_binding')

    return response


def get_aaauser_vpntrafficpolicy_binding(priority=None, username=None, gotopriorityexpression=None, policy=None):
    '''
    Show the running configuration for the aaauser_vpntrafficpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_vpntrafficpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_vpntrafficpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_vpntrafficpolicy_binding')

    return response


def get_aaauser_vpnurl_binding(urlname=None, username=None, gotopriorityexpression=None):
    '''
    Show the running configuration for the aaauser_vpnurl_binding config key.

    urlname(str): Filters results that only match the urlname field.

    username(str): Filters results that only match the username field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.get_aaauser_vpnurl_binding

    '''

    search_filter = []

    if urlname:
        search_filter.append(['urlname', urlname])

    if username:
        search_filter.append(['username', username])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/aaauser_vpnurl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'aaauser_vpnurl_binding')

    return response


def unset_aaacertparams(usernamefield=None, groupnamefield=None, defaultauthenticationgroup=None, save=False):
    '''
    Unsets values from the aaacertparams configuration key.

    usernamefield(bool): Unsets the usernamefield value.

    groupnamefield(bool): Unsets the groupnamefield value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.unset_aaacertparams <args>

    '''

    result = {}

    payload = {'aaacertparams': {}}

    if usernamefield:
        payload['aaacertparams']['usernamefield'] = True

    if groupnamefield:
        payload['aaacertparams']['groupnamefield'] = True

    if defaultauthenticationgroup:
        payload['aaacertparams']['defaultauthenticationgroup'] = True

    execution = __proxy__['citrixns.post']('config/aaacertparams?action=unset', payload)

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


def unset_aaakcdaccount(kcdaccount=None, keytab=None, realmstr=None, delegateduser=None, kcdpassword=None, usercert=None,
                        cacert=None, userrealm=None, enterpriserealm=None, servicespn=None, save=False):
    '''
    Unsets values from the aaakcdaccount configuration key.

    kcdaccount(bool): Unsets the kcdaccount value.

    keytab(bool): Unsets the keytab value.

    realmstr(bool): Unsets the realmstr value.

    delegateduser(bool): Unsets the delegateduser value.

    kcdpassword(bool): Unsets the kcdpassword value.

    usercert(bool): Unsets the usercert value.

    cacert(bool): Unsets the cacert value.

    userrealm(bool): Unsets the userrealm value.

    enterpriserealm(bool): Unsets the enterpriserealm value.

    servicespn(bool): Unsets the servicespn value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.unset_aaakcdaccount <args>

    '''

    result = {}

    payload = {'aaakcdaccount': {}}

    if kcdaccount:
        payload['aaakcdaccount']['kcdaccount'] = True

    if keytab:
        payload['aaakcdaccount']['keytab'] = True

    if realmstr:
        payload['aaakcdaccount']['realmstr'] = True

    if delegateduser:
        payload['aaakcdaccount']['delegateduser'] = True

    if kcdpassword:
        payload['aaakcdaccount']['kcdpassword'] = True

    if usercert:
        payload['aaakcdaccount']['usercert'] = True

    if cacert:
        payload['aaakcdaccount']['cacert'] = True

    if userrealm:
        payload['aaakcdaccount']['userrealm'] = True

    if enterpriserealm:
        payload['aaakcdaccount']['enterpriserealm'] = True

    if servicespn:
        payload['aaakcdaccount']['servicespn'] = True

    execution = __proxy__['citrixns.post']('config/aaakcdaccount?action=unset', payload)

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


def unset_aaaldapparams(serverip=None, serverport=None, authtimeout=None, ldapbase=None, ldapbinddn=None,
                        ldapbinddnpassword=None, ldaploginname=None, searchfilter=None, groupattrname=None,
                        subattributename=None, sectype=None, svrtype=None, ssonameattribute=None, passwdchange=None,
                        nestedgroupextraction=None, maxnestinglevel=None, groupnameidentifier=None,
                        groupsearchattribute=None, groupsearchsubattribute=None, groupsearchfilter=None,
                        defaultauthenticationgroup=None, save=False):
    '''
    Unsets values from the aaaldapparams configuration key.

    serverip(bool): Unsets the serverip value.

    serverport(bool): Unsets the serverport value.

    authtimeout(bool): Unsets the authtimeout value.

    ldapbase(bool): Unsets the ldapbase value.

    ldapbinddn(bool): Unsets the ldapbinddn value.

    ldapbinddnpassword(bool): Unsets the ldapbinddnpassword value.

    ldaploginname(bool): Unsets the ldaploginname value.

    searchfilter(bool): Unsets the searchfilter value.

    groupattrname(bool): Unsets the groupattrname value.

    subattributename(bool): Unsets the subattributename value.

    sectype(bool): Unsets the sectype value.

    svrtype(bool): Unsets the svrtype value.

    ssonameattribute(bool): Unsets the ssonameattribute value.

    passwdchange(bool): Unsets the passwdchange value.

    nestedgroupextraction(bool): Unsets the nestedgroupextraction value.

    maxnestinglevel(bool): Unsets the maxnestinglevel value.

    groupnameidentifier(bool): Unsets the groupnameidentifier value.

    groupsearchattribute(bool): Unsets the groupsearchattribute value.

    groupsearchsubattribute(bool): Unsets the groupsearchsubattribute value.

    groupsearchfilter(bool): Unsets the groupsearchfilter value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.unset_aaaldapparams <args>

    '''

    result = {}

    payload = {'aaaldapparams': {}}

    if serverip:
        payload['aaaldapparams']['serverip'] = True

    if serverport:
        payload['aaaldapparams']['serverport'] = True

    if authtimeout:
        payload['aaaldapparams']['authtimeout'] = True

    if ldapbase:
        payload['aaaldapparams']['ldapbase'] = True

    if ldapbinddn:
        payload['aaaldapparams']['ldapbinddn'] = True

    if ldapbinddnpassword:
        payload['aaaldapparams']['ldapbinddnpassword'] = True

    if ldaploginname:
        payload['aaaldapparams']['ldaploginname'] = True

    if searchfilter:
        payload['aaaldapparams']['searchfilter'] = True

    if groupattrname:
        payload['aaaldapparams']['groupattrname'] = True

    if subattributename:
        payload['aaaldapparams']['subattributename'] = True

    if sectype:
        payload['aaaldapparams']['sectype'] = True

    if svrtype:
        payload['aaaldapparams']['svrtype'] = True

    if ssonameattribute:
        payload['aaaldapparams']['ssonameattribute'] = True

    if passwdchange:
        payload['aaaldapparams']['passwdchange'] = True

    if nestedgroupextraction:
        payload['aaaldapparams']['nestedgroupextraction'] = True

    if maxnestinglevel:
        payload['aaaldapparams']['maxnestinglevel'] = True

    if groupnameidentifier:
        payload['aaaldapparams']['groupnameidentifier'] = True

    if groupsearchattribute:
        payload['aaaldapparams']['groupsearchattribute'] = True

    if groupsearchsubattribute:
        payload['aaaldapparams']['groupsearchsubattribute'] = True

    if groupsearchfilter:
        payload['aaaldapparams']['groupsearchfilter'] = True

    if defaultauthenticationgroup:
        payload['aaaldapparams']['defaultauthenticationgroup'] = True

    execution = __proxy__['citrixns.post']('config/aaaldapparams?action=unset', payload)

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


def unset_aaaparameter(enablestaticpagecaching=None, enableenhancedauthfeedback=None, defaultauthtype=None,
                       maxaaausers=None, maxloginattempts=None, failedlogintimeout=None, aaadnatip=None,
                       enablesessionstickiness=None, aaasessionloglevel=None, aaadloglevel=None, dynaddr=None,
                       ftmode=None, save=False):
    '''
    Unsets values from the aaaparameter configuration key.

    enablestaticpagecaching(bool): Unsets the enablestaticpagecaching value.

    enableenhancedauthfeedback(bool): Unsets the enableenhancedauthfeedback value.

    defaultauthtype(bool): Unsets the defaultauthtype value.

    maxaaausers(bool): Unsets the maxaaausers value.

    maxloginattempts(bool): Unsets the maxloginattempts value.

    failedlogintimeout(bool): Unsets the failedlogintimeout value.

    aaadnatip(bool): Unsets the aaadnatip value.

    enablesessionstickiness(bool): Unsets the enablesessionstickiness value.

    aaasessionloglevel(bool): Unsets the aaasessionloglevel value.

    aaadloglevel(bool): Unsets the aaadloglevel value.

    dynaddr(bool): Unsets the dynaddr value.

    ftmode(bool): Unsets the ftmode value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.unset_aaaparameter <args>

    '''

    result = {}

    payload = {'aaaparameter': {}}

    if enablestaticpagecaching:
        payload['aaaparameter']['enablestaticpagecaching'] = True

    if enableenhancedauthfeedback:
        payload['aaaparameter']['enableenhancedauthfeedback'] = True

    if defaultauthtype:
        payload['aaaparameter']['defaultauthtype'] = True

    if maxaaausers:
        payload['aaaparameter']['maxaaausers'] = True

    if maxloginattempts:
        payload['aaaparameter']['maxloginattempts'] = True

    if failedlogintimeout:
        payload['aaaparameter']['failedlogintimeout'] = True

    if aaadnatip:
        payload['aaaparameter']['aaadnatip'] = True

    if enablesessionstickiness:
        payload['aaaparameter']['enablesessionstickiness'] = True

    if aaasessionloglevel:
        payload['aaaparameter']['aaasessionloglevel'] = True

    if aaadloglevel:
        payload['aaaparameter']['aaadloglevel'] = True

    if dynaddr:
        payload['aaaparameter']['dynaddr'] = True

    if ftmode:
        payload['aaaparameter']['ftmode'] = True

    execution = __proxy__['citrixns.post']('config/aaaparameter?action=unset', payload)

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


def unset_aaapreauthenticationaction(name=None, preauthenticationaction=None, killprocess=None, deletefiles=None,
                                     defaultepagroup=None, save=False):
    '''
    Unsets values from the aaapreauthenticationaction configuration key.

    name(bool): Unsets the name value.

    preauthenticationaction(bool): Unsets the preauthenticationaction value.

    killprocess(bool): Unsets the killprocess value.

    deletefiles(bool): Unsets the deletefiles value.

    defaultepagroup(bool): Unsets the defaultepagroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.unset_aaapreauthenticationaction <args>

    '''

    result = {}

    payload = {'aaapreauthenticationaction': {}}

    if name:
        payload['aaapreauthenticationaction']['name'] = True

    if preauthenticationaction:
        payload['aaapreauthenticationaction']['preauthenticationaction'] = True

    if killprocess:
        payload['aaapreauthenticationaction']['killprocess'] = True

    if deletefiles:
        payload['aaapreauthenticationaction']['deletefiles'] = True

    if defaultepagroup:
        payload['aaapreauthenticationaction']['defaultepagroup'] = True

    execution = __proxy__['citrixns.post']('config/aaapreauthenticationaction?action=unset', payload)

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


def unset_aaapreauthenticationparameter(preauthenticationaction=None, rule=None, killprocess=None, deletefiles=None,
                                        save=False):
    '''
    Unsets values from the aaapreauthenticationparameter configuration key.

    preauthenticationaction(bool): Unsets the preauthenticationaction value.

    rule(bool): Unsets the rule value.

    killprocess(bool): Unsets the killprocess value.

    deletefiles(bool): Unsets the deletefiles value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.unset_aaapreauthenticationparameter <args>

    '''

    result = {}

    payload = {'aaapreauthenticationparameter': {}}

    if preauthenticationaction:
        payload['aaapreauthenticationparameter']['preauthenticationaction'] = True

    if rule:
        payload['aaapreauthenticationparameter']['rule'] = True

    if killprocess:
        payload['aaapreauthenticationparameter']['killprocess'] = True

    if deletefiles:
        payload['aaapreauthenticationparameter']['deletefiles'] = True

    execution = __proxy__['citrixns.post']('config/aaapreauthenticationparameter?action=unset', payload)

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


def unset_aaaradiusparams(serverip=None, serverport=None, authtimeout=None, radkey=None, radnasip=None, radnasid=None,
                          radvendorid=None, radattributetype=None, radgroupsprefix=None, radgroupseparator=None,
                          passencoding=None, ipvendorid=None, ipattributetype=None, accounting=None, pwdvendorid=None,
                          pwdattributetype=None, defaultauthenticationgroup=None, callingstationid=None,
                          authservretry=None, authentication=None, save=False):
    '''
    Unsets values from the aaaradiusparams configuration key.

    serverip(bool): Unsets the serverip value.

    serverport(bool): Unsets the serverport value.

    authtimeout(bool): Unsets the authtimeout value.

    radkey(bool): Unsets the radkey value.

    radnasip(bool): Unsets the radnasip value.

    radnasid(bool): Unsets the radnasid value.

    radvendorid(bool): Unsets the radvendorid value.

    radattributetype(bool): Unsets the radattributetype value.

    radgroupsprefix(bool): Unsets the radgroupsprefix value.

    radgroupseparator(bool): Unsets the radgroupseparator value.

    passencoding(bool): Unsets the passencoding value.

    ipvendorid(bool): Unsets the ipvendorid value.

    ipattributetype(bool): Unsets the ipattributetype value.

    accounting(bool): Unsets the accounting value.

    pwdvendorid(bool): Unsets the pwdvendorid value.

    pwdattributetype(bool): Unsets the pwdattributetype value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    callingstationid(bool): Unsets the callingstationid value.

    authservretry(bool): Unsets the authservretry value.

    authentication(bool): Unsets the authentication value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.unset_aaaradiusparams <args>

    '''

    result = {}

    payload = {'aaaradiusparams': {}}

    if serverip:
        payload['aaaradiusparams']['serverip'] = True

    if serverport:
        payload['aaaradiusparams']['serverport'] = True

    if authtimeout:
        payload['aaaradiusparams']['authtimeout'] = True

    if radkey:
        payload['aaaradiusparams']['radkey'] = True

    if radnasip:
        payload['aaaradiusparams']['radnasip'] = True

    if radnasid:
        payload['aaaradiusparams']['radnasid'] = True

    if radvendorid:
        payload['aaaradiusparams']['radvendorid'] = True

    if radattributetype:
        payload['aaaradiusparams']['radattributetype'] = True

    if radgroupsprefix:
        payload['aaaradiusparams']['radgroupsprefix'] = True

    if radgroupseparator:
        payload['aaaradiusparams']['radgroupseparator'] = True

    if passencoding:
        payload['aaaradiusparams']['passencoding'] = True

    if ipvendorid:
        payload['aaaradiusparams']['ipvendorid'] = True

    if ipattributetype:
        payload['aaaradiusparams']['ipattributetype'] = True

    if accounting:
        payload['aaaradiusparams']['accounting'] = True

    if pwdvendorid:
        payload['aaaradiusparams']['pwdvendorid'] = True

    if pwdattributetype:
        payload['aaaradiusparams']['pwdattributetype'] = True

    if defaultauthenticationgroup:
        payload['aaaradiusparams']['defaultauthenticationgroup'] = True

    if callingstationid:
        payload['aaaradiusparams']['callingstationid'] = True

    if authservretry:
        payload['aaaradiusparams']['authservretry'] = True

    if authentication:
        payload['aaaradiusparams']['authentication'] = True

    execution = __proxy__['citrixns.post']('config/aaaradiusparams?action=unset', payload)

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


def unset_aaatacacsparams(serverip=None, serverport=None, authtimeout=None, tacacssecret=None, authorization=None,
                          accounting=None, auditfailedcmds=None, groupattrname=None, defaultauthenticationgroup=None,
                          save=False):
    '''
    Unsets values from the aaatacacsparams configuration key.

    serverip(bool): Unsets the serverip value.

    serverport(bool): Unsets the serverport value.

    authtimeout(bool): Unsets the authtimeout value.

    tacacssecret(bool): Unsets the tacacssecret value.

    authorization(bool): Unsets the authorization value.

    accounting(bool): Unsets the accounting value.

    auditfailedcmds(bool): Unsets the auditfailedcmds value.

    groupattrname(bool): Unsets the groupattrname value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.unset_aaatacacsparams <args>

    '''

    result = {}

    payload = {'aaatacacsparams': {}}

    if serverip:
        payload['aaatacacsparams']['serverip'] = True

    if serverport:
        payload['aaatacacsparams']['serverport'] = True

    if authtimeout:
        payload['aaatacacsparams']['authtimeout'] = True

    if tacacssecret:
        payload['aaatacacsparams']['tacacssecret'] = True

    if authorization:
        payload['aaatacacsparams']['authorization'] = True

    if accounting:
        payload['aaatacacsparams']['accounting'] = True

    if auditfailedcmds:
        payload['aaatacacsparams']['auditfailedcmds'] = True

    if groupattrname:
        payload['aaatacacsparams']['groupattrname'] = True

    if defaultauthenticationgroup:
        payload['aaatacacsparams']['defaultauthenticationgroup'] = True

    execution = __proxy__['citrixns.post']('config/aaatacacsparams?action=unset', payload)

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


def update_aaacertparams(usernamefield=None, groupnamefield=None, defaultauthenticationgroup=None, save=False):
    '''
    Update the running configuration for the aaacertparams config key.

    usernamefield(str): Client certificate field that contains the username, in the format ;lt;field;gt;:;lt;subfield;gt;. .

    groupnamefield(str): Client certificate field that specifies the group, in the format ;lt;field;gt;:;lt;subfield;gt;.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups. Maximum length = 64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaacertparams <args>

    '''

    result = {}

    payload = {'aaacertparams': {}}

    if usernamefield:
        payload['aaacertparams']['usernamefield'] = usernamefield

    if groupnamefield:
        payload['aaacertparams']['groupnamefield'] = groupnamefield

    if defaultauthenticationgroup:
        payload['aaacertparams']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.put']('config/aaacertparams', payload)

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


def update_aaakcdaccount(kcdaccount=None, keytab=None, realmstr=None, delegateduser=None, kcdpassword=None,
                         usercert=None, cacert=None, userrealm=None, enterpriserealm=None, servicespn=None, save=False):
    '''
    Update the running configuration for the aaakcdaccount config key.

    kcdaccount(str): The name of the KCD account. Minimum length = 1

    keytab(str): The path to the keytab file. If specified other parameters in this command need not be given.

    realmstr(str): Kerberos Realm.

    delegateduser(str): Username that can perform kerberos constrained delegation.

    kcdpassword(str): Password for Delegated User.

    usercert(str): SSL Cert (including private key) for Delegated User.

    cacert(str): CA Cert for UserCert or when doing PKINIT backchannel.

    userrealm(str): Realm of the user.

    enterpriserealm(str): Enterprise Realm of the user. This should be given only in certain KDC deployments where KDC
        expects Enterprise username instead of Principal Name.

    servicespn(str): Service SPN. When specified, this will be used to fetch kerberos tickets. If not specified, Netscaler
        will construct SPN using service fqdn.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaakcdaccount <args>

    '''

    result = {}

    payload = {'aaakcdaccount': {}}

    if kcdaccount:
        payload['aaakcdaccount']['kcdaccount'] = kcdaccount

    if keytab:
        payload['aaakcdaccount']['keytab'] = keytab

    if realmstr:
        payload['aaakcdaccount']['realmstr'] = realmstr

    if delegateduser:
        payload['aaakcdaccount']['delegateduser'] = delegateduser

    if kcdpassword:
        payload['aaakcdaccount']['kcdpassword'] = kcdpassword

    if usercert:
        payload['aaakcdaccount']['usercert'] = usercert

    if cacert:
        payload['aaakcdaccount']['cacert'] = cacert

    if userrealm:
        payload['aaakcdaccount']['userrealm'] = userrealm

    if enterpriserealm:
        payload['aaakcdaccount']['enterpriserealm'] = enterpriserealm

    if servicespn:
        payload['aaakcdaccount']['servicespn'] = servicespn

    execution = __proxy__['citrixns.put']('config/aaakcdaccount', payload)

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


def update_aaaldapparams(serverip=None, serverport=None, authtimeout=None, ldapbase=None, ldapbinddn=None,
                         ldapbinddnpassword=None, ldaploginname=None, searchfilter=None, groupattrname=None,
                         subattributename=None, sectype=None, svrtype=None, ssonameattribute=None, passwdchange=None,
                         nestedgroupextraction=None, maxnestinglevel=None, groupnameidentifier=None,
                         groupsearchattribute=None, groupsearchsubattribute=None, groupsearchfilter=None,
                         defaultauthenticationgroup=None, save=False):
    '''
    Update the running configuration for the aaaldapparams config key.

    serverip(str): IP address of your LDAP server.

    serverport(int): Port number on which the LDAP server listens for connections. Default value: 389 Minimum value = 1

    authtimeout(int): Maximum number of seconds that the NetScaler appliance waits for a response from the LDAP server.
        Default value: 3 Minimum value = 1

    ldapbase(str): Base (the server and location) from which LDAP search commands should start.  If the LDAP server is
        running locally, the default value of base is dc=netscaler, dc=com.

    ldapbinddn(str): Complete distinguished name (DN) string used for binding to the LDAP server.

    ldapbinddnpassword(str): Password for binding to the LDAP server. Minimum length = 1

    ldaploginname(str): Name attribute that the NetScaler appliance uses to query the external LDAP server or an Active
        Directory.

    searchfilter(str): String to be combined with the default LDAP user search string to form the value to use when executing
        an LDAP search.  For example, the following values: vpnallowed=true, ldaploginame=""samaccount"" when combined
        with the user-supplied username ""bob"", yield the following LDAP search string:
        ""(;amp;(vpnallowed=true)(samaccount=bob)"". Minimum length = 1

    groupattrname(str): Attribute name used for group extraction from the LDAP server.

    subattributename(str): Subattribute name used for group extraction from the LDAP server.

    sectype(str): Type of security used for communications between the NetScaler appliance and the LDAP server. For the
        PLAINTEXT setting, no encryption is required. Default value: PLAINTEXT Possible values = PLAINTEXT, TLS, SSL

    svrtype(str): The type of LDAP server. Default value: AAA_LDAP_SERVER_TYPE_DEFAULT Possible values = AD, NDS

    ssonameattribute(str): Attribute used by the NetScaler appliance to query an external LDAP server or Active Directory for
        an alternative username.  This alternative username is then used for single sign-on (SSO).

    passwdchange(str): Accept password change requests. Default value: DISABLED Possible values = ENABLED, DISABLED

    nestedgroupextraction(str): Queries the external LDAP server to determine whether the specified group belongs to another
        group. Default value: OFF Possible values = ON, OFF

    maxnestinglevel(int): Number of levels up to which the system can query nested LDAP groups. Default value: 2 Minimum
        value = 2

    groupnameidentifier(str): LDAP-group attribute that uniquely identifies the group. No two groups on one LDAP server can
        have the same group name identifier.

    groupsearchattribute(str): LDAP-group attribute that designates the parent group of the specified group. Use this
        attribute to search for a groups parent group.

    groupsearchsubattribute(str): LDAP-group subattribute that designates the parent group of the specified group. Use this
        attribute to search for a groups parent group.

    groupsearchfilter(str): Search-expression that can be specified for sending group-search requests to the LDAP server.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups. Maximum length = 64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaaldapparams <args>

    '''

    result = {}

    payload = {'aaaldapparams': {}}

    if serverip:
        payload['aaaldapparams']['serverip'] = serverip

    if serverport:
        payload['aaaldapparams']['serverport'] = serverport

    if authtimeout:
        payload['aaaldapparams']['authtimeout'] = authtimeout

    if ldapbase:
        payload['aaaldapparams']['ldapbase'] = ldapbase

    if ldapbinddn:
        payload['aaaldapparams']['ldapbinddn'] = ldapbinddn

    if ldapbinddnpassword:
        payload['aaaldapparams']['ldapbinddnpassword'] = ldapbinddnpassword

    if ldaploginname:
        payload['aaaldapparams']['ldaploginname'] = ldaploginname

    if searchfilter:
        payload['aaaldapparams']['searchfilter'] = searchfilter

    if groupattrname:
        payload['aaaldapparams']['groupattrname'] = groupattrname

    if subattributename:
        payload['aaaldapparams']['subattributename'] = subattributename

    if sectype:
        payload['aaaldapparams']['sectype'] = sectype

    if svrtype:
        payload['aaaldapparams']['svrtype'] = svrtype

    if ssonameattribute:
        payload['aaaldapparams']['ssonameattribute'] = ssonameattribute

    if passwdchange:
        payload['aaaldapparams']['passwdchange'] = passwdchange

    if nestedgroupextraction:
        payload['aaaldapparams']['nestedgroupextraction'] = nestedgroupextraction

    if maxnestinglevel:
        payload['aaaldapparams']['maxnestinglevel'] = maxnestinglevel

    if groupnameidentifier:
        payload['aaaldapparams']['groupnameidentifier'] = groupnameidentifier

    if groupsearchattribute:
        payload['aaaldapparams']['groupsearchattribute'] = groupsearchattribute

    if groupsearchsubattribute:
        payload['aaaldapparams']['groupsearchsubattribute'] = groupsearchsubattribute

    if groupsearchfilter:
        payload['aaaldapparams']['groupsearchfilter'] = groupsearchfilter

    if defaultauthenticationgroup:
        payload['aaaldapparams']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.put']('config/aaaldapparams', payload)

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


def update_aaaparameter(enablestaticpagecaching=None, enableenhancedauthfeedback=None, defaultauthtype=None,
                        maxaaausers=None, maxloginattempts=None, failedlogintimeout=None, aaadnatip=None,
                        enablesessionstickiness=None, aaasessionloglevel=None, aaadloglevel=None, dynaddr=None,
                        ftmode=None, save=False):
    '''
    Update the running configuration for the aaaparameter config key.

    enablestaticpagecaching(str): The default state of VPN Static Page caching. If nothing is specified, the default value is
        set to YES. Default value: YES Possible values = YES, NO

    enableenhancedauthfeedback(str): Enhanced auth feedback provides more information to the end user about the reason for an
        authentication failure. The default value is set to NO. Default value: NO Possible values = YES, NO

    defaultauthtype(str): The default authentication server type. Default value: LOCAL Possible values = LOCAL, LDAP, RADIUS,
        TACACS, CERT

    maxaaausers(int): Maximum number of concurrent users allowed to log on to VPN simultaneously. Minimum value = 1

    maxloginattempts(int): Maximum Number of login Attempts. Minimum value = 1

    failedlogintimeout(int): Number of minutes an account will be locked if user exceeds maximum permissible attempts.
        Minimum value = 1

    aaadnatip(str): Source IP address to use for traffic that is sent to the authentication server.

    enablesessionstickiness(str): Enables/Disables stickiness to authentication servers. Default value: NO Possible values =
        YES, NO

    aaasessionloglevel(str): Audit log level, which specifies the types of events to log for cli executed commands.
        Available values function as follows:  * EMERGENCY - Events that indicate an immediate crisis on the server. *
        ALERT - Events that might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR -
        Events that indicate some type of error. * WARNING - Events that require action in the near future. * NOTICE -
        Events that the administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All
        events, in extreme detail. Default value: DEFAULT_LOGLEVEL_AAA Possible values = EMERGENCY, ALERT, CRITICAL,
        ERROR, WARNING, NOTICE, INFORMATIONAL, DEBUG

    aaadloglevel(str): AAAD log level, which specifies the types of AAAD events to log in nsvpn.log.  Available values
        function as follows:  * EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT - Events that
        might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events that indicate
        some type of error. * WARNING - Events that require action in the near future. * NOTICE - Events that the
        administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in extreme
        detail. Default value: INFORMATIONAL Possible values = EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE,
        INFORMATIONAL, DEBUG

    dynaddr(str): Set by the DHCP client when the IP address was fetched dynamically. Default value: OFF Possible values =
        ON, OFF

    ftmode(str): First time user mode determines which configuration options are shown by default when logging in to the GUI.
        This setting is controlled by the GUI. Default value: ON Possible values = ON, HA, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaaparameter <args>

    '''

    result = {}

    payload = {'aaaparameter': {}}

    if enablestaticpagecaching:
        payload['aaaparameter']['enablestaticpagecaching'] = enablestaticpagecaching

    if enableenhancedauthfeedback:
        payload['aaaparameter']['enableenhancedauthfeedback'] = enableenhancedauthfeedback

    if defaultauthtype:
        payload['aaaparameter']['defaultauthtype'] = defaultauthtype

    if maxaaausers:
        payload['aaaparameter']['maxaaausers'] = maxaaausers

    if maxloginattempts:
        payload['aaaparameter']['maxloginattempts'] = maxloginattempts

    if failedlogintimeout:
        payload['aaaparameter']['failedlogintimeout'] = failedlogintimeout

    if aaadnatip:
        payload['aaaparameter']['aaadnatip'] = aaadnatip

    if enablesessionstickiness:
        payload['aaaparameter']['enablesessionstickiness'] = enablesessionstickiness

    if aaasessionloglevel:
        payload['aaaparameter']['aaasessionloglevel'] = aaasessionloglevel

    if aaadloglevel:
        payload['aaaparameter']['aaadloglevel'] = aaadloglevel

    if dynaddr:
        payload['aaaparameter']['dynaddr'] = dynaddr

    if ftmode:
        payload['aaaparameter']['ftmode'] = ftmode

    execution = __proxy__['citrixns.put']('config/aaaparameter', payload)

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


def update_aaapreauthenticationaction(name=None, preauthenticationaction=None, killprocess=None, deletefiles=None,
                                      defaultepagroup=None, save=False):
    '''
    Update the running configuration for the aaapreauthenticationaction config key.

    name(str): Name for the preauthentication action. Must begin with a letter, number, or the underscore character (_), and
        must consist only of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after preauthentication action is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my aaa action" or my aaa action). Minimum length = 1

    preauthenticationaction(str): Allow or deny logon after endpoint analysis (EPA) results. Possible values = ALLOW, DENY

    killprocess(str): String specifying the name of a process to be terminated by the endpoint analysis (EPA) tool.

    deletefiles(str): String specifying the path(s) and name(s) of the files to be deleted by the endpoint analysis (EPA)
        tool.

    defaultepagroup(str): This is the default group that is chosen when the EPA check succeeds. Maximum length = 64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaapreauthenticationaction <args>

    '''

    result = {}

    payload = {'aaapreauthenticationaction': {}}

    if name:
        payload['aaapreauthenticationaction']['name'] = name

    if preauthenticationaction:
        payload['aaapreauthenticationaction']['preauthenticationaction'] = preauthenticationaction

    if killprocess:
        payload['aaapreauthenticationaction']['killprocess'] = killprocess

    if deletefiles:
        payload['aaapreauthenticationaction']['deletefiles'] = deletefiles

    if defaultepagroup:
        payload['aaapreauthenticationaction']['defaultepagroup'] = defaultepagroup

    execution = __proxy__['citrixns.put']('config/aaapreauthenticationaction', payload)

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


def update_aaapreauthenticationparameter(preauthenticationaction=None, rule=None, killprocess=None, deletefiles=None,
                                         save=False):
    '''
    Update the running configuration for the aaapreauthenticationparameter config key.

    preauthenticationaction(str): Deny or allow login on the basis of end point analysis results. Possible values = ALLOW,
        DENY

    rule(str): Name of the NetScaler named rule, or a default syntax expression, to be evaluated by the EPA tool.

    killprocess(str): String specifying the name of a process to be terminated by the EPA tool.

    deletefiles(str): String specifying the path(s) to and name(s) of the files to be deleted by the EPA tool, as a string of
        between 1 and 1023 characters.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaapreauthenticationparameter <args>

    '''

    result = {}

    payload = {'aaapreauthenticationparameter': {}}

    if preauthenticationaction:
        payload['aaapreauthenticationparameter']['preauthenticationaction'] = preauthenticationaction

    if rule:
        payload['aaapreauthenticationparameter']['rule'] = rule

    if killprocess:
        payload['aaapreauthenticationparameter']['killprocess'] = killprocess

    if deletefiles:
        payload['aaapreauthenticationparameter']['deletefiles'] = deletefiles

    execution = __proxy__['citrixns.put']('config/aaapreauthenticationparameter', payload)

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


def update_aaapreauthenticationpolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Update the running configuration for the aaapreauthenticationpolicy config key.

    name(str): Name for the preauthentication policy. Must begin with a letter, number, or the underscore character (_), and
        must consist only of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals
        (=), colon (:), and underscore characters. Cannot be changed after the preauthentication policy is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, defining connections that match the policy.

    reqaction(str): Name of the action that the policy is to invoke when a connection matches the policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaapreauthenticationpolicy <args>

    '''

    result = {}

    payload = {'aaapreauthenticationpolicy': {}}

    if name:
        payload['aaapreauthenticationpolicy']['name'] = name

    if rule:
        payload['aaapreauthenticationpolicy']['rule'] = rule

    if reqaction:
        payload['aaapreauthenticationpolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.put']('config/aaapreauthenticationpolicy', payload)

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


def update_aaaradiusparams(serverip=None, serverport=None, authtimeout=None, radkey=None, radnasip=None, radnasid=None,
                           radvendorid=None, radattributetype=None, radgroupsprefix=None, radgroupseparator=None,
                           passencoding=None, ipvendorid=None, ipattributetype=None, accounting=None, pwdvendorid=None,
                           pwdattributetype=None, defaultauthenticationgroup=None, callingstationid=None,
                           authservretry=None, authentication=None, save=False):
    '''
    Update the running configuration for the aaaradiusparams config key.

    serverip(str): IP address of your RADIUS server. Minimum length = 1

    serverport(int): Port number on which the RADIUS server listens for connections. Default value: 1812 Minimum value = 1

    authtimeout(int): Maximum number of seconds that the NetScaler appliance waits for a response from the RADIUS server.
        Default value: 3 Minimum value = 1

    radkey(str): The key shared between the RADIUS server and clients.  Required for allowing the NetScaler appliance to
        communicate with the RADIUS server. Minimum length = 1

    radnasip(str): Send the NetScaler IP (NSIP) address to the RADIUS server as the Network Access Server IP (NASIP) part of
        the Radius protocol. Possible values = ENABLED, DISABLED

    radnasid(str): Send the Network Access Server ID (NASID) for your NetScaler appliance to the RADIUS server as the nasid
        part of the Radius protocol.

    radvendorid(int): Vendor ID for RADIUS group extraction. Minimum value = 1

    radattributetype(int): Attribute type for RADIUS group extraction. Minimum value = 1

    radgroupsprefix(str): Prefix string that precedes group names within a RADIUS attribute for RADIUS group extraction.

    radgroupseparator(str): Group separator string that delimits group names within a RADIUS attribute for RADIUS group
        extraction.

    passencoding(str): Enable password encoding in RADIUS packets that the NetScaler appliance sends to the RADIUS server.
        Default value: pap Possible values = pap, chap, mschapv1, mschapv2

    ipvendorid(int): Vendor ID attribute in the RADIUS response.  If the attribute is not vendor-encoded, it is set to 0.

    ipattributetype(int): IP attribute type in the RADIUS response. Minimum value = 1

    accounting(str): Configure the RADIUS server state to accept or refuse accounting messages. Possible values = ON, OFF

    pwdvendorid(int): Vendor ID of the password in the RADIUS response. Used to extract the user password. Minimum value = 1

    pwdattributetype(int): Attribute type of the Vendor ID in the RADIUS response. Minimum value = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups. Maximum length = 64

    callingstationid(str): Send Calling-Station-ID of the client to the RADIUS server. IP Address of the client is sent as
        its Calling-Station-ID. Default value: DISABLED Possible values = ENABLED, DISABLED

    authservretry(int): Number of retry by the NetScaler appliance before getting response from the RADIUS server. Default
        value: 3 Minimum value = 1 Maximum value = 10

    authentication(str): Configure the RADIUS server state to accept or refuse authentication messages. Default value: ON
        Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaaradiusparams <args>

    '''

    result = {}

    payload = {'aaaradiusparams': {}}

    if serverip:
        payload['aaaradiusparams']['serverip'] = serverip

    if serverport:
        payload['aaaradiusparams']['serverport'] = serverport

    if authtimeout:
        payload['aaaradiusparams']['authtimeout'] = authtimeout

    if radkey:
        payload['aaaradiusparams']['radkey'] = radkey

    if radnasip:
        payload['aaaradiusparams']['radnasip'] = radnasip

    if radnasid:
        payload['aaaradiusparams']['radnasid'] = radnasid

    if radvendorid:
        payload['aaaradiusparams']['radvendorid'] = radvendorid

    if radattributetype:
        payload['aaaradiusparams']['radattributetype'] = radattributetype

    if radgroupsprefix:
        payload['aaaradiusparams']['radgroupsprefix'] = radgroupsprefix

    if radgroupseparator:
        payload['aaaradiusparams']['radgroupseparator'] = radgroupseparator

    if passencoding:
        payload['aaaradiusparams']['passencoding'] = passencoding

    if ipvendorid:
        payload['aaaradiusparams']['ipvendorid'] = ipvendorid

    if ipattributetype:
        payload['aaaradiusparams']['ipattributetype'] = ipattributetype

    if accounting:
        payload['aaaradiusparams']['accounting'] = accounting

    if pwdvendorid:
        payload['aaaradiusparams']['pwdvendorid'] = pwdvendorid

    if pwdattributetype:
        payload['aaaradiusparams']['pwdattributetype'] = pwdattributetype

    if defaultauthenticationgroup:
        payload['aaaradiusparams']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if callingstationid:
        payload['aaaradiusparams']['callingstationid'] = callingstationid

    if authservretry:
        payload['aaaradiusparams']['authservretry'] = authservretry

    if authentication:
        payload['aaaradiusparams']['authentication'] = authentication

    execution = __proxy__['citrixns.put']('config/aaaradiusparams', payload)

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


def update_aaatacacsparams(serverip=None, serverport=None, authtimeout=None, tacacssecret=None, authorization=None,
                           accounting=None, auditfailedcmds=None, groupattrname=None, defaultauthenticationgroup=None,
                           save=False):
    '''
    Update the running configuration for the aaatacacsparams config key.

    serverip(str): IP address of your TACACS+ server. Minimum length = 1

    serverport(int): Port number on which the TACACS+ server listens for connections. Default value: 49 Minimum value = 1

    authtimeout(int): Maximum number of seconds that the NetScaler appliance waits for a response from the TACACS+ server.
        Default value: 3 Minimum value = 1

    tacacssecret(str): Key shared between the TACACS+ server and clients. Required for allowing the NetScaler appliance to
        communicate with the TACACS+ server. Minimum length = 1

    authorization(str): Use streaming authorization on the TACACS+ server. Possible values = ON, OFF

    accounting(str): Send accounting messages to the TACACS+ server. Possible values = ON, OFF

    auditfailedcmds(str): The option for sending accounting messages to the TACACS+ server. Possible values = ON, OFF

    groupattrname(str): TACACS+ group attribute name.Used for group extraction on the TACACS+ server.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups. Maximum length = 64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaatacacsparams <args>

    '''

    result = {}

    payload = {'aaatacacsparams': {}}

    if serverip:
        payload['aaatacacsparams']['serverip'] = serverip

    if serverport:
        payload['aaatacacsparams']['serverport'] = serverport

    if authtimeout:
        payload['aaatacacsparams']['authtimeout'] = authtimeout

    if tacacssecret:
        payload['aaatacacsparams']['tacacssecret'] = tacacssecret

    if authorization:
        payload['aaatacacsparams']['authorization'] = authorization

    if accounting:
        payload['aaatacacsparams']['accounting'] = accounting

    if auditfailedcmds:
        payload['aaatacacsparams']['auditfailedcmds'] = auditfailedcmds

    if groupattrname:
        payload['aaatacacsparams']['groupattrname'] = groupattrname

    if defaultauthenticationgroup:
        payload['aaatacacsparams']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.put']('config/aaatacacsparams', payload)

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


def update_aaauser(username=None, password=None, loggedin=None, save=False):
    '''
    Update the running configuration for the aaauser config key.

    username(str): Name for the user. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the user is added.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my aaa user" or "my aaa user"). Minimum length = 1

    password(str): Password with which the user logs on. Required for any user account that does not exist on an external
        authentication server.  If you are not using an external authentication server, all user accounts must have a
        password. If you are using an external authentication server, you must provide a password for local user accounts
        that do not exist on the authentication server. Minimum length = 1

    loggedin(bool): Show whether the user is logged in or not.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' aaa.update_aaauser <args>

    '''

    result = {}

    payload = {'aaauser': {}}

    if username:
        payload['aaauser']['username'] = username

    if password:
        payload['aaauser']['password'] = password

    if loggedin:
        payload['aaauser']['loggedin'] = loggedin

    execution = __proxy__['citrixns.put']('config/aaauser', payload)

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
