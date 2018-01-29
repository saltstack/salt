# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the front-end-optimization key.

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

__virtualname__ = 'front_end_optimization'


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

    return False, 'The front_end_optimization execution module can only be loaded for citrixns proxy minions.'


def add_feoaction(name=None, pageextendcache=None, cachemaxage=None, imgshrinktoattrib=None, imggiftopng=None,
                  imgtowebp=None, imgtojpegxr=None, imginline=None, cssimginline=None, jpgoptimize=None,
                  imglazyload=None, cssminify=None, cssinline=None, csscombine=None, convertimporttolink=None,
                  jsminify=None, jsinline=None, htmlminify=None, cssmovetohead=None, jsmovetoend=None,
                  domainsharding=None, dnsshards=None, clientsidemeasurements=None, save=False):
    '''
    Add a new feoaction to the running configuration.

    name(str): The name of the front end optimization action. Minimum length = 1

    pageextendcache(bool): Extend the time period during which the browser can use the cached resource.

    cachemaxage(int): Maxage for cache extension. Default value: 30 Minimum value = 0 Maximum value = 360

    imgshrinktoattrib(bool): Shrink image dimensions as per the height and width attributes specified in the ;lt;img;gt;
        tag.

    imggiftopng(bool): Convert GIF image formats to PNG formats.

    imgtowebp(bool): Convert JPEG, GIF, PNG image formats to WEBP format.

    imgtojpegxr(bool): Convert JPEG, GIF, PNG image formats to JXR format.

    imginline(bool): Inline images whose size is less than 2KB.

    cssimginline(bool): Inline small images (less than 2KB) referred within CSS files as background-URLs.

    jpgoptimize(bool): Remove non-image data such as comments from JPEG images.

    imglazyload(bool): Download images, only when the user scrolls the page to view them.

    cssminify(bool): Remove comments and whitespaces from CSSs.

    cssinline(bool): Inline CSS files, whose size is less than 2KB, within the main page.

    csscombine(bool): Combine one or more CSS files into one file.

    convertimporttolink(bool): Convert CSS import statements to HTML link tags.

    jsminify(bool): Remove comments and whitespaces from JavaScript.

    jsinline(bool): Convert linked JavaScript files (less than 2KB) to inline JavaScript files.

    htmlminify(bool): Remove comments and whitespaces from an HTML page.

    cssmovetohead(bool): Move any CSS file present within the body tag of an HTML page to the head tag.

    jsmovetoend(bool): Move any JavaScript present in the body tag to the end of the body tag.

    domainsharding(str): Domain name of the server.

    dnsshards(list(str)): Set of domain names that replaces the parent domain.

    clientsidemeasurements(bool): Send AppFlow records about the web pages optimized by this action. The records provide FEO
        statistics, such as the number of HTTP requests that have been reduced for this page. You must enable the Appflow
        feature before enabling this parameter.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.add_feoaction <args>

    '''

    result = {}

    payload = {'feoaction': {}}

    if name:
        payload['feoaction']['name'] = name

    if pageextendcache:
        payload['feoaction']['pageextendcache'] = pageextendcache

    if cachemaxage:
        payload['feoaction']['cachemaxage'] = cachemaxage

    if imgshrinktoattrib:
        payload['feoaction']['imgshrinktoattrib'] = imgshrinktoattrib

    if imggiftopng:
        payload['feoaction']['imggiftopng'] = imggiftopng

    if imgtowebp:
        payload['feoaction']['imgtowebp'] = imgtowebp

    if imgtojpegxr:
        payload['feoaction']['imgtojpegxr'] = imgtojpegxr

    if imginline:
        payload['feoaction']['imginline'] = imginline

    if cssimginline:
        payload['feoaction']['cssimginline'] = cssimginline

    if jpgoptimize:
        payload['feoaction']['jpgoptimize'] = jpgoptimize

    if imglazyload:
        payload['feoaction']['imglazyload'] = imglazyload

    if cssminify:
        payload['feoaction']['cssminify'] = cssminify

    if cssinline:
        payload['feoaction']['cssinline'] = cssinline

    if csscombine:
        payload['feoaction']['csscombine'] = csscombine

    if convertimporttolink:
        payload['feoaction']['convertimporttolink'] = convertimporttolink

    if jsminify:
        payload['feoaction']['jsminify'] = jsminify

    if jsinline:
        payload['feoaction']['jsinline'] = jsinline

    if htmlminify:
        payload['feoaction']['htmlminify'] = htmlminify

    if cssmovetohead:
        payload['feoaction']['cssmovetohead'] = cssmovetohead

    if jsmovetoend:
        payload['feoaction']['jsmovetoend'] = jsmovetoend

    if domainsharding:
        payload['feoaction']['domainsharding'] = domainsharding

    if dnsshards:
        payload['feoaction']['dnsshards'] = dnsshards

    if clientsidemeasurements:
        payload['feoaction']['clientsidemeasurements'] = clientsidemeasurements

    execution = __proxy__['citrixns.post']('config/feoaction', payload)

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


def add_feoglobal_feopolicy_binding(priority=None, globalbindtype=None, policyname=None, gotopriorityexpression=None,
                                    ns_type=None, save=False):
    '''
    Add a new feoglobal_feopolicy_binding to the running configuration.

    priority(int): The priority assigned to the policy binding.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): The name of the globally bound front end optimization policy.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    ns_type(str): Bindpoint to which the policy is bound. Possible values = REQ_OVERRIDE, REQ_DEFAULT, RES_OVERRIDE,
        RES_DEFAULT, NONE

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.add_feoglobal_feopolicy_binding <args>

    '''

    result = {}

    payload = {'feoglobal_feopolicy_binding': {}}

    if priority:
        payload['feoglobal_feopolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['feoglobal_feopolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['feoglobal_feopolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['feoglobal_feopolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if ns_type:
        payload['feoglobal_feopolicy_binding']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/feoglobal_feopolicy_binding', payload)

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


def add_feopolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new feopolicy to the running configuration.

    name(str): The name of the front end optimization policy. Minimum length = 1

    rule(str): The rule associated with the front end optimization policy.

    action(str): The front end optimization action that has to be performed when the rule matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.add_feopolicy <args>

    '''

    result = {}

    payload = {'feopolicy': {}}

    if name:
        payload['feopolicy']['name'] = name

    if rule:
        payload['feopolicy']['rule'] = rule

    if action:
        payload['feopolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/feopolicy', payload)

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


def get_feoaction(name=None, pageextendcache=None, cachemaxage=None, imgshrinktoattrib=None, imggiftopng=None,
                  imgtowebp=None, imgtojpegxr=None, imginline=None, cssimginline=None, jpgoptimize=None,
                  imglazyload=None, cssminify=None, cssinline=None, csscombine=None, convertimporttolink=None,
                  jsminify=None, jsinline=None, htmlminify=None, cssmovetohead=None, jsmovetoend=None,
                  domainsharding=None, dnsshards=None, clientsidemeasurements=None):
    '''
    Show the running configuration for the feoaction config key.

    name(str): Filters results that only match the name field.

    pageextendcache(bool): Filters results that only match the pageextendcache field.

    cachemaxage(int): Filters results that only match the cachemaxage field.

    imgshrinktoattrib(bool): Filters results that only match the imgshrinktoattrib field.

    imggiftopng(bool): Filters results that only match the imggiftopng field.

    imgtowebp(bool): Filters results that only match the imgtowebp field.

    imgtojpegxr(bool): Filters results that only match the imgtojpegxr field.

    imginline(bool): Filters results that only match the imginline field.

    cssimginline(bool): Filters results that only match the cssimginline field.

    jpgoptimize(bool): Filters results that only match the jpgoptimize field.

    imglazyload(bool): Filters results that only match the imglazyload field.

    cssminify(bool): Filters results that only match the cssminify field.

    cssinline(bool): Filters results that only match the cssinline field.

    csscombine(bool): Filters results that only match the csscombine field.

    convertimporttolink(bool): Filters results that only match the convertimporttolink field.

    jsminify(bool): Filters results that only match the jsminify field.

    jsinline(bool): Filters results that only match the jsinline field.

    htmlminify(bool): Filters results that only match the htmlminify field.

    cssmovetohead(bool): Filters results that only match the cssmovetohead field.

    jsmovetoend(bool): Filters results that only match the jsmovetoend field.

    domainsharding(str): Filters results that only match the domainsharding field.

    dnsshards(list(str)): Filters results that only match the dnsshards field.

    clientsidemeasurements(bool): Filters results that only match the clientsidemeasurements field.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feoaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if pageextendcache:
        search_filter.append(['pageextendcache', pageextendcache])

    if cachemaxage:
        search_filter.append(['cachemaxage', cachemaxage])

    if imgshrinktoattrib:
        search_filter.append(['imgshrinktoattrib', imgshrinktoattrib])

    if imggiftopng:
        search_filter.append(['imggiftopng', imggiftopng])

    if imgtowebp:
        search_filter.append(['imgtowebp', imgtowebp])

    if imgtojpegxr:
        search_filter.append(['imgtojpegxr', imgtojpegxr])

    if imginline:
        search_filter.append(['imginline', imginline])

    if cssimginline:
        search_filter.append(['cssimginline', cssimginline])

    if jpgoptimize:
        search_filter.append(['jpgoptimize', jpgoptimize])

    if imglazyload:
        search_filter.append(['imglazyload', imglazyload])

    if cssminify:
        search_filter.append(['cssminify', cssminify])

    if cssinline:
        search_filter.append(['cssinline', cssinline])

    if csscombine:
        search_filter.append(['csscombine', csscombine])

    if convertimporttolink:
        search_filter.append(['convertimporttolink', convertimporttolink])

    if jsminify:
        search_filter.append(['jsminify', jsminify])

    if jsinline:
        search_filter.append(['jsinline', jsinline])

    if htmlminify:
        search_filter.append(['htmlminify', htmlminify])

    if cssmovetohead:
        search_filter.append(['cssmovetohead', cssmovetohead])

    if jsmovetoend:
        search_filter.append(['jsmovetoend', jsmovetoend])

    if domainsharding:
        search_filter.append(['domainsharding', domainsharding])

    if dnsshards:
        search_filter.append(['dnsshards', dnsshards])

    if clientsidemeasurements:
        search_filter.append(['clientsidemeasurements', clientsidemeasurements])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/feoaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'feoaction')

    return response


def get_feoglobal_binding():
    '''
    Show the running configuration for the feoglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feoglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/feoglobal_binding'), 'feoglobal_binding')

    return response


def get_feoglobal_feopolicy_binding(priority=None, globalbindtype=None, policyname=None, gotopriorityexpression=None,
                                    ns_type=None):
    '''
    Show the running configuration for the feoglobal_feopolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feoglobal_feopolicy_binding

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
            __proxy__['citrixns.get']('config/feoglobal_feopolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'feoglobal_feopolicy_binding')

    return response


def get_feoparameter():
    '''
    Show the running configuration for the feoparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feoparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/feoparameter'), 'feoparameter')

    return response


def get_feopolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the feopolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feopolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/feopolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'feopolicy')

    return response


def get_feopolicy_binding():
    '''
    Show the running configuration for the feopolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feopolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/feopolicy_binding'), 'feopolicy_binding')

    return response


def get_feopolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the feopolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feopolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/feopolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'feopolicy_csvserver_binding')

    return response


def get_feopolicy_feoglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the feopolicy_feoglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feopolicy_feoglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/feopolicy_feoglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'feopolicy_feoglobal_binding')

    return response


def get_feopolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the feopolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.get_feopolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/feopolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'feopolicy_lbvserver_binding')

    return response


def unset_feoaction(name=None, pageextendcache=None, cachemaxage=None, imgshrinktoattrib=None, imggiftopng=None,
                    imgtowebp=None, imgtojpegxr=None, imginline=None, cssimginline=None, jpgoptimize=None,
                    imglazyload=None, cssminify=None, cssinline=None, csscombine=None, convertimporttolink=None,
                    jsminify=None, jsinline=None, htmlminify=None, cssmovetohead=None, jsmovetoend=None,
                    domainsharding=None, dnsshards=None, clientsidemeasurements=None, save=False):
    '''
    Unsets values from the feoaction configuration key.

    name(bool): Unsets the name value.

    pageextendcache(bool): Unsets the pageextendcache value.

    cachemaxage(bool): Unsets the cachemaxage value.

    imgshrinktoattrib(bool): Unsets the imgshrinktoattrib value.

    imggiftopng(bool): Unsets the imggiftopng value.

    imgtowebp(bool): Unsets the imgtowebp value.

    imgtojpegxr(bool): Unsets the imgtojpegxr value.

    imginline(bool): Unsets the imginline value.

    cssimginline(bool): Unsets the cssimginline value.

    jpgoptimize(bool): Unsets the jpgoptimize value.

    imglazyload(bool): Unsets the imglazyload value.

    cssminify(bool): Unsets the cssminify value.

    cssinline(bool): Unsets the cssinline value.

    csscombine(bool): Unsets the csscombine value.

    convertimporttolink(bool): Unsets the convertimporttolink value.

    jsminify(bool): Unsets the jsminify value.

    jsinline(bool): Unsets the jsinline value.

    htmlminify(bool): Unsets the htmlminify value.

    cssmovetohead(bool): Unsets the cssmovetohead value.

    jsmovetoend(bool): Unsets the jsmovetoend value.

    domainsharding(bool): Unsets the domainsharding value.

    dnsshards(bool): Unsets the dnsshards value.

    clientsidemeasurements(bool): Unsets the clientsidemeasurements value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.unset_feoaction <args>

    '''

    result = {}

    payload = {'feoaction': {}}

    if name:
        payload['feoaction']['name'] = True

    if pageextendcache:
        payload['feoaction']['pageextendcache'] = True

    if cachemaxage:
        payload['feoaction']['cachemaxage'] = True

    if imgshrinktoattrib:
        payload['feoaction']['imgshrinktoattrib'] = True

    if imggiftopng:
        payload['feoaction']['imggiftopng'] = True

    if imgtowebp:
        payload['feoaction']['imgtowebp'] = True

    if imgtojpegxr:
        payload['feoaction']['imgtojpegxr'] = True

    if imginline:
        payload['feoaction']['imginline'] = True

    if cssimginline:
        payload['feoaction']['cssimginline'] = True

    if jpgoptimize:
        payload['feoaction']['jpgoptimize'] = True

    if imglazyload:
        payload['feoaction']['imglazyload'] = True

    if cssminify:
        payload['feoaction']['cssminify'] = True

    if cssinline:
        payload['feoaction']['cssinline'] = True

    if csscombine:
        payload['feoaction']['csscombine'] = True

    if convertimporttolink:
        payload['feoaction']['convertimporttolink'] = True

    if jsminify:
        payload['feoaction']['jsminify'] = True

    if jsinline:
        payload['feoaction']['jsinline'] = True

    if htmlminify:
        payload['feoaction']['htmlminify'] = True

    if cssmovetohead:
        payload['feoaction']['cssmovetohead'] = True

    if jsmovetoend:
        payload['feoaction']['jsmovetoend'] = True

    if domainsharding:
        payload['feoaction']['domainsharding'] = True

    if dnsshards:
        payload['feoaction']['dnsshards'] = True

    if clientsidemeasurements:
        payload['feoaction']['clientsidemeasurements'] = True

    execution = __proxy__['citrixns.post']('config/feoaction?action=unset', payload)

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


def unset_feoparameter(jpegqualitypercent=None, cssinlinethressize=None, jsinlinethressize=None, imginlinethressize=None,
                       save=False):
    '''
    Unsets values from the feoparameter configuration key.

    jpegqualitypercent(bool): Unsets the jpegqualitypercent value.

    cssinlinethressize(bool): Unsets the cssinlinethressize value.

    jsinlinethressize(bool): Unsets the jsinlinethressize value.

    imginlinethressize(bool): Unsets the imginlinethressize value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.unset_feoparameter <args>

    '''

    result = {}

    payload = {'feoparameter': {}}

    if jpegqualitypercent:
        payload['feoparameter']['jpegqualitypercent'] = True

    if cssinlinethressize:
        payload['feoparameter']['cssinlinethressize'] = True

    if jsinlinethressize:
        payload['feoparameter']['jsinlinethressize'] = True

    if imginlinethressize:
        payload['feoparameter']['imginlinethressize'] = True

    execution = __proxy__['citrixns.post']('config/feoparameter?action=unset', payload)

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


def unset_feopolicy(name=None, rule=None, action=None, save=False):
    '''
    Unsets values from the feopolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.unset_feopolicy <args>

    '''

    result = {}

    payload = {'feopolicy': {}}

    if name:
        payload['feopolicy']['name'] = True

    if rule:
        payload['feopolicy']['rule'] = True

    if action:
        payload['feopolicy']['action'] = True

    execution = __proxy__['citrixns.post']('config/feopolicy?action=unset', payload)

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


def update_feoaction(name=None, pageextendcache=None, cachemaxage=None, imgshrinktoattrib=None, imggiftopng=None,
                     imgtowebp=None, imgtojpegxr=None, imginline=None, cssimginline=None, jpgoptimize=None,
                     imglazyload=None, cssminify=None, cssinline=None, csscombine=None, convertimporttolink=None,
                     jsminify=None, jsinline=None, htmlminify=None, cssmovetohead=None, jsmovetoend=None,
                     domainsharding=None, dnsshards=None, clientsidemeasurements=None, save=False):
    '''
    Update the running configuration for the feoaction config key.

    name(str): The name of the front end optimization action. Minimum length = 1

    pageextendcache(bool): Extend the time period during which the browser can use the cached resource.

    cachemaxage(int): Maxage for cache extension. Default value: 30 Minimum value = 0 Maximum value = 360

    imgshrinktoattrib(bool): Shrink image dimensions as per the height and width attributes specified in the ;lt;img;gt;
        tag.

    imggiftopng(bool): Convert GIF image formats to PNG formats.

    imgtowebp(bool): Convert JPEG, GIF, PNG image formats to WEBP format.

    imgtojpegxr(bool): Convert JPEG, GIF, PNG image formats to JXR format.

    imginline(bool): Inline images whose size is less than 2KB.

    cssimginline(bool): Inline small images (less than 2KB) referred within CSS files as background-URLs.

    jpgoptimize(bool): Remove non-image data such as comments from JPEG images.

    imglazyload(bool): Download images, only when the user scrolls the page to view them.

    cssminify(bool): Remove comments and whitespaces from CSSs.

    cssinline(bool): Inline CSS files, whose size is less than 2KB, within the main page.

    csscombine(bool): Combine one or more CSS files into one file.

    convertimporttolink(bool): Convert CSS import statements to HTML link tags.

    jsminify(bool): Remove comments and whitespaces from JavaScript.

    jsinline(bool): Convert linked JavaScript files (less than 2KB) to inline JavaScript files.

    htmlminify(bool): Remove comments and whitespaces from an HTML page.

    cssmovetohead(bool): Move any CSS file present within the body tag of an HTML page to the head tag.

    jsmovetoend(bool): Move any JavaScript present in the body tag to the end of the body tag.

    domainsharding(str): Domain name of the server.

    dnsshards(list(str)): Set of domain names that replaces the parent domain.

    clientsidemeasurements(bool): Send AppFlow records about the web pages optimized by this action. The records provide FEO
        statistics, such as the number of HTTP requests that have been reduced for this page. You must enable the Appflow
        feature before enabling this parameter.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.update_feoaction <args>

    '''

    result = {}

    payload = {'feoaction': {}}

    if name:
        payload['feoaction']['name'] = name

    if pageextendcache:
        payload['feoaction']['pageextendcache'] = pageextendcache

    if cachemaxage:
        payload['feoaction']['cachemaxage'] = cachemaxage

    if imgshrinktoattrib:
        payload['feoaction']['imgshrinktoattrib'] = imgshrinktoattrib

    if imggiftopng:
        payload['feoaction']['imggiftopng'] = imggiftopng

    if imgtowebp:
        payload['feoaction']['imgtowebp'] = imgtowebp

    if imgtojpegxr:
        payload['feoaction']['imgtojpegxr'] = imgtojpegxr

    if imginline:
        payload['feoaction']['imginline'] = imginline

    if cssimginline:
        payload['feoaction']['cssimginline'] = cssimginline

    if jpgoptimize:
        payload['feoaction']['jpgoptimize'] = jpgoptimize

    if imglazyload:
        payload['feoaction']['imglazyload'] = imglazyload

    if cssminify:
        payload['feoaction']['cssminify'] = cssminify

    if cssinline:
        payload['feoaction']['cssinline'] = cssinline

    if csscombine:
        payload['feoaction']['csscombine'] = csscombine

    if convertimporttolink:
        payload['feoaction']['convertimporttolink'] = convertimporttolink

    if jsminify:
        payload['feoaction']['jsminify'] = jsminify

    if jsinline:
        payload['feoaction']['jsinline'] = jsinline

    if htmlminify:
        payload['feoaction']['htmlminify'] = htmlminify

    if cssmovetohead:
        payload['feoaction']['cssmovetohead'] = cssmovetohead

    if jsmovetoend:
        payload['feoaction']['jsmovetoend'] = jsmovetoend

    if domainsharding:
        payload['feoaction']['domainsharding'] = domainsharding

    if dnsshards:
        payload['feoaction']['dnsshards'] = dnsshards

    if clientsidemeasurements:
        payload['feoaction']['clientsidemeasurements'] = clientsidemeasurements

    execution = __proxy__['citrixns.put']('config/feoaction', payload)

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


def update_feoparameter(jpegqualitypercent=None, cssinlinethressize=None, jsinlinethressize=None,
                        imginlinethressize=None, save=False):
    '''
    Update the running configuration for the feoparameter config key.

    jpegqualitypercent(int): The percentage value of a JPEG image quality to be reduced. Range: 0 - 100. Default value: 75
        Minimum value = 0 Maximum value = 100

    cssinlinethressize(int): Threshold value of the file size (in bytes) for converting external CSS files to inline CSS
        files. Default value: 1024 Minimum value = 1 Maximum value = 2048

    jsinlinethressize(int): Threshold value of the file size (in bytes), for converting external JavaScript files to inline
        JavaScript files. Default value: 1024 Minimum value = 1 Maximum value = 2048

    imginlinethressize(int): Maximum file size of an image (in bytes), for coverting linked images to inline images. Default
        value: 1024 Minimum value = 1 Maximum value = 2048

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.update_feoparameter <args>

    '''

    result = {}

    payload = {'feoparameter': {}}

    if jpegqualitypercent:
        payload['feoparameter']['jpegqualitypercent'] = jpegqualitypercent

    if cssinlinethressize:
        payload['feoparameter']['cssinlinethressize'] = cssinlinethressize

    if jsinlinethressize:
        payload['feoparameter']['jsinlinethressize'] = jsinlinethressize

    if imginlinethressize:
        payload['feoparameter']['imginlinethressize'] = imginlinethressize

    execution = __proxy__['citrixns.put']('config/feoparameter', payload)

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


def update_feopolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the feopolicy config key.

    name(str): The name of the front end optimization policy. Minimum length = 1

    rule(str): The rule associated with the front end optimization policy.

    action(str): The front end optimization action that has to be performed when the rule matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' front_end_optimization.update_feopolicy <args>

    '''

    result = {}

    payload = {'feopolicy': {}}

    if name:
        payload['feopolicy']['name'] = name

    if rule:
        payload['feopolicy']['rule'] = rule

    if action:
        payload['feopolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/feopolicy', payload)

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
