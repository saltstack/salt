# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the integrated-caching key.

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

__virtualname__ = 'integrated_caching'


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

    return False, 'The integrated_caching execution module can only be loaded for citrixns proxy minions.'


def add_cachecontentgroup(name=None, weakposrelexpiry=None, heurexpiryparam=None, relexpiry=None, relexpirymillisec=None,
                          absexpiry=None, absexpirygmt=None, weaknegrelexpiry=None, hitparams=None, invalparams=None,
                          ignoreparamvaluecase=None, matchcookies=None, invalrestrictedtohost=None, polleverytime=None,
                          ignorereloadreq=None, removecookies=None, prefetch=None, prefetchperiod=None,
                          prefetchperiodmillisec=None, prefetchmaxpending=None, flashcache=None, expireatlastbyte=None,
                          insertvia=None, insertage=None, insertetag=None, cachecontrol=None, quickabortsize=None,
                          minressize=None, maxressize=None, memlimit=None, ignorereqcachinghdrs=None, minhits=None,
                          alwaysevalpolicies=None, persistha=None, pinned=None, lazydnsresolve=None, hitselector=None,
                          invalselector=None, ns_type=None, query=None, host=None, selectorvalue=None, tosecondary=None,
                          save=False):
    '''
    Add a new cachecontentgroup to the running configuration.

    name(str): Name for the content group. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the content group is created. Minimum length = 1

    weakposrelexpiry(int): Relative expiry time, in seconds, for expiring positive responses with response codes between 200
        and 399. Cannot be used in combination with other Expiry attributes. Similar to -relExpiry but has lower
        precedence. Minimum value = 0 Maximum value = 31536000

    heurexpiryparam(int): Heuristic expiry time, in percent of the duration, since the object was last modified. Minimum
        value = 0 Maximum value = 100

    relexpiry(int): Relative expiry time, in seconds, after which to expire an object cached in this content group. Minimum
        value = 0 Maximum value = 31536000

    relexpirymillisec(int): Relative expiry time, in milliseconds, after which to expire an object cached in this content
        group. Minimum value = 0 Maximum value = 86400000

    absexpiry(list(str)): Local time, up to 4 times a day, at which all objects in the content group must expire.   CLI
        Users: For example, to specify that the objects in the content group should expire by 11:00 PM, type the
        following command: add cache contentgroup ;lt;contentgroup name;gt; -absexpiry 23:00  To specify that the objects
        in the content group should expire at 10:00 AM, 3 PM, 6 PM, and 11:00 PM, type: add cache contentgroup
        ;lt;contentgroup name;gt; -absexpiry 10:00 15:00 18:00 23:00.

    absexpirygmt(list(str)): Coordinated Universal Time (GMT), up to 4 times a day, when all objects in the content group
        must expire.

    weaknegrelexpiry(int): Relative expiry time, in seconds, for expiring negative responses. This value is used only if the
        expiry time cannot be determined from any other source. It is applicable only to the following status codes: 307,
        403, 404, and 410. Minimum value = 0 Maximum value = 31536000

    hitparams(list(str)): Parameters to use for parameterized hit evaluation of an object. Up to 128 parameters can be
        specified. Mutually exclusive with the Hit Selector parameter. Minimum length = 1

    invalparams(list(str)): Parameters for parameterized invalidation of an object. You can specify up to 8 parameters.
        Mutually exclusive with invalSelector. Minimum length = 1

    ignoreparamvaluecase(str): Ignore case when comparing parameter values during parameterized hit evaluation. (Parameter
        value case is ignored by default during parameterized invalidation.). Possible values = YES, NO

    matchcookies(str): Evaluate for parameters in the cookie header also. Possible values = YES, NO

    invalrestrictedtohost(str): Take the host header into account during parameterized invalidation. Possible values = YES,
        NO

    polleverytime(str): Always poll for the objects in this content group. That is, retrieve the objects from the origin
        server whenever they are requested. Default value: NO Possible values = YES, NO

    ignorereloadreq(str): Ignore any request to reload a cached object from the origin server. To guard against Denial of
        Service attacks, set this parameter to YES. For RFC-compliant behavior, set it to NO. Default value: YES Possible
        values = YES, NO

    removecookies(str): Remove cookies from responses. Default value: YES Possible values = YES, NO

    prefetch(str): Attempt to refresh objects that are about to go stale. Default value: YES Possible values = YES, NO

    prefetchperiod(int): Time period, in seconds before an objects calculated expiry time, during which to attempt prefetch.
        Minimum value = 0 Maximum value = 4294967294

    prefetchperiodmillisec(int): Time period, in milliseconds before an objects calculated expiry time, during which to
        attempt prefetch. Minimum value = 0 Maximum value = 4294967290

    prefetchmaxpending(int): Maximum number of outstanding prefetches that can be queued for the content group. Minimum value
        = 0 Maximum value = 4294967294

    flashcache(str): Perform flash cache. Mutually exclusive with Poll Every Time (PET) on the same content group. Default
        value: NO Possible values = YES, NO

    expireatlastbyte(str): Force expiration of the content immediately after the response is downloaded (upon receipt of the
        last byte of the response body). Applicable only to positive responses. Default value: NO Possible values = YES,
        NO

    insertvia(str): Insert a Via header into the response. Default value: YES Possible values = YES, NO

    insertage(str): Insert an Age header into the response. An Age header contains information about the age of the object,
        in seconds, as calculated by the integrated cache. Default value: YES Possible values = YES, NO

    insertetag(str): Insert an ETag header in the response. With ETag header insertion, the integrated cache does not serve
        full responses on repeat requests. Default value: YES Possible values = YES, NO

    cachecontrol(str): Insert a Cache-Control header into the response. Minimum length = 1

    quickabortsize(int): If the size of an object that is being downloaded is less than or equal to the quick abort value,
        and a client aborts during the download, the cache stops downloading the response. If the object is larger than
        the quick abort size, the cache continues to download the response. Default value: 4194303 Minimum value = 0
        Maximum value = 4194303

    minressize(int): Minimum size of a response that can be cached in this content group.  Default minimum response size is
        0. Minimum value = 0 Maximum value = 2097151

    maxressize(int): Maximum size of a response that can be cached in this content group. Default value: 80 Minimum value = 0
        Maximum value = 2097151

    memlimit(int): Maximum amount of memory that the cache can use. The effective limit is based on the available memory of
        the NetScaler appliance. Default value: 65536

    ignorereqcachinghdrs(str): Ignore Cache-Control and Pragma headers in the incoming request. Default value: YES Possible
        values = YES, NO

    minhits(int): Number of hits that qualifies a response for storage in this content group. Default value: 0

    alwaysevalpolicies(str): Force policy evaluation for each response arriving from the origin server. Cannot be set to YES
        if the Prefetch parameter is also set to YES. Default value: NO Possible values = YES, NO

    persistha(str): Setting persistHA to YES causes IC to save objects in contentgroup to Secondary node in HA deployment.
        Default value: NO Possible values = YES, NO

    pinned(str): Do not flush objects from this content group under memory pressure. Default value: NO Possible values = YES,
        NO

    lazydnsresolve(str): Perform DNS resolution for responses only if the destination IP address in the request does not
        match the destination IP address of the cached response. Default value: YES Possible values = YES, NO

    hitselector(str): Selector for evaluating whether an object gets stored in a particular content group. A selector is an
        abstraction for a collection of PIXL expressions.

    invalselector(str): Selector for invalidating objects in the content group. A selector is an abstraction for a collection
        of PIXL expressions.

    ns_type(str): The type of the content group. Default value: HTTP Possible values = HTTP, MYSQL, MSSQL

    query(str): Query string specifying individual objects to flush from this group by using parameterized invalidation. If
        this parameter is not set, all objects are flushed from the group. Minimum length = 1

    host(str): Flush only objects that belong to the specified host. Do not use except with parameterized invalidation. Also,
        the Invalidation Restricted to Host parameter for the group must be set to YES. Minimum length = 1

    selectorvalue(str): Value of the selector to be used for flushing objects from the content group. Requires that an
        invalidation selector be configured for the content group. Minimum length = 1

    tosecondary(str): content group whose objects are to be sent to secondary. Default value: NO Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.add_cachecontentgroup <args>

    '''

    result = {}

    payload = {'cachecontentgroup': {}}

    if name:
        payload['cachecontentgroup']['name'] = name

    if weakposrelexpiry:
        payload['cachecontentgroup']['weakposrelexpiry'] = weakposrelexpiry

    if heurexpiryparam:
        payload['cachecontentgroup']['heurexpiryparam'] = heurexpiryparam

    if relexpiry:
        payload['cachecontentgroup']['relexpiry'] = relexpiry

    if relexpirymillisec:
        payload['cachecontentgroup']['relexpirymillisec'] = relexpirymillisec

    if absexpiry:
        payload['cachecontentgroup']['absexpiry'] = absexpiry

    if absexpirygmt:
        payload['cachecontentgroup']['absexpirygmt'] = absexpirygmt

    if weaknegrelexpiry:
        payload['cachecontentgroup']['weaknegrelexpiry'] = weaknegrelexpiry

    if hitparams:
        payload['cachecontentgroup']['hitparams'] = hitparams

    if invalparams:
        payload['cachecontentgroup']['invalparams'] = invalparams

    if ignoreparamvaluecase:
        payload['cachecontentgroup']['ignoreparamvaluecase'] = ignoreparamvaluecase

    if matchcookies:
        payload['cachecontentgroup']['matchcookies'] = matchcookies

    if invalrestrictedtohost:
        payload['cachecontentgroup']['invalrestrictedtohost'] = invalrestrictedtohost

    if polleverytime:
        payload['cachecontentgroup']['polleverytime'] = polleverytime

    if ignorereloadreq:
        payload['cachecontentgroup']['ignorereloadreq'] = ignorereloadreq

    if removecookies:
        payload['cachecontentgroup']['removecookies'] = removecookies

    if prefetch:
        payload['cachecontentgroup']['prefetch'] = prefetch

    if prefetchperiod:
        payload['cachecontentgroup']['prefetchperiod'] = prefetchperiod

    if prefetchperiodmillisec:
        payload['cachecontentgroup']['prefetchperiodmillisec'] = prefetchperiodmillisec

    if prefetchmaxpending:
        payload['cachecontentgroup']['prefetchmaxpending'] = prefetchmaxpending

    if flashcache:
        payload['cachecontentgroup']['flashcache'] = flashcache

    if expireatlastbyte:
        payload['cachecontentgroup']['expireatlastbyte'] = expireatlastbyte

    if insertvia:
        payload['cachecontentgroup']['insertvia'] = insertvia

    if insertage:
        payload['cachecontentgroup']['insertage'] = insertage

    if insertetag:
        payload['cachecontentgroup']['insertetag'] = insertetag

    if cachecontrol:
        payload['cachecontentgroup']['cachecontrol'] = cachecontrol

    if quickabortsize:
        payload['cachecontentgroup']['quickabortsize'] = quickabortsize

    if minressize:
        payload['cachecontentgroup']['minressize'] = minressize

    if maxressize:
        payload['cachecontentgroup']['maxressize'] = maxressize

    if memlimit:
        payload['cachecontentgroup']['memlimit'] = memlimit

    if ignorereqcachinghdrs:
        payload['cachecontentgroup']['ignorereqcachinghdrs'] = ignorereqcachinghdrs

    if minhits:
        payload['cachecontentgroup']['minhits'] = minhits

    if alwaysevalpolicies:
        payload['cachecontentgroup']['alwaysevalpolicies'] = alwaysevalpolicies

    if persistha:
        payload['cachecontentgroup']['persistha'] = persistha

    if pinned:
        payload['cachecontentgroup']['pinned'] = pinned

    if lazydnsresolve:
        payload['cachecontentgroup']['lazydnsresolve'] = lazydnsresolve

    if hitselector:
        payload['cachecontentgroup']['hitselector'] = hitselector

    if invalselector:
        payload['cachecontentgroup']['invalselector'] = invalselector

    if ns_type:
        payload['cachecontentgroup']['type'] = ns_type

    if query:
        payload['cachecontentgroup']['query'] = query

    if host:
        payload['cachecontentgroup']['host'] = host

    if selectorvalue:
        payload['cachecontentgroup']['selectorvalue'] = selectorvalue

    if tosecondary:
        payload['cachecontentgroup']['tosecondary'] = tosecondary

    execution = __proxy__['citrixns.post']('config/cachecontentgroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_cacheforwardproxy(ipaddress=None, port=None, save=False):
    '''
    Add a new cacheforwardproxy to the running configuration.

    ipaddress(str): IP address of the NetScaler appliance or a cache server for which the cache acts as a proxy. Requests
        coming to the NetScaler with the configured IP address are forwarded to the particular address, without involving
        the Integrated Cache in any way. Minimum length = 1

    port(int): Port on the NetScaler appliance or a server for which the cache acts as a proxy. Minimum value = 1 Range 1 -
        65535 * in CLI is represented as 65535 in NITRO API

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.add_cacheforwardproxy <args>

    '''

    result = {}

    payload = {'cacheforwardproxy': {}}

    if ipaddress:
        payload['cacheforwardproxy']['ipaddress'] = ipaddress

    if port:
        payload['cacheforwardproxy']['port'] = port

    execution = __proxy__['citrixns.post']('config/cacheforwardproxy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_cacheglobal_cachepolicy_binding(priority=None, globalbindtype=None, gotopriorityexpression=None, policy=None,
                                        ns_type=None, precededefrules=None, labeltype=None, labelname=None, invoke=None,
                                        save=False):
    '''
    Add a new cacheglobal_cachepolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policy(str): Name of the cache policy.

    ns_type(str): The bind point to which policy is bound. When you specify the type, detailed information about that bind
        point appears. Possible values = REQ_OVERRIDE, REQ_DEFAULT, RES_OVERRIDE, RES_DEFAULT

    precededefrules(str): Specify whether this policy should be evaluated. Default value: NO Possible values = YES, NO

    labeltype(str): Type of policy label to invoke. Possible values = reqvserver, resvserver, policylabel

    labelname(str): Name of the label to invoke if the current policy rule evaluates to TRUE. (To invoke a label associated
        with a virtual server, specify the name of the virtual server.).

    invoke(bool): Invoke policies bound to a virtual server or a user-defined policy label. After the invoked policies are
        evaluated, the flow returns to the policy with the next priority. Applicable only to default-syntax policies.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.add_cacheglobal_cachepolicy_binding <args>

    '''

    result = {}

    payload = {'cacheglobal_cachepolicy_binding': {}}

    if priority:
        payload['cacheglobal_cachepolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['cacheglobal_cachepolicy_binding']['globalbindtype'] = globalbindtype

    if gotopriorityexpression:
        payload['cacheglobal_cachepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policy:
        payload['cacheglobal_cachepolicy_binding']['policy'] = policy

    if ns_type:
        payload['cacheglobal_cachepolicy_binding']['type'] = ns_type

    if precededefrules:
        payload['cacheglobal_cachepolicy_binding']['precededefrules'] = precededefrules

    if labeltype:
        payload['cacheglobal_cachepolicy_binding']['labeltype'] = labeltype

    if labelname:
        payload['cacheglobal_cachepolicy_binding']['labelname'] = labelname

    if invoke:
        payload['cacheglobal_cachepolicy_binding']['invoke'] = invoke

    execution = __proxy__['citrixns.post']('config/cacheglobal_cachepolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_cachepolicy(policyname=None, rule=None, action=None, storeingroup=None, invalgroups=None, invalobjects=None,
                    undefaction=None, newname=None, save=False):
    '''
    Add a new cachepolicy to the running configuration.

    policyname(str): Name for the policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Can be changed after the policy is created. Minimum length = 1

    rule(str): Expression against which the traffic is evaluated. Note: Maximum length of a string literal in the expression
        is 255 characters. A longer string can be split into smaller strings of up to 255 characters each, and the
        smaller strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" The following requirements apply only to
        the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression in double
        quotation marks. * If the expression itself includes double quotation marks, escape the quotations by using the
        \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks.

    action(str): Action to apply to content that matches the policy.  * CACHE or MAY_CACHE action - positive cachability
        policy * NOCACHE or MAY_NOCACHE action - negative cachability policy * INVAL action - Dynamic Invalidation
        Policy. Possible values = CACHE, NOCACHE, MAY_CACHE, MAY_NOCACHE, INVAL

    storeingroup(str): Name of the content group in which to store the object when the final result of policy evaluation is
        CACHE. The content group must exist before being mentioned here. Use the "show cache contentgroup" command to
        view the list of existing content groups. Minimum length = 1

    invalgroups(list(str)): Content group(s) to be invalidated when the INVAL action is applied. Maximum number of content
        groups that can be specified is 16. Minimum length = 1

    invalobjects(list(str)): Content groups(s) in which the objects will be invalidated if the action is INVAL. Minimum
        length = 1

    undefaction(str): Action to be performed when the result of rule evaluation is undefined. Possible values = NOCACHE,
        RESET

    newname(str): New name for the cache policy. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.add_cachepolicy <args>

    '''

    result = {}

    payload = {'cachepolicy': {}}

    if policyname:
        payload['cachepolicy']['policyname'] = policyname

    if rule:
        payload['cachepolicy']['rule'] = rule

    if action:
        payload['cachepolicy']['action'] = action

    if storeingroup:
        payload['cachepolicy']['storeingroup'] = storeingroup

    if invalgroups:
        payload['cachepolicy']['invalgroups'] = invalgroups

    if invalobjects:
        payload['cachepolicy']['invalobjects'] = invalobjects

    if undefaction:
        payload['cachepolicy']['undefaction'] = undefaction

    if newname:
        payload['cachepolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/cachepolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_cachepolicylabel(labelname=None, evaluates=None, newname=None, save=False):
    '''
    Add a new cachepolicylabel to the running configuration.

    labelname(str): Name for the label. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Can be changed after the label is created.

    evaluates(str): When to evaluate policies bound to this label: request-time or response-time. Possible values = REQ, RES,
        MSSQL_REQ, MSSQL_RES, MYSQL_REQ, MYSQL_RES

    newname(str): New name for the cache-policy label. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.add_cachepolicylabel <args>

    '''

    result = {}

    payload = {'cachepolicylabel': {}}

    if labelname:
        payload['cachepolicylabel']['labelname'] = labelname

    if evaluates:
        payload['cachepolicylabel']['evaluates'] = evaluates

    if newname:
        payload['cachepolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/cachepolicylabel', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_cachepolicylabel_cachepolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                             gotopriorityexpression=None, invoke=None, labeltype=None, save=False):
    '''
    Add a new cachepolicylabel_cachepolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): Name of the cache policy to bind to the policy label.

    labelname(str): Name of the cache policy label to which to bind the policy.

    invoke_labelname(str): Name of the policy label to invoke if the current policy rule evaluates to TRUE.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke policies bound to a virtual server or a user-defined policy label. After the invoked policies are
        evaluated, the flow returns to the policy with the next-lower priority.

    labeltype(str): Type of policy label to invoke: an unnamed label associated with a virtual server, or user-defined policy
        label. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.add_cachepolicylabel_cachepolicy_binding <args>

    '''

    result = {}

    payload = {'cachepolicylabel_cachepolicy_binding': {}}

    if priority:
        payload['cachepolicylabel_cachepolicy_binding']['priority'] = priority

    if policyname:
        payload['cachepolicylabel_cachepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['cachepolicylabel_cachepolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['cachepolicylabel_cachepolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['cachepolicylabel_cachepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['cachepolicylabel_cachepolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['cachepolicylabel_cachepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/cachepolicylabel_cachepolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_cacheselector(selectorname=None, rule=None, save=False):
    '''
    Add a new cacheselector to the running configuration.

    selectorname(str): Name for the selector. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.

    rule(list(str)): One or multiple PIXL expressions for evaluating an HTTP request or response. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.add_cacheselector <args>

    '''

    result = {}

    payload = {'cacheselector': {}}

    if selectorname:
        payload['cacheselector']['selectorname'] = selectorname

    if rule:
        payload['cacheselector']['rule'] = rule

    execution = __proxy__['citrixns.post']('config/cacheselector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_cachecontentgroup(name=None, weakposrelexpiry=None, heurexpiryparam=None, relexpiry=None, relexpirymillisec=None,
                          absexpiry=None, absexpirygmt=None, weaknegrelexpiry=None, hitparams=None, invalparams=None,
                          ignoreparamvaluecase=None, matchcookies=None, invalrestrictedtohost=None, polleverytime=None,
                          ignorereloadreq=None, removecookies=None, prefetch=None, prefetchperiod=None,
                          prefetchperiodmillisec=None, prefetchmaxpending=None, flashcache=None, expireatlastbyte=None,
                          insertvia=None, insertage=None, insertetag=None, cachecontrol=None, quickabortsize=None,
                          minressize=None, maxressize=None, memlimit=None, ignorereqcachinghdrs=None, minhits=None,
                          alwaysevalpolicies=None, persistha=None, pinned=None, lazydnsresolve=None, hitselector=None,
                          invalselector=None, ns_type=None, query=None, host=None, selectorvalue=None,
                          tosecondary=None):
    '''
    Show the running configuration for the cachecontentgroup config key.

    name(str): Filters results that only match the name field.

    weakposrelexpiry(int): Filters results that only match the weakposrelexpiry field.

    heurexpiryparam(int): Filters results that only match the heurexpiryparam field.

    relexpiry(int): Filters results that only match the relexpiry field.

    relexpirymillisec(int): Filters results that only match the relexpirymillisec field.

    absexpiry(list(str)): Filters results that only match the absexpiry field.

    absexpirygmt(list(str)): Filters results that only match the absexpirygmt field.

    weaknegrelexpiry(int): Filters results that only match the weaknegrelexpiry field.

    hitparams(list(str)): Filters results that only match the hitparams field.

    invalparams(list(str)): Filters results that only match the invalparams field.

    ignoreparamvaluecase(str): Filters results that only match the ignoreparamvaluecase field.

    matchcookies(str): Filters results that only match the matchcookies field.

    invalrestrictedtohost(str): Filters results that only match the invalrestrictedtohost field.

    polleverytime(str): Filters results that only match the polleverytime field.

    ignorereloadreq(str): Filters results that only match the ignorereloadreq field.

    removecookies(str): Filters results that only match the removecookies field.

    prefetch(str): Filters results that only match the prefetch field.

    prefetchperiod(int): Filters results that only match the prefetchperiod field.

    prefetchperiodmillisec(int): Filters results that only match the prefetchperiodmillisec field.

    prefetchmaxpending(int): Filters results that only match the prefetchmaxpending field.

    flashcache(str): Filters results that only match the flashcache field.

    expireatlastbyte(str): Filters results that only match the expireatlastbyte field.

    insertvia(str): Filters results that only match the insertvia field.

    insertage(str): Filters results that only match the insertage field.

    insertetag(str): Filters results that only match the insertetag field.

    cachecontrol(str): Filters results that only match the cachecontrol field.

    quickabortsize(int): Filters results that only match the quickabortsize field.

    minressize(int): Filters results that only match the minressize field.

    maxressize(int): Filters results that only match the maxressize field.

    memlimit(int): Filters results that only match the memlimit field.

    ignorereqcachinghdrs(str): Filters results that only match the ignorereqcachinghdrs field.

    minhits(int): Filters results that only match the minhits field.

    alwaysevalpolicies(str): Filters results that only match the alwaysevalpolicies field.

    persistha(str): Filters results that only match the persistha field.

    pinned(str): Filters results that only match the pinned field.

    lazydnsresolve(str): Filters results that only match the lazydnsresolve field.

    hitselector(str): Filters results that only match the hitselector field.

    invalselector(str): Filters results that only match the invalselector field.

    ns_type(str): Filters results that only match the type field.

    query(str): Filters results that only match the query field.

    host(str): Filters results that only match the host field.

    selectorvalue(str): Filters results that only match the selectorvalue field.

    tosecondary(str): Filters results that only match the tosecondary field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachecontentgroup

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if weakposrelexpiry:
        search_filter.append(['weakposrelexpiry', weakposrelexpiry])

    if heurexpiryparam:
        search_filter.append(['heurexpiryparam', heurexpiryparam])

    if relexpiry:
        search_filter.append(['relexpiry', relexpiry])

    if relexpirymillisec:
        search_filter.append(['relexpirymillisec', relexpirymillisec])

    if absexpiry:
        search_filter.append(['absexpiry', absexpiry])

    if absexpirygmt:
        search_filter.append(['absexpirygmt', absexpirygmt])

    if weaknegrelexpiry:
        search_filter.append(['weaknegrelexpiry', weaknegrelexpiry])

    if hitparams:
        search_filter.append(['hitparams', hitparams])

    if invalparams:
        search_filter.append(['invalparams', invalparams])

    if ignoreparamvaluecase:
        search_filter.append(['ignoreparamvaluecase', ignoreparamvaluecase])

    if matchcookies:
        search_filter.append(['matchcookies', matchcookies])

    if invalrestrictedtohost:
        search_filter.append(['invalrestrictedtohost', invalrestrictedtohost])

    if polleverytime:
        search_filter.append(['polleverytime', polleverytime])

    if ignorereloadreq:
        search_filter.append(['ignorereloadreq', ignorereloadreq])

    if removecookies:
        search_filter.append(['removecookies', removecookies])

    if prefetch:
        search_filter.append(['prefetch', prefetch])

    if prefetchperiod:
        search_filter.append(['prefetchperiod', prefetchperiod])

    if prefetchperiodmillisec:
        search_filter.append(['prefetchperiodmillisec', prefetchperiodmillisec])

    if prefetchmaxpending:
        search_filter.append(['prefetchmaxpending', prefetchmaxpending])

    if flashcache:
        search_filter.append(['flashcache', flashcache])

    if expireatlastbyte:
        search_filter.append(['expireatlastbyte', expireatlastbyte])

    if insertvia:
        search_filter.append(['insertvia', insertvia])

    if insertage:
        search_filter.append(['insertage', insertage])

    if insertetag:
        search_filter.append(['insertetag', insertetag])

    if cachecontrol:
        search_filter.append(['cachecontrol', cachecontrol])

    if quickabortsize:
        search_filter.append(['quickabortsize', quickabortsize])

    if minressize:
        search_filter.append(['minressize', minressize])

    if maxressize:
        search_filter.append(['maxressize', maxressize])

    if memlimit:
        search_filter.append(['memlimit', memlimit])

    if ignorereqcachinghdrs:
        search_filter.append(['ignorereqcachinghdrs', ignorereqcachinghdrs])

    if minhits:
        search_filter.append(['minhits', minhits])

    if alwaysevalpolicies:
        search_filter.append(['alwaysevalpolicies', alwaysevalpolicies])

    if persistha:
        search_filter.append(['persistha', persistha])

    if pinned:
        search_filter.append(['pinned', pinned])

    if lazydnsresolve:
        search_filter.append(['lazydnsresolve', lazydnsresolve])

    if hitselector:
        search_filter.append(['hitselector', hitselector])

    if invalselector:
        search_filter.append(['invalselector', invalselector])

    if ns_type:
        search_filter.append(['type', ns_type])

    if query:
        search_filter.append(['query', query])

    if host:
        search_filter.append(['host', host])

    if selectorvalue:
        search_filter.append(['selectorvalue', selectorvalue])

    if tosecondary:
        search_filter.append(['tosecondary', tosecondary])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachecontentgroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachecontentgroup')

    return response


def get_cacheforwardproxy(ipaddress=None, port=None):
    '''
    Show the running configuration for the cacheforwardproxy config key.

    ipaddress(str): Filters results that only match the ipaddress field.

    port(int): Filters results that only match the port field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cacheforwardproxy

    '''

    search_filter = []

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if port:
        search_filter.append(['port', port])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cacheforwardproxy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cacheforwardproxy')

    return response


def get_cacheglobal_binding():
    '''
    Show the running configuration for the cacheglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cacheglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cacheglobal_binding'), 'cacheglobal_binding')

    return response


def get_cacheglobal_cachepolicy_binding(priority=None, globalbindtype=None, gotopriorityexpression=None, policy=None,
                                        ns_type=None, precededefrules=None, labeltype=None, labelname=None,
                                        invoke=None):
    '''
    Show the running configuration for the cacheglobal_cachepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policy(str): Filters results that only match the policy field.

    ns_type(str): Filters results that only match the type field.

    precededefrules(str): Filters results that only match the precededefrules field.

    labeltype(str): Filters results that only match the labeltype field.

    labelname(str): Filters results that only match the labelname field.

    invoke(bool): Filters results that only match the invoke field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cacheglobal_cachepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policy:
        search_filter.append(['policy', policy])

    if ns_type:
        search_filter.append(['type', ns_type])

    if precededefrules:
        search_filter.append(['precededefrules', precededefrules])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    if labelname:
        search_filter.append(['labelname', labelname])

    if invoke:
        search_filter.append(['invoke', invoke])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cacheglobal_cachepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cacheglobal_cachepolicy_binding')

    return response


def get_cacheobject(url=None, locator=None, httpstatus=None, host=None, port=None, groupname=None, httpmethod=None,
                    group=None, ignoremarkerobjects=None, includenotreadyobjects=None, nodeid=None, tosecondary=None):
    '''
    Show the running configuration for the cacheobject config key.

    url(str): Filters results that only match the url field.

    locator(int): Filters results that only match the locator field.

    httpstatus(int): Filters results that only match the httpstatus field.

    host(str): Filters results that only match the host field.

    port(int): Filters results that only match the port field.

    groupname(str): Filters results that only match the groupname field.

    httpmethod(str): Filters results that only match the httpmethod field.

    group(str): Filters results that only match the group field.

    ignoremarkerobjects(str): Filters results that only match the ignoremarkerobjects field.

    includenotreadyobjects(str): Filters results that only match the includenotreadyobjects field.

    nodeid(int): Filters results that only match the nodeid field.

    tosecondary(str): Filters results that only match the tosecondary field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cacheobject

    '''

    search_filter = []

    if url:
        search_filter.append(['url', url])

    if locator:
        search_filter.append(['locator', locator])

    if httpstatus:
        search_filter.append(['httpstatus', httpstatus])

    if host:
        search_filter.append(['host', host])

    if port:
        search_filter.append(['port', port])

    if groupname:
        search_filter.append(['groupname', groupname])

    if httpmethod:
        search_filter.append(['httpmethod', httpmethod])

    if group:
        search_filter.append(['group', group])

    if ignoremarkerobjects:
        search_filter.append(['ignoremarkerobjects', ignoremarkerobjects])

    if includenotreadyobjects:
        search_filter.append(['includenotreadyobjects', includenotreadyobjects])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    if tosecondary:
        search_filter.append(['tosecondary', tosecondary])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cacheobject{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cacheobject')

    return response


def get_cacheparameter():
    '''
    Show the running configuration for the cacheparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cacheparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cacheparameter'), 'cacheparameter')

    return response


def get_cachepolicy(policyname=None, rule=None, action=None, storeingroup=None, invalgroups=None, invalobjects=None,
                    undefaction=None, newname=None):
    '''
    Show the running configuration for the cachepolicy config key.

    policyname(str): Filters results that only match the policyname field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    storeingroup(str): Filters results that only match the storeingroup field.

    invalgroups(list(str)): Filters results that only match the invalgroups field.

    invalobjects(list(str)): Filters results that only match the invalobjects field.

    undefaction(str): Filters results that only match the undefaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicy

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    if storeingroup:
        search_filter.append(['storeingroup', storeingroup])

    if invalgroups:
        search_filter.append(['invalgroups', invalgroups])

    if invalobjects:
        search_filter.append(['invalobjects', invalobjects])

    if undefaction:
        search_filter.append(['undefaction', undefaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachepolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachepolicy')

    return response


def get_cachepolicy_binding():
    '''
    Show the running configuration for the cachepolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachepolicy_binding'), 'cachepolicy_binding')

    return response


def get_cachepolicy_cacheglobal_binding(policyname=None, boundto=None):
    '''
    Show the running configuration for the cachepolicy_cacheglobal_binding config key.

    policyname(str): Filters results that only match the policyname field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicy_cacheglobal_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachepolicy_cacheglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachepolicy_cacheglobal_binding')

    return response


def get_cachepolicy_cachepolicylabel_binding(policyname=None, boundto=None):
    '''
    Show the running configuration for the cachepolicy_cachepolicylabel_binding config key.

    policyname(str): Filters results that only match the policyname field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicy_cachepolicylabel_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachepolicy_cachepolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachepolicy_cachepolicylabel_binding')

    return response


def get_cachepolicy_csvserver_binding(policyname=None, boundto=None):
    '''
    Show the running configuration for the cachepolicy_csvserver_binding config key.

    policyname(str): Filters results that only match the policyname field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicy_csvserver_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachepolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachepolicy_csvserver_binding')

    return response


def get_cachepolicy_lbvserver_binding(policyname=None, boundto=None):
    '''
    Show the running configuration for the cachepolicy_lbvserver_binding config key.

    policyname(str): Filters results that only match the policyname field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicy_lbvserver_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachepolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachepolicy_lbvserver_binding')

    return response


def get_cachepolicylabel(labelname=None, evaluates=None, newname=None):
    '''
    Show the running configuration for the cachepolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    evaluates(str): Filters results that only match the evaluates field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if evaluates:
        search_filter.append(['evaluates', evaluates])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachepolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachepolicylabel')

    return response


def get_cachepolicylabel_binding():
    '''
    Show the running configuration for the cachepolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cachepolicylabel_binding'), 'cachepolicylabel_binding')

    return response


def get_cachepolicylabel_cachepolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                             gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the cachepolicylabel_cachepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicylabel_cachepolicy_binding

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
            __proxy__['citrixns.get']('config/cachepolicylabel_cachepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachepolicylabel_cachepolicy_binding')

    return response


def get_cachepolicylabel_policybinding_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                               gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the cachepolicylabel_policybinding_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cachepolicylabel_policybinding_binding

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
            __proxy__['citrixns.get']('config/cachepolicylabel_policybinding_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cachepolicylabel_policybinding_binding')

    return response


def get_cacheselector(selectorname=None, rule=None):
    '''
    Show the running configuration for the cacheselector config key.

    selectorname(str): Filters results that only match the selectorname field.

    rule(list(str)): Filters results that only match the rule field.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.get_cacheselector

    '''

    search_filter = []

    if selectorname:
        search_filter.append(['selectorname', selectorname])

    if rule:
        search_filter.append(['rule', rule])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cacheselector{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cacheselector')

    return response


def unset_cachecontentgroup(name=None, weakposrelexpiry=None, heurexpiryparam=None, relexpiry=None,
                            relexpirymillisec=None, absexpiry=None, absexpirygmt=None, weaknegrelexpiry=None,
                            hitparams=None, invalparams=None, ignoreparamvaluecase=None, matchcookies=None,
                            invalrestrictedtohost=None, polleverytime=None, ignorereloadreq=None, removecookies=None,
                            prefetch=None, prefetchperiod=None, prefetchperiodmillisec=None, prefetchmaxpending=None,
                            flashcache=None, expireatlastbyte=None, insertvia=None, insertage=None, insertetag=None,
                            cachecontrol=None, quickabortsize=None, minressize=None, maxressize=None, memlimit=None,
                            ignorereqcachinghdrs=None, minhits=None, alwaysevalpolicies=None, persistha=None,
                            pinned=None, lazydnsresolve=None, hitselector=None, invalselector=None, ns_type=None,
                            query=None, host=None, selectorvalue=None, tosecondary=None, save=False):
    '''
    Unsets values from the cachecontentgroup configuration key.

    name(bool): Unsets the name value.

    weakposrelexpiry(bool): Unsets the weakposrelexpiry value.

    heurexpiryparam(bool): Unsets the heurexpiryparam value.

    relexpiry(bool): Unsets the relexpiry value.

    relexpirymillisec(bool): Unsets the relexpirymillisec value.

    absexpiry(bool): Unsets the absexpiry value.

    absexpirygmt(bool): Unsets the absexpirygmt value.

    weaknegrelexpiry(bool): Unsets the weaknegrelexpiry value.

    hitparams(bool): Unsets the hitparams value.

    invalparams(bool): Unsets the invalparams value.

    ignoreparamvaluecase(bool): Unsets the ignoreparamvaluecase value.

    matchcookies(bool): Unsets the matchcookies value.

    invalrestrictedtohost(bool): Unsets the invalrestrictedtohost value.

    polleverytime(bool): Unsets the polleverytime value.

    ignorereloadreq(bool): Unsets the ignorereloadreq value.

    removecookies(bool): Unsets the removecookies value.

    prefetch(bool): Unsets the prefetch value.

    prefetchperiod(bool): Unsets the prefetchperiod value.

    prefetchperiodmillisec(bool): Unsets the prefetchperiodmillisec value.

    prefetchmaxpending(bool): Unsets the prefetchmaxpending value.

    flashcache(bool): Unsets the flashcache value.

    expireatlastbyte(bool): Unsets the expireatlastbyte value.

    insertvia(bool): Unsets the insertvia value.

    insertage(bool): Unsets the insertage value.

    insertetag(bool): Unsets the insertetag value.

    cachecontrol(bool): Unsets the cachecontrol value.

    quickabortsize(bool): Unsets the quickabortsize value.

    minressize(bool): Unsets the minressize value.

    maxressize(bool): Unsets the maxressize value.

    memlimit(bool): Unsets the memlimit value.

    ignorereqcachinghdrs(bool): Unsets the ignorereqcachinghdrs value.

    minhits(bool): Unsets the minhits value.

    alwaysevalpolicies(bool): Unsets the alwaysevalpolicies value.

    persistha(bool): Unsets the persistha value.

    pinned(bool): Unsets the pinned value.

    lazydnsresolve(bool): Unsets the lazydnsresolve value.

    hitselector(bool): Unsets the hitselector value.

    invalselector(bool): Unsets the invalselector value.

    ns_type(bool): Unsets the ns_type value.

    query(bool): Unsets the query value.

    host(bool): Unsets the host value.

    selectorvalue(bool): Unsets the selectorvalue value.

    tosecondary(bool): Unsets the tosecondary value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.unset_cachecontentgroup <args>

    '''

    result = {}

    payload = {'cachecontentgroup': {}}

    if name:
        payload['cachecontentgroup']['name'] = True

    if weakposrelexpiry:
        payload['cachecontentgroup']['weakposrelexpiry'] = True

    if heurexpiryparam:
        payload['cachecontentgroup']['heurexpiryparam'] = True

    if relexpiry:
        payload['cachecontentgroup']['relexpiry'] = True

    if relexpirymillisec:
        payload['cachecontentgroup']['relexpirymillisec'] = True

    if absexpiry:
        payload['cachecontentgroup']['absexpiry'] = True

    if absexpirygmt:
        payload['cachecontentgroup']['absexpirygmt'] = True

    if weaknegrelexpiry:
        payload['cachecontentgroup']['weaknegrelexpiry'] = True

    if hitparams:
        payload['cachecontentgroup']['hitparams'] = True

    if invalparams:
        payload['cachecontentgroup']['invalparams'] = True

    if ignoreparamvaluecase:
        payload['cachecontentgroup']['ignoreparamvaluecase'] = True

    if matchcookies:
        payload['cachecontentgroup']['matchcookies'] = True

    if invalrestrictedtohost:
        payload['cachecontentgroup']['invalrestrictedtohost'] = True

    if polleverytime:
        payload['cachecontentgroup']['polleverytime'] = True

    if ignorereloadreq:
        payload['cachecontentgroup']['ignorereloadreq'] = True

    if removecookies:
        payload['cachecontentgroup']['removecookies'] = True

    if prefetch:
        payload['cachecontentgroup']['prefetch'] = True

    if prefetchperiod:
        payload['cachecontentgroup']['prefetchperiod'] = True

    if prefetchperiodmillisec:
        payload['cachecontentgroup']['prefetchperiodmillisec'] = True

    if prefetchmaxpending:
        payload['cachecontentgroup']['prefetchmaxpending'] = True

    if flashcache:
        payload['cachecontentgroup']['flashcache'] = True

    if expireatlastbyte:
        payload['cachecontentgroup']['expireatlastbyte'] = True

    if insertvia:
        payload['cachecontentgroup']['insertvia'] = True

    if insertage:
        payload['cachecontentgroup']['insertage'] = True

    if insertetag:
        payload['cachecontentgroup']['insertetag'] = True

    if cachecontrol:
        payload['cachecontentgroup']['cachecontrol'] = True

    if quickabortsize:
        payload['cachecontentgroup']['quickabortsize'] = True

    if minressize:
        payload['cachecontentgroup']['minressize'] = True

    if maxressize:
        payload['cachecontentgroup']['maxressize'] = True

    if memlimit:
        payload['cachecontentgroup']['memlimit'] = True

    if ignorereqcachinghdrs:
        payload['cachecontentgroup']['ignorereqcachinghdrs'] = True

    if minhits:
        payload['cachecontentgroup']['minhits'] = True

    if alwaysevalpolicies:
        payload['cachecontentgroup']['alwaysevalpolicies'] = True

    if persistha:
        payload['cachecontentgroup']['persistha'] = True

    if pinned:
        payload['cachecontentgroup']['pinned'] = True

    if lazydnsresolve:
        payload['cachecontentgroup']['lazydnsresolve'] = True

    if hitselector:
        payload['cachecontentgroup']['hitselector'] = True

    if invalselector:
        payload['cachecontentgroup']['invalselector'] = True

    if ns_type:
        payload['cachecontentgroup']['type'] = True

    if query:
        payload['cachecontentgroup']['query'] = True

    if host:
        payload['cachecontentgroup']['host'] = True

    if selectorvalue:
        payload['cachecontentgroup']['selectorvalue'] = True

    if tosecondary:
        payload['cachecontentgroup']['tosecondary'] = True

    execution = __proxy__['citrixns.post']('config/cachecontentgroup?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_cacheparameter(memlimit=None, via=None, verifyusing=None, maxpostlen=None, prefetchmaxpending=None,
                         enablebypass=None, undefaction=None, enablehaobjpersist=None, save=False):
    '''
    Unsets values from the cacheparameter configuration key.

    memlimit(bool): Unsets the memlimit value.

    via(bool): Unsets the via value.

    verifyusing(bool): Unsets the verifyusing value.

    maxpostlen(bool): Unsets the maxpostlen value.

    prefetchmaxpending(bool): Unsets the prefetchmaxpending value.

    enablebypass(bool): Unsets the enablebypass value.

    undefaction(bool): Unsets the undefaction value.

    enablehaobjpersist(bool): Unsets the enablehaobjpersist value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.unset_cacheparameter <args>

    '''

    result = {}

    payload = {'cacheparameter': {}}

    if memlimit:
        payload['cacheparameter']['memlimit'] = True

    if via:
        payload['cacheparameter']['via'] = True

    if verifyusing:
        payload['cacheparameter']['verifyusing'] = True

    if maxpostlen:
        payload['cacheparameter']['maxpostlen'] = True

    if prefetchmaxpending:
        payload['cacheparameter']['prefetchmaxpending'] = True

    if enablebypass:
        payload['cacheparameter']['enablebypass'] = True

    if undefaction:
        payload['cacheparameter']['undefaction'] = True

    if enablehaobjpersist:
        payload['cacheparameter']['enablehaobjpersist'] = True

    execution = __proxy__['citrixns.post']('config/cacheparameter?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_cachepolicy(policyname=None, rule=None, action=None, storeingroup=None, invalgroups=None, invalobjects=None,
                      undefaction=None, newname=None, save=False):
    '''
    Unsets values from the cachepolicy configuration key.

    policyname(bool): Unsets the policyname value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    storeingroup(bool): Unsets the storeingroup value.

    invalgroups(bool): Unsets the invalgroups value.

    invalobjects(bool): Unsets the invalobjects value.

    undefaction(bool): Unsets the undefaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.unset_cachepolicy <args>

    '''

    result = {}

    payload = {'cachepolicy': {}}

    if policyname:
        payload['cachepolicy']['policyname'] = True

    if rule:
        payload['cachepolicy']['rule'] = True

    if action:
        payload['cachepolicy']['action'] = True

    if storeingroup:
        payload['cachepolicy']['storeingroup'] = True

    if invalgroups:
        payload['cachepolicy']['invalgroups'] = True

    if invalobjects:
        payload['cachepolicy']['invalobjects'] = True

    if undefaction:
        payload['cachepolicy']['undefaction'] = True

    if newname:
        payload['cachepolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/cachepolicy?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_cachecontentgroup(name=None, weakposrelexpiry=None, heurexpiryparam=None, relexpiry=None,
                             relexpirymillisec=None, absexpiry=None, absexpirygmt=None, weaknegrelexpiry=None,
                             hitparams=None, invalparams=None, ignoreparamvaluecase=None, matchcookies=None,
                             invalrestrictedtohost=None, polleverytime=None, ignorereloadreq=None, removecookies=None,
                             prefetch=None, prefetchperiod=None, prefetchperiodmillisec=None, prefetchmaxpending=None,
                             flashcache=None, expireatlastbyte=None, insertvia=None, insertage=None, insertetag=None,
                             cachecontrol=None, quickabortsize=None, minressize=None, maxressize=None, memlimit=None,
                             ignorereqcachinghdrs=None, minhits=None, alwaysevalpolicies=None, persistha=None,
                             pinned=None, lazydnsresolve=None, hitselector=None, invalselector=None, ns_type=None,
                             query=None, host=None, selectorvalue=None, tosecondary=None, save=False):
    '''
    Update the running configuration for the cachecontentgroup config key.

    name(str): Name for the content group. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the content group is created. Minimum length = 1

    weakposrelexpiry(int): Relative expiry time, in seconds, for expiring positive responses with response codes between 200
        and 399. Cannot be used in combination with other Expiry attributes. Similar to -relExpiry but has lower
        precedence. Minimum value = 0 Maximum value = 31536000

    heurexpiryparam(int): Heuristic expiry time, in percent of the duration, since the object was last modified. Minimum
        value = 0 Maximum value = 100

    relexpiry(int): Relative expiry time, in seconds, after which to expire an object cached in this content group. Minimum
        value = 0 Maximum value = 31536000

    relexpirymillisec(int): Relative expiry time, in milliseconds, after which to expire an object cached in this content
        group. Minimum value = 0 Maximum value = 86400000

    absexpiry(list(str)): Local time, up to 4 times a day, at which all objects in the content group must expire.   CLI
        Users: For example, to specify that the objects in the content group should expire by 11:00 PM, type the
        following command: add cache contentgroup ;lt;contentgroup name;gt; -absexpiry 23:00  To specify that the objects
        in the content group should expire at 10:00 AM, 3 PM, 6 PM, and 11:00 PM, type: add cache contentgroup
        ;lt;contentgroup name;gt; -absexpiry 10:00 15:00 18:00 23:00.

    absexpirygmt(list(str)): Coordinated Universal Time (GMT), up to 4 times a day, when all objects in the content group
        must expire.

    weaknegrelexpiry(int): Relative expiry time, in seconds, for expiring negative responses. This value is used only if the
        expiry time cannot be determined from any other source. It is applicable only to the following status codes: 307,
        403, 404, and 410. Minimum value = 0 Maximum value = 31536000

    hitparams(list(str)): Parameters to use for parameterized hit evaluation of an object. Up to 128 parameters can be
        specified. Mutually exclusive with the Hit Selector parameter. Minimum length = 1

    invalparams(list(str)): Parameters for parameterized invalidation of an object. You can specify up to 8 parameters.
        Mutually exclusive with invalSelector. Minimum length = 1

    ignoreparamvaluecase(str): Ignore case when comparing parameter values during parameterized hit evaluation. (Parameter
        value case is ignored by default during parameterized invalidation.). Possible values = YES, NO

    matchcookies(str): Evaluate for parameters in the cookie header also. Possible values = YES, NO

    invalrestrictedtohost(str): Take the host header into account during parameterized invalidation. Possible values = YES,
        NO

    polleverytime(str): Always poll for the objects in this content group. That is, retrieve the objects from the origin
        server whenever they are requested. Default value: NO Possible values = YES, NO

    ignorereloadreq(str): Ignore any request to reload a cached object from the origin server. To guard against Denial of
        Service attacks, set this parameter to YES. For RFC-compliant behavior, set it to NO. Default value: YES Possible
        values = YES, NO

    removecookies(str): Remove cookies from responses. Default value: YES Possible values = YES, NO

    prefetch(str): Attempt to refresh objects that are about to go stale. Default value: YES Possible values = YES, NO

    prefetchperiod(int): Time period, in seconds before an objects calculated expiry time, during which to attempt prefetch.
        Minimum value = 0 Maximum value = 4294967294

    prefetchperiodmillisec(int): Time period, in milliseconds before an objects calculated expiry time, during which to
        attempt prefetch. Minimum value = 0 Maximum value = 4294967290

    prefetchmaxpending(int): Maximum number of outstanding prefetches that can be queued for the content group. Minimum value
        = 0 Maximum value = 4294967294

    flashcache(str): Perform flash cache. Mutually exclusive with Poll Every Time (PET) on the same content group. Default
        value: NO Possible values = YES, NO

    expireatlastbyte(str): Force expiration of the content immediately after the response is downloaded (upon receipt of the
        last byte of the response body). Applicable only to positive responses. Default value: NO Possible values = YES,
        NO

    insertvia(str): Insert a Via header into the response. Default value: YES Possible values = YES, NO

    insertage(str): Insert an Age header into the response. An Age header contains information about the age of the object,
        in seconds, as calculated by the integrated cache. Default value: YES Possible values = YES, NO

    insertetag(str): Insert an ETag header in the response. With ETag header insertion, the integrated cache does not serve
        full responses on repeat requests. Default value: YES Possible values = YES, NO

    cachecontrol(str): Insert a Cache-Control header into the response. Minimum length = 1

    quickabortsize(int): If the size of an object that is being downloaded is less than or equal to the quick abort value,
        and a client aborts during the download, the cache stops downloading the response. If the object is larger than
        the quick abort size, the cache continues to download the response. Default value: 4194303 Minimum value = 0
        Maximum value = 4194303

    minressize(int): Minimum size of a response that can be cached in this content group.  Default minimum response size is
        0. Minimum value = 0 Maximum value = 2097151

    maxressize(int): Maximum size of a response that can be cached in this content group. Default value: 80 Minimum value = 0
        Maximum value = 2097151

    memlimit(int): Maximum amount of memory that the cache can use. The effective limit is based on the available memory of
        the NetScaler appliance. Default value: 65536

    ignorereqcachinghdrs(str): Ignore Cache-Control and Pragma headers in the incoming request. Default value: YES Possible
        values = YES, NO

    minhits(int): Number of hits that qualifies a response for storage in this content group. Default value: 0

    alwaysevalpolicies(str): Force policy evaluation for each response arriving from the origin server. Cannot be set to YES
        if the Prefetch parameter is also set to YES. Default value: NO Possible values = YES, NO

    persistha(str): Setting persistHA to YES causes IC to save objects in contentgroup to Secondary node in HA deployment.
        Default value: NO Possible values = YES, NO

    pinned(str): Do not flush objects from this content group under memory pressure. Default value: NO Possible values = YES,
        NO

    lazydnsresolve(str): Perform DNS resolution for responses only if the destination IP address in the request does not
        match the destination IP address of the cached response. Default value: YES Possible values = YES, NO

    hitselector(str): Selector for evaluating whether an object gets stored in a particular content group. A selector is an
        abstraction for a collection of PIXL expressions.

    invalselector(str): Selector for invalidating objects in the content group. A selector is an abstraction for a collection
        of PIXL expressions.

    ns_type(str): The type of the content group. Default value: HTTP Possible values = HTTP, MYSQL, MSSQL

    query(str): Query string specifying individual objects to flush from this group by using parameterized invalidation. If
        this parameter is not set, all objects are flushed from the group. Minimum length = 1

    host(str): Flush only objects that belong to the specified host. Do not use except with parameterized invalidation. Also,
        the Invalidation Restricted to Host parameter for the group must be set to YES. Minimum length = 1

    selectorvalue(str): Value of the selector to be used for flushing objects from the content group. Requires that an
        invalidation selector be configured for the content group. Minimum length = 1

    tosecondary(str): content group whose objects are to be sent to secondary. Default value: NO Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.update_cachecontentgroup <args>

    '''

    result = {}

    payload = {'cachecontentgroup': {}}

    if name:
        payload['cachecontentgroup']['name'] = name

    if weakposrelexpiry:
        payload['cachecontentgroup']['weakposrelexpiry'] = weakposrelexpiry

    if heurexpiryparam:
        payload['cachecontentgroup']['heurexpiryparam'] = heurexpiryparam

    if relexpiry:
        payload['cachecontentgroup']['relexpiry'] = relexpiry

    if relexpirymillisec:
        payload['cachecontentgroup']['relexpirymillisec'] = relexpirymillisec

    if absexpiry:
        payload['cachecontentgroup']['absexpiry'] = absexpiry

    if absexpirygmt:
        payload['cachecontentgroup']['absexpirygmt'] = absexpirygmt

    if weaknegrelexpiry:
        payload['cachecontentgroup']['weaknegrelexpiry'] = weaknegrelexpiry

    if hitparams:
        payload['cachecontentgroup']['hitparams'] = hitparams

    if invalparams:
        payload['cachecontentgroup']['invalparams'] = invalparams

    if ignoreparamvaluecase:
        payload['cachecontentgroup']['ignoreparamvaluecase'] = ignoreparamvaluecase

    if matchcookies:
        payload['cachecontentgroup']['matchcookies'] = matchcookies

    if invalrestrictedtohost:
        payload['cachecontentgroup']['invalrestrictedtohost'] = invalrestrictedtohost

    if polleverytime:
        payload['cachecontentgroup']['polleverytime'] = polleverytime

    if ignorereloadreq:
        payload['cachecontentgroup']['ignorereloadreq'] = ignorereloadreq

    if removecookies:
        payload['cachecontentgroup']['removecookies'] = removecookies

    if prefetch:
        payload['cachecontentgroup']['prefetch'] = prefetch

    if prefetchperiod:
        payload['cachecontentgroup']['prefetchperiod'] = prefetchperiod

    if prefetchperiodmillisec:
        payload['cachecontentgroup']['prefetchperiodmillisec'] = prefetchperiodmillisec

    if prefetchmaxpending:
        payload['cachecontentgroup']['prefetchmaxpending'] = prefetchmaxpending

    if flashcache:
        payload['cachecontentgroup']['flashcache'] = flashcache

    if expireatlastbyte:
        payload['cachecontentgroup']['expireatlastbyte'] = expireatlastbyte

    if insertvia:
        payload['cachecontentgroup']['insertvia'] = insertvia

    if insertage:
        payload['cachecontentgroup']['insertage'] = insertage

    if insertetag:
        payload['cachecontentgroup']['insertetag'] = insertetag

    if cachecontrol:
        payload['cachecontentgroup']['cachecontrol'] = cachecontrol

    if quickabortsize:
        payload['cachecontentgroup']['quickabortsize'] = quickabortsize

    if minressize:
        payload['cachecontentgroup']['minressize'] = minressize

    if maxressize:
        payload['cachecontentgroup']['maxressize'] = maxressize

    if memlimit:
        payload['cachecontentgroup']['memlimit'] = memlimit

    if ignorereqcachinghdrs:
        payload['cachecontentgroup']['ignorereqcachinghdrs'] = ignorereqcachinghdrs

    if minhits:
        payload['cachecontentgroup']['minhits'] = minhits

    if alwaysevalpolicies:
        payload['cachecontentgroup']['alwaysevalpolicies'] = alwaysevalpolicies

    if persistha:
        payload['cachecontentgroup']['persistha'] = persistha

    if pinned:
        payload['cachecontentgroup']['pinned'] = pinned

    if lazydnsresolve:
        payload['cachecontentgroup']['lazydnsresolve'] = lazydnsresolve

    if hitselector:
        payload['cachecontentgroup']['hitselector'] = hitselector

    if invalselector:
        payload['cachecontentgroup']['invalselector'] = invalselector

    if ns_type:
        payload['cachecontentgroup']['type'] = ns_type

    if query:
        payload['cachecontentgroup']['query'] = query

    if host:
        payload['cachecontentgroup']['host'] = host

    if selectorvalue:
        payload['cachecontentgroup']['selectorvalue'] = selectorvalue

    if tosecondary:
        payload['cachecontentgroup']['tosecondary'] = tosecondary

    execution = __proxy__['citrixns.put']('config/cachecontentgroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_cacheparameter(memlimit=None, via=None, verifyusing=None, maxpostlen=None, prefetchmaxpending=None,
                          enablebypass=None, undefaction=None, enablehaobjpersist=None, save=False):
    '''
    Update the running configuration for the cacheparameter config key.

    memlimit(int): Amount of memory available for storing the cache objects. In practice, the amount of memory available for
        caching can be less than half the total memory of the NetScaler appliance.

    via(str): String to include in the Via header. A Via header is inserted into all responses served from a content group if
        its Insert Via flag is set. Minimum length = 1

    verifyusing(str): Criteria for deciding whether a cached object can be served for an incoming HTTP request. Available
        settings function as follows: HOSTNAME - The URL, host name, and host port values in the incoming HTTP request
        header must match the cache policy. The IP address and the TCP port of the destination host are not evaluated. Do
        not use the HOSTNAME setting unless you are certain that no rogue client can access a rogue server through the
        cache.  HOSTNAME_AND_IP - The URL, host name, host port in the incoming HTTP request header, and the IP address
        and TCP port of the destination server, must match the cache policy. DNS - The URL, host name and host port in
        the incoming HTTP request, and the TCP port must match the cache policy. The host name is used for DNS lookup of
        the destination servers IP address, and is compared with the set of addresses returned by the DNS lookup.
        Possible values = HOSTNAME, HOSTNAME_AND_IP, DNS

    maxpostlen(int): Maximum number of POST body bytes to consider when evaluating parameters for a content group for which
        you have configured hit parameters and invalidation parameters. Default value: 4096 Minimum value = 0 Maximum
        value = 131072

    prefetchmaxpending(int): Maximum number of outstanding prefetches in the Integrated Cache.

    enablebypass(str): Evaluate the request-time policies before attempting hit selection. If set to NO, an incoming request
        for which a matching object is found in cache storage results in a response regardless of the policy
        configuration. If the request matches a policy with a NOCACHE action, the request bypasses all cache processing.
        This parameter does not affect processing of requests that match any invalidation policy. Possible values = YES,
        NO

    undefaction(str): Action to take when a policy cannot be evaluated. Possible values = NOCACHE, RESET

    enablehaobjpersist(str): The HA object persisting parameter. When this value is set to YES, cache objects can be synced
        to Secondary in a HA deployment. If set to NO, objects will never be synced to Secondary node. Default value: NO
        Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.update_cacheparameter <args>

    '''

    result = {}

    payload = {'cacheparameter': {}}

    if memlimit:
        payload['cacheparameter']['memlimit'] = memlimit

    if via:
        payload['cacheparameter']['via'] = via

    if verifyusing:
        payload['cacheparameter']['verifyusing'] = verifyusing

    if maxpostlen:
        payload['cacheparameter']['maxpostlen'] = maxpostlen

    if prefetchmaxpending:
        payload['cacheparameter']['prefetchmaxpending'] = prefetchmaxpending

    if enablebypass:
        payload['cacheparameter']['enablebypass'] = enablebypass

    if undefaction:
        payload['cacheparameter']['undefaction'] = undefaction

    if enablehaobjpersist:
        payload['cacheparameter']['enablehaobjpersist'] = enablehaobjpersist

    execution = __proxy__['citrixns.put']('config/cacheparameter', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_cachepolicy(policyname=None, rule=None, action=None, storeingroup=None, invalgroups=None, invalobjects=None,
                       undefaction=None, newname=None, save=False):
    '''
    Update the running configuration for the cachepolicy config key.

    policyname(str): Name for the policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Can be changed after the policy is created. Minimum length = 1

    rule(str): Expression against which the traffic is evaluated. Note: Maximum length of a string literal in the expression
        is 255 characters. A longer string can be split into smaller strings of up to 255 characters each, and the
        smaller strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" The following requirements apply only to
        the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression in double
        quotation marks. * If the expression itself includes double quotation marks, escape the quotations by using the
        \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks.

    action(str): Action to apply to content that matches the policy.  * CACHE or MAY_CACHE action - positive cachability
        policy * NOCACHE or MAY_NOCACHE action - negative cachability policy * INVAL action - Dynamic Invalidation
        Policy. Possible values = CACHE, NOCACHE, MAY_CACHE, MAY_NOCACHE, INVAL

    storeingroup(str): Name of the content group in which to store the object when the final result of policy evaluation is
        CACHE. The content group must exist before being mentioned here. Use the "show cache contentgroup" command to
        view the list of existing content groups. Minimum length = 1

    invalgroups(list(str)): Content group(s) to be invalidated when the INVAL action is applied. Maximum number of content
        groups that can be specified is 16. Minimum length = 1

    invalobjects(list(str)): Content groups(s) in which the objects will be invalidated if the action is INVAL. Minimum
        length = 1

    undefaction(str): Action to be performed when the result of rule evaluation is undefined. Possible values = NOCACHE,
        RESET

    newname(str): New name for the cache policy. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.update_cachepolicy <args>

    '''

    result = {}

    payload = {'cachepolicy': {}}

    if policyname:
        payload['cachepolicy']['policyname'] = policyname

    if rule:
        payload['cachepolicy']['rule'] = rule

    if action:
        payload['cachepolicy']['action'] = action

    if storeingroup:
        payload['cachepolicy']['storeingroup'] = storeingroup

    if invalgroups:
        payload['cachepolicy']['invalgroups'] = invalgroups

    if invalobjects:
        payload['cachepolicy']['invalobjects'] = invalobjects

    if undefaction:
        payload['cachepolicy']['undefaction'] = undefaction

    if newname:
        payload['cachepolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/cachepolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_cacheselector(selectorname=None, rule=None, save=False):
    '''
    Update the running configuration for the cacheselector config key.

    selectorname(str): Name for the selector. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.

    rule(list(str)): One or multiple PIXL expressions for evaluating an HTTP request or response. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' integrated_caching.update_cacheselector <args>

    '''

    result = {}

    payload = {'cacheselector': {}}

    if selectorname:
        payload['cacheselector']['selectorname'] = selectorname

    if rule:
        payload['cacheselector']['rule'] = rule

    execution = __proxy__['citrixns.put']('config/cacheselector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
