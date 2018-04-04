# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the compression key.

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

__virtualname__ = 'compression'


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

    return False, 'The compression execution module can only be loaded for citrixns proxy minions.'


def add_cmpaction(name=None, cmptype=None, addvaryheader=None, varyheadervalue=None, deltatype=None, newname=None,
                  save=False):
    '''
    Add a new cmpaction to the running configuration.

    name(str): Name of the compression action. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the action is added.   The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my cmp action" or my cmp action). Minimum length = 1

    cmptype(str): Type of compression performed by this action.  Available settings function as follows:  * COMPRESS - Apply
        GZIP or DEFLATE compression to the response, depending on the request header. Prefer GZIP. * GZIP - Apply GZIP
        compression. * DEFLATE - Apply DEFLATE compression. * NOCOMPRESS - Do not compress the response if the request
        matches a policy that uses this action. Possible values = compress, gzip, deflate, nocompress

    addvaryheader(str): Control insertion of the Vary header in HTTP responses compressed by NetScaler. Intermediate caches
        store different versions of the response for different values of the headers present in the Vary response header.
        Default value: GLOBAL Possible values = GLOBAL, DISABLED, ENABLED

    varyheadervalue(str): The value of the HTTP Vary header for compressed responses. Minimum length = 1

    deltatype(str): The type of delta action (if delta type compression action is defined). Default value: PERURL Possible
        values = PERURL, PERPOLICY

    newname(str): New name for the compression action. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.  Choose a name that can be correlated with the function that the action performs.   The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my cmp action" or my cmp action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.add_cmpaction <args>

    '''

    result = {}

    payload = {'cmpaction': {}}

    if name:
        payload['cmpaction']['name'] = name

    if cmptype:
        payload['cmpaction']['cmptype'] = cmptype

    if addvaryheader:
        payload['cmpaction']['addvaryheader'] = addvaryheader

    if varyheadervalue:
        payload['cmpaction']['varyheadervalue'] = varyheadervalue

    if deltatype:
        payload['cmpaction']['deltatype'] = deltatype

    if newname:
        payload['cmpaction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/cmpaction', payload)

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


def add_cmpglobal_cmppolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None, state=None,
                                    gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None, save=False):
    '''
    Add a new cmpglobal_cmppolicy_binding to the running configuration.

    priority(int): Positive integer specifying the priority of the policy. The lower the number, the higher the priority. By
        default, polices within a label are evaluated in the order of their priority numbers. In the configuration
        utility, you can click the Priority field and edit the priority level or drag the entry to a new position in the
        list. If you drag the entry to a new position, the priority level is updated automatically.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): The name of the globally bound HTTP compression policy.

    labelname(str): Name of the label to invoke if the current policy rule evaluates to TRUE. Applicable only to advanced
        (default-syntax) policies.

    state(str): The current state of the policy binding. This attribute is relevant only for CLASSIC policies. Possible
        values = ENABLED, DISABLED

    gotopriorityexpression(str): Expression or other value specifying the priority of the next policy, within the policy
        label, to evaluate if the current policy evaluates to TRUE. Specify one of the following values: * NEXT -
        Evaluate the policy with the next higher numbered priority. * END - Stop evaluation. * USE_INVOCATION_RESULT -
        Applicable if this policy invokes another policy label. If the final goto in the invoked policy label has a value
        of END, the evaluation stops. If the final goto is anything other than END, the current policy label performs a
        NEXT. * An expression that evaluates to a number. If you specify an expression, its evaluation result determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, that policy
        is evaluated next. * If the expression evaluates to the priority of the current policy, the policy with the next
        higher priority number is evaluated next. * If the expression evaluates to a priority number that is numerically
        higher than the highest priority number, policy evaluation ends. An UNDEF event is triggered if: * The expression
        is invalid. * The expression evaluates to a priority number that is numerically lower than the current policys
        priority. * The expression evaluates to a priority number that is between the current policys priority number
        (say, 30) and the highest priority number (say, 100), but does not match any configured priority number (for
        example, the expression evaluates to the number 85). This example assumes that the priority number increments by
        10 for every successive policy, and therefore a priority number of 85 does not exist in the policy label.

    invoke(bool): Invoke policies bound to a virtual server or a policy label. After the invoked policies are evaluated, the
        flow returns to the policy with the next priority. Applicable only for default-syntax policies.

    ns_type(str): Bind point to which the policy is bound. Possible values = REQ_OVERRIDE, REQ_DEFAULT, RES_OVERRIDE,
        RES_DEFAULT

    labeltype(str): Type of policy label invocation. This argument is relevant only for advanced (default-syntax) policies.
        Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.add_cmpglobal_cmppolicy_binding <args>

    '''

    result = {}

    payload = {'cmpglobal_cmppolicy_binding': {}}

    if priority:
        payload['cmpglobal_cmppolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['cmpglobal_cmppolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['cmpglobal_cmppolicy_binding']['policyname'] = policyname

    if labelname:
        payload['cmpglobal_cmppolicy_binding']['labelname'] = labelname

    if state:
        payload['cmpglobal_cmppolicy_binding']['state'] = state

    if gotopriorityexpression:
        payload['cmpglobal_cmppolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['cmpglobal_cmppolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['cmpglobal_cmppolicy_binding']['type'] = ns_type

    if labeltype:
        payload['cmpglobal_cmppolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/cmpglobal_cmppolicy_binding', payload)

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


def add_cmppolicy(name=None, rule=None, resaction=None, newname=None, save=False):
    '''
    Add a new cmppolicy to the running configuration.

    name(str): Name of the HTTP compression policy. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the policy is created.   The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my cmp policy" or my cmp policy). Minimum length = 1

    rule(str): Expression that determines which HTTP requests or responses match the compression policy. Can be a classic
        expression or a default-syntax expression.  Note: Maximum length of a string literal in the expression is 255
        characters. A longer string can be split into smaller strings of up to 255 characters each, and the smaller
        strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements apply only to
        the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression in double
        quotation marks. * If the expression itself includes double quotation marks, escape the quotations by using the
        \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks.

    resaction(str): The built-in or user-defined compression action to apply to the response when the policy matches a
        request or response. Minimum length = 1

    newname(str): New name for the compression policy. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Choose a name that reflects the function that the policy performs.   The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my cmp policy" or my cmp policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.add_cmppolicy <args>

    '''

    result = {}

    payload = {'cmppolicy': {}}

    if name:
        payload['cmppolicy']['name'] = name

    if rule:
        payload['cmppolicy']['rule'] = rule

    if resaction:
        payload['cmppolicy']['resaction'] = resaction

    if newname:
        payload['cmppolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/cmppolicy', payload)

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


def add_cmppolicylabel(labelname=None, ns_type=None, newname=None, save=False):
    '''
    Add a new cmppolicylabel to the running configuration.

    labelname(str): Name of the HTTP compression policy label. Must begin with a letter, number, or the underscore character
        (_). Additional characters allowed, after the first character, are the hyphen (-), period (.) pound sign (#),
        space ( ), at sign (@), equals (=), and colon (:). The name must be unique within the list of policy labels for
        compression policies. Can be renamed after the policy label is created.     The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my cmp policylabel" or my cmp policylabel). Minimum length = 1

    ns_type(str): Type of packets (request packets or response) against which to match the policies bound to this policy
        label. Possible values = REQ, RES

    newname(str): New name for the compression policy label. Must begin with an ASCII alphabetic or underscore (_) character,
        and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=),
        and hyphen (-) characters.    The following requirement applies only to the NetScaler CLI: If the name includes
        one or more spaces, enclose the name in double or single quotation marks (for example, "my cmp policylabel" or my
        cmp policylabel). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.add_cmppolicylabel <args>

    '''

    result = {}

    payload = {'cmppolicylabel': {}}

    if labelname:
        payload['cmppolicylabel']['labelname'] = labelname

    if ns_type:
        payload['cmppolicylabel']['type'] = ns_type

    if newname:
        payload['cmppolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/cmppolicylabel', payload)

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


def add_cmppolicylabel_cmppolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                         gotopriorityexpression=None, invoke=None, labeltype=None, save=False):
    '''
    Add a new cmppolicylabel_cmppolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): The compression policy name.

    labelname(str): Name of the HTTP compression policy label to which to bind the policy. Minimum length = 1

    invoke_labelname(str): Name of the label to invoke if the current policy evaluates to TRUE.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke policies bound to a virtual server or a user-defined policy label. After the invoked policies are
        evaluated, the flow returns to the policy with the next higher priority number in the original label.

    labeltype(str): Type of policy label invocation. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.add_cmppolicylabel_cmppolicy_binding <args>

    '''

    result = {}

    payload = {'cmppolicylabel_cmppolicy_binding': {}}

    if priority:
        payload['cmppolicylabel_cmppolicy_binding']['priority'] = priority

    if policyname:
        payload['cmppolicylabel_cmppolicy_binding']['policyname'] = policyname

    if labelname:
        payload['cmppolicylabel_cmppolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['cmppolicylabel_cmppolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['cmppolicylabel_cmppolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['cmppolicylabel_cmppolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['cmppolicylabel_cmppolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/cmppolicylabel_cmppolicy_binding', payload)

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


def get_cmpaction(name=None, cmptype=None, addvaryheader=None, varyheadervalue=None, deltatype=None, newname=None):
    '''
    Show the running configuration for the cmpaction config key.

    name(str): Filters results that only match the name field.

    cmptype(str): Filters results that only match the cmptype field.

    addvaryheader(str): Filters results that only match the addvaryheader field.

    varyheadervalue(str): Filters results that only match the varyheadervalue field.

    deltatype(str): Filters results that only match the deltatype field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmpaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if cmptype:
        search_filter.append(['cmptype', cmptype])

    if addvaryheader:
        search_filter.append(['addvaryheader', addvaryheader])

    if varyheadervalue:
        search_filter.append(['varyheadervalue', varyheadervalue])

    if deltatype:
        search_filter.append(['deltatype', deltatype])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmpaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmpaction')

    return response


def get_cmpglobal_binding():
    '''
    Show the running configuration for the cmpglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmpglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmpglobal_binding'), 'cmpglobal_binding')

    return response


def get_cmpglobal_cmppolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None, state=None,
                                    gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the cmpglobal_cmppolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    state(str): Filters results that only match the state field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    ns_type(str): Filters results that only match the type field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmpglobal_cmppolicy_binding

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

    if state:
        search_filter.append(['state', state])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if ns_type:
        search_filter.append(['type', ns_type])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmpglobal_cmppolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmpglobal_cmppolicy_binding')

    return response


def get_cmpparameter():
    '''
    Show the running configuration for the cmpparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmpparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmpparameter'), 'cmpparameter')

    return response


def get_cmppolicy(name=None, rule=None, resaction=None, newname=None):
    '''
    Show the running configuration for the cmppolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    resaction(str): Filters results that only match the resaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if resaction:
        search_filter.append(['resaction', resaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicy')

    return response


def get_cmppolicy_binding():
    '''
    Show the running configuration for the cmppolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicy_binding'), 'cmppolicy_binding')

    return response


def get_cmppolicy_cmpglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the cmppolicy_cmpglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicy_cmpglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicy_cmpglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicy_cmpglobal_binding')

    return response


def get_cmppolicy_cmppolicylabel_binding(boundto=None, name=None):
    '''
    Show the running configuration for the cmppolicy_cmppolicylabel_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicy_cmppolicylabel_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicy_cmppolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicy_cmppolicylabel_binding')

    return response


def get_cmppolicy_crvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the cmppolicy_crvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicy_crvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicy_crvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicy_crvserver_binding')

    return response


def get_cmppolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the cmppolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicy_csvserver_binding')

    return response


def get_cmppolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the cmppolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicy_lbvserver_binding')

    return response


def get_cmppolicylabel(labelname=None, ns_type=None, newname=None):
    '''
    Show the running configuration for the cmppolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    ns_type(str): Filters results that only match the type field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if ns_type:
        search_filter.append(['type', ns_type])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicylabel')

    return response


def get_cmppolicylabel_binding():
    '''
    Show the running configuration for the cmppolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cmppolicylabel_binding'), 'cmppolicylabel_binding')

    return response


def get_cmppolicylabel_cmppolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                         gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the cmppolicylabel_cmppolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicylabel_cmppolicy_binding

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
            __proxy__['citrixns.get']('config/cmppolicylabel_cmppolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicylabel_cmppolicy_binding')

    return response


def get_cmppolicylabel_policybinding_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                             gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the cmppolicylabel_policybinding_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.get_cmppolicylabel_policybinding_binding

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
            __proxy__['citrixns.get']('config/cmppolicylabel_policybinding_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cmppolicylabel_policybinding_binding')

    return response


def unset_cmpaction(name=None, cmptype=None, addvaryheader=None, varyheadervalue=None, deltatype=None, newname=None,
                    save=False):
    '''
    Unsets values from the cmpaction configuration key.

    name(bool): Unsets the name value.

    cmptype(bool): Unsets the cmptype value.

    addvaryheader(bool): Unsets the addvaryheader value.

    varyheadervalue(bool): Unsets the varyheadervalue value.

    deltatype(bool): Unsets the deltatype value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.unset_cmpaction <args>

    '''

    result = {}

    payload = {'cmpaction': {}}

    if name:
        payload['cmpaction']['name'] = True

    if cmptype:
        payload['cmpaction']['cmptype'] = True

    if addvaryheader:
        payload['cmpaction']['addvaryheader'] = True

    if varyheadervalue:
        payload['cmpaction']['varyheadervalue'] = True

    if deltatype:
        payload['cmpaction']['deltatype'] = True

    if newname:
        payload['cmpaction']['newname'] = True

    execution = __proxy__['citrixns.post']('config/cmpaction?action=unset', payload)

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


def unset_cmpparameter(cmplevel=None, quantumsize=None, servercmp=None, heurexpiry=None, heurexpirythres=None,
                       heurexpiryhistwt=None, minressize=None, cmpbypasspct=None, cmponpush=None, policytype=None,
                       addvaryheader=None, varyheadervalue=None, externalcache=None, save=False):
    '''
    Unsets values from the cmpparameter configuration key.

    cmplevel(bool): Unsets the cmplevel value.

    quantumsize(bool): Unsets the quantumsize value.

    servercmp(bool): Unsets the servercmp value.

    heurexpiry(bool): Unsets the heurexpiry value.

    heurexpirythres(bool): Unsets the heurexpirythres value.

    heurexpiryhistwt(bool): Unsets the heurexpiryhistwt value.

    minressize(bool): Unsets the minressize value.

    cmpbypasspct(bool): Unsets the cmpbypasspct value.

    cmponpush(bool): Unsets the cmponpush value.

    policytype(bool): Unsets the policytype value.

    addvaryheader(bool): Unsets the addvaryheader value.

    varyheadervalue(bool): Unsets the varyheadervalue value.

    externalcache(bool): Unsets the externalcache value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.unset_cmpparameter <args>

    '''

    result = {}

    payload = {'cmpparameter': {}}

    if cmplevel:
        payload['cmpparameter']['cmplevel'] = True

    if quantumsize:
        payload['cmpparameter']['quantumsize'] = True

    if servercmp:
        payload['cmpparameter']['servercmp'] = True

    if heurexpiry:
        payload['cmpparameter']['heurexpiry'] = True

    if heurexpirythres:
        payload['cmpparameter']['heurexpirythres'] = True

    if heurexpiryhistwt:
        payload['cmpparameter']['heurexpiryhistwt'] = True

    if minressize:
        payload['cmpparameter']['minressize'] = True

    if cmpbypasspct:
        payload['cmpparameter']['cmpbypasspct'] = True

    if cmponpush:
        payload['cmpparameter']['cmponpush'] = True

    if policytype:
        payload['cmpparameter']['policytype'] = True

    if addvaryheader:
        payload['cmpparameter']['addvaryheader'] = True

    if varyheadervalue:
        payload['cmpparameter']['varyheadervalue'] = True

    if externalcache:
        payload['cmpparameter']['externalcache'] = True

    execution = __proxy__['citrixns.post']('config/cmpparameter?action=unset', payload)

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


def update_cmpaction(name=None, cmptype=None, addvaryheader=None, varyheadervalue=None, deltatype=None, newname=None,
                     save=False):
    '''
    Update the running configuration for the cmpaction config key.

    name(str): Name of the compression action. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the action is added.   The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my cmp action" or my cmp action). Minimum length = 1

    cmptype(str): Type of compression performed by this action.  Available settings function as follows:  * COMPRESS - Apply
        GZIP or DEFLATE compression to the response, depending on the request header. Prefer GZIP. * GZIP - Apply GZIP
        compression. * DEFLATE - Apply DEFLATE compression. * NOCOMPRESS - Do not compress the response if the request
        matches a policy that uses this action. Possible values = compress, gzip, deflate, nocompress

    addvaryheader(str): Control insertion of the Vary header in HTTP responses compressed by NetScaler. Intermediate caches
        store different versions of the response for different values of the headers present in the Vary response header.
        Default value: GLOBAL Possible values = GLOBAL, DISABLED, ENABLED

    varyheadervalue(str): The value of the HTTP Vary header for compressed responses. Minimum length = 1

    deltatype(str): The type of delta action (if delta type compression action is defined). Default value: PERURL Possible
        values = PERURL, PERPOLICY

    newname(str): New name for the compression action. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.  Choose a name that can be correlated with the function that the action performs.   The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my cmp action" or my cmp action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.update_cmpaction <args>

    '''

    result = {}

    payload = {'cmpaction': {}}

    if name:
        payload['cmpaction']['name'] = name

    if cmptype:
        payload['cmpaction']['cmptype'] = cmptype

    if addvaryheader:
        payload['cmpaction']['addvaryheader'] = addvaryheader

    if varyheadervalue:
        payload['cmpaction']['varyheadervalue'] = varyheadervalue

    if deltatype:
        payload['cmpaction']['deltatype'] = deltatype

    if newname:
        payload['cmpaction']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/cmpaction', payload)

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


def update_cmpparameter(cmplevel=None, quantumsize=None, servercmp=None, heurexpiry=None, heurexpirythres=None,
                        heurexpiryhistwt=None, minressize=None, cmpbypasspct=None, cmponpush=None, policytype=None,
                        addvaryheader=None, varyheadervalue=None, externalcache=None, save=False):
    '''
    Update the running configuration for the cmpparameter config key.

    cmplevel(str): Specify a compression level. Available settings function as follows:  * Optimal - Corresponds to a gzip
        GZIP level of 5-7.  * Best speed - Corresponds to a gzip level of 1.  * Best compression - Corresponds to a gzip
        level of 9. Default value: optimal Possible values = optimal, bestspeed, bestcompression

    quantumsize(int): Minimum quantum of data to be filled before compression begins. Default value: 57344 Minimum value = 8
        Maximum value = 63488

    servercmp(str): Allow the server to send compressed data to the NetScaler appliance. With the default setting, the
        NetScaler appliance handles all compression. Default value: ON Possible values = ON, OFF

    heurexpiry(str): Heuristic basefile expiry. Default value: OFF Possible values = ON, OFF

    heurexpirythres(int): Threshold compression ratio for heuristic basefile expiry, multiplied by 100. For example, to set
        the threshold ratio to 1.25, specify 125. Default value: 100 Minimum value = 1 Maximum value = 1000

    heurexpiryhistwt(int): For heuristic basefile expiry, weightage to be given to historical delta compression ratio,
        specified as percentage. For example, to give 25% weightage to historical ratio (and therefore 75% weightage to
        the ratio for current delta compression transaction), specify 25. Default value: 50 Minimum value = 1 Maximum
        value = 100

    minressize(int): Smallest response size, in bytes, to be compressed.

    cmpbypasspct(int): NetScaler CPU threshold after which compression is not performed. Range: 0 - 100. Default value: 100
        Minimum value = 0 Maximum value = 100

    cmponpush(str): NetScaler appliance does not wait for the quantum to be filled before starting to compress data. Upon
        receipt of a packet with a PUSH flag, the appliance immediately begins compression of the accumulated packets.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    policytype(str): Type of policy. Available settings function as follows:  * Classic - Classic policies evaluate basic
        characteristics of traffic and other data.  * Advanced - Advanced policies (which have been renamed as default
        syntax policies) can perform the same type of evaluations as classic policies. They also enable you to analyze
        more data (for example, the body of an HTTP request) and to configure more operations in the policy rule (for
        example, transforming data in the body of a request into an HTTP header). Possible values = CLASSIC, ADVANCED

    addvaryheader(str): Control insertion of the Vary header in HTTP responses compressed by NetScaler. Intermediate caches
        store different versions of the response for different values of the headers present in the Vary response header.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    varyheadervalue(str): The value of the HTTP Vary header for compressed responses. If this argument is not specified, a
        default value of "Accept-Encoding" will be used. Minimum length = 1

    externalcache(str): Enable insertion of Cache-Control: private response directive to indicate response message is
        intended for a single user and must not be cached by a shared or proxy cache. Default value: NO Possible values =
        YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.update_cmpparameter <args>

    '''

    result = {}

    payload = {'cmpparameter': {}}

    if cmplevel:
        payload['cmpparameter']['cmplevel'] = cmplevel

    if quantumsize:
        payload['cmpparameter']['quantumsize'] = quantumsize

    if servercmp:
        payload['cmpparameter']['servercmp'] = servercmp

    if heurexpiry:
        payload['cmpparameter']['heurexpiry'] = heurexpiry

    if heurexpirythres:
        payload['cmpparameter']['heurexpirythres'] = heurexpirythres

    if heurexpiryhistwt:
        payload['cmpparameter']['heurexpiryhistwt'] = heurexpiryhistwt

    if minressize:
        payload['cmpparameter']['minressize'] = minressize

    if cmpbypasspct:
        payload['cmpparameter']['cmpbypasspct'] = cmpbypasspct

    if cmponpush:
        payload['cmpparameter']['cmponpush'] = cmponpush

    if policytype:
        payload['cmpparameter']['policytype'] = policytype

    if addvaryheader:
        payload['cmpparameter']['addvaryheader'] = addvaryheader

    if varyheadervalue:
        payload['cmpparameter']['varyheadervalue'] = varyheadervalue

    if externalcache:
        payload['cmpparameter']['externalcache'] = externalcache

    execution = __proxy__['citrixns.put']('config/cmpparameter', payload)

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


def update_cmppolicy(name=None, rule=None, resaction=None, newname=None, save=False):
    '''
    Update the running configuration for the cmppolicy config key.

    name(str): Name of the HTTP compression policy. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the policy is created.   The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my cmp policy" or my cmp policy). Minimum length = 1

    rule(str): Expression that determines which HTTP requests or responses match the compression policy. Can be a classic
        expression or a default-syntax expression.  Note: Maximum length of a string literal in the expression is 255
        characters. A longer string can be split into smaller strings of up to 255 characters each, and the smaller
        strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements apply only to
        the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression in double
        quotation marks. * If the expression itself includes double quotation marks, escape the quotations by using the
        \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks.

    resaction(str): The built-in or user-defined compression action to apply to the response when the policy matches a
        request or response. Minimum length = 1

    newname(str): New name for the compression policy. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Choose a name that reflects the function that the policy performs.   The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my cmp policy" or my cmp policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' compression.update_cmppolicy <args>

    '''

    result = {}

    payload = {'cmppolicy': {}}

    if name:
        payload['cmppolicy']['name'] = name

    if rule:
        payload['cmppolicy']['rule'] = rule

    if resaction:
        payload['cmppolicy']['resaction'] = resaction

    if newname:
        payload['cmppolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/cmppolicy', payload)

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
