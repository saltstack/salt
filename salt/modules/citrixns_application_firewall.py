# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the application-firewall key.

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

__virtualname__ = 'application_firewall'


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

    return False, 'The application_firewall execution module can only be loaded for citrixns proxy minions.'


def add_appfwconfidfield(fieldname=None, url=None, isregex=None, comment=None, state=None, save=False):
    '''
    Add a new appfwconfidfield to the running configuration.

    fieldname(str): Name of the form field to designate as confidential. Minimum length = 1

    url(str): URL of the web page that contains the web form. Minimum length = 1

    isregex(str): Method of specifying the form field name. Available settings function as follows: * REGEX. Form field is a
        regular expression. * NOTREGEX. Form field is a literal string. Default value: NOTREGEX Possible values = REGEX,
        NOTREGEX

    comment(str): Any comments to preserve information about the form field designation.

    state(str): Enable or disable the confidential field designation. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwconfidfield <args>

    '''

    result = {}

    payload = {'appfwconfidfield': {}}

    if fieldname:
        payload['appfwconfidfield']['fieldname'] = fieldname

    if url:
        payload['appfwconfidfield']['url'] = url

    if isregex:
        payload['appfwconfidfield']['isregex'] = isregex

    if comment:
        payload['appfwconfidfield']['comment'] = comment

    if state:
        payload['appfwconfidfield']['state'] = state

    execution = __proxy__['citrixns.post']('config/appfwconfidfield', payload)

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


def add_appfwfieldtype(name=None, regex=None, priority=None, comment=None, nocharmaps=None, save=False):
    '''
    Add a new appfwfieldtype to the running configuration.

    name(str): Name for the field type. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the field type is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my field type" or my field type). Minimum length = 1

    regex(str): PCRE - format regular expression defining the characters and length allowed for this field type. Minimum
        length = 1

    priority(int): Positive integer specifying the priority of the field type. A lower number specifies a higher priority.
        Field types are checked in the order of their priority numbers. Minimum value = 0 Maximum value = 64000

    comment(str): Comment describing the type of field that this field type is intended to match.

    nocharmaps(bool): will not show internal field types added as part of FieldFormat learn rules deployment.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwfieldtype <args>

    '''

    result = {}

    payload = {'appfwfieldtype': {}}

    if name:
        payload['appfwfieldtype']['name'] = name

    if regex:
        payload['appfwfieldtype']['regex'] = regex

    if priority:
        payload['appfwfieldtype']['priority'] = priority

    if comment:
        payload['appfwfieldtype']['comment'] = comment

    if nocharmaps:
        payload['appfwfieldtype']['nocharmaps'] = nocharmaps

    execution = __proxy__['citrixns.post']('config/appfwfieldtype', payload)

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


def add_appfwglobal_appfwpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None, state=None,
                                        gotopriorityexpression=None, ns_type=None, invoke=None, labeltype=None,
                                        save=False):
    '''
    Add a new appfwglobal_appfwpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the policy.

    labelname(str): Name of the policy label to invoke if the current policy evaluates to TRUE, the invoke parameter is set,
        and Label Type is set to Policy Label.

    state(str): Enable or disable the binding to activate or deactivate the policy. This is applicable to classic policies
        only. Possible values = ENABLED, DISABLED

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    ns_type(str): Bind point to which to policy is bound. Possible values = REQ_OVERRIDE, REQ_DEFAULT, NONE

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then forward the request to the specified virtual server or evaluate the specified policy label.

    labeltype(str): Type of policy label invocation. Possible values = reqvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwglobal_appfwpolicy_binding <args>

    '''

    result = {}

    payload = {'appfwglobal_appfwpolicy_binding': {}}

    if priority:
        payload['appfwglobal_appfwpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['appfwglobal_appfwpolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['appfwglobal_appfwpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['appfwglobal_appfwpolicy_binding']['labelname'] = labelname

    if state:
        payload['appfwglobal_appfwpolicy_binding']['state'] = state

    if gotopriorityexpression:
        payload['appfwglobal_appfwpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if ns_type:
        payload['appfwglobal_appfwpolicy_binding']['type'] = ns_type

    if invoke:
        payload['appfwglobal_appfwpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['appfwglobal_appfwpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/appfwglobal_appfwpolicy_binding', payload)

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


def add_appfwglobal_auditnslogpolicy_binding(priority=None, policyname=None, labelname=None, state=None,
                                             gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None,
                                             save=False):
    '''
    Add a new appfwglobal_auditnslogpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    policyname(str): Name of the policy.

    labelname(str): Name of the policy label to invoke if the current policy evaluates to TRUE, the invoke parameter is set,
        and Label Type is set to Policy Label.

    state(str): Enable or disable the binding to activate or deactivate the policy. This is applicable to classic policies
        only. Possible values = ENABLED, DISABLED

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is smaller than the current
        policys priority number. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then forward the request to the specified virtual server or evaluate the specified policy label.

    ns_type(str): Bind point to which to policy is bound. Possible values = REQ_OVERRIDE, REQ_DEFAULT, NONE

    labeltype(str): Type of policy label to invoke if the current policy evaluates to TRUE and the invoke parameter is set.
        Available settings function as follows: * reqvserver. Invoke the unnamed policy label associated with the
        specified request virtual server. * policylabel. Invoke the specified user-defined policy label. Possible values
        = reqvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwglobal_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'appfwglobal_auditnslogpolicy_binding': {}}

    if priority:
        payload['appfwglobal_auditnslogpolicy_binding']['priority'] = priority

    if policyname:
        payload['appfwglobal_auditnslogpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['appfwglobal_auditnslogpolicy_binding']['labelname'] = labelname

    if state:
        payload['appfwglobal_auditnslogpolicy_binding']['state'] = state

    if gotopriorityexpression:
        payload['appfwglobal_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['appfwglobal_auditnslogpolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['appfwglobal_auditnslogpolicy_binding']['type'] = ns_type

    if labeltype:
        payload['appfwglobal_auditnslogpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/appfwglobal_auditnslogpolicy_binding', payload)

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


def add_appfwglobal_auditsyslogpolicy_binding(priority=None, policyname=None, labelname=None, state=None,
                                              gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None,
                                              save=False):
    '''
    Add a new appfwglobal_auditsyslogpolicy_binding to the running configuration.

    priority(int): The priority of the policy.

    policyname(str): Name of the policy.

    labelname(str): Name of the policy label to invoke if the current policy evaluates to TRUE, the invoke parameter is set,
        and Label Type is set to Policy Label.

    state(str): Enable or disable the binding to activate or deactivate the policy. This is applicable to classic policies
        only. Possible values = ENABLED, DISABLED

    gotopriorityexpression(str): Expression or other value specifying the next policy to evaluate if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax or
        classic expression that evaluates to a number. If you specify an expression, the number to which it evaluates
        determines the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority,
        the policy with that priority is evaluated next. * If the expression evaluates to the priority of the current
        policy, the policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a
        number that is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if:
        * The expression is invalid. * The expression evaluates to a priority number that is smaller than the current
        policys priority number. * The expression evaluates to a priority number that is between the current policys
        priority number (say, 30) and the highest priority number (say, 100), but does not match any configured priority
        number (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then forward the request to the specified virtual server or evaluate the specified policy label.

    ns_type(str): Bind point to which to policy is bound. Possible values = REQ_OVERRIDE, REQ_DEFAULT, NONE

    labeltype(str): Type of policy label to invoke if the current policy evaluates to TRUE and the invoke parameter is set.
        Available settings function as follows: * reqvserver. Invoke the unnamed policy label associated with the
        specified request virtual server. * policylabel. Invoke the specified user-defined policy label. Possible values
        = reqvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwglobal_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'appfwglobal_auditsyslogpolicy_binding': {}}

    if priority:
        payload['appfwglobal_auditsyslogpolicy_binding']['priority'] = priority

    if policyname:
        payload['appfwglobal_auditsyslogpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['appfwglobal_auditsyslogpolicy_binding']['labelname'] = labelname

    if state:
        payload['appfwglobal_auditsyslogpolicy_binding']['state'] = state

    if gotopriorityexpression:
        payload['appfwglobal_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['appfwglobal_auditsyslogpolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['appfwglobal_auditsyslogpolicy_binding']['type'] = ns_type

    if labeltype:
        payload['appfwglobal_auditsyslogpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/appfwglobal_auditsyslogpolicy_binding', payload)

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


def add_appfwjsoncontenttype(jsoncontenttypevalue=None, isregex=None, save=False):
    '''
    Add a new appfwjsoncontenttype to the running configuration.

    jsoncontenttypevalue(str): Content type to be classified as JSON. Minimum length = 1

    isregex(str): Is json content type a regular expression?. Default value: NOTREGEX Possible values = REGEX, NOTREGEX

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwjsoncontenttype <args>

    '''

    result = {}

    payload = {'appfwjsoncontenttype': {}}

    if jsoncontenttypevalue:
        payload['appfwjsoncontenttype']['jsoncontenttypevalue'] = jsoncontenttypevalue

    if isregex:
        payload['appfwjsoncontenttype']['isregex'] = isregex

    execution = __proxy__['citrixns.post']('config/appfwjsoncontenttype', payload)

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


def add_appfwpolicy(name=None, rule=None, profilename=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Add a new appfwpolicy to the running configuration.

    name(str): Name for the policy.  Must begin with a letter, number, or the underscore character \\(_\\), and must contain
        only letters, numbers, and the hyphen \\(-\\), period \\(.\\) pound \\(\\#\\), space \\( \\), at (@), equals
        \\(=\\), colon \\(:\\), and underscore characters. Can be changed after the policy is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks \\(for example, "my policy" or my policy\\). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a NetScaler default syntax expression, that the policy uses to determine
        whether to filter the connection through the application firewall with the designated profile.

    profilename(str): Name of the application firewall profile to use if the policy matches. Minimum length = 1

    comment(str): Any comments to preserve information about the policy for later reference.

    logaction(str): Where to log information for connections that match this policy.

    newname(str): New name for the policy. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my policy" or my
        policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwpolicy <args>

    '''

    result = {}

    payload = {'appfwpolicy': {}}

    if name:
        payload['appfwpolicy']['name'] = name

    if rule:
        payload['appfwpolicy']['rule'] = rule

    if profilename:
        payload['appfwpolicy']['profilename'] = profilename

    if comment:
        payload['appfwpolicy']['comment'] = comment

    if logaction:
        payload['appfwpolicy']['logaction'] = logaction

    if newname:
        payload['appfwpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/appfwpolicy', payload)

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


def add_appfwpolicylabel(labelname=None, policylabeltype=None, newname=None, save=False):
    '''
    Add a new appfwpolicylabel to the running configuration.

    labelname(str): Name for the policy label. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Can be changed after the policy label is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my policy label" or my policy label).

    policylabeltype(str): Type of transformations allowed by the policies bound to the label. Always http_req for application
        firewall policy labels. Possible values = http_req

    newname(str): The new name of the application firewall policylabel. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwpolicylabel <args>

    '''

    result = {}

    payload = {'appfwpolicylabel': {}}

    if labelname:
        payload['appfwpolicylabel']['labelname'] = labelname

    if policylabeltype:
        payload['appfwpolicylabel']['policylabeltype'] = policylabeltype

    if newname:
        payload['appfwpolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/appfwpolicylabel', payload)

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


def add_appfwpolicylabel_appfwpolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                             gotopriorityexpression=None, invoke=None, labeltype=None, save=False):
    '''
    Add a new appfwpolicylabel_appfwpolicy_binding to the running configuration.

    priority(int): Positive integer specifying the priority of the policy. A lower number specifies a higher priority. Must
        be unique within a group of policies that are bound to the same bind point or label. Policies are evaluated in
        the order of their priority numbers.

    policyname(str): Name of the application firewall policy to bind to the policy label.

    labelname(str): Name of the application firewall policy label.

    invoke_labelname(str): Name of the policy label to invoke if the current policy evaluates to TRUE, the invoke parameter
        is set, and Label Type is set to Policy Label.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then forward the request to the specified virtual server or evaluate the specified policy label.

    labeltype(str): Type of policy label to invoke if the current policy evaluates to TRUE and the invoke parameter is set.
        Available settings function as follows: * reqvserver. Invoke the unnamed policy label associated with the
        specified request virtual server. * policylabel. Invoke the specified user-defined policy label. Possible values
        = reqvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwpolicylabel_appfwpolicy_binding <args>

    '''

    result = {}

    payload = {'appfwpolicylabel_appfwpolicy_binding': {}}

    if priority:
        payload['appfwpolicylabel_appfwpolicy_binding']['priority'] = priority

    if policyname:
        payload['appfwpolicylabel_appfwpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['appfwpolicylabel_appfwpolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['appfwpolicylabel_appfwpolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['appfwpolicylabel_appfwpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['appfwpolicylabel_appfwpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['appfwpolicylabel_appfwpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/appfwpolicylabel_appfwpolicy_binding', payload)

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


def add_appfwprofile(name=None, defaults=None, starturlaction=None, contenttypeaction=None, inspectcontenttypes=None,
                     starturlclosure=None, denyurlaction=None, refererheadercheck=None, cookieconsistencyaction=None,
                     cookietransforms=None, cookieencryption=None, cookieproxying=None, addcookieflags=None,
                     fieldconsistencyaction=None, csrftagaction=None, crosssitescriptingaction=None,
                     crosssitescriptingtransformunsafehtml=None, crosssitescriptingcheckcompleteurls=None,
                     sqlinjectionaction=None, sqlinjectiontransformspecialchars=None,
                     sqlinjectiononlycheckfieldswithsqlchars=None, sqlinjectiontype=None,
                     sqlinjectionchecksqlwildchars=None, fieldformataction=None, defaultfieldformattype=None,
                     defaultfieldformatminlength=None, defaultfieldformatmaxlength=None, bufferoverflowaction=None,
                     bufferoverflowmaxurllength=None, bufferoverflowmaxheaderlength=None,
                     bufferoverflowmaxcookielength=None, creditcardaction=None, creditcard=None,
                     creditcardmaxallowed=None, creditcardxout=None, dosecurecreditcardlogging=None, streaming=None,
                     trace=None, requestcontenttype=None, responsecontenttype=None, xmldosaction=None,
                     xmlformataction=None, xmlsqlinjectionaction=None, xmlsqlinjectiononlycheckfieldswithsqlchars=None,
                     xmlsqlinjectiontype=None, xmlsqlinjectionchecksqlwildchars=None, xmlsqlinjectionparsecomments=None,
                     xmlxssaction=None, xmlwsiaction=None, xmlattachmentaction=None, xmlvalidationaction=None,
                     xmlerrorobject=None, customsettings=None, signatures=None, xmlsoapfaultaction=None,
                     usehtmlerrorobject=None, errorurl=None, htmlerrorobject=None, logeverypolicyhit=None,
                     stripcomments=None, striphtmlcomments=None, stripxmlcomments=None,
                     exemptclosureurlsfromsecuritychecks=None, defaultcharset=None, postbodylimit=None,
                     fileuploadmaxnum=None, canonicalizehtmlresponse=None, enableformtagging=None,
                     sessionlessfieldconsistency=None, sessionlessurlclosure=None, semicolonfieldseparator=None,
                     excludefileuploadfromchecks=None, sqlinjectionparsecomments=None, invalidpercenthandling=None,
                     ns_type=None, checkrequestheaders=None, optimizepartialreqs=None, urldecoderequestcookies=None,
                     comment=None, percentdecoderecursively=None, multipleheaderaction=None, archivename=None,
                     save=False):
    '''
    Add a new appfwprofile to the running configuration.

    name(str): Name for the profile. Must begin with a letter, number, or the underscore character (_), and must contain only
        letters, numbers, and the hyphen (-), period (.), pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore (_) characters. Cannot be changed after the profile is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my profile" or my profile). Minimum length = 1

    defaults(str): Default configuration to apply to the profile. Basic defaults are intended for standard content that
        requires little further configuration, such as static web site content. Advanced defaults are intended for
        specialized content that requires significant specialized configuration, such as heavily scripted or dynamic
        content.  CLI users: When adding an application firewall profile, you can set either the defaults or the type,
        but not both. To set both options, create the profile by using the add appfw profile command, and then use the
        set appfw profile command to configure the other option. Possible values = basic, advanced

    starturlaction(list(str)): One or more Start URL actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Learn - Use the learning engine to generate a list of exceptions
        to this security check. * Log - Log violations of this security check. * Stats - Generate statistics for this
        security check. * None - Disable all actions for this security check.  CLI users: To enable one or more actions,
        type "set appfw profile -startURLaction" followed by the actions to be enabled. To turn off all actions, type
        "set appfw profile -startURLaction none". Possible values = none, block, learn, log, stats

    contenttypeaction(list(str)): One or more Content-type actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Learn - Use the learning engine to generate a list of exceptions
        to this security check. * Log - Log violations of this security check. * Stats - Generate statistics for this
        security check. * None - Disable all actions for this security check.  CLI users: To enable one or more actions,
        type "set appfw profile -contentTypeaction" followed by the actions to be enabled. To turn off all actions, type
        "set appfw profile -contentTypeaction none". Possible values = none, block, learn, log, stats

    inspectcontenttypes(list(str)): One or more InspectContentType lists.  * application/x-www-form-urlencoded *
        multipart/form-data * text/x-gwt-rpc  CLI users: To enable, type "set appfw profile -InspectContentTypes"
        followed by the content types to be inspected. Possible values = none, application/x-www-form-urlencoded,
        multipart/form-data, text/x-gwt-rpc

    starturlclosure(str): Toggle the state of Start URL Closure. Default value: OFF Possible values = ON, OFF

    denyurlaction(list(str)): One or more Deny URL actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  NOTE: The Deny URL
        check takes precedence over the Start URL check. If you enable blocking for the Deny URL check, the application
        firewall blocks any URL that is explicitly blocked by a Deny URL, even if the same URL would otherwise be allowed
        by the Start URL check.  CLI users: To enable one or more actions, type "set appfw profile -denyURLaction"
        followed by the actions to be enabled. To turn off all actions, type "set appfw profile -denyURLaction none".
        Possible values = none, block, learn, log, stats

    refererheadercheck(str): Enable validation of Referer headers.  Referer validation ensures that a web form that a user
        sends to your web site originally came from your web site, not an outside attacker.  Although this parameter is
        part of the Start URL check, referer validation protects against cross-site request forgery (CSRF) attacks, not
        Start URL attacks. Default value: OFF Possible values = OFF, if_present, AlwaysExceptStartURLs,
        AlwaysExceptFirstRequest

    cookieconsistencyaction(list(str)): One or more Cookie Consistency actions. Available settings function as follows: *
        Block - Block connections that violate this security check. * Learn - Use the learning engine to generate a list
        of exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -cookieConsistencyAction" followed by the actions to be enabled. To
        turn off all actions, type "set appfw profile -cookieConsistencyAction none". Default value: none Possible values
        = none, block, learn, log, stats

    cookietransforms(str): Perform the specified type of cookie transformation.  Available settings function as follows:  *
        Encryption - Encrypt cookies. * Proxying - Mask contents of server cookies by sending proxy cookie to users. *
        Cookie flags - Flag cookies as HTTP only to prevent scripts on users browser from accessing and possibly
        modifying them. CAUTION: Make sure that this parameter is set to ON if you are configuring any cookie
        transformations. If it is set to OFF, no cookie transformations are performed regardless of any other settings.
        Default value: OFF Possible values = ON, OFF

    cookieencryption(str): Type of cookie encryption. Available settings function as follows: * None - Do not encrypt
        cookies. * Decrypt Only - Decrypt encrypted cookies, but do not encrypt cookies. * Encrypt Session Only - Encrypt
        session cookies, but not permanent cookies. * Encrypt All - Encrypt all cookies. Default value: none Possible
        values = none, decryptOnly, encryptSessionOnly, encryptAll

    cookieproxying(str): Cookie proxy setting. Available settings function as follows: * None - Do not proxy cookies. *
        Session Only - Proxy session cookies by using the NetScaler session ID, but do not proxy permanent cookies.
        Default value: none Possible values = none, sessionOnly

    addcookieflags(str): Add the specified flags to cookies. Available settings function as follows: * None - Do not add
        flags to cookies. * HTTP Only - Add the HTTP Only flag to cookies, which prevents scripts from accessing cookies.
        * Secure - Add Secure flag to cookies. * All - Add both HTTPOnly and Secure flags to cookies. Default value: none
        Possible values = none, httpOnly, secure, all

    fieldconsistencyaction(list(str)): One or more Form Field Consistency actions. Available settings function as follows: *
        Block - Block connections that violate this security check. * Learn - Use the learning engine to generate a list
        of exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -fieldConsistencyaction" followed by the actions to be enabled. To
        turn off all actions, type "set appfw profile -fieldConsistencyAction none". Default value: none Possible values
        = none, block, learn, log, stats

    csrftagaction(list(str)): One or more Cross-Site Request Forgery (CSRF) Tagging actions. Available settings function as
        follows: * Block - Block connections that violate this security check. * Learn - Use the learning engine to
        generate a list of exceptions to this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -CSRFTagAction" followed by the actions to be enabled. To
        turn off all actions, type "set appfw profile -CSRFTagAction none". Default value: none Possible values = none,
        block, learn, log, stats

    crosssitescriptingaction(list(str)): One or more Cross-Site Scripting (XSS) actions. Available settings function as
        follows: * Block - Block connections that violate this security check. * Learn - Use the learning engine to
        generate a list of exceptions to this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -crossSiteScriptingAction" followed by the actions to be
        enabled. To turn off all actions, type "set appfw profile -crossSiteScriptingAction none". Possible values =
        none, block, learn, log, stats

    crosssitescriptingtransformunsafehtml(str): Transform cross-site scripts. This setting configures the application
        firewall to disable dangerous HTML instead of blocking the request.  CAUTION: Make sure that this parameter is
        set to ON if you are configuring any cross-site scripting transformations. If it is set to OFF, no cross-site
        scripting transformations are performed regardless of any other settings. Default value: OFF Possible values =
        ON, OFF

    crosssitescriptingcheckcompleteurls(str): Check complete URLs for cross-site scripts, instead of just the query portions
        of URLs. Default value: OFF Possible values = ON, OFF

    sqlinjectionaction(list(str)): One or more HTML SQL Injection actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Learn - Use the learning engine to generate a list of
        exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate statistics
        for this security check. * None - Disable all actions for this security check.  CLI users: To enable one or more
        actions, type "set appfw profile -SQLInjectionAction" followed by the actions to be enabled. To turn off all
        actions, type "set appfw profile -SQLInjectionAction none". Possible values = none, block, learn, log, stats

    sqlinjectiontransformspecialchars(str): Transform injected SQL code. This setting configures the application firewall to
        disable SQL special strings instead of blocking the request. Since most SQL servers require a special string to
        activate an SQL keyword, in most cases a request that contains injected SQL code is safe if special strings are
        disabled. CAUTION: Make sure that this parameter is set to ON if you are configuring any SQL injection
        transformations. If it is set to OFF, no SQL injection transformations are performed regardless of any other
        settings. Default value: OFF Possible values = ON, OFF

    sqlinjectiononlycheckfieldswithsqlchars(str): Check only form fields that contain SQL special strings (characters) for
        injected SQL code. Most SQL servers require a special string to activate an SQL request, so SQL code without a
        special string is harmless to most SQL servers. Default value: ON Possible values = ON, OFF

    sqlinjectiontype(str): Available SQL injection types.  -SQLSplChar : Checks for SQL Special Chars -SQLKeyword : Checks
        for SQL Keywords -SQLSplCharANDKeyword : Checks for both and blocks if both are found -SQLSplCharORKeyword :
        Checks for both and blocks if anyone is found. Default value: SQLSplCharANDKeyword Possible values = SQLSplChar,
        SQLKeyword, SQLSplCharORKeyword, SQLSplCharANDKeyword

    sqlinjectionchecksqlwildchars(str): Check for form fields that contain SQL wild chars . Default value: OFF Possible
        values = ON, OFF

    fieldformataction(list(str)): One or more Field Format actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Learn - Use the learning engine to generate a list of suggested
        web form fields and field format assignments. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -fieldFormatAction" followed by the actions to be enabled. To turn
        off all actions, type "set appfw profile -fieldFormatAction none". Possible values = none, block, learn, log,
        stats

    defaultfieldformattype(str): Designate a default field type to be applied to web form fields that do not have a field
        type explicitly assigned to them. Minimum length = 1

    defaultfieldformatminlength(int): Minimum length, in characters, for data entered into a field that is assigned the
        default field type.  To disable the minimum and maximum length settings and allow data of any length to be
        entered into the field, set this parameter to zero (0). Default value: 0 Minimum value = 0 Maximum value =
        2147483647

    defaultfieldformatmaxlength(int): Maximum length, in characters, for data entered into a field that is assigned the
        default field type. Default value: 65535 Minimum value = 1 Maximum value = 2147483647

    bufferoverflowaction(list(str)): One or more Buffer Overflow actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -bufferOverflowAction" followed by the actions to be enabled.
        To turn off all actions, type "set appfw profile -bufferOverflowAction none". Possible values = none, block,
        learn, log, stats

    bufferoverflowmaxurllength(int): Maximum length, in characters, for URLs on your protected web sites. Requests with
        longer URLs are blocked. Default value: 1024 Minimum value = 0 Maximum value = 65535

    bufferoverflowmaxheaderlength(int): Maximum length, in characters, for HTTP headers in requests sent to your protected
        web sites. Requests with longer headers are blocked. Default value: 4096 Minimum value = 0 Maximum value = 65535

    bufferoverflowmaxcookielength(int): Maximum length, in characters, for cookies sent to your protected web sites. Requests
        with longer cookies are blocked. Default value: 4096 Minimum value = 0 Maximum value = 65535

    creditcardaction(list(str)): One or more Credit Card actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -creditCardAction" followed by the actions to be enabled. To turn
        off all actions, type "set appfw profile -creditCardAction none". Default value: none Possible values = none,
        block, learn, log, stats

    creditcard(list(str)): Credit card types that the application firewall should protect. Possible values = visa,
        mastercard, discover, amex, jcb, dinersclub

    creditcardmaxallowed(int): This parameter value is used by the block action. It represents the maximum number of credit
        card numbers that can appear on a web page served by your protected web sites. Pages that contain more credit
        card numbers are blocked. Minimum value = 0 Maximum value = 255

    creditcardxout(str): Mask any credit card number detected in a response by replacing each digit, except the digits in the
        final group, with the letter "X.". Default value: OFF Possible values = ON, OFF

    dosecurecreditcardlogging(str): Setting this option logs credit card numbers in the response when the match is found.
        Default value: ON Possible values = ON, OFF

    streaming(str): Setting this option converts content-length form submission requests (requests with content-type
        "application/x-www-form-urlencoded" or "multipart/form-data") to chunked requests when atleast one of the
        following protections : SQL injection protection, XSS protection, form field consistency protection, starturl
        closure, CSRF tagging is enabled. Please make sure that the backend server accepts chunked requests before
        enabling this option. Default value: OFF Possible values = ON, OFF

    trace(str): Toggle the state of trace. Default value: OFF Possible values = ON, OFF

    requestcontenttype(str): Default Content-Type header for requests.  A Content-Type header can contain 0-255 letters,
        numbers, and the hyphen (-) and underscore (_) characters. Minimum length = 1 Maximum length = 255

    responsecontenttype(str): Default Content-Type header for responses.  A Content-Type header can contain 0-255 letters,
        numbers, and the hyphen (-) and underscore (_) characters. Minimum length = 1 Maximum length = 255

    xmldosaction(list(str)): One or more XML Denial-of-Service (XDoS) actions. Available settings function as follows: *
        Block - Block connections that violate this security check. * Learn - Use the learning engine to generate a list
        of exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -XMLDoSAction" followed by the actions to be enabled. To turn off
        all actions, type "set appfw profile -XMLDoSAction none". Possible values = none, block, learn, log, stats

    xmlformataction(list(str)): One or more XML Format actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -XMLFormatAction" followed by the actions to be enabled. To turn off
        all actions, type "set appfw profile -XMLFormatAction none". Possible values = none, block, learn, log, stats

    xmlsqlinjectionaction(list(str)): One or more XML SQL Injection actions. Available settings function as follows: * Block
        - Block connections that violate this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -XMLSQLInjectionAction" followed by the actions to be
        enabled. To turn off all actions, type "set appfw profile -XMLSQLInjectionAction none". Possible values = none,
        block, learn, log, stats

    xmlsqlinjectiononlycheckfieldswithsqlchars(str): Check only form fields that contain SQL special characters, which most
        SQL servers require before accepting an SQL command, for injected SQL. Default value: ON Possible values = ON,
        OFF

    xmlsqlinjectiontype(str): Available SQL injection types. -SQLSplChar : Checks for SQL Special Chars -SQLKeyword : Checks
        for SQL Keywords -SQLSplCharANDKeyword : Checks for both and blocks if both are found -SQLSplCharORKeyword :
        Checks for both and blocks if anyone is found. Default value: SQLSplCharANDKeyword Possible values = SQLSplChar,
        SQLKeyword, SQLSplCharORKeyword, SQLSplCharANDKeyword

    xmlsqlinjectionchecksqlwildchars(str): Check for form fields that contain SQL wild chars . Default value: OFF Possible
        values = ON, OFF

    xmlsqlinjectionparsecomments(str): Parse comments in XML Data and exempt those sections of the request that are from the
        XML SQL Injection check. You must configure the type of comments that the application firewall is to detect and
        exempt from this security check. Available settings function as follows: * Check all - Check all content. * ANSI
        - Exempt content that is part of an ANSI (Mozilla-style) comment.  * Nested - Exempt content that is part of a
        nested (Microsoft-style) comment. * ANSI Nested - Exempt content that is part of any type of comment. Default
        value: checkall Possible values = checkall, ansi, nested, ansinested

    xmlxssaction(list(str)): One or more XML Cross-Site Scripting actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -XMLXSSAction" followed by the actions to be enabled. To turn
        off all actions, type "set appfw profile -XMLXSSAction none". Possible values = none, block, learn, log, stats

    xmlwsiaction(list(str)): One or more Web Services Interoperability (WSI) actions. Available settings function as follows:
        * Block - Block connections that violate this security check. * Learn - Use the learning engine to generate a
        list of exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -XMLWSIAction" followed by the actions to be enabled. To turn off
        all actions, type "set appfw profile -XMLWSIAction none". Possible values = none, block, learn, log, stats

    xmlattachmentaction(list(str)): One or more XML Attachment actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Learn - Use the learning engine to generate a list of
        exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate statistics
        for this security check. * None - Disable all actions for this security check.  CLI users: To enable one or more
        actions, type "set appfw profile -XMLAttachmentAction" followed by the actions to be enabled. To turn off all
        actions, type "set appfw profile -XMLAttachmentAction none". Possible values = none, block, learn, log, stats

    xmlvalidationaction(list(str)): One or more XML Validation actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.   CLI users:
        To enable one or more actions, type "set appfw profile -XMLValidationAction" followed by the actions to be
        enabled. To turn off all actions, type "set appfw profile -XMLValidationAction none". Possible values = none,
        block, learn, log, stats

    xmlerrorobject(str): Name to assign to the XML Error Object, which the application firewall displays when a user request
        is blocked. Must begin with a letter, number, or the underscore character \\(_\\), and must contain only letters,
        numbers, and the hyphen \\(-\\), period \\(.\\) pound \\(\\#\\), space \\( \\), at (@), equals \\(=\\), colon
        \\(:\\), and underscore characters. Cannot be changed after the XML error object is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks \\(for example, "my XML error object" or my XML error object\\). Minimum length
        = 1

    customsettings(str): Object name for custom settings. This check is applicable to Profile Type: HTML, XML. . Minimum
        length = 1

    signatures(str): Object name for signatures. This check is applicable to Profile Type: HTML, XML. . Minimum length = 1

    xmlsoapfaultaction(list(str)): One or more XML SOAP Fault Filtering actions. Available settings function as follows: *
        Block - Block connections that violate this security check. * Log - Log violations of this security check. *
        Stats - Generate statistics for this security check. * None - Disable all actions for this security check. *
        Remove - Remove all violations for this security check.  CLI users: To enable one or more actions, type "set
        appfw profile -XMLSOAPFaultAction" followed by the actions to be enabled. To turn off all actions, type "set
        appfw profile -XMLSOAPFaultAction none". Possible values = none, block, log, remove, stats

    usehtmlerrorobject(str): Send an imported HTML Error object to a user when a request is blocked, instead of redirecting
        the user to the designated Error URL. Default value: OFF Possible values = ON, OFF

    errorurl(str): URL that application firewall uses as the Error URL. Minimum length = 1

    htmlerrorobject(str): Name to assign to the HTML Error Object.  Must begin with a letter, number, or the underscore
        character \\(_\\), and must contain only letters, numbers, and the hyphen \\(-\\), period \\(.\\) pound
        \\(\\#\\), space \\( \\), at (@), equals \\(=\\), colon \\(:\\), and underscore characters. Cannot be changed
        after the HTML error object is added.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks \\(for example, "my HTML error
        object" or my HTML error object\\). Minimum length = 1

    logeverypolicyhit(str): Log every profile match, regardless of security checks results. Default value: OFF Possible
        values = ON, OFF

    stripcomments(str): Strip HTML comments. This check is applicable to Profile Type: HTML. . Default value: OFF Possible
        values = ON, OFF

    striphtmlcomments(str): Strip HTML comments before forwarding a web page sent by a protected web site in response to a
        user request. Default value: none Possible values = none, all, exclude_script_tag

    stripxmlcomments(str): Strip XML comments before forwarding a web page sent by a protected web site in response to a user
        request. Default value: none Possible values = none, all

    exemptclosureurlsfromsecuritychecks(str): Exempt URLs that pass the Start URL closure check from SQL injection,
        cross-site script, field format and field consistency security checks at locations other than headers. Default
        value: ON Possible values = ON, OFF

    defaultcharset(str): Default character set for protected web pages. Web pages sent by your protected web sites in
        response to user requests are assigned this character set if the page does not already specify a character set.
        The character sets supported by the application firewall are:  * iso-8859-1 (English US) * big5 (Chinese
        Traditional) * gb2312 (Chinese Simplified) * sjis (Japanese Shift-JIS) * euc-jp (Japanese EUC-JP) * iso-8859-9
        (Turkish) * utf-8 (Unicode) * euc-kr (Korean). Minimum length = 1 Maximum length = 31

    postbodylimit(int): Maximum allowed HTTP post body size, in bytes. Default value: 20000000

    fileuploadmaxnum(int): Maximum allowed number of file uploads per form-submission request. The maximum setting (65535)
        allows an unlimited number of uploads. Default value: 65535 Minimum value = 0 Maximum value = 65535

    canonicalizehtmlresponse(str): Perform HTML entity encoding for any special characters in responses sent by your
        protected web sites. Default value: ON Possible values = ON, OFF

    enableformtagging(str): Enable tagging of web form fields for use by the Form Field Consistency and CSRF Form Tagging
        checks. Default value: ON Possible values = ON, OFF

    sessionlessfieldconsistency(str): Perform sessionless Field Consistency Checks. Default value: OFF Possible values = OFF,
        ON, postOnly

    sessionlessurlclosure(str): Enable session less URL Closure Checks. This check is applicable to Profile Type: HTML. .
        Default value: OFF Possible values = ON, OFF

    semicolonfieldseparator(str): Allow ; as a form field separator in URL queries and POST form bodies. . Default value: OFF
        Possible values = ON, OFF

    excludefileuploadfromchecks(str): Exclude uploaded files from Form checks. Default value: OFF Possible values = ON, OFF

    sqlinjectionparsecomments(str): Parse HTML comments and exempt them from the HTML SQL Injection check. You must specify
        the type of comments that the application firewall is to detect and exempt from this security check. Available
        settings function as follows: * Check all - Check all content. * ANSI - Exempt content that is part of an ANSI
        (Mozilla-style) comment.  * Nested - Exempt content that is part of a nested (Microsoft-style) comment. * ANSI
        Nested - Exempt content that is part of any type of comment. Possible values = checkall, ansi, nested,
        ansinested

    invalidpercenthandling(str): Configure the method that the application firewall uses to handle percent-encoded names and
        values. Available settings function as follows:  * apache_mode - Apache format. * asp_mode - Microsoft ASP
        format. * secure_mode - Secure format. Default value: secure_mode Possible values = apache_mode, asp_mode,
        secure_mode

    ns_type(list(str)): Application firewall profile type, which controls which security checks and settings are applied to
        content that is filtered with the profile. Available settings function as follows: * HTML - HTML-based web sites.
        * XML - XML-based web sites and services. * HTML XML (Web 2.0) - Sites that contain both HTML and XML content,
        such as ATOM feeds, blogs, and RSS feeds. Default value: HTML Possible values = HTML, XML

    checkrequestheaders(str): Check request headers as well as web forms for injected SQL and cross-site scripts. Default
        value: OFF Possible values = ON, OFF

    optimizepartialreqs(str): Optimize handle of HTTP partial requests i.e. those with range headers. Available settings are
        as follows:  * ON - Partial requests by the client result in partial requests to the backend server in most
        cases. * OFF - Partial requests by the client are changed to full requests to the backend server. Default value:
        ON Possible values = ON, OFF

    urldecoderequestcookies(str): URL Decode request cookies before subjecting them to SQL and cross-site scripting checks.
        Default value: OFF Possible values = ON, OFF

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    percentdecoderecursively(str): Configure whether the application firewall should use percentage recursive decoding.
        Default value: OFF Possible values = ON, OFF

    multipleheaderaction(list(str)): One or more multiple header actions. Available settings function as follows: * Block -
        Block connections that have multiple headers. * Log - Log connections that have multiple headers. * KeepLast -
        Keep only last header when multiple headers are present.  CLI users: To enable one or more actions, type "set
        appfw profile -multipleHeaderAction" followed by the actions to be enabled. Possible values = block, keepLast,
        log, none

    archivename(str): Source for tar archive. Minimum length = 1 Maximum length = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile <args>

    '''

    result = {}

    payload = {'appfwprofile': {}}

    if name:
        payload['appfwprofile']['name'] = name

    if defaults:
        payload['appfwprofile']['defaults'] = defaults

    if starturlaction:
        payload['appfwprofile']['starturlaction'] = starturlaction

    if contenttypeaction:
        payload['appfwprofile']['contenttypeaction'] = contenttypeaction

    if inspectcontenttypes:
        payload['appfwprofile']['inspectcontenttypes'] = inspectcontenttypes

    if starturlclosure:
        payload['appfwprofile']['starturlclosure'] = starturlclosure

    if denyurlaction:
        payload['appfwprofile']['denyurlaction'] = denyurlaction

    if refererheadercheck:
        payload['appfwprofile']['refererheadercheck'] = refererheadercheck

    if cookieconsistencyaction:
        payload['appfwprofile']['cookieconsistencyaction'] = cookieconsistencyaction

    if cookietransforms:
        payload['appfwprofile']['cookietransforms'] = cookietransforms

    if cookieencryption:
        payload['appfwprofile']['cookieencryption'] = cookieencryption

    if cookieproxying:
        payload['appfwprofile']['cookieproxying'] = cookieproxying

    if addcookieflags:
        payload['appfwprofile']['addcookieflags'] = addcookieflags

    if fieldconsistencyaction:
        payload['appfwprofile']['fieldconsistencyaction'] = fieldconsistencyaction

    if csrftagaction:
        payload['appfwprofile']['csrftagaction'] = csrftagaction

    if crosssitescriptingaction:
        payload['appfwprofile']['crosssitescriptingaction'] = crosssitescriptingaction

    if crosssitescriptingtransformunsafehtml:
        payload['appfwprofile']['crosssitescriptingtransformunsafehtml'] = crosssitescriptingtransformunsafehtml

    if crosssitescriptingcheckcompleteurls:
        payload['appfwprofile']['crosssitescriptingcheckcompleteurls'] = crosssitescriptingcheckcompleteurls

    if sqlinjectionaction:
        payload['appfwprofile']['sqlinjectionaction'] = sqlinjectionaction

    if sqlinjectiontransformspecialchars:
        payload['appfwprofile']['sqlinjectiontransformspecialchars'] = sqlinjectiontransformspecialchars

    if sqlinjectiononlycheckfieldswithsqlchars:
        payload['appfwprofile']['sqlinjectiononlycheckfieldswithsqlchars'] = sqlinjectiononlycheckfieldswithsqlchars

    if sqlinjectiontype:
        payload['appfwprofile']['sqlinjectiontype'] = sqlinjectiontype

    if sqlinjectionchecksqlwildchars:
        payload['appfwprofile']['sqlinjectionchecksqlwildchars'] = sqlinjectionchecksqlwildchars

    if fieldformataction:
        payload['appfwprofile']['fieldformataction'] = fieldformataction

    if defaultfieldformattype:
        payload['appfwprofile']['defaultfieldformattype'] = defaultfieldformattype

    if defaultfieldformatminlength:
        payload['appfwprofile']['defaultfieldformatminlength'] = defaultfieldformatminlength

    if defaultfieldformatmaxlength:
        payload['appfwprofile']['defaultfieldformatmaxlength'] = defaultfieldformatmaxlength

    if bufferoverflowaction:
        payload['appfwprofile']['bufferoverflowaction'] = bufferoverflowaction

    if bufferoverflowmaxurllength:
        payload['appfwprofile']['bufferoverflowmaxurllength'] = bufferoverflowmaxurllength

    if bufferoverflowmaxheaderlength:
        payload['appfwprofile']['bufferoverflowmaxheaderlength'] = bufferoverflowmaxheaderlength

    if bufferoverflowmaxcookielength:
        payload['appfwprofile']['bufferoverflowmaxcookielength'] = bufferoverflowmaxcookielength

    if creditcardaction:
        payload['appfwprofile']['creditcardaction'] = creditcardaction

    if creditcard:
        payload['appfwprofile']['creditcard'] = creditcard

    if creditcardmaxallowed:
        payload['appfwprofile']['creditcardmaxallowed'] = creditcardmaxallowed

    if creditcardxout:
        payload['appfwprofile']['creditcardxout'] = creditcardxout

    if dosecurecreditcardlogging:
        payload['appfwprofile']['dosecurecreditcardlogging'] = dosecurecreditcardlogging

    if streaming:
        payload['appfwprofile']['streaming'] = streaming

    if trace:
        payload['appfwprofile']['trace'] = trace

    if requestcontenttype:
        payload['appfwprofile']['requestcontenttype'] = requestcontenttype

    if responsecontenttype:
        payload['appfwprofile']['responsecontenttype'] = responsecontenttype

    if xmldosaction:
        payload['appfwprofile']['xmldosaction'] = xmldosaction

    if xmlformataction:
        payload['appfwprofile']['xmlformataction'] = xmlformataction

    if xmlsqlinjectionaction:
        payload['appfwprofile']['xmlsqlinjectionaction'] = xmlsqlinjectionaction

    if xmlsqlinjectiononlycheckfieldswithsqlchars:
        payload['appfwprofile']['xmlsqlinjectiononlycheckfieldswithsqlchars'] = xmlsqlinjectiononlycheckfieldswithsqlchars

    if xmlsqlinjectiontype:
        payload['appfwprofile']['xmlsqlinjectiontype'] = xmlsqlinjectiontype

    if xmlsqlinjectionchecksqlwildchars:
        payload['appfwprofile']['xmlsqlinjectionchecksqlwildchars'] = xmlsqlinjectionchecksqlwildchars

    if xmlsqlinjectionparsecomments:
        payload['appfwprofile']['xmlsqlinjectionparsecomments'] = xmlsqlinjectionparsecomments

    if xmlxssaction:
        payload['appfwprofile']['xmlxssaction'] = xmlxssaction

    if xmlwsiaction:
        payload['appfwprofile']['xmlwsiaction'] = xmlwsiaction

    if xmlattachmentaction:
        payload['appfwprofile']['xmlattachmentaction'] = xmlattachmentaction

    if xmlvalidationaction:
        payload['appfwprofile']['xmlvalidationaction'] = xmlvalidationaction

    if xmlerrorobject:
        payload['appfwprofile']['xmlerrorobject'] = xmlerrorobject

    if customsettings:
        payload['appfwprofile']['customsettings'] = customsettings

    if signatures:
        payload['appfwprofile']['signatures'] = signatures

    if xmlsoapfaultaction:
        payload['appfwprofile']['xmlsoapfaultaction'] = xmlsoapfaultaction

    if usehtmlerrorobject:
        payload['appfwprofile']['usehtmlerrorobject'] = usehtmlerrorobject

    if errorurl:
        payload['appfwprofile']['errorurl'] = errorurl

    if htmlerrorobject:
        payload['appfwprofile']['htmlerrorobject'] = htmlerrorobject

    if logeverypolicyhit:
        payload['appfwprofile']['logeverypolicyhit'] = logeverypolicyhit

    if stripcomments:
        payload['appfwprofile']['stripcomments'] = stripcomments

    if striphtmlcomments:
        payload['appfwprofile']['striphtmlcomments'] = striphtmlcomments

    if stripxmlcomments:
        payload['appfwprofile']['stripxmlcomments'] = stripxmlcomments

    if exemptclosureurlsfromsecuritychecks:
        payload['appfwprofile']['exemptclosureurlsfromsecuritychecks'] = exemptclosureurlsfromsecuritychecks

    if defaultcharset:
        payload['appfwprofile']['defaultcharset'] = defaultcharset

    if postbodylimit:
        payload['appfwprofile']['postbodylimit'] = postbodylimit

    if fileuploadmaxnum:
        payload['appfwprofile']['fileuploadmaxnum'] = fileuploadmaxnum

    if canonicalizehtmlresponse:
        payload['appfwprofile']['canonicalizehtmlresponse'] = canonicalizehtmlresponse

    if enableformtagging:
        payload['appfwprofile']['enableformtagging'] = enableformtagging

    if sessionlessfieldconsistency:
        payload['appfwprofile']['sessionlessfieldconsistency'] = sessionlessfieldconsistency

    if sessionlessurlclosure:
        payload['appfwprofile']['sessionlessurlclosure'] = sessionlessurlclosure

    if semicolonfieldseparator:
        payload['appfwprofile']['semicolonfieldseparator'] = semicolonfieldseparator

    if excludefileuploadfromchecks:
        payload['appfwprofile']['excludefileuploadfromchecks'] = excludefileuploadfromchecks

    if sqlinjectionparsecomments:
        payload['appfwprofile']['sqlinjectionparsecomments'] = sqlinjectionparsecomments

    if invalidpercenthandling:
        payload['appfwprofile']['invalidpercenthandling'] = invalidpercenthandling

    if ns_type:
        payload['appfwprofile']['type'] = ns_type

    if checkrequestheaders:
        payload['appfwprofile']['checkrequestheaders'] = checkrequestheaders

    if optimizepartialreqs:
        payload['appfwprofile']['optimizepartialreqs'] = optimizepartialreqs

    if urldecoderequestcookies:
        payload['appfwprofile']['urldecoderequestcookies'] = urldecoderequestcookies

    if comment:
        payload['appfwprofile']['comment'] = comment

    if percentdecoderecursively:
        payload['appfwprofile']['percentdecoderecursively'] = percentdecoderecursively

    if multipleheaderaction:
        payload['appfwprofile']['multipleheaderaction'] = multipleheaderaction

    if archivename:
        payload['appfwprofile']['archivename'] = archivename

    execution = __proxy__['citrixns.post']('config/appfwprofile', payload)

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


def add_appfwprofile_contenttype_binding(state=None, name=None, contenttype=None, comment=None, save=False):
    '''
    Add a new appfwprofile_contenttype_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    contenttype(str): A regular expression that designates a content-type on the content-types list.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_contenttype_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_contenttype_binding': {}}

    if state:
        payload['appfwprofile_contenttype_binding']['state'] = state

    if name:
        payload['appfwprofile_contenttype_binding']['name'] = name

    if contenttype:
        payload['appfwprofile_contenttype_binding']['contenttype'] = contenttype

    if comment:
        payload['appfwprofile_contenttype_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_contenttype_binding', payload)

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


def add_appfwprofile_cookieconsistency_binding(state=None, name=None, isregex=None, cookieconsistency=None, comment=None,
                                               save=False):
    '''
    Add a new appfwprofile_cookieconsistency_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    isregex(str): Is the cookie name a regular expression?. Possible values = REGEX, NOTREGEX

    cookieconsistency(str): The name of the cookie to be checked.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_cookieconsistency_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_cookieconsistency_binding': {}}

    if state:
        payload['appfwprofile_cookieconsistency_binding']['state'] = state

    if name:
        payload['appfwprofile_cookieconsistency_binding']['name'] = name

    if isregex:
        payload['appfwprofile_cookieconsistency_binding']['isregex'] = isregex

    if cookieconsistency:
        payload['appfwprofile_cookieconsistency_binding']['cookieconsistency'] = cookieconsistency

    if comment:
        payload['appfwprofile_cookieconsistency_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_cookieconsistency_binding', payload)

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


def add_appfwprofile_creditcardnumber_binding(creditcardnumberurl=None, state=None, name=None, creditcardnumber=None,
                                              comment=None, save=False):
    '''
    Add a new appfwprofile_creditcardnumber_binding to the running configuration.

    creditcardnumberurl(str): The url for which the list of credit card numbers are needed to be bypassed from inspection.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    creditcardnumber(str): The object expression that is to be excluded from safe commerce check.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_creditcardnumber_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_creditcardnumber_binding': {}}

    if creditcardnumberurl:
        payload['appfwprofile_creditcardnumber_binding']['creditcardnumberurl'] = creditcardnumberurl

    if state:
        payload['appfwprofile_creditcardnumber_binding']['state'] = state

    if name:
        payload['appfwprofile_creditcardnumber_binding']['name'] = name

    if creditcardnumber:
        payload['appfwprofile_creditcardnumber_binding']['creditcardnumber'] = creditcardnumber

    if comment:
        payload['appfwprofile_creditcardnumber_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_creditcardnumber_binding', payload)

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


def add_appfwprofile_crosssitescripting_binding(crosssitescripting=None, name=None, isregex_xss=None, state=None,
                                                comment=None, formactionurl_xss=None, as_value_expr_xss=None,
                                                as_scan_location_xss=None, as_value_type_xss=None, isvalueregex_xss=None,
                                                save=False):
    '''
    Add a new appfwprofile_crosssitescripting_binding to the running configuration.

    crosssitescripting(str): The web form field name.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    isregex_xss(str): Is the web form field name a regular expression?. Possible values = REGEX, NOTREGEX

    state(str): Enabled. Possible values = ENABLED, DISABLED

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    formactionurl_xss(str): The web form action URL.

    as_value_expr_xss(str): The web form value expression.

    as_scan_location_xss(str): Location of cross-site scripting exception - form field, header or cookie. Possible values =
        FORMFIELD, HEADER, COOKIE

    as_value_type_xss(str): The web form value type. Possible values = Tag, Attribute, Pattern

    isvalueregex_xss(str): Is the web form field value a regular expression?. Possible values = REGEX, NOTREGEX

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_crosssitescripting_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_crosssitescripting_binding': {}}

    if crosssitescripting:
        payload['appfwprofile_crosssitescripting_binding']['crosssitescripting'] = crosssitescripting

    if name:
        payload['appfwprofile_crosssitescripting_binding']['name'] = name

    if isregex_xss:
        payload['appfwprofile_crosssitescripting_binding']['isregex_xss'] = isregex_xss

    if state:
        payload['appfwprofile_crosssitescripting_binding']['state'] = state

    if comment:
        payload['appfwprofile_crosssitescripting_binding']['comment'] = comment

    if formactionurl_xss:
        payload['appfwprofile_crosssitescripting_binding']['formactionurl_xss'] = formactionurl_xss

    if as_value_expr_xss:
        payload['appfwprofile_crosssitescripting_binding']['as_value_expr_xss'] = as_value_expr_xss

    if as_scan_location_xss:
        payload['appfwprofile_crosssitescripting_binding']['as_scan_location_xss'] = as_scan_location_xss

    if as_value_type_xss:
        payload['appfwprofile_crosssitescripting_binding']['as_value_type_xss'] = as_value_type_xss

    if isvalueregex_xss:
        payload['appfwprofile_crosssitescripting_binding']['isvalueregex_xss'] = isvalueregex_xss

    execution = __proxy__['citrixns.post']('config/appfwprofile_crosssitescripting_binding', payload)

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


def add_appfwprofile_csrftag_binding(state=None, name=None, csrftag=None, csrfformactionurl=None, comment=None,
                                     save=False):
    '''
    Add a new appfwprofile_csrftag_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    csrftag(str): The web form originating URL.

    csrfformactionurl(str): The web form action URL.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_csrftag_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_csrftag_binding': {}}

    if state:
        payload['appfwprofile_csrftag_binding']['state'] = state

    if name:
        payload['appfwprofile_csrftag_binding']['name'] = name

    if csrftag:
        payload['appfwprofile_csrftag_binding']['csrftag'] = csrftag

    if csrfformactionurl:
        payload['appfwprofile_csrftag_binding']['csrfformactionurl'] = csrfformactionurl

    if comment:
        payload['appfwprofile_csrftag_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_csrftag_binding', payload)

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


def add_appfwprofile_denyurl_binding(state=None, denyurl=None, name=None, comment=None, save=False):
    '''
    Add a new appfwprofile_denyurl_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    denyurl(str): A regular expression that designates a URL on the Deny URL list.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_denyurl_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_denyurl_binding': {}}

    if state:
        payload['appfwprofile_denyurl_binding']['state'] = state

    if denyurl:
        payload['appfwprofile_denyurl_binding']['denyurl'] = denyurl

    if name:
        payload['appfwprofile_denyurl_binding']['name'] = name

    if comment:
        payload['appfwprofile_denyurl_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_denyurl_binding', payload)

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


def add_appfwprofile_excluderescontenttype_binding(excluderescontenttype=None, name=None, state=None, comment=None,
                                                   save=False):
    '''
    Add a new appfwprofile_excluderescontenttype_binding to the running configuration.

    excluderescontenttype(str): A regular expression that represents the content type of the response that are to be excluded
        from inspection.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    state(str): Enabled. Possible values = ENABLED, DISABLED

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_excluderescontenttype_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_excluderescontenttype_binding': {}}

    if excluderescontenttype:
        payload['appfwprofile_excluderescontenttype_binding']['excluderescontenttype'] = excluderescontenttype

    if name:
        payload['appfwprofile_excluderescontenttype_binding']['name'] = name

    if state:
        payload['appfwprofile_excluderescontenttype_binding']['state'] = state

    if comment:
        payload['appfwprofile_excluderescontenttype_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_excluderescontenttype_binding', payload)

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


def add_appfwprofile_fieldconsistency_binding(fieldconsistency=None, state=None, name=None, isregex_ffc=None,
                                              formactionurl_ffc=None, comment=None, save=False):
    '''
    Add a new appfwprofile_fieldconsistency_binding to the running configuration.

    fieldconsistency(str): The web form field name.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    isregex_ffc(str): Is the web form field name a regular expression?. Possible values = REGEX, NOTREGEX

    formactionurl_ffc(str): The web form action URL.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_fieldconsistency_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_fieldconsistency_binding': {}}

    if fieldconsistency:
        payload['appfwprofile_fieldconsistency_binding']['fieldconsistency'] = fieldconsistency

    if state:
        payload['appfwprofile_fieldconsistency_binding']['state'] = state

    if name:
        payload['appfwprofile_fieldconsistency_binding']['name'] = name

    if isregex_ffc:
        payload['appfwprofile_fieldconsistency_binding']['isregex_ffc'] = isregex_ffc

    if formactionurl_ffc:
        payload['appfwprofile_fieldconsistency_binding']['formactionurl_ffc'] = formactionurl_ffc

    if comment:
        payload['appfwprofile_fieldconsistency_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_fieldconsistency_binding', payload)

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


def add_appfwprofile_fieldformat_binding(state=None, fieldformatmaxlength=None, isregex_ff=None, fieldtype=None,
                                         formactionurl_ff=None, name=None, fieldformatminlength=None, comment=None,
                                         fieldformat=None, save=False):
    '''
    Add a new appfwprofile_fieldformat_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    fieldformatmaxlength(int): The maximum allowed length for data in this form field.

    isregex_ff(str): Is the form field name a regular expression?. Possible values = REGEX, NOTREGEX

    fieldtype(str): The field type you are assigning to this form field.

    formactionurl_ff(str): Action URL of the form field to which a field format will be assigned.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    fieldformatminlength(int): The minimum allowed length for data in this form field.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    fieldformat(str): Name of the form field to which a field format will be assigned.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_fieldformat_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_fieldformat_binding': {}}

    if state:
        payload['appfwprofile_fieldformat_binding']['state'] = state

    if fieldformatmaxlength:
        payload['appfwprofile_fieldformat_binding']['fieldformatmaxlength'] = fieldformatmaxlength

    if isregex_ff:
        payload['appfwprofile_fieldformat_binding']['isregex_ff'] = isregex_ff

    if fieldtype:
        payload['appfwprofile_fieldformat_binding']['fieldtype'] = fieldtype

    if formactionurl_ff:
        payload['appfwprofile_fieldformat_binding']['formactionurl_ff'] = formactionurl_ff

    if name:
        payload['appfwprofile_fieldformat_binding']['name'] = name

    if fieldformatminlength:
        payload['appfwprofile_fieldformat_binding']['fieldformatminlength'] = fieldformatminlength

    if comment:
        payload['appfwprofile_fieldformat_binding']['comment'] = comment

    if fieldformat:
        payload['appfwprofile_fieldformat_binding']['fieldformat'] = fieldformat

    execution = __proxy__['citrixns.post']('config/appfwprofile_fieldformat_binding', payload)

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


def add_appfwprofile_safeobject_binding(maxmatchlength=None, state=None, expression=None, name=None, safeobject=None,
                                        comment=None, action=None, save=False):
    '''
    Add a new appfwprofile_safeobject_binding to the running configuration.

    maxmatchlength(int): Maximum match length for a Safe Object expression.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    expression(str): A regular expression that defines the Safe Object.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    safeobject(str): Name of the Safe Object.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    action(list(str)): Safe Object action types. (BLOCK | LOG | STATS | NONE). Possible values = none, block, log, remove,
        stats, xout

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_safeobject_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_safeobject_binding': {}}

    if maxmatchlength:
        payload['appfwprofile_safeobject_binding']['maxmatchlength'] = maxmatchlength

    if state:
        payload['appfwprofile_safeobject_binding']['state'] = state

    if expression:
        payload['appfwprofile_safeobject_binding']['expression'] = expression

    if name:
        payload['appfwprofile_safeobject_binding']['name'] = name

    if safeobject:
        payload['appfwprofile_safeobject_binding']['safeobject'] = safeobject

    if comment:
        payload['appfwprofile_safeobject_binding']['comment'] = comment

    if action:
        payload['appfwprofile_safeobject_binding']['action'] = action

    execution = __proxy__['citrixns.post']('config/appfwprofile_safeobject_binding', payload)

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


def add_appfwprofile_sqlinjection_binding(as_value_expr_sql=None, state=None, formactionurl_sql=None, name=None,
                                          isregex_sql=None, isvalueregex_sql=None, as_scan_location_sql=None,
                                          sqlinjection=None, as_value_type_sql=None, comment=None, save=False):
    '''
    Add a new appfwprofile_sqlinjection_binding to the running configuration.

    as_value_expr_sql(str): The web form value expression.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    formactionurl_sql(str): The web form action URL.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    isregex_sql(str): Is the web form field name a regular expression?. Possible values = REGEX, NOTREGEX

    isvalueregex_sql(str): Is the web form field value a regular expression?. Possible values = REGEX, NOTREGEX

    as_scan_location_sql(str): Location of SQL injection exception - form field, header or cookie. Possible values =
        FORMFIELD, HEADER, COOKIE

    sqlinjection(str): The web form field name.

    as_value_type_sql(str): The web form value type. Possible values = Keyword, SpecialString, Wildchar

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_sqlinjection_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_sqlinjection_binding': {}}

    if as_value_expr_sql:
        payload['appfwprofile_sqlinjection_binding']['as_value_expr_sql'] = as_value_expr_sql

    if state:
        payload['appfwprofile_sqlinjection_binding']['state'] = state

    if formactionurl_sql:
        payload['appfwprofile_sqlinjection_binding']['formactionurl_sql'] = formactionurl_sql

    if name:
        payload['appfwprofile_sqlinjection_binding']['name'] = name

    if isregex_sql:
        payload['appfwprofile_sqlinjection_binding']['isregex_sql'] = isregex_sql

    if isvalueregex_sql:
        payload['appfwprofile_sqlinjection_binding']['isvalueregex_sql'] = isvalueregex_sql

    if as_scan_location_sql:
        payload['appfwprofile_sqlinjection_binding']['as_scan_location_sql'] = as_scan_location_sql

    if sqlinjection:
        payload['appfwprofile_sqlinjection_binding']['sqlinjection'] = sqlinjection

    if as_value_type_sql:
        payload['appfwprofile_sqlinjection_binding']['as_value_type_sql'] = as_value_type_sql

    if comment:
        payload['appfwprofile_sqlinjection_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_sqlinjection_binding', payload)

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


def add_appfwprofile_starturl_binding(state=None, name=None, starturl=None, comment=None, save=False):
    '''
    Add a new appfwprofile_starturl_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    starturl(str): A regular expression that designates a URL on the Start URL list.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_starturl_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_starturl_binding': {}}

    if state:
        payload['appfwprofile_starturl_binding']['state'] = state

    if name:
        payload['appfwprofile_starturl_binding']['name'] = name

    if starturl:
        payload['appfwprofile_starturl_binding']['starturl'] = starturl

    if comment:
        payload['appfwprofile_starturl_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_starturl_binding', payload)

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


def add_appfwprofile_trustedlearningclients_binding(state=None, trustedlearningclients=None, name=None, comment=None,
                                                    save=False):
    '''
    Add a new appfwprofile_trustedlearningclients_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    trustedlearningclients(str): Specify trusted host/network IP.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_trustedlearningclients_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_trustedlearningclients_binding': {}}

    if state:
        payload['appfwprofile_trustedlearningclients_binding']['state'] = state

    if trustedlearningclients:
        payload['appfwprofile_trustedlearningclients_binding']['trustedlearningclients'] = trustedlearningclients

    if name:
        payload['appfwprofile_trustedlearningclients_binding']['name'] = name

    if comment:
        payload['appfwprofile_trustedlearningclients_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_trustedlearningclients_binding', payload)

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


def add_appfwprofile_xmlattachmenturl_binding(xmlattachmenturl=None, name=None, xmlmaxattachmentsize=None,
                                              xmlmaxattachmentsizecheck=None, state=None,
                                              xmlattachmentcontenttypecheck=None, comment=None,
                                              xmlattachmentcontenttype=None, save=False):
    '''
    Add a new appfwprofile_xmlattachmenturl_binding to the running configuration.

    xmlattachmenturl(str): XML attachment URL regular expression length.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    xmlmaxattachmentsize(int): Specify maximum attachment size.

    xmlmaxattachmentsizecheck(str): State if XML Max attachment size Check is ON or OFF. Protects against XML requests with
        large attachment data. Possible values = ON, OFF

    state(str): Enabled. Possible values = ENABLED, DISABLED

    xmlattachmentcontenttypecheck(str): State if XML attachment content-type check is ON or OFF. Protects against XML
        requests with illegal attachments. Possible values = ON, OFF

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    xmlattachmentcontenttype(str): Specify content-type regular expression.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_xmlattachmenturl_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_xmlattachmenturl_binding': {}}

    if xmlattachmenturl:
        payload['appfwprofile_xmlattachmenturl_binding']['xmlattachmenturl'] = xmlattachmenturl

    if name:
        payload['appfwprofile_xmlattachmenturl_binding']['name'] = name

    if xmlmaxattachmentsize:
        payload['appfwprofile_xmlattachmenturl_binding']['xmlmaxattachmentsize'] = xmlmaxattachmentsize

    if xmlmaxattachmentsizecheck:
        payload['appfwprofile_xmlattachmenturl_binding']['xmlmaxattachmentsizecheck'] = xmlmaxattachmentsizecheck

    if state:
        payload['appfwprofile_xmlattachmenturl_binding']['state'] = state

    if xmlattachmentcontenttypecheck:
        payload['appfwprofile_xmlattachmenturl_binding']['xmlattachmentcontenttypecheck'] = xmlattachmentcontenttypecheck

    if comment:
        payload['appfwprofile_xmlattachmenturl_binding']['comment'] = comment

    if xmlattachmentcontenttype:
        payload['appfwprofile_xmlattachmenturl_binding']['xmlattachmentcontenttype'] = xmlattachmentcontenttype

    execution = __proxy__['citrixns.post']('config/appfwprofile_xmlattachmenturl_binding', payload)

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


def add_appfwprofile_xmldosurl_binding(xmlmaxelementdepthcheck=None, xmlmaxfilesize=None, xmlmaxnamespaceurilength=None,
                                       xmldosurl=None, state=None, xmlsoaparraycheck=None,
                                       xmlmaxelementnamelengthcheck=None, xmlmaxelementscheck=None,
                                       xmlmaxentityexpansions=None, xmlmaxattributes=None, xmlmaxfilesizecheck=None,
                                       xmlmaxchardatalength=None, xmlmaxnamespacescheck=None, xmlmaxnamespaces=None,
                                       xmlmaxattributenamelengthcheck=None, xmlblockdtd=None,
                                       xmlmaxattributevaluelength=None, xmlmaxelementdepth=None,
                                       xmlmaxelementnamelength=None, name=None, xmlblockpi=None,
                                       xmlmaxelementchildrencheck=None, xmlmaxelements=None,
                                       xmlmaxentityexpansionscheck=None, xmlmaxnamespaceurilengthcheck=None,
                                       xmlmaxentityexpansiondepthcheck=None, xmlmaxattributevaluelengthcheck=None,
                                       xmlmaxsoaparraysize=None, xmlmaxentityexpansiondepth=None, xmlmaxnodescheck=None,
                                       xmlmaxattributenamelength=None, xmlmaxchardatalengthcheck=None,
                                       xmlminfilesizecheck=None, xmlmaxelementchildren=None, xmlminfilesize=None,
                                       xmlmaxnodes=None, comment=None, xmlmaxattributescheck=None,
                                       xmlmaxsoaparrayrank=None, xmlblockexternalentities=None, save=False):
    '''
    Add a new appfwprofile_xmldosurl_binding to the running configuration.

    xmlmaxelementdepthcheck(str): State if XML Max element depth check is ON or OFF. Possible values = ON, OFF

    xmlmaxfilesize(int): Specify the maximum size of XML messages. Protects against overflow attacks.

    xmlmaxnamespaceurilength(int): Specify the longest URI of any XML namespace. Protects against overflow attacks.

    xmldosurl(str): XML DoS URL regular expression length.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    xmlsoaparraycheck(str): State if XML SOAP Array check is ON or OFF. Possible values = ON, OFF

    xmlmaxelementnamelengthcheck(str): State if XML Max element name length check is ON or OFF. Possible values = ON, OFF

    xmlmaxelementscheck(str): State if XML Max elements check is ON or OFF. Possible values = ON, OFF

    xmlmaxentityexpansions(int): Specify maximum allowed number of entity expansions. Protects aganist Entity Expansion
        Attack.

    xmlmaxattributes(int): Specify maximum number of attributes per XML element. Protects against overflow attacks.

    xmlmaxfilesizecheck(str): State if XML Max file size check is ON or OFF. Possible values = ON, OFF

    xmlmaxchardatalength(int): Specify the maximum size of CDATA. Protects against overflow attacks and large quantities of
        unparsed data within XML messages.

    xmlmaxnamespacescheck(str): State if XML Max namespaces check is ON or OFF. Possible values = ON, OFF

    xmlmaxnamespaces(int): Specify maximum number of active namespaces. Protects against overflow attacks.

    xmlmaxattributenamelengthcheck(str): State if XML Max attribute name length check is ON or OFF. Possible values = ON,
        OFF

    xmlblockdtd(str): State if XML DTD is ON or OFF. Protects against recursive Document Type Declaration (DTD) entity
        expansion attacks. Also, SOAP messages cannot have DTDs in messages. . Possible values = ON, OFF

    xmlmaxattributevaluelength(int): Specify the longest value of any XML attribute. Protects against overflow attacks.

    xmlmaxelementdepth(int): Maximum nesting (depth) of XML elements. This check protects against documents that have
        excessive hierarchy depths.

    xmlmaxelementnamelength(int): Specify the longest name of any element (including the expanded namespace) to protect
        against overflow attacks.

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    xmlblockpi(str): State if XML Block PI is ON or OFF. Protects resources from denial of service attacks as SOAP messages
        cannot have processing instructions (PI) in messages. Possible values = ON, OFF

    xmlmaxelementchildrencheck(str): State if XML Max element children check is ON or OFF. Possible values = ON, OFF

    xmlmaxelements(int): Specify the maximum number of XML elements allowed. Protects against overflow attacks.

    xmlmaxentityexpansionscheck(str): State if XML Max Entity Expansions Check is ON or OFF. Possible values = ON, OFF

    xmlmaxnamespaceurilengthcheck(str): State if XML Max namespace URI length check is ON or OFF. Possible values = ON, OFF

    xmlmaxentityexpansiondepthcheck(str): State if XML Max Entity Expansions Depth Check is ON or OFF. Possible values = ON,
        OFF

    xmlmaxattributevaluelengthcheck(str): State if XML Max atribute value length is ON or OFF. Possible values = ON, OFF

    xmlmaxsoaparraysize(int): XML Max Total SOAP Array Size. Protects against SOAP Array Abuse attack.

    xmlmaxentityexpansiondepth(int): Specify maximum entity expansion depth. Protects aganist Entity Expansion Attack.

    xmlmaxnodescheck(str): State if XML Max nodes check is ON or OFF. Possible values = ON, OFF

    xmlmaxattributenamelength(int): Specify the longest name of any XML attribute. Protects against overflow attacks.

    xmlmaxchardatalengthcheck(str): State if XML Max CDATA length check is ON or OFF. Possible values = ON, OFF

    xmlminfilesizecheck(str): State if XML Min file size check is ON or OFF. Possible values = ON, OFF

    xmlmaxelementchildren(int): Specify the maximum number of children allowed per XML element. Protects against overflow
        attacks.

    xmlminfilesize(int): Enforces minimum message size.

    xmlmaxnodes(int): Specify the maximum number of XML nodes. Protects against overflow attacks.

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    xmlmaxattributescheck(str): State if XML Max attributes check is ON or OFF. Possible values = ON, OFF

    xmlmaxsoaparrayrank(int): XML Max Individual SOAP Array Rank. This is the dimension of the SOAP array.

    xmlblockexternalentities(str): State if XML Block External Entities Check is ON or OFF. Protects against XML External
        Entity (XXE) attacks that force applications to parse untrusted external entities (sources) in XML documents.
        Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_xmldosurl_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_xmldosurl_binding': {}}

    if xmlmaxelementdepthcheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxelementdepthcheck'] = xmlmaxelementdepthcheck

    if xmlmaxfilesize:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxfilesize'] = xmlmaxfilesize

    if xmlmaxnamespaceurilength:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxnamespaceurilength'] = xmlmaxnamespaceurilength

    if xmldosurl:
        payload['appfwprofile_xmldosurl_binding']['xmldosurl'] = xmldosurl

    if state:
        payload['appfwprofile_xmldosurl_binding']['state'] = state

    if xmlsoaparraycheck:
        payload['appfwprofile_xmldosurl_binding']['xmlsoaparraycheck'] = xmlsoaparraycheck

    if xmlmaxelementnamelengthcheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxelementnamelengthcheck'] = xmlmaxelementnamelengthcheck

    if xmlmaxelementscheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxelementscheck'] = xmlmaxelementscheck

    if xmlmaxentityexpansions:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxentityexpansions'] = xmlmaxentityexpansions

    if xmlmaxattributes:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxattributes'] = xmlmaxattributes

    if xmlmaxfilesizecheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxfilesizecheck'] = xmlmaxfilesizecheck

    if xmlmaxchardatalength:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxchardatalength'] = xmlmaxchardatalength

    if xmlmaxnamespacescheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxnamespacescheck'] = xmlmaxnamespacescheck

    if xmlmaxnamespaces:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxnamespaces'] = xmlmaxnamespaces

    if xmlmaxattributenamelengthcheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxattributenamelengthcheck'] = xmlmaxattributenamelengthcheck

    if xmlblockdtd:
        payload['appfwprofile_xmldosurl_binding']['xmlblockdtd'] = xmlblockdtd

    if xmlmaxattributevaluelength:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxattributevaluelength'] = xmlmaxattributevaluelength

    if xmlmaxelementdepth:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxelementdepth'] = xmlmaxelementdepth

    if xmlmaxelementnamelength:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxelementnamelength'] = xmlmaxelementnamelength

    if name:
        payload['appfwprofile_xmldosurl_binding']['name'] = name

    if xmlblockpi:
        payload['appfwprofile_xmldosurl_binding']['xmlblockpi'] = xmlblockpi

    if xmlmaxelementchildrencheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxelementchildrencheck'] = xmlmaxelementchildrencheck

    if xmlmaxelements:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxelements'] = xmlmaxelements

    if xmlmaxentityexpansionscheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxentityexpansionscheck'] = xmlmaxentityexpansionscheck

    if xmlmaxnamespaceurilengthcheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxnamespaceurilengthcheck'] = xmlmaxnamespaceurilengthcheck

    if xmlmaxentityexpansiondepthcheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxentityexpansiondepthcheck'] = xmlmaxentityexpansiondepthcheck

    if xmlmaxattributevaluelengthcheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxattributevaluelengthcheck'] = xmlmaxattributevaluelengthcheck

    if xmlmaxsoaparraysize:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxsoaparraysize'] = xmlmaxsoaparraysize

    if xmlmaxentityexpansiondepth:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxentityexpansiondepth'] = xmlmaxentityexpansiondepth

    if xmlmaxnodescheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxnodescheck'] = xmlmaxnodescheck

    if xmlmaxattributenamelength:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxattributenamelength'] = xmlmaxattributenamelength

    if xmlmaxchardatalengthcheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxchardatalengthcheck'] = xmlmaxchardatalengthcheck

    if xmlminfilesizecheck:
        payload['appfwprofile_xmldosurl_binding']['xmlminfilesizecheck'] = xmlminfilesizecheck

    if xmlmaxelementchildren:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxelementchildren'] = xmlmaxelementchildren

    if xmlminfilesize:
        payload['appfwprofile_xmldosurl_binding']['xmlminfilesize'] = xmlminfilesize

    if xmlmaxnodes:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxnodes'] = xmlmaxnodes

    if comment:
        payload['appfwprofile_xmldosurl_binding']['comment'] = comment

    if xmlmaxattributescheck:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxattributescheck'] = xmlmaxattributescheck

    if xmlmaxsoaparrayrank:
        payload['appfwprofile_xmldosurl_binding']['xmlmaxsoaparrayrank'] = xmlmaxsoaparrayrank

    if xmlblockexternalentities:
        payload['appfwprofile_xmldosurl_binding']['xmlblockexternalentities'] = xmlblockexternalentities

    execution = __proxy__['citrixns.post']('config/appfwprofile_xmldosurl_binding', payload)

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


def add_appfwprofile_xmlsqlinjection_binding(as_scan_location_xmlsql=None, state=None, name=None, xmlsqlinjection=None,
                                             isregex_xmlsql=None, comment=None, save=False):
    '''
    Add a new appfwprofile_xmlsqlinjection_binding to the running configuration.

    as_scan_location_xmlsql(str): Location of SQL injection exception - XML Element or Attribute. Possible values = ELEMENT,
        ATTRIBUTE

    state(str): Enabled. Possible values = ENABLED, DISABLED

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    xmlsqlinjection(str): Exempt the specified URL from the XML SQL injection check. An XML SQL injection exemption
        (relaxation) consists of the following items: * Name. Name to exempt, as a string or a PCRE-format regular
        expression. * ISREGEX flag. REGEX if URL is a regular expression, NOTREGEX if URL is a fixed string. * Location.
        ELEMENT if the injection is located in an XML element, ATTRIBUTE if located in an XML attribute.

    isregex_xmlsql(str): Is the XML SQL Injection exempted field name a regular expression?. Possible values = REGEX,
        NOTREGEX

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_xmlsqlinjection_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_xmlsqlinjection_binding': {}}

    if as_scan_location_xmlsql:
        payload['appfwprofile_xmlsqlinjection_binding']['as_scan_location_xmlsql'] = as_scan_location_xmlsql

    if state:
        payload['appfwprofile_xmlsqlinjection_binding']['state'] = state

    if name:
        payload['appfwprofile_xmlsqlinjection_binding']['name'] = name

    if xmlsqlinjection:
        payload['appfwprofile_xmlsqlinjection_binding']['xmlsqlinjection'] = xmlsqlinjection

    if isregex_xmlsql:
        payload['appfwprofile_xmlsqlinjection_binding']['isregex_xmlsql'] = isregex_xmlsql

    if comment:
        payload['appfwprofile_xmlsqlinjection_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_xmlsqlinjection_binding', payload)

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


def add_appfwprofile_xmlvalidationurl_binding(state=None, xmlwsdl=None, xmlendpointcheck=None, name=None,
                                              xmlvalidateresponse=None, xmlvalidationurl=None, xmlresponseschema=None,
                                              xmlvalidatesoapenvelope=None, xmlrequestschema=None,
                                              xmladditionalsoapheaders=None, comment=None, save=False):
    '''
    Add a new appfwprofile_xmlvalidationurl_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    xmlwsdl(str): WSDL object for soap request validation.

    xmlendpointcheck(str): Modifies the behaviour of the Request URL validation w.r.t. the Service URL. If set to ABSOLUTE,
        the entire request URL is validated with the entire URL mentioned in Service of the associated WSDL. eg: Service
        URL: http://example.org/ExampleService, Request URL: http//example.com/ExampleService would FAIL the validation.
        If set to RELAIVE, only the non-hostname part of the request URL is validated against the non-hostname part of
        the Service URL. eg: Service URL: http://example.org/ExampleService, Request URL:
        http//example.com/ExampleService would PASS the validation. Possible values = ABSOLUTE, RELATIVE

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    xmlvalidateresponse(str): Validate response message. Possible values = ON, OFF

    xmlvalidationurl(str): XML Validation URL regular expression.

    xmlresponseschema(str): XML Schema object for response validation.

    xmlvalidatesoapenvelope(str): Validate SOAP Evelope only. Possible values = ON, OFF

    xmlrequestschema(str): XML Schema object for request validation .

    xmladditionalsoapheaders(str): Allow addtional soap headers. Possible values = ON, OFF

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_xmlvalidationurl_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_xmlvalidationurl_binding': {}}

    if state:
        payload['appfwprofile_xmlvalidationurl_binding']['state'] = state

    if xmlwsdl:
        payload['appfwprofile_xmlvalidationurl_binding']['xmlwsdl'] = xmlwsdl

    if xmlendpointcheck:
        payload['appfwprofile_xmlvalidationurl_binding']['xmlendpointcheck'] = xmlendpointcheck

    if name:
        payload['appfwprofile_xmlvalidationurl_binding']['name'] = name

    if xmlvalidateresponse:
        payload['appfwprofile_xmlvalidationurl_binding']['xmlvalidateresponse'] = xmlvalidateresponse

    if xmlvalidationurl:
        payload['appfwprofile_xmlvalidationurl_binding']['xmlvalidationurl'] = xmlvalidationurl

    if xmlresponseschema:
        payload['appfwprofile_xmlvalidationurl_binding']['xmlresponseschema'] = xmlresponseschema

    if xmlvalidatesoapenvelope:
        payload['appfwprofile_xmlvalidationurl_binding']['xmlvalidatesoapenvelope'] = xmlvalidatesoapenvelope

    if xmlrequestschema:
        payload['appfwprofile_xmlvalidationurl_binding']['xmlrequestschema'] = xmlrequestschema

    if xmladditionalsoapheaders:
        payload['appfwprofile_xmlvalidationurl_binding']['xmladditionalsoapheaders'] = xmladditionalsoapheaders

    if comment:
        payload['appfwprofile_xmlvalidationurl_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_xmlvalidationurl_binding', payload)

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


def add_appfwprofile_xmlwsiurl_binding(xmlwsichecks=None, name=None, xmlwsiurl=None, state=None, comment=None,
                                       save=False):
    '''
    Add a new appfwprofile_xmlwsiurl_binding to the running configuration.

    xmlwsichecks(str): Specify a comma separated list of relevant WS-I rule IDs. (R1140, R1141).

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    xmlwsiurl(str): XML WS-I URL regular expression length.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_xmlwsiurl_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_xmlwsiurl_binding': {}}

    if xmlwsichecks:
        payload['appfwprofile_xmlwsiurl_binding']['xmlwsichecks'] = xmlwsichecks

    if name:
        payload['appfwprofile_xmlwsiurl_binding']['name'] = name

    if xmlwsiurl:
        payload['appfwprofile_xmlwsiurl_binding']['xmlwsiurl'] = xmlwsiurl

    if state:
        payload['appfwprofile_xmlwsiurl_binding']['state'] = state

    if comment:
        payload['appfwprofile_xmlwsiurl_binding']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/appfwprofile_xmlwsiurl_binding', payload)

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


def add_appfwprofile_xmlxss_binding(state=None, name=None, as_scan_location_xmlxss=None, isregex_xmlxss=None,
                                    comment=None, xmlxss=None, save=False):
    '''
    Add a new appfwprofile_xmlxss_binding to the running configuration.

    state(str): Enabled. Possible values = ENABLED, DISABLED

    name(str): Name of the profile to which to bind an exemption or rule. Minimum length = 1

    as_scan_location_xmlxss(str): Location of XSS injection exception - XML Element or Attribute. Possible values = ELEMENT,
        ATTRIBUTE

    isregex_xmlxss(str): Is the XML XSS exempted field name a regular expression?. Possible values = REGEX, NOTREGEX

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    xmlxss(str): Exempt the specified URL from the XML cross-site scripting (XSS) check. An XML cross-site scripting
        exemption (relaxation) consists of the following items: * URL. URL to exempt, as a string or a PCRE-format
        regular expression. * ISREGEX flag. REGEX if URL is a regular expression, NOTREGEX if URL is a fixed string. *
        Location. ELEMENT if the attachment is located in an XML element, ATTRIBUTE if located in an XML attribute.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwprofile_xmlxss_binding <args>

    '''

    result = {}

    payload = {'appfwprofile_xmlxss_binding': {}}

    if state:
        payload['appfwprofile_xmlxss_binding']['state'] = state

    if name:
        payload['appfwprofile_xmlxss_binding']['name'] = name

    if as_scan_location_xmlxss:
        payload['appfwprofile_xmlxss_binding']['as_scan_location_xmlxss'] = as_scan_location_xmlxss

    if isregex_xmlxss:
        payload['appfwprofile_xmlxss_binding']['isregex_xmlxss'] = isregex_xmlxss

    if comment:
        payload['appfwprofile_xmlxss_binding']['comment'] = comment

    if xmlxss:
        payload['appfwprofile_xmlxss_binding']['xmlxss'] = xmlxss

    execution = __proxy__['citrixns.post']('config/appfwprofile_xmlxss_binding', payload)

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


def add_appfwxmlcontenttype(xmlcontenttypevalue=None, isregex=None, save=False):
    '''
    Add a new appfwxmlcontenttype to the running configuration.

    xmlcontenttypevalue(str): Content type to be classified as XML. Minimum length = 1

    isregex(str): Is field name a regular expression?. Default value: NOTREGEX Possible values = REGEX, NOTREGEX

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.add_appfwxmlcontenttype <args>

    '''

    result = {}

    payload = {'appfwxmlcontenttype': {}}

    if xmlcontenttypevalue:
        payload['appfwxmlcontenttype']['xmlcontenttypevalue'] = xmlcontenttypevalue

    if isregex:
        payload['appfwxmlcontenttype']['isregex'] = isregex

    execution = __proxy__['citrixns.post']('config/appfwxmlcontenttype', payload)

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


def get_appfwarchive():
    '''
    Show the running configuration for the appfwarchive config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwarchive

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwarchive'), 'appfwarchive')

    return response


def get_appfwconfidfield(fieldname=None, url=None, isregex=None, comment=None, state=None):
    '''
    Show the running configuration for the appfwconfidfield config key.

    fieldname(str): Filters results that only match the fieldname field.

    url(str): Filters results that only match the url field.

    isregex(str): Filters results that only match the isregex field.

    comment(str): Filters results that only match the comment field.

    state(str): Filters results that only match the state field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwconfidfield

    '''

    search_filter = []

    if fieldname:
        search_filter.append(['fieldname', fieldname])

    if url:
        search_filter.append(['url', url])

    if isregex:
        search_filter.append(['isregex', isregex])

    if comment:
        search_filter.append(['comment', comment])

    if state:
        search_filter.append(['state', state])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwconfidfield{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwconfidfield')

    return response


def get_appfwfieldtype(name=None, regex=None, priority=None, comment=None, nocharmaps=None):
    '''
    Show the running configuration for the appfwfieldtype config key.

    name(str): Filters results that only match the name field.

    regex(str): Filters results that only match the regex field.

    priority(int): Filters results that only match the priority field.

    comment(str): Filters results that only match the comment field.

    nocharmaps(bool): Filters results that only match the nocharmaps field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwfieldtype

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if regex:
        search_filter.append(['regex', regex])

    if priority:
        search_filter.append(['priority', priority])

    if comment:
        search_filter.append(['comment', comment])

    if nocharmaps:
        search_filter.append(['nocharmaps', nocharmaps])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwfieldtype{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwfieldtype')

    return response


def get_appfwglobal_appfwpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None, state=None,
                                        gotopriorityexpression=None, ns_type=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the appfwglobal_appfwpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    state(str): Filters results that only match the state field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    ns_type(str): Filters results that only match the type field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwglobal_appfwpolicy_binding

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

    if ns_type:
        search_filter.append(['type', ns_type])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwglobal_appfwpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwglobal_appfwpolicy_binding')

    return response


def get_appfwglobal_auditnslogpolicy_binding(priority=None, policyname=None, labelname=None, state=None,
                                             gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the appfwglobal_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    state(str): Filters results that only match the state field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    ns_type(str): Filters results that only match the type field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwglobal_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

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
            __proxy__['citrixns.get']('config/appfwglobal_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwglobal_auditnslogpolicy_binding')

    return response


def get_appfwglobal_auditsyslogpolicy_binding(priority=None, policyname=None, labelname=None, state=None,
                                              gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the appfwglobal_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    state(str): Filters results that only match the state field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    ns_type(str): Filters results that only match the type field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwglobal_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

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
            __proxy__['citrixns.get']('config/appfwglobal_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwglobal_auditsyslogpolicy_binding')

    return response


def get_appfwglobal_binding():
    '''
    Show the running configuration for the appfwglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwglobal_binding'), 'appfwglobal_binding')

    return response


def get_appfwhtmlerrorpage():
    '''
    Show the running configuration for the appfwhtmlerrorpage config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwhtmlerrorpage

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwhtmlerrorpage'), 'appfwhtmlerrorpage')

    return response


def get_appfwjsoncontenttype(jsoncontenttypevalue=None, isregex=None):
    '''
    Show the running configuration for the appfwjsoncontenttype config key.

    jsoncontenttypevalue(str): Filters results that only match the jsoncontenttypevalue field.

    isregex(str): Filters results that only match the isregex field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwjsoncontenttype

    '''

    search_filter = []

    if jsoncontenttypevalue:
        search_filter.append(['jsoncontenttypevalue', jsoncontenttypevalue])

    if isregex:
        search_filter.append(['isregex', isregex])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwjsoncontenttype{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwjsoncontenttype')

    return response


def get_appfwlearningdata(profilename=None, starturl=None, cookieconsistency=None, fieldconsistency=None,
                          formactionurl_ffc=None, contenttype=None, crosssitescripting=None, formactionurl_xss=None,
                          as_scan_location_xss=None, as_value_type_xss=None, as_value_expr_xss=None, sqlinjection=None,
                          formactionurl_sql=None, as_scan_location_sql=None, as_value_type_sql=None,
                          as_value_expr_sql=None, fieldformat=None, formactionurl_ff=None, csrftag=None,
                          csrfformoriginurl=None, creditcardnumber=None, creditcardnumberurl=None, xmldoscheck=None,
                          xmlwsicheck=None, xmlattachmentcheck=None, totalxmlrequests=None, securitycheck=None,
                          target=None):
    '''
    Show the running configuration for the appfwlearningdata config key.

    profilename(str): Filters results that only match the profilename field.

    starturl(str): Filters results that only match the starturl field.

    cookieconsistency(str): Filters results that only match the cookieconsistency field.

    fieldconsistency(str): Filters results that only match the fieldconsistency field.

    formactionurl_ffc(str): Filters results that only match the formactionurl_ffc field.

    contenttype(str): Filters results that only match the contenttype field.

    crosssitescripting(str): Filters results that only match the crosssitescripting field.

    formactionurl_xss(str): Filters results that only match the formactionurl_xss field.

    as_scan_location_xss(str): Filters results that only match the as_scan_location_xss field.

    as_value_type_xss(str): Filters results that only match the as_value_type_xss field.

    as_value_expr_xss(str): Filters results that only match the as_value_expr_xss field.

    sqlinjection(str): Filters results that only match the sqlinjection field.

    formactionurl_sql(str): Filters results that only match the formactionurl_sql field.

    as_scan_location_sql(str): Filters results that only match the as_scan_location_sql field.

    as_value_type_sql(str): Filters results that only match the as_value_type_sql field.

    as_value_expr_sql(str): Filters results that only match the as_value_expr_sql field.

    fieldformat(str): Filters results that only match the fieldformat field.

    formactionurl_ff(str): Filters results that only match the formactionurl_ff field.

    csrftag(str): Filters results that only match the csrftag field.

    csrfformoriginurl(str): Filters results that only match the csrfformoriginurl field.

    creditcardnumber(str): Filters results that only match the creditcardnumber field.

    creditcardnumberurl(str): Filters results that only match the creditcardnumberurl field.

    xmldoscheck(str): Filters results that only match the xmldoscheck field.

    xmlwsicheck(str): Filters results that only match the xmlwsicheck field.

    xmlattachmentcheck(str): Filters results that only match the xmlattachmentcheck field.

    totalxmlrequests(bool): Filters results that only match the totalxmlrequests field.

    securitycheck(str): Filters results that only match the securitycheck field.

    target(str): Filters results that only match the target field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwlearningdata

    '''

    search_filter = []

    if profilename:
        search_filter.append(['profilename', profilename])

    if starturl:
        search_filter.append(['starturl', starturl])

    if cookieconsistency:
        search_filter.append(['cookieconsistency', cookieconsistency])

    if fieldconsistency:
        search_filter.append(['fieldconsistency', fieldconsistency])

    if formactionurl_ffc:
        search_filter.append(['formactionurl_ffc', formactionurl_ffc])

    if contenttype:
        search_filter.append(['contenttype', contenttype])

    if crosssitescripting:
        search_filter.append(['crosssitescripting', crosssitescripting])

    if formactionurl_xss:
        search_filter.append(['formactionurl_xss', formactionurl_xss])

    if as_scan_location_xss:
        search_filter.append(['as_scan_location_xss', as_scan_location_xss])

    if as_value_type_xss:
        search_filter.append(['as_value_type_xss', as_value_type_xss])

    if as_value_expr_xss:
        search_filter.append(['as_value_expr_xss', as_value_expr_xss])

    if sqlinjection:
        search_filter.append(['sqlinjection', sqlinjection])

    if formactionurl_sql:
        search_filter.append(['formactionurl_sql', formactionurl_sql])

    if as_scan_location_sql:
        search_filter.append(['as_scan_location_sql', as_scan_location_sql])

    if as_value_type_sql:
        search_filter.append(['as_value_type_sql', as_value_type_sql])

    if as_value_expr_sql:
        search_filter.append(['as_value_expr_sql', as_value_expr_sql])

    if fieldformat:
        search_filter.append(['fieldformat', fieldformat])

    if formactionurl_ff:
        search_filter.append(['formactionurl_ff', formactionurl_ff])

    if csrftag:
        search_filter.append(['csrftag', csrftag])

    if csrfformoriginurl:
        search_filter.append(['csrfformoriginurl', csrfformoriginurl])

    if creditcardnumber:
        search_filter.append(['creditcardnumber', creditcardnumber])

    if creditcardnumberurl:
        search_filter.append(['creditcardnumberurl', creditcardnumberurl])

    if xmldoscheck:
        search_filter.append(['xmldoscheck', xmldoscheck])

    if xmlwsicheck:
        search_filter.append(['xmlwsicheck', xmlwsicheck])

    if xmlattachmentcheck:
        search_filter.append(['xmlattachmentcheck', xmlattachmentcheck])

    if totalxmlrequests:
        search_filter.append(['totalxmlrequests', totalxmlrequests])

    if securitycheck:
        search_filter.append(['securitycheck', securitycheck])

    if target:
        search_filter.append(['target', target])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwlearningdata{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwlearningdata')

    return response


def get_appfwlearningsettings(profilename=None, starturlminthreshold=None, starturlpercentthreshold=None,
                              cookieconsistencyminthreshold=None, cookieconsistencypercentthreshold=None,
                              csrftagminthreshold=None, csrftagpercentthreshold=None, fieldconsistencyminthreshold=None,
                              fieldconsistencypercentthreshold=None, crosssitescriptingminthreshold=None,
                              crosssitescriptingpercentthreshold=None, sqlinjectionminthreshold=None,
                              sqlinjectionpercentthreshold=None, fieldformatminthreshold=None,
                              fieldformatpercentthreshold=None, creditcardnumberminthreshold=None,
                              creditcardnumberpercentthreshold=None, contenttypeminthreshold=None,
                              contenttypepercentthreshold=None, xmlwsiminthreshold=None, xmlwsipercentthreshold=None,
                              xmlattachmentminthreshold=None, xmlattachmentpercentthreshold=None):
    '''
    Show the running configuration for the appfwlearningsettings config key.

    profilename(str): Filters results that only match the profilename field.

    starturlminthreshold(int): Filters results that only match the starturlminthreshold field.

    starturlpercentthreshold(int): Filters results that only match the starturlpercentthreshold field.

    cookieconsistencyminthreshold(int): Filters results that only match the cookieconsistencyminthreshold field.

    cookieconsistencypercentthreshold(int): Filters results that only match the cookieconsistencypercentthreshold field.

    csrftagminthreshold(int): Filters results that only match the csrftagminthreshold field.

    csrftagpercentthreshold(int): Filters results that only match the csrftagpercentthreshold field.

    fieldconsistencyminthreshold(int): Filters results that only match the fieldconsistencyminthreshold field.

    fieldconsistencypercentthreshold(int): Filters results that only match the fieldconsistencypercentthreshold field.

    crosssitescriptingminthreshold(int): Filters results that only match the crosssitescriptingminthreshold field.

    crosssitescriptingpercentthreshold(int): Filters results that only match the crosssitescriptingpercentthreshold field.

    sqlinjectionminthreshold(int): Filters results that only match the sqlinjectionminthreshold field.

    sqlinjectionpercentthreshold(int): Filters results that only match the sqlinjectionpercentthreshold field.

    fieldformatminthreshold(int): Filters results that only match the fieldformatminthreshold field.

    fieldformatpercentthreshold(int): Filters results that only match the fieldformatpercentthreshold field.

    creditcardnumberminthreshold(int): Filters results that only match the creditcardnumberminthreshold field.

    creditcardnumberpercentthreshold(int): Filters results that only match the creditcardnumberpercentthreshold field.

    contenttypeminthreshold(int): Filters results that only match the contenttypeminthreshold field.

    contenttypepercentthreshold(int): Filters results that only match the contenttypepercentthreshold field.

    xmlwsiminthreshold(int): Filters results that only match the xmlwsiminthreshold field.

    xmlwsipercentthreshold(int): Filters results that only match the xmlwsipercentthreshold field.

    xmlattachmentminthreshold(int): Filters results that only match the xmlattachmentminthreshold field.

    xmlattachmentpercentthreshold(int): Filters results that only match the xmlattachmentpercentthreshold field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwlearningsettings

    '''

    search_filter = []

    if profilename:
        search_filter.append(['profilename', profilename])

    if starturlminthreshold:
        search_filter.append(['starturlminthreshold', starturlminthreshold])

    if starturlpercentthreshold:
        search_filter.append(['starturlpercentthreshold', starturlpercentthreshold])

    if cookieconsistencyminthreshold:
        search_filter.append(['cookieconsistencyminthreshold', cookieconsistencyminthreshold])

    if cookieconsistencypercentthreshold:
        search_filter.append(['cookieconsistencypercentthreshold', cookieconsistencypercentthreshold])

    if csrftagminthreshold:
        search_filter.append(['csrftagminthreshold', csrftagminthreshold])

    if csrftagpercentthreshold:
        search_filter.append(['csrftagpercentthreshold', csrftagpercentthreshold])

    if fieldconsistencyminthreshold:
        search_filter.append(['fieldconsistencyminthreshold', fieldconsistencyminthreshold])

    if fieldconsistencypercentthreshold:
        search_filter.append(['fieldconsistencypercentthreshold', fieldconsistencypercentthreshold])

    if crosssitescriptingminthreshold:
        search_filter.append(['crosssitescriptingminthreshold', crosssitescriptingminthreshold])

    if crosssitescriptingpercentthreshold:
        search_filter.append(['crosssitescriptingpercentthreshold', crosssitescriptingpercentthreshold])

    if sqlinjectionminthreshold:
        search_filter.append(['sqlinjectionminthreshold', sqlinjectionminthreshold])

    if sqlinjectionpercentthreshold:
        search_filter.append(['sqlinjectionpercentthreshold', sqlinjectionpercentthreshold])

    if fieldformatminthreshold:
        search_filter.append(['fieldformatminthreshold', fieldformatminthreshold])

    if fieldformatpercentthreshold:
        search_filter.append(['fieldformatpercentthreshold', fieldformatpercentthreshold])

    if creditcardnumberminthreshold:
        search_filter.append(['creditcardnumberminthreshold', creditcardnumberminthreshold])

    if creditcardnumberpercentthreshold:
        search_filter.append(['creditcardnumberpercentthreshold', creditcardnumberpercentthreshold])

    if contenttypeminthreshold:
        search_filter.append(['contenttypeminthreshold', contenttypeminthreshold])

    if contenttypepercentthreshold:
        search_filter.append(['contenttypepercentthreshold', contenttypepercentthreshold])

    if xmlwsiminthreshold:
        search_filter.append(['xmlwsiminthreshold', xmlwsiminthreshold])

    if xmlwsipercentthreshold:
        search_filter.append(['xmlwsipercentthreshold', xmlwsipercentthreshold])

    if xmlattachmentminthreshold:
        search_filter.append(['xmlattachmentminthreshold', xmlattachmentminthreshold])

    if xmlattachmentpercentthreshold:
        search_filter.append(['xmlattachmentpercentthreshold', xmlattachmentpercentthreshold])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwlearningsettings{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwlearningsettings')

    return response


def get_appfwpolicy(name=None, rule=None, profilename=None, comment=None, logaction=None, newname=None):
    '''
    Show the running configuration for the appfwpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    profilename(str): Filters results that only match the profilename field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if profilename:
        search_filter.append(['profilename', profilename])

    if comment:
        search_filter.append(['comment', comment])

    if logaction:
        search_filter.append(['logaction', logaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwpolicy')

    return response


def get_appfwpolicy_appfwglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the appfwpolicy_appfwglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicy_appfwglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwpolicy_appfwglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwpolicy_appfwglobal_binding')

    return response


def get_appfwpolicy_appfwpolicylabel_binding(name=None, boundto=None):
    '''
    Show the running configuration for the appfwpolicy_appfwpolicylabel_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicy_appfwpolicylabel_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwpolicy_appfwpolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwpolicy_appfwpolicylabel_binding')

    return response


def get_appfwpolicy_binding():
    '''
    Show the running configuration for the appfwpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwpolicy_binding'), 'appfwpolicy_binding')

    return response


def get_appfwpolicy_csvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the appfwpolicy_csvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicy_csvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwpolicy_csvserver_binding')

    return response


def get_appfwpolicy_lbvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the appfwpolicy_lbvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicy_lbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwpolicy_lbvserver_binding')

    return response


def get_appfwpolicylabel(labelname=None, policylabeltype=None, newname=None):
    '''
    Show the running configuration for the appfwpolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    policylabeltype(str): Filters results that only match the policylabeltype field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if policylabeltype:
        search_filter.append(['policylabeltype', policylabeltype])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwpolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwpolicylabel')

    return response


def get_appfwpolicylabel_appfwpolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                             gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the appfwpolicylabel_appfwpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicylabel_appfwpolicy_binding

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
            __proxy__['citrixns.get']('config/appfwpolicylabel_appfwpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwpolicylabel_appfwpolicy_binding')

    return response


def get_appfwpolicylabel_binding():
    '''
    Show the running configuration for the appfwpolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwpolicylabel_binding'), 'appfwpolicylabel_binding')

    return response


def get_appfwpolicylabel_policybinding_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                               gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the appfwpolicylabel_policybinding_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwpolicylabel_policybinding_binding

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
            __proxy__['citrixns.get']('config/appfwpolicylabel_policybinding_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwpolicylabel_policybinding_binding')

    return response


def get_appfwprofile(name=None, defaults=None, starturlaction=None, contenttypeaction=None, inspectcontenttypes=None,
                     starturlclosure=None, denyurlaction=None, refererheadercheck=None, cookieconsistencyaction=None,
                     cookietransforms=None, cookieencryption=None, cookieproxying=None, addcookieflags=None,
                     fieldconsistencyaction=None, csrftagaction=None, crosssitescriptingaction=None,
                     crosssitescriptingtransformunsafehtml=None, crosssitescriptingcheckcompleteurls=None,
                     sqlinjectionaction=None, sqlinjectiontransformspecialchars=None,
                     sqlinjectiononlycheckfieldswithsqlchars=None, sqlinjectiontype=None,
                     sqlinjectionchecksqlwildchars=None, fieldformataction=None, defaultfieldformattype=None,
                     defaultfieldformatminlength=None, defaultfieldformatmaxlength=None, bufferoverflowaction=None,
                     bufferoverflowmaxurllength=None, bufferoverflowmaxheaderlength=None,
                     bufferoverflowmaxcookielength=None, creditcardaction=None, creditcard=None,
                     creditcardmaxallowed=None, creditcardxout=None, dosecurecreditcardlogging=None, streaming=None,
                     trace=None, requestcontenttype=None, responsecontenttype=None, xmldosaction=None,
                     xmlformataction=None, xmlsqlinjectionaction=None, xmlsqlinjectiononlycheckfieldswithsqlchars=None,
                     xmlsqlinjectiontype=None, xmlsqlinjectionchecksqlwildchars=None, xmlsqlinjectionparsecomments=None,
                     xmlxssaction=None, xmlwsiaction=None, xmlattachmentaction=None, xmlvalidationaction=None,
                     xmlerrorobject=None, customsettings=None, signatures=None, xmlsoapfaultaction=None,
                     usehtmlerrorobject=None, errorurl=None, htmlerrorobject=None, logeverypolicyhit=None,
                     stripcomments=None, striphtmlcomments=None, stripxmlcomments=None,
                     exemptclosureurlsfromsecuritychecks=None, defaultcharset=None, postbodylimit=None,
                     fileuploadmaxnum=None, canonicalizehtmlresponse=None, enableformtagging=None,
                     sessionlessfieldconsistency=None, sessionlessurlclosure=None, semicolonfieldseparator=None,
                     excludefileuploadfromchecks=None, sqlinjectionparsecomments=None, invalidpercenthandling=None,
                     ns_type=None, checkrequestheaders=None, optimizepartialreqs=None, urldecoderequestcookies=None,
                     comment=None, percentdecoderecursively=None, multipleheaderaction=None, archivename=None):
    '''
    Show the running configuration for the appfwprofile config key.

    name(str): Filters results that only match the name field.

    defaults(str): Filters results that only match the defaults field.

    starturlaction(list(str)): Filters results that only match the starturlaction field.

    contenttypeaction(list(str)): Filters results that only match the contenttypeaction field.

    inspectcontenttypes(list(str)): Filters results that only match the inspectcontenttypes field.

    starturlclosure(str): Filters results that only match the starturlclosure field.

    denyurlaction(list(str)): Filters results that only match the denyurlaction field.

    refererheadercheck(str): Filters results that only match the refererheadercheck field.

    cookieconsistencyaction(list(str)): Filters results that only match the cookieconsistencyaction field.

    cookietransforms(str): Filters results that only match the cookietransforms field.

    cookieencryption(str): Filters results that only match the cookieencryption field.

    cookieproxying(str): Filters results that only match the cookieproxying field.

    addcookieflags(str): Filters results that only match the addcookieflags field.

    fieldconsistencyaction(list(str)): Filters results that only match the fieldconsistencyaction field.

    csrftagaction(list(str)): Filters results that only match the csrftagaction field.

    crosssitescriptingaction(list(str)): Filters results that only match the crosssitescriptingaction field.

    crosssitescriptingtransformunsafehtml(str): Filters results that only match the crosssitescriptingtransformunsafehtml
        field.

    crosssitescriptingcheckcompleteurls(str): Filters results that only match the crosssitescriptingcheckcompleteurls field.

    sqlinjectionaction(list(str)): Filters results that only match the sqlinjectionaction field.

    sqlinjectiontransformspecialchars(str): Filters results that only match the sqlinjectiontransformspecialchars field.

    sqlinjectiononlycheckfieldswithsqlchars(str): Filters results that only match the sqlinjectiononlycheckfieldswithsqlchars
        field.

    sqlinjectiontype(str): Filters results that only match the sqlinjectiontype field.

    sqlinjectionchecksqlwildchars(str): Filters results that only match the sqlinjectionchecksqlwildchars field.

    fieldformataction(list(str)): Filters results that only match the fieldformataction field.

    defaultfieldformattype(str): Filters results that only match the defaultfieldformattype field.

    defaultfieldformatminlength(int): Filters results that only match the defaultfieldformatminlength field.

    defaultfieldformatmaxlength(int): Filters results that only match the defaultfieldformatmaxlength field.

    bufferoverflowaction(list(str)): Filters results that only match the bufferoverflowaction field.

    bufferoverflowmaxurllength(int): Filters results that only match the bufferoverflowmaxurllength field.

    bufferoverflowmaxheaderlength(int): Filters results that only match the bufferoverflowmaxheaderlength field.

    bufferoverflowmaxcookielength(int): Filters results that only match the bufferoverflowmaxcookielength field.

    creditcardaction(list(str)): Filters results that only match the creditcardaction field.

    creditcard(list(str)): Filters results that only match the creditcard field.

    creditcardmaxallowed(int): Filters results that only match the creditcardmaxallowed field.

    creditcardxout(str): Filters results that only match the creditcardxout field.

    dosecurecreditcardlogging(str): Filters results that only match the dosecurecreditcardlogging field.

    streaming(str): Filters results that only match the streaming field.

    trace(str): Filters results that only match the trace field.

    requestcontenttype(str): Filters results that only match the requestcontenttype field.

    responsecontenttype(str): Filters results that only match the responsecontenttype field.

    xmldosaction(list(str)): Filters results that only match the xmldosaction field.

    xmlformataction(list(str)): Filters results that only match the xmlformataction field.

    xmlsqlinjectionaction(list(str)): Filters results that only match the xmlsqlinjectionaction field.

    xmlsqlinjectiononlycheckfieldswithsqlchars(str): Filters results that only match the
        xmlsqlinjectiononlycheckfieldswithsqlchars field.

    xmlsqlinjectiontype(str): Filters results that only match the xmlsqlinjectiontype field.

    xmlsqlinjectionchecksqlwildchars(str): Filters results that only match the xmlsqlinjectionchecksqlwildchars field.

    xmlsqlinjectionparsecomments(str): Filters results that only match the xmlsqlinjectionparsecomments field.

    xmlxssaction(list(str)): Filters results that only match the xmlxssaction field.

    xmlwsiaction(list(str)): Filters results that only match the xmlwsiaction field.

    xmlattachmentaction(list(str)): Filters results that only match the xmlattachmentaction field.

    xmlvalidationaction(list(str)): Filters results that only match the xmlvalidationaction field.

    xmlerrorobject(str): Filters results that only match the xmlerrorobject field.

    customsettings(str): Filters results that only match the customsettings field.

    signatures(str): Filters results that only match the signatures field.

    xmlsoapfaultaction(list(str)): Filters results that only match the xmlsoapfaultaction field.

    usehtmlerrorobject(str): Filters results that only match the usehtmlerrorobject field.

    errorurl(str): Filters results that only match the errorurl field.

    htmlerrorobject(str): Filters results that only match the htmlerrorobject field.

    logeverypolicyhit(str): Filters results that only match the logeverypolicyhit field.

    stripcomments(str): Filters results that only match the stripcomments field.

    striphtmlcomments(str): Filters results that only match the striphtmlcomments field.

    stripxmlcomments(str): Filters results that only match the stripxmlcomments field.

    exemptclosureurlsfromsecuritychecks(str): Filters results that only match the exemptclosureurlsfromsecuritychecks field.

    defaultcharset(str): Filters results that only match the defaultcharset field.

    postbodylimit(int): Filters results that only match the postbodylimit field.

    fileuploadmaxnum(int): Filters results that only match the fileuploadmaxnum field.

    canonicalizehtmlresponse(str): Filters results that only match the canonicalizehtmlresponse field.

    enableformtagging(str): Filters results that only match the enableformtagging field.

    sessionlessfieldconsistency(str): Filters results that only match the sessionlessfieldconsistency field.

    sessionlessurlclosure(str): Filters results that only match the sessionlessurlclosure field.

    semicolonfieldseparator(str): Filters results that only match the semicolonfieldseparator field.

    excludefileuploadfromchecks(str): Filters results that only match the excludefileuploadfromchecks field.

    sqlinjectionparsecomments(str): Filters results that only match the sqlinjectionparsecomments field.

    invalidpercenthandling(str): Filters results that only match the invalidpercenthandling field.

    ns_type(list(str)): Filters results that only match the type field.

    checkrequestheaders(str): Filters results that only match the checkrequestheaders field.

    optimizepartialreqs(str): Filters results that only match the optimizepartialreqs field.

    urldecoderequestcookies(str): Filters results that only match the urldecoderequestcookies field.

    comment(str): Filters results that only match the comment field.

    percentdecoderecursively(str): Filters results that only match the percentdecoderecursively field.

    multipleheaderaction(list(str)): Filters results that only match the multipleheaderaction field.

    archivename(str): Filters results that only match the archivename field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if defaults:
        search_filter.append(['defaults', defaults])

    if starturlaction:
        search_filter.append(['starturlaction', starturlaction])

    if contenttypeaction:
        search_filter.append(['contenttypeaction', contenttypeaction])

    if inspectcontenttypes:
        search_filter.append(['inspectcontenttypes', inspectcontenttypes])

    if starturlclosure:
        search_filter.append(['starturlclosure', starturlclosure])

    if denyurlaction:
        search_filter.append(['denyurlaction', denyurlaction])

    if refererheadercheck:
        search_filter.append(['refererheadercheck', refererheadercheck])

    if cookieconsistencyaction:
        search_filter.append(['cookieconsistencyaction', cookieconsistencyaction])

    if cookietransforms:
        search_filter.append(['cookietransforms', cookietransforms])

    if cookieencryption:
        search_filter.append(['cookieencryption', cookieencryption])

    if cookieproxying:
        search_filter.append(['cookieproxying', cookieproxying])

    if addcookieflags:
        search_filter.append(['addcookieflags', addcookieflags])

    if fieldconsistencyaction:
        search_filter.append(['fieldconsistencyaction', fieldconsistencyaction])

    if csrftagaction:
        search_filter.append(['csrftagaction', csrftagaction])

    if crosssitescriptingaction:
        search_filter.append(['crosssitescriptingaction', crosssitescriptingaction])

    if crosssitescriptingtransformunsafehtml:
        search_filter.append(['crosssitescriptingtransformunsafehtml', crosssitescriptingtransformunsafehtml])

    if crosssitescriptingcheckcompleteurls:
        search_filter.append(['crosssitescriptingcheckcompleteurls', crosssitescriptingcheckcompleteurls])

    if sqlinjectionaction:
        search_filter.append(['sqlinjectionaction', sqlinjectionaction])

    if sqlinjectiontransformspecialchars:
        search_filter.append(['sqlinjectiontransformspecialchars', sqlinjectiontransformspecialchars])

    if sqlinjectiononlycheckfieldswithsqlchars:
        search_filter.append(['sqlinjectiononlycheckfieldswithsqlchars', sqlinjectiononlycheckfieldswithsqlchars])

    if sqlinjectiontype:
        search_filter.append(['sqlinjectiontype', sqlinjectiontype])

    if sqlinjectionchecksqlwildchars:
        search_filter.append(['sqlinjectionchecksqlwildchars', sqlinjectionchecksqlwildchars])

    if fieldformataction:
        search_filter.append(['fieldformataction', fieldformataction])

    if defaultfieldformattype:
        search_filter.append(['defaultfieldformattype', defaultfieldformattype])

    if defaultfieldformatminlength:
        search_filter.append(['defaultfieldformatminlength', defaultfieldformatminlength])

    if defaultfieldformatmaxlength:
        search_filter.append(['defaultfieldformatmaxlength', defaultfieldformatmaxlength])

    if bufferoverflowaction:
        search_filter.append(['bufferoverflowaction', bufferoverflowaction])

    if bufferoverflowmaxurllength:
        search_filter.append(['bufferoverflowmaxurllength', bufferoverflowmaxurllength])

    if bufferoverflowmaxheaderlength:
        search_filter.append(['bufferoverflowmaxheaderlength', bufferoverflowmaxheaderlength])

    if bufferoverflowmaxcookielength:
        search_filter.append(['bufferoverflowmaxcookielength', bufferoverflowmaxcookielength])

    if creditcardaction:
        search_filter.append(['creditcardaction', creditcardaction])

    if creditcard:
        search_filter.append(['creditcard', creditcard])

    if creditcardmaxallowed:
        search_filter.append(['creditcardmaxallowed', creditcardmaxallowed])

    if creditcardxout:
        search_filter.append(['creditcardxout', creditcardxout])

    if dosecurecreditcardlogging:
        search_filter.append(['dosecurecreditcardlogging', dosecurecreditcardlogging])

    if streaming:
        search_filter.append(['streaming', streaming])

    if trace:
        search_filter.append(['trace', trace])

    if requestcontenttype:
        search_filter.append(['requestcontenttype', requestcontenttype])

    if responsecontenttype:
        search_filter.append(['responsecontenttype', responsecontenttype])

    if xmldosaction:
        search_filter.append(['xmldosaction', xmldosaction])

    if xmlformataction:
        search_filter.append(['xmlformataction', xmlformataction])

    if xmlsqlinjectionaction:
        search_filter.append(['xmlsqlinjectionaction', xmlsqlinjectionaction])

    if xmlsqlinjectiononlycheckfieldswithsqlchars:
        search_filter.append(['xmlsqlinjectiononlycheckfieldswithsqlchars', xmlsqlinjectiononlycheckfieldswithsqlchars])

    if xmlsqlinjectiontype:
        search_filter.append(['xmlsqlinjectiontype', xmlsqlinjectiontype])

    if xmlsqlinjectionchecksqlwildchars:
        search_filter.append(['xmlsqlinjectionchecksqlwildchars', xmlsqlinjectionchecksqlwildchars])

    if xmlsqlinjectionparsecomments:
        search_filter.append(['xmlsqlinjectionparsecomments', xmlsqlinjectionparsecomments])

    if xmlxssaction:
        search_filter.append(['xmlxssaction', xmlxssaction])

    if xmlwsiaction:
        search_filter.append(['xmlwsiaction', xmlwsiaction])

    if xmlattachmentaction:
        search_filter.append(['xmlattachmentaction', xmlattachmentaction])

    if xmlvalidationaction:
        search_filter.append(['xmlvalidationaction', xmlvalidationaction])

    if xmlerrorobject:
        search_filter.append(['xmlerrorobject', xmlerrorobject])

    if customsettings:
        search_filter.append(['customsettings', customsettings])

    if signatures:
        search_filter.append(['signatures', signatures])

    if xmlsoapfaultaction:
        search_filter.append(['xmlsoapfaultaction', xmlsoapfaultaction])

    if usehtmlerrorobject:
        search_filter.append(['usehtmlerrorobject', usehtmlerrorobject])

    if errorurl:
        search_filter.append(['errorurl', errorurl])

    if htmlerrorobject:
        search_filter.append(['htmlerrorobject', htmlerrorobject])

    if logeverypolicyhit:
        search_filter.append(['logeverypolicyhit', logeverypolicyhit])

    if stripcomments:
        search_filter.append(['stripcomments', stripcomments])

    if striphtmlcomments:
        search_filter.append(['striphtmlcomments', striphtmlcomments])

    if stripxmlcomments:
        search_filter.append(['stripxmlcomments', stripxmlcomments])

    if exemptclosureurlsfromsecuritychecks:
        search_filter.append(['exemptclosureurlsfromsecuritychecks', exemptclosureurlsfromsecuritychecks])

    if defaultcharset:
        search_filter.append(['defaultcharset', defaultcharset])

    if postbodylimit:
        search_filter.append(['postbodylimit', postbodylimit])

    if fileuploadmaxnum:
        search_filter.append(['fileuploadmaxnum', fileuploadmaxnum])

    if canonicalizehtmlresponse:
        search_filter.append(['canonicalizehtmlresponse', canonicalizehtmlresponse])

    if enableformtagging:
        search_filter.append(['enableformtagging', enableformtagging])

    if sessionlessfieldconsistency:
        search_filter.append(['sessionlessfieldconsistency', sessionlessfieldconsistency])

    if sessionlessurlclosure:
        search_filter.append(['sessionlessurlclosure', sessionlessurlclosure])

    if semicolonfieldseparator:
        search_filter.append(['semicolonfieldseparator', semicolonfieldseparator])

    if excludefileuploadfromchecks:
        search_filter.append(['excludefileuploadfromchecks', excludefileuploadfromchecks])

    if sqlinjectionparsecomments:
        search_filter.append(['sqlinjectionparsecomments', sqlinjectionparsecomments])

    if invalidpercenthandling:
        search_filter.append(['invalidpercenthandling', invalidpercenthandling])

    if ns_type:
        search_filter.append(['type', ns_type])

    if checkrequestheaders:
        search_filter.append(['checkrequestheaders', checkrequestheaders])

    if optimizepartialreqs:
        search_filter.append(['optimizepartialreqs', optimizepartialreqs])

    if urldecoderequestcookies:
        search_filter.append(['urldecoderequestcookies', urldecoderequestcookies])

    if comment:
        search_filter.append(['comment', comment])

    if percentdecoderecursively:
        search_filter.append(['percentdecoderecursively', percentdecoderecursively])

    if multipleheaderaction:
        search_filter.append(['multipleheaderaction', multipleheaderaction])

    if archivename:
        search_filter.append(['archivename', archivename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile')

    return response


def get_appfwprofile_binding():
    '''
    Show the running configuration for the appfwprofile_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_binding'), 'appfwprofile_binding')

    return response


def get_appfwprofile_contenttype_binding(state=None, name=None, contenttype=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_contenttype_binding config key.

    state(str): Filters results that only match the state field.

    name(str): Filters results that only match the name field.

    contenttype(str): Filters results that only match the contenttype field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_contenttype_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if name:
        search_filter.append(['name', name])

    if contenttype:
        search_filter.append(['contenttype', contenttype])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_contenttype_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_contenttype_binding')

    return response


def get_appfwprofile_cookieconsistency_binding(state=None, name=None, isregex=None, cookieconsistency=None,
                                               comment=None):
    '''
    Show the running configuration for the appfwprofile_cookieconsistency_binding config key.

    state(str): Filters results that only match the state field.

    name(str): Filters results that only match the name field.

    isregex(str): Filters results that only match the isregex field.

    cookieconsistency(str): Filters results that only match the cookieconsistency field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_cookieconsistency_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if name:
        search_filter.append(['name', name])

    if isregex:
        search_filter.append(['isregex', isregex])

    if cookieconsistency:
        search_filter.append(['cookieconsistency', cookieconsistency])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_cookieconsistency_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_cookieconsistency_binding')

    return response


def get_appfwprofile_creditcardnumber_binding(creditcardnumberurl=None, state=None, name=None, creditcardnumber=None,
                                              comment=None):
    '''
    Show the running configuration for the appfwprofile_creditcardnumber_binding config key.

    creditcardnumberurl(str): Filters results that only match the creditcardnumberurl field.

    state(str): Filters results that only match the state field.

    name(str): Filters results that only match the name field.

    creditcardnumber(str): Filters results that only match the creditcardnumber field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_creditcardnumber_binding

    '''

    search_filter = []

    if creditcardnumberurl:
        search_filter.append(['creditcardnumberurl', creditcardnumberurl])

    if state:
        search_filter.append(['state', state])

    if name:
        search_filter.append(['name', name])

    if creditcardnumber:
        search_filter.append(['creditcardnumber', creditcardnumber])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_creditcardnumber_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_creditcardnumber_binding')

    return response


def get_appfwprofile_crosssitescripting_binding(crosssitescripting=None, name=None, isregex_xss=None, state=None,
                                                comment=None, formactionurl_xss=None, as_value_expr_xss=None,
                                                as_scan_location_xss=None, as_value_type_xss=None,
                                                isvalueregex_xss=None):
    '''
    Show the running configuration for the appfwprofile_crosssitescripting_binding config key.

    crosssitescripting(str): Filters results that only match the crosssitescripting field.

    name(str): Filters results that only match the name field.

    isregex_xss(str): Filters results that only match the isregex_xss field.

    state(str): Filters results that only match the state field.

    comment(str): Filters results that only match the comment field.

    formactionurl_xss(str): Filters results that only match the formactionurl_xss field.

    as_value_expr_xss(str): Filters results that only match the as_value_expr_xss field.

    as_scan_location_xss(str): Filters results that only match the as_scan_location_xss field.

    as_value_type_xss(str): Filters results that only match the as_value_type_xss field.

    isvalueregex_xss(str): Filters results that only match the isvalueregex_xss field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_crosssitescripting_binding

    '''

    search_filter = []

    if crosssitescripting:
        search_filter.append(['crosssitescripting', crosssitescripting])

    if name:
        search_filter.append(['name', name])

    if isregex_xss:
        search_filter.append(['isregex_xss', isregex_xss])

    if state:
        search_filter.append(['state', state])

    if comment:
        search_filter.append(['comment', comment])

    if formactionurl_xss:
        search_filter.append(['formactionurl_xss', formactionurl_xss])

    if as_value_expr_xss:
        search_filter.append(['as_value_expr_xss', as_value_expr_xss])

    if as_scan_location_xss:
        search_filter.append(['as_scan_location_xss', as_scan_location_xss])

    if as_value_type_xss:
        search_filter.append(['as_value_type_xss', as_value_type_xss])

    if isvalueregex_xss:
        search_filter.append(['isvalueregex_xss', isvalueregex_xss])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_crosssitescripting_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_crosssitescripting_binding')

    return response


def get_appfwprofile_csrftag_binding(state=None, name=None, csrftag=None, csrfformactionurl=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_csrftag_binding config key.

    state(str): Filters results that only match the state field.

    name(str): Filters results that only match the name field.

    csrftag(str): Filters results that only match the csrftag field.

    csrfformactionurl(str): Filters results that only match the csrfformactionurl field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_csrftag_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if name:
        search_filter.append(['name', name])

    if csrftag:
        search_filter.append(['csrftag', csrftag])

    if csrfformactionurl:
        search_filter.append(['csrfformactionurl', csrfformactionurl])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_csrftag_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_csrftag_binding')

    return response


def get_appfwprofile_denyurl_binding(state=None, denyurl=None, name=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_denyurl_binding config key.

    state(str): Filters results that only match the state field.

    denyurl(str): Filters results that only match the denyurl field.

    name(str): Filters results that only match the name field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_denyurl_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if denyurl:
        search_filter.append(['denyurl', denyurl])

    if name:
        search_filter.append(['name', name])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_denyurl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_denyurl_binding')

    return response


def get_appfwprofile_excluderescontenttype_binding(excluderescontenttype=None, name=None, state=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_excluderescontenttype_binding config key.

    excluderescontenttype(str): Filters results that only match the excluderescontenttype field.

    name(str): Filters results that only match the name field.

    state(str): Filters results that only match the state field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_excluderescontenttype_binding

    '''

    search_filter = []

    if excluderescontenttype:
        search_filter.append(['excluderescontenttype', excluderescontenttype])

    if name:
        search_filter.append(['name', name])

    if state:
        search_filter.append(['state', state])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_excluderescontenttype_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_excluderescontenttype_binding')

    return response


def get_appfwprofile_fieldconsistency_binding(fieldconsistency=None, state=None, name=None, isregex_ffc=None,
                                              formactionurl_ffc=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_fieldconsistency_binding config key.

    fieldconsistency(str): Filters results that only match the fieldconsistency field.

    state(str): Filters results that only match the state field.

    name(str): Filters results that only match the name field.

    isregex_ffc(str): Filters results that only match the isregex_ffc field.

    formactionurl_ffc(str): Filters results that only match the formactionurl_ffc field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_fieldconsistency_binding

    '''

    search_filter = []

    if fieldconsistency:
        search_filter.append(['fieldconsistency', fieldconsistency])

    if state:
        search_filter.append(['state', state])

    if name:
        search_filter.append(['name', name])

    if isregex_ffc:
        search_filter.append(['isregex_ffc', isregex_ffc])

    if formactionurl_ffc:
        search_filter.append(['formactionurl_ffc', formactionurl_ffc])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_fieldconsistency_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_fieldconsistency_binding')

    return response


def get_appfwprofile_fieldformat_binding(state=None, fieldformatmaxlength=None, isregex_ff=None, fieldtype=None,
                                         formactionurl_ff=None, name=None, fieldformatminlength=None, comment=None,
                                         fieldformat=None):
    '''
    Show the running configuration for the appfwprofile_fieldformat_binding config key.

    state(str): Filters results that only match the state field.

    fieldformatmaxlength(int): Filters results that only match the fieldformatmaxlength field.

    isregex_ff(str): Filters results that only match the isregex_ff field.

    fieldtype(str): Filters results that only match the fieldtype field.

    formactionurl_ff(str): Filters results that only match the formactionurl_ff field.

    name(str): Filters results that only match the name field.

    fieldformatminlength(int): Filters results that only match the fieldformatminlength field.

    comment(str): Filters results that only match the comment field.

    fieldformat(str): Filters results that only match the fieldformat field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_fieldformat_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if fieldformatmaxlength:
        search_filter.append(['fieldformatmaxlength', fieldformatmaxlength])

    if isregex_ff:
        search_filter.append(['isregex_ff', isregex_ff])

    if fieldtype:
        search_filter.append(['fieldtype', fieldtype])

    if formactionurl_ff:
        search_filter.append(['formactionurl_ff', formactionurl_ff])

    if name:
        search_filter.append(['name', name])

    if fieldformatminlength:
        search_filter.append(['fieldformatminlength', fieldformatminlength])

    if comment:
        search_filter.append(['comment', comment])

    if fieldformat:
        search_filter.append(['fieldformat', fieldformat])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_fieldformat_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_fieldformat_binding')

    return response


def get_appfwprofile_safeobject_binding(maxmatchlength=None, state=None, expression=None, name=None, safeobject=None,
                                        comment=None, action=None):
    '''
    Show the running configuration for the appfwprofile_safeobject_binding config key.

    maxmatchlength(int): Filters results that only match the maxmatchlength field.

    state(str): Filters results that only match the state field.

    expression(str): Filters results that only match the expression field.

    name(str): Filters results that only match the name field.

    safeobject(str): Filters results that only match the safeobject field.

    comment(str): Filters results that only match the comment field.

    action(list(str)): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_safeobject_binding

    '''

    search_filter = []

    if maxmatchlength:
        search_filter.append(['maxmatchlength', maxmatchlength])

    if state:
        search_filter.append(['state', state])

    if expression:
        search_filter.append(['expression', expression])

    if name:
        search_filter.append(['name', name])

    if safeobject:
        search_filter.append(['safeobject', safeobject])

    if comment:
        search_filter.append(['comment', comment])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_safeobject_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_safeobject_binding')

    return response


def get_appfwprofile_sqlinjection_binding(as_value_expr_sql=None, state=None, formactionurl_sql=None, name=None,
                                          isregex_sql=None, isvalueregex_sql=None, as_scan_location_sql=None,
                                          sqlinjection=None, as_value_type_sql=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_sqlinjection_binding config key.

    as_value_expr_sql(str): Filters results that only match the as_value_expr_sql field.

    state(str): Filters results that only match the state field.

    formactionurl_sql(str): Filters results that only match the formactionurl_sql field.

    name(str): Filters results that only match the name field.

    isregex_sql(str): Filters results that only match the isregex_sql field.

    isvalueregex_sql(str): Filters results that only match the isvalueregex_sql field.

    as_scan_location_sql(str): Filters results that only match the as_scan_location_sql field.

    sqlinjection(str): Filters results that only match the sqlinjection field.

    as_value_type_sql(str): Filters results that only match the as_value_type_sql field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_sqlinjection_binding

    '''

    search_filter = []

    if as_value_expr_sql:
        search_filter.append(['as_value_expr_sql', as_value_expr_sql])

    if state:
        search_filter.append(['state', state])

    if formactionurl_sql:
        search_filter.append(['formactionurl_sql', formactionurl_sql])

    if name:
        search_filter.append(['name', name])

    if isregex_sql:
        search_filter.append(['isregex_sql', isregex_sql])

    if isvalueregex_sql:
        search_filter.append(['isvalueregex_sql', isvalueregex_sql])

    if as_scan_location_sql:
        search_filter.append(['as_scan_location_sql', as_scan_location_sql])

    if sqlinjection:
        search_filter.append(['sqlinjection', sqlinjection])

    if as_value_type_sql:
        search_filter.append(['as_value_type_sql', as_value_type_sql])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_sqlinjection_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_sqlinjection_binding')

    return response


def get_appfwprofile_starturl_binding(state=None, name=None, starturl=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_starturl_binding config key.

    state(str): Filters results that only match the state field.

    name(str): Filters results that only match the name field.

    starturl(str): Filters results that only match the starturl field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_starturl_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if name:
        search_filter.append(['name', name])

    if starturl:
        search_filter.append(['starturl', starturl])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_starturl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_starturl_binding')

    return response


def get_appfwprofile_trustedlearningclients_binding(state=None, trustedlearningclients=None, name=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_trustedlearningclients_binding config key.

    state(str): Filters results that only match the state field.

    trustedlearningclients(str): Filters results that only match the trustedlearningclients field.

    name(str): Filters results that only match the name field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_trustedlearningclients_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if trustedlearningclients:
        search_filter.append(['trustedlearningclients', trustedlearningclients])

    if name:
        search_filter.append(['name', name])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_trustedlearningclients_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_trustedlearningclients_binding')

    return response


def get_appfwprofile_xmlattachmenturl_binding(xmlattachmenturl=None, name=None, xmlmaxattachmentsize=None,
                                              xmlmaxattachmentsizecheck=None, state=None,
                                              xmlattachmentcontenttypecheck=None, comment=None,
                                              xmlattachmentcontenttype=None):
    '''
    Show the running configuration for the appfwprofile_xmlattachmenturl_binding config key.

    xmlattachmenturl(str): Filters results that only match the xmlattachmenturl field.

    name(str): Filters results that only match the name field.

    xmlmaxattachmentsize(int): Filters results that only match the xmlmaxattachmentsize field.

    xmlmaxattachmentsizecheck(str): Filters results that only match the xmlmaxattachmentsizecheck field.

    state(str): Filters results that only match the state field.

    xmlattachmentcontenttypecheck(str): Filters results that only match the xmlattachmentcontenttypecheck field.

    comment(str): Filters results that only match the comment field.

    xmlattachmentcontenttype(str): Filters results that only match the xmlattachmentcontenttype field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_xmlattachmenturl_binding

    '''

    search_filter = []

    if xmlattachmenturl:
        search_filter.append(['xmlattachmenturl', xmlattachmenturl])

    if name:
        search_filter.append(['name', name])

    if xmlmaxattachmentsize:
        search_filter.append(['xmlmaxattachmentsize', xmlmaxattachmentsize])

    if xmlmaxattachmentsizecheck:
        search_filter.append(['xmlmaxattachmentsizecheck', xmlmaxattachmentsizecheck])

    if state:
        search_filter.append(['state', state])

    if xmlattachmentcontenttypecheck:
        search_filter.append(['xmlattachmentcontenttypecheck', xmlattachmentcontenttypecheck])

    if comment:
        search_filter.append(['comment', comment])

    if xmlattachmentcontenttype:
        search_filter.append(['xmlattachmentcontenttype', xmlattachmentcontenttype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_xmlattachmenturl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_xmlattachmenturl_binding')

    return response


def get_appfwprofile_xmldosurl_binding(xmlmaxelementdepthcheck=None, xmlmaxfilesize=None, xmlmaxnamespaceurilength=None,
                                       xmldosurl=None, state=None, xmlsoaparraycheck=None,
                                       xmlmaxelementnamelengthcheck=None, xmlmaxelementscheck=None,
                                       xmlmaxentityexpansions=None, xmlmaxattributes=None, xmlmaxfilesizecheck=None,
                                       xmlmaxchardatalength=None, xmlmaxnamespacescheck=None, xmlmaxnamespaces=None,
                                       xmlmaxattributenamelengthcheck=None, xmlblockdtd=None,
                                       xmlmaxattributevaluelength=None, xmlmaxelementdepth=None,
                                       xmlmaxelementnamelength=None, name=None, xmlblockpi=None,
                                       xmlmaxelementchildrencheck=None, xmlmaxelements=None,
                                       xmlmaxentityexpansionscheck=None, xmlmaxnamespaceurilengthcheck=None,
                                       xmlmaxentityexpansiondepthcheck=None, xmlmaxattributevaluelengthcheck=None,
                                       xmlmaxsoaparraysize=None, xmlmaxentityexpansiondepth=None, xmlmaxnodescheck=None,
                                       xmlmaxattributenamelength=None, xmlmaxchardatalengthcheck=None,
                                       xmlminfilesizecheck=None, xmlmaxelementchildren=None, xmlminfilesize=None,
                                       xmlmaxnodes=None, comment=None, xmlmaxattributescheck=None,
                                       xmlmaxsoaparrayrank=None, xmlblockexternalentities=None):
    '''
    Show the running configuration for the appfwprofile_xmldosurl_binding config key.

    xmlmaxelementdepthcheck(str): Filters results that only match the xmlmaxelementdepthcheck field.

    xmlmaxfilesize(int): Filters results that only match the xmlmaxfilesize field.

    xmlmaxnamespaceurilength(int): Filters results that only match the xmlmaxnamespaceurilength field.

    xmldosurl(str): Filters results that only match the xmldosurl field.

    state(str): Filters results that only match the state field.

    xmlsoaparraycheck(str): Filters results that only match the xmlsoaparraycheck field.

    xmlmaxelementnamelengthcheck(str): Filters results that only match the xmlmaxelementnamelengthcheck field.

    xmlmaxelementscheck(str): Filters results that only match the xmlmaxelementscheck field.

    xmlmaxentityexpansions(int): Filters results that only match the xmlmaxentityexpansions field.

    xmlmaxattributes(int): Filters results that only match the xmlmaxattributes field.

    xmlmaxfilesizecheck(str): Filters results that only match the xmlmaxfilesizecheck field.

    xmlmaxchardatalength(int): Filters results that only match the xmlmaxchardatalength field.

    xmlmaxnamespacescheck(str): Filters results that only match the xmlmaxnamespacescheck field.

    xmlmaxnamespaces(int): Filters results that only match the xmlmaxnamespaces field.

    xmlmaxattributenamelengthcheck(str): Filters results that only match the xmlmaxattributenamelengthcheck field.

    xmlblockdtd(str): Filters results that only match the xmlblockdtd field.

    xmlmaxattributevaluelength(int): Filters results that only match the xmlmaxattributevaluelength field.

    xmlmaxelementdepth(int): Filters results that only match the xmlmaxelementdepth field.

    xmlmaxelementnamelength(int): Filters results that only match the xmlmaxelementnamelength field.

    name(str): Filters results that only match the name field.

    xmlblockpi(str): Filters results that only match the xmlblockpi field.

    xmlmaxelementchildrencheck(str): Filters results that only match the xmlmaxelementchildrencheck field.

    xmlmaxelements(int): Filters results that only match the xmlmaxelements field.

    xmlmaxentityexpansionscheck(str): Filters results that only match the xmlmaxentityexpansionscheck field.

    xmlmaxnamespaceurilengthcheck(str): Filters results that only match the xmlmaxnamespaceurilengthcheck field.

    xmlmaxentityexpansiondepthcheck(str): Filters results that only match the xmlmaxentityexpansiondepthcheck field.

    xmlmaxattributevaluelengthcheck(str): Filters results that only match the xmlmaxattributevaluelengthcheck field.

    xmlmaxsoaparraysize(int): Filters results that only match the xmlmaxsoaparraysize field.

    xmlmaxentityexpansiondepth(int): Filters results that only match the xmlmaxentityexpansiondepth field.

    xmlmaxnodescheck(str): Filters results that only match the xmlmaxnodescheck field.

    xmlmaxattributenamelength(int): Filters results that only match the xmlmaxattributenamelength field.

    xmlmaxchardatalengthcheck(str): Filters results that only match the xmlmaxchardatalengthcheck field.

    xmlminfilesizecheck(str): Filters results that only match the xmlminfilesizecheck field.

    xmlmaxelementchildren(int): Filters results that only match the xmlmaxelementchildren field.

    xmlminfilesize(int): Filters results that only match the xmlminfilesize field.

    xmlmaxnodes(int): Filters results that only match the xmlmaxnodes field.

    comment(str): Filters results that only match the comment field.

    xmlmaxattributescheck(str): Filters results that only match the xmlmaxattributescheck field.

    xmlmaxsoaparrayrank(int): Filters results that only match the xmlmaxsoaparrayrank field.

    xmlblockexternalentities(str): Filters results that only match the xmlblockexternalentities field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_xmldosurl_binding

    '''

    search_filter = []

    if xmlmaxelementdepthcheck:
        search_filter.append(['xmlmaxelementdepthcheck', xmlmaxelementdepthcheck])

    if xmlmaxfilesize:
        search_filter.append(['xmlmaxfilesize', xmlmaxfilesize])

    if xmlmaxnamespaceurilength:
        search_filter.append(['xmlmaxnamespaceurilength', xmlmaxnamespaceurilength])

    if xmldosurl:
        search_filter.append(['xmldosurl', xmldosurl])

    if state:
        search_filter.append(['state', state])

    if xmlsoaparraycheck:
        search_filter.append(['xmlsoaparraycheck', xmlsoaparraycheck])

    if xmlmaxelementnamelengthcheck:
        search_filter.append(['xmlmaxelementnamelengthcheck', xmlmaxelementnamelengthcheck])

    if xmlmaxelementscheck:
        search_filter.append(['xmlmaxelementscheck', xmlmaxelementscheck])

    if xmlmaxentityexpansions:
        search_filter.append(['xmlmaxentityexpansions', xmlmaxentityexpansions])

    if xmlmaxattributes:
        search_filter.append(['xmlmaxattributes', xmlmaxattributes])

    if xmlmaxfilesizecheck:
        search_filter.append(['xmlmaxfilesizecheck', xmlmaxfilesizecheck])

    if xmlmaxchardatalength:
        search_filter.append(['xmlmaxchardatalength', xmlmaxchardatalength])

    if xmlmaxnamespacescheck:
        search_filter.append(['xmlmaxnamespacescheck', xmlmaxnamespacescheck])

    if xmlmaxnamespaces:
        search_filter.append(['xmlmaxnamespaces', xmlmaxnamespaces])

    if xmlmaxattributenamelengthcheck:
        search_filter.append(['xmlmaxattributenamelengthcheck', xmlmaxattributenamelengthcheck])

    if xmlblockdtd:
        search_filter.append(['xmlblockdtd', xmlblockdtd])

    if xmlmaxattributevaluelength:
        search_filter.append(['xmlmaxattributevaluelength', xmlmaxattributevaluelength])

    if xmlmaxelementdepth:
        search_filter.append(['xmlmaxelementdepth', xmlmaxelementdepth])

    if xmlmaxelementnamelength:
        search_filter.append(['xmlmaxelementnamelength', xmlmaxelementnamelength])

    if name:
        search_filter.append(['name', name])

    if xmlblockpi:
        search_filter.append(['xmlblockpi', xmlblockpi])

    if xmlmaxelementchildrencheck:
        search_filter.append(['xmlmaxelementchildrencheck', xmlmaxelementchildrencheck])

    if xmlmaxelements:
        search_filter.append(['xmlmaxelements', xmlmaxelements])

    if xmlmaxentityexpansionscheck:
        search_filter.append(['xmlmaxentityexpansionscheck', xmlmaxentityexpansionscheck])

    if xmlmaxnamespaceurilengthcheck:
        search_filter.append(['xmlmaxnamespaceurilengthcheck', xmlmaxnamespaceurilengthcheck])

    if xmlmaxentityexpansiondepthcheck:
        search_filter.append(['xmlmaxentityexpansiondepthcheck', xmlmaxentityexpansiondepthcheck])

    if xmlmaxattributevaluelengthcheck:
        search_filter.append(['xmlmaxattributevaluelengthcheck', xmlmaxattributevaluelengthcheck])

    if xmlmaxsoaparraysize:
        search_filter.append(['xmlmaxsoaparraysize', xmlmaxsoaparraysize])

    if xmlmaxentityexpansiondepth:
        search_filter.append(['xmlmaxentityexpansiondepth', xmlmaxentityexpansiondepth])

    if xmlmaxnodescheck:
        search_filter.append(['xmlmaxnodescheck', xmlmaxnodescheck])

    if xmlmaxattributenamelength:
        search_filter.append(['xmlmaxattributenamelength', xmlmaxattributenamelength])

    if xmlmaxchardatalengthcheck:
        search_filter.append(['xmlmaxchardatalengthcheck', xmlmaxchardatalengthcheck])

    if xmlminfilesizecheck:
        search_filter.append(['xmlminfilesizecheck', xmlminfilesizecheck])

    if xmlmaxelementchildren:
        search_filter.append(['xmlmaxelementchildren', xmlmaxelementchildren])

    if xmlminfilesize:
        search_filter.append(['xmlminfilesize', xmlminfilesize])

    if xmlmaxnodes:
        search_filter.append(['xmlmaxnodes', xmlmaxnodes])

    if comment:
        search_filter.append(['comment', comment])

    if xmlmaxattributescheck:
        search_filter.append(['xmlmaxattributescheck', xmlmaxattributescheck])

    if xmlmaxsoaparrayrank:
        search_filter.append(['xmlmaxsoaparrayrank', xmlmaxsoaparrayrank])

    if xmlblockexternalentities:
        search_filter.append(['xmlblockexternalentities', xmlblockexternalentities])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_xmldosurl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_xmldosurl_binding')

    return response


def get_appfwprofile_xmlsqlinjection_binding(as_scan_location_xmlsql=None, state=None, name=None, xmlsqlinjection=None,
                                             isregex_xmlsql=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_xmlsqlinjection_binding config key.

    as_scan_location_xmlsql(str): Filters results that only match the as_scan_location_xmlsql field.

    state(str): Filters results that only match the state field.

    name(str): Filters results that only match the name field.

    xmlsqlinjection(str): Filters results that only match the xmlsqlinjection field.

    isregex_xmlsql(str): Filters results that only match the isregex_xmlsql field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_xmlsqlinjection_binding

    '''

    search_filter = []

    if as_scan_location_xmlsql:
        search_filter.append(['as_scan_location_xmlsql', as_scan_location_xmlsql])

    if state:
        search_filter.append(['state', state])

    if name:
        search_filter.append(['name', name])

    if xmlsqlinjection:
        search_filter.append(['xmlsqlinjection', xmlsqlinjection])

    if isregex_xmlsql:
        search_filter.append(['isregex_xmlsql', isregex_xmlsql])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_xmlsqlinjection_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_xmlsqlinjection_binding')

    return response


def get_appfwprofile_xmlvalidationurl_binding(state=None, xmlwsdl=None, xmlendpointcheck=None, name=None,
                                              xmlvalidateresponse=None, xmlvalidationurl=None, xmlresponseschema=None,
                                              xmlvalidatesoapenvelope=None, xmlrequestschema=None,
                                              xmladditionalsoapheaders=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_xmlvalidationurl_binding config key.

    state(str): Filters results that only match the state field.

    xmlwsdl(str): Filters results that only match the xmlwsdl field.

    xmlendpointcheck(str): Filters results that only match the xmlendpointcheck field.

    name(str): Filters results that only match the name field.

    xmlvalidateresponse(str): Filters results that only match the xmlvalidateresponse field.

    xmlvalidationurl(str): Filters results that only match the xmlvalidationurl field.

    xmlresponseschema(str): Filters results that only match the xmlresponseschema field.

    xmlvalidatesoapenvelope(str): Filters results that only match the xmlvalidatesoapenvelope field.

    xmlrequestschema(str): Filters results that only match the xmlrequestschema field.

    xmladditionalsoapheaders(str): Filters results that only match the xmladditionalsoapheaders field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_xmlvalidationurl_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if xmlwsdl:
        search_filter.append(['xmlwsdl', xmlwsdl])

    if xmlendpointcheck:
        search_filter.append(['xmlendpointcheck', xmlendpointcheck])

    if name:
        search_filter.append(['name', name])

    if xmlvalidateresponse:
        search_filter.append(['xmlvalidateresponse', xmlvalidateresponse])

    if xmlvalidationurl:
        search_filter.append(['xmlvalidationurl', xmlvalidationurl])

    if xmlresponseschema:
        search_filter.append(['xmlresponseschema', xmlresponseschema])

    if xmlvalidatesoapenvelope:
        search_filter.append(['xmlvalidatesoapenvelope', xmlvalidatesoapenvelope])

    if xmlrequestschema:
        search_filter.append(['xmlrequestschema', xmlrequestschema])

    if xmladditionalsoapheaders:
        search_filter.append(['xmladditionalsoapheaders', xmladditionalsoapheaders])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_xmlvalidationurl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_xmlvalidationurl_binding')

    return response


def get_appfwprofile_xmlwsiurl_binding(xmlwsichecks=None, name=None, xmlwsiurl=None, state=None, comment=None):
    '''
    Show the running configuration for the appfwprofile_xmlwsiurl_binding config key.

    xmlwsichecks(str): Filters results that only match the xmlwsichecks field.

    name(str): Filters results that only match the name field.

    xmlwsiurl(str): Filters results that only match the xmlwsiurl field.

    state(str): Filters results that only match the state field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_xmlwsiurl_binding

    '''

    search_filter = []

    if xmlwsichecks:
        search_filter.append(['xmlwsichecks', xmlwsichecks])

    if name:
        search_filter.append(['name', name])

    if xmlwsiurl:
        search_filter.append(['xmlwsiurl', xmlwsiurl])

    if state:
        search_filter.append(['state', state])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_xmlwsiurl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_xmlwsiurl_binding')

    return response


def get_appfwprofile_xmlxss_binding(state=None, name=None, as_scan_location_xmlxss=None, isregex_xmlxss=None,
                                    comment=None, xmlxss=None):
    '''
    Show the running configuration for the appfwprofile_xmlxss_binding config key.

    state(str): Filters results that only match the state field.

    name(str): Filters results that only match the name field.

    as_scan_location_xmlxss(str): Filters results that only match the as_scan_location_xmlxss field.

    isregex_xmlxss(str): Filters results that only match the isregex_xmlxss field.

    comment(str): Filters results that only match the comment field.

    xmlxss(str): Filters results that only match the xmlxss field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwprofile_xmlxss_binding

    '''

    search_filter = []

    if state:
        search_filter.append(['state', state])

    if name:
        search_filter.append(['name', name])

    if as_scan_location_xmlxss:
        search_filter.append(['as_scan_location_xmlxss', as_scan_location_xmlxss])

    if isregex_xmlxss:
        search_filter.append(['isregex_xmlxss', isregex_xmlxss])

    if comment:
        search_filter.append(['comment', comment])

    if xmlxss:
        search_filter.append(['xmlxss', xmlxss])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwprofile_xmlxss_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwprofile_xmlxss_binding')

    return response


def get_appfwsettings():
    '''
    Show the running configuration for the appfwsettings config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwsettings

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwsettings'), 'appfwsettings')

    return response


def get_appfwsignatures():
    '''
    Show the running configuration for the appfwsignatures config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwsignatures

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwsignatures'), 'appfwsignatures')

    return response


def get_appfwtransactionrecords(nodeid=None):
    '''
    Show the running configuration for the appfwtransactionrecords config key.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwtransactionrecords

    '''

    search_filter = []

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwtransactionrecords{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwtransactionrecords')

    return response


def get_appfwwsdl():
    '''
    Show the running configuration for the appfwwsdl config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwwsdl

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwwsdl'), 'appfwwsdl')

    return response


def get_appfwxmlcontenttype(xmlcontenttypevalue=None, isregex=None):
    '''
    Show the running configuration for the appfwxmlcontenttype config key.

    xmlcontenttypevalue(str): Filters results that only match the xmlcontenttypevalue field.

    isregex(str): Filters results that only match the isregex field.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwxmlcontenttype

    '''

    search_filter = []

    if xmlcontenttypevalue:
        search_filter.append(['xmlcontenttypevalue', xmlcontenttypevalue])

    if isregex:
        search_filter.append(['isregex', isregex])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwxmlcontenttype{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appfwxmlcontenttype')

    return response


def get_appfwxmlerrorpage():
    '''
    Show the running configuration for the appfwxmlerrorpage config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwxmlerrorpage

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwxmlerrorpage'), 'appfwxmlerrorpage')

    return response


def get_appfwxmlschema():
    '''
    Show the running configuration for the appfwxmlschema config key.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.get_appfwxmlschema

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appfwxmlschema'), 'appfwxmlschema')

    return response


def unset_appfwconfidfield(fieldname=None, url=None, isregex=None, comment=None, state=None, save=False):
    '''
    Unsets values from the appfwconfidfield configuration key.

    fieldname(bool): Unsets the fieldname value.

    url(bool): Unsets the url value.

    isregex(bool): Unsets the isregex value.

    comment(bool): Unsets the comment value.

    state(bool): Unsets the state value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.unset_appfwconfidfield <args>

    '''

    result = {}

    payload = {'appfwconfidfield': {}}

    if fieldname:
        payload['appfwconfidfield']['fieldname'] = True

    if url:
        payload['appfwconfidfield']['url'] = True

    if isregex:
        payload['appfwconfidfield']['isregex'] = True

    if comment:
        payload['appfwconfidfield']['comment'] = True

    if state:
        payload['appfwconfidfield']['state'] = True

    execution = __proxy__['citrixns.post']('config/appfwconfidfield?action=unset', payload)

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


def unset_appfwlearningsettings(profilename=None, starturlminthreshold=None, starturlpercentthreshold=None,
                                cookieconsistencyminthreshold=None, cookieconsistencypercentthreshold=None,
                                csrftagminthreshold=None, csrftagpercentthreshold=None,
                                fieldconsistencyminthreshold=None, fieldconsistencypercentthreshold=None,
                                crosssitescriptingminthreshold=None, crosssitescriptingpercentthreshold=None,
                                sqlinjectionminthreshold=None, sqlinjectionpercentthreshold=None,
                                fieldformatminthreshold=None, fieldformatpercentthreshold=None,
                                creditcardnumberminthreshold=None, creditcardnumberpercentthreshold=None,
                                contenttypeminthreshold=None, contenttypepercentthreshold=None, xmlwsiminthreshold=None,
                                xmlwsipercentthreshold=None, xmlattachmentminthreshold=None,
                                xmlattachmentpercentthreshold=None, save=False):
    '''
    Unsets values from the appfwlearningsettings configuration key.

    profilename(bool): Unsets the profilename value.

    starturlminthreshold(bool): Unsets the starturlminthreshold value.

    starturlpercentthreshold(bool): Unsets the starturlpercentthreshold value.

    cookieconsistencyminthreshold(bool): Unsets the cookieconsistencyminthreshold value.

    cookieconsistencypercentthreshold(bool): Unsets the cookieconsistencypercentthreshold value.

    csrftagminthreshold(bool): Unsets the csrftagminthreshold value.

    csrftagpercentthreshold(bool): Unsets the csrftagpercentthreshold value.

    fieldconsistencyminthreshold(bool): Unsets the fieldconsistencyminthreshold value.

    fieldconsistencypercentthreshold(bool): Unsets the fieldconsistencypercentthreshold value.

    crosssitescriptingminthreshold(bool): Unsets the crosssitescriptingminthreshold value.

    crosssitescriptingpercentthreshold(bool): Unsets the crosssitescriptingpercentthreshold value.

    sqlinjectionminthreshold(bool): Unsets the sqlinjectionminthreshold value.

    sqlinjectionpercentthreshold(bool): Unsets the sqlinjectionpercentthreshold value.

    fieldformatminthreshold(bool): Unsets the fieldformatminthreshold value.

    fieldformatpercentthreshold(bool): Unsets the fieldformatpercentthreshold value.

    creditcardnumberminthreshold(bool): Unsets the creditcardnumberminthreshold value.

    creditcardnumberpercentthreshold(bool): Unsets the creditcardnumberpercentthreshold value.

    contenttypeminthreshold(bool): Unsets the contenttypeminthreshold value.

    contenttypepercentthreshold(bool): Unsets the contenttypepercentthreshold value.

    xmlwsiminthreshold(bool): Unsets the xmlwsiminthreshold value.

    xmlwsipercentthreshold(bool): Unsets the xmlwsipercentthreshold value.

    xmlattachmentminthreshold(bool): Unsets the xmlattachmentminthreshold value.

    xmlattachmentpercentthreshold(bool): Unsets the xmlattachmentpercentthreshold value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.unset_appfwlearningsettings <args>

    '''

    result = {}

    payload = {'appfwlearningsettings': {}}

    if profilename:
        payload['appfwlearningsettings']['profilename'] = True

    if starturlminthreshold:
        payload['appfwlearningsettings']['starturlminthreshold'] = True

    if starturlpercentthreshold:
        payload['appfwlearningsettings']['starturlpercentthreshold'] = True

    if cookieconsistencyminthreshold:
        payload['appfwlearningsettings']['cookieconsistencyminthreshold'] = True

    if cookieconsistencypercentthreshold:
        payload['appfwlearningsettings']['cookieconsistencypercentthreshold'] = True

    if csrftagminthreshold:
        payload['appfwlearningsettings']['csrftagminthreshold'] = True

    if csrftagpercentthreshold:
        payload['appfwlearningsettings']['csrftagpercentthreshold'] = True

    if fieldconsistencyminthreshold:
        payload['appfwlearningsettings']['fieldconsistencyminthreshold'] = True

    if fieldconsistencypercentthreshold:
        payload['appfwlearningsettings']['fieldconsistencypercentthreshold'] = True

    if crosssitescriptingminthreshold:
        payload['appfwlearningsettings']['crosssitescriptingminthreshold'] = True

    if crosssitescriptingpercentthreshold:
        payload['appfwlearningsettings']['crosssitescriptingpercentthreshold'] = True

    if sqlinjectionminthreshold:
        payload['appfwlearningsettings']['sqlinjectionminthreshold'] = True

    if sqlinjectionpercentthreshold:
        payload['appfwlearningsettings']['sqlinjectionpercentthreshold'] = True

    if fieldformatminthreshold:
        payload['appfwlearningsettings']['fieldformatminthreshold'] = True

    if fieldformatpercentthreshold:
        payload['appfwlearningsettings']['fieldformatpercentthreshold'] = True

    if creditcardnumberminthreshold:
        payload['appfwlearningsettings']['creditcardnumberminthreshold'] = True

    if creditcardnumberpercentthreshold:
        payload['appfwlearningsettings']['creditcardnumberpercentthreshold'] = True

    if contenttypeminthreshold:
        payload['appfwlearningsettings']['contenttypeminthreshold'] = True

    if contenttypepercentthreshold:
        payload['appfwlearningsettings']['contenttypepercentthreshold'] = True

    if xmlwsiminthreshold:
        payload['appfwlearningsettings']['xmlwsiminthreshold'] = True

    if xmlwsipercentthreshold:
        payload['appfwlearningsettings']['xmlwsipercentthreshold'] = True

    if xmlattachmentminthreshold:
        payload['appfwlearningsettings']['xmlattachmentminthreshold'] = True

    if xmlattachmentpercentthreshold:
        payload['appfwlearningsettings']['xmlattachmentpercentthreshold'] = True

    execution = __proxy__['citrixns.post']('config/appfwlearningsettings?action=unset', payload)

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


def unset_appfwpolicy(name=None, rule=None, profilename=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Unsets values from the appfwpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    profilename(bool): Unsets the profilename value.

    comment(bool): Unsets the comment value.

    logaction(bool): Unsets the logaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.unset_appfwpolicy <args>

    '''

    result = {}

    payload = {'appfwpolicy': {}}

    if name:
        payload['appfwpolicy']['name'] = True

    if rule:
        payload['appfwpolicy']['rule'] = True

    if profilename:
        payload['appfwpolicy']['profilename'] = True

    if comment:
        payload['appfwpolicy']['comment'] = True

    if logaction:
        payload['appfwpolicy']['logaction'] = True

    if newname:
        payload['appfwpolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/appfwpolicy?action=unset', payload)

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


def unset_appfwprofile(name=None, defaults=None, starturlaction=None, contenttypeaction=None, inspectcontenttypes=None,
                       starturlclosure=None, denyurlaction=None, refererheadercheck=None, cookieconsistencyaction=None,
                       cookietransforms=None, cookieencryption=None, cookieproxying=None, addcookieflags=None,
                       fieldconsistencyaction=None, csrftagaction=None, crosssitescriptingaction=None,
                       crosssitescriptingtransformunsafehtml=None, crosssitescriptingcheckcompleteurls=None,
                       sqlinjectionaction=None, sqlinjectiontransformspecialchars=None,
                       sqlinjectiononlycheckfieldswithsqlchars=None, sqlinjectiontype=None,
                       sqlinjectionchecksqlwildchars=None, fieldformataction=None, defaultfieldformattype=None,
                       defaultfieldformatminlength=None, defaultfieldformatmaxlength=None, bufferoverflowaction=None,
                       bufferoverflowmaxurllength=None, bufferoverflowmaxheaderlength=None,
                       bufferoverflowmaxcookielength=None, creditcardaction=None, creditcard=None,
                       creditcardmaxallowed=None, creditcardxout=None, dosecurecreditcardlogging=None, streaming=None,
                       trace=None, requestcontenttype=None, responsecontenttype=None, xmldosaction=None,
                       xmlformataction=None, xmlsqlinjectionaction=None, xmlsqlinjectiononlycheckfieldswithsqlchars=None,
                       xmlsqlinjectiontype=None, xmlsqlinjectionchecksqlwildchars=None,
                       xmlsqlinjectionparsecomments=None, xmlxssaction=None, xmlwsiaction=None, xmlattachmentaction=None,
                       xmlvalidationaction=None, xmlerrorobject=None, customsettings=None, signatures=None,
                       xmlsoapfaultaction=None, usehtmlerrorobject=None, errorurl=None, htmlerrorobject=None,
                       logeverypolicyhit=None, stripcomments=None, striphtmlcomments=None, stripxmlcomments=None,
                       exemptclosureurlsfromsecuritychecks=None, defaultcharset=None, postbodylimit=None,
                       fileuploadmaxnum=None, canonicalizehtmlresponse=None, enableformtagging=None,
                       sessionlessfieldconsistency=None, sessionlessurlclosure=None, semicolonfieldseparator=None,
                       excludefileuploadfromchecks=None, sqlinjectionparsecomments=None, invalidpercenthandling=None,
                       ns_type=None, checkrequestheaders=None, optimizepartialreqs=None, urldecoderequestcookies=None,
                       comment=None, percentdecoderecursively=None, multipleheaderaction=None, archivename=None,
                       save=False):
    '''
    Unsets values from the appfwprofile configuration key.

    name(bool): Unsets the name value.

    defaults(bool): Unsets the defaults value.

    starturlaction(bool): Unsets the starturlaction value.

    contenttypeaction(bool): Unsets the contenttypeaction value.

    inspectcontenttypes(bool): Unsets the inspectcontenttypes value.

    starturlclosure(bool): Unsets the starturlclosure value.

    denyurlaction(bool): Unsets the denyurlaction value.

    refererheadercheck(bool): Unsets the refererheadercheck value.

    cookieconsistencyaction(bool): Unsets the cookieconsistencyaction value.

    cookietransforms(bool): Unsets the cookietransforms value.

    cookieencryption(bool): Unsets the cookieencryption value.

    cookieproxying(bool): Unsets the cookieproxying value.

    addcookieflags(bool): Unsets the addcookieflags value.

    fieldconsistencyaction(bool): Unsets the fieldconsistencyaction value.

    csrftagaction(bool): Unsets the csrftagaction value.

    crosssitescriptingaction(bool): Unsets the crosssitescriptingaction value.

    crosssitescriptingtransformunsafehtml(bool): Unsets the crosssitescriptingtransformunsafehtml value.

    crosssitescriptingcheckcompleteurls(bool): Unsets the crosssitescriptingcheckcompleteurls value.

    sqlinjectionaction(bool): Unsets the sqlinjectionaction value.

    sqlinjectiontransformspecialchars(bool): Unsets the sqlinjectiontransformspecialchars value.

    sqlinjectiononlycheckfieldswithsqlchars(bool): Unsets the sqlinjectiononlycheckfieldswithsqlchars value.

    sqlinjectiontype(bool): Unsets the sqlinjectiontype value.

    sqlinjectionchecksqlwildchars(bool): Unsets the sqlinjectionchecksqlwildchars value.

    fieldformataction(bool): Unsets the fieldformataction value.

    defaultfieldformattype(bool): Unsets the defaultfieldformattype value.

    defaultfieldformatminlength(bool): Unsets the defaultfieldformatminlength value.

    defaultfieldformatmaxlength(bool): Unsets the defaultfieldformatmaxlength value.

    bufferoverflowaction(bool): Unsets the bufferoverflowaction value.

    bufferoverflowmaxurllength(bool): Unsets the bufferoverflowmaxurllength value.

    bufferoverflowmaxheaderlength(bool): Unsets the bufferoverflowmaxheaderlength value.

    bufferoverflowmaxcookielength(bool): Unsets the bufferoverflowmaxcookielength value.

    creditcardaction(bool): Unsets the creditcardaction value.

    creditcard(bool): Unsets the creditcard value.

    creditcardmaxallowed(bool): Unsets the creditcardmaxallowed value.

    creditcardxout(bool): Unsets the creditcardxout value.

    dosecurecreditcardlogging(bool): Unsets the dosecurecreditcardlogging value.

    streaming(bool): Unsets the streaming value.

    trace(bool): Unsets the trace value.

    requestcontenttype(bool): Unsets the requestcontenttype value.

    responsecontenttype(bool): Unsets the responsecontenttype value.

    xmldosaction(bool): Unsets the xmldosaction value.

    xmlformataction(bool): Unsets the xmlformataction value.

    xmlsqlinjectionaction(bool): Unsets the xmlsqlinjectionaction value.

    xmlsqlinjectiononlycheckfieldswithsqlchars(bool): Unsets the xmlsqlinjectiononlycheckfieldswithsqlchars value.

    xmlsqlinjectiontype(bool): Unsets the xmlsqlinjectiontype value.

    xmlsqlinjectionchecksqlwildchars(bool): Unsets the xmlsqlinjectionchecksqlwildchars value.

    xmlsqlinjectionparsecomments(bool): Unsets the xmlsqlinjectionparsecomments value.

    xmlxssaction(bool): Unsets the xmlxssaction value.

    xmlwsiaction(bool): Unsets the xmlwsiaction value.

    xmlattachmentaction(bool): Unsets the xmlattachmentaction value.

    xmlvalidationaction(bool): Unsets the xmlvalidationaction value.

    xmlerrorobject(bool): Unsets the xmlerrorobject value.

    customsettings(bool): Unsets the customsettings value.

    signatures(bool): Unsets the signatures value.

    xmlsoapfaultaction(bool): Unsets the xmlsoapfaultaction value.

    usehtmlerrorobject(bool): Unsets the usehtmlerrorobject value.

    errorurl(bool): Unsets the errorurl value.

    htmlerrorobject(bool): Unsets the htmlerrorobject value.

    logeverypolicyhit(bool): Unsets the logeverypolicyhit value.

    stripcomments(bool): Unsets the stripcomments value.

    striphtmlcomments(bool): Unsets the striphtmlcomments value.

    stripxmlcomments(bool): Unsets the stripxmlcomments value.

    exemptclosureurlsfromsecuritychecks(bool): Unsets the exemptclosureurlsfromsecuritychecks value.

    defaultcharset(bool): Unsets the defaultcharset value.

    postbodylimit(bool): Unsets the postbodylimit value.

    fileuploadmaxnum(bool): Unsets the fileuploadmaxnum value.

    canonicalizehtmlresponse(bool): Unsets the canonicalizehtmlresponse value.

    enableformtagging(bool): Unsets the enableformtagging value.

    sessionlessfieldconsistency(bool): Unsets the sessionlessfieldconsistency value.

    sessionlessurlclosure(bool): Unsets the sessionlessurlclosure value.

    semicolonfieldseparator(bool): Unsets the semicolonfieldseparator value.

    excludefileuploadfromchecks(bool): Unsets the excludefileuploadfromchecks value.

    sqlinjectionparsecomments(bool): Unsets the sqlinjectionparsecomments value.

    invalidpercenthandling(bool): Unsets the invalidpercenthandling value.

    ns_type(bool): Unsets the ns_type value.

    checkrequestheaders(bool): Unsets the checkrequestheaders value.

    optimizepartialreqs(bool): Unsets the optimizepartialreqs value.

    urldecoderequestcookies(bool): Unsets the urldecoderequestcookies value.

    comment(bool): Unsets the comment value.

    percentdecoderecursively(bool): Unsets the percentdecoderecursively value.

    multipleheaderaction(bool): Unsets the multipleheaderaction value.

    archivename(bool): Unsets the archivename value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.unset_appfwprofile <args>

    '''

    result = {}

    payload = {'appfwprofile': {}}

    if name:
        payload['appfwprofile']['name'] = True

    if defaults:
        payload['appfwprofile']['defaults'] = True

    if starturlaction:
        payload['appfwprofile']['starturlaction'] = True

    if contenttypeaction:
        payload['appfwprofile']['contenttypeaction'] = True

    if inspectcontenttypes:
        payload['appfwprofile']['inspectcontenttypes'] = True

    if starturlclosure:
        payload['appfwprofile']['starturlclosure'] = True

    if denyurlaction:
        payload['appfwprofile']['denyurlaction'] = True

    if refererheadercheck:
        payload['appfwprofile']['refererheadercheck'] = True

    if cookieconsistencyaction:
        payload['appfwprofile']['cookieconsistencyaction'] = True

    if cookietransforms:
        payload['appfwprofile']['cookietransforms'] = True

    if cookieencryption:
        payload['appfwprofile']['cookieencryption'] = True

    if cookieproxying:
        payload['appfwprofile']['cookieproxying'] = True

    if addcookieflags:
        payload['appfwprofile']['addcookieflags'] = True

    if fieldconsistencyaction:
        payload['appfwprofile']['fieldconsistencyaction'] = True

    if csrftagaction:
        payload['appfwprofile']['csrftagaction'] = True

    if crosssitescriptingaction:
        payload['appfwprofile']['crosssitescriptingaction'] = True

    if crosssitescriptingtransformunsafehtml:
        payload['appfwprofile']['crosssitescriptingtransformunsafehtml'] = True

    if crosssitescriptingcheckcompleteurls:
        payload['appfwprofile']['crosssitescriptingcheckcompleteurls'] = True

    if sqlinjectionaction:
        payload['appfwprofile']['sqlinjectionaction'] = True

    if sqlinjectiontransformspecialchars:
        payload['appfwprofile']['sqlinjectiontransformspecialchars'] = True

    if sqlinjectiononlycheckfieldswithsqlchars:
        payload['appfwprofile']['sqlinjectiononlycheckfieldswithsqlchars'] = True

    if sqlinjectiontype:
        payload['appfwprofile']['sqlinjectiontype'] = True

    if sqlinjectionchecksqlwildchars:
        payload['appfwprofile']['sqlinjectionchecksqlwildchars'] = True

    if fieldformataction:
        payload['appfwprofile']['fieldformataction'] = True

    if defaultfieldformattype:
        payload['appfwprofile']['defaultfieldformattype'] = True

    if defaultfieldformatminlength:
        payload['appfwprofile']['defaultfieldformatminlength'] = True

    if defaultfieldformatmaxlength:
        payload['appfwprofile']['defaultfieldformatmaxlength'] = True

    if bufferoverflowaction:
        payload['appfwprofile']['bufferoverflowaction'] = True

    if bufferoverflowmaxurllength:
        payload['appfwprofile']['bufferoverflowmaxurllength'] = True

    if bufferoverflowmaxheaderlength:
        payload['appfwprofile']['bufferoverflowmaxheaderlength'] = True

    if bufferoverflowmaxcookielength:
        payload['appfwprofile']['bufferoverflowmaxcookielength'] = True

    if creditcardaction:
        payload['appfwprofile']['creditcardaction'] = True

    if creditcard:
        payload['appfwprofile']['creditcard'] = True

    if creditcardmaxallowed:
        payload['appfwprofile']['creditcardmaxallowed'] = True

    if creditcardxout:
        payload['appfwprofile']['creditcardxout'] = True

    if dosecurecreditcardlogging:
        payload['appfwprofile']['dosecurecreditcardlogging'] = True

    if streaming:
        payload['appfwprofile']['streaming'] = True

    if trace:
        payload['appfwprofile']['trace'] = True

    if requestcontenttype:
        payload['appfwprofile']['requestcontenttype'] = True

    if responsecontenttype:
        payload['appfwprofile']['responsecontenttype'] = True

    if xmldosaction:
        payload['appfwprofile']['xmldosaction'] = True

    if xmlformataction:
        payload['appfwprofile']['xmlformataction'] = True

    if xmlsqlinjectionaction:
        payload['appfwprofile']['xmlsqlinjectionaction'] = True

    if xmlsqlinjectiononlycheckfieldswithsqlchars:
        payload['appfwprofile']['xmlsqlinjectiononlycheckfieldswithsqlchars'] = True

    if xmlsqlinjectiontype:
        payload['appfwprofile']['xmlsqlinjectiontype'] = True

    if xmlsqlinjectionchecksqlwildchars:
        payload['appfwprofile']['xmlsqlinjectionchecksqlwildchars'] = True

    if xmlsqlinjectionparsecomments:
        payload['appfwprofile']['xmlsqlinjectionparsecomments'] = True

    if xmlxssaction:
        payload['appfwprofile']['xmlxssaction'] = True

    if xmlwsiaction:
        payload['appfwprofile']['xmlwsiaction'] = True

    if xmlattachmentaction:
        payload['appfwprofile']['xmlattachmentaction'] = True

    if xmlvalidationaction:
        payload['appfwprofile']['xmlvalidationaction'] = True

    if xmlerrorobject:
        payload['appfwprofile']['xmlerrorobject'] = True

    if customsettings:
        payload['appfwprofile']['customsettings'] = True

    if signatures:
        payload['appfwprofile']['signatures'] = True

    if xmlsoapfaultaction:
        payload['appfwprofile']['xmlsoapfaultaction'] = True

    if usehtmlerrorobject:
        payload['appfwprofile']['usehtmlerrorobject'] = True

    if errorurl:
        payload['appfwprofile']['errorurl'] = True

    if htmlerrorobject:
        payload['appfwprofile']['htmlerrorobject'] = True

    if logeverypolicyhit:
        payload['appfwprofile']['logeverypolicyhit'] = True

    if stripcomments:
        payload['appfwprofile']['stripcomments'] = True

    if striphtmlcomments:
        payload['appfwprofile']['striphtmlcomments'] = True

    if stripxmlcomments:
        payload['appfwprofile']['stripxmlcomments'] = True

    if exemptclosureurlsfromsecuritychecks:
        payload['appfwprofile']['exemptclosureurlsfromsecuritychecks'] = True

    if defaultcharset:
        payload['appfwprofile']['defaultcharset'] = True

    if postbodylimit:
        payload['appfwprofile']['postbodylimit'] = True

    if fileuploadmaxnum:
        payload['appfwprofile']['fileuploadmaxnum'] = True

    if canonicalizehtmlresponse:
        payload['appfwprofile']['canonicalizehtmlresponse'] = True

    if enableformtagging:
        payload['appfwprofile']['enableformtagging'] = True

    if sessionlessfieldconsistency:
        payload['appfwprofile']['sessionlessfieldconsistency'] = True

    if sessionlessurlclosure:
        payload['appfwprofile']['sessionlessurlclosure'] = True

    if semicolonfieldseparator:
        payload['appfwprofile']['semicolonfieldseparator'] = True

    if excludefileuploadfromchecks:
        payload['appfwprofile']['excludefileuploadfromchecks'] = True

    if sqlinjectionparsecomments:
        payload['appfwprofile']['sqlinjectionparsecomments'] = True

    if invalidpercenthandling:
        payload['appfwprofile']['invalidpercenthandling'] = True

    if ns_type:
        payload['appfwprofile']['type'] = True

    if checkrequestheaders:
        payload['appfwprofile']['checkrequestheaders'] = True

    if optimizepartialreqs:
        payload['appfwprofile']['optimizepartialreqs'] = True

    if urldecoderequestcookies:
        payload['appfwprofile']['urldecoderequestcookies'] = True

    if comment:
        payload['appfwprofile']['comment'] = True

    if percentdecoderecursively:
        payload['appfwprofile']['percentdecoderecursively'] = True

    if multipleheaderaction:
        payload['appfwprofile']['multipleheaderaction'] = True

    if archivename:
        payload['appfwprofile']['archivename'] = True

    execution = __proxy__['citrixns.post']('config/appfwprofile?action=unset', payload)

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


def unset_appfwsettings(defaultprofile=None, undefaction=None, sessiontimeout=None, learnratelimit=None,
                        sessionlifetime=None, sessioncookiename=None, clientiploggingheader=None, importsizelimit=None,
                        signatureautoupdate=None, signatureurl=None, cookiepostencryptprefix=None, logmalformedreq=None,
                        geolocationlogging=None, ceflogging=None, entitydecoding=None, useconfigurablesecretkey=None,
                        sessionlimit=None, save=False):
    '''
    Unsets values from the appfwsettings configuration key.

    defaultprofile(bool): Unsets the defaultprofile value.

    undefaction(bool): Unsets the undefaction value.

    sessiontimeout(bool): Unsets the sessiontimeout value.

    learnratelimit(bool): Unsets the learnratelimit value.

    sessionlifetime(bool): Unsets the sessionlifetime value.

    sessioncookiename(bool): Unsets the sessioncookiename value.

    clientiploggingheader(bool): Unsets the clientiploggingheader value.

    importsizelimit(bool): Unsets the importsizelimit value.

    signatureautoupdate(bool): Unsets the signatureautoupdate value.

    signatureurl(bool): Unsets the signatureurl value.

    cookiepostencryptprefix(bool): Unsets the cookiepostencryptprefix value.

    logmalformedreq(bool): Unsets the logmalformedreq value.

    geolocationlogging(bool): Unsets the geolocationlogging value.

    ceflogging(bool): Unsets the ceflogging value.

    entitydecoding(bool): Unsets the entitydecoding value.

    useconfigurablesecretkey(bool): Unsets the useconfigurablesecretkey value.

    sessionlimit(bool): Unsets the sessionlimit value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.unset_appfwsettings <args>

    '''

    result = {}

    payload = {'appfwsettings': {}}

    if defaultprofile:
        payload['appfwsettings']['defaultprofile'] = True

    if undefaction:
        payload['appfwsettings']['undefaction'] = True

    if sessiontimeout:
        payload['appfwsettings']['sessiontimeout'] = True

    if learnratelimit:
        payload['appfwsettings']['learnratelimit'] = True

    if sessionlifetime:
        payload['appfwsettings']['sessionlifetime'] = True

    if sessioncookiename:
        payload['appfwsettings']['sessioncookiename'] = True

    if clientiploggingheader:
        payload['appfwsettings']['clientiploggingheader'] = True

    if importsizelimit:
        payload['appfwsettings']['importsizelimit'] = True

    if signatureautoupdate:
        payload['appfwsettings']['signatureautoupdate'] = True

    if signatureurl:
        payload['appfwsettings']['signatureurl'] = True

    if cookiepostencryptprefix:
        payload['appfwsettings']['cookiepostencryptprefix'] = True

    if logmalformedreq:
        payload['appfwsettings']['logmalformedreq'] = True

    if geolocationlogging:
        payload['appfwsettings']['geolocationlogging'] = True

    if ceflogging:
        payload['appfwsettings']['ceflogging'] = True

    if entitydecoding:
        payload['appfwsettings']['entitydecoding'] = True

    if useconfigurablesecretkey:
        payload['appfwsettings']['useconfigurablesecretkey'] = True

    if sessionlimit:
        payload['appfwsettings']['sessionlimit'] = True

    execution = __proxy__['citrixns.post']('config/appfwsettings?action=unset', payload)

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


def update_appfwconfidfield(fieldname=None, url=None, isregex=None, comment=None, state=None, save=False):
    '''
    Update the running configuration for the appfwconfidfield config key.

    fieldname(str): Name of the form field to designate as confidential. Minimum length = 1

    url(str): URL of the web page that contains the web form. Minimum length = 1

    isregex(str): Method of specifying the form field name. Available settings function as follows: * REGEX. Form field is a
        regular expression. * NOTREGEX. Form field is a literal string. Default value: NOTREGEX Possible values = REGEX,
        NOTREGEX

    comment(str): Any comments to preserve information about the form field designation.

    state(str): Enable or disable the confidential field designation. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.update_appfwconfidfield <args>

    '''

    result = {}

    payload = {'appfwconfidfield': {}}

    if fieldname:
        payload['appfwconfidfield']['fieldname'] = fieldname

    if url:
        payload['appfwconfidfield']['url'] = url

    if isregex:
        payload['appfwconfidfield']['isregex'] = isregex

    if comment:
        payload['appfwconfidfield']['comment'] = comment

    if state:
        payload['appfwconfidfield']['state'] = state

    execution = __proxy__['citrixns.put']('config/appfwconfidfield', payload)

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


def update_appfwfieldtype(name=None, regex=None, priority=None, comment=None, nocharmaps=None, save=False):
    '''
    Update the running configuration for the appfwfieldtype config key.

    name(str): Name for the field type. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the field type is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my field type" or my field type). Minimum length = 1

    regex(str): PCRE - format regular expression defining the characters and length allowed for this field type. Minimum
        length = 1

    priority(int): Positive integer specifying the priority of the field type. A lower number specifies a higher priority.
        Field types are checked in the order of their priority numbers. Minimum value = 0 Maximum value = 64000

    comment(str): Comment describing the type of field that this field type is intended to match.

    nocharmaps(bool): will not show internal field types added as part of FieldFormat learn rules deployment.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.update_appfwfieldtype <args>

    '''

    result = {}

    payload = {'appfwfieldtype': {}}

    if name:
        payload['appfwfieldtype']['name'] = name

    if regex:
        payload['appfwfieldtype']['regex'] = regex

    if priority:
        payload['appfwfieldtype']['priority'] = priority

    if comment:
        payload['appfwfieldtype']['comment'] = comment

    if nocharmaps:
        payload['appfwfieldtype']['nocharmaps'] = nocharmaps

    execution = __proxy__['citrixns.put']('config/appfwfieldtype', payload)

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


def update_appfwlearningsettings(profilename=None, starturlminthreshold=None, starturlpercentthreshold=None,
                                 cookieconsistencyminthreshold=None, cookieconsistencypercentthreshold=None,
                                 csrftagminthreshold=None, csrftagpercentthreshold=None,
                                 fieldconsistencyminthreshold=None, fieldconsistencypercentthreshold=None,
                                 crosssitescriptingminthreshold=None, crosssitescriptingpercentthreshold=None,
                                 sqlinjectionminthreshold=None, sqlinjectionpercentthreshold=None,
                                 fieldformatminthreshold=None, fieldformatpercentthreshold=None,
                                 creditcardnumberminthreshold=None, creditcardnumberpercentthreshold=None,
                                 contenttypeminthreshold=None, contenttypepercentthreshold=None, xmlwsiminthreshold=None,
                                 xmlwsipercentthreshold=None, xmlattachmentminthreshold=None,
                                 xmlattachmentpercentthreshold=None, save=False):
    '''
    Update the running configuration for the appfwlearningsettings config key.

    profilename(str): Name of the profile. Minimum length = 1

    starturlminthreshold(int): Minimum number of application firewall sessions that the learning engine must observe to learn
        start URLs. Default value: 1 Minimum value = 1

    starturlpercentthreshold(int): Minimum percentage of application firewall sessions that must contain a particular start
        URL pattern for the learning engine to learn that start URL. Default value: 0 Minimum value = 0 Maximum value =
        100

    cookieconsistencyminthreshold(int): Minimum number of application firewall sessions that the learning engine must observe
        to learn cookies. Default value: 1 Minimum value = 1

    cookieconsistencypercentthreshold(int): Minimum percentage of application firewall sessions that must contain a
        particular cookie pattern for the learning engine to learn that cookie. Default value: 0 Minimum value = 0
        Maximum value = 100

    csrftagminthreshold(int): Minimum number of application firewall sessions that the learning engine must observe to learn
        cross-site request forgery (CSRF) tags. Default value: 1 Minimum value = 1

    csrftagpercentthreshold(int): Minimum percentage of application firewall sessions that must contain a particular CSRF tag
        for the learning engine to learn that CSRF tag. Default value: 0 Minimum value = 0 Maximum value = 100

    fieldconsistencyminthreshold(int): Minimum number of application firewall sessions that the learning engine must observe
        to learn field consistency information. Default value: 1 Minimum value = 1

    fieldconsistencypercentthreshold(int): Minimum percentage of application firewall sessions that must contain a particular
        field consistency pattern for the learning engine to learn that field consistency pattern. Default value: 0
        Minimum value = 0 Maximum value = 100

    crosssitescriptingminthreshold(int): Minimum number of application firewall sessions that the learning engine must
        observe to learn HTML cross-site scripting patterns. Default value: 1 Minimum value = 1

    crosssitescriptingpercentthreshold(int): Minimum percentage of application firewall sessions that must contain a
        particular cross-site scripting pattern for the learning engine to learn that cross-site scripting pattern.
        Default value: 0 Minimum value = 0 Maximum value = 100

    sqlinjectionminthreshold(int): Minimum number of application firewall sessions that the learning engine must observe to
        learn HTML SQL injection patterns. Default value: 1 Minimum value = 1

    sqlinjectionpercentthreshold(int): Minimum percentage of application firewall sessions that must contain a particular
        HTML SQL injection pattern for the learning engine to learn that HTML SQL injection pattern. Default value: 0
        Minimum value = 0 Maximum value = 100

    fieldformatminthreshold(int): Minimum number of application firewall sessions that the learning engine must observe to
        learn field formats. Default value: 1 Minimum value = 1

    fieldformatpercentthreshold(int): Minimum percentage of application firewall sessions that must contain a particular web
        form field pattern for the learning engine to recommend a field format for that form field. Default value: 0
        Minimum value = 0 Maximum value = 100

    creditcardnumberminthreshold(int): Minimum threshold to learn Credit Card information. Default value: 1 Minimum value =
        1

    creditcardnumberpercentthreshold(int): Minimum threshold in percent to learn Credit Card information. Default value: 0
        Minimum value = 0 Maximum value = 100

    contenttypeminthreshold(int): Minimum threshold to learn Content Type information. Default value: 1 Minimum value = 1

    contenttypepercentthreshold(int): Minimum threshold in percent to learn Content Type information. Default value: 0
        Minimum value = 0 Maximum value = 100

    xmlwsiminthreshold(int): Minimum number of application firewall sessions that the learning engine must observe to learn
        web services interoperability (WSI) information. Default value: 1 Minimum value = 1

    xmlwsipercentthreshold(int): Minimum percentage of application firewall sessions that must contain a particular pattern
        for the learning engine to learn a web services interoperability (WSI) pattern. Default value: 0 Minimum value =
        0 Maximum value = 100

    xmlattachmentminthreshold(int): Minimum number of application firewall sessions that the learning engine must observe to
        learn XML attachment patterns. Default value: 1 Minimum value = 1

    xmlattachmentpercentthreshold(int): Minimum percentage of application firewall sessions that must contain a particular
        XML attachment pattern for the learning engine to learn that XML attachment pattern. Default value: 0 Minimum
        value = 0 Maximum value = 100

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.update_appfwlearningsettings <args>

    '''

    result = {}

    payload = {'appfwlearningsettings': {}}

    if profilename:
        payload['appfwlearningsettings']['profilename'] = profilename

    if starturlminthreshold:
        payload['appfwlearningsettings']['starturlminthreshold'] = starturlminthreshold

    if starturlpercentthreshold:
        payload['appfwlearningsettings']['starturlpercentthreshold'] = starturlpercentthreshold

    if cookieconsistencyminthreshold:
        payload['appfwlearningsettings']['cookieconsistencyminthreshold'] = cookieconsistencyminthreshold

    if cookieconsistencypercentthreshold:
        payload['appfwlearningsettings']['cookieconsistencypercentthreshold'] = cookieconsistencypercentthreshold

    if csrftagminthreshold:
        payload['appfwlearningsettings']['csrftagminthreshold'] = csrftagminthreshold

    if csrftagpercentthreshold:
        payload['appfwlearningsettings']['csrftagpercentthreshold'] = csrftagpercentthreshold

    if fieldconsistencyminthreshold:
        payload['appfwlearningsettings']['fieldconsistencyminthreshold'] = fieldconsistencyminthreshold

    if fieldconsistencypercentthreshold:
        payload['appfwlearningsettings']['fieldconsistencypercentthreshold'] = fieldconsistencypercentthreshold

    if crosssitescriptingminthreshold:
        payload['appfwlearningsettings']['crosssitescriptingminthreshold'] = crosssitescriptingminthreshold

    if crosssitescriptingpercentthreshold:
        payload['appfwlearningsettings']['crosssitescriptingpercentthreshold'] = crosssitescriptingpercentthreshold

    if sqlinjectionminthreshold:
        payload['appfwlearningsettings']['sqlinjectionminthreshold'] = sqlinjectionminthreshold

    if sqlinjectionpercentthreshold:
        payload['appfwlearningsettings']['sqlinjectionpercentthreshold'] = sqlinjectionpercentthreshold

    if fieldformatminthreshold:
        payload['appfwlearningsettings']['fieldformatminthreshold'] = fieldformatminthreshold

    if fieldformatpercentthreshold:
        payload['appfwlearningsettings']['fieldformatpercentthreshold'] = fieldformatpercentthreshold

    if creditcardnumberminthreshold:
        payload['appfwlearningsettings']['creditcardnumberminthreshold'] = creditcardnumberminthreshold

    if creditcardnumberpercentthreshold:
        payload['appfwlearningsettings']['creditcardnumberpercentthreshold'] = creditcardnumberpercentthreshold

    if contenttypeminthreshold:
        payload['appfwlearningsettings']['contenttypeminthreshold'] = contenttypeminthreshold

    if contenttypepercentthreshold:
        payload['appfwlearningsettings']['contenttypepercentthreshold'] = contenttypepercentthreshold

    if xmlwsiminthreshold:
        payload['appfwlearningsettings']['xmlwsiminthreshold'] = xmlwsiminthreshold

    if xmlwsipercentthreshold:
        payload['appfwlearningsettings']['xmlwsipercentthreshold'] = xmlwsipercentthreshold

    if xmlattachmentminthreshold:
        payload['appfwlearningsettings']['xmlattachmentminthreshold'] = xmlattachmentminthreshold

    if xmlattachmentpercentthreshold:
        payload['appfwlearningsettings']['xmlattachmentpercentthreshold'] = xmlattachmentpercentthreshold

    execution = __proxy__['citrixns.put']('config/appfwlearningsettings', payload)

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


def update_appfwpolicy(name=None, rule=None, profilename=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Update the running configuration for the appfwpolicy config key.

    name(str): Name for the policy.  Must begin with a letter, number, or the underscore character \\(_\\), and must contain
        only letters, numbers, and the hyphen \\(-\\), period \\(.\\) pound \\(\\#\\), space \\( \\), at (@), equals
        \\(=\\), colon \\(:\\), and underscore characters. Can be changed after the policy is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks \\(for example, "my policy" or my policy\\). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a NetScaler default syntax expression, that the policy uses to determine
        whether to filter the connection through the application firewall with the designated profile.

    profilename(str): Name of the application firewall profile to use if the policy matches. Minimum length = 1

    comment(str): Any comments to preserve information about the policy for later reference.

    logaction(str): Where to log information for connections that match this policy.

    newname(str): New name for the policy. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my policy" or my
        policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.update_appfwpolicy <args>

    '''

    result = {}

    payload = {'appfwpolicy': {}}

    if name:
        payload['appfwpolicy']['name'] = name

    if rule:
        payload['appfwpolicy']['rule'] = rule

    if profilename:
        payload['appfwpolicy']['profilename'] = profilename

    if comment:
        payload['appfwpolicy']['comment'] = comment

    if logaction:
        payload['appfwpolicy']['logaction'] = logaction

    if newname:
        payload['appfwpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/appfwpolicy', payload)

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


def update_appfwprofile(name=None, defaults=None, starturlaction=None, contenttypeaction=None, inspectcontenttypes=None,
                        starturlclosure=None, denyurlaction=None, refererheadercheck=None, cookieconsistencyaction=None,
                        cookietransforms=None, cookieencryption=None, cookieproxying=None, addcookieflags=None,
                        fieldconsistencyaction=None, csrftagaction=None, crosssitescriptingaction=None,
                        crosssitescriptingtransformunsafehtml=None, crosssitescriptingcheckcompleteurls=None,
                        sqlinjectionaction=None, sqlinjectiontransformspecialchars=None,
                        sqlinjectiononlycheckfieldswithsqlchars=None, sqlinjectiontype=None,
                        sqlinjectionchecksqlwildchars=None, fieldformataction=None, defaultfieldformattype=None,
                        defaultfieldformatminlength=None, defaultfieldformatmaxlength=None, bufferoverflowaction=None,
                        bufferoverflowmaxurllength=None, bufferoverflowmaxheaderlength=None,
                        bufferoverflowmaxcookielength=None, creditcardaction=None, creditcard=None,
                        creditcardmaxallowed=None, creditcardxout=None, dosecurecreditcardlogging=None, streaming=None,
                        trace=None, requestcontenttype=None, responsecontenttype=None, xmldosaction=None,
                        xmlformataction=None, xmlsqlinjectionaction=None,
                        xmlsqlinjectiononlycheckfieldswithsqlchars=None, xmlsqlinjectiontype=None,
                        xmlsqlinjectionchecksqlwildchars=None, xmlsqlinjectionparsecomments=None, xmlxssaction=None,
                        xmlwsiaction=None, xmlattachmentaction=None, xmlvalidationaction=None, xmlerrorobject=None,
                        customsettings=None, signatures=None, xmlsoapfaultaction=None, usehtmlerrorobject=None,
                        errorurl=None, htmlerrorobject=None, logeverypolicyhit=None, stripcomments=None,
                        striphtmlcomments=None, stripxmlcomments=None, exemptclosureurlsfromsecuritychecks=None,
                        defaultcharset=None, postbodylimit=None, fileuploadmaxnum=None, canonicalizehtmlresponse=None,
                        enableformtagging=None, sessionlessfieldconsistency=None, sessionlessurlclosure=None,
                        semicolonfieldseparator=None, excludefileuploadfromchecks=None, sqlinjectionparsecomments=None,
                        invalidpercenthandling=None, ns_type=None, checkrequestheaders=None, optimizepartialreqs=None,
                        urldecoderequestcookies=None, comment=None, percentdecoderecursively=None,
                        multipleheaderaction=None, archivename=None, save=False):
    '''
    Update the running configuration for the appfwprofile config key.

    name(str): Name for the profile. Must begin with a letter, number, or the underscore character (_), and must contain only
        letters, numbers, and the hyphen (-), period (.), pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore (_) characters. Cannot be changed after the profile is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my profile" or my profile). Minimum length = 1

    defaults(str): Default configuration to apply to the profile. Basic defaults are intended for standard content that
        requires little further configuration, such as static web site content. Advanced defaults are intended for
        specialized content that requires significant specialized configuration, such as heavily scripted or dynamic
        content.  CLI users: When adding an application firewall profile, you can set either the defaults or the type,
        but not both. To set both options, create the profile by using the add appfw profile command, and then use the
        set appfw profile command to configure the other option. Possible values = basic, advanced

    starturlaction(list(str)): One or more Start URL actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Learn - Use the learning engine to generate a list of exceptions
        to this security check. * Log - Log violations of this security check. * Stats - Generate statistics for this
        security check. * None - Disable all actions for this security check.  CLI users: To enable one or more actions,
        type "set appfw profile -startURLaction" followed by the actions to be enabled. To turn off all actions, type
        "set appfw profile -startURLaction none". Possible values = none, block, learn, log, stats

    contenttypeaction(list(str)): One or more Content-type actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Learn - Use the learning engine to generate a list of exceptions
        to this security check. * Log - Log violations of this security check. * Stats - Generate statistics for this
        security check. * None - Disable all actions for this security check.  CLI users: To enable one or more actions,
        type "set appfw profile -contentTypeaction" followed by the actions to be enabled. To turn off all actions, type
        "set appfw profile -contentTypeaction none". Possible values = none, block, learn, log, stats

    inspectcontenttypes(list(str)): One or more InspectContentType lists.  * application/x-www-form-urlencoded *
        multipart/form-data * text/x-gwt-rpc  CLI users: To enable, type "set appfw profile -InspectContentTypes"
        followed by the content types to be inspected. Possible values = none, application/x-www-form-urlencoded,
        multipart/form-data, text/x-gwt-rpc

    starturlclosure(str): Toggle the state of Start URL Closure. Default value: OFF Possible values = ON, OFF

    denyurlaction(list(str)): One or more Deny URL actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  NOTE: The Deny URL
        check takes precedence over the Start URL check. If you enable blocking for the Deny URL check, the application
        firewall blocks any URL that is explicitly blocked by a Deny URL, even if the same URL would otherwise be allowed
        by the Start URL check.  CLI users: To enable one or more actions, type "set appfw profile -denyURLaction"
        followed by the actions to be enabled. To turn off all actions, type "set appfw profile -denyURLaction none".
        Possible values = none, block, learn, log, stats

    refererheadercheck(str): Enable validation of Referer headers.  Referer validation ensures that a web form that a user
        sends to your web site originally came from your web site, not an outside attacker.  Although this parameter is
        part of the Start URL check, referer validation protects against cross-site request forgery (CSRF) attacks, not
        Start URL attacks. Default value: OFF Possible values = OFF, if_present, AlwaysExceptStartURLs,
        AlwaysExceptFirstRequest

    cookieconsistencyaction(list(str)): One or more Cookie Consistency actions. Available settings function as follows: *
        Block - Block connections that violate this security check. * Learn - Use the learning engine to generate a list
        of exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -cookieConsistencyAction" followed by the actions to be enabled. To
        turn off all actions, type "set appfw profile -cookieConsistencyAction none". Default value: none Possible values
        = none, block, learn, log, stats

    cookietransforms(str): Perform the specified type of cookie transformation.  Available settings function as follows:  *
        Encryption - Encrypt cookies. * Proxying - Mask contents of server cookies by sending proxy cookie to users. *
        Cookie flags - Flag cookies as HTTP only to prevent scripts on users browser from accessing and possibly
        modifying them. CAUTION: Make sure that this parameter is set to ON if you are configuring any cookie
        transformations. If it is set to OFF, no cookie transformations are performed regardless of any other settings.
        Default value: OFF Possible values = ON, OFF

    cookieencryption(str): Type of cookie encryption. Available settings function as follows: * None - Do not encrypt
        cookies. * Decrypt Only - Decrypt encrypted cookies, but do not encrypt cookies. * Encrypt Session Only - Encrypt
        session cookies, but not permanent cookies. * Encrypt All - Encrypt all cookies. Default value: none Possible
        values = none, decryptOnly, encryptSessionOnly, encryptAll

    cookieproxying(str): Cookie proxy setting. Available settings function as follows: * None - Do not proxy cookies. *
        Session Only - Proxy session cookies by using the NetScaler session ID, but do not proxy permanent cookies.
        Default value: none Possible values = none, sessionOnly

    addcookieflags(str): Add the specified flags to cookies. Available settings function as follows: * None - Do not add
        flags to cookies. * HTTP Only - Add the HTTP Only flag to cookies, which prevents scripts from accessing cookies.
        * Secure - Add Secure flag to cookies. * All - Add both HTTPOnly and Secure flags to cookies. Default value: none
        Possible values = none, httpOnly, secure, all

    fieldconsistencyaction(list(str)): One or more Form Field Consistency actions. Available settings function as follows: *
        Block - Block connections that violate this security check. * Learn - Use the learning engine to generate a list
        of exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -fieldConsistencyaction" followed by the actions to be enabled. To
        turn off all actions, type "set appfw profile -fieldConsistencyAction none". Default value: none Possible values
        = none, block, learn, log, stats

    csrftagaction(list(str)): One or more Cross-Site Request Forgery (CSRF) Tagging actions. Available settings function as
        follows: * Block - Block connections that violate this security check. * Learn - Use the learning engine to
        generate a list of exceptions to this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -CSRFTagAction" followed by the actions to be enabled. To
        turn off all actions, type "set appfw profile -CSRFTagAction none". Default value: none Possible values = none,
        block, learn, log, stats

    crosssitescriptingaction(list(str)): One or more Cross-Site Scripting (XSS) actions. Available settings function as
        follows: * Block - Block connections that violate this security check. * Learn - Use the learning engine to
        generate a list of exceptions to this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -crossSiteScriptingAction" followed by the actions to be
        enabled. To turn off all actions, type "set appfw profile -crossSiteScriptingAction none". Possible values =
        none, block, learn, log, stats

    crosssitescriptingtransformunsafehtml(str): Transform cross-site scripts. This setting configures the application
        firewall to disable dangerous HTML instead of blocking the request.  CAUTION: Make sure that this parameter is
        set to ON if you are configuring any cross-site scripting transformations. If it is set to OFF, no cross-site
        scripting transformations are performed regardless of any other settings. Default value: OFF Possible values =
        ON, OFF

    crosssitescriptingcheckcompleteurls(str): Check complete URLs for cross-site scripts, instead of just the query portions
        of URLs. Default value: OFF Possible values = ON, OFF

    sqlinjectionaction(list(str)): One or more HTML SQL Injection actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Learn - Use the learning engine to generate a list of
        exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate statistics
        for this security check. * None - Disable all actions for this security check.  CLI users: To enable one or more
        actions, type "set appfw profile -SQLInjectionAction" followed by the actions to be enabled. To turn off all
        actions, type "set appfw profile -SQLInjectionAction none". Possible values = none, block, learn, log, stats

    sqlinjectiontransformspecialchars(str): Transform injected SQL code. This setting configures the application firewall to
        disable SQL special strings instead of blocking the request. Since most SQL servers require a special string to
        activate an SQL keyword, in most cases a request that contains injected SQL code is safe if special strings are
        disabled. CAUTION: Make sure that this parameter is set to ON if you are configuring any SQL injection
        transformations. If it is set to OFF, no SQL injection transformations are performed regardless of any other
        settings. Default value: OFF Possible values = ON, OFF

    sqlinjectiononlycheckfieldswithsqlchars(str): Check only form fields that contain SQL special strings (characters) for
        injected SQL code. Most SQL servers require a special string to activate an SQL request, so SQL code without a
        special string is harmless to most SQL servers. Default value: ON Possible values = ON, OFF

    sqlinjectiontype(str): Available SQL injection types.  -SQLSplChar : Checks for SQL Special Chars -SQLKeyword : Checks
        for SQL Keywords -SQLSplCharANDKeyword : Checks for both and blocks if both are found -SQLSplCharORKeyword :
        Checks for both and blocks if anyone is found. Default value: SQLSplCharANDKeyword Possible values = SQLSplChar,
        SQLKeyword, SQLSplCharORKeyword, SQLSplCharANDKeyword

    sqlinjectionchecksqlwildchars(str): Check for form fields that contain SQL wild chars . Default value: OFF Possible
        values = ON, OFF

    fieldformataction(list(str)): One or more Field Format actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Learn - Use the learning engine to generate a list of suggested
        web form fields and field format assignments. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -fieldFormatAction" followed by the actions to be enabled. To turn
        off all actions, type "set appfw profile -fieldFormatAction none". Possible values = none, block, learn, log,
        stats

    defaultfieldformattype(str): Designate a default field type to be applied to web form fields that do not have a field
        type explicitly assigned to them. Minimum length = 1

    defaultfieldformatminlength(int): Minimum length, in characters, for data entered into a field that is assigned the
        default field type.  To disable the minimum and maximum length settings and allow data of any length to be
        entered into the field, set this parameter to zero (0). Default value: 0 Minimum value = 0 Maximum value =
        2147483647

    defaultfieldformatmaxlength(int): Maximum length, in characters, for data entered into a field that is assigned the
        default field type. Default value: 65535 Minimum value = 1 Maximum value = 2147483647

    bufferoverflowaction(list(str)): One or more Buffer Overflow actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -bufferOverflowAction" followed by the actions to be enabled.
        To turn off all actions, type "set appfw profile -bufferOverflowAction none". Possible values = none, block,
        learn, log, stats

    bufferoverflowmaxurllength(int): Maximum length, in characters, for URLs on your protected web sites. Requests with
        longer URLs are blocked. Default value: 1024 Minimum value = 0 Maximum value = 65535

    bufferoverflowmaxheaderlength(int): Maximum length, in characters, for HTTP headers in requests sent to your protected
        web sites. Requests with longer headers are blocked. Default value: 4096 Minimum value = 0 Maximum value = 65535

    bufferoverflowmaxcookielength(int): Maximum length, in characters, for cookies sent to your protected web sites. Requests
        with longer cookies are blocked. Default value: 4096 Minimum value = 0 Maximum value = 65535

    creditcardaction(list(str)): One or more Credit Card actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -creditCardAction" followed by the actions to be enabled. To turn
        off all actions, type "set appfw profile -creditCardAction none". Default value: none Possible values = none,
        block, learn, log, stats

    creditcard(list(str)): Credit card types that the application firewall should protect. Possible values = visa,
        mastercard, discover, amex, jcb, dinersclub

    creditcardmaxallowed(int): This parameter value is used by the block action. It represents the maximum number of credit
        card numbers that can appear on a web page served by your protected web sites. Pages that contain more credit
        card numbers are blocked. Minimum value = 0 Maximum value = 255

    creditcardxout(str): Mask any credit card number detected in a response by replacing each digit, except the digits in the
        final group, with the letter "X.". Default value: OFF Possible values = ON, OFF

    dosecurecreditcardlogging(str): Setting this option logs credit card numbers in the response when the match is found.
        Default value: ON Possible values = ON, OFF

    streaming(str): Setting this option converts content-length form submission requests (requests with content-type
        "application/x-www-form-urlencoded" or "multipart/form-data") to chunked requests when atleast one of the
        following protections : SQL injection protection, XSS protection, form field consistency protection, starturl
        closure, CSRF tagging is enabled. Please make sure that the backend server accepts chunked requests before
        enabling this option. Default value: OFF Possible values = ON, OFF

    trace(str): Toggle the state of trace. Default value: OFF Possible values = ON, OFF

    requestcontenttype(str): Default Content-Type header for requests.  A Content-Type header can contain 0-255 letters,
        numbers, and the hyphen (-) and underscore (_) characters. Minimum length = 1 Maximum length = 255

    responsecontenttype(str): Default Content-Type header for responses.  A Content-Type header can contain 0-255 letters,
        numbers, and the hyphen (-) and underscore (_) characters. Minimum length = 1 Maximum length = 255

    xmldosaction(list(str)): One or more XML Denial-of-Service (XDoS) actions. Available settings function as follows: *
        Block - Block connections that violate this security check. * Learn - Use the learning engine to generate a list
        of exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -XMLDoSAction" followed by the actions to be enabled. To turn off
        all actions, type "set appfw profile -XMLDoSAction none". Possible values = none, block, learn, log, stats

    xmlformataction(list(str)): One or more XML Format actions. Available settings function as follows: * Block - Block
        connections that violate this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -XMLFormatAction" followed by the actions to be enabled. To turn off
        all actions, type "set appfw profile -XMLFormatAction none". Possible values = none, block, learn, log, stats

    xmlsqlinjectionaction(list(str)): One or more XML SQL Injection actions. Available settings function as follows: * Block
        - Block connections that violate this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -XMLSQLInjectionAction" followed by the actions to be
        enabled. To turn off all actions, type "set appfw profile -XMLSQLInjectionAction none". Possible values = none,
        block, learn, log, stats

    xmlsqlinjectiononlycheckfieldswithsqlchars(str): Check only form fields that contain SQL special characters, which most
        SQL servers require before accepting an SQL command, for injected SQL. Default value: ON Possible values = ON,
        OFF

    xmlsqlinjectiontype(str): Available SQL injection types. -SQLSplChar : Checks for SQL Special Chars -SQLKeyword : Checks
        for SQL Keywords -SQLSplCharANDKeyword : Checks for both and blocks if both are found -SQLSplCharORKeyword :
        Checks for both and blocks if anyone is found. Default value: SQLSplCharANDKeyword Possible values = SQLSplChar,
        SQLKeyword, SQLSplCharORKeyword, SQLSplCharANDKeyword

    xmlsqlinjectionchecksqlwildchars(str): Check for form fields that contain SQL wild chars . Default value: OFF Possible
        values = ON, OFF

    xmlsqlinjectionparsecomments(str): Parse comments in XML Data and exempt those sections of the request that are from the
        XML SQL Injection check. You must configure the type of comments that the application firewall is to detect and
        exempt from this security check. Available settings function as follows: * Check all - Check all content. * ANSI
        - Exempt content that is part of an ANSI (Mozilla-style) comment.  * Nested - Exempt content that is part of a
        nested (Microsoft-style) comment. * ANSI Nested - Exempt content that is part of any type of comment. Default
        value: checkall Possible values = checkall, ansi, nested, ansinested

    xmlxssaction(list(str)): One or more XML Cross-Site Scripting actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.  CLI users: To
        enable one or more actions, type "set appfw profile -XMLXSSAction" followed by the actions to be enabled. To turn
        off all actions, type "set appfw profile -XMLXSSAction none". Possible values = none, block, learn, log, stats

    xmlwsiaction(list(str)): One or more Web Services Interoperability (WSI) actions. Available settings function as follows:
        * Block - Block connections that violate this security check. * Learn - Use the learning engine to generate a
        list of exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate
        statistics for this security check. * None - Disable all actions for this security check.  CLI users: To enable
        one or more actions, type "set appfw profile -XMLWSIAction" followed by the actions to be enabled. To turn off
        all actions, type "set appfw profile -XMLWSIAction none". Possible values = none, block, learn, log, stats

    xmlattachmentaction(list(str)): One or more XML Attachment actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Learn - Use the learning engine to generate a list of
        exceptions to this security check. * Log - Log violations of this security check. * Stats - Generate statistics
        for this security check. * None - Disable all actions for this security check.  CLI users: To enable one or more
        actions, type "set appfw profile -XMLAttachmentAction" followed by the actions to be enabled. To turn off all
        actions, type "set appfw profile -XMLAttachmentAction none". Possible values = none, block, learn, log, stats

    xmlvalidationaction(list(str)): One or more XML Validation actions. Available settings function as follows: * Block -
        Block connections that violate this security check. * Log - Log violations of this security check. * Stats -
        Generate statistics for this security check. * None - Disable all actions for this security check.   CLI users:
        To enable one or more actions, type "set appfw profile -XMLValidationAction" followed by the actions to be
        enabled. To turn off all actions, type "set appfw profile -XMLValidationAction none". Possible values = none,
        block, learn, log, stats

    xmlerrorobject(str): Name to assign to the XML Error Object, which the application firewall displays when a user request
        is blocked. Must begin with a letter, number, or the underscore character \\(_\\), and must contain only letters,
        numbers, and the hyphen \\(-\\), period \\(.\\) pound \\(\\#\\), space \\( \\), at (@), equals \\(=\\), colon
        \\(:\\), and underscore characters. Cannot be changed after the XML error object is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks \\(for example, "my XML error object" or my XML error object\\). Minimum length
        = 1

    customsettings(str): Object name for custom settings. This check is applicable to Profile Type: HTML, XML. . Minimum
        length = 1

    signatures(str): Object name for signatures. This check is applicable to Profile Type: HTML, XML. . Minimum length = 1

    xmlsoapfaultaction(list(str)): One or more XML SOAP Fault Filtering actions. Available settings function as follows: *
        Block - Block connections that violate this security check. * Log - Log violations of this security check. *
        Stats - Generate statistics for this security check. * None - Disable all actions for this security check. *
        Remove - Remove all violations for this security check.  CLI users: To enable one or more actions, type "set
        appfw profile -XMLSOAPFaultAction" followed by the actions to be enabled. To turn off all actions, type "set
        appfw profile -XMLSOAPFaultAction none". Possible values = none, block, log, remove, stats

    usehtmlerrorobject(str): Send an imported HTML Error object to a user when a request is blocked, instead of redirecting
        the user to the designated Error URL. Default value: OFF Possible values = ON, OFF

    errorurl(str): URL that application firewall uses as the Error URL. Minimum length = 1

    htmlerrorobject(str): Name to assign to the HTML Error Object.  Must begin with a letter, number, or the underscore
        character \\(_\\), and must contain only letters, numbers, and the hyphen \\(-\\), period \\(.\\) pound
        \\(\\#\\), space \\( \\), at (@), equals \\(=\\), colon \\(:\\), and underscore characters. Cannot be changed
        after the HTML error object is added.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks \\(for example, "my HTML error
        object" or my HTML error object\\). Minimum length = 1

    logeverypolicyhit(str): Log every profile match, regardless of security checks results. Default value: OFF Possible
        values = ON, OFF

    stripcomments(str): Strip HTML comments. This check is applicable to Profile Type: HTML. . Default value: OFF Possible
        values = ON, OFF

    striphtmlcomments(str): Strip HTML comments before forwarding a web page sent by a protected web site in response to a
        user request. Default value: none Possible values = none, all, exclude_script_tag

    stripxmlcomments(str): Strip XML comments before forwarding a web page sent by a protected web site in response to a user
        request. Default value: none Possible values = none, all

    exemptclosureurlsfromsecuritychecks(str): Exempt URLs that pass the Start URL closure check from SQL injection,
        cross-site script, field format and field consistency security checks at locations other than headers. Default
        value: ON Possible values = ON, OFF

    defaultcharset(str): Default character set for protected web pages. Web pages sent by your protected web sites in
        response to user requests are assigned this character set if the page does not already specify a character set.
        The character sets supported by the application firewall are:  * iso-8859-1 (English US) * big5 (Chinese
        Traditional) * gb2312 (Chinese Simplified) * sjis (Japanese Shift-JIS) * euc-jp (Japanese EUC-JP) * iso-8859-9
        (Turkish) * utf-8 (Unicode) * euc-kr (Korean). Minimum length = 1 Maximum length = 31

    postbodylimit(int): Maximum allowed HTTP post body size, in bytes. Default value: 20000000

    fileuploadmaxnum(int): Maximum allowed number of file uploads per form-submission request. The maximum setting (65535)
        allows an unlimited number of uploads. Default value: 65535 Minimum value = 0 Maximum value = 65535

    canonicalizehtmlresponse(str): Perform HTML entity encoding for any special characters in responses sent by your
        protected web sites. Default value: ON Possible values = ON, OFF

    enableformtagging(str): Enable tagging of web form fields for use by the Form Field Consistency and CSRF Form Tagging
        checks. Default value: ON Possible values = ON, OFF

    sessionlessfieldconsistency(str): Perform sessionless Field Consistency Checks. Default value: OFF Possible values = OFF,
        ON, postOnly

    sessionlessurlclosure(str): Enable session less URL Closure Checks. This check is applicable to Profile Type: HTML. .
        Default value: OFF Possible values = ON, OFF

    semicolonfieldseparator(str): Allow ; as a form field separator in URL queries and POST form bodies. . Default value: OFF
        Possible values = ON, OFF

    excludefileuploadfromchecks(str): Exclude uploaded files from Form checks. Default value: OFF Possible values = ON, OFF

    sqlinjectionparsecomments(str): Parse HTML comments and exempt them from the HTML SQL Injection check. You must specify
        the type of comments that the application firewall is to detect and exempt from this security check. Available
        settings function as follows: * Check all - Check all content. * ANSI - Exempt content that is part of an ANSI
        (Mozilla-style) comment.  * Nested - Exempt content that is part of a nested (Microsoft-style) comment. * ANSI
        Nested - Exempt content that is part of any type of comment. Possible values = checkall, ansi, nested,
        ansinested

    invalidpercenthandling(str): Configure the method that the application firewall uses to handle percent-encoded names and
        values. Available settings function as follows:  * apache_mode - Apache format. * asp_mode - Microsoft ASP
        format. * secure_mode - Secure format. Default value: secure_mode Possible values = apache_mode, asp_mode,
        secure_mode

    ns_type(list(str)): Application firewall profile type, which controls which security checks and settings are applied to
        content that is filtered with the profile. Available settings function as follows: * HTML - HTML-based web sites.
        * XML - XML-based web sites and services. * HTML XML (Web 2.0) - Sites that contain both HTML and XML content,
        such as ATOM feeds, blogs, and RSS feeds. Default value: HTML Possible values = HTML, XML

    checkrequestheaders(str): Check request headers as well as web forms for injected SQL and cross-site scripts. Default
        value: OFF Possible values = ON, OFF

    optimizepartialreqs(str): Optimize handle of HTTP partial requests i.e. those with range headers. Available settings are
        as follows:  * ON - Partial requests by the client result in partial requests to the backend server in most
        cases. * OFF - Partial requests by the client are changed to full requests to the backend server. Default value:
        ON Possible values = ON, OFF

    urldecoderequestcookies(str): URL Decode request cookies before subjecting them to SQL and cross-site scripting checks.
        Default value: OFF Possible values = ON, OFF

    comment(str): Any comments about the purpose of profile, or other useful information about the profile.

    percentdecoderecursively(str): Configure whether the application firewall should use percentage recursive decoding.
        Default value: OFF Possible values = ON, OFF

    multipleheaderaction(list(str)): One or more multiple header actions. Available settings function as follows: * Block -
        Block connections that have multiple headers. * Log - Log connections that have multiple headers. * KeepLast -
        Keep only last header when multiple headers are present.  CLI users: To enable one or more actions, type "set
        appfw profile -multipleHeaderAction" followed by the actions to be enabled. Possible values = block, keepLast,
        log, none

    archivename(str): Source for tar archive. Minimum length = 1 Maximum length = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.update_appfwprofile <args>

    '''

    result = {}

    payload = {'appfwprofile': {}}

    if name:
        payload['appfwprofile']['name'] = name

    if defaults:
        payload['appfwprofile']['defaults'] = defaults

    if starturlaction:
        payload['appfwprofile']['starturlaction'] = starturlaction

    if contenttypeaction:
        payload['appfwprofile']['contenttypeaction'] = contenttypeaction

    if inspectcontenttypes:
        payload['appfwprofile']['inspectcontenttypes'] = inspectcontenttypes

    if starturlclosure:
        payload['appfwprofile']['starturlclosure'] = starturlclosure

    if denyurlaction:
        payload['appfwprofile']['denyurlaction'] = denyurlaction

    if refererheadercheck:
        payload['appfwprofile']['refererheadercheck'] = refererheadercheck

    if cookieconsistencyaction:
        payload['appfwprofile']['cookieconsistencyaction'] = cookieconsistencyaction

    if cookietransforms:
        payload['appfwprofile']['cookietransforms'] = cookietransforms

    if cookieencryption:
        payload['appfwprofile']['cookieencryption'] = cookieencryption

    if cookieproxying:
        payload['appfwprofile']['cookieproxying'] = cookieproxying

    if addcookieflags:
        payload['appfwprofile']['addcookieflags'] = addcookieflags

    if fieldconsistencyaction:
        payload['appfwprofile']['fieldconsistencyaction'] = fieldconsistencyaction

    if csrftagaction:
        payload['appfwprofile']['csrftagaction'] = csrftagaction

    if crosssitescriptingaction:
        payload['appfwprofile']['crosssitescriptingaction'] = crosssitescriptingaction

    if crosssitescriptingtransformunsafehtml:
        payload['appfwprofile']['crosssitescriptingtransformunsafehtml'] = crosssitescriptingtransformunsafehtml

    if crosssitescriptingcheckcompleteurls:
        payload['appfwprofile']['crosssitescriptingcheckcompleteurls'] = crosssitescriptingcheckcompleteurls

    if sqlinjectionaction:
        payload['appfwprofile']['sqlinjectionaction'] = sqlinjectionaction

    if sqlinjectiontransformspecialchars:
        payload['appfwprofile']['sqlinjectiontransformspecialchars'] = sqlinjectiontransformspecialchars

    if sqlinjectiononlycheckfieldswithsqlchars:
        payload['appfwprofile']['sqlinjectiononlycheckfieldswithsqlchars'] = sqlinjectiononlycheckfieldswithsqlchars

    if sqlinjectiontype:
        payload['appfwprofile']['sqlinjectiontype'] = sqlinjectiontype

    if sqlinjectionchecksqlwildchars:
        payload['appfwprofile']['sqlinjectionchecksqlwildchars'] = sqlinjectionchecksqlwildchars

    if fieldformataction:
        payload['appfwprofile']['fieldformataction'] = fieldformataction

    if defaultfieldformattype:
        payload['appfwprofile']['defaultfieldformattype'] = defaultfieldformattype

    if defaultfieldformatminlength:
        payload['appfwprofile']['defaultfieldformatminlength'] = defaultfieldformatminlength

    if defaultfieldformatmaxlength:
        payload['appfwprofile']['defaultfieldformatmaxlength'] = defaultfieldformatmaxlength

    if bufferoverflowaction:
        payload['appfwprofile']['bufferoverflowaction'] = bufferoverflowaction

    if bufferoverflowmaxurllength:
        payload['appfwprofile']['bufferoverflowmaxurllength'] = bufferoverflowmaxurllength

    if bufferoverflowmaxheaderlength:
        payload['appfwprofile']['bufferoverflowmaxheaderlength'] = bufferoverflowmaxheaderlength

    if bufferoverflowmaxcookielength:
        payload['appfwprofile']['bufferoverflowmaxcookielength'] = bufferoverflowmaxcookielength

    if creditcardaction:
        payload['appfwprofile']['creditcardaction'] = creditcardaction

    if creditcard:
        payload['appfwprofile']['creditcard'] = creditcard

    if creditcardmaxallowed:
        payload['appfwprofile']['creditcardmaxallowed'] = creditcardmaxallowed

    if creditcardxout:
        payload['appfwprofile']['creditcardxout'] = creditcardxout

    if dosecurecreditcardlogging:
        payload['appfwprofile']['dosecurecreditcardlogging'] = dosecurecreditcardlogging

    if streaming:
        payload['appfwprofile']['streaming'] = streaming

    if trace:
        payload['appfwprofile']['trace'] = trace

    if requestcontenttype:
        payload['appfwprofile']['requestcontenttype'] = requestcontenttype

    if responsecontenttype:
        payload['appfwprofile']['responsecontenttype'] = responsecontenttype

    if xmldosaction:
        payload['appfwprofile']['xmldosaction'] = xmldosaction

    if xmlformataction:
        payload['appfwprofile']['xmlformataction'] = xmlformataction

    if xmlsqlinjectionaction:
        payload['appfwprofile']['xmlsqlinjectionaction'] = xmlsqlinjectionaction

    if xmlsqlinjectiononlycheckfieldswithsqlchars:
        payload['appfwprofile']['xmlsqlinjectiononlycheckfieldswithsqlchars'] = xmlsqlinjectiononlycheckfieldswithsqlchars

    if xmlsqlinjectiontype:
        payload['appfwprofile']['xmlsqlinjectiontype'] = xmlsqlinjectiontype

    if xmlsqlinjectionchecksqlwildchars:
        payload['appfwprofile']['xmlsqlinjectionchecksqlwildchars'] = xmlsqlinjectionchecksqlwildchars

    if xmlsqlinjectionparsecomments:
        payload['appfwprofile']['xmlsqlinjectionparsecomments'] = xmlsqlinjectionparsecomments

    if xmlxssaction:
        payload['appfwprofile']['xmlxssaction'] = xmlxssaction

    if xmlwsiaction:
        payload['appfwprofile']['xmlwsiaction'] = xmlwsiaction

    if xmlattachmentaction:
        payload['appfwprofile']['xmlattachmentaction'] = xmlattachmentaction

    if xmlvalidationaction:
        payload['appfwprofile']['xmlvalidationaction'] = xmlvalidationaction

    if xmlerrorobject:
        payload['appfwprofile']['xmlerrorobject'] = xmlerrorobject

    if customsettings:
        payload['appfwprofile']['customsettings'] = customsettings

    if signatures:
        payload['appfwprofile']['signatures'] = signatures

    if xmlsoapfaultaction:
        payload['appfwprofile']['xmlsoapfaultaction'] = xmlsoapfaultaction

    if usehtmlerrorobject:
        payload['appfwprofile']['usehtmlerrorobject'] = usehtmlerrorobject

    if errorurl:
        payload['appfwprofile']['errorurl'] = errorurl

    if htmlerrorobject:
        payload['appfwprofile']['htmlerrorobject'] = htmlerrorobject

    if logeverypolicyhit:
        payload['appfwprofile']['logeverypolicyhit'] = logeverypolicyhit

    if stripcomments:
        payload['appfwprofile']['stripcomments'] = stripcomments

    if striphtmlcomments:
        payload['appfwprofile']['striphtmlcomments'] = striphtmlcomments

    if stripxmlcomments:
        payload['appfwprofile']['stripxmlcomments'] = stripxmlcomments

    if exemptclosureurlsfromsecuritychecks:
        payload['appfwprofile']['exemptclosureurlsfromsecuritychecks'] = exemptclosureurlsfromsecuritychecks

    if defaultcharset:
        payload['appfwprofile']['defaultcharset'] = defaultcharset

    if postbodylimit:
        payload['appfwprofile']['postbodylimit'] = postbodylimit

    if fileuploadmaxnum:
        payload['appfwprofile']['fileuploadmaxnum'] = fileuploadmaxnum

    if canonicalizehtmlresponse:
        payload['appfwprofile']['canonicalizehtmlresponse'] = canonicalizehtmlresponse

    if enableformtagging:
        payload['appfwprofile']['enableformtagging'] = enableformtagging

    if sessionlessfieldconsistency:
        payload['appfwprofile']['sessionlessfieldconsistency'] = sessionlessfieldconsistency

    if sessionlessurlclosure:
        payload['appfwprofile']['sessionlessurlclosure'] = sessionlessurlclosure

    if semicolonfieldseparator:
        payload['appfwprofile']['semicolonfieldseparator'] = semicolonfieldseparator

    if excludefileuploadfromchecks:
        payload['appfwprofile']['excludefileuploadfromchecks'] = excludefileuploadfromchecks

    if sqlinjectionparsecomments:
        payload['appfwprofile']['sqlinjectionparsecomments'] = sqlinjectionparsecomments

    if invalidpercenthandling:
        payload['appfwprofile']['invalidpercenthandling'] = invalidpercenthandling

    if ns_type:
        payload['appfwprofile']['type'] = ns_type

    if checkrequestheaders:
        payload['appfwprofile']['checkrequestheaders'] = checkrequestheaders

    if optimizepartialreqs:
        payload['appfwprofile']['optimizepartialreqs'] = optimizepartialreqs

    if urldecoderequestcookies:
        payload['appfwprofile']['urldecoderequestcookies'] = urldecoderequestcookies

    if comment:
        payload['appfwprofile']['comment'] = comment

    if percentdecoderecursively:
        payload['appfwprofile']['percentdecoderecursively'] = percentdecoderecursively

    if multipleheaderaction:
        payload['appfwprofile']['multipleheaderaction'] = multipleheaderaction

    if archivename:
        payload['appfwprofile']['archivename'] = archivename

    execution = __proxy__['citrixns.put']('config/appfwprofile', payload)

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


def update_appfwsettings(defaultprofile=None, undefaction=None, sessiontimeout=None, learnratelimit=None,
                         sessionlifetime=None, sessioncookiename=None, clientiploggingheader=None, importsizelimit=None,
                         signatureautoupdate=None, signatureurl=None, cookiepostencryptprefix=None, logmalformedreq=None,
                         geolocationlogging=None, ceflogging=None, entitydecoding=None, useconfigurablesecretkey=None,
                         sessionlimit=None, save=False):
    '''
    Update the running configuration for the appfwsettings config key.

    defaultprofile(str): Profile to use when a connection does not match any policy. Default setting is APPFW_BYPASS, which
        sends unmatched connections back to the NetScaler appliance without attempting to filter them further. Default
        value: APPFW_BYPASS Minimum length = 1

    undefaction(str): Profile to use when an application firewall policy evaluates to undefined (UNDEF).  An UNDEF event
        indicates an internal error condition. The APPFW_BLOCK built-in profile is the default setting. You can specify a
        different built-in or user-created profile as the UNDEF profile. Default value: APPFW_BLOCK Minimum length = 1

    sessiontimeout(int): Timeout, in seconds, after which a user session is terminated. Before continuing to use the
        protected web site, the user must establish a new session by opening a designated start URL. Default value: 900
        Minimum value = 1 Maximum value = 65535

    learnratelimit(int): Maximum number of connections per second that the application firewall learning engine examines to
        generate new relaxations for learning-enabled security checks. The application firewall drops any connections
        above this limit from the list of connections used by the learning engine. Default value: 400 Minimum value = 1
        Maximum value = 1000

    sessionlifetime(int): Maximum amount of time (in seconds) that the application firewall allows a user session to remain
        active, regardless of user activity. After this time, the user session is terminated. Before continuing to use
        the protected web site, the user must establish a new session by opening a designated start URL. Default value: 0
        Minimum value = 0 Maximum value = 2147483647

    sessioncookiename(str): Name of the session cookie that the application firewall uses to track user sessions.  Must begin
        with a letter or number, and can consist of from 1 to 31 letters, numbers, and the hyphen (-) and underscore (_)
        symbols.  The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my cookie name" or my cookie name). Minimum
        length = 1

    clientiploggingheader(str): Name of an HTTP header that contains the IP address that the client used to connect to the
        protected web site or service.

    importsizelimit(int): Cumulative total maximum number of bytes in web forms imported to a protected web site. If a user
        attempts to upload files with a total byte count higher than the specified limit, the application firewall blocks
        the request. Default value: 134217728 Minimum value = 1 Maximum value = 134217728

    signatureautoupdate(str): Flag used to enable/disable auto update signatures. Default value: OFF Possible values = ON,
        OFF

    signatureurl(str): URL to download the mapping file from server. Default value:
        https://s3.amazonaws.com/NSAppFwSignatures/SignaturesMapping.xml

    cookiepostencryptprefix(str): String that is prepended to all encrypted cookie values. Minimum length = 1

    logmalformedreq(str): Log requests that are so malformed that application firewall parsing doesnt occur. Default value:
        ON Possible values = ON, OFF

    geolocationlogging(str): Enable Geo-Location Logging in CEF format logs. Default value: OFF Possible values = ON, OFF

    ceflogging(str): Enable CEF format logs. Default value: OFF Possible values = ON, OFF

    entitydecoding(str): Transform multibyte (double- or half-width) characters to single width characters. Default value:
        OFF Possible values = ON, OFF

    useconfigurablesecretkey(str): Use configurable secret key in AppFw operations. Default value: OFF Possible values = ON,
        OFF

    sessionlimit(int): Maximum number of sessions that the application firewall allows to be active, regardless of user
        activity. After the max_limit reaches, No more user session will be created . Default value: 100000 Minimum value
        = 0 Maximum value = 500000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' application_firewall.update_appfwsettings <args>

    '''

    result = {}

    payload = {'appfwsettings': {}}

    if defaultprofile:
        payload['appfwsettings']['defaultprofile'] = defaultprofile

    if undefaction:
        payload['appfwsettings']['undefaction'] = undefaction

    if sessiontimeout:
        payload['appfwsettings']['sessiontimeout'] = sessiontimeout

    if learnratelimit:
        payload['appfwsettings']['learnratelimit'] = learnratelimit

    if sessionlifetime:
        payload['appfwsettings']['sessionlifetime'] = sessionlifetime

    if sessioncookiename:
        payload['appfwsettings']['sessioncookiename'] = sessioncookiename

    if clientiploggingheader:
        payload['appfwsettings']['clientiploggingheader'] = clientiploggingheader

    if importsizelimit:
        payload['appfwsettings']['importsizelimit'] = importsizelimit

    if signatureautoupdate:
        payload['appfwsettings']['signatureautoupdate'] = signatureautoupdate

    if signatureurl:
        payload['appfwsettings']['signatureurl'] = signatureurl

    if cookiepostencryptprefix:
        payload['appfwsettings']['cookiepostencryptprefix'] = cookiepostencryptprefix

    if logmalformedreq:
        payload['appfwsettings']['logmalformedreq'] = logmalformedreq

    if geolocationlogging:
        payload['appfwsettings']['geolocationlogging'] = geolocationlogging

    if ceflogging:
        payload['appfwsettings']['ceflogging'] = ceflogging

    if entitydecoding:
        payload['appfwsettings']['entitydecoding'] = entitydecoding

    if useconfigurablesecretkey:
        payload['appfwsettings']['useconfigurablesecretkey'] = useconfigurablesecretkey

    if sessionlimit:
        payload['appfwsettings']['sessionlimit'] = sessionlimit

    execution = __proxy__['citrixns.put']('config/appfwsettings', payload)

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
