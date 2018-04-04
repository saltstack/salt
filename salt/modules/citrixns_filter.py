# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the filter key.

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

__virtualname__ = 'filter'


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

    return False, 'The filter execution module can only be loaded for citrixns proxy minions.'


def add_filteraction(name=None, qual=None, servicename=None, value=None, respcode=None, page=None, save=False):
    '''
    Add a new filteraction to the running configuration.

    name(str): Name for the filtering action. Must begin with a letter, number, or the underscore character (_). Other
        characters allowed, after the first character, are the hyphen (-), period (.) hash (#), space ( ), at sign (@),
        equals (=), and colon (:) characters. Choose a name that helps identify the type of action. The name of a filter
        action cannot be changed after it is created.  CLI Users: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    qual(str): Qualifier, which is the action to be performed. The qualifier cannot be changed after it is set. The available
        options function as follows: ADD - Adds the specified HTTP header. RESET - Terminates the connection, sending the
        appropriate termination notice to the users browser. FORWARD - Redirects the request to the designated service.
        You must specify either a service name or a page, but not both. DROP - Silently deletes the request, without
        sending a response to the users browser.  CORRUPT - Modifies the designated HTTP header to prevent it from
        performing the function it was intended to perform, then sends the request/response to the server/browser.
        ERRORCODE. Returns the designated HTTP error code to the users browser (for example, 404, the standard HTTP code
        for a non-existent Web page). Possible values = reset, add, corrupt, forward, errorcode, drop

    servicename(str): Service to which to forward HTTP requests. Required if the qualifier is FORWARD. Minimum length = 1

    value(str): String containing the header_name and header_value. If the qualifier is ADD, specify
        ;lt;header_name;gt;:;lt;header_value;gt;. If the qualifier is CORRUPT, specify only the header_name. Minimum
        length = 1

    respcode(int): Response code to be returned for HTTP requests (for use with the ERRORCODE qualifier). Minimum value = 1

    page(str): HTML page to return for HTTP requests (For use with the ERRORCODE qualifier). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.add_filteraction <args>

    '''

    result = {}

    payload = {'filteraction': {}}

    if name:
        payload['filteraction']['name'] = name

    if qual:
        payload['filteraction']['qual'] = qual

    if servicename:
        payload['filteraction']['servicename'] = servicename

    if value:
        payload['filteraction']['value'] = value

    if respcode:
        payload['filteraction']['respcode'] = respcode

    if page:
        payload['filteraction']['page'] = page

    execution = __proxy__['citrixns.post']('config/filteraction', payload)

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


def add_filterglobal_filterpolicy_binding(priority=None, state=None, policyname=None, save=False):
    '''
    Add a new filterglobal_filterpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    state(str): State of the binding. Possible values = ENABLED, DISABLED

    policyname(str): The name of the filter policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.add_filterglobal_filterpolicy_binding <args>

    '''

    result = {}

    payload = {'filterglobal_filterpolicy_binding': {}}

    if priority:
        payload['filterglobal_filterpolicy_binding']['priority'] = priority

    if state:
        payload['filterglobal_filterpolicy_binding']['state'] = state

    if policyname:
        payload['filterglobal_filterpolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/filterglobal_filterpolicy_binding', payload)

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


def add_filterhtmlinjectionvariable(variable=None, value=None, save=False):
    '''
    Add a new filterhtmlinjectionvariable to the running configuration.

    variable(str): Name for the HTML injection variable to be added. Minimum length = 1 Maximum length = 31

    value(str): Value to be assigned to the new variable. Minimum length = 1 Maximum length = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.add_filterhtmlinjectionvariable <args>

    '''

    result = {}

    payload = {'filterhtmlinjectionvariable': {}}

    if variable:
        payload['filterhtmlinjectionvariable']['variable'] = variable

    if value:
        payload['filterhtmlinjectionvariable']['value'] = value

    execution = __proxy__['citrixns.post']('config/filterhtmlinjectionvariable', payload)

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


def add_filterpolicy(name=None, rule=None, reqaction=None, resaction=None, save=False):
    '''
    Add a new filterpolicy to the running configuration.

    name(str): Name for the filtering action. Must begin with a letter, number, or the underscore character (_). Other
        characters allowed, after the first character, are the hyphen (-), period (.) pound (#), space ( ), at (@),
        equals (=), and colon (:) characters. Choose a name that helps identify the type of action. The name cannot be
        updated after the policy is created.  CLI Users: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    rule(str): NetScaler classic expression specifying the type of connections that match this policy. Minimum length = 1

    reqaction(str): Name of the action to be performed on requests that match the policy. Cannot be specified if the rule
        includes condition to be evaluated for responses. Minimum length = 1

    resaction(str): The action to be performed on the response. The string value can be a filter action created filter action
        or a built-in action. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.add_filterpolicy <args>

    '''

    result = {}

    payload = {'filterpolicy': {}}

    if name:
        payload['filterpolicy']['name'] = name

    if rule:
        payload['filterpolicy']['rule'] = rule

    if reqaction:
        payload['filterpolicy']['reqaction'] = reqaction

    if resaction:
        payload['filterpolicy']['resaction'] = resaction

    execution = __proxy__['citrixns.post']('config/filterpolicy', payload)

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


def get_filteraction(name=None, qual=None, servicename=None, value=None, respcode=None, page=None):
    '''
    Show the running configuration for the filteraction config key.

    name(str): Filters results that only match the name field.

    qual(str): Filters results that only match the qual field.

    servicename(str): Filters results that only match the servicename field.

    value(str): Filters results that only match the value field.

    respcode(int): Filters results that only match the respcode field.

    page(str): Filters results that only match the page field.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filteraction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if qual:
        search_filter.append(['qual', qual])

    if servicename:
        search_filter.append(['servicename', servicename])

    if value:
        search_filter.append(['value', value])

    if respcode:
        search_filter.append(['respcode', respcode])

    if page:
        search_filter.append(['page', page])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filteraction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'filteraction')

    return response


def get_filterglobal_binding():
    '''
    Show the running configuration for the filterglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterglobal_binding'), 'filterglobal_binding')

    return response


def get_filterglobal_filterpolicy_binding(priority=None, state=None, policyname=None):
    '''
    Show the running configuration for the filterglobal_filterpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    state(str): Filters results that only match the state field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterglobal_filterpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if state:
        search_filter.append(['state', state])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterglobal_filterpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'filterglobal_filterpolicy_binding')

    return response


def get_filterhtmlinjectionparameter():
    '''
    Show the running configuration for the filterhtmlinjectionparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterhtmlinjectionparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterhtmlinjectionparameter'), 'filterhtmlinjectionparameter')

    return response


def get_filterhtmlinjectionvariable(variable=None, value=None):
    '''
    Show the running configuration for the filterhtmlinjectionvariable config key.

    variable(str): Filters results that only match the variable field.

    value(str): Filters results that only match the value field.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterhtmlinjectionvariable

    '''

    search_filter = []

    if variable:
        search_filter.append(['variable', variable])

    if value:
        search_filter.append(['value', value])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterhtmlinjectionvariable{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'filterhtmlinjectionvariable')

    return response


def get_filterpolicy(name=None, rule=None, reqaction=None, resaction=None):
    '''
    Show the running configuration for the filterpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    resaction(str): Filters results that only match the resaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    if resaction:
        search_filter.append(['resaction', resaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'filterpolicy')

    return response


def get_filterpolicy_binding():
    '''
    Show the running configuration for the filterpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterpolicy_binding'), 'filterpolicy_binding')

    return response


def get_filterpolicy_crvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the filterpolicy_crvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterpolicy_crvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterpolicy_crvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'filterpolicy_crvserver_binding')

    return response


def get_filterpolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the filterpolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterpolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'filterpolicy_csvserver_binding')

    return response


def get_filterpolicy_filterglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the filterpolicy_filterglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterpolicy_filterglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterpolicy_filterglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'filterpolicy_filterglobal_binding')

    return response


def get_filterpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the filterpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'filterpolicy_lbvserver_binding')

    return response


def get_filterpostbodyinjection():
    '''
    Show the running configuration for the filterpostbodyinjection config key.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterpostbodyinjection

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterpostbodyinjection'), 'filterpostbodyinjection')

    return response


def get_filterprebodyinjection():
    '''
    Show the running configuration for the filterprebodyinjection config key.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.get_filterprebodyinjection

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/filterprebodyinjection'), 'filterprebodyinjection')

    return response


def unset_filteraction(name=None, qual=None, servicename=None, value=None, respcode=None, page=None, save=False):
    '''
    Unsets values from the filteraction configuration key.

    name(bool): Unsets the name value.

    qual(bool): Unsets the qual value.

    servicename(bool): Unsets the servicename value.

    value(bool): Unsets the value value.

    respcode(bool): Unsets the respcode value.

    page(bool): Unsets the page value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.unset_filteraction <args>

    '''

    result = {}

    payload = {'filteraction': {}}

    if name:
        payload['filteraction']['name'] = True

    if qual:
        payload['filteraction']['qual'] = True

    if servicename:
        payload['filteraction']['servicename'] = True

    if value:
        payload['filteraction']['value'] = True

    if respcode:
        payload['filteraction']['respcode'] = True

    if page:
        payload['filteraction']['page'] = True

    execution = __proxy__['citrixns.post']('config/filteraction?action=unset', payload)

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


def unset_filterhtmlinjectionparameter(rate=None, frequency=None, strict=None, htmlsearchlen=None, save=False):
    '''
    Unsets values from the filterhtmlinjectionparameter configuration key.

    rate(bool): Unsets the rate value.

    frequency(bool): Unsets the frequency value.

    strict(bool): Unsets the strict value.

    htmlsearchlen(bool): Unsets the htmlsearchlen value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.unset_filterhtmlinjectionparameter <args>

    '''

    result = {}

    payload = {'filterhtmlinjectionparameter': {}}

    if rate:
        payload['filterhtmlinjectionparameter']['rate'] = True

    if frequency:
        payload['filterhtmlinjectionparameter']['frequency'] = True

    if strict:
        payload['filterhtmlinjectionparameter']['strict'] = True

    if htmlsearchlen:
        payload['filterhtmlinjectionparameter']['htmlsearchlen'] = True

    execution = __proxy__['citrixns.post']('config/filterhtmlinjectionparameter?action=unset', payload)

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


def unset_filterhtmlinjectionvariable(variable=None, value=None, save=False):
    '''
    Unsets values from the filterhtmlinjectionvariable configuration key.

    variable(bool): Unsets the variable value.

    value(bool): Unsets the value value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.unset_filterhtmlinjectionvariable <args>

    '''

    result = {}

    payload = {'filterhtmlinjectionvariable': {}}

    if variable:
        payload['filterhtmlinjectionvariable']['variable'] = True

    if value:
        payload['filterhtmlinjectionvariable']['value'] = True

    execution = __proxy__['citrixns.post']('config/filterhtmlinjectionvariable?action=unset', payload)

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


def unset_filterpostbodyinjection(postbody=None, save=False):
    '''
    Unsets values from the filterpostbodyinjection configuration key.

    postbody(bool): Unsets the postbody value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.unset_filterpostbodyinjection <args>

    '''

    result = {}

    payload = {'filterpostbodyinjection': {}}

    if postbody:
        payload['filterpostbodyinjection']['postbody'] = True

    execution = __proxy__['citrixns.post']('config/filterpostbodyinjection?action=unset', payload)

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


def unset_filterprebodyinjection(prebody=None, save=False):
    '''
    Unsets values from the filterprebodyinjection configuration key.

    prebody(bool): Unsets the prebody value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.unset_filterprebodyinjection <args>

    '''

    result = {}

    payload = {'filterprebodyinjection': {}}

    if prebody:
        payload['filterprebodyinjection']['prebody'] = True

    execution = __proxy__['citrixns.post']('config/filterprebodyinjection?action=unset', payload)

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


def update_filteraction(name=None, qual=None, servicename=None, value=None, respcode=None, page=None, save=False):
    '''
    Update the running configuration for the filteraction config key.

    name(str): Name for the filtering action. Must begin with a letter, number, or the underscore character (_). Other
        characters allowed, after the first character, are the hyphen (-), period (.) hash (#), space ( ), at sign (@),
        equals (=), and colon (:) characters. Choose a name that helps identify the type of action. The name of a filter
        action cannot be changed after it is created.  CLI Users: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    qual(str): Qualifier, which is the action to be performed. The qualifier cannot be changed after it is set. The available
        options function as follows: ADD - Adds the specified HTTP header. RESET - Terminates the connection, sending the
        appropriate termination notice to the users browser. FORWARD - Redirects the request to the designated service.
        You must specify either a service name or a page, but not both. DROP - Silently deletes the request, without
        sending a response to the users browser.  CORRUPT - Modifies the designated HTTP header to prevent it from
        performing the function it was intended to perform, then sends the request/response to the server/browser.
        ERRORCODE. Returns the designated HTTP error code to the users browser (for example, 404, the standard HTTP code
        for a non-existent Web page). Possible values = reset, add, corrupt, forward, errorcode, drop

    servicename(str): Service to which to forward HTTP requests. Required if the qualifier is FORWARD. Minimum length = 1

    value(str): String containing the header_name and header_value. If the qualifier is ADD, specify
        ;lt;header_name;gt;:;lt;header_value;gt;. If the qualifier is CORRUPT, specify only the header_name. Minimum
        length = 1

    respcode(int): Response code to be returned for HTTP requests (for use with the ERRORCODE qualifier). Minimum value = 1

    page(str): HTML page to return for HTTP requests (For use with the ERRORCODE qualifier). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.update_filteraction <args>

    '''

    result = {}

    payload = {'filteraction': {}}

    if name:
        payload['filteraction']['name'] = name

    if qual:
        payload['filteraction']['qual'] = qual

    if servicename:
        payload['filteraction']['servicename'] = servicename

    if value:
        payload['filteraction']['value'] = value

    if respcode:
        payload['filteraction']['respcode'] = respcode

    if page:
        payload['filteraction']['page'] = page

    execution = __proxy__['citrixns.put']('config/filteraction', payload)

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


def update_filterhtmlinjectionparameter(rate=None, frequency=None, strict=None, htmlsearchlen=None, save=False):
    '''
    Update the running configuration for the filterhtmlinjectionparameter config key.

    rate(int): For a rate of x, HTML injection is done for 1 out of x policy matches. Default value: 1 Minimum value = 1

    frequency(int): For a frequency of x, HTML injection is done at least once per x milliseconds. Default value: 1 Minimum
        value = 1

    strict(str): Searching for ;lt;html;gt; tag. If this parameter is enabled, HTML injection does not insert the prebody or
        postbody content unless the ;lt;html;gt; tag is found. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    htmlsearchlen(int): Number of characters, in the HTTP body, in which to search for the ;lt;html;gt; tag if strict mode is
        set. Default value: 1024 Minimum value = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.update_filterhtmlinjectionparameter <args>

    '''

    result = {}

    payload = {'filterhtmlinjectionparameter': {}}

    if rate:
        payload['filterhtmlinjectionparameter']['rate'] = rate

    if frequency:
        payload['filterhtmlinjectionparameter']['frequency'] = frequency

    if strict:
        payload['filterhtmlinjectionparameter']['strict'] = strict

    if htmlsearchlen:
        payload['filterhtmlinjectionparameter']['htmlsearchlen'] = htmlsearchlen

    execution = __proxy__['citrixns.put']('config/filterhtmlinjectionparameter', payload)

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


def update_filterhtmlinjectionvariable(variable=None, value=None, save=False):
    '''
    Update the running configuration for the filterhtmlinjectionvariable config key.

    variable(str): Name for the HTML injection variable to be added. Minimum length = 1 Maximum length = 31

    value(str): Value to be assigned to the new variable. Minimum length = 1 Maximum length = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.update_filterhtmlinjectionvariable <args>

    '''

    result = {}

    payload = {'filterhtmlinjectionvariable': {}}

    if variable:
        payload['filterhtmlinjectionvariable']['variable'] = variable

    if value:
        payload['filterhtmlinjectionvariable']['value'] = value

    execution = __proxy__['citrixns.put']('config/filterhtmlinjectionvariable', payload)

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


def update_filterpolicy(name=None, rule=None, reqaction=None, resaction=None, save=False):
    '''
    Update the running configuration for the filterpolicy config key.

    name(str): Name for the filtering action. Must begin with a letter, number, or the underscore character (_). Other
        characters allowed, after the first character, are the hyphen (-), period (.) pound (#), space ( ), at (@),
        equals (=), and colon (:) characters. Choose a name that helps identify the type of action. The name cannot be
        updated after the policy is created.  CLI Users: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    rule(str): NetScaler classic expression specifying the type of connections that match this policy. Minimum length = 1

    reqaction(str): Name of the action to be performed on requests that match the policy. Cannot be specified if the rule
        includes condition to be evaluated for responses. Minimum length = 1

    resaction(str): The action to be performed on the response. The string value can be a filter action created filter action
        or a built-in action. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.update_filterpolicy <args>

    '''

    result = {}

    payload = {'filterpolicy': {}}

    if name:
        payload['filterpolicy']['name'] = name

    if rule:
        payload['filterpolicy']['rule'] = rule

    if reqaction:
        payload['filterpolicy']['reqaction'] = reqaction

    if resaction:
        payload['filterpolicy']['resaction'] = resaction

    execution = __proxy__['citrixns.put']('config/filterpolicy', payload)

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


def update_filterpostbodyinjection(postbody=None, save=False):
    '''
    Update the running configuration for the filterpostbodyinjection config key.

    postbody(str): Name of file whose contents are to be inserted after the response body. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.update_filterpostbodyinjection <args>

    '''

    result = {}

    payload = {'filterpostbodyinjection': {}}

    if postbody:
        payload['filterpostbodyinjection']['postbody'] = postbody

    execution = __proxy__['citrixns.put']('config/filterpostbodyinjection', payload)

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


def update_filterprebodyinjection(prebody=None, save=False):
    '''
    Update the running configuration for the filterprebodyinjection config key.

    prebody(str): Name of file whose contents are to be inserted before the response body. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' filter.update_filterprebodyinjection <args>

    '''

    result = {}

    payload = {'filterprebodyinjection': {}}

    if prebody:
        payload['filterprebodyinjection']['prebody'] = prebody

    execution = __proxy__['citrixns.put']('config/filterprebodyinjection', payload)

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
