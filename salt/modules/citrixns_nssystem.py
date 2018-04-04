# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the system key.

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

__virtualname__ = 'nssystem'


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

    return False, 'The system execution module can only be loaded for citrixns proxy minions.'


def add_systembackup(filename=None, level=None, comment=None, skipbackup=None, save=False):
    '''
    Add a new systembackup to the running configuration.

    filename(str): Name of the backup file(*.tgz) to be restored.

    level(str): Level of data to be backed up. Default value: basic Possible values = basic, full

    comment(str): Comment specified at the time of creation of the backup file(*.tgz).

    skipbackup(bool): Use this option to skip taking backup during restore operation.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systembackup <args>

    '''

    result = {}

    payload = {'systembackup': {}}

    if filename:
        payload['systembackup']['filename'] = filename

    if level:
        payload['systembackup']['level'] = level

    if comment:
        payload['systembackup']['comment'] = comment

    if skipbackup:
        payload['systembackup']['skipbackup'] = skipbackup

    execution = __proxy__['citrixns.post']('config/systembackup', payload)

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


def add_systemcmdpolicy(policyname=None, action=None, cmdspec=None, save=False):
    '''
    Add a new systemcmdpolicy to the running configuration.

    policyname(str): Name for a command policy. Must begin with a letter, number, or the underscore (_) character, and must
        contain only alphanumeric, hyphen (-), period (.), hash (#), space ( ), at (@), equal (=), colon (:), and
        underscore characters. Cannot be changed after the policy is created.  CLI Users: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my policy" or my policy).
        Minimum length = 1

    action(str): Action to perform when a request matches the policy. Possible values = ALLOW, DENY

    cmdspec(str): Regular expression specifying the data that matches the policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemcmdpolicy <args>

    '''

    result = {}

    payload = {'systemcmdpolicy': {}}

    if policyname:
        payload['systemcmdpolicy']['policyname'] = policyname

    if action:
        payload['systemcmdpolicy']['action'] = action

    if cmdspec:
        payload['systemcmdpolicy']['cmdspec'] = cmdspec

    execution = __proxy__['citrixns.post']('config/systemcmdpolicy', payload)

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


def add_systemfile(filename=None, filecontent=None, filelocation=None, fileencoding=None, save=False):
    '''
    Add a new systemfile to the running configuration.

    filename(str): Name of the file. It should not include filepath. Maximum length = 63

    filecontent(str): file content in Base64 format.

    filelocation(str): location of the file on NetScaler. Maximum length = 127

    fileencoding(str): encoding type of the file content. Default value: "BASE64"

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemfile <args>

    '''

    result = {}

    payload = {'systemfile': {}}

    if filename:
        payload['systemfile']['filename'] = filename

    if filecontent:
        payload['systemfile']['filecontent'] = filecontent

    if filelocation:
        payload['systemfile']['filelocation'] = filelocation

    if fileencoding:
        payload['systemfile']['fileencoding'] = fileencoding

    execution = __proxy__['citrixns.post']('config/systemfile', payload)

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


def add_systemglobal_auditnslogpolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                              gotopriorityexpression=None, builtin=None, policyname=None, save=False):
    '''
    Add a new systemglobal_auditnslogpolicy_binding to the running configuration.

    priority(int): The priority of the command policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    nextfactor(str): On success invoke label. Applicable for advanced authentication policy binding.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the command policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemglobal_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'systemglobal_auditnslogpolicy_binding': {}}

    if priority:
        payload['systemglobal_auditnslogpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['systemglobal_auditnslogpolicy_binding']['globalbindtype'] = globalbindtype

    if nextfactor:
        payload['systemglobal_auditnslogpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['systemglobal_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if builtin:
        payload['systemglobal_auditnslogpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['systemglobal_auditnslogpolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/systemglobal_auditnslogpolicy_binding', payload)

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


def add_systemglobal_auditsyslogpolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                               gotopriorityexpression=None, builtin=None, policyname=None, save=False):
    '''
    Add a new systemglobal_auditsyslogpolicy_binding to the running configuration.

    priority(int): The priority of the command policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    nextfactor(str): On success invoke label. Applicable for advanced authentication policy binding.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the command policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemglobal_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'systemglobal_auditsyslogpolicy_binding': {}}

    if priority:
        payload['systemglobal_auditsyslogpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['systemglobal_auditsyslogpolicy_binding']['globalbindtype'] = globalbindtype

    if nextfactor:
        payload['systemglobal_auditsyslogpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['systemglobal_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if builtin:
        payload['systemglobal_auditsyslogpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['systemglobal_auditsyslogpolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/systemglobal_auditsyslogpolicy_binding', payload)

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


def add_systemglobal_authenticationldappolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                      gotopriorityexpression=None, builtin=None, policyname=None,
                                                      save=False):
    '''
    Add a new systemglobal_authenticationldappolicy_binding to the running configuration.

    priority(int): The priority of the command policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    nextfactor(str): On success invoke label. Applicable for advanced authentication policy binding.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the command policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemglobal_authenticationldappolicy_binding <args>

    '''

    result = {}

    payload = {'systemglobal_authenticationldappolicy_binding': {}}

    if priority:
        payload['systemglobal_authenticationldappolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['systemglobal_authenticationldappolicy_binding']['globalbindtype'] = globalbindtype

    if nextfactor:
        payload['systemglobal_authenticationldappolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['systemglobal_authenticationldappolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if builtin:
        payload['systemglobal_authenticationldappolicy_binding']['builtin'] = builtin

    if policyname:
        payload['systemglobal_authenticationldappolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/systemglobal_authenticationldappolicy_binding', payload)

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


def add_systemglobal_authenticationlocalpolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                       gotopriorityexpression=None, builtin=None, policyname=None,
                                                       save=False):
    '''
    Add a new systemglobal_authenticationlocalpolicy_binding to the running configuration.

    priority(int): The priority of the command policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    nextfactor(str): On success invoke label. Applicable for advanced authentication policy binding.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the command policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemglobal_authenticationlocalpolicy_binding <args>

    '''

    result = {}

    payload = {'systemglobal_authenticationlocalpolicy_binding': {}}

    if priority:
        payload['systemglobal_authenticationlocalpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['systemglobal_authenticationlocalpolicy_binding']['globalbindtype'] = globalbindtype

    if nextfactor:
        payload['systemglobal_authenticationlocalpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['systemglobal_authenticationlocalpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if builtin:
        payload['systemglobal_authenticationlocalpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['systemglobal_authenticationlocalpolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/systemglobal_authenticationlocalpolicy_binding', payload)

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


def add_systemglobal_authenticationpolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                  gotopriorityexpression=None, builtin=None, policyname=None,
                                                  save=False):
    '''
    Add a new systemglobal_authenticationpolicy_binding to the running configuration.

    priority(int): The priority of the command policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    nextfactor(str): On success invoke label. Applicable for advanced authentication policy binding.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the command policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemglobal_authenticationpolicy_binding <args>

    '''

    result = {}

    payload = {'systemglobal_authenticationpolicy_binding': {}}

    if priority:
        payload['systemglobal_authenticationpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['systemglobal_authenticationpolicy_binding']['globalbindtype'] = globalbindtype

    if nextfactor:
        payload['systemglobal_authenticationpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['systemglobal_authenticationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if builtin:
        payload['systemglobal_authenticationpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['systemglobal_authenticationpolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/systemglobal_authenticationpolicy_binding', payload)

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


def add_systemglobal_authenticationradiuspolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                        gotopriorityexpression=None, builtin=None, policyname=None,
                                                        save=False):
    '''
    Add a new systemglobal_authenticationradiuspolicy_binding to the running configuration.

    priority(int): The priority of the command policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    nextfactor(str): On success invoke label. Applicable for advanced authentication policy binding.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the command policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemglobal_authenticationradiuspolicy_binding <args>

    '''

    result = {}

    payload = {'systemglobal_authenticationradiuspolicy_binding': {}}

    if priority:
        payload['systemglobal_authenticationradiuspolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['systemglobal_authenticationradiuspolicy_binding']['globalbindtype'] = globalbindtype

    if nextfactor:
        payload['systemglobal_authenticationradiuspolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['systemglobal_authenticationradiuspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if builtin:
        payload['systemglobal_authenticationradiuspolicy_binding']['builtin'] = builtin

    if policyname:
        payload['systemglobal_authenticationradiuspolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/systemglobal_authenticationradiuspolicy_binding', payload)

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


def add_systemglobal_authenticationtacacspolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                        gotopriorityexpression=None, builtin=None, policyname=None,
                                                        save=False):
    '''
    Add a new systemglobal_authenticationtacacspolicy_binding to the running configuration.

    priority(int): The priority of the command policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    nextfactor(str): On success invoke label. Applicable for advanced authentication policy binding.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): The name of the command policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemglobal_authenticationtacacspolicy_binding <args>

    '''

    result = {}

    payload = {'systemglobal_authenticationtacacspolicy_binding': {}}

    if priority:
        payload['systemglobal_authenticationtacacspolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['systemglobal_authenticationtacacspolicy_binding']['globalbindtype'] = globalbindtype

    if nextfactor:
        payload['systemglobal_authenticationtacacspolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['systemglobal_authenticationtacacspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if builtin:
        payload['systemglobal_authenticationtacacspolicy_binding']['builtin'] = builtin

    if policyname:
        payload['systemglobal_authenticationtacacspolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/systemglobal_authenticationtacacspolicy_binding', payload)

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


def add_systemgroup(groupname=None, promptstring=None, timeout=None, save=False):
    '''
    Add a new systemgroup to the running configuration.

    groupname(str): Name for the group. Must begin with a letter, number, or the underscore (_) character, and must contain
        only alphanumeric, hyphen (-), period (.), hash (#), space ( ), at (@), equal (=), colon (:), and underscore
        characters. Cannot be changed after the group is created.  CLI Users: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my group" or my group). Minimum length = 1

    promptstring(str): String to display at the command-line prompt. Can consist of letters, numbers, hyphen (-), period (.),
        hash (#), space ( ), at (@), equal (=), colon (:), underscore (_), and the following variables:  * %u - Will be
        replaced by the user name. * %h - Will be replaced by the hostname of the NetScaler appliance. * %t - Will be
        replaced by the current time in 12-hour format. * %T - Will be replaced by the current time in 24-hour format. *
        %d - Will be replaced by the current date. * %s - Will be replaced by the state of the NetScaler appliance.
        Note: The 63-character limit for the length of the string does not apply to the characters that replace the
        variables. Minimum length = 1

    timeout(int): CLI session inactivity timeout, in seconds. If Restrictedtimeout argument of system parameter is enabled,
        Timeout can have values in the range [300-86400] seconds.If Restrictedtimeout argument of system parameter is
        disabled, Timeout can have values in the range [0, 10-100000000] seconds. Default value is 900 seconds.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemgroup <args>

    '''

    result = {}

    payload = {'systemgroup': {}}

    if groupname:
        payload['systemgroup']['groupname'] = groupname

    if promptstring:
        payload['systemgroup']['promptstring'] = promptstring

    if timeout:
        payload['systemgroup']['timeout'] = timeout

    execution = __proxy__['citrixns.post']('config/systemgroup', payload)

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


def add_systemgroup_nspartition_binding(partitionname=None, groupname=None, save=False):
    '''
    Add a new systemgroup_nspartition_binding to the running configuration.

    partitionname(str): Name of the Partition to bind to the system group. Minimum length = 1

    groupname(str): Name of the system group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemgroup_nspartition_binding <args>

    '''

    result = {}

    payload = {'systemgroup_nspartition_binding': {}}

    if partitionname:
        payload['systemgroup_nspartition_binding']['partitionname'] = partitionname

    if groupname:
        payload['systemgroup_nspartition_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/systemgroup_nspartition_binding', payload)

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


def add_systemgroup_systemcmdpolicy_binding(priority=None, policyname=None, groupname=None, save=False):
    '''
    Add a new systemgroup_systemcmdpolicy_binding to the running configuration.

    priority(int): The priority of the command policy.

    policyname(str): The name of command policy.

    groupname(str): Name of the system group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemgroup_systemcmdpolicy_binding <args>

    '''

    result = {}

    payload = {'systemgroup_systemcmdpolicy_binding': {}}

    if priority:
        payload['systemgroup_systemcmdpolicy_binding']['priority'] = priority

    if policyname:
        payload['systemgroup_systemcmdpolicy_binding']['policyname'] = policyname

    if groupname:
        payload['systemgroup_systemcmdpolicy_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/systemgroup_systemcmdpolicy_binding', payload)

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


def add_systemgroup_systemuser_binding(username=None, groupname=None, save=False):
    '''
    Add a new systemgroup_systemuser_binding to the running configuration.

    username(str): The system user.

    groupname(str): Name of the system group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemgroup_systemuser_binding <args>

    '''

    result = {}

    payload = {'systemgroup_systemuser_binding': {}}

    if username:
        payload['systemgroup_systemuser_binding']['username'] = username

    if groupname:
        payload['systemgroup_systemuser_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/systemgroup_systemuser_binding', payload)

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


def add_systemuser(username=None, password=None, externalauth=None, promptstring=None, timeout=None, logging=None,
                   maxsession=None, save=False):
    '''
    Add a new systemuser to the running configuration.

    username(str): Name for a user. Must begin with a letter, number, or the underscore (_) character, and must contain only
        alphanumeric, hyphen (-), period (.), hash (#), space ( ), at (@), equal (=), colon (:), and underscore
        characters. Cannot be changed after the user is added.  CLI Users: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my user" or my user). Minimum length = 1

    password(str): Password for the system user. Can include any ASCII character. Minimum length = 1

    externalauth(str): Whether to use external authentication servers for the system user authentication or not. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    promptstring(str): String to display at the command-line prompt. Can consist of letters, numbers, hyphen (-), period (.),
        hash (#), space ( ), at (@), equal (=), colon (:), underscore (_), and the following variables:  * %u - Will be
        replaced by the user name. * %h - Will be replaced by the hostname of the NetScaler appliance. * %t - Will be
        replaced by the current time in 12-hour format. * %T - Will be replaced by the current time in 24-hour format. *
        %d - Will be replaced by the current date. * %s - Will be replaced by the state of the NetScaler appliance.
        Note: The 63-character limit for the length of the string does not apply to the characters that replace the
        variables. Minimum length = 1

    timeout(int): CLI session inactivity timeout, in seconds. If Restrictedtimeout argument of system parameter is enabled,
        Timeout can have values in the range [300-86400] seconds. If Restrictedtimeout argument of system parameter is
        disabled, Timeout can have values in the range [0, 10-100000000] seconds. Default value is 900 seconds.

    logging(str): Users logging privilege. Default value: DISABLED Possible values = ENABLED, DISABLED

    maxsession(int): Maximum number of client connection allowed per user. Default value: 20 Minimum value = 1 Maximum value
        = 40

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemuser <args>

    '''

    result = {}

    payload = {'systemuser': {}}

    if username:
        payload['systemuser']['username'] = username

    if password:
        payload['systemuser']['password'] = password

    if externalauth:
        payload['systemuser']['externalauth'] = externalauth

    if promptstring:
        payload['systemuser']['promptstring'] = promptstring

    if timeout:
        payload['systemuser']['timeout'] = timeout

    if logging:
        payload['systemuser']['logging'] = logging

    if maxsession:
        payload['systemuser']['maxsession'] = maxsession

    execution = __proxy__['citrixns.post']('config/systemuser', payload)

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


def add_systemuser_nspartition_binding(username=None, partitionname=None, save=False):
    '''
    Add a new systemuser_nspartition_binding to the running configuration.

    username(str): Name of the system-user entry to which to bind the command policy. Minimum length = 1

    partitionname(str): Name of the Partition to bind to the system user.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemuser_nspartition_binding <args>

    '''

    result = {}

    payload = {'systemuser_nspartition_binding': {}}

    if username:
        payload['systemuser_nspartition_binding']['username'] = username

    if partitionname:
        payload['systemuser_nspartition_binding']['partitionname'] = partitionname

    execution = __proxy__['citrixns.post']('config/systemuser_nspartition_binding', payload)

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


def add_systemuser_systemcmdpolicy_binding(priority=None, policyname=None, username=None, save=False):
    '''
    Add a new systemuser_systemcmdpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    policyname(str): The name of command policy.

    username(str): Name of the system-user entry to which to bind the command policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.add_systemuser_systemcmdpolicy_binding <args>

    '''

    result = {}

    payload = {'systemuser_systemcmdpolicy_binding': {}}

    if priority:
        payload['systemuser_systemcmdpolicy_binding']['priority'] = priority

    if policyname:
        payload['systemuser_systemcmdpolicy_binding']['policyname'] = policyname

    if username:
        payload['systemuser_systemcmdpolicy_binding']['username'] = username

    execution = __proxy__['citrixns.post']('config/systemuser_systemcmdpolicy_binding', payload)

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


def disable_systemextramgmtcpu(configuredstate=None, save=False):
    '''
    Disables a systemextramgmtcpu matching the specified filter.

    configuredstate(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.disable_systemextramgmtcpu configuredstate=foo

    '''

    result = {}

    payload = {'systemextramgmtcpu': {}}

    if configuredstate:
        payload['systemextramgmtcpu']['configuredstate'] = configuredstate
    else:
        result['result'] = 'False'
        result['error'] = 'configuredstate value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/systemextramgmtcpu?action=disable', payload)

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


def enable_systemextramgmtcpu(configuredstate=None, save=False):
    '''
    Enables a systemextramgmtcpu matching the specified filter.

    configuredstate(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.enable_systemextramgmtcpu configuredstate=foo

    '''

    result = {}

    payload = {'systemextramgmtcpu': {}}

    if configuredstate:
        payload['systemextramgmtcpu']['configuredstate'] = configuredstate
    else:
        result['result'] = 'False'
        result['error'] = 'configuredstate value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/systemextramgmtcpu?action=enable', payload)

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


def get_systembackup(filename=None, level=None, comment=None, skipbackup=None):
    '''
    Show the running configuration for the systembackup config key.

    filename(str): Filters results that only match the filename field.

    level(str): Filters results that only match the level field.

    comment(str): Filters results that only match the comment field.

    skipbackup(bool): Filters results that only match the skipbackup field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systembackup

    '''

    search_filter = []

    if filename:
        search_filter.append(['filename', filename])

    if level:
        search_filter.append(['level', level])

    if comment:
        search_filter.append(['comment', comment])

    if skipbackup:
        search_filter.append(['skipbackup', skipbackup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systembackup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systembackup')

    return response


def get_systemcmdpolicy(policyname=None, action=None, cmdspec=None):
    '''
    Show the running configuration for the systemcmdpolicy config key.

    policyname(str): Filters results that only match the policyname field.

    action(str): Filters results that only match the action field.

    cmdspec(str): Filters results that only match the cmdspec field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemcmdpolicy

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if action:
        search_filter.append(['action', action])

    if cmdspec:
        search_filter.append(['cmdspec', cmdspec])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemcmdpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemcmdpolicy')

    return response


def get_systemcollectionparam():
    '''
    Show the running configuration for the systemcollectionparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemcollectionparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemcollectionparam'), 'systemcollectionparam')

    return response


def get_systemcore():
    '''
    Show the running configuration for the systemcore config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemcore

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemcore'), 'systemcore')

    return response


def get_systemcountergroup():
    '''
    Show the running configuration for the systemcountergroup config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemcountergroup

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemcountergroup'), 'systemcountergroup')

    return response


def get_systemcounters():
    '''
    Show the running configuration for the systemcounters config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemcounters

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemcounters'), 'systemcounters')

    return response


def get_systemdatasource():
    '''
    Show the running configuration for the systemdatasource config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemdatasource

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemdatasource'), 'systemdatasource')

    return response


def get_systementity():
    '''
    Show the running configuration for the systementity config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systementity

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systementity'), 'systementity')

    return response


def get_systementitydata():
    '''
    Show the running configuration for the systementitydata config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systementitydata

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systementitydata'), 'systementitydata')

    return response


def get_systementitytype():
    '''
    Show the running configuration for the systementitytype config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systementitytype

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systementitytype'), 'systementitytype')

    return response


def get_systemeventhistory():
    '''
    Show the running configuration for the systemeventhistory config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemeventhistory

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemeventhistory'), 'systemeventhistory')

    return response


def get_systemextramgmtcpu():
    '''
    Show the running configuration for the systemextramgmtcpu config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemextramgmtcpu

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemextramgmtcpu'), 'systemextramgmtcpu')

    return response


def get_systemfile():
    '''
    Show the running configuration for the systemfile config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemfile

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemfile'), 'systemfile')

    return response


def get_systemglobal_auditnslogpolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                              gotopriorityexpression=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the systemglobal_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobal_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobal_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemglobal_auditnslogpolicy_binding')

    return response


def get_systemglobal_auditsyslogpolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                               gotopriorityexpression=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the systemglobal_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobal_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobal_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemglobal_auditsyslogpolicy_binding')

    return response


def get_systemglobal_authenticationldappolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                      gotopriorityexpression=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the systemglobal_authenticationldappolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobal_authenticationldappolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobal_authenticationldappolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemglobal_authenticationldappolicy_binding')

    return response


def get_systemglobal_authenticationlocalpolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                       gotopriorityexpression=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the systemglobal_authenticationlocalpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobal_authenticationlocalpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobal_authenticationlocalpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemglobal_authenticationlocalpolicy_binding')

    return response


def get_systemglobal_authenticationpolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                  gotopriorityexpression=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the systemglobal_authenticationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobal_authenticationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobal_authenticationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemglobal_authenticationpolicy_binding')

    return response


def get_systemglobal_authenticationradiuspolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                        gotopriorityexpression=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the systemglobal_authenticationradiuspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobal_authenticationradiuspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobal_authenticationradiuspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemglobal_authenticationradiuspolicy_binding')

    return response


def get_systemglobal_authenticationtacacspolicy_binding(priority=None, globalbindtype=None, nextfactor=None,
                                                        gotopriorityexpression=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the systemglobal_authenticationtacacspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobal_authenticationtacacspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobal_authenticationtacacspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemglobal_authenticationtacacspolicy_binding')

    return response


def get_systemglobal_binding():
    '''
    Show the running configuration for the systemglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobal_binding'), 'systemglobal_binding')

    return response


def get_systemglobaldata():
    '''
    Show the running configuration for the systemglobaldata config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemglobaldata

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemglobaldata'), 'systemglobaldata')

    return response


def get_systemgroup(groupname=None, promptstring=None, timeout=None):
    '''
    Show the running configuration for the systemgroup config key.

    groupname(str): Filters results that only match the groupname field.

    promptstring(str): Filters results that only match the promptstring field.

    timeout(int): Filters results that only match the timeout field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemgroup

    '''

    search_filter = []

    if groupname:
        search_filter.append(['groupname', groupname])

    if promptstring:
        search_filter.append(['promptstring', promptstring])

    if timeout:
        search_filter.append(['timeout', timeout])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemgroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemgroup')

    return response


def get_systemgroup_binding():
    '''
    Show the running configuration for the systemgroup_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemgroup_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemgroup_binding'), 'systemgroup_binding')

    return response


def get_systemgroup_nspartition_binding(partitionname=None, groupname=None):
    '''
    Show the running configuration for the systemgroup_nspartition_binding config key.

    partitionname(str): Filters results that only match the partitionname field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemgroup_nspartition_binding

    '''

    search_filter = []

    if partitionname:
        search_filter.append(['partitionname', partitionname])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemgroup_nspartition_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemgroup_nspartition_binding')

    return response


def get_systemgroup_systemcmdpolicy_binding(priority=None, policyname=None, groupname=None):
    '''
    Show the running configuration for the systemgroup_systemcmdpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemgroup_systemcmdpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemgroup_systemcmdpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemgroup_systemcmdpolicy_binding')

    return response


def get_systemgroup_systemuser_binding(username=None, groupname=None):
    '''
    Show the running configuration for the systemgroup_systemuser_binding config key.

    username(str): Filters results that only match the username field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemgroup_systemuser_binding

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemgroup_systemuser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemgroup_systemuser_binding')

    return response


def get_systemparameter():
    '''
    Show the running configuration for the systemparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemparameter'), 'systemparameter')

    return response


def get_systemsession(sid=None):
    '''
    Show the running configuration for the systemsession config key.

    sid(int): Filters results that only match the sid field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemsession

    '''

    search_filter = []

    if sid:
        search_filter.append(['sid', sid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemsession{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemsession')

    return response


def get_systemsshkey():
    '''
    Show the running configuration for the systemsshkey config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemsshkey

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemsshkey'), 'systemsshkey')

    return response


def get_systemuser(username=None, password=None, externalauth=None, promptstring=None, timeout=None, logging=None,
                   maxsession=None):
    '''
    Show the running configuration for the systemuser config key.

    username(str): Filters results that only match the username field.

    password(str): Filters results that only match the password field.

    externalauth(str): Filters results that only match the externalauth field.

    promptstring(str): Filters results that only match the promptstring field.

    timeout(int): Filters results that only match the timeout field.

    logging(str): Filters results that only match the logging field.

    maxsession(int): Filters results that only match the maxsession field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemuser

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if password:
        search_filter.append(['password', password])

    if externalauth:
        search_filter.append(['externalauth', externalauth])

    if promptstring:
        search_filter.append(['promptstring', promptstring])

    if timeout:
        search_filter.append(['timeout', timeout])

    if logging:
        search_filter.append(['logging', logging])

    if maxsession:
        search_filter.append(['maxsession', maxsession])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemuser{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemuser')

    return response


def get_systemuser_binding():
    '''
    Show the running configuration for the systemuser_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemuser_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemuser_binding'), 'systemuser_binding')

    return response


def get_systemuser_nspartition_binding(username=None, partitionname=None):
    '''
    Show the running configuration for the systemuser_nspartition_binding config key.

    username(str): Filters results that only match the username field.

    partitionname(str): Filters results that only match the partitionname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemuser_nspartition_binding

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if partitionname:
        search_filter.append(['partitionname', partitionname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemuser_nspartition_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemuser_nspartition_binding')

    return response


def get_systemuser_systemcmdpolicy_binding(priority=None, policyname=None, username=None):
    '''
    Show the running configuration for the systemuser_systemcmdpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    username(str): Filters results that only match the username field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemuser_systemcmdpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if username:
        search_filter.append(['username', username])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemuser_systemcmdpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemuser_systemcmdpolicy_binding')

    return response


def get_systemuser_systemgroup_binding(username=None, groupname=None):
    '''
    Show the running configuration for the systemuser_systemgroup_binding config key.

    username(str): Filters results that only match the username field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.get_systemuser_systemgroup_binding

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/systemuser_systemgroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'systemuser_systemgroup_binding')

    return response


def unset_systemcollectionparam(communityname=None, loglevel=None, datapath=None, save=False):
    '''
    Unsets values from the systemcollectionparam configuration key.

    communityname(bool): Unsets the communityname value.

    loglevel(bool): Unsets the loglevel value.

    datapath(bool): Unsets the datapath value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.unset_systemcollectionparam <args>

    '''

    result = {}

    payload = {'systemcollectionparam': {}}

    if communityname:
        payload['systemcollectionparam']['communityname'] = True

    if loglevel:
        payload['systemcollectionparam']['loglevel'] = True

    if datapath:
        payload['systemcollectionparam']['datapath'] = True

    execution = __proxy__['citrixns.post']('config/systemcollectionparam?action=unset', payload)

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


def unset_systemgroup(groupname=None, promptstring=None, timeout=None, save=False):
    '''
    Unsets values from the systemgroup configuration key.

    groupname(bool): Unsets the groupname value.

    promptstring(bool): Unsets the promptstring value.

    timeout(bool): Unsets the timeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.unset_systemgroup <args>

    '''

    result = {}

    payload = {'systemgroup': {}}

    if groupname:
        payload['systemgroup']['groupname'] = True

    if promptstring:
        payload['systemgroup']['promptstring'] = True

    if timeout:
        payload['systemgroup']['timeout'] = True

    execution = __proxy__['citrixns.post']('config/systemgroup?action=unset', payload)

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


def unset_systemparameter(rbaonresponse=None, promptstring=None, natpcbforceflushlimit=None, natpcbrstontimeout=None,
                          timeout=None, localauth=None, minpasswordlen=None, strongpassword=None, restrictedtimeout=None,
                          fipsusermode=None, doppler=None, googleanalytics=None, totalauthtimeout=None, cliloglevel=None,
                          forcepasswordchange=None, basicauth=None, save=False):
    '''
    Unsets values from the systemparameter configuration key.

    rbaonresponse(bool): Unsets the rbaonresponse value.

    promptstring(bool): Unsets the promptstring value.

    natpcbforceflushlimit(bool): Unsets the natpcbforceflushlimit value.

    natpcbrstontimeout(bool): Unsets the natpcbrstontimeout value.

    timeout(bool): Unsets the timeout value.

    localauth(bool): Unsets the localauth value.

    minpasswordlen(bool): Unsets the minpasswordlen value.

    strongpassword(bool): Unsets the strongpassword value.

    restrictedtimeout(bool): Unsets the restrictedtimeout value.

    fipsusermode(bool): Unsets the fipsusermode value.

    doppler(bool): Unsets the doppler value.

    googleanalytics(bool): Unsets the googleanalytics value.

    totalauthtimeout(bool): Unsets the totalauthtimeout value.

    cliloglevel(bool): Unsets the cliloglevel value.

    forcepasswordchange(bool): Unsets the forcepasswordchange value.

    basicauth(bool): Unsets the basicauth value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.unset_systemparameter <args>

    '''

    result = {}

    payload = {'systemparameter': {}}

    if rbaonresponse:
        payload['systemparameter']['rbaonresponse'] = True

    if promptstring:
        payload['systemparameter']['promptstring'] = True

    if natpcbforceflushlimit:
        payload['systemparameter']['natpcbforceflushlimit'] = True

    if natpcbrstontimeout:
        payload['systemparameter']['natpcbrstontimeout'] = True

    if timeout:
        payload['systemparameter']['timeout'] = True

    if localauth:
        payload['systemparameter']['localauth'] = True

    if minpasswordlen:
        payload['systemparameter']['minpasswordlen'] = True

    if strongpassword:
        payload['systemparameter']['strongpassword'] = True

    if restrictedtimeout:
        payload['systemparameter']['restrictedtimeout'] = True

    if fipsusermode:
        payload['systemparameter']['fipsusermode'] = True

    if doppler:
        payload['systemparameter']['doppler'] = True

    if googleanalytics:
        payload['systemparameter']['googleanalytics'] = True

    if totalauthtimeout:
        payload['systemparameter']['totalauthtimeout'] = True

    if cliloglevel:
        payload['systemparameter']['cliloglevel'] = True

    if forcepasswordchange:
        payload['systemparameter']['forcepasswordchange'] = True

    if basicauth:
        payload['systemparameter']['basicauth'] = True

    execution = __proxy__['citrixns.post']('config/systemparameter?action=unset', payload)

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


def unset_systemuser(username=None, password=None, externalauth=None, promptstring=None, timeout=None, logging=None,
                     maxsession=None, save=False):
    '''
    Unsets values from the systemuser configuration key.

    username(bool): Unsets the username value.

    password(bool): Unsets the password value.

    externalauth(bool): Unsets the externalauth value.

    promptstring(bool): Unsets the promptstring value.

    timeout(bool): Unsets the timeout value.

    logging(bool): Unsets the logging value.

    maxsession(bool): Unsets the maxsession value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.unset_systemuser <args>

    '''

    result = {}

    payload = {'systemuser': {}}

    if username:
        payload['systemuser']['username'] = True

    if password:
        payload['systemuser']['password'] = True

    if externalauth:
        payload['systemuser']['externalauth'] = True

    if promptstring:
        payload['systemuser']['promptstring'] = True

    if timeout:
        payload['systemuser']['timeout'] = True

    if logging:
        payload['systemuser']['logging'] = True

    if maxsession:
        payload['systemuser']['maxsession'] = True

    execution = __proxy__['citrixns.post']('config/systemuser?action=unset', payload)

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


def update_systemcmdpolicy(policyname=None, action=None, cmdspec=None, save=False):
    '''
    Update the running configuration for the systemcmdpolicy config key.

    policyname(str): Name for a command policy. Must begin with a letter, number, or the underscore (_) character, and must
        contain only alphanumeric, hyphen (-), period (.), hash (#), space ( ), at (@), equal (=), colon (:), and
        underscore characters. Cannot be changed after the policy is created.  CLI Users: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my policy" or my policy).
        Minimum length = 1

    action(str): Action to perform when a request matches the policy. Possible values = ALLOW, DENY

    cmdspec(str): Regular expression specifying the data that matches the policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.update_systemcmdpolicy <args>

    '''

    result = {}

    payload = {'systemcmdpolicy': {}}

    if policyname:
        payload['systemcmdpolicy']['policyname'] = policyname

    if action:
        payload['systemcmdpolicy']['action'] = action

    if cmdspec:
        payload['systemcmdpolicy']['cmdspec'] = cmdspec

    execution = __proxy__['citrixns.put']('config/systemcmdpolicy', payload)

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


def update_systemcollectionparam(communityname=None, loglevel=None, datapath=None, save=False):
    '''
    Update the running configuration for the systemcollectionparam config key.

    communityname(str): SNMPv1 community name for authentication.

    loglevel(str): specify the log level. Possible values CRITICAL,WARNING,INFO,DEBUG1,DEBUG2. Minimum length = 1

    datapath(str): specify the data path to the database. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.update_systemcollectionparam <args>

    '''

    result = {}

    payload = {'systemcollectionparam': {}}

    if communityname:
        payload['systemcollectionparam']['communityname'] = communityname

    if loglevel:
        payload['systemcollectionparam']['loglevel'] = loglevel

    if datapath:
        payload['systemcollectionparam']['datapath'] = datapath

    execution = __proxy__['citrixns.put']('config/systemcollectionparam', payload)

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


def update_systemgroup(groupname=None, promptstring=None, timeout=None, save=False):
    '''
    Update the running configuration for the systemgroup config key.

    groupname(str): Name for the group. Must begin with a letter, number, or the underscore (_) character, and must contain
        only alphanumeric, hyphen (-), period (.), hash (#), space ( ), at (@), equal (=), colon (:), and underscore
        characters. Cannot be changed after the group is created.  CLI Users: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my group" or my group). Minimum length = 1

    promptstring(str): String to display at the command-line prompt. Can consist of letters, numbers, hyphen (-), period (.),
        hash (#), space ( ), at (@), equal (=), colon (:), underscore (_), and the following variables:  * %u - Will be
        replaced by the user name. * %h - Will be replaced by the hostname of the NetScaler appliance. * %t - Will be
        replaced by the current time in 12-hour format. * %T - Will be replaced by the current time in 24-hour format. *
        %d - Will be replaced by the current date. * %s - Will be replaced by the state of the NetScaler appliance.
        Note: The 63-character limit for the length of the string does not apply to the characters that replace the
        variables. Minimum length = 1

    timeout(int): CLI session inactivity timeout, in seconds. If Restrictedtimeout argument of system parameter is enabled,
        Timeout can have values in the range [300-86400] seconds.If Restrictedtimeout argument of system parameter is
        disabled, Timeout can have values in the range [0, 10-100000000] seconds. Default value is 900 seconds.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.update_systemgroup <args>

    '''

    result = {}

    payload = {'systemgroup': {}}

    if groupname:
        payload['systemgroup']['groupname'] = groupname

    if promptstring:
        payload['systemgroup']['promptstring'] = promptstring

    if timeout:
        payload['systemgroup']['timeout'] = timeout

    execution = __proxy__['citrixns.put']('config/systemgroup', payload)

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


def update_systemparameter(rbaonresponse=None, promptstring=None, natpcbforceflushlimit=None, natpcbrstontimeout=None,
                           timeout=None, localauth=None, minpasswordlen=None, strongpassword=None,
                           restrictedtimeout=None, fipsusermode=None, doppler=None, googleanalytics=None,
                           totalauthtimeout=None, cliloglevel=None, forcepasswordchange=None, basicauth=None,
                           save=False):
    '''
    Update the running configuration for the systemparameter config key.

    rbaonresponse(str): Enable or disable Role-Based Authentication (RBA) on responses. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    promptstring(str): String to display at the command-line prompt. Can consist of letters, numbers, hyphen (-), period (.),
        hash (#), space ( ), at (@), equal (=), colon (:), underscore (_), and the following variables:  * %u - Will be
        replaced by the user name. * %h - Will be replaced by the hostname of the NetScaler appliance. * %t - Will be
        replaced by the current time in 12-hour format. * %T - Will be replaced by the current time in 24-hour format. *
        %d - Will be replaced by the current date. * %s - Will be replaced by the state of the NetScaler appliance.
        Note: The 63-character limit for the length of the string does not apply to the characters that replace the
        variables. Minimum length = 1

    natpcbforceflushlimit(int): Flush the system if the number of Network Address Translation Protocol Control Blocks
        (NATPCBs) exceeds this value. Default value: 2147483647 Minimum value = 1000

    natpcbrstontimeout(str): Send a reset signal to client and server connections when their NATPCBs time out. Avoids the
        buildup of idle TCP connections on both the sides. Default value: DISABLED Possible values = ENABLED, DISABLED

    timeout(int): CLI session inactivity timeout, in seconds. If Restrictedtimeout argument is enabled, Timeout can have
        values in the range [300-86400] seconds. If Restrictedtimeout argument is disabled, Timeout can have values in
        the range [0, 10-100000000] seconds. Default value is 900 seconds.

    localauth(str): When enabled, local users can access NetScaler even when external authentication is configured. When
        disabled, local users are not allowed to access the NetScaler, Local users can access the NetScaler only when the
        configured external authentication servers are unavailable. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    minpasswordlen(int): Minimum length of system user password. When strong password is enabled default minimum length is 4.
        User entered value can be greater than or equal to 4. Default mininum value is 1 when strong password is
        disabled. Maximum value is 127 in both cases. Minimum value = 1 Maximum value = 127

    strongpassword(str): After enabling strong password (enableall / enablelocal - not included in exclude list), all the
        passwords / sensitive information must have - Atleast 1 Lower case character, Atleast 1 Upper case character,
        Atleast 1 numeric character, Atleast 1 special character ( ~, `, !, @, #, $, %, ^, ;amp;, *, -, _, =, +, {, }, [,
        ], |, \\, :, ;lt;, ;gt;, /, ., ,, " "). Exclude list in case of enablelocal is - NS_FIPS, NS_CRL, NS_RSAKEY,
        NS_PKCS12, NS_PKCS8, NS_LDAP, NS_TACACS, NS_TACACSACTION, NS_RADIUS, NS_RADIUSACTION, NS_ENCRYPTION_PARAMS. So no
        Strong Password checks will be performed on these ObjectType commands for enablelocal case. Default value:
        disabled Possible values = enableall, enablelocal, disabled

    restrictedtimeout(str): Enable/Disable the restricted timeout behaviour. When enabled, timeout cannot be configured
        beyond admin configured timeout and also it will have the [minimum - maximum] range check. When disabled, timeout
        will have the old behaviour. By default the value is disabled. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    fipsusermode(str): Use this option to set the FIPS mode for key user-land processes. When enabled, these user-land
        processes will operate in FIPS mode. In this mode, theses processes will use FIPS 140-2 Level-1 certified crypto
        algorithms. Default is disabled, wherein, these user-land processes will not operate in FIPS mode. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    doppler(str): Enable or disable Doppler. Default value: 0 Possible values = ENABLED, DISABLED

    googleanalytics(str): Enable or disable Google analytics. Default value: DISABLED Possible values = ENABLED, DISABLED

    totalauthtimeout(int): Total time a request can take for authentication/authorization. Default value: 20 Minimum value =
        5 Maximum value = 120

    cliloglevel(str): Audit log level, which specifies the types of events to log for cli executed commands. Available values
        function as follows: * EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT - Events that
        might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events that indicate
        some type of error. * WARNING - Events that require action in the near future. * NOTICE - Events that the
        administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in extreme
        detail. Default value: INFORMATIONAL Possible values = EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE,
        INFORMATIONAL, DEBUG

    forcepasswordchange(str): Enable or disable force password change for nsroot user. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    basicauth(str): Enable or disable basic authentication for Nitro API. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.update_systemparameter <args>

    '''

    result = {}

    payload = {'systemparameter': {}}

    if rbaonresponse:
        payload['systemparameter']['rbaonresponse'] = rbaonresponse

    if promptstring:
        payload['systemparameter']['promptstring'] = promptstring

    if natpcbforceflushlimit:
        payload['systemparameter']['natpcbforceflushlimit'] = natpcbforceflushlimit

    if natpcbrstontimeout:
        payload['systemparameter']['natpcbrstontimeout'] = natpcbrstontimeout

    if timeout:
        payload['systemparameter']['timeout'] = timeout

    if localauth:
        payload['systemparameter']['localauth'] = localauth

    if minpasswordlen:
        payload['systemparameter']['minpasswordlen'] = minpasswordlen

    if strongpassword:
        payload['systemparameter']['strongpassword'] = strongpassword

    if restrictedtimeout:
        payload['systemparameter']['restrictedtimeout'] = restrictedtimeout

    if fipsusermode:
        payload['systemparameter']['fipsusermode'] = fipsusermode

    if doppler:
        payload['systemparameter']['doppler'] = doppler

    if googleanalytics:
        payload['systemparameter']['googleanalytics'] = googleanalytics

    if totalauthtimeout:
        payload['systemparameter']['totalauthtimeout'] = totalauthtimeout

    if cliloglevel:
        payload['systemparameter']['cliloglevel'] = cliloglevel

    if forcepasswordchange:
        payload['systemparameter']['forcepasswordchange'] = forcepasswordchange

    if basicauth:
        payload['systemparameter']['basicauth'] = basicauth

    execution = __proxy__['citrixns.put']('config/systemparameter', payload)

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


def update_systemuser(username=None, password=None, externalauth=None, promptstring=None, timeout=None, logging=None,
                      maxsession=None, save=False):
    '''
    Update the running configuration for the systemuser config key.

    username(str): Name for a user. Must begin with a letter, number, or the underscore (_) character, and must contain only
        alphanumeric, hyphen (-), period (.), hash (#), space ( ), at (@), equal (=), colon (:), and underscore
        characters. Cannot be changed after the user is added.  CLI Users: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my user" or my user). Minimum length = 1

    password(str): Password for the system user. Can include any ASCII character. Minimum length = 1

    externalauth(str): Whether to use external authentication servers for the system user authentication or not. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    promptstring(str): String to display at the command-line prompt. Can consist of letters, numbers, hyphen (-), period (.),
        hash (#), space ( ), at (@), equal (=), colon (:), underscore (_), and the following variables:  * %u - Will be
        replaced by the user name. * %h - Will be replaced by the hostname of the NetScaler appliance. * %t - Will be
        replaced by the current time in 12-hour format. * %T - Will be replaced by the current time in 24-hour format. *
        %d - Will be replaced by the current date. * %s - Will be replaced by the state of the NetScaler appliance.
        Note: The 63-character limit for the length of the string does not apply to the characters that replace the
        variables. Minimum length = 1

    timeout(int): CLI session inactivity timeout, in seconds. If Restrictedtimeout argument of system parameter is enabled,
        Timeout can have values in the range [300-86400] seconds. If Restrictedtimeout argument of system parameter is
        disabled, Timeout can have values in the range [0, 10-100000000] seconds. Default value is 900 seconds.

    logging(str): Users logging privilege. Default value: DISABLED Possible values = ENABLED, DISABLED

    maxsession(int): Maximum number of client connection allowed per user. Default value: 20 Minimum value = 1 Maximum value
        = 40

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' nssystem.update_systemuser <args>

    '''

    result = {}

    payload = {'systemuser': {}}

    if username:
        payload['systemuser']['username'] = username

    if password:
        payload['systemuser']['password'] = password

    if externalauth:
        payload['systemuser']['externalauth'] = externalauth

    if promptstring:
        payload['systemuser']['promptstring'] = promptstring

    if timeout:
        payload['systemuser']['timeout'] = timeout

    if logging:
        payload['systemuser']['logging'] = logging

    if maxsession:
        payload['systemuser']['maxsession'] = maxsession

    execution = __proxy__['citrixns.put']('config/systemuser', payload)

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
