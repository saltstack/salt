# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the policy key.

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

__virtualname__ = 'policy'


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

    return False, 'The policy execution module can only be loaded for citrixns proxy minions.'


def add_policydataset(name=None, ns_type=None, indextype=None, comment=None, save=False):
    '''
    Add a new policydataset to the running configuration.

    name(str): Name of the dataset. Must not exceed 127 characters. Minimum length = 1

    ns_type(str): Type of value to bind to the dataset. Possible values = ipv4, number, ipv6, ulong, double, mac

    indextype(str): Index type. Possible values = Auto-generated, User-defined

    comment(str): Any comments to preserve information about this dataset.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policydataset <args>

    '''

    result = {}

    payload = {'policydataset': {}}

    if name:
        payload['policydataset']['name'] = name

    if ns_type:
        payload['policydataset']['type'] = ns_type

    if indextype:
        payload['policydataset']['indextype'] = indextype

    if comment:
        payload['policydataset']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/policydataset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policydataset_value_binding(value=None, name=None, index=None, save=False):
    '''
    Add a new policydataset_value_binding to the running configuration.

    value(str): Value of the specified type that is associated with the dataset.

    name(str): Name of the dataset to which to bind the value. Minimum length = 1

    index(int): The index of the value (ipv4, ipv6, number) associated with the set.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policydataset_value_binding <args>

    '''

    result = {}

    payload = {'policydataset_value_binding': {}}

    if value:
        payload['policydataset_value_binding']['value'] = value

    if name:
        payload['policydataset_value_binding']['name'] = name

    if index:
        payload['policydataset_value_binding']['index'] = index

    execution = __proxy__['citrixns.post']('config/policydataset_value_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policyexpression(name=None, value=None, description=None, comment=None, clientsecuritymessage=None, ns_type=None,
                         save=False):
    '''
    Add a new policyexpression to the running configuration.

    name(str): Unique name for the expression. Not case sensitive. Must begin with an ASCII letter or underscore (_)
        character, and must consist only of ASCII alphanumeric or underscore characters. Must not begin with re or xp or
        be a word reserved for use as a default syntax expression qualifier prefix (such as HTTP) or enumeration value
        (such as ASCII). Must not be the name of an existing named expression, pattern set, dataset, stringmap, or HTTP
        callout. Minimum length = 1

    value(str): Expression string. For example: http.req.body(100).contains("this").

    description(str): Description for the expression.

    comment(str): Any comments associated with the expression. Displayed upon viewing the policy expression.

    clientsecuritymessage(str): Message to display if the expression fails. Allowed for classic end-point check expressions
        only. Minimum length = 1

    ns_type(str): Type of expression. Can be a classic or default syntax (advanced) expression. Possible values = CLASSIC,
        ADVANCED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policyexpression <args>

    '''

    result = {}

    payload = {'policyexpression': {}}

    if name:
        payload['policyexpression']['name'] = name

    if value:
        payload['policyexpression']['value'] = value

    if description:
        payload['policyexpression']['description'] = description

    if comment:
        payload['policyexpression']['comment'] = comment

    if clientsecuritymessage:
        payload['policyexpression']['clientsecuritymessage'] = clientsecuritymessage

    if ns_type:
        payload['policyexpression']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/policyexpression', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policyhttpcallout(name=None, ipaddress=None, port=None, vserver=None, returntype=None, httpmethod=None,
                          hostexpr=None, urlstemexpr=None, headers=None, parameters=None, bodyexpr=None,
                          fullreqexpr=None, scheme=None, resultexpr=None, cacheforsecs=None, comment=None, save=False):
    '''
    Add a new policyhttpcallout to the running configuration.

    name(str): Name for the HTTP callout. Not case sensitive. Must begin with an ASCII letter or underscore (_) character,
        and must consist only of ASCII alphanumeric or underscore characters. Must not begin with re or xp or be a word
        reserved for use as a default syntax expression qualifier prefix (such as HTTP) or enumeration value (such as
        ASCII). Must not be the name of an existing named expression, pattern set, dataset, stringmap, or HTTP callout.
        Minimum length = 1

    ipaddress(str): IP Address of the server (callout agent) to which the callout is sent. Can be an IPv4 or IPv6 address.
        Mutually exclusive with the Virtual Server parameter. Therefore, you cannot set the ;lt;IP Address, Port;gt; and
        the Virtual Server in the same HTTP callout.

    port(int): Server port to which the HTTP callout agent is mapped. Mutually exclusive with the Virtual Server parameter.
        Therefore, you cannot set the ;lt;IP Address, Port;gt; and the Virtual Server in the same HTTP callout. Minimum
        value = 1

    vserver(str): Name of the load balancing, content switching, or cache redirection virtual server (the callout agent) to
        which the HTTP callout is sent. The service type of the virtual server must be HTTP. Mutually exclusive with the
        IP address and port parameters. Therefore, you cannot set the ;lt;IP Address, Port;gt; and the Virtual Server in
        the same HTTP callout. Minimum length = 1

    returntype(str): Type of data that the target callout agent returns in response to the callout.  Available settings
        function as follows: * TEXT - Treat the returned value as a text string.  * NUM - Treat the returned value as a
        number. * BOOL - Treat the returned value as a Boolean value.  Note: You cannot change the return type after it
        is set. Possible values = BOOL, NUM, TEXT

    httpmethod(str): Method used in the HTTP request that this callout sends. Mutually exclusive with the full HTTP request
        expression. Possible values = GET, POST

    hostexpr(str): Default Syntax string expression to configure the Host header. Can contain a literal value (for example,
        10.101.10.11) or a derived value (for example, http.req.header("Host")). The literal value can be an IP address
        or a fully qualified domain name. Mutually exclusive with the full HTTP request expression. Minimum length = 1

    urlstemexpr(str): Default Syntax string expression for generating the URL stem. Can contain a literal string (for
        example, "/mysite/index.html") or an expression that derives the value (for example, http.req.url). Mutually
        exclusive with the full HTTP request expression. Minimum length = 1

    headers(list(str)): One or more headers to insert into the HTTP request. Each header is specified as "name(expr)", where
        expr is a default syntax expression that is evaluated at runtime to provide the value for the named header. You
        can configure a maximum of eight headers for an HTTP callout. Mutually exclusive with the full HTTP request
        expression.

    parameters(list(str)): One or more query parameters to insert into the HTTP request URL (for a GET request) or into the
        request body (for a POST request). Each parameter is specified as "name(expr)", where expr is an default syntax
        expression that is evaluated at run time to provide the value for the named parameter (name=value). The parameter
        values are URL encoded. Mutually exclusive with the full HTTP request expression.

    bodyexpr(str): An advanced string expression for generating the body of the request. The expression can contain a literal
        string or an expression that derives the value (for example, client.ip.src). Mutually exclusive with
        -fullReqExpr. Minimum length = 1

    fullreqexpr(str): Exact HTTP request, in the form of a default syntax expression, which the NetScaler appliance sends to
        the callout agent. If you set this parameter, you must not include HTTP method, host expression, URL stem
        expression, headers, or parameters. The request expression is constrained by the feature for which the callout is
        used. For example, an HTTP.RES expression cannot be used in a request-time policy bank or in a TCP content
        switching policy bank. The NetScaler appliance does not check the validity of this request. You must manually
        validate the request. Minimum length = 1

    scheme(str): Type of scheme for the callout server. Possible values = http, https

    resultexpr(str): Expression that extracts the callout results from the response sent by the HTTP callout agent. Must be a
        response based expression, that is, it must begin with HTTP.RES. The operations in this expression must match the
        return type. For example, if you configure a return type of TEXT, the result expression must be a text based
        expression. If the return type is NUM, the result expression (resultExpr) must return a numeric value, as in the
        following example: http.res.body(10000).length. Minimum length = 1

    cacheforsecs(int): Duration, in seconds, for which the callout response is cached. The cached responses are stored in an
        integrated caching content group named "calloutContentGroup". If no duration is configured, the callout responses
        will not be cached unless normal caching configuration is used to cache them. This parameter takes precedence
        over any normal caching configuration that would otherwise apply to these responses.  Note that the
        calloutContentGroup definition may not be modified or removed nor may it be used with other cache policies.
        Minimum value = 1 Maximum value = 31536000

    comment(str): Any comments to preserve information about this HTTP callout.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policyhttpcallout <args>

    '''

    result = {}

    payload = {'policyhttpcallout': {}}

    if name:
        payload['policyhttpcallout']['name'] = name

    if ipaddress:
        payload['policyhttpcallout']['ipaddress'] = ipaddress

    if port:
        payload['policyhttpcallout']['port'] = port

    if vserver:
        payload['policyhttpcallout']['vserver'] = vserver

    if returntype:
        payload['policyhttpcallout']['returntype'] = returntype

    if httpmethod:
        payload['policyhttpcallout']['httpmethod'] = httpmethod

    if hostexpr:
        payload['policyhttpcallout']['hostexpr'] = hostexpr

    if urlstemexpr:
        payload['policyhttpcallout']['urlstemexpr'] = urlstemexpr

    if headers:
        payload['policyhttpcallout']['headers'] = headers

    if parameters:
        payload['policyhttpcallout']['parameters'] = parameters

    if bodyexpr:
        payload['policyhttpcallout']['bodyexpr'] = bodyexpr

    if fullreqexpr:
        payload['policyhttpcallout']['fullreqexpr'] = fullreqexpr

    if scheme:
        payload['policyhttpcallout']['scheme'] = scheme

    if resultexpr:
        payload['policyhttpcallout']['resultexpr'] = resultexpr

    if cacheforsecs:
        payload['policyhttpcallout']['cacheforsecs'] = cacheforsecs

    if comment:
        payload['policyhttpcallout']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/policyhttpcallout', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policymap(mappolicyname=None, sd=None, su=None, td=None, tu=None, save=False):
    '''
    Add a new policymap to the running configuration.

    mappolicyname(str): Name for the map policy. Must begin with a letter, number, or the underscore (_) character and must
        consist only of letters, numbers, and the hash (#), period (.), colon (:), space ( ), at (@), equals (=), hyphen
        (-), and underscore (_) characters.  CLI Users: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my map" or my map). Minimum length = 1

    sd(str): Publicly known source domain name. This is the domain name with which a client request arrives at a reverse
        proxy virtual server for cache redirection. If you specify a source domain, you must specify a target domain.
        Minimum length = 1

    su(str): Source URL. Specify all or part of the source URL, in the following format: /[[prefix] [*]] [.suffix]. Minimum
        length = 1

    td(str): Target domain name sent to the server. The source domain name is replaced with this domain name. Minimum length
        = 1

    tu(str): Target URL. Specify the target URL in the following format: /[[prefix] [*]][.suffix]. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policymap <args>

    '''

    result = {}

    payload = {'policymap': {}}

    if mappolicyname:
        payload['policymap']['mappolicyname'] = mappolicyname

    if sd:
        payload['policymap']['sd'] = sd

    if su:
        payload['policymap']['su'] = su

    if td:
        payload['policymap']['td'] = td

    if tu:
        payload['policymap']['tu'] = tu

    execution = __proxy__['citrixns.post']('config/policymap', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policypatset(name=None, indextype=None, comment=None, save=False):
    '''
    Add a new policypatset to the running configuration.

    name(str): Unique name of the pattern set. Not case sensitive. Must begin with an ASCII letter or underscore (_)
        character and must contain only alphanumeric and underscore characters. Must not be the name of an existing named
        expression, pattern set, dataset, string map, or HTTP callout. Minimum length = 1

    indextype(str): Index type. Possible values = Auto-generated, User-defined

    comment(str): Any comments to preserve information about this patset.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policypatset <args>

    '''

    result = {}

    payload = {'policypatset': {}}

    if name:
        payload['policypatset']['name'] = name

    if indextype:
        payload['policypatset']['indextype'] = indextype

    if comment:
        payload['policypatset']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/policypatset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policypatset_pattern_binding(string=None, builtin=None, name=None, charset=None, index=None, save=False):
    '''
    Add a new policypatset_pattern_binding to the running configuration.

    string(str): String of characters that constitutes a pattern. For more information about the characters that can be used,
        refer to the character set parameter. Note: Minimum length for pattern sets used in rewrite actions of type
        REPLACE_ALL, DELETE_ALL, INSERT_AFTER_ALL, and INSERT_BEFORE_ALL, is three characters.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    name(str): Name of the pattern set to which to bind the string. Minimum length = 1

    charset(str): Character set associated with the characters in the string. Note: UTF-8 characters can be entered directly
        (if the UI supports it) or can be encoded as a sequence of hexadecimal bytes \\xNN. For example, the UTF-8
        character ? can be encoded as \\xC3\\xBC. Possible values = ASCII, UTF_8

    index(int): The index of the string associated with the patset.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policypatset_pattern_binding <args>

    '''

    result = {}

    payload = {'policypatset_pattern_binding': {}}

    if string:
        payload['policypatset_pattern_binding']['String'] = string

    if builtin:
        payload['policypatset_pattern_binding']['builtin'] = builtin

    if name:
        payload['policypatset_pattern_binding']['name'] = name

    if charset:
        payload['policypatset_pattern_binding']['charset'] = charset

    if index:
        payload['policypatset_pattern_binding']['index'] = index

    execution = __proxy__['citrixns.post']('config/policypatset_pattern_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policystringmap(name=None, comment=None, save=False):
    '''
    Add a new policystringmap to the running configuration.

    name(str): Unique name for the string map. Not case sensitive. Must begin with an ASCII letter or underscore (_)
        character, and must consist only of ASCII alphanumeric or underscore characters. Must not begin with re or xp or
        be a word reserved for use as a default syntax expression qualifier prefix (such as HTTP) or enumeration value
        (such as ASCII). Must not be the name of an existing named expression, pattern set, dataset, string map, or HTTP
        callout. Minimum length = 1

    comment(str): Comments associated with the string map.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policystringmap <args>

    '''

    result = {}

    payload = {'policystringmap': {}}

    if name:
        payload['policystringmap']['name'] = name

    if comment:
        payload['policystringmap']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/policystringmap', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policystringmap_pattern_binding(value=None, name=None, key=None, save=False):
    '''
    Add a new policystringmap_pattern_binding to the running configuration.

    value(str): Character string constituting the value associated with the key. This value is returned when processed data
        matches the associated key. Refer to the key parameter for details of the value character set. Minimum length =
        1

    name(str): Name of the string map to which to bind the key-value pair. Minimum length = 1

    key(str): Character string constituting the key to be bound to the string map. The key is matched against the data
        processed by the operation that uses the string map. The default character set is ASCII. UTF-8 characters can be
        included if the character set is UTF-8. UTF-8 characters can be entered directly (if the UI supports it) or can
        be encoded as a sequence of hexadecimal bytes \\xNN. For example, the UTF-8 character ? can be encoded as
        \\xC3\\xBC. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policystringmap_pattern_binding <args>

    '''

    result = {}

    payload = {'policystringmap_pattern_binding': {}}

    if value:
        payload['policystringmap_pattern_binding']['value'] = value

    if name:
        payload['policystringmap_pattern_binding']['name'] = name

    if key:
        payload['policystringmap_pattern_binding']['key'] = key

    execution = __proxy__['citrixns.post']('config/policystringmap_pattern_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_policyurlset(name=None, comment=None, overwrite=None, delimiter=None, rowseparator=None, url=None, interval=None,
                     privateset=None, canaryurl=None, save=False):
    '''
    Add a new policyurlset to the running configuration.

    name(str): Unique name of the url set. Not case sensitive. Must begin with an ASCII letter or underscore (_) character
        and must contain only alphanumeric and underscore characters. Must not be the name of an existing named
        expression, pattern set, dataset, string map, or HTTP callout. Minimum length = 1 Maximum length = 127

    comment(str): Any comments to preserve information about this url set.

    overwrite(bool): Overwrites the existing file. Default value: 0

    delimiter(str): CSV file record delimiter. Default value: 44

    rowseparator(str): CSV file row separator. Default value: 10

    url(str): URL (protocol, host, path and file name) from where the CSV (comma separated file) file will be imported or
        exported. Each record/line will one entry within the urlset. The first field contains the URL pattern, subsequent
        fields contains the metadata, if available. HTTP, HTTPS and FTP protocols are supported. NOTE: The operation
        fails if the destination HTTPS server requires client certificate authentication for access. Minimum length = 1
        Maximum length = 2047

    interval(int): The interval, in seconds, rounded down to the nearest 15 minutes, at which the update of urlset occurs.
        Default value: 0 Minimum value = 0 Maximum value = 2592000

    privateset(bool): Prevent this urlset from being exported. Default value: 0

    canaryurl(str): Add this URL to this urlset. Used for testing when contents of urlset is kept confidential. Minimum
        length = 1 Maximum length = 2047

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.add_policyurlset <args>

    '''

    result = {}

    payload = {'policyurlset': {}}

    if name:
        payload['policyurlset']['name'] = name

    if comment:
        payload['policyurlset']['comment'] = comment

    if overwrite:
        payload['policyurlset']['overwrite'] = overwrite

    if delimiter:
        payload['policyurlset']['delimiter'] = delimiter

    if rowseparator:
        payload['policyurlset']['rowseparator'] = rowseparator

    if url:
        payload['policyurlset']['url'] = url

    if interval:
        payload['policyurlset']['interval'] = interval

    if privateset:
        payload['policyurlset']['privateset'] = privateset

    if canaryurl:
        payload['policyurlset']['canaryurl'] = canaryurl

    execution = __proxy__['citrixns.post']('config/policyurlset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_policydataset(name=None, ns_type=None, indextype=None, comment=None):
    '''
    Show the running configuration for the policydataset config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    indextype(str): Filters results that only match the indextype field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policydataset

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if indextype:
        search_filter.append(['indextype', indextype])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policydataset{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policydataset')

    return response


def get_policydataset_binding():
    '''
    Show the running configuration for the policydataset_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policydataset_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policydataset_binding'), 'policydataset_binding')

    return response


def get_policydataset_value_binding(value=None, name=None, index=None):
    '''
    Show the running configuration for the policydataset_value_binding config key.

    value(str): Filters results that only match the value field.

    name(str): Filters results that only match the name field.

    index(int): Filters results that only match the index field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policydataset_value_binding

    '''

    search_filter = []

    if value:
        search_filter.append(['value', value])

    if name:
        search_filter.append(['name', name])

    if index:
        search_filter.append(['index', index])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policydataset_value_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policydataset_value_binding')

    return response


def get_policyevaluation(expression=None, action=None, ns_type=None, input=None):
    '''
    Show the running configuration for the policyevaluation config key.

    expression(str): Filters results that only match the expression field.

    action(str): Filters results that only match the action field.

    ns_type(str): Filters results that only match the type field.

    input(str): Filters results that only match the input field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policyevaluation

    '''

    search_filter = []

    if expression:
        search_filter.append(['expression', expression])

    if action:
        search_filter.append(['action', action])

    if ns_type:
        search_filter.append(['type', ns_type])

    if input:
        search_filter.append(['input', input])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policyevaluation{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policyevaluation')

    return response


def get_policyexpression(name=None, value=None, description=None, comment=None, clientsecuritymessage=None,
                         ns_type=None):
    '''
    Show the running configuration for the policyexpression config key.

    name(str): Filters results that only match the name field.

    value(str): Filters results that only match the value field.

    description(str): Filters results that only match the description field.

    comment(str): Filters results that only match the comment field.

    clientsecuritymessage(str): Filters results that only match the clientsecuritymessage field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policyexpression

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if value:
        search_filter.append(['value', value])

    if description:
        search_filter.append(['description', description])

    if comment:
        search_filter.append(['comment', comment])

    if clientsecuritymessage:
        search_filter.append(['clientsecuritymessage', clientsecuritymessage])

    if ns_type:
        search_filter.append(['type', ns_type])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policyexpression{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policyexpression')

    return response


def get_policyhttpcallout(name=None, ipaddress=None, port=None, vserver=None, returntype=None, httpmethod=None,
                          hostexpr=None, urlstemexpr=None, headers=None, parameters=None, bodyexpr=None,
                          fullreqexpr=None, scheme=None, resultexpr=None, cacheforsecs=None, comment=None):
    '''
    Show the running configuration for the policyhttpcallout config key.

    name(str): Filters results that only match the name field.

    ipaddress(str): Filters results that only match the ipaddress field.

    port(int): Filters results that only match the port field.

    vserver(str): Filters results that only match the vserver field.

    returntype(str): Filters results that only match the returntype field.

    httpmethod(str): Filters results that only match the httpmethod field.

    hostexpr(str): Filters results that only match the hostexpr field.

    urlstemexpr(str): Filters results that only match the urlstemexpr field.

    headers(list(str)): Filters results that only match the headers field.

    parameters(list(str)): Filters results that only match the parameters field.

    bodyexpr(str): Filters results that only match the bodyexpr field.

    fullreqexpr(str): Filters results that only match the fullreqexpr field.

    scheme(str): Filters results that only match the scheme field.

    resultexpr(str): Filters results that only match the resultexpr field.

    cacheforsecs(int): Filters results that only match the cacheforsecs field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policyhttpcallout

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if port:
        search_filter.append(['port', port])

    if vserver:
        search_filter.append(['vserver', vserver])

    if returntype:
        search_filter.append(['returntype', returntype])

    if httpmethod:
        search_filter.append(['httpmethod', httpmethod])

    if hostexpr:
        search_filter.append(['hostexpr', hostexpr])

    if urlstemexpr:
        search_filter.append(['urlstemexpr', urlstemexpr])

    if headers:
        search_filter.append(['headers', headers])

    if parameters:
        search_filter.append(['parameters', parameters])

    if bodyexpr:
        search_filter.append(['bodyexpr', bodyexpr])

    if fullreqexpr:
        search_filter.append(['fullreqexpr', fullreqexpr])

    if scheme:
        search_filter.append(['scheme', scheme])

    if resultexpr:
        search_filter.append(['resultexpr', resultexpr])

    if cacheforsecs:
        search_filter.append(['cacheforsecs', cacheforsecs])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policyhttpcallout{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policyhttpcallout')

    return response


def get_policymap(mappolicyname=None, sd=None, su=None, td=None, tu=None):
    '''
    Show the running configuration for the policymap config key.

    mappolicyname(str): Filters results that only match the mappolicyname field.

    sd(str): Filters results that only match the sd field.

    su(str): Filters results that only match the su field.

    td(str): Filters results that only match the td field.

    tu(str): Filters results that only match the tu field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policymap

    '''

    search_filter = []

    if mappolicyname:
        search_filter.append(['mappolicyname', mappolicyname])

    if sd:
        search_filter.append(['sd', sd])

    if su:
        search_filter.append(['su', su])

    if td:
        search_filter.append(['td', td])

    if tu:
        search_filter.append(['tu', tu])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policymap{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policymap')

    return response


def get_policyparam():
    '''
    Show the running configuration for the policyparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policyparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policyparam'), 'policyparam')

    return response


def get_policypatset(name=None, indextype=None, comment=None):
    '''
    Show the running configuration for the policypatset config key.

    name(str): Filters results that only match the name field.

    indextype(str): Filters results that only match the indextype field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policypatset

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if indextype:
        search_filter.append(['indextype', indextype])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policypatset{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policypatset')

    return response


def get_policypatset_binding():
    '''
    Show the running configuration for the policypatset_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policypatset_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policypatset_binding'), 'policypatset_binding')

    return response


def get_policypatset_pattern_binding(string=None, builtin=None, name=None, charset=None, index=None):
    '''
    Show the running configuration for the policypatset_pattern_binding config key.

    string(str): Filters results that only match the String field.

    builtin(list(str)): Filters results that only match the builtin field.

    name(str): Filters results that only match the name field.

    charset(str): Filters results that only match the charset field.

    index(int): Filters results that only match the index field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policypatset_pattern_binding

    '''

    search_filter = []

    if string:
        search_filter.append(['String', string])

    if builtin:
        search_filter.append(['builtin', builtin])

    if name:
        search_filter.append(['name', name])

    if charset:
        search_filter.append(['charset', charset])

    if index:
        search_filter.append(['index', index])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policypatset_pattern_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policypatset_pattern_binding')

    return response


def get_policystringmap(name=None, comment=None):
    '''
    Show the running configuration for the policystringmap config key.

    name(str): Filters results that only match the name field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policystringmap

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policystringmap{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policystringmap')

    return response


def get_policystringmap_binding():
    '''
    Show the running configuration for the policystringmap_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policystringmap_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policystringmap_binding'), 'policystringmap_binding')

    return response


def get_policystringmap_pattern_binding(value=None, name=None, key=None):
    '''
    Show the running configuration for the policystringmap_pattern_binding config key.

    value(str): Filters results that only match the value field.

    name(str): Filters results that only match the name field.

    key(str): Filters results that only match the key field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policystringmap_pattern_binding

    '''

    search_filter = []

    if value:
        search_filter.append(['value', value])

    if name:
        search_filter.append(['name', name])

    if key:
        search_filter.append(['key', key])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policystringmap_pattern_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policystringmap_pattern_binding')

    return response


def get_policyurlset(name=None, comment=None, overwrite=None, delimiter=None, rowseparator=None, url=None, interval=None,
                     privateset=None, canaryurl=None):
    '''
    Show the running configuration for the policyurlset config key.

    name(str): Filters results that only match the name field.

    comment(str): Filters results that only match the comment field.

    overwrite(bool): Filters results that only match the overwrite field.

    delimiter(str): Filters results that only match the delimiter field.

    rowseparator(str): Filters results that only match the rowseparator field.

    url(str): Filters results that only match the url field.

    interval(int): Filters results that only match the interval field.

    privateset(bool): Filters results that only match the privateset field.

    canaryurl(str): Filters results that only match the canaryurl field.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.get_policyurlset

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if comment:
        search_filter.append(['comment', comment])

    if overwrite:
        search_filter.append(['overwrite', overwrite])

    if delimiter:
        search_filter.append(['delimiter', delimiter])

    if rowseparator:
        search_filter.append(['rowseparator', rowseparator])

    if url:
        search_filter.append(['url', url])

    if interval:
        search_filter.append(['interval', interval])

    if privateset:
        search_filter.append(['privateset', privateset])

    if canaryurl:
        search_filter.append(['canaryurl', canaryurl])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/policyurlset{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'policyurlset')

    return response


def unset_policyexpression(name=None, value=None, description=None, comment=None, clientsecuritymessage=None,
                           ns_type=None, save=False):
    '''
    Unsets values from the policyexpression configuration key.

    name(bool): Unsets the name value.

    value(bool): Unsets the value value.

    description(bool): Unsets the description value.

    comment(bool): Unsets the comment value.

    clientsecuritymessage(bool): Unsets the clientsecuritymessage value.

    ns_type(bool): Unsets the ns_type value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.unset_policyexpression <args>

    '''

    result = {}

    payload = {'policyexpression': {}}

    if name:
        payload['policyexpression']['name'] = True

    if value:
        payload['policyexpression']['value'] = True

    if description:
        payload['policyexpression']['description'] = True

    if comment:
        payload['policyexpression']['comment'] = True

    if clientsecuritymessage:
        payload['policyexpression']['clientsecuritymessage'] = True

    if ns_type:
        payload['policyexpression']['type'] = True

    execution = __proxy__['citrixns.post']('config/policyexpression?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_policyhttpcallout(name=None, ipaddress=None, port=None, vserver=None, returntype=None, httpmethod=None,
                            hostexpr=None, urlstemexpr=None, headers=None, parameters=None, bodyexpr=None,
                            fullreqexpr=None, scheme=None, resultexpr=None, cacheforsecs=None, comment=None,
                            save=False):
    '''
    Unsets values from the policyhttpcallout configuration key.

    name(bool): Unsets the name value.

    ipaddress(bool): Unsets the ipaddress value.

    port(bool): Unsets the port value.

    vserver(bool): Unsets the vserver value.

    returntype(bool): Unsets the returntype value.

    httpmethod(bool): Unsets the httpmethod value.

    hostexpr(bool): Unsets the hostexpr value.

    urlstemexpr(bool): Unsets the urlstemexpr value.

    headers(bool): Unsets the headers value.

    parameters(bool): Unsets the parameters value.

    bodyexpr(bool): Unsets the bodyexpr value.

    fullreqexpr(bool): Unsets the fullreqexpr value.

    scheme(bool): Unsets the scheme value.

    resultexpr(bool): Unsets the resultexpr value.

    cacheforsecs(bool): Unsets the cacheforsecs value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.unset_policyhttpcallout <args>

    '''

    result = {}

    payload = {'policyhttpcallout': {}}

    if name:
        payload['policyhttpcallout']['name'] = True

    if ipaddress:
        payload['policyhttpcallout']['ipaddress'] = True

    if port:
        payload['policyhttpcallout']['port'] = True

    if vserver:
        payload['policyhttpcallout']['vserver'] = True

    if returntype:
        payload['policyhttpcallout']['returntype'] = True

    if httpmethod:
        payload['policyhttpcallout']['httpmethod'] = True

    if hostexpr:
        payload['policyhttpcallout']['hostexpr'] = True

    if urlstemexpr:
        payload['policyhttpcallout']['urlstemexpr'] = True

    if headers:
        payload['policyhttpcallout']['headers'] = True

    if parameters:
        payload['policyhttpcallout']['parameters'] = True

    if bodyexpr:
        payload['policyhttpcallout']['bodyexpr'] = True

    if fullreqexpr:
        payload['policyhttpcallout']['fullreqexpr'] = True

    if scheme:
        payload['policyhttpcallout']['scheme'] = True

    if resultexpr:
        payload['policyhttpcallout']['resultexpr'] = True

    if cacheforsecs:
        payload['policyhttpcallout']['cacheforsecs'] = True

    if comment:
        payload['policyhttpcallout']['comment'] = True

    execution = __proxy__['citrixns.post']('config/policyhttpcallout?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_policyparam(timeout=None, save=False):
    '''
    Unsets values from the policyparam configuration key.

    timeout(bool): Unsets the timeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.unset_policyparam <args>

    '''

    result = {}

    payload = {'policyparam': {}}

    if timeout:
        payload['policyparam']['timeout'] = True

    execution = __proxy__['citrixns.post']('config/policyparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_policystringmap(name=None, comment=None, save=False):
    '''
    Unsets values from the policystringmap configuration key.

    name(bool): Unsets the name value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.unset_policystringmap <args>

    '''

    result = {}

    payload = {'policystringmap': {}}

    if name:
        payload['policystringmap']['name'] = True

    if comment:
        payload['policystringmap']['comment'] = True

    execution = __proxy__['citrixns.post']('config/policystringmap?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_policyexpression(name=None, value=None, description=None, comment=None, clientsecuritymessage=None,
                            ns_type=None, save=False):
    '''
    Update the running configuration for the policyexpression config key.

    name(str): Unique name for the expression. Not case sensitive. Must begin with an ASCII letter or underscore (_)
        character, and must consist only of ASCII alphanumeric or underscore characters. Must not begin with re or xp or
        be a word reserved for use as a default syntax expression qualifier prefix (such as HTTP) or enumeration value
        (such as ASCII). Must not be the name of an existing named expression, pattern set, dataset, stringmap, or HTTP
        callout. Minimum length = 1

    value(str): Expression string. For example: http.req.body(100).contains("this").

    description(str): Description for the expression.

    comment(str): Any comments associated with the expression. Displayed upon viewing the policy expression.

    clientsecuritymessage(str): Message to display if the expression fails. Allowed for classic end-point check expressions
        only. Minimum length = 1

    ns_type(str): Type of expression. Can be a classic or default syntax (advanced) expression. Possible values = CLASSIC,
        ADVANCED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.update_policyexpression <args>

    '''

    result = {}

    payload = {'policyexpression': {}}

    if name:
        payload['policyexpression']['name'] = name

    if value:
        payload['policyexpression']['value'] = value

    if description:
        payload['policyexpression']['description'] = description

    if comment:
        payload['policyexpression']['comment'] = comment

    if clientsecuritymessage:
        payload['policyexpression']['clientsecuritymessage'] = clientsecuritymessage

    if ns_type:
        payload['policyexpression']['type'] = ns_type

    execution = __proxy__['citrixns.put']('config/policyexpression', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_policyhttpcallout(name=None, ipaddress=None, port=None, vserver=None, returntype=None, httpmethod=None,
                             hostexpr=None, urlstemexpr=None, headers=None, parameters=None, bodyexpr=None,
                             fullreqexpr=None, scheme=None, resultexpr=None, cacheforsecs=None, comment=None,
                             save=False):
    '''
    Update the running configuration for the policyhttpcallout config key.

    name(str): Name for the HTTP callout. Not case sensitive. Must begin with an ASCII letter or underscore (_) character,
        and must consist only of ASCII alphanumeric or underscore characters. Must not begin with re or xp or be a word
        reserved for use as a default syntax expression qualifier prefix (such as HTTP) or enumeration value (such as
        ASCII). Must not be the name of an existing named expression, pattern set, dataset, stringmap, or HTTP callout.
        Minimum length = 1

    ipaddress(str): IP Address of the server (callout agent) to which the callout is sent. Can be an IPv4 or IPv6 address.
        Mutually exclusive with the Virtual Server parameter. Therefore, you cannot set the ;lt;IP Address, Port;gt; and
        the Virtual Server in the same HTTP callout.

    port(int): Server port to which the HTTP callout agent is mapped. Mutually exclusive with the Virtual Server parameter.
        Therefore, you cannot set the ;lt;IP Address, Port;gt; and the Virtual Server in the same HTTP callout. Minimum
        value = 1

    vserver(str): Name of the load balancing, content switching, or cache redirection virtual server (the callout agent) to
        which the HTTP callout is sent. The service type of the virtual server must be HTTP. Mutually exclusive with the
        IP address and port parameters. Therefore, you cannot set the ;lt;IP Address, Port;gt; and the Virtual Server in
        the same HTTP callout. Minimum length = 1

    returntype(str): Type of data that the target callout agent returns in response to the callout.  Available settings
        function as follows: * TEXT - Treat the returned value as a text string.  * NUM - Treat the returned value as a
        number. * BOOL - Treat the returned value as a Boolean value.  Note: You cannot change the return type after it
        is set. Possible values = BOOL, NUM, TEXT

    httpmethod(str): Method used in the HTTP request that this callout sends. Mutually exclusive with the full HTTP request
        expression. Possible values = GET, POST

    hostexpr(str): Default Syntax string expression to configure the Host header. Can contain a literal value (for example,
        10.101.10.11) or a derived value (for example, http.req.header("Host")). The literal value can be an IP address
        or a fully qualified domain name. Mutually exclusive with the full HTTP request expression. Minimum length = 1

    urlstemexpr(str): Default Syntax string expression for generating the URL stem. Can contain a literal string (for
        example, "/mysite/index.html") or an expression that derives the value (for example, http.req.url). Mutually
        exclusive with the full HTTP request expression. Minimum length = 1

    headers(list(str)): One or more headers to insert into the HTTP request. Each header is specified as "name(expr)", where
        expr is a default syntax expression that is evaluated at runtime to provide the value for the named header. You
        can configure a maximum of eight headers for an HTTP callout. Mutually exclusive with the full HTTP request
        expression.

    parameters(list(str)): One or more query parameters to insert into the HTTP request URL (for a GET request) or into the
        request body (for a POST request). Each parameter is specified as "name(expr)", where expr is an default syntax
        expression that is evaluated at run time to provide the value for the named parameter (name=value). The parameter
        values are URL encoded. Mutually exclusive with the full HTTP request expression.

    bodyexpr(str): An advanced string expression for generating the body of the request. The expression can contain a literal
        string or an expression that derives the value (for example, client.ip.src). Mutually exclusive with
        -fullReqExpr. Minimum length = 1

    fullreqexpr(str): Exact HTTP request, in the form of a default syntax expression, which the NetScaler appliance sends to
        the callout agent. If you set this parameter, you must not include HTTP method, host expression, URL stem
        expression, headers, or parameters. The request expression is constrained by the feature for which the callout is
        used. For example, an HTTP.RES expression cannot be used in a request-time policy bank or in a TCP content
        switching policy bank. The NetScaler appliance does not check the validity of this request. You must manually
        validate the request. Minimum length = 1

    scheme(str): Type of scheme for the callout server. Possible values = http, https

    resultexpr(str): Expression that extracts the callout results from the response sent by the HTTP callout agent. Must be a
        response based expression, that is, it must begin with HTTP.RES. The operations in this expression must match the
        return type. For example, if you configure a return type of TEXT, the result expression must be a text based
        expression. If the return type is NUM, the result expression (resultExpr) must return a numeric value, as in the
        following example: http.res.body(10000).length. Minimum length = 1

    cacheforsecs(int): Duration, in seconds, for which the callout response is cached. The cached responses are stored in an
        integrated caching content group named "calloutContentGroup". If no duration is configured, the callout responses
        will not be cached unless normal caching configuration is used to cache them. This parameter takes precedence
        over any normal caching configuration that would otherwise apply to these responses.  Note that the
        calloutContentGroup definition may not be modified or removed nor may it be used with other cache policies.
        Minimum value = 1 Maximum value = 31536000

    comment(str): Any comments to preserve information about this HTTP callout.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.update_policyhttpcallout <args>

    '''

    result = {}

    payload = {'policyhttpcallout': {}}

    if name:
        payload['policyhttpcallout']['name'] = name

    if ipaddress:
        payload['policyhttpcallout']['ipaddress'] = ipaddress

    if port:
        payload['policyhttpcallout']['port'] = port

    if vserver:
        payload['policyhttpcallout']['vserver'] = vserver

    if returntype:
        payload['policyhttpcallout']['returntype'] = returntype

    if httpmethod:
        payload['policyhttpcallout']['httpmethod'] = httpmethod

    if hostexpr:
        payload['policyhttpcallout']['hostexpr'] = hostexpr

    if urlstemexpr:
        payload['policyhttpcallout']['urlstemexpr'] = urlstemexpr

    if headers:
        payload['policyhttpcallout']['headers'] = headers

    if parameters:
        payload['policyhttpcallout']['parameters'] = parameters

    if bodyexpr:
        payload['policyhttpcallout']['bodyexpr'] = bodyexpr

    if fullreqexpr:
        payload['policyhttpcallout']['fullreqexpr'] = fullreqexpr

    if scheme:
        payload['policyhttpcallout']['scheme'] = scheme

    if resultexpr:
        payload['policyhttpcallout']['resultexpr'] = resultexpr

    if cacheforsecs:
        payload['policyhttpcallout']['cacheforsecs'] = cacheforsecs

    if comment:
        payload['policyhttpcallout']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/policyhttpcallout', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_policyparam(timeout=None, save=False):
    '''
    Update the running configuration for the policyparam config key.

    timeout(int): Maximum time in milliseconds to allow for processing expressions without interruption. If the timeout is
        reached then the evaluation causes an UNDEF to be raised and no further processing is performed. Minimum value =
        1 Maximum value = 5000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.update_policyparam <args>

    '''

    result = {}

    payload = {'policyparam': {}}

    if timeout:
        payload['policyparam']['timeout'] = timeout

    execution = __proxy__['citrixns.put']('config/policyparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_policystringmap(name=None, comment=None, save=False):
    '''
    Update the running configuration for the policystringmap config key.

    name(str): Unique name for the string map. Not case sensitive. Must begin with an ASCII letter or underscore (_)
        character, and must consist only of ASCII alphanumeric or underscore characters. Must not begin with re or xp or
        be a word reserved for use as a default syntax expression qualifier prefix (such as HTTP) or enumeration value
        (such as ASCII). Must not be the name of an existing named expression, pattern set, dataset, string map, or HTTP
        callout. Minimum length = 1

    comment(str): Comments associated with the string map.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' policy.update_policystringmap <args>

    '''

    result = {}

    payload = {'policystringmap': {}}

    if name:
        payload['policystringmap']['name'] = name

    if comment:
        payload['policystringmap']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/policystringmap', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
