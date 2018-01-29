# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the rewrite key.

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

__virtualname__ = 'rewrite'


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

    return False, 'The rewrite execution module can only be loaded for citrixns proxy minions.'


def add_rewriteaction(name=None, ns_type=None, target=None, stringbuilderexpr=None, pattern=None, search=None,
                      bypasssafetycheck=None, refinesearch=None, comment=None, newname=None, save=False):
    '''
    Add a new rewriteaction to the running configuration.

    name(str): Name for the user-defined rewrite action. Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Can be changed after the rewrite policy is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my rewrite action" or my rewrite action).

    ns_type(str): Type of user-defined rewrite action. The information that you provide for, and the effect of, each type are
        as follows::  * REPLACE ;lt;target;gt; ;lt;string_builder_expr;gt;. Replaces the string with the string-builder
        expression. * REPLACE_ALL ;lt;target;gt; ;lt;string_builder_expr1;gt; -(pattern|search)
        ;lt;string_builder_expr2;gt;. In the request or response specified by ;lt;target;gt;, replaces all occurrences of
        the string defined by ;lt;string_builder_expr1;gt; with the string defined by ;lt;string_builder_expr2;gt;. You
        can use a PCRE-format pattern or the search facility to find the strings to be replaced. * REPLACE_HTTP_RES
        ;lt;string_builder_expr;gt;. Replaces the complete HTTP response with the string defined by the string-builder
        expression. * REPLACE_SIP_RES ;lt;target;gt; - Replaces the complete SIP response with the string specified by
        ;lt;target;gt;. * INSERT_HTTP_HEADER ;lt;header_string_builder_expr;gt; ;lt;contents_string_builder_expr;gt;.
        Inserts the HTTP header specified by ;lt;header_string_builder_expr;gt; and header contents specified by
        ;lt;contents_string_builder_expr;gt;. * DELETE_HTTP_HEADER ;lt;target;gt;. Deletes the HTTP header specified by
        ;lt;target;gt;. * CORRUPT_HTTP_HEADER ;lt;target;gt;. Replaces the header name of all occurrences of the HTTP
        header specified by ;lt;target;gt; with a corrupted name, so that it will not be recognized by the receiver
        Example: MY_HEADER is changed to MHEY_ADER. * INSERT_BEFORE ;lt;string_builder_expr1;gt;
        ;lt;string_builder_expr1;gt;. Finds the string specified in ;lt;string_builder_expr1;gt; and inserts the string
        in ;lt;string_builder_expr2;gt; before it. * INSERT_BEFORE_ALL ;lt;target;gt; ;lt;string_builder_expr1;gt;
        -(pattern|search) ;lt;string_builder_expr2;gt;. In the request or response specified by ;lt;target;gt;, locates
        all occurrences of the string specified in ;lt;string_builder_expr1;gt; and inserts the string specified in
        ;lt;string_builder_expr2;gt; before each. You can use a PCRE-format pattern or the search facility to find the
        strings. * INSERT_AFTER ;lt;string_builder_expr1;gt; ;lt;string_builder_expr2;gt;. Finds the string specified in
        ;lt;string_builder_expr1;gt;, and inserts the string specified in ;lt;string_builder_expr2;gt; after it. *
        INSERT_AFTER_ALL ;lt;target;gt; ;lt;string_builder_expr1;gt; -(pattern|search) ;lt;string_builder_expr;gt;. In
        the request or response specified by ;lt;target;gt;, locates all occurrences of the string specified by
        ;lt;string_builder_expr1;gt; and inserts the string specified by ;lt;string_builder_expr2;gt; after each. You can
        use a PCRE-format pattern or the search facility to find the strings. * DELETE ;lt;target;gt;. Finds and deletes
        the specified target. * DELETE_ALL ;lt;target;gt; -(pattern|search) ;lt;string_builder_expr;gt;. In the request
        or response specified by ;lt;target;gt;, locates and deletes all occurrences of the string specified by
        ;lt;string_builder_expr;gt;. You can use a PCRE-format pattern or the search facility to find the strings. *
        REPLACE_DIAMETER_HEADER_FIELD ;lt;target;gt; ;lt;field value;gt;. In the request or response modify the header
        field specified by ;lt;target;gt;. Use Diameter.req.flags.SET(;lt;flag;gt;) or
        Diameter.req.flags.UNSET;lt;flag;gt; as stringbuilderexpression to set or unset flags. * REPLACE_DNS_HEADER_FIELD
        ;lt;target;gt;. In the request or response modify the header field specified by ;lt;target;gt;.  *
        REPLACE_DNS_ANSWER_SECTION ;lt;target;gt;. Replace the DNS answer section in the response. This is currently
        applicable for A and AAAA records only. Use DNS.NEW_RRSET_A ;amp; DNS.NEW_RRSET_AAAA expressions to configure the
        new answer section . Possible values = noop, delete, insert_http_header, delete_http_header, corrupt_http_header,
        insert_before, insert_after, replace, replace_http_res, delete_all, replace_all, insert_before_all,
        insert_after_all, clientless_vpn_encode, clientless_vpn_encode_all, clientless_vpn_decode,
        clientless_vpn_decode_all, insert_sip_header, delete_sip_header, corrupt_sip_header, replace_sip_res,
        replace_diameter_header_field, replace_dns_header_field, replace_dns_answer_section

    target(str): Default syntax expression that specifies which part of the request or response to rewrite. Minimum length =
        1

    stringbuilderexpr(str): Default syntax expression that specifies the content to insert into the request or response at
        the specified location, or that replaces the specified string.

    pattern(str): Pattern that is used to match multiple strings in the request or response. The pattern may be a string
        literal (without quotes) or a PCRE-format regular expression with a delimiter that consists of any printable
        ASCII non-alphanumeric character except for the underscore (_) and space ( ) that is not otherwise used in the
        expression. Example: re~https?://|HTTPS?://~ The preceding regular expression can use the tilde (~) as the
        delimiter because that character does not appear in the regular expression itself. Used in the INSERT_BEFORE_ALL,
        INSERT_AFTER_ALL, REPLACE_ALL, and DELETE_ALL action types.

    search(str): Search facility that is used to match multiple strings in the request or response. Used in the
        INSERT_BEFORE_ALL, INSERT_AFTER_ALL, REPLACE_ALL, and DELETE_ALL action types. The following search types are
        supported: * Text ("text(string)") - A literal string. Example: -search text("hello") * Regular expression
        ("regex(re;lt;delimiter;gt;regular exp;lt;delimiter;gt;)") - Pattern that is used to match multiple strings in
        the request or response. The pattern may be a string literal (without quotes) or a PCRE-format regular expression
        with a delimiter that consists of any printable ASCII non-alphanumeric character except for the underscore (_)
        and space ( ) that is not otherwise used in the expression. Example: -search regex(re~^hello~) The preceding
        regular expression can use the tilde (~) as the delimiter because that character does not appear in the regular
        expression itself. * XPath ("xpath(xp;lt;delimiter;gt;xpath expression;lt;delimiter;gt;)") - An XPath expression.
        Example: -search xpath(xp%/a/b%) * JSON ("xpath_json(xp;lt;delimiter;gt;xpath expression;lt;delimiter;gt;)") - An
        XPath JSON expression. Example: -search xpath_json(xp%/a/b%) NOTE: JSON searches use the same syntax as XPath
        searches, but operate on JSON files instead of standard XML files. * Patset ("patset(patset)") - A predefined
        pattern set. Example: -search patset("patset1"). * Datset ("dataset(dataset)") - A predefined dataset. Example:
        -search dataset("dataset1"). * AVP ("avp(avp number)") - AVP number that is used to match multiple AVPs in a
        Diameter/Radius Message. Example: -search avp(999).

    bypasssafetycheck(str): Bypass the safety check and allow unsafe expressions. An unsafe expression is one that contains
        references to message elements that might not be present in all messages. If an expression refers to a missing
        request element, an empty string is used instead. Default value: NO Possible values = YES, NO

    refinesearch(str): Specify additional criteria to refine the results of the search.  Always starts with the "extend(m,n)"
        operation, where m specifies number of bytes to the left of selected data and n specifies number of bytes to the
        right of selected data. You can use refineSearch only on body expressions, and for the INSERT_BEFORE_ALL,
        INSERT_AFTER_ALL, REPLACE_ALL, and DELETE_ALL action types.

    comment(str): Comment. Can be used to preserve information about this rewrite action.

    newname(str): New name for the rewrite action.  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Can be changed after the rewrite policy is added.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my rewrite action" or my rewrite action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.add_rewriteaction <args>

    '''

    result = {}

    payload = {'rewriteaction': {}}

    if name:
        payload['rewriteaction']['name'] = name

    if ns_type:
        payload['rewriteaction']['type'] = ns_type

    if target:
        payload['rewriteaction']['target'] = target

    if stringbuilderexpr:
        payload['rewriteaction']['stringbuilderexpr'] = stringbuilderexpr

    if pattern:
        payload['rewriteaction']['pattern'] = pattern

    if search:
        payload['rewriteaction']['search'] = search

    if bypasssafetycheck:
        payload['rewriteaction']['bypasssafetycheck'] = bypasssafetycheck

    if refinesearch:
        payload['rewriteaction']['refinesearch'] = refinesearch

    if comment:
        payload['rewriteaction']['comment'] = comment

    if newname:
        payload['rewriteaction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/rewriteaction', payload)

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


def add_rewriteglobal_rewritepolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                            gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None,
                                            save=False):
    '''
    Add a new rewriteglobal_rewritepolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the rewrite policy.

    labelname(str): * If labelType is policylabel, name of the policy label to invoke. * If labelType is reqvserver or
        resvserver, name of the virtual server to which to forward the request of response.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Terminate evaluation of policies bound to the current policy label, and then forward the request to the
        specified virtual server or evaluate the specified policy label.

    ns_type(str): The bindpoint to which to policy is bound. Possible values = REQ_OVERRIDE, REQ_DEFAULT, RES_OVERRIDE,
        RES_DEFAULT, OTHERTCP_REQ_OVERRIDE, OTHERTCP_REQ_DEFAULT, OTHERTCP_RES_OVERRIDE, OTHERTCP_RES_DEFAULT,
        SIPUDP_REQ_OVERRIDE, SIPUDP_REQ_DEFAULT, SIPUDP_RES_OVERRIDE, SIPUDP_RES_DEFAULT, SIPTCP_REQ_OVERRIDE,
        SIPTCP_REQ_DEFAULT, SIPTCP_RES_OVERRIDE, SIPTCP_RES_DEFAULT, DIAMETER_REQ_OVERRIDE, DIAMETER_REQ_DEFAULT,
        DIAMETER_RES_OVERRIDE, DIAMETER_RES_DEFAULT, RADIUS_REQ_OVERRIDE, RADIUS_REQ_DEFAULT, RADIUS_RES_OVERRIDE,
        RADIUS_RES_DEFAULT, DNS_REQ_OVERRIDE, DNS_REQ_DEFAULT, DNS_RES_OVERRIDE, DNS_RES_DEFAULT

    labeltype(str): Type of invocation. Available settings function as follows: * reqvserver - Forward the request to the
        specified request virtual server. * resvserver - Forward the response to the specified response virtual server. *
        policylabel - Invoke the specified policy label. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.add_rewriteglobal_rewritepolicy_binding <args>

    '''

    result = {}

    payload = {'rewriteglobal_rewritepolicy_binding': {}}

    if priority:
        payload['rewriteglobal_rewritepolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['rewriteglobal_rewritepolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['rewriteglobal_rewritepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['rewriteglobal_rewritepolicy_binding']['labelname'] = labelname

    if gotopriorityexpression:
        payload['rewriteglobal_rewritepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['rewriteglobal_rewritepolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['rewriteglobal_rewritepolicy_binding']['type'] = ns_type

    if labeltype:
        payload['rewriteglobal_rewritepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/rewriteglobal_rewritepolicy_binding', payload)

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


def add_rewritepolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None, newname=None,
                      save=False):
    '''
    Add a new rewritepolicy to the running configuration.

    name(str): Name for the rewrite policy. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon (:),
        and underscore characters. Can be changed after the rewrite policy is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my rewrite policy" or my rewrite policy).

    rule(str): Expression against which traffic is evaluated. Written in default syntax. Note: Maximum length of a string
        literal in the expression is 255 characters. A longer string can be split into smaller strings of up to 255
        characters each, and the smaller strings concatenated with the + operator. For example, you can create a
        500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" (Classic
        expressions are not supported in the cluster build.)  The following requirements apply only to the NetScaler CLI:
        * If the expression includes one or more spaces, enclose the entire expression in double quotation marks. * If
        the expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Name of the rewrite action to perform if the request or response matches this rewrite policy. There are also
        some built-in actions which can be used. These are: * NOREWRITE - Send the request from the client to the server
        or response from the server to the client without making any changes in the message. * RESET - Resets the client
        connection by closing it. The client program, such as a browser, will handle this and may inform the user. The
        client may then resend the request if desired. * DROP - Drop the request without sending a response to the user.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any comments to preserve information about this rewrite policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the rewrite policy.  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my rewrite
        policy" or my rewrite policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.add_rewritepolicy <args>

    '''

    result = {}

    payload = {'rewritepolicy': {}}

    if name:
        payload['rewritepolicy']['name'] = name

    if rule:
        payload['rewritepolicy']['rule'] = rule

    if action:
        payload['rewritepolicy']['action'] = action

    if undefaction:
        payload['rewritepolicy']['undefaction'] = undefaction

    if comment:
        payload['rewritepolicy']['comment'] = comment

    if logaction:
        payload['rewritepolicy']['logaction'] = logaction

    if newname:
        payload['rewritepolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/rewritepolicy', payload)

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


def add_rewritepolicylabel(labelname=None, transform=None, comment=None, newname=None, save=False):
    '''
    Add a new rewritepolicylabel to the running configuration.

    labelname(str): Name for the rewrite policy label. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the rewrite policy label is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my rewrite policy label" or my rewrite policy label).

    transform(str): Types of transformations allowed by the policies bound to the label. For Rewrite, the following types are
        supported: * http_req - HTTP requests * http_res - HTTP responses * othertcp_req - Non-HTTP TCP requests *
        othertcp_res - Non-HTTP TCP responses * url - URLs * text - Text strings * clientless_vpn_req - NetScaler
        clientless VPN requests * clientless_vpn_res - NetScaler clientless VPN responses * sipudp_req - SIP requests *
        sipudp_res - SIP responses * diameter_req - DIAMETER requests * diameter_res - DIAMETER responses * radius_req -
        RADIUS requests * radius_res - RADIUS responses * dns_req - DNS requests * dns_res - DNS responses. Possible
        values = http_req, http_res, othertcp_req, othertcp_res, url, text, clientless_vpn_req, clientless_vpn_res,
        sipudp_req, sipudp_res, siptcp_req, siptcp_res, diameter_req, diameter_res, radius_req, radius_res, dns_req,
        dns_res

    comment(str): Any comments to preserve information about this rewrite policy label.

    newname(str): New name for the rewrite policy label.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my policy label"
        or my policy label). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.add_rewritepolicylabel <args>

    '''

    result = {}

    payload = {'rewritepolicylabel': {}}

    if labelname:
        payload['rewritepolicylabel']['labelname'] = labelname

    if transform:
        payload['rewritepolicylabel']['transform'] = transform

    if comment:
        payload['rewritepolicylabel']['comment'] = comment

    if newname:
        payload['rewritepolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/rewritepolicylabel', payload)

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


def add_rewritepolicylabel_rewritepolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                                 gotopriorityexpression=None, invoke=None, labeltype=None, save=False):
    '''
    Add a new rewritepolicylabel_rewritepolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): Name of the rewrite policy to bind to the policy label.

    labelname(str): Name of the rewrite policy label to which to bind the policy.

    invoke_labelname(str): * If labelType is policylabel, name of the policy label to invoke. * If labelType is reqvserver or
        resvserver, name of the virtual server to which to forward the request or response.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Suspend evaluation of policies bound to the current policy label, and then forward the request to the
        specified virtual server or evaluate the specified policy label.

    labeltype(str): Type of invocation. Available settings function as follows: * reqvserver - Forward the request to the
        specified request virtual server. * resvserver - Forward the response to the specified response virtual server. *
        policylabel - Invoke the specified policy label. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.add_rewritepolicylabel_rewritepolicy_binding <args>

    '''

    result = {}

    payload = {'rewritepolicylabel_rewritepolicy_binding': {}}

    if priority:
        payload['rewritepolicylabel_rewritepolicy_binding']['priority'] = priority

    if policyname:
        payload['rewritepolicylabel_rewritepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['rewritepolicylabel_rewritepolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['rewritepolicylabel_rewritepolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['rewritepolicylabel_rewritepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['rewritepolicylabel_rewritepolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['rewritepolicylabel_rewritepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/rewritepolicylabel_rewritepolicy_binding', payload)

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


def get_rewriteaction(name=None, ns_type=None, target=None, stringbuilderexpr=None, pattern=None, search=None,
                      bypasssafetycheck=None, refinesearch=None, comment=None, newname=None):
    '''
    Show the running configuration for the rewriteaction config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    target(str): Filters results that only match the target field.

    stringbuilderexpr(str): Filters results that only match the stringbuilderexpr field.

    pattern(str): Filters results that only match the pattern field.

    search(str): Filters results that only match the search field.

    bypasssafetycheck(str): Filters results that only match the bypasssafetycheck field.

    refinesearch(str): Filters results that only match the refinesearch field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewriteaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if target:
        search_filter.append(['target', target])

    if stringbuilderexpr:
        search_filter.append(['stringbuilderexpr', stringbuilderexpr])

    if pattern:
        search_filter.append(['pattern', pattern])

    if search:
        search_filter.append(['search', search])

    if bypasssafetycheck:
        search_filter.append(['bypasssafetycheck', bypasssafetycheck])

    if refinesearch:
        search_filter.append(['refinesearch', refinesearch])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewriteaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewriteaction')

    return response


def get_rewriteglobal_binding():
    '''
    Show the running configuration for the rewriteglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewriteglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewriteglobal_binding'), 'rewriteglobal_binding')

    return response


def get_rewriteglobal_rewritepolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                            gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the rewriteglobal_rewritepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    ns_type(str): Filters results that only match the type field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewriteglobal_rewritepolicy_binding

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

    if invoke:
        search_filter.append(['invoke', invoke])

    if ns_type:
        search_filter.append(['type', ns_type])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewriteglobal_rewritepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewriteglobal_rewritepolicy_binding')

    return response


def get_rewriteparam():
    '''
    Show the running configuration for the rewriteparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewriteparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewriteparam'), 'rewriteparam')

    return response


def get_rewritepolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None, newname=None):
    '''
    Show the running configuration for the rewritepolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicy

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
            __proxy__['citrixns.get']('config/rewritepolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewritepolicy')

    return response


def get_rewritepolicy_binding():
    '''
    Show the running configuration for the rewritepolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewritepolicy_binding'), 'rewritepolicy_binding')

    return response


def get_rewritepolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the rewritepolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewritepolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewritepolicy_csvserver_binding')

    return response


def get_rewritepolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the rewritepolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewritepolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewritepolicy_lbvserver_binding')

    return response


def get_rewritepolicy_rewriteglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the rewritepolicy_rewriteglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicy_rewriteglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewritepolicy_rewriteglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewritepolicy_rewriteglobal_binding')

    return response


def get_rewritepolicy_rewritepolicylabel_binding(boundto=None, name=None):
    '''
    Show the running configuration for the rewritepolicy_rewritepolicylabel_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicy_rewritepolicylabel_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewritepolicy_rewritepolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewritepolicy_rewritepolicylabel_binding')

    return response


def get_rewritepolicylabel(labelname=None, transform=None, comment=None, newname=None):
    '''
    Show the running configuration for the rewritepolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    transform(str): Filters results that only match the transform field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if transform:
        search_filter.append(['transform', transform])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewritepolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewritepolicylabel')

    return response


def get_rewritepolicylabel_binding():
    '''
    Show the running configuration for the rewritepolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rewritepolicylabel_binding'), 'rewritepolicylabel_binding')

    return response


def get_rewritepolicylabel_policybinding_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                                 gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the rewritepolicylabel_policybinding_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicylabel_policybinding_binding

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
            __proxy__['citrixns.get']('config/rewritepolicylabel_policybinding_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewritepolicylabel_policybinding_binding')

    return response


def get_rewritepolicylabel_rewritepolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                                 gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the rewritepolicylabel_rewritepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.get_rewritepolicylabel_rewritepolicy_binding

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
            __proxy__['citrixns.get']('config/rewritepolicylabel_rewritepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rewritepolicylabel_rewritepolicy_binding')

    return response


def unset_rewriteaction(name=None, ns_type=None, target=None, stringbuilderexpr=None, pattern=None, search=None,
                        bypasssafetycheck=None, refinesearch=None, comment=None, newname=None, save=False):
    '''
    Unsets values from the rewriteaction configuration key.

    name(bool): Unsets the name value.

    ns_type(bool): Unsets the ns_type value.

    target(bool): Unsets the target value.

    stringbuilderexpr(bool): Unsets the stringbuilderexpr value.

    pattern(bool): Unsets the pattern value.

    search(bool): Unsets the search value.

    bypasssafetycheck(bool): Unsets the bypasssafetycheck value.

    refinesearch(bool): Unsets the refinesearch value.

    comment(bool): Unsets the comment value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.unset_rewriteaction <args>

    '''

    result = {}

    payload = {'rewriteaction': {}}

    if name:
        payload['rewriteaction']['name'] = True

    if ns_type:
        payload['rewriteaction']['type'] = True

    if target:
        payload['rewriteaction']['target'] = True

    if stringbuilderexpr:
        payload['rewriteaction']['stringbuilderexpr'] = True

    if pattern:
        payload['rewriteaction']['pattern'] = True

    if search:
        payload['rewriteaction']['search'] = True

    if bypasssafetycheck:
        payload['rewriteaction']['bypasssafetycheck'] = True

    if refinesearch:
        payload['rewriteaction']['refinesearch'] = True

    if comment:
        payload['rewriteaction']['comment'] = True

    if newname:
        payload['rewriteaction']['newname'] = True

    execution = __proxy__['citrixns.post']('config/rewriteaction?action=unset', payload)

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


def unset_rewriteparam(undefaction=None, timeout=None, save=False):
    '''
    Unsets values from the rewriteparam configuration key.

    undefaction(bool): Unsets the undefaction value.

    timeout(bool): Unsets the timeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.unset_rewriteparam <args>

    '''

    result = {}

    payload = {'rewriteparam': {}}

    if undefaction:
        payload['rewriteparam']['undefaction'] = True

    if timeout:
        payload['rewriteparam']['timeout'] = True

    execution = __proxy__['citrixns.post']('config/rewriteparam?action=unset', payload)

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


def unset_rewritepolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None, newname=None,
                        save=False):
    '''
    Unsets values from the rewritepolicy configuration key.

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

    salt '*' rewrite.unset_rewritepolicy <args>

    '''

    result = {}

    payload = {'rewritepolicy': {}}

    if name:
        payload['rewritepolicy']['name'] = True

    if rule:
        payload['rewritepolicy']['rule'] = True

    if action:
        payload['rewritepolicy']['action'] = True

    if undefaction:
        payload['rewritepolicy']['undefaction'] = True

    if comment:
        payload['rewritepolicy']['comment'] = True

    if logaction:
        payload['rewritepolicy']['logaction'] = True

    if newname:
        payload['rewritepolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/rewritepolicy?action=unset', payload)

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


def update_rewriteaction(name=None, ns_type=None, target=None, stringbuilderexpr=None, pattern=None, search=None,
                         bypasssafetycheck=None, refinesearch=None, comment=None, newname=None, save=False):
    '''
    Update the running configuration for the rewriteaction config key.

    name(str): Name for the user-defined rewrite action. Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Can be changed after the rewrite policy is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my rewrite action" or my rewrite action).

    ns_type(str): Type of user-defined rewrite action. The information that you provide for, and the effect of, each type are
        as follows::  * REPLACE ;lt;target;gt; ;lt;string_builder_expr;gt;. Replaces the string with the string-builder
        expression. * REPLACE_ALL ;lt;target;gt; ;lt;string_builder_expr1;gt; -(pattern|search)
        ;lt;string_builder_expr2;gt;. In the request or response specified by ;lt;target;gt;, replaces all occurrences of
        the string defined by ;lt;string_builder_expr1;gt; with the string defined by ;lt;string_builder_expr2;gt;. You
        can use a PCRE-format pattern or the search facility to find the strings to be replaced. * REPLACE_HTTP_RES
        ;lt;string_builder_expr;gt;. Replaces the complete HTTP response with the string defined by the string-builder
        expression. * REPLACE_SIP_RES ;lt;target;gt; - Replaces the complete SIP response with the string specified by
        ;lt;target;gt;. * INSERT_HTTP_HEADER ;lt;header_string_builder_expr;gt; ;lt;contents_string_builder_expr;gt;.
        Inserts the HTTP header specified by ;lt;header_string_builder_expr;gt; and header contents specified by
        ;lt;contents_string_builder_expr;gt;. * DELETE_HTTP_HEADER ;lt;target;gt;. Deletes the HTTP header specified by
        ;lt;target;gt;. * CORRUPT_HTTP_HEADER ;lt;target;gt;. Replaces the header name of all occurrences of the HTTP
        header specified by ;lt;target;gt; with a corrupted name, so that it will not be recognized by the receiver
        Example: MY_HEADER is changed to MHEY_ADER. * INSERT_BEFORE ;lt;string_builder_expr1;gt;
        ;lt;string_builder_expr1;gt;. Finds the string specified in ;lt;string_builder_expr1;gt; and inserts the string
        in ;lt;string_builder_expr2;gt; before it. * INSERT_BEFORE_ALL ;lt;target;gt; ;lt;string_builder_expr1;gt;
        -(pattern|search) ;lt;string_builder_expr2;gt;. In the request or response specified by ;lt;target;gt;, locates
        all occurrences of the string specified in ;lt;string_builder_expr1;gt; and inserts the string specified in
        ;lt;string_builder_expr2;gt; before each. You can use a PCRE-format pattern or the search facility to find the
        strings. * INSERT_AFTER ;lt;string_builder_expr1;gt; ;lt;string_builder_expr2;gt;. Finds the string specified in
        ;lt;string_builder_expr1;gt;, and inserts the string specified in ;lt;string_builder_expr2;gt; after it. *
        INSERT_AFTER_ALL ;lt;target;gt; ;lt;string_builder_expr1;gt; -(pattern|search) ;lt;string_builder_expr;gt;. In
        the request or response specified by ;lt;target;gt;, locates all occurrences of the string specified by
        ;lt;string_builder_expr1;gt; and inserts the string specified by ;lt;string_builder_expr2;gt; after each. You can
        use a PCRE-format pattern or the search facility to find the strings. * DELETE ;lt;target;gt;. Finds and deletes
        the specified target. * DELETE_ALL ;lt;target;gt; -(pattern|search) ;lt;string_builder_expr;gt;. In the request
        or response specified by ;lt;target;gt;, locates and deletes all occurrences of the string specified by
        ;lt;string_builder_expr;gt;. You can use a PCRE-format pattern or the search facility to find the strings. *
        REPLACE_DIAMETER_HEADER_FIELD ;lt;target;gt; ;lt;field value;gt;. In the request or response modify the header
        field specified by ;lt;target;gt;. Use Diameter.req.flags.SET(;lt;flag;gt;) or
        Diameter.req.flags.UNSET;lt;flag;gt; as stringbuilderexpression to set or unset flags. * REPLACE_DNS_HEADER_FIELD
        ;lt;target;gt;. In the request or response modify the header field specified by ;lt;target;gt;.  *
        REPLACE_DNS_ANSWER_SECTION ;lt;target;gt;. Replace the DNS answer section in the response. This is currently
        applicable for A and AAAA records only. Use DNS.NEW_RRSET_A ;amp; DNS.NEW_RRSET_AAAA expressions to configure the
        new answer section . Possible values = noop, delete, insert_http_header, delete_http_header, corrupt_http_header,
        insert_before, insert_after, replace, replace_http_res, delete_all, replace_all, insert_before_all,
        insert_after_all, clientless_vpn_encode, clientless_vpn_encode_all, clientless_vpn_decode,
        clientless_vpn_decode_all, insert_sip_header, delete_sip_header, corrupt_sip_header, replace_sip_res,
        replace_diameter_header_field, replace_dns_header_field, replace_dns_answer_section

    target(str): Default syntax expression that specifies which part of the request or response to rewrite. Minimum length =
        1

    stringbuilderexpr(str): Default syntax expression that specifies the content to insert into the request or response at
        the specified location, or that replaces the specified string.

    pattern(str): Pattern that is used to match multiple strings in the request or response. The pattern may be a string
        literal (without quotes) or a PCRE-format regular expression with a delimiter that consists of any printable
        ASCII non-alphanumeric character except for the underscore (_) and space ( ) that is not otherwise used in the
        expression. Example: re~https?://|HTTPS?://~ The preceding regular expression can use the tilde (~) as the
        delimiter because that character does not appear in the regular expression itself. Used in the INSERT_BEFORE_ALL,
        INSERT_AFTER_ALL, REPLACE_ALL, and DELETE_ALL action types.

    search(str): Search facility that is used to match multiple strings in the request or response. Used in the
        INSERT_BEFORE_ALL, INSERT_AFTER_ALL, REPLACE_ALL, and DELETE_ALL action types. The following search types are
        supported: * Text ("text(string)") - A literal string. Example: -search text("hello") * Regular expression
        ("regex(re;lt;delimiter;gt;regular exp;lt;delimiter;gt;)") - Pattern that is used to match multiple strings in
        the request or response. The pattern may be a string literal (without quotes) or a PCRE-format regular expression
        with a delimiter that consists of any printable ASCII non-alphanumeric character except for the underscore (_)
        and space ( ) that is not otherwise used in the expression. Example: -search regex(re~^hello~) The preceding
        regular expression can use the tilde (~) as the delimiter because that character does not appear in the regular
        expression itself. * XPath ("xpath(xp;lt;delimiter;gt;xpath expression;lt;delimiter;gt;)") - An XPath expression.
        Example: -search xpath(xp%/a/b%) * JSON ("xpath_json(xp;lt;delimiter;gt;xpath expression;lt;delimiter;gt;)") - An
        XPath JSON expression. Example: -search xpath_json(xp%/a/b%) NOTE: JSON searches use the same syntax as XPath
        searches, but operate on JSON files instead of standard XML files. * Patset ("patset(patset)") - A predefined
        pattern set. Example: -search patset("patset1"). * Datset ("dataset(dataset)") - A predefined dataset. Example:
        -search dataset("dataset1"). * AVP ("avp(avp number)") - AVP number that is used to match multiple AVPs in a
        Diameter/Radius Message. Example: -search avp(999).

    bypasssafetycheck(str): Bypass the safety check and allow unsafe expressions. An unsafe expression is one that contains
        references to message elements that might not be present in all messages. If an expression refers to a missing
        request element, an empty string is used instead. Default value: NO Possible values = YES, NO

    refinesearch(str): Specify additional criteria to refine the results of the search.  Always starts with the "extend(m,n)"
        operation, where m specifies number of bytes to the left of selected data and n specifies number of bytes to the
        right of selected data. You can use refineSearch only on body expressions, and for the INSERT_BEFORE_ALL,
        INSERT_AFTER_ALL, REPLACE_ALL, and DELETE_ALL action types.

    comment(str): Comment. Can be used to preserve information about this rewrite action.

    newname(str): New name for the rewrite action.  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Can be changed after the rewrite policy is added.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my rewrite action" or my rewrite action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.update_rewriteaction <args>

    '''

    result = {}

    payload = {'rewriteaction': {}}

    if name:
        payload['rewriteaction']['name'] = name

    if ns_type:
        payload['rewriteaction']['type'] = ns_type

    if target:
        payload['rewriteaction']['target'] = target

    if stringbuilderexpr:
        payload['rewriteaction']['stringbuilderexpr'] = stringbuilderexpr

    if pattern:
        payload['rewriteaction']['pattern'] = pattern

    if search:
        payload['rewriteaction']['search'] = search

    if bypasssafetycheck:
        payload['rewriteaction']['bypasssafetycheck'] = bypasssafetycheck

    if refinesearch:
        payload['rewriteaction']['refinesearch'] = refinesearch

    if comment:
        payload['rewriteaction']['comment'] = comment

    if newname:
        payload['rewriteaction']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/rewriteaction', payload)

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


def update_rewriteparam(undefaction=None, timeout=None, save=False):
    '''
    Update the running configuration for the rewriteparam config key.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        error condition in evaluating the expression. Available settings function as follows: * NOREWRITE - Do not modify
        the message. * RESET - Reset the connection and notify the users browser, so that the user can resend the
        request. * DROP - Drop the message without sending a response to the user. Default value: "NOREWRITE"

    timeout(int): Maximum time in milliseconds to allow for processing all the policies and their selected actions without
        interruption. If the timeout is reached then the evaluation causes an UNDEF to be raised and no further
        processing is performed. Note that some rewrites may have already been performed. Minimum value = 1 Maximum value
        = 5000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.update_rewriteparam <args>

    '''

    result = {}

    payload = {'rewriteparam': {}}

    if undefaction:
        payload['rewriteparam']['undefaction'] = undefaction

    if timeout:
        payload['rewriteparam']['timeout'] = timeout

    execution = __proxy__['citrixns.put']('config/rewriteparam', payload)

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


def update_rewritepolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None, newname=None,
                         save=False):
    '''
    Update the running configuration for the rewritepolicy config key.

    name(str): Name for the rewrite policy. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon (:),
        and underscore characters. Can be changed after the rewrite policy is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my rewrite policy" or my rewrite policy).

    rule(str): Expression against which traffic is evaluated. Written in default syntax. Note: Maximum length of a string
        literal in the expression is 255 characters. A longer string can be split into smaller strings of up to 255
        characters each, and the smaller strings concatenated with the + operator. For example, you can create a
        500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" (Classic
        expressions are not supported in the cluster build.)  The following requirements apply only to the NetScaler CLI:
        * If the expression includes one or more spaces, enclose the entire expression in double quotation marks. * If
        the expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Name of the rewrite action to perform if the request or response matches this rewrite policy. There are also
        some built-in actions which can be used. These are: * NOREWRITE - Send the request from the client to the server
        or response from the server to the client without making any changes in the message. * RESET - Resets the client
        connection by closing it. The client program, such as a browser, will handle this and may inform the user. The
        client may then resend the request if desired. * DROP - Drop the request without sending a response to the user.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any comments to preserve information about this rewrite policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the rewrite policy.  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my rewrite
        policy" or my rewrite policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rewrite.update_rewritepolicy <args>

    '''

    result = {}

    payload = {'rewritepolicy': {}}

    if name:
        payload['rewritepolicy']['name'] = name

    if rule:
        payload['rewritepolicy']['rule'] = rule

    if action:
        payload['rewritepolicy']['action'] = action

    if undefaction:
        payload['rewritepolicy']['undefaction'] = undefaction

    if comment:
        payload['rewritepolicy']['comment'] = comment

    if logaction:
        payload['rewritepolicy']['logaction'] = logaction

    if newname:
        payload['rewritepolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/rewritepolicy', payload)

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
