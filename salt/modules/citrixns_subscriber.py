# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the subscriber key.

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

__virtualname__ = 'subscriber'


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

    return False, 'The subscriber execution module can only be loaded for citrixns proxy minions.'


def add_subscriberprofile(ip=None, subscriberrules=None, subscriptionidtype=None, subscriptionidvalue=None,
                          servicepath=None, save=False):
    '''
    Add a new subscriberprofile to the running configuration.

    ip(str): Subscriber ip address.

    subscriberrules(list(str)): Rules configured for this subscriber. This is similar to rules received from PCRF for dynamic
        subscriber sessions.

    subscriptionidtype(str): Subscription-Id type. Possible values = E164, IMSI, SIP_URI, NAI, PRIVATE

    subscriptionidvalue(str): Subscription-Id value.

    servicepath(str): Name of the servicepath to be taken for this subscriber.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.add_subscriberprofile <args>

    '''

    result = {}

    payload = {'subscriberprofile': {}}

    if ip:
        payload['subscriberprofile']['ip'] = ip

    if subscriberrules:
        payload['subscriberprofile']['subscriberrules'] = subscriberrules

    if subscriptionidtype:
        payload['subscriberprofile']['subscriptionidtype'] = subscriptionidtype

    if subscriptionidvalue:
        payload['subscriberprofile']['subscriptionidvalue'] = subscriptionidvalue

    if servicepath:
        payload['subscriberprofile']['servicepath'] = servicepath

    execution = __proxy__['citrixns.post']('config/subscriberprofile', payload)

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


def get_subscribergxinterface():
    '''
    Show the running configuration for the subscribergxinterface config key.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.get_subscribergxinterface

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/subscribergxinterface'), 'subscribergxinterface')

    return response


def get_subscriberparam():
    '''
    Show the running configuration for the subscriberparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.get_subscriberparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/subscriberparam'), 'subscriberparam')

    return response


def get_subscriberprofile(ip=None, subscriberrules=None, subscriptionidtype=None, subscriptionidvalue=None,
                          servicepath=None):
    '''
    Show the running configuration for the subscriberprofile config key.

    ip(str): Filters results that only match the ip field.

    subscriberrules(list(str)): Filters results that only match the subscriberrules field.

    subscriptionidtype(str): Filters results that only match the subscriptionidtype field.

    subscriptionidvalue(str): Filters results that only match the subscriptionidvalue field.

    servicepath(str): Filters results that only match the servicepath field.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.get_subscriberprofile

    '''

    search_filter = []

    if ip:
        search_filter.append(['ip', ip])

    if subscriberrules:
        search_filter.append(['subscriberrules', subscriberrules])

    if subscriptionidtype:
        search_filter.append(['subscriptionidtype', subscriptionidtype])

    if subscriptionidvalue:
        search_filter.append(['subscriptionidvalue', subscriptionidvalue])

    if servicepath:
        search_filter.append(['servicepath', servicepath])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/subscriberprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'subscriberprofile')

    return response


def get_subscriberradiusinterface():
    '''
    Show the running configuration for the subscriberradiusinterface config key.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.get_subscriberradiusinterface

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/subscriberradiusinterface'), 'subscriberradiusinterface')

    return response


def get_subscribersessions(ip=None):
    '''
    Show the running configuration for the subscribersessions config key.

    ip(str): Filters results that only match the ip field.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.get_subscribersessions

    '''

    search_filter = []

    if ip:
        search_filter.append(['ip', ip])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/subscribersessions{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'subscribersessions')

    return response


def unset_subscribergxinterface(vserver=None, service=None, pcrfrealm=None, holdonsubscriberabsence=None,
                                requesttimeout=None, requestretryattempts=None, idlettl=None, revalidationtimeout=None,
                                negativettl=None, servicepathavp=None, servicepathvendorid=None, save=False):
    '''
    Unsets values from the subscribergxinterface configuration key.

    vserver(bool): Unsets the vserver value.

    service(bool): Unsets the service value.

    pcrfrealm(bool): Unsets the pcrfrealm value.

    holdonsubscriberabsence(bool): Unsets the holdonsubscriberabsence value.

    requesttimeout(bool): Unsets the requesttimeout value.

    requestretryattempts(bool): Unsets the requestretryattempts value.

    idlettl(bool): Unsets the idlettl value.

    revalidationtimeout(bool): Unsets the revalidationtimeout value.

    negativettl(bool): Unsets the negativettl value.

    servicepathavp(bool): Unsets the servicepathavp value.

    servicepathvendorid(bool): Unsets the servicepathvendorid value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.unset_subscribergxinterface <args>

    '''

    result = {}

    payload = {'subscribergxinterface': {}}

    if vserver:
        payload['subscribergxinterface']['vserver'] = True

    if service:
        payload['subscribergxinterface']['service'] = True

    if pcrfrealm:
        payload['subscribergxinterface']['pcrfrealm'] = True

    if holdonsubscriberabsence:
        payload['subscribergxinterface']['holdonsubscriberabsence'] = True

    if requesttimeout:
        payload['subscribergxinterface']['requesttimeout'] = True

    if requestretryattempts:
        payload['subscribergxinterface']['requestretryattempts'] = True

    if idlettl:
        payload['subscribergxinterface']['idlettl'] = True

    if revalidationtimeout:
        payload['subscribergxinterface']['revalidationtimeout'] = True

    if negativettl:
        payload['subscribergxinterface']['negativettl'] = True

    if servicepathavp:
        payload['subscribergxinterface']['servicepathavp'] = True

    if servicepathvendorid:
        payload['subscribergxinterface']['servicepathvendorid'] = True

    execution = __proxy__['citrixns.post']('config/subscribergxinterface?action=unset', payload)

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


def unset_subscriberparam(keytype=None, interfacetype=None, idlettl=None, idleaction=None, ipv6prefixlookuplist=None,
                          save=False):
    '''
    Unsets values from the subscriberparam configuration key.

    keytype(bool): Unsets the keytype value.

    interfacetype(bool): Unsets the interfacetype value.

    idlettl(bool): Unsets the idlettl value.

    idleaction(bool): Unsets the idleaction value.

    ipv6prefixlookuplist(bool): Unsets the ipv6prefixlookuplist value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.unset_subscriberparam <args>

    '''

    result = {}

    payload = {'subscriberparam': {}}

    if keytype:
        payload['subscriberparam']['keytype'] = True

    if interfacetype:
        payload['subscriberparam']['interfacetype'] = True

    if idlettl:
        payload['subscriberparam']['idlettl'] = True

    if idleaction:
        payload['subscriberparam']['idleaction'] = True

    if ipv6prefixlookuplist:
        payload['subscriberparam']['ipv6prefixlookuplist'] = True

    execution = __proxy__['citrixns.post']('config/subscriberparam?action=unset', payload)

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


def unset_subscriberprofile(ip=None, subscriberrules=None, subscriptionidtype=None, subscriptionidvalue=None,
                            servicepath=None, save=False):
    '''
    Unsets values from the subscriberprofile configuration key.

    ip(bool): Unsets the ip value.

    subscriberrules(bool): Unsets the subscriberrules value.

    subscriptionidtype(bool): Unsets the subscriptionidtype value.

    subscriptionidvalue(bool): Unsets the subscriptionidvalue value.

    servicepath(bool): Unsets the servicepath value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.unset_subscriberprofile <args>

    '''

    result = {}

    payload = {'subscriberprofile': {}}

    if ip:
        payload['subscriberprofile']['ip'] = True

    if subscriberrules:
        payload['subscriberprofile']['subscriberrules'] = True

    if subscriptionidtype:
        payload['subscriberprofile']['subscriptionidtype'] = True

    if subscriptionidvalue:
        payload['subscriberprofile']['subscriptionidvalue'] = True

    if servicepath:
        payload['subscriberprofile']['servicepath'] = True

    execution = __proxy__['citrixns.post']('config/subscriberprofile?action=unset', payload)

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


def update_subscribergxinterface(vserver=None, service=None, pcrfrealm=None, holdonsubscriberabsence=None,
                                 requesttimeout=None, requestretryattempts=None, idlettl=None, revalidationtimeout=None,
                                 negativettl=None, servicepathavp=None, servicepathvendorid=None, save=False):
    '''
    Update the running configuration for the subscribergxinterface config key.

    vserver(str): Name of the load balancing, or content switching vserver to which the Gx connections are established. The
        service type of the virtual server must be DIAMETER/SSL_DIAMETER. Mutually exclusive with the service parameter.
        Therefore, you cannot set both service and the Virtual Server in the Gx Interface. Minimum length = 1

    service(str): Name of DIAMETER/SSL_DIAMETER service corresponding to PCRF to which the Gx connection is established. The
        service type of the service must be DIAMETER/SSL_DIAMETER. Mutually exclusive with vserver parameter. Therefore,
        you cannot set both Service and the Virtual Server in the Gx Interface. Minimum length = 1

    pcrfrealm(str): PCRF realm is of type DiameterIdentity and contains the realm of PCRF to which the message is to be
        routed. This is the realm used in Destination-Realm AVP by Netscaler Gx client (as a Diameter node).  Minimum
        length = 1

    holdonsubscriberabsence(str): Set this setting to yes if Netscaler needs to Hold pakcets till subscriber session is
        fetched from PCRF. Else set to NO. By default set to yes. If this setting is set to NO, then till NetScaler
        fetches subscriber from PCRF, default subscriber profile will be applied to this subscriber if configured. If
        default subscriber profile is also not configured an undef would be raised to expressions which use Subscriber
        attributes. . Default value: NO Possible values = YES, NO

    requesttimeout(int): q!Time, in seconds, within which the Gx CCR request must complete. If the request does not complete
        within this time, the request is retransmitted for requestRetryAttempts time. If still reuqest is not complete
        then default subscriber profile will be applied to this subscriber if configured. If default subscriber profile
        is also not configured an undef would be raised to expressions which use Subscriber attributes. Zero disables the
        timeout. !. Default value: 10 Minimum value = 0 Maximum value = 86400

    requestretryattempts(int): If the request does not complete within requestTimeout time, the request is retransmitted for
        requestRetryAttempts time. Default value: 3

    idlettl(int): q!Idle Time, in seconds, after which the Gx CCR-U request will be sent after any PCRF activity on a
        session. Any RAR or CCA message resets the timer. Zero value disables the idle timeout. !. Default value: 900
        Minimum value = 0 Maximum value = 86400

    revalidationtimeout(int): q!Revalidation Timeout, in seconds, after which the Gx CCR-U request will be sent after any
        PCRF activity on a session. Any RAR or CCA message resets the timer. Zero value disables the idle timeout. !.
        Default value: 0 Minimum value = 0 Maximum value = 86400

    negativettl(int): q!Negative TTL, in seconds, after which the Gx CCR-I request will be resent for sessions that have not
        been resolved by PCRF due to server being down or no response or failed response. Instead of polling the PCRF
        server constantly, negative-TTL makes NS stick to un-resolved session. Meanwhile Netscaler installs a negative
        session to avoid going to PCRF. For Negative Sessions, Netcaler inherits the attributes from default subscriber
        profile if default subscriber is configured. A default subscriber could be configured as add subscriber profile
        *. Or these attributes can be inherited from Radius as well if Radius is configued. Zero value disables the
        Negative Sessions. And Netscaler does not install Negative sessions even if subscriber session could not be
        fetched. !. Default value: 600 Minimum value = 0 Maximum value = 86400

    servicepathavp(list(int)): The AVP code in which PCRF sends service path applicable for subscriber. Minimum value = 1

    servicepathvendorid(int): The vendorid of the AVP in which PCRF sends service path for subscriber.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.update_subscribergxinterface <args>

    '''

    result = {}

    payload = {'subscribergxinterface': {}}

    if vserver:
        payload['subscribergxinterface']['vserver'] = vserver

    if service:
        payload['subscribergxinterface']['service'] = service

    if pcrfrealm:
        payload['subscribergxinterface']['pcrfrealm'] = pcrfrealm

    if holdonsubscriberabsence:
        payload['subscribergxinterface']['holdonsubscriberabsence'] = holdonsubscriberabsence

    if requesttimeout:
        payload['subscribergxinterface']['requesttimeout'] = requesttimeout

    if requestretryattempts:
        payload['subscribergxinterface']['requestretryattempts'] = requestretryattempts

    if idlettl:
        payload['subscribergxinterface']['idlettl'] = idlettl

    if revalidationtimeout:
        payload['subscribergxinterface']['revalidationtimeout'] = revalidationtimeout

    if negativettl:
        payload['subscribergxinterface']['negativettl'] = negativettl

    if servicepathavp:
        payload['subscribergxinterface']['servicepathavp'] = servicepathavp

    if servicepathvendorid:
        payload['subscribergxinterface']['servicepathvendorid'] = servicepathvendorid

    execution = __proxy__['citrixns.put']('config/subscribergxinterface', payload)

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


def update_subscriberparam(keytype=None, interfacetype=None, idlettl=None, idleaction=None, ipv6prefixlookuplist=None,
                           save=False):
    '''
    Update the running configuration for the subscriberparam config key.

    keytype(str): Type of subscriber key type IP or IPANDVLAN. Default value: IP Possible values = IP

    interfacetype(str): Subscriber Interface refers to Netscaler interaction with control plane protocols, RADIUS and GX.
        Types of subscriber interface: NONE, RadiusOnly, RadiusAndGx, GxOnly. NONE: Only static subscribers can be
        configured. RadiusOnly: GX interface is absent. Subscriber information is obtained through RADIUS Accounting
        messages. RadiusAndGx: Subscriber ID obtained through RADIUS Accounting is used to query PCRF. Subscriber
        information is obtained from both RADIUS and PCRF. GxOnly: RADIUS interface is absent. Subscriber information is
        queried using Subscriber IP.  Default value: None Possible values = None, RadiusOnly, RadiusAndGx, GxOnly

    idlettl(int): q!Idle Timeout, in seconds, after which Netscaler will take an idleAction on a subscriber session (refer to
        idleAction arguement in set subscriber param for more details on idleAction). Any data-plane or control plane
        activity updates the idleTimeout on subscriber session. idleAction could be to just delete the session or delete
        and CCR-T (if PCRF is configured) or do not delete but send a CCR-U.  Zero value disables the idle timeout. !.
        Default value: 0 Minimum value = 0 Maximum value = 172800

    idleaction(str): q!Once idleTTL exprires on a subscriber session, Netscaler will take an idle action on that session.
        idleAction could be chosen from one of these ==;gt; 1. ccrTerminate: (default) send CCR-T to inform PCRF about
        session termination and delete the session.  2. delete: Just delete the subscriber session without informing
        PCRF. 3. ccrUpdate: Do not delete the session and instead send a CCR-U to PCRF requesting for an updated session.
        !. Default value: ccrTerminate Possible values = ccrTerminate, delete, ccrUpdate

    ipv6prefixlookuplist(list(int)): The ipv6PrefixLookupList should consist of all the ipv6 prefix lengths assigned to the
        UEs. Minimum value = 1 Maximum value = 128

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.update_subscriberparam <args>

    '''

    result = {}

    payload = {'subscriberparam': {}}

    if keytype:
        payload['subscriberparam']['keytype'] = keytype

    if interfacetype:
        payload['subscriberparam']['interfacetype'] = interfacetype

    if idlettl:
        payload['subscriberparam']['idlettl'] = idlettl

    if idleaction:
        payload['subscriberparam']['idleaction'] = idleaction

    if ipv6prefixlookuplist:
        payload['subscriberparam']['ipv6prefixlookuplist'] = ipv6prefixlookuplist

    execution = __proxy__['citrixns.put']('config/subscriberparam', payload)

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


def update_subscriberprofile(ip=None, subscriberrules=None, subscriptionidtype=None, subscriptionidvalue=None,
                             servicepath=None, save=False):
    '''
    Update the running configuration for the subscriberprofile config key.

    ip(str): Subscriber ip address.

    subscriberrules(list(str)): Rules configured for this subscriber. This is similar to rules received from PCRF for dynamic
        subscriber sessions.

    subscriptionidtype(str): Subscription-Id type. Possible values = E164, IMSI, SIP_URI, NAI, PRIVATE

    subscriptionidvalue(str): Subscription-Id value.

    servicepath(str): Name of the servicepath to be taken for this subscriber.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.update_subscriberprofile <args>

    '''

    result = {}

    payload = {'subscriberprofile': {}}

    if ip:
        payload['subscriberprofile']['ip'] = ip

    if subscriberrules:
        payload['subscriberprofile']['subscriberrules'] = subscriberrules

    if subscriptionidtype:
        payload['subscriberprofile']['subscriptionidtype'] = subscriptionidtype

    if subscriptionidvalue:
        payload['subscriberprofile']['subscriptionidvalue'] = subscriptionidvalue

    if servicepath:
        payload['subscriberprofile']['servicepath'] = servicepath

    execution = __proxy__['citrixns.put']('config/subscriberprofile', payload)

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


def update_subscriberradiusinterface(listeningservice=None, save=False):
    '''
    Update the running configuration for the subscriberradiusinterface config key.

    listeningservice(str): Name of RADIUS LISTENING service that will process RADIUS accounting requests. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' subscriber.update_subscriberradiusinterface <args>

    '''

    result = {}

    payload = {'subscriberradiusinterface': {}}

    if listeningservice:
        payload['subscriberradiusinterface']['listeningservice'] = listeningservice

    execution = __proxy__['citrixns.put']('config/subscriberradiusinterface', payload)

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
