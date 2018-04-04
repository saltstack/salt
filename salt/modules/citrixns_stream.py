# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the stream key.

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

__virtualname__ = 'stream'


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

    return False, 'The stream execution module can only be loaded for citrixns proxy minions.'


def add_streamidentifier(name=None, selectorname=None, interval=None, samplecount=None, sort=None, snmptrap=None,
                         appflowlog=None, tracktransactions=None, maxtransactionthreshold=None,
                         mintransactionthreshold=None, acceptancethreshold=None, breachthreshold=None, save=False):
    '''
    Add a new streamidentifier to the running configuration.

    name(str): The name of stream identifier.

    selectorname(str): Name of the selector to use with the stream identifier. Minimum length = 1

    interval(int): Number of minutes of data to use when calculating session statistics (number of requests, bandwidth, and
        response times). The interval is a moving window that keeps the most recently collected data. Older data is
        discarded at regular intervals. Default value: 1 Minimum value = 1

    samplecount(int): Size of the sample from which to select a request for evaluation. The smaller the sample count, the
        more accurate is the statistical data. To evaluate all requests, set the sample count to 1. However, such a low
        setting can result in excessive consumption of memory and processing resources. Default value: 1 Minimum value =
        1 Maximum value = 65535

    sort(str): Sort stored records by the specified statistics column, in descending order. Performed during data collection,
        the sorting enables real-time data evaluation through NetScaler policies (for example, compression and caching
        policies) that use functions such as IS_TOP(n). Default value: REQUESTS Possible values = REQUESTS, CONNECTIONS,
        RESPTIME, BANDWIDTH, RESPTIME_BREACHES, NONE

    snmptrap(str): Enable/disable SNMP trap for stream identifier. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    appflowlog(str): Enable/disable Appflow logging for stream identifier. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    tracktransactions(str): Track transactions exceeding configured threshold. Transaction tracking can be enabled for
        following metric: ResponseTime. By default transaction tracking is disabled. Default value: NONE Possible values
        = RESPTIME, NONE

    maxtransactionthreshold(int): Maximum per transcation value of metric. Metric to be tracked is specified by
        tracktransactions attribute. Default value: 0

    mintransactionthreshold(int): Minimum per transcation value of metric. Metric to be tracked is specified by
        tracktransactions attribute. Default value: 0

    acceptancethreshold(str): Non-Breaching transactions to Total transactions threshold expressed in percent. Maximum of 6
        decimal places is supported. Default value: 0.000000 Maximum length = 10

    breachthreshold(int): Breaching transactions threshold calculated over interval. Default value: 0

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.add_streamidentifier <args>

    '''

    result = {}

    payload = {'streamidentifier': {}}

    if name:
        payload['streamidentifier']['name'] = name

    if selectorname:
        payload['streamidentifier']['selectorname'] = selectorname

    if interval:
        payload['streamidentifier']['interval'] = interval

    if samplecount:
        payload['streamidentifier']['samplecount'] = samplecount

    if sort:
        payload['streamidentifier']['sort'] = sort

    if snmptrap:
        payload['streamidentifier']['snmptrap'] = snmptrap

    if appflowlog:
        payload['streamidentifier']['appflowlog'] = appflowlog

    if tracktransactions:
        payload['streamidentifier']['tracktransactions'] = tracktransactions

    if maxtransactionthreshold:
        payload['streamidentifier']['maxtransactionthreshold'] = maxtransactionthreshold

    if mintransactionthreshold:
        payload['streamidentifier']['mintransactionthreshold'] = mintransactionthreshold

    if acceptancethreshold:
        payload['streamidentifier']['acceptancethreshold'] = acceptancethreshold

    if breachthreshold:
        payload['streamidentifier']['breachthreshold'] = breachthreshold

    execution = __proxy__['citrixns.post']('config/streamidentifier', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_streamselector(name=None, rule=None, save=False):
    '''
    Add a new streamselector to the running configuration.

    name(str): Name for the selector. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. If the name includes one or more spaces, and you are using the NetScaler CLI, enclose the name in
        double or single quotation marks (for example, "my selector" or my selector).

    rule(list(str)): Set of up to five individual (not compound) default syntax expressions. Maximum length: 7499 characters.
        Each expression must identify a specific request characteristic, such as the clients IP address (with
        CLIENT.IP.SRC) or requested server resource (with HTTP.REQ.URL).  Note: If two or more selectors contain the same
        expressions in different order, a separate set of records is created for each selector. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.add_streamselector <args>

    '''

    result = {}

    payload = {'streamselector': {}}

    if name:
        payload['streamselector']['name'] = name

    if rule:
        payload['streamselector']['rule'] = rule

    execution = __proxy__['citrixns.post']('config/streamselector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_streamidentifier(name=None, selectorname=None, interval=None, samplecount=None, sort=None, snmptrap=None,
                         appflowlog=None, tracktransactions=None, maxtransactionthreshold=None,
                         mintransactionthreshold=None, acceptancethreshold=None, breachthreshold=None):
    '''
    Show the running configuration for the streamidentifier config key.

    name(str): Filters results that only match the name field.

    selectorname(str): Filters results that only match the selectorname field.

    interval(int): Filters results that only match the interval field.

    samplecount(int): Filters results that only match the samplecount field.

    sort(str): Filters results that only match the sort field.

    snmptrap(str): Filters results that only match the snmptrap field.

    appflowlog(str): Filters results that only match the appflowlog field.

    tracktransactions(str): Filters results that only match the tracktransactions field.

    maxtransactionthreshold(int): Filters results that only match the maxtransactionthreshold field.

    mintransactionthreshold(int): Filters results that only match the mintransactionthreshold field.

    acceptancethreshold(str): Filters results that only match the acceptancethreshold field.

    breachthreshold(int): Filters results that only match the breachthreshold field.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.get_streamidentifier

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if selectorname:
        search_filter.append(['selectorname', selectorname])

    if interval:
        search_filter.append(['interval', interval])

    if samplecount:
        search_filter.append(['samplecount', samplecount])

    if sort:
        search_filter.append(['sort', sort])

    if snmptrap:
        search_filter.append(['snmptrap', snmptrap])

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if tracktransactions:
        search_filter.append(['tracktransactions', tracktransactions])

    if maxtransactionthreshold:
        search_filter.append(['maxtransactionthreshold', maxtransactionthreshold])

    if mintransactionthreshold:
        search_filter.append(['mintransactionthreshold', mintransactionthreshold])

    if acceptancethreshold:
        search_filter.append(['acceptancethreshold', acceptancethreshold])

    if breachthreshold:
        search_filter.append(['breachthreshold', breachthreshold])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/streamidentifier{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'streamidentifier')

    return response


def get_streamidentifier_binding():
    '''
    Show the running configuration for the streamidentifier_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.get_streamidentifier_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/streamidentifier_binding'), 'streamidentifier_binding')

    return response


def get_streamidentifier_streamsession_binding(name=None):
    '''
    Show the running configuration for the streamidentifier_streamsession_binding config key.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.get_streamidentifier_streamsession_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/streamidentifier_streamsession_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'streamidentifier_streamsession_binding')

    return response


def get_streamselector(name=None, rule=None):
    '''
    Show the running configuration for the streamselector config key.

    name(str): Filters results that only match the name field.

    rule(list(str)): Filters results that only match the rule field.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.get_streamselector

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/streamselector{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'streamselector')

    return response


def unset_streamidentifier(name=None, selectorname=None, interval=None, samplecount=None, sort=None, snmptrap=None,
                           appflowlog=None, tracktransactions=None, maxtransactionthreshold=None,
                           mintransactionthreshold=None, acceptancethreshold=None, breachthreshold=None, save=False):
    '''
    Unsets values from the streamidentifier configuration key.

    name(bool): Unsets the name value.

    selectorname(bool): Unsets the selectorname value.

    interval(bool): Unsets the interval value.

    samplecount(bool): Unsets the samplecount value.

    sort(bool): Unsets the sort value.

    snmptrap(bool): Unsets the snmptrap value.

    appflowlog(bool): Unsets the appflowlog value.

    tracktransactions(bool): Unsets the tracktransactions value.

    maxtransactionthreshold(bool): Unsets the maxtransactionthreshold value.

    mintransactionthreshold(bool): Unsets the mintransactionthreshold value.

    acceptancethreshold(bool): Unsets the acceptancethreshold value.

    breachthreshold(bool): Unsets the breachthreshold value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.unset_streamidentifier <args>

    '''

    result = {}

    payload = {'streamidentifier': {}}

    if name:
        payload['streamidentifier']['name'] = True

    if selectorname:
        payload['streamidentifier']['selectorname'] = True

    if interval:
        payload['streamidentifier']['interval'] = True

    if samplecount:
        payload['streamidentifier']['samplecount'] = True

    if sort:
        payload['streamidentifier']['sort'] = True

    if snmptrap:
        payload['streamidentifier']['snmptrap'] = True

    if appflowlog:
        payload['streamidentifier']['appflowlog'] = True

    if tracktransactions:
        payload['streamidentifier']['tracktransactions'] = True

    if maxtransactionthreshold:
        payload['streamidentifier']['maxtransactionthreshold'] = True

    if mintransactionthreshold:
        payload['streamidentifier']['mintransactionthreshold'] = True

    if acceptancethreshold:
        payload['streamidentifier']['acceptancethreshold'] = True

    if breachthreshold:
        payload['streamidentifier']['breachthreshold'] = True

    execution = __proxy__['citrixns.post']('config/streamidentifier?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_streamidentifier(name=None, selectorname=None, interval=None, samplecount=None, sort=None, snmptrap=None,
                            appflowlog=None, tracktransactions=None, maxtransactionthreshold=None,
                            mintransactionthreshold=None, acceptancethreshold=None, breachthreshold=None, save=False):
    '''
    Update the running configuration for the streamidentifier config key.

    name(str): The name of stream identifier.

    selectorname(str): Name of the selector to use with the stream identifier. Minimum length = 1

    interval(int): Number of minutes of data to use when calculating session statistics (number of requests, bandwidth, and
        response times). The interval is a moving window that keeps the most recently collected data. Older data is
        discarded at regular intervals. Default value: 1 Minimum value = 1

    samplecount(int): Size of the sample from which to select a request for evaluation. The smaller the sample count, the
        more accurate is the statistical data. To evaluate all requests, set the sample count to 1. However, such a low
        setting can result in excessive consumption of memory and processing resources. Default value: 1 Minimum value =
        1 Maximum value = 65535

    sort(str): Sort stored records by the specified statistics column, in descending order. Performed during data collection,
        the sorting enables real-time data evaluation through NetScaler policies (for example, compression and caching
        policies) that use functions such as IS_TOP(n). Default value: REQUESTS Possible values = REQUESTS, CONNECTIONS,
        RESPTIME, BANDWIDTH, RESPTIME_BREACHES, NONE

    snmptrap(str): Enable/disable SNMP trap for stream identifier. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    appflowlog(str): Enable/disable Appflow logging for stream identifier. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    tracktransactions(str): Track transactions exceeding configured threshold. Transaction tracking can be enabled for
        following metric: ResponseTime. By default transaction tracking is disabled. Default value: NONE Possible values
        = RESPTIME, NONE

    maxtransactionthreshold(int): Maximum per transcation value of metric. Metric to be tracked is specified by
        tracktransactions attribute. Default value: 0

    mintransactionthreshold(int): Minimum per transcation value of metric. Metric to be tracked is specified by
        tracktransactions attribute. Default value: 0

    acceptancethreshold(str): Non-Breaching transactions to Total transactions threshold expressed in percent. Maximum of 6
        decimal places is supported. Default value: 0.000000 Maximum length = 10

    breachthreshold(int): Breaching transactions threshold calculated over interval. Default value: 0

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.update_streamidentifier <args>

    '''

    result = {}

    payload = {'streamidentifier': {}}

    if name:
        payload['streamidentifier']['name'] = name

    if selectorname:
        payload['streamidentifier']['selectorname'] = selectorname

    if interval:
        payload['streamidentifier']['interval'] = interval

    if samplecount:
        payload['streamidentifier']['samplecount'] = samplecount

    if sort:
        payload['streamidentifier']['sort'] = sort

    if snmptrap:
        payload['streamidentifier']['snmptrap'] = snmptrap

    if appflowlog:
        payload['streamidentifier']['appflowlog'] = appflowlog

    if tracktransactions:
        payload['streamidentifier']['tracktransactions'] = tracktransactions

    if maxtransactionthreshold:
        payload['streamidentifier']['maxtransactionthreshold'] = maxtransactionthreshold

    if mintransactionthreshold:
        payload['streamidentifier']['mintransactionthreshold'] = mintransactionthreshold

    if acceptancethreshold:
        payload['streamidentifier']['acceptancethreshold'] = acceptancethreshold

    if breachthreshold:
        payload['streamidentifier']['breachthreshold'] = breachthreshold

    execution = __proxy__['citrixns.put']('config/streamidentifier', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_streamselector(name=None, rule=None, save=False):
    '''
    Update the running configuration for the streamselector config key.

    name(str): Name for the selector. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. If the name includes one or more spaces, and you are using the NetScaler CLI, enclose the name in
        double or single quotation marks (for example, "my selector" or my selector).

    rule(list(str)): Set of up to five individual (not compound) default syntax expressions. Maximum length: 7499 characters.
        Each expression must identify a specific request characteristic, such as the clients IP address (with
        CLIENT.IP.SRC) or requested server resource (with HTTP.REQ.URL).  Note: If two or more selectors contain the same
        expressions in different order, a separate set of records is created for each selector. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' stream.update_streamselector <args>

    '''

    result = {}

    payload = {'streamselector': {}}

    if name:
        payload['streamselector']['name'] = name

    if rule:
        payload['streamselector']['rule'] = rule

    execution = __proxy__['citrixns.put']('config/streamselector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
