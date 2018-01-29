# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the videooptimization key.

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

__virtualname__ = 'videooptimization'


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

    return False, 'The videooptimization execution module can only be loaded for citrixns proxy minions.'


def add_videooptimizationaction(name=None, ns_type=None, rate=None, comment=None, newname=None, save=False):
    '''
    Add a new videooptimizationaction to the running configuration.

    name(str): Name for the video optimization action. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.

    ns_type(str): Type of video optimization action. Available settings function as follows: * clear_text_pd - Cleartext PD
        type is detected. * clear_text_abr - Cleartext ABR is detected. * encrypted_abr - Encrypted ABR is detected. *
        trigger_enc_abr - Possible encrypted ABR is detected. * optimize_abr - Optimize detected ABR. Possible values =
        clear_text_pd, clear_text_abr, encrypted_abr, trigger_enc_abr, optimize_abr

    rate(int): ABR Optimization Rate (in Kbps). Default value: 1000 Minimum value = 1 Maximum value = 2147483647

    comment(str): Comment. Any type of information about this video optimization action.

    newname(str): New name for the videooptimization action. Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.add_videooptimizationaction <args>

    '''

    result = {}

    payload = {'videooptimizationaction': {}}

    if name:
        payload['videooptimizationaction']['name'] = name

    if ns_type:
        payload['videooptimizationaction']['type'] = ns_type

    if rate:
        payload['videooptimizationaction']['rate'] = rate

    if comment:
        payload['videooptimizationaction']['comment'] = comment

    if newname:
        payload['videooptimizationaction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/videooptimizationaction', payload)

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


def add_videooptimizationglobal_videooptimizationpolicy_binding(priority=None, globalbindtype=None, policyname=None,
                                                                labelname=None, gotopriorityexpression=None,
                                                                ns_type=None, invoke=None, labeltype=None, save=False):
    '''
    Add a new videooptimizationglobal_videooptimizationpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the video optimization policy.

    labelname(str): Name of the policy label to invoke. If the current policy evaluates to TRUE, the invoke parameter is set,
        and Label Type is policylabel.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    ns_type(str): Specifies the bind point whose policies you want to display. Possible values = REQ_OVERRIDE, REQ_DEFAULT,
        RES_OVERRIDE, RES_DEFAULT

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then forward the request to the specified virtual server or evaluate the specified policy label.

    labeltype(str): Type of invocation, Available settings function as follows: * vserver - Forward the request to the
        specified virtual server. * policylabel - Invoke the specified policy label. Possible values = vserver,
        policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.add_videooptimizationglobal_videooptimizationpolicy_binding <args>

    '''

    result = {}

    payload = {'videooptimizationglobal_videooptimizationpolicy_binding': {}}

    if priority:
        payload['videooptimizationglobal_videooptimizationpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['videooptimizationglobal_videooptimizationpolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['videooptimizationglobal_videooptimizationpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['videooptimizationglobal_videooptimizationpolicy_binding']['labelname'] = labelname

    if gotopriorityexpression:
        payload['videooptimizationglobal_videooptimizationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if ns_type:
        payload['videooptimizationglobal_videooptimizationpolicy_binding']['type'] = ns_type

    if invoke:
        payload['videooptimizationglobal_videooptimizationpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['videooptimizationglobal_videooptimizationpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/videooptimizationglobal_videooptimizationpolicy_binding', payload)

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


def add_videooptimizationpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                newname=None, save=False):
    '''
    Add a new videooptimizationpolicy to the running configuration.

    name(str): Name for the videooptimization policy. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters.Can be modified, removed or renamed.

    rule(str): Expression that determines which request or response match the video optimization policy. Written in default
        syntax. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;" (Classic expressions are not supported in the cluster build.)  The following
        requirements apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire
        expression in double quotation marks. * If the expression itself includes double quotation marks, escape the
        quotations by using the \\ character. * Alternatively, you can use single quotation marks to enclose the rule, in
        which case you do not have to escape the double quotation marks.

    action(str): Name of the videooptimization action to perform if the request matches this videooptimization policy.
        Built-in actions should be used. These are: * DETECT_CLEARTEXT_PD - Cleartext PD is detected and increment
        related counters. * DETECT_CLEARTEXT_ABR - Cleartext ABR is detected and increment related counters. *
        DETECT_ENCRYPTED_ABR - Encrypted ABR is detected and increment related counters. * TRIGGER_ENC_ABR_DETECTION -
        This is possible encrypted ABR. Internal traffic heuristics algorithms will further process traffic to confirm
        detection.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any type of information about this videooptimization policy.

    logaction(str): Name of the messagelog action to use for requests that match this policy.

    newname(str): New name for the videooptimization policy. Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.add_videooptimizationpolicy <args>

    '''

    result = {}

    payload = {'videooptimizationpolicy': {}}

    if name:
        payload['videooptimizationpolicy']['name'] = name

    if rule:
        payload['videooptimizationpolicy']['rule'] = rule

    if action:
        payload['videooptimizationpolicy']['action'] = action

    if undefaction:
        payload['videooptimizationpolicy']['undefaction'] = undefaction

    if comment:
        payload['videooptimizationpolicy']['comment'] = comment

    if logaction:
        payload['videooptimizationpolicy']['logaction'] = logaction

    if newname:
        payload['videooptimizationpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/videooptimizationpolicy', payload)

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


def add_videooptimizationpolicylabel(labelname=None, policylabeltype=None, comment=None, newname=None, save=False):
    '''
    Add a new videooptimizationpolicylabel to the running configuration.

    labelname(str): Name for the Video optimization policy label. Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period ( .) hash (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters. Cannot be changed after the videooptimization policy label
        is added.  The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my videooptimization policy label" or my
        videooptimization policy label).

    policylabeltype(str): Type of responses sent by the policies bound to this policy label. Types are: * HTTP - HTTP
        responses. * OTHERTCP - NON-HTTP TCP responses. Default value: NS_PLTMAP_RSP_REQ Possible values = videoopt_req,
        videoopt_res

    comment(str): Any comments to preserve information about this videooptimization policy label.

    newname(str): New name for the videooptimization policy label. Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen ( -), period (.) hash (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.add_videooptimizationpolicylabel <args>

    '''

    result = {}

    payload = {'videooptimizationpolicylabel': {}}

    if labelname:
        payload['videooptimizationpolicylabel']['labelname'] = labelname

    if policylabeltype:
        payload['videooptimizationpolicylabel']['policylabeltype'] = policylabeltype

    if comment:
        payload['videooptimizationpolicylabel']['comment'] = comment

    if newname:
        payload['videooptimizationpolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/videooptimizationpolicylabel', payload)

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


def add_videooptimizationpolicylabel_videooptimizationpolicy_binding(priority=None, policyname=None, labelname=None,
                                                                     invoke_labelname=None, gotopriorityexpression=None,
                                                                     invoke=None, labeltype=None, save=False):
    '''
    Add a new videooptimizationpolicylabel_videooptimizationpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): Name of the videooptimization policy.

    labelname(str): Name of the videooptimization policy label to which to bind the policy.

    invoke_labelname(str): * If labelType is policylabel, name of the policy label to invoke. * If labelType is reqvserver or
        resvserver, name of the virtual server.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy label
        and evaluate the specified policy label.

    labeltype(str): Type of policy label to invoke. Available settings function as follows: * vserver - Invoke an unnamed
        policy label associated with a virtual server. * policylabel - Invoke a user-defined policy label. Possible
        values = vserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.add_videooptimizationpolicylabel_videooptimizationpolicy_binding <args>

    '''

    result = {}

    payload = {'videooptimizationpolicylabel_videooptimizationpolicy_binding': {}}

    if priority:
        payload['videooptimizationpolicylabel_videooptimizationpolicy_binding']['priority'] = priority

    if policyname:
        payload['videooptimizationpolicylabel_videooptimizationpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['videooptimizationpolicylabel_videooptimizationpolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['videooptimizationpolicylabel_videooptimizationpolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['videooptimizationpolicylabel_videooptimizationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['videooptimizationpolicylabel_videooptimizationpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['videooptimizationpolicylabel_videooptimizationpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/videooptimizationpolicylabel_videooptimizationpolicy_binding', payload)

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


def get_videooptimizationaction(name=None, ns_type=None, rate=None, comment=None, newname=None):
    '''
    Show the running configuration for the videooptimizationaction config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    rate(int): Filters results that only match the rate field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if rate:
        search_filter.append(['rate', rate])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'videooptimizationaction')

    return response


def get_videooptimizationglobal_binding():
    '''
    Show the running configuration for the videooptimizationglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationglobal_binding'), 'videooptimizationglobal_binding')

    return response


def get_videooptimizationglobal_videooptimizationpolicy_binding(priority=None, globalbindtype=None, policyname=None,
                                                                labelname=None, gotopriorityexpression=None,
                                                                ns_type=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the videooptimizationglobal_videooptimizationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    ns_type(str): Filters results that only match the type field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationglobal_videooptimizationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if ns_type:
        search_filter.append(['type', ns_type])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationglobal_videooptimizationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'videooptimizationglobal_videooptimizationpolicy_binding')

    return response


def get_videooptimizationparameter():
    '''
    Show the running configuration for the videooptimizationparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationparameter'), 'videooptimizationparameter')

    return response


def get_videooptimizationpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                newname=None):
    '''
    Show the running configuration for the videooptimizationpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    if undefaction:
        search_filter.append(['undefaction', undefaction])

    if comment:
        search_filter.append(['comment', comment])

    if logaction:
        search_filter.append(['logaction', logaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'videooptimizationpolicy')

    return response


def get_videooptimizationpolicy_binding():
    '''
    Show the running configuration for the videooptimizationpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationpolicy_binding'), 'videooptimizationpolicy_binding')

    return response


def get_videooptimizationpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the videooptimizationpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'videooptimizationpolicy_lbvserver_binding')

    return response


def get_videooptimizationpolicy_videooptimizationglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the videooptimizationpolicy_videooptimizationglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationpolicy_videooptimizationglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationpolicy_videooptimizationglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'videooptimizationpolicy_videooptimizationglobal_binding')

    return response


def get_videooptimizationpolicylabel(labelname=None, policylabeltype=None, comment=None, newname=None):
    '''
    Show the running configuration for the videooptimizationpolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    policylabeltype(str): Filters results that only match the policylabeltype field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationpolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if policylabeltype:
        search_filter.append(['policylabeltype', policylabeltype])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationpolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'videooptimizationpolicylabel')

    return response


def get_videooptimizationpolicylabel_binding():
    '''
    Show the running configuration for the videooptimizationpolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationpolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationpolicylabel_binding'), 'videooptimizationpolicylabel_binding')

    return response


def get_videooptimizationpolicylabel_policybinding_binding(priority=None, policyname=None, labelname=None,
                                                           invoke_labelname=None, gotopriorityexpression=None,
                                                           invoke=None, labeltype=None):
    '''
    Show the running configuration for the videooptimizationpolicylabel_policybinding_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationpolicylabel_policybinding_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if invoke_labelname:
        search_filter.append(['invoke_labelname', invoke_labelname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationpolicylabel_policybinding_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'videooptimizationpolicylabel_policybinding_binding')

    return response


def get_videooptimizationpolicylabel_videooptimizationpolicy_binding(priority=None, policyname=None, labelname=None,
                                                                     invoke_labelname=None, gotopriorityexpression=None,
                                                                     invoke=None, labeltype=None):
    '''
    Show the running configuration for the videooptimizationpolicylabel_videooptimizationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.get_videooptimizationpolicylabel_videooptimizationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if invoke_labelname:
        search_filter.append(['invoke_labelname', invoke_labelname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/videooptimizationpolicylabel_videooptimizationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'videooptimizationpolicylabel_videooptimizationpolicy_binding')

    return response


def unset_videooptimizationaction(name=None, ns_type=None, rate=None, comment=None, newname=None, save=False):
    '''
    Unsets values from the videooptimizationaction configuration key.

    name(bool): Unsets the name value.

    ns_type(bool): Unsets the ns_type value.

    rate(bool): Unsets the rate value.

    comment(bool): Unsets the comment value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.unset_videooptimizationaction <args>

    '''

    result = {}

    payload = {'videooptimizationaction': {}}

    if name:
        payload['videooptimizationaction']['name'] = True

    if ns_type:
        payload['videooptimizationaction']['type'] = True

    if rate:
        payload['videooptimizationaction']['rate'] = True

    if comment:
        payload['videooptimizationaction']['comment'] = True

    if newname:
        payload['videooptimizationaction']['newname'] = True

    execution = __proxy__['citrixns.post']('config/videooptimizationaction?action=unset', payload)

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


def unset_videooptimizationparameter(randomsamplingpercentage=None, save=False):
    '''
    Unsets values from the videooptimizationparameter configuration key.

    randomsamplingpercentage(bool): Unsets the randomsamplingpercentage value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.unset_videooptimizationparameter <args>

    '''

    result = {}

    payload = {'videooptimizationparameter': {}}

    if randomsamplingpercentage:
        payload['videooptimizationparameter']['randomsamplingpercentage'] = True

    execution = __proxy__['citrixns.post']('config/videooptimizationparameter?action=unset', payload)

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


def unset_videooptimizationpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                  newname=None, save=False):
    '''
    Unsets values from the videooptimizationpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    undefaction(bool): Unsets the undefaction value.

    comment(bool): Unsets the comment value.

    logaction(bool): Unsets the logaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.unset_videooptimizationpolicy <args>

    '''

    result = {}

    payload = {'videooptimizationpolicy': {}}

    if name:
        payload['videooptimizationpolicy']['name'] = True

    if rule:
        payload['videooptimizationpolicy']['rule'] = True

    if action:
        payload['videooptimizationpolicy']['action'] = True

    if undefaction:
        payload['videooptimizationpolicy']['undefaction'] = True

    if comment:
        payload['videooptimizationpolicy']['comment'] = True

    if logaction:
        payload['videooptimizationpolicy']['logaction'] = True

    if newname:
        payload['videooptimizationpolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/videooptimizationpolicy?action=unset', payload)

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


def update_videooptimizationaction(name=None, ns_type=None, rate=None, comment=None, newname=None, save=False):
    '''
    Update the running configuration for the videooptimizationaction config key.

    name(str): Name for the video optimization action. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.

    ns_type(str): Type of video optimization action. Available settings function as follows: * clear_text_pd - Cleartext PD
        type is detected. * clear_text_abr - Cleartext ABR is detected. * encrypted_abr - Encrypted ABR is detected. *
        trigger_enc_abr - Possible encrypted ABR is detected. * optimize_abr - Optimize detected ABR. Possible values =
        clear_text_pd, clear_text_abr, encrypted_abr, trigger_enc_abr, optimize_abr

    rate(int): ABR Optimization Rate (in Kbps). Default value: 1000 Minimum value = 1 Maximum value = 2147483647

    comment(str): Comment. Any type of information about this video optimization action.

    newname(str): New name for the videooptimization action. Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.update_videooptimizationaction <args>

    '''

    result = {}

    payload = {'videooptimizationaction': {}}

    if name:
        payload['videooptimizationaction']['name'] = name

    if ns_type:
        payload['videooptimizationaction']['type'] = ns_type

    if rate:
        payload['videooptimizationaction']['rate'] = rate

    if comment:
        payload['videooptimizationaction']['comment'] = comment

    if newname:
        payload['videooptimizationaction']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/videooptimizationaction', payload)

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


def update_videooptimizationparameter(randomsamplingpercentage=None, save=False):
    '''
    Update the running configuration for the videooptimizationparameter config key.

    randomsamplingpercentage(int): Random Sampling Percentage. Default value: 0 Minimum value = 0 Maximum value = 100

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.update_videooptimizationparameter <args>

    '''

    result = {}

    payload = {'videooptimizationparameter': {}}

    if randomsamplingpercentage:
        payload['videooptimizationparameter']['randomsamplingpercentage'] = randomsamplingpercentage

    execution = __proxy__['citrixns.put']('config/videooptimizationparameter', payload)

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


def update_videooptimizationpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                   newname=None, save=False):
    '''
    Update the running configuration for the videooptimizationpolicy config key.

    name(str): Name for the videooptimization policy. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters.Can be modified, removed or renamed.

    rule(str): Expression that determines which request or response match the video optimization policy. Written in default
        syntax. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;" (Classic expressions are not supported in the cluster build.)  The following
        requirements apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire
        expression in double quotation marks. * If the expression itself includes double quotation marks, escape the
        quotations by using the \\ character. * Alternatively, you can use single quotation marks to enclose the rule, in
        which case you do not have to escape the double quotation marks.

    action(str): Name of the videooptimization action to perform if the request matches this videooptimization policy.
        Built-in actions should be used. These are: * DETECT_CLEARTEXT_PD - Cleartext PD is detected and increment
        related counters. * DETECT_CLEARTEXT_ABR - Cleartext ABR is detected and increment related counters. *
        DETECT_ENCRYPTED_ABR - Encrypted ABR is detected and increment related counters. * TRIGGER_ENC_ABR_DETECTION -
        This is possible encrypted ABR. Internal traffic heuristics algorithms will further process traffic to confirm
        detection.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any type of information about this videooptimization policy.

    logaction(str): Name of the messagelog action to use for requests that match this policy.

    newname(str): New name for the videooptimization policy. Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' videooptimization.update_videooptimizationpolicy <args>

    '''

    result = {}

    payload = {'videooptimizationpolicy': {}}

    if name:
        payload['videooptimizationpolicy']['name'] = name

    if rule:
        payload['videooptimizationpolicy']['rule'] = rule

    if action:
        payload['videooptimizationpolicy']['action'] = action

    if undefaction:
        payload['videooptimizationpolicy']['undefaction'] = undefaction

    if comment:
        payload['videooptimizationpolicy']['comment'] = comment

    if logaction:
        payload['videooptimizationpolicy']['logaction'] = logaction

    if newname:
        payload['videooptimizationpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/videooptimizationpolicy', payload)

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
