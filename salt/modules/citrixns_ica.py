# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the ica key.

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

__virtualname__ = 'ica'


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

    return False, 'The ica execution module can only be loaded for citrixns proxy minions.'


def add_icaaccessprofile(name=None, connectclientlptports=None, clientaudioredirection=None, localremotedatasharing=None,
                         clientclipboardredirection=None, clientcomportredirection=None, clientdriveredirection=None,
                         clientprinterredirection=None, multistream=None, clientusbdriveredirection=None, save=False):
    '''
    Add a new icaaccessprofile to the running configuration.

    name(str): Name for the ICA accessprofile. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the ICA accessprofile is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my ica accessprofile" or my ica accessprofile).  Each of the
        features can be configured as DEFAULT/DISABLED. Here, DISABLED means that the policy settings on the backend
        XenApp/XenDesktop server are overridden and the NetScaler makes the decision to deny access. Whereas DEFAULT
        means that the NetScaler allows the request to reach the XenApp/XenDesktop that takes the decision to allow/deny
        access based on the policy configured on it. For example, if ClientAudioRedirection is enabled on the backend
        XenApp/XenDesktop server, and the configured profile has ClientAudioRedirection as DISABLED, the NetScaler makes
        the decision to deny the request irrespective of the configuration on the backend. If the configured profile has
        ClientAudioRedirection as DEFAULT, then the NetScaler forwards the requests to the backend XenApp/XenDesktop
        server.It then makes the decision to allow/deny access based on the policy configured on it. Minimum length = 1

    connectclientlptports(str): Allow Default access/Disable automatic connection of LPT ports from the client when the user
        logs on. Default value: DISABLED Possible values = DEFAULT, DISABLED

    clientaudioredirection(str): Allow Default access/Disable applications hosted on the server to play sounds through a
        sound device installed on the client computer, also allows or prevents users to record audio input. Default
        value: DISABLED Possible values = DEFAULT, DISABLED

    localremotedatasharing(str): Allow Default access/Disable file/data sharing via the Reciever for HTML5. Default value:
        DISABLED Possible values = DEFAULT, DISABLED

    clientclipboardredirection(str): Allow Default access/Disable the clipboard on the client device to be mapped to the
        clipboard on the server. Default value: DISABLED Possible values = DEFAULT, DISABLED

    clientcomportredirection(str): Allow Default access/Disable COM port redirection to and from the client. Default value:
        DISABLED Possible values = DEFAULT, DISABLED

    clientdriveredirection(str): Allow Default access/Disables drive redirection to and from the client. Default value:
        DISABLED Possible values = DEFAULT, DISABLED

    clientprinterredirection(str): Allow Default access/Disable client printers to be mapped to a server when a user logs on
        to a session. Default value: DISABLED Possible values = DEFAULT, DISABLED

    multistream(str): Allow Default access/Disable the multistream feature for the specified users. Default value: DISABLED
        Possible values = DEFAULT, DISABLED

    clientusbdriveredirection(str): Allow Default access/Disable the redirection of USB devices to and from the client.
        Default value: DISABLED Possible values = DEFAULT, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.add_icaaccessprofile <args>

    '''

    result = {}

    payload = {'icaaccessprofile': {}}

    if name:
        payload['icaaccessprofile']['name'] = name

    if connectclientlptports:
        payload['icaaccessprofile']['connectclientlptports'] = connectclientlptports

    if clientaudioredirection:
        payload['icaaccessprofile']['clientaudioredirection'] = clientaudioredirection

    if localremotedatasharing:
        payload['icaaccessprofile']['localremotedatasharing'] = localremotedatasharing

    if clientclipboardredirection:
        payload['icaaccessprofile']['clientclipboardredirection'] = clientclipboardredirection

    if clientcomportredirection:
        payload['icaaccessprofile']['clientcomportredirection'] = clientcomportredirection

    if clientdriveredirection:
        payload['icaaccessprofile']['clientdriveredirection'] = clientdriveredirection

    if clientprinterredirection:
        payload['icaaccessprofile']['clientprinterredirection'] = clientprinterredirection

    if multistream:
        payload['icaaccessprofile']['multistream'] = multistream

    if clientusbdriveredirection:
        payload['icaaccessprofile']['clientusbdriveredirection'] = clientusbdriveredirection

    execution = __proxy__['citrixns.post']('config/icaaccessprofile', payload)

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


def add_icaaction(name=None, accessprofilename=None, latencyprofilename=None, newname=None, save=False):
    '''
    Add a new icaaction to the running configuration.

    name(str): Name for the ICA action. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the ICA action is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my ica action" or my ica action). Minimum length = 1

    accessprofilename(str): Name of the ica accessprofile to be associated with this action.

    latencyprofilename(str): Name of the ica latencyprofile to be associated with this action.

    newname(str): New name for the ICA action. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#),period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. The following requirement applies only to the NetScaler CLI: If the name includes one or
        more spaces, enclose the name in double or single quotation marks ( for example, "my ica action" or my ica
        action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.add_icaaction <args>

    '''

    result = {}

    payload = {'icaaction': {}}

    if name:
        payload['icaaction']['name'] = name

    if accessprofilename:
        payload['icaaction']['accessprofilename'] = accessprofilename

    if latencyprofilename:
        payload['icaaction']['latencyprofilename'] = latencyprofilename

    if newname:
        payload['icaaction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/icaaction', payload)

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


def add_icaglobal_icapolicy_binding(priority=None, globalbindtype=None, policyname=None, gotopriorityexpression=None,
                                    ns_type=None, save=False):
    '''
    Add a new icaglobal_icapolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the ICA policy.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    ns_type(str): Global bind point for which to show detailed information about the policies bound to the bind point.
        Possible values = ICA_REQ_OVERRIDE, ICA_REQ_DEFAULT

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.add_icaglobal_icapolicy_binding <args>

    '''

    result = {}

    payload = {'icaglobal_icapolicy_binding': {}}

    if priority:
        payload['icaglobal_icapolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['icaglobal_icapolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['icaglobal_icapolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['icaglobal_icapolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if ns_type:
        payload['icaglobal_icapolicy_binding']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/icaglobal_icapolicy_binding', payload)

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


def add_icalatencyprofile(name=None, l7latencymonitoring=None, l7latencythresholdfactor=None, l7latencywaittime=None,
                          l7latencynotifyinterval=None, l7latencymaxnotifycount=None, save=False):
    '''
    Add a new icalatencyprofile to the running configuration.

    name(str): Name for the ICA latencyprofile. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the ICA latency profile is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my ica l7latencyprofile" or my ica l7latencyprofile). Minimum
        length = 1

    l7latencymonitoring(str): Enable/Disable L7 Latency monitoring for L7 latency notifications. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    l7latencythresholdfactor(int): L7 Latency threshold factor. This is the factor by which the active latency should be
        greater than the minimum observed value to determine that the latency is high and may need to be reported.
        Default value: 4 Minimum value = 2 Maximum value = 65535

    l7latencywaittime(int): L7 Latency Wait time. This is the time for which the Netscaler waits after the threshold is
        exceeded before it sends out a Notification to the Insight Center. Default value: 20 Minimum value = 1 Maximum
        value = 65535

    l7latencynotifyinterval(int): L7 Latency Notify Interval. This is the interval at which the Netscaler sends out
        notifications to the Insight Center after the wait time has passed. Default value: 20 Minimum value = 1 Maximum
        value = 65535

    l7latencymaxnotifycount(int): L7 Latency Max notify Count. This is the upper limit on the number of notifications sent to
        the Insight Center within an interval where the Latency is above the threshold. Default value: 5 Minimum value =
        1 Maximum value = 65535

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.add_icalatencyprofile <args>

    '''

    result = {}

    payload = {'icalatencyprofile': {}}

    if name:
        payload['icalatencyprofile']['name'] = name

    if l7latencymonitoring:
        payload['icalatencyprofile']['l7latencymonitoring'] = l7latencymonitoring

    if l7latencythresholdfactor:
        payload['icalatencyprofile']['l7latencythresholdfactor'] = l7latencythresholdfactor

    if l7latencywaittime:
        payload['icalatencyprofile']['l7latencywaittime'] = l7latencywaittime

    if l7latencynotifyinterval:
        payload['icalatencyprofile']['l7latencynotifyinterval'] = l7latencynotifyinterval

    if l7latencymaxnotifycount:
        payload['icalatencyprofile']['l7latencymaxnotifycount'] = l7latencymaxnotifycount

    execution = __proxy__['citrixns.post']('config/icalatencyprofile', payload)

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


def add_icapolicy(name=None, rule=None, action=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Add a new icapolicy to the running configuration.

    name(str): Name for the policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my ica policy" or my ica policy).

    rule(str): Expression or other value against which the traffic is evaluated. Must be a Boolean, default syntax
        expression. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character. *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Name of the ica action to be associated with this policy.

    comment(str): Any type of information about this ICA policy.

    logaction(str): Name of the messagelog action to use for requests that match this policy.

    newname(str): New name for the policy. Must begin with an ASCII alphabetic or underscore (_)character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), s pace, colon (:), at (@), equals (=), and hyphen (-)
        characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my ica policy" or my ica policy).
        Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.add_icapolicy <args>

    '''

    result = {}

    payload = {'icapolicy': {}}

    if name:
        payload['icapolicy']['name'] = name

    if rule:
        payload['icapolicy']['rule'] = rule

    if action:
        payload['icapolicy']['action'] = action

    if comment:
        payload['icapolicy']['comment'] = comment

    if logaction:
        payload['icapolicy']['logaction'] = logaction

    if newname:
        payload['icapolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/icapolicy', payload)

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


def get_icaaccessprofile(name=None, connectclientlptports=None, clientaudioredirection=None, localremotedatasharing=None,
                         clientclipboardredirection=None, clientcomportredirection=None, clientdriveredirection=None,
                         clientprinterredirection=None, multistream=None, clientusbdriveredirection=None):
    '''
    Show the running configuration for the icaaccessprofile config key.

    name(str): Filters results that only match the name field.

    connectclientlptports(str): Filters results that only match the connectclientlptports field.

    clientaudioredirection(str): Filters results that only match the clientaudioredirection field.

    localremotedatasharing(str): Filters results that only match the localremotedatasharing field.

    clientclipboardredirection(str): Filters results that only match the clientclipboardredirection field.

    clientcomportredirection(str): Filters results that only match the clientcomportredirection field.

    clientdriveredirection(str): Filters results that only match the clientdriveredirection field.

    clientprinterredirection(str): Filters results that only match the clientprinterredirection field.

    multistream(str): Filters results that only match the multistream field.

    clientusbdriveredirection(str): Filters results that only match the clientusbdriveredirection field.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icaaccessprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if connectclientlptports:
        search_filter.append(['connectclientlptports', connectclientlptports])

    if clientaudioredirection:
        search_filter.append(['clientaudioredirection', clientaudioredirection])

    if localremotedatasharing:
        search_filter.append(['localremotedatasharing', localremotedatasharing])

    if clientclipboardredirection:
        search_filter.append(['clientclipboardredirection', clientclipboardredirection])

    if clientcomportredirection:
        search_filter.append(['clientcomportredirection', clientcomportredirection])

    if clientdriveredirection:
        search_filter.append(['clientdriveredirection', clientdriveredirection])

    if clientprinterredirection:
        search_filter.append(['clientprinterredirection', clientprinterredirection])

    if multistream:
        search_filter.append(['multistream', multistream])

    if clientusbdriveredirection:
        search_filter.append(['clientusbdriveredirection', clientusbdriveredirection])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icaaccessprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'icaaccessprofile')

    return response


def get_icaaction(name=None, accessprofilename=None, latencyprofilename=None, newname=None):
    '''
    Show the running configuration for the icaaction config key.

    name(str): Filters results that only match the name field.

    accessprofilename(str): Filters results that only match the accessprofilename field.

    latencyprofilename(str): Filters results that only match the latencyprofilename field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icaaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if accessprofilename:
        search_filter.append(['accessprofilename', accessprofilename])

    if latencyprofilename:
        search_filter.append(['latencyprofilename', latencyprofilename])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icaaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'icaaction')

    return response


def get_icaglobal_binding():
    '''
    Show the running configuration for the icaglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icaglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icaglobal_binding'), 'icaglobal_binding')

    return response


def get_icaglobal_icapolicy_binding(priority=None, globalbindtype=None, policyname=None, gotopriorityexpression=None,
                                    ns_type=None):
    '''
    Show the running configuration for the icaglobal_icapolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icaglobal_icapolicy_binding

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
            __proxy__['citrixns.get']('config/icaglobal_icapolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'icaglobal_icapolicy_binding')

    return response


def get_icalatencyprofile(name=None, l7latencymonitoring=None, l7latencythresholdfactor=None, l7latencywaittime=None,
                          l7latencynotifyinterval=None, l7latencymaxnotifycount=None):
    '''
    Show the running configuration for the icalatencyprofile config key.

    name(str): Filters results that only match the name field.

    l7latencymonitoring(str): Filters results that only match the l7latencymonitoring field.

    l7latencythresholdfactor(int): Filters results that only match the l7latencythresholdfactor field.

    l7latencywaittime(int): Filters results that only match the l7latencywaittime field.

    l7latencynotifyinterval(int): Filters results that only match the l7latencynotifyinterval field.

    l7latencymaxnotifycount(int): Filters results that only match the l7latencymaxnotifycount field.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icalatencyprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if l7latencymonitoring:
        search_filter.append(['l7latencymonitoring', l7latencymonitoring])

    if l7latencythresholdfactor:
        search_filter.append(['l7latencythresholdfactor', l7latencythresholdfactor])

    if l7latencywaittime:
        search_filter.append(['l7latencywaittime', l7latencywaittime])

    if l7latencynotifyinterval:
        search_filter.append(['l7latencynotifyinterval', l7latencynotifyinterval])

    if l7latencymaxnotifycount:
        search_filter.append(['l7latencymaxnotifycount', l7latencymaxnotifycount])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icalatencyprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'icalatencyprofile')

    return response


def get_icaparameter():
    '''
    Show the running configuration for the icaparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icaparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icaparameter'), 'icaparameter')

    return response


def get_icapolicy(name=None, rule=None, action=None, comment=None, logaction=None, newname=None):
    '''
    Show the running configuration for the icapolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icapolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    if comment:
        search_filter.append(['comment', comment])

    if logaction:
        search_filter.append(['logaction', logaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icapolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'icapolicy')

    return response


def get_icapolicy_binding():
    '''
    Show the running configuration for the icapolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icapolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icapolicy_binding'), 'icapolicy_binding')

    return response


def get_icapolicy_crvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the icapolicy_crvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icapolicy_crvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icapolicy_crvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'icapolicy_crvserver_binding')

    return response


def get_icapolicy_icaglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the icapolicy_icaglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icapolicy_icaglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icapolicy_icaglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'icapolicy_icaglobal_binding')

    return response


def get_icapolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the icapolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.get_icapolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/icapolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'icapolicy_vpnvserver_binding')

    return response


def unset_icaaccessprofile(name=None, connectclientlptports=None, clientaudioredirection=None,
                           localremotedatasharing=None, clientclipboardredirection=None, clientcomportredirection=None,
                           clientdriveredirection=None, clientprinterredirection=None, multistream=None,
                           clientusbdriveredirection=None, save=False):
    '''
    Unsets values from the icaaccessprofile configuration key.

    name(bool): Unsets the name value.

    connectclientlptports(bool): Unsets the connectclientlptports value.

    clientaudioredirection(bool): Unsets the clientaudioredirection value.

    localremotedatasharing(bool): Unsets the localremotedatasharing value.

    clientclipboardredirection(bool): Unsets the clientclipboardredirection value.

    clientcomportredirection(bool): Unsets the clientcomportredirection value.

    clientdriveredirection(bool): Unsets the clientdriveredirection value.

    clientprinterredirection(bool): Unsets the clientprinterredirection value.

    multistream(bool): Unsets the multistream value.

    clientusbdriveredirection(bool): Unsets the clientusbdriveredirection value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.unset_icaaccessprofile <args>

    '''

    result = {}

    payload = {'icaaccessprofile': {}}

    if name:
        payload['icaaccessprofile']['name'] = True

    if connectclientlptports:
        payload['icaaccessprofile']['connectclientlptports'] = True

    if clientaudioredirection:
        payload['icaaccessprofile']['clientaudioredirection'] = True

    if localremotedatasharing:
        payload['icaaccessprofile']['localremotedatasharing'] = True

    if clientclipboardredirection:
        payload['icaaccessprofile']['clientclipboardredirection'] = True

    if clientcomportredirection:
        payload['icaaccessprofile']['clientcomportredirection'] = True

    if clientdriveredirection:
        payload['icaaccessprofile']['clientdriveredirection'] = True

    if clientprinterredirection:
        payload['icaaccessprofile']['clientprinterredirection'] = True

    if multistream:
        payload['icaaccessprofile']['multistream'] = True

    if clientusbdriveredirection:
        payload['icaaccessprofile']['clientusbdriveredirection'] = True

    execution = __proxy__['citrixns.post']('config/icaaccessprofile?action=unset', payload)

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


def unset_icaaction(name=None, accessprofilename=None, latencyprofilename=None, newname=None, save=False):
    '''
    Unsets values from the icaaction configuration key.

    name(bool): Unsets the name value.

    accessprofilename(bool): Unsets the accessprofilename value.

    latencyprofilename(bool): Unsets the latencyprofilename value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.unset_icaaction <args>

    '''

    result = {}

    payload = {'icaaction': {}}

    if name:
        payload['icaaction']['name'] = True

    if accessprofilename:
        payload['icaaction']['accessprofilename'] = True

    if latencyprofilename:
        payload['icaaction']['latencyprofilename'] = True

    if newname:
        payload['icaaction']['newname'] = True

    execution = __proxy__['citrixns.post']('config/icaaction?action=unset', payload)

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


def unset_icalatencyprofile(name=None, l7latencymonitoring=None, l7latencythresholdfactor=None, l7latencywaittime=None,
                            l7latencynotifyinterval=None, l7latencymaxnotifycount=None, save=False):
    '''
    Unsets values from the icalatencyprofile configuration key.

    name(bool): Unsets the name value.

    l7latencymonitoring(bool): Unsets the l7latencymonitoring value.

    l7latencythresholdfactor(bool): Unsets the l7latencythresholdfactor value.

    l7latencywaittime(bool): Unsets the l7latencywaittime value.

    l7latencynotifyinterval(bool): Unsets the l7latencynotifyinterval value.

    l7latencymaxnotifycount(bool): Unsets the l7latencymaxnotifycount value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.unset_icalatencyprofile <args>

    '''

    result = {}

    payload = {'icalatencyprofile': {}}

    if name:
        payload['icalatencyprofile']['name'] = True

    if l7latencymonitoring:
        payload['icalatencyprofile']['l7latencymonitoring'] = True

    if l7latencythresholdfactor:
        payload['icalatencyprofile']['l7latencythresholdfactor'] = True

    if l7latencywaittime:
        payload['icalatencyprofile']['l7latencywaittime'] = True

    if l7latencynotifyinterval:
        payload['icalatencyprofile']['l7latencynotifyinterval'] = True

    if l7latencymaxnotifycount:
        payload['icalatencyprofile']['l7latencymaxnotifycount'] = True

    execution = __proxy__['citrixns.post']('config/icalatencyprofile?action=unset', payload)

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


def unset_icaparameter(enablesronhafailover=None, save=False):
    '''
    Unsets values from the icaparameter configuration key.

    enablesronhafailover(bool): Unsets the enablesronhafailover value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.unset_icaparameter <args>

    '''

    result = {}

    payload = {'icaparameter': {}}

    if enablesronhafailover:
        payload['icaparameter']['enablesronhafailover'] = True

    execution = __proxy__['citrixns.post']('config/icaparameter?action=unset', payload)

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


def unset_icapolicy(name=None, rule=None, action=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Unsets values from the icapolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    comment(bool): Unsets the comment value.

    logaction(bool): Unsets the logaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.unset_icapolicy <args>

    '''

    result = {}

    payload = {'icapolicy': {}}

    if name:
        payload['icapolicy']['name'] = True

    if rule:
        payload['icapolicy']['rule'] = True

    if action:
        payload['icapolicy']['action'] = True

    if comment:
        payload['icapolicy']['comment'] = True

    if logaction:
        payload['icapolicy']['logaction'] = True

    if newname:
        payload['icapolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/icapolicy?action=unset', payload)

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


def update_icaaccessprofile(name=None, connectclientlptports=None, clientaudioredirection=None,
                            localremotedatasharing=None, clientclipboardredirection=None, clientcomportredirection=None,
                            clientdriveredirection=None, clientprinterredirection=None, multistream=None,
                            clientusbdriveredirection=None, save=False):
    '''
    Update the running configuration for the icaaccessprofile config key.

    name(str): Name for the ICA accessprofile. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the ICA accessprofile is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my ica accessprofile" or my ica accessprofile).  Each of the
        features can be configured as DEFAULT/DISABLED. Here, DISABLED means that the policy settings on the backend
        XenApp/XenDesktop server are overridden and the NetScaler makes the decision to deny access. Whereas DEFAULT
        means that the NetScaler allows the request to reach the XenApp/XenDesktop that takes the decision to allow/deny
        access based on the policy configured on it. For example, if ClientAudioRedirection is enabled on the backend
        XenApp/XenDesktop server, and the configured profile has ClientAudioRedirection as DISABLED, the NetScaler makes
        the decision to deny the request irrespective of the configuration on the backend. If the configured profile has
        ClientAudioRedirection as DEFAULT, then the NetScaler forwards the requests to the backend XenApp/XenDesktop
        server.It then makes the decision to allow/deny access based on the policy configured on it. Minimum length = 1

    connectclientlptports(str): Allow Default access/Disable automatic connection of LPT ports from the client when the user
        logs on. Default value: DISABLED Possible values = DEFAULT, DISABLED

    clientaudioredirection(str): Allow Default access/Disable applications hosted on the server to play sounds through a
        sound device installed on the client computer, also allows or prevents users to record audio input. Default
        value: DISABLED Possible values = DEFAULT, DISABLED

    localremotedatasharing(str): Allow Default access/Disable file/data sharing via the Reciever for HTML5. Default value:
        DISABLED Possible values = DEFAULT, DISABLED

    clientclipboardredirection(str): Allow Default access/Disable the clipboard on the client device to be mapped to the
        clipboard on the server. Default value: DISABLED Possible values = DEFAULT, DISABLED

    clientcomportredirection(str): Allow Default access/Disable COM port redirection to and from the client. Default value:
        DISABLED Possible values = DEFAULT, DISABLED

    clientdriveredirection(str): Allow Default access/Disables drive redirection to and from the client. Default value:
        DISABLED Possible values = DEFAULT, DISABLED

    clientprinterredirection(str): Allow Default access/Disable client printers to be mapped to a server when a user logs on
        to a session. Default value: DISABLED Possible values = DEFAULT, DISABLED

    multistream(str): Allow Default access/Disable the multistream feature for the specified users. Default value: DISABLED
        Possible values = DEFAULT, DISABLED

    clientusbdriveredirection(str): Allow Default access/Disable the redirection of USB devices to and from the client.
        Default value: DISABLED Possible values = DEFAULT, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.update_icaaccessprofile <args>

    '''

    result = {}

    payload = {'icaaccessprofile': {}}

    if name:
        payload['icaaccessprofile']['name'] = name

    if connectclientlptports:
        payload['icaaccessprofile']['connectclientlptports'] = connectclientlptports

    if clientaudioredirection:
        payload['icaaccessprofile']['clientaudioredirection'] = clientaudioredirection

    if localremotedatasharing:
        payload['icaaccessprofile']['localremotedatasharing'] = localremotedatasharing

    if clientclipboardredirection:
        payload['icaaccessprofile']['clientclipboardredirection'] = clientclipboardredirection

    if clientcomportredirection:
        payload['icaaccessprofile']['clientcomportredirection'] = clientcomportredirection

    if clientdriveredirection:
        payload['icaaccessprofile']['clientdriveredirection'] = clientdriveredirection

    if clientprinterredirection:
        payload['icaaccessprofile']['clientprinterredirection'] = clientprinterredirection

    if multistream:
        payload['icaaccessprofile']['multistream'] = multistream

    if clientusbdriveredirection:
        payload['icaaccessprofile']['clientusbdriveredirection'] = clientusbdriveredirection

    execution = __proxy__['citrixns.put']('config/icaaccessprofile', payload)

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


def update_icaaction(name=None, accessprofilename=None, latencyprofilename=None, newname=None, save=False):
    '''
    Update the running configuration for the icaaction config key.

    name(str): Name for the ICA action. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the ICA action is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my ica action" or my ica action). Minimum length = 1

    accessprofilename(str): Name of the ica accessprofile to be associated with this action.

    latencyprofilename(str): Name of the ica latencyprofile to be associated with this action.

    newname(str): New name for the ICA action. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#),period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. The following requirement applies only to the NetScaler CLI: If the name includes one or
        more spaces, enclose the name in double or single quotation marks ( for example, "my ica action" or my ica
        action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.update_icaaction <args>

    '''

    result = {}

    payload = {'icaaction': {}}

    if name:
        payload['icaaction']['name'] = name

    if accessprofilename:
        payload['icaaction']['accessprofilename'] = accessprofilename

    if latencyprofilename:
        payload['icaaction']['latencyprofilename'] = latencyprofilename

    if newname:
        payload['icaaction']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/icaaction', payload)

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


def update_icalatencyprofile(name=None, l7latencymonitoring=None, l7latencythresholdfactor=None, l7latencywaittime=None,
                             l7latencynotifyinterval=None, l7latencymaxnotifycount=None, save=False):
    '''
    Update the running configuration for the icalatencyprofile config key.

    name(str): Name for the ICA latencyprofile. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the ICA latency profile is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my ica l7latencyprofile" or my ica l7latencyprofile). Minimum
        length = 1

    l7latencymonitoring(str): Enable/Disable L7 Latency monitoring for L7 latency notifications. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    l7latencythresholdfactor(int): L7 Latency threshold factor. This is the factor by which the active latency should be
        greater than the minimum observed value to determine that the latency is high and may need to be reported.
        Default value: 4 Minimum value = 2 Maximum value = 65535

    l7latencywaittime(int): L7 Latency Wait time. This is the time for which the Netscaler waits after the threshold is
        exceeded before it sends out a Notification to the Insight Center. Default value: 20 Minimum value = 1 Maximum
        value = 65535

    l7latencynotifyinterval(int): L7 Latency Notify Interval. This is the interval at which the Netscaler sends out
        notifications to the Insight Center after the wait time has passed. Default value: 20 Minimum value = 1 Maximum
        value = 65535

    l7latencymaxnotifycount(int): L7 Latency Max notify Count. This is the upper limit on the number of notifications sent to
        the Insight Center within an interval where the Latency is above the threshold. Default value: 5 Minimum value =
        1 Maximum value = 65535

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.update_icalatencyprofile <args>

    '''

    result = {}

    payload = {'icalatencyprofile': {}}

    if name:
        payload['icalatencyprofile']['name'] = name

    if l7latencymonitoring:
        payload['icalatencyprofile']['l7latencymonitoring'] = l7latencymonitoring

    if l7latencythresholdfactor:
        payload['icalatencyprofile']['l7latencythresholdfactor'] = l7latencythresholdfactor

    if l7latencywaittime:
        payload['icalatencyprofile']['l7latencywaittime'] = l7latencywaittime

    if l7latencynotifyinterval:
        payload['icalatencyprofile']['l7latencynotifyinterval'] = l7latencynotifyinterval

    if l7latencymaxnotifycount:
        payload['icalatencyprofile']['l7latencymaxnotifycount'] = l7latencymaxnotifycount

    execution = __proxy__['citrixns.put']('config/icalatencyprofile', payload)

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


def update_icaparameter(enablesronhafailover=None, save=False):
    '''
    Update the running configuration for the icaparameter config key.

    enablesronhafailover(str): Enable/Disable Session Reliability on HA failover. The default value is No. Default value: NO
        Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.update_icaparameter <args>

    '''

    result = {}

    payload = {'icaparameter': {}}

    if enablesronhafailover:
        payload['icaparameter']['enablesronhafailover'] = enablesronhafailover

    execution = __proxy__['citrixns.put']('config/icaparameter', payload)

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


def update_icapolicy(name=None, rule=None, action=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Update the running configuration for the icapolicy config key.

    name(str): Name for the policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my ica policy" or my ica policy).

    rule(str): Expression or other value against which the traffic is evaluated. Must be a Boolean, default syntax
        expression. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character. *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Name of the ica action to be associated with this policy.

    comment(str): Any type of information about this ICA policy.

    logaction(str): Name of the messagelog action to use for requests that match this policy.

    newname(str): New name for the policy. Must begin with an ASCII alphabetic or underscore (_)character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), s pace, colon (:), at (@), equals (=), and hyphen (-)
        characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my ica policy" or my ica policy).
        Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ica.update_icapolicy <args>

    '''

    result = {}

    payload = {'icapolicy': {}}

    if name:
        payload['icapolicy']['name'] = name

    if rule:
        payload['icapolicy']['rule'] = rule

    if action:
        payload['icapolicy']['action'] = action

    if comment:
        payload['icapolicy']['comment'] = comment

    if logaction:
        payload['icapolicy']['logaction'] = logaction

    if newname:
        payload['icapolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/icapolicy', payload)

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
