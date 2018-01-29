# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the domain-name-service key.

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

__virtualname__ = 'domain_name_service'


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

    return False, 'The domain_name_service execution module can only be loaded for citrixns proxy minions.'


def add_dnsaaaarec(hostname=None, ipv6address=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Add a new dnsaaaarec to the running configuration.

    hostname(str): Domain name. Minimum length = 1

    ipv6address(str): One or more IPv6 addresses to assign to the domain name. Minimum length = 1

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached records need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Possible
        values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsaaaarec <args>

    '''

    result = {}

    payload = {'dnsaaaarec': {}}

    if hostname:
        payload['dnsaaaarec']['hostname'] = hostname

    if ipv6address:
        payload['dnsaaaarec']['ipv6address'] = ipv6address

    if ttl:
        payload['dnsaaaarec']['ttl'] = ttl

    if ecssubnet:
        payload['dnsaaaarec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnsaaaarec']['type'] = ns_type

    if nodeid:
        payload['dnsaaaarec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnsaaaarec', payload)

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


def add_dnsaction(actionname=None, actiontype=None, ipaddress=None, ttl=None, viewname=None, preferredloclist=None,
                  dnsprofilename=None, save=False):
    '''
    Add a new dnsaction to the running configuration.

    actionname(str): Name of the dns action.

    actiontype(str): The type of DNS action that is being configured. Possible values = ViewName, GslbPrefLoc, noop, Drop,
        Cache_Bypass, Rewrite_Response

    ipaddress(list(str)): List of IP address to be returned in case of rewrite_response actiontype. They can be of IPV4 or
        IPV6 type.  In case of set command We will remove all the IP address previously present in the action and will
        add new once given in set dns action command.

    ttl(int): Time to live, in seconds. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    viewname(str): The view name that must be used for the given action.

    preferredloclist(list(str)): The location list in priority order used for the given action. Minimum length = 1

    dnsprofilename(str): Name of the DNS profile to be associated with the transaction for which the action is chosen.
        Minimum length = 1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsaction <args>

    '''

    result = {}

    payload = {'dnsaction': {}}

    if actionname:
        payload['dnsaction']['actionname'] = actionname

    if actiontype:
        payload['dnsaction']['actiontype'] = actiontype

    if ipaddress:
        payload['dnsaction']['ipaddress'] = ipaddress

    if ttl:
        payload['dnsaction']['ttl'] = ttl

    if viewname:
        payload['dnsaction']['viewname'] = viewname

    if preferredloclist:
        payload['dnsaction']['preferredloclist'] = preferredloclist

    if dnsprofilename:
        payload['dnsaction']['dnsprofilename'] = dnsprofilename

    execution = __proxy__['citrixns.post']('config/dnsaction', payload)

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


def add_dnsaction64(actionname=None, prefix=None, mappedrule=None, excluderule=None, save=False):
    '''
    Add a new dnsaction64 to the running configuration.

    actionname(str): Name of the dns64 action.

    prefix(str): The dns64 prefix to be used if the after evaluating the rules.

    mappedrule(str): The expression to select the criteria for ipv4 addresses to be used for synthesis.  Only if the
        mappedrule is evaluated to true the corresponding ipv4 address is used for synthesis using respective prefix,
        otherwise the A RR is discarded.

    excluderule(str): The expression to select the criteria for eliminating the corresponding ipv6 addresses from the
        response.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsaction64 <args>

    '''

    result = {}

    payload = {'dnsaction64': {}}

    if actionname:
        payload['dnsaction64']['actionname'] = actionname

    if prefix:
        payload['dnsaction64']['prefix'] = prefix

    if mappedrule:
        payload['dnsaction64']['mappedrule'] = mappedrule

    if excluderule:
        payload['dnsaction64']['excluderule'] = excluderule

    execution = __proxy__['citrixns.post']('config/dnsaction64', payload)

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


def add_dnsaddrec(hostname=None, ipaddress=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Add a new dnsaddrec to the running configuration.

    hostname(str): Domain name. Minimum length = 1

    ipaddress(str): One or more IPv4 addresses to assign to the domain name. Minimum length = 1

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached address records need to be removed.

    ns_type(str): The address record type. The type can take 3 values: ADNS - If this is specified, all of the authoritative
        address records will be displayed. PROXY - If this is specified, all of the proxy address records will be
        displayed. ALL - If this is specified, all of the address records will be displayed. Possible values = ALL, ADNS,
        PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsaddrec <args>

    '''

    result = {}

    payload = {'dnsaddrec': {}}

    if hostname:
        payload['dnsaddrec']['hostname'] = hostname

    if ipaddress:
        payload['dnsaddrec']['ipaddress'] = ipaddress

    if ttl:
        payload['dnsaddrec']['ttl'] = ttl

    if ecssubnet:
        payload['dnsaddrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnsaddrec']['type'] = ns_type

    if nodeid:
        payload['dnsaddrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnsaddrec', payload)

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


def add_dnscnamerec(aliasname=None, canonicalname=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None,
                    save=False):
    '''
    Add a new dnscnamerec to the running configuration.

    aliasname(str): Alias for the canonical domain name. Minimum length = 1

    canonicalname(str): Canonical domain name. Minimum length = 1

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached CNAME record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Default value:
        ADNS Possible values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnscnamerec <args>

    '''

    result = {}

    payload = {'dnscnamerec': {}}

    if aliasname:
        payload['dnscnamerec']['aliasname'] = aliasname

    if canonicalname:
        payload['dnscnamerec']['canonicalname'] = canonicalname

    if ttl:
        payload['dnscnamerec']['ttl'] = ttl

    if ecssubnet:
        payload['dnscnamerec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnscnamerec']['type'] = ns_type

    if nodeid:
        payload['dnscnamerec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnscnamerec', payload)

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


def add_dnsglobal_dnspolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                    gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None, save=False):
    '''
    Add a new dnsglobal_dnspolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy with which it is bound. Maximum allowed priority should be less than
        65535.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the dns policy.

    labelname(str): Name of the label to invoke if the current policy rule evaluates to TRUE.

    gotopriorityexpression(str): Expression or other value specifying the next policy to be evaluated if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a priority
        number that is numerically higher than the highest numbered priority, policy evaluation ends. An UNDEF event is
        triggered if: * The expression is invalid. * The expression evaluates to a priority number that is numerically
        lower than the current policys priority. * The expression evaluates to a priority number that is between the
        current policys priority number (say, 30) and the highest priority number (say, 100), but does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number increments by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label. Minimum length = 1

    invoke(bool): Invoke flag.

    ns_type(str): Type of global bind point for which to show bound policies. Possible values = REQ_OVERRIDE, REQ_DEFAULT,
        RES_OVERRIDE, RES_DEFAULT

    labeltype(str): Type of policy label invocation. Possible values = policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsglobal_dnspolicy_binding <args>

    '''

    result = {}

    payload = {'dnsglobal_dnspolicy_binding': {}}

    if priority:
        payload['dnsglobal_dnspolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['dnsglobal_dnspolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['dnsglobal_dnspolicy_binding']['policyname'] = policyname

    if labelname:
        payload['dnsglobal_dnspolicy_binding']['labelname'] = labelname

    if gotopriorityexpression:
        payload['dnsglobal_dnspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['dnsglobal_dnspolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['dnsglobal_dnspolicy_binding']['type'] = ns_type

    if labeltype:
        payload['dnsglobal_dnspolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/dnsglobal_dnspolicy_binding', payload)

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


def add_dnskey(keyname=None, publickey=None, privatekey=None, expires=None, units1=None, notificationperiod=None,
               units2=None, ttl=None, password=None, zonename=None, keytype=None, algorithm=None, keysize=None,
               filenameprefix=None, src=None, save=False):
    '''
    Add a new dnskey to the running configuration.

    keyname(str): Name of the public-private key pair to publish in the zone. Minimum length = 1

    publickey(str): File name of the public key.

    privatekey(str): File name of the private key.

    expires(int): Time period for which to consider the key valid, after the key is used to sign a zone. Default value: 120
        Minimum value = 1 Maximum value = 32767

    units1(str): Units for the expiry period. Default value: DAYS Possible values = MINUTES, HOURS, DAYS

    notificationperiod(int): Time at which to generate notification of key expiration, specified as number of days, hours, or
        minutes before expiry. Must be less than the expiry period. The notification is an SNMP trap sent to an SNMP
        manager. To enable the appliance to send the trap, enable the DNSKEY-EXPIRY SNMP alarm. Default value: 7 Minimum
        value = 1 Maximum value = 32767

    units2(str): Units for the notification period. Default value: DAYS Possible values = MINUTES, HOURS, DAYS

    ttl(int): Time to Live (TTL), in seconds, for the DNSKEY resource record created in the zone. TTL is the time for which
        the record must be cached by the DNS proxies. If the TTL is not specified, either the DNS zones minimum TTL or
        the default value of 3600 is used. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    password(str): Passphrase for reading the encrypted public/private DNS keys. Minimum length = 1

    zonename(str): Name of the zone for which to create a key. Minimum length = 1

    keytype(str): Type of key to create. Default value: NS_DNSKEY_ZSK Possible values = KSK, KeySigningKey, ZSK,
        ZoneSigningKey

    algorithm(str): Algorithm to generate for zone signing. Default value: NS_DNSKEYALGO_RSASHA1 Possible values = RSASHA1

    keysize(int): Size of the key, in bits. Default value: 512

    filenameprefix(str): Common prefix for the names of the generated public and private key files and the Delegation Signer
        (DS) resource record. During key generation, the .key, .private, and .ds suffixes are appended automatically to
        the file name prefix to produce the names of the public key, the private key, and the DS record, respectively.

    src(str): URL (protocol, host, path, and file name) from where the DNS key file will be imported. NOTE: The import fails
        if the object to be imported is on an HTTPS server that requires client certificate authentication for access.
        This is a mandatory argument. Minimum length = 1 Maximum length = 2047

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnskey <args>

    '''

    result = {}

    payload = {'dnskey': {}}

    if keyname:
        payload['dnskey']['keyname'] = keyname

    if publickey:
        payload['dnskey']['publickey'] = publickey

    if privatekey:
        payload['dnskey']['privatekey'] = privatekey

    if expires:
        payload['dnskey']['expires'] = expires

    if units1:
        payload['dnskey']['units1'] = units1

    if notificationperiod:
        payload['dnskey']['notificationperiod'] = notificationperiod

    if units2:
        payload['dnskey']['units2'] = units2

    if ttl:
        payload['dnskey']['ttl'] = ttl

    if password:
        payload['dnskey']['password'] = password

    if zonename:
        payload['dnskey']['zonename'] = zonename

    if keytype:
        payload['dnskey']['keytype'] = keytype

    if algorithm:
        payload['dnskey']['algorithm'] = algorithm

    if keysize:
        payload['dnskey']['keysize'] = keysize

    if filenameprefix:
        payload['dnskey']['filenameprefix'] = filenameprefix

    if src:
        payload['dnskey']['src'] = src

    execution = __proxy__['citrixns.post']('config/dnskey', payload)

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


def add_dnsmxrec(domain=None, mx=None, pref=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Add a new dnsmxrec to the running configuration.

    domain(str): Domain name for which to add the MX record. Minimum length = 1

    mx(str): Host name of the mail exchange server. Minimum length = 1

    pref(int): Priority number to assign to the mail exchange server. A domain name can have multiple mail servers, with a
        priority number assigned to each server. The lower the priority number, the higher the mail servers priority.
        When other mail servers have to deliver mail to the specified domain, they begin with the mail server with the
        lowest priority number, and use other configured mail servers, in priority order, as backups. Minimum value = 0
        Maximum value = 65535

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached MX record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Default value:
        ADNS Possible values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsmxrec <args>

    '''

    result = {}

    payload = {'dnsmxrec': {}}

    if domain:
        payload['dnsmxrec']['domain'] = domain

    if mx:
        payload['dnsmxrec']['mx'] = mx

    if pref:
        payload['dnsmxrec']['pref'] = pref

    if ttl:
        payload['dnsmxrec']['ttl'] = ttl

    if ecssubnet:
        payload['dnsmxrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnsmxrec']['type'] = ns_type

    if nodeid:
        payload['dnsmxrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnsmxrec', payload)

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


def add_dnsnameserver(ip=None, dnsvservername=None, local=None, state=None, ns_type=None, dnsprofilename=None,
                      save=False):
    '''
    Add a new dnsnameserver to the running configuration.

    ip(str): IP address of an external name server or, if the Local parameter is set, IP address of a local DNS server
        (LDNS). Minimum length = 1

    dnsvservername(str): Name of a DNS virtual server. Overrides any IP address-based name servers configured on the
        NetScaler appliance. Minimum length = 1

    local(bool): Mark the IP address as one that belongs to a local recursive DNS server on the NetScaler appliance. The
        appliance recursively resolves queries received on an IP address that is marked as being local. For recursive
        resolution to work, the global DNS parameter, Recursion, must also be set.   If no name server is marked as being
        local, the appliance functions as a stub resolver and load balances the name servers.

    state(str): Administrative state of the name server. Default value: ENABLED Possible values = ENABLED, DISABLED

    ns_type(str): Protocol used by the name server. UDP_TCP is not valid if the name server is a DNS virtual server
        configured on the appliance. Default value: UDP Possible values = UDP, TCP, UDP_TCP

    dnsprofilename(str): Name of the DNS profile to be associated with the name server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsnameserver <args>

    '''

    result = {}

    payload = {'dnsnameserver': {}}

    if ip:
        payload['dnsnameserver']['ip'] = ip

    if dnsvservername:
        payload['dnsnameserver']['dnsvservername'] = dnsvservername

    if local:
        payload['dnsnameserver']['local'] = local

    if state:
        payload['dnsnameserver']['state'] = state

    if ns_type:
        payload['dnsnameserver']['type'] = ns_type

    if dnsprofilename:
        payload['dnsnameserver']['dnsprofilename'] = dnsprofilename

    execution = __proxy__['citrixns.post']('config/dnsnameserver', payload)

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


def add_dnsnaptrrec(domain=None, order=None, preference=None, flags=None, services=None, regexp=None, replacement=None,
                    ttl=None, recordid=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Add a new dnsnaptrrec to the running configuration.

    domain(str): Name of the domain for the NAPTR record. Minimum length = 1

    order(int): An integer specifying the order in which the NAPTR records MUST be processed in order to accurately represent
        the ordered list of Rules. The ordering is from lowest to highest. Minimum value = 0 Maximum value = 65535

    preference(int): An integer specifying the preference of this NAPTR among NAPTR records having same order. lower the
        number, higher the preference. Minimum value = 0 Maximum value = 65535

    flags(str): flags for this NAPTR. Maximum length = 255

    services(str): Service Parameters applicable to this delegation path. Maximum length = 255

    regexp(str): The regular expression, that specifies the substitution expression for this NAPTR. Maximum length = 255

    replacement(str): The replacement domain name for this NAPTR. Maximum length = 255

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    recordid(int): Unique, internally generated record ID. View the details of the naptr record to obtain its record ID.
        Records can be removed by either specifying the domain name and record id OR by specifying domain name and all
        other naptr record attributes as was supplied during the add command. Minimum value = 1 Maximum value = 65535

    ecssubnet(str): Subnet for which the cached NAPTR record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Default value:
        ADNS Possible values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsnaptrrec <args>

    '''

    result = {}

    payload = {'dnsnaptrrec': {}}

    if domain:
        payload['dnsnaptrrec']['domain'] = domain

    if order:
        payload['dnsnaptrrec']['order'] = order

    if preference:
        payload['dnsnaptrrec']['preference'] = preference

    if flags:
        payload['dnsnaptrrec']['flags'] = flags

    if services:
        payload['dnsnaptrrec']['services'] = services

    if regexp:
        payload['dnsnaptrrec']['regexp'] = regexp

    if replacement:
        payload['dnsnaptrrec']['replacement'] = replacement

    if ttl:
        payload['dnsnaptrrec']['ttl'] = ttl

    if recordid:
        payload['dnsnaptrrec']['recordid'] = recordid

    if ecssubnet:
        payload['dnsnaptrrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnsnaptrrec']['type'] = ns_type

    if nodeid:
        payload['dnsnaptrrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnsnaptrrec', payload)

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


def add_dnsnsrec(domain=None, nameserver=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Add a new dnsnsrec to the running configuration.

    domain(str): Domain name. Minimum length = 1

    nameserver(str): Host name of the name server to add to the domain. Minimum length = 1

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached name server record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Possible
        values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsnsrec <args>

    '''

    result = {}

    payload = {'dnsnsrec': {}}

    if domain:
        payload['dnsnsrec']['domain'] = domain

    if nameserver:
        payload['dnsnsrec']['nameserver'] = nameserver

    if ttl:
        payload['dnsnsrec']['ttl'] = ttl

    if ecssubnet:
        payload['dnsnsrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnsnsrec']['type'] = ns_type

    if nodeid:
        payload['dnsnsrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnsnsrec', payload)

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


def add_dnspolicy(name=None, rule=None, viewname=None, preferredlocation=None, preferredloclist=None, drop=None,
                  cachebypass=None, actionname=None, logaction=None, save=False):
    '''
    Add a new dnspolicy to the running configuration.

    name(str): Name for the DNS policy.

    rule(str): Expression against which DNS traffic is evaluated. Written in the default syntax. Note: * On the command line
        interface, if the expression includes blank spaces, the entire expression must be enclosed in double quotation
        marks. * If the expression itself includes double quotation marks, you must escape the quotations by using the
        character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks.  Maximum length of a string literal in the expression is 255
        characters. A longer string can be split into smaller strings of up to 255 characters each, and the smaller
        strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" Example:
        CLIENT.UDP.DNS.DOMAIN.EQ("domainname").

    viewname(str): The view name that must be used for the given policy.

    preferredlocation(str): The location used for the given policy. This is deprecated attribute. Please use -prefLocList.

    preferredloclist(list(str)): The location list in priority order used for the given policy. Minimum length = 1

    drop(str): The dns packet must be dropped. Possible values = YES, NO

    cachebypass(str): By pass dns cache for this. Possible values = YES, NO

    actionname(str): Name of the DNS action to perform when the rule evaluates to TRUE. The built in actions function as
        follows: * dns_default_act_Drop. Drop the DNS request. * dns_default_act_Cachebypass. Bypass the DNS cache and
        forward the request to the name server. You can create custom actions by using the add dns action command in the
        CLI or the DNS ;gt; Actions ;gt; Create DNS Action dialog box in the NetScaler configuration utility.

    logaction(str): Name of the messagelog action to use for requests that match this policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnspolicy <args>

    '''

    result = {}

    payload = {'dnspolicy': {}}

    if name:
        payload['dnspolicy']['name'] = name

    if rule:
        payload['dnspolicy']['rule'] = rule

    if viewname:
        payload['dnspolicy']['viewname'] = viewname

    if preferredlocation:
        payload['dnspolicy']['preferredlocation'] = preferredlocation

    if preferredloclist:
        payload['dnspolicy']['preferredloclist'] = preferredloclist

    if drop:
        payload['dnspolicy']['drop'] = drop

    if cachebypass:
        payload['dnspolicy']['cachebypass'] = cachebypass

    if actionname:
        payload['dnspolicy']['actionname'] = actionname

    if logaction:
        payload['dnspolicy']['logaction'] = logaction

    execution = __proxy__['citrixns.post']('config/dnspolicy', payload)

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


def add_dnspolicy64(name=None, rule=None, action=None, save=False):
    '''
    Add a new dnspolicy64 to the running configuration.

    name(str): Name for the DNS64 policy.

    rule(str): Expression against which DNS traffic is evaluated. Written in the default syntax. Note: * On the command line
        interface, if the expression includes blank spaces, the entire expression must be enclosed in double quotation
        marks. * If the expression itself includes double quotation marks, you must escape the quotations by using the
        character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks.  Maximum length of a string literal in the expression is 255
        characters. A longer string can be split into smaller strings of up to 255 characters each, and the smaller
        strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" Example:
        CLIENT.IP.SRC.IN_SUBENT(23.34.0.0/16).

    action(str): Name of the DNS64 action to perform when the rule evaluates to TRUE. The built in actions function as
        follows: * A default dns64 action with prefix ;lt;default prefix;gt; and mapped and exclude are any  You can
        create custom actions by using the add dns action command in the CLI or the DNS64 ;gt; Actions ;gt; Create DNS64
        Action dialog box in the NetScaler configuration utility.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnspolicy64 <args>

    '''

    result = {}

    payload = {'dnspolicy64': {}}

    if name:
        payload['dnspolicy64']['name'] = name

    if rule:
        payload['dnspolicy64']['rule'] = rule

    if action:
        payload['dnspolicy64']['action'] = action

    execution = __proxy__['citrixns.post']('config/dnspolicy64', payload)

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


def add_dnspolicylabel(labelname=None, transform=None, newname=None, save=False):
    '''
    Add a new dnspolicylabel to the running configuration.

    labelname(str): Name of the dns policy label.

    transform(str): The type of transformations allowed by the policies bound to the label. Possible values = dns_req,
        dns_res

    newname(str): The new name of the dns policylabel. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnspolicylabel <args>

    '''

    result = {}

    payload = {'dnspolicylabel': {}}

    if labelname:
        payload['dnspolicylabel']['labelname'] = labelname

    if transform:
        payload['dnspolicylabel']['transform'] = transform

    if newname:
        payload['dnspolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/dnspolicylabel', payload)

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


def add_dnspolicylabel_dnspolicy_binding(priority=None, gotopriorityexpression=None, policyname=None, labeltype=None,
                                         labelname=None, invoke_labelname=None, invoke=None, save=False):
    '''
    Add a new dnspolicylabel_dnspolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policyname(str): The dns policy name.

    labeltype(str): Type of policy label invocation. Possible values = policylabel

    labelname(str): Name of the dns policy label.

    invoke_labelname(str): Name of the label to invoke if the current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnspolicylabel_dnspolicy_binding <args>

    '''

    result = {}

    payload = {'dnspolicylabel_dnspolicy_binding': {}}

    if priority:
        payload['dnspolicylabel_dnspolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['dnspolicylabel_dnspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policyname:
        payload['dnspolicylabel_dnspolicy_binding']['policyname'] = policyname

    if labeltype:
        payload['dnspolicylabel_dnspolicy_binding']['labeltype'] = labeltype

    if labelname:
        payload['dnspolicylabel_dnspolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['dnspolicylabel_dnspolicy_binding']['invoke_labelname'] = invoke_labelname

    if invoke:
        payload['dnspolicylabel_dnspolicy_binding']['invoke'] = invoke

    execution = __proxy__['citrixns.post']('config/dnspolicylabel_dnspolicy_binding', payload)

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


def add_dnsprofile(dnsprofilename=None, dnsquerylogging=None, dnsanswerseclogging=None, dnsextendedlogging=None,
                   dnserrorlogging=None, cacherecords=None, cachenegativeresponses=None, dropmultiqueryrequest=None,
                   cacheecsresponses=None, save=False):
    '''
    Add a new dnsprofile to the running configuration.

    dnsprofilename(str): Name of the DNS profile. Minimum length = 1 Maximum length = 127

    dnsquerylogging(str): DNS query logging; if enabled, DNS query information such as DNS query id, DNS query flags , DNS
        domain name and DNS query type will be logged. Default value: DISABLED Possible values = ENABLED, DISABLED

    dnsanswerseclogging(str): DNS answer section; if enabled, answer section in the response will be logged. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    dnsextendedlogging(str): DNS extended logging; if enabled, authority and additional section in the response will be
        logged. Default value: DISABLED Possible values = ENABLED, DISABLED

    dnserrorlogging(str): DNS error logging; if enabled, whenever error is encountered in DNS module reason for the error
        will be logged. Default value: DISABLED Possible values = ENABLED, DISABLED

    cacherecords(str): Cache resource records in the DNS cache. Applies to resource records obtained through proxy
        configurations only. End resolver and forwarder configurations always cache records in the DNS cache, and you
        cannot disable this behavior. When you disable record caching, the appliance stops caching server responses.
        However, cached records are not flushed. The appliance does not serve requests from the cache until record
        caching is enabled again. Default value: ENABLED Possible values = ENABLED, DISABLED

    cachenegativeresponses(str): Cache negative responses in the DNS cache. When disabled, the appliance stops caching
        negative responses except referral records. This applies to all configurations - proxy, end resolver, and
        forwarder. However, cached responses are not flushed. The appliance does not serve negative responses from the
        cache until this parameter is enabled again. Default value: ENABLED Possible values = ENABLED, DISABLED

    dropmultiqueryrequest(str): Drop the DNS requests containing multiple queries. When enabled, DNS requests containing
        multiple queries will be dropped. In case of proxy configuration by default the DNS request containing multiple
        queries is forwarded to the backend and in case of ADNS and Resolver configuration NOCODE error response will be
        sent to the client. Default value: DISABLED Possible values = ENABLED, DISABLED

    cacheecsresponses(str): Cache DNS responses with EDNS Client Subnet(ECS) option in the DNS cache. When disabled, the
        appliance stops caching responses with ECS option. This is relevant to proxy configuration. Enabling/disabling
        support of ECS option when NetScaler is authoritative for a GSLB domain is supported using a knob in GSLB
        vserver. In all other modes, ECS option is ignored. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsprofile <args>

    '''

    result = {}

    payload = {'dnsprofile': {}}

    if dnsprofilename:
        payload['dnsprofile']['dnsprofilename'] = dnsprofilename

    if dnsquerylogging:
        payload['dnsprofile']['dnsquerylogging'] = dnsquerylogging

    if dnsanswerseclogging:
        payload['dnsprofile']['dnsanswerseclogging'] = dnsanswerseclogging

    if dnsextendedlogging:
        payload['dnsprofile']['dnsextendedlogging'] = dnsextendedlogging

    if dnserrorlogging:
        payload['dnsprofile']['dnserrorlogging'] = dnserrorlogging

    if cacherecords:
        payload['dnsprofile']['cacherecords'] = cacherecords

    if cachenegativeresponses:
        payload['dnsprofile']['cachenegativeresponses'] = cachenegativeresponses

    if dropmultiqueryrequest:
        payload['dnsprofile']['dropmultiqueryrequest'] = dropmultiqueryrequest

    if cacheecsresponses:
        payload['dnsprofile']['cacheecsresponses'] = cacheecsresponses

    execution = __proxy__['citrixns.post']('config/dnsprofile', payload)

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


def add_dnsptrrec(reversedomain=None, domain=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Add a new dnsptrrec to the running configuration.

    reversedomain(str): Reversed domain name representation of the IPv4 or IPv6 address for which to create the PTR record.
        Use the "in-addr.arpa." suffix for IPv4 addresses and the "ip6.arpa." suffix for IPv6 addresses. Minimum length =
        1

    domain(str): Domain name for which to configure reverse mapping. Minimum length = 1

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached PTR record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Possible
        values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsptrrec <args>

    '''

    result = {}

    payload = {'dnsptrrec': {}}

    if reversedomain:
        payload['dnsptrrec']['reversedomain'] = reversedomain

    if domain:
        payload['dnsptrrec']['domain'] = domain

    if ttl:
        payload['dnsptrrec']['ttl'] = ttl

    if ecssubnet:
        payload['dnsptrrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnsptrrec']['type'] = ns_type

    if nodeid:
        payload['dnsptrrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnsptrrec', payload)

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


def add_dnssoarec(domain=None, originserver=None, contact=None, serial=None, refresh=None, retry=None, expire=None,
                  minimum=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Add a new dnssoarec to the running configuration.

    domain(str): Domain name for which to add the SOA record. Minimum length = 1

    originserver(str): Domain name of the name server that responds authoritatively for the domain. Minimum length = 1

    contact(str): Email address of the contact to whom domain issues can be addressed. In the email address, replace the @
        sign with a period (.). For example, enter domainadmin.example.com instead of domainadmin@example.com. Minimum
        length = 1

    serial(int): The secondary server uses this parameter to determine whether it requires a zone transfer from the primary
        server. Default value: 100 Minimum value = 0 Maximum value = 4294967294

    refresh(int): Time, in seconds, for which a secondary server must wait between successive checks on the value of the
        serial number. Default value: 3600 Minimum value = 0 Maximum value = 4294967294

    retry(int): Time, in seconds, between retries if a secondary servers attempt to contact the primary server for a zone
        refresh fails. Default value: 3 Minimum value = 0 Maximum value = 4294967294

    expire(int): Time, in seconds, after which the zone data on a secondary name server can no longer be considered
        authoritative because all refresh and retry attempts made during the period have failed. After the expiry period,
        the secondary server stops serving the zone. Typically one week. Not used by the primary server. Default value:
        3600 Minimum value = 0 Maximum value = 4294967294

    minimum(int): Default time to live (TTL) for all records in the zone. Can be overridden for individual records. Default
        value: 5 Minimum value = 0 Maximum value = 2147483647

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached SOA record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Possible
        values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnssoarec <args>

    '''

    result = {}

    payload = {'dnssoarec': {}}

    if domain:
        payload['dnssoarec']['domain'] = domain

    if originserver:
        payload['dnssoarec']['originserver'] = originserver

    if contact:
        payload['dnssoarec']['contact'] = contact

    if serial:
        payload['dnssoarec']['serial'] = serial

    if refresh:
        payload['dnssoarec']['refresh'] = refresh

    if retry:
        payload['dnssoarec']['retry'] = retry

    if expire:
        payload['dnssoarec']['expire'] = expire

    if minimum:
        payload['dnssoarec']['minimum'] = minimum

    if ttl:
        payload['dnssoarec']['ttl'] = ttl

    if ecssubnet:
        payload['dnssoarec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnssoarec']['type'] = ns_type

    if nodeid:
        payload['dnssoarec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnssoarec', payload)

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


def add_dnssrvrec(domain=None, target=None, priority=None, weight=None, port=None, ttl=None, ecssubnet=None,
                  ns_type=None, nodeid=None, save=False):
    '''
    Add a new dnssrvrec to the running configuration.

    domain(str): Domain name, which, by convention, is prefixed by the symbolic name of the desired service and the symbolic
        name of the desired protocol, each with an underscore (_) prepended. For example, if an SRV-aware client wants to
        discover a SIP service that is provided over UDP, in the domain example.com, the client performs a lookup for
        _sip._udp.example.com. Minimum length = 1

    target(str): Target host for the specified service.

    priority(int): Integer specifying the priority of the target host. The lower the number, the higher the priority. If
        multiple target hosts have the same priority, selection is based on the Weight parameter. Minimum value = 0
        Maximum value = 65535

    weight(int): Weight for the target host. Aids host selection when two or more hosts have the same priority. A larger
        number indicates greater weight. Minimum value = 0 Maximum value = 65535

    port(int): Port on which the target host listens for client requests. Minimum value = 0 Maximum value = 65535

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached SRV record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Possible
        values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnssrvrec <args>

    '''

    result = {}

    payload = {'dnssrvrec': {}}

    if domain:
        payload['dnssrvrec']['domain'] = domain

    if target:
        payload['dnssrvrec']['target'] = target

    if priority:
        payload['dnssrvrec']['priority'] = priority

    if weight:
        payload['dnssrvrec']['weight'] = weight

    if port:
        payload['dnssrvrec']['port'] = port

    if ttl:
        payload['dnssrvrec']['ttl'] = ttl

    if ecssubnet:
        payload['dnssrvrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnssrvrec']['type'] = ns_type

    if nodeid:
        payload['dnssrvrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnssrvrec', payload)

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


def add_dnssuffix(dnssuffix=None, save=False):
    '''
    Add a new dnssuffix to the running configuration.

    dnssuffix(str): Suffix to be appended when resolving domain names that are not fully qualified. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnssuffix <args>

    '''

    result = {}

    payload = {'dnssuffix': {}}

    if dnssuffix:
        payload['dnssuffix']['Dnssuffix'] = dnssuffix

    execution = __proxy__['citrixns.post']('config/dnssuffix', payload)

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


def add_dnstxtrec(domain=None, string=None, ttl=None, recordid=None, ecssubnet=None, ns_type=None, nodeid=None,
                  save=False):
    '''
    Add a new dnstxtrec to the running configuration.

    domain(str): Name of the domain for the TXT record. Minimum length = 1

    string(list(str)): Information to store in the TXT resource record. Enclose the string in single or double quotation
        marks. A TXT resource record can contain up to six strings, each of which can contain up to 255 characters. If
        you want to add a string of more than 255 characters, evaluate whether splitting it into two or more smaller
        strings, subject to the six-string limit, works for you. Maximum length = 255

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    recordid(int): Unique, internally generated record ID. View the details of the TXT record to obtain its record ID.
        Mutually exclusive with the string parameter. Minimum value = 1 Maximum value = 65535

    ecssubnet(str): Subnet for which the cached TXT record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Default value:
        ADNS Possible values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnstxtrec <args>

    '''

    result = {}

    payload = {'dnstxtrec': {}}

    if domain:
        payload['dnstxtrec']['domain'] = domain

    if string:
        payload['dnstxtrec']['String'] = string

    if ttl:
        payload['dnstxtrec']['ttl'] = ttl

    if recordid:
        payload['dnstxtrec']['recordid'] = recordid

    if ecssubnet:
        payload['dnstxtrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnstxtrec']['type'] = ns_type

    if nodeid:
        payload['dnstxtrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/dnstxtrec', payload)

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


def add_dnsview(viewname=None, save=False):
    '''
    Add a new dnsview to the running configuration.

    viewname(str): Name for the DNS view. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnsview <args>

    '''

    result = {}

    payload = {'dnsview': {}}

    if viewname:
        payload['dnsview']['viewname'] = viewname

    execution = __proxy__['citrixns.post']('config/dnsview', payload)

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


def add_dnszone(zonename=None, proxymode=None, dnssecoffload=None, nsec=None, keyname=None, ns_type=None, save=False):
    '''
    Add a new dnszone to the running configuration.

    zonename(str): Name of the zone to create. Minimum length = 1

    proxymode(str): Deploy the zone in proxy mode. Enable in the following scenarios: * The load balanced DNS servers are
        authoritative for the zone and all resource records that are part of the zone.  * The load balanced DNS servers
        are authoritative for the zone, but the NetScaler appliance owns a subset of the resource records that belong to
        the zone (partial zone ownership configuration). Typically seen in global server load balancing (GSLB)
        configurations, in which the appliance responds authoritatively to queries for GSLB domain names but forwards
        queries for other domain names in the zone to the load balanced servers. In either scenario, do not create the
        zones Start of Authority (SOA) and name server (NS) resource records on the appliance.  Disable if the appliance
        is authoritative for the zone, but make sure that you have created the SOA and NS records on the appliance before
        you create the zone. Default value: ENABLED Possible values = YES, NO

    dnssecoffload(str): Enable dnssec offload for this zone. Default value: DISABLED Possible values = ENABLED, DISABLED

    nsec(str): Enable nsec generation for dnssec offload. Default value: DISABLED Possible values = ENABLED, DISABLED

    keyname(list(str)): Name of the public/private DNS key pair with which to sign the zone. You can sign a zone with up to
        four keys. Minimum length = 1

    ns_type(str): Type of zone to display. Mutually exclusive with the DNS Zone (zoneName) parameter. Available settings
        function as follows: * ADNS - Display all the zones for which the NetScaler appliance is authoritative. * PROXY -
        Display all the zones for which the NetScaler appliance is functioning as a proxy server. * ALL - Display all the
        zones configured on the appliance. Possible values = ALL, ADNS, PROXY

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.add_dnszone <args>

    '''

    result = {}

    payload = {'dnszone': {}}

    if zonename:
        payload['dnszone']['zonename'] = zonename

    if proxymode:
        payload['dnszone']['proxymode'] = proxymode

    if dnssecoffload:
        payload['dnszone']['dnssecoffload'] = dnssecoffload

    if nsec:
        payload['dnszone']['nsec'] = nsec

    if keyname:
        payload['dnszone']['keyname'] = keyname

    if ns_type:
        payload['dnszone']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/dnszone', payload)

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


def disable_dnsnameserver(ip=None, save=False):
    '''
    Disables a dnsnameserver matching the specified filter.

    ip(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.disable_dnsnameserver ip=foo

    '''

    result = {}

    payload = {'dnsnameserver': {}}

    if ip:
        payload['dnsnameserver']['ip'] = ip
    else:
        result['result'] = 'False'
        result['error'] = 'ip value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/dnsnameserver?action=disable', payload)

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


def enable_dnsnameserver(ip=None, save=False):
    '''
    Enables a dnsnameserver matching the specified filter.

    ip(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.enable_dnsnameserver ip=foo

    '''

    result = {}

    payload = {'dnsnameserver': {}}

    if ip:
        payload['dnsnameserver']['ip'] = ip
    else:
        result['result'] = 'False'
        result['error'] = 'ip value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/dnsnameserver?action=enable', payload)

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


def get_dnsaaaarec(hostname=None, ipv6address=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnsaaaarec config key.

    hostname(str): Filters results that only match the hostname field.

    ipv6address(str): Filters results that only match the ipv6address field.

    ttl(int): Filters results that only match the ttl field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsaaaarec

    '''

    search_filter = []

    if hostname:
        search_filter.append(['hostname', hostname])

    if ipv6address:
        search_filter.append(['ipv6address', ipv6address])

    if ttl:
        search_filter.append(['ttl', ttl])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsaaaarec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsaaaarec')

    return response


def get_dnsaction(actionname=None, actiontype=None, ipaddress=None, ttl=None, viewname=None, preferredloclist=None,
                  dnsprofilename=None):
    '''
    Show the running configuration for the dnsaction config key.

    actionname(str): Filters results that only match the actionname field.

    actiontype(str): Filters results that only match the actiontype field.

    ipaddress(list(str)): Filters results that only match the ipaddress field.

    ttl(int): Filters results that only match the ttl field.

    viewname(str): Filters results that only match the viewname field.

    preferredloclist(list(str)): Filters results that only match the preferredloclist field.

    dnsprofilename(str): Filters results that only match the dnsprofilename field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsaction

    '''

    search_filter = []

    if actionname:
        search_filter.append(['actionname', actionname])

    if actiontype:
        search_filter.append(['actiontype', actiontype])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if ttl:
        search_filter.append(['ttl', ttl])

    if viewname:
        search_filter.append(['viewname', viewname])

    if preferredloclist:
        search_filter.append(['preferredloclist', preferredloclist])

    if dnsprofilename:
        search_filter.append(['dnsprofilename', dnsprofilename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsaction')

    return response


def get_dnsaction64(actionname=None, prefix=None, mappedrule=None, excluderule=None):
    '''
    Show the running configuration for the dnsaction64 config key.

    actionname(str): Filters results that only match the actionname field.

    prefix(str): Filters results that only match the prefix field.

    mappedrule(str): Filters results that only match the mappedrule field.

    excluderule(str): Filters results that only match the excluderule field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsaction64

    '''

    search_filter = []

    if actionname:
        search_filter.append(['actionname', actionname])

    if prefix:
        search_filter.append(['prefix', prefix])

    if mappedrule:
        search_filter.append(['mappedrule', mappedrule])

    if excluderule:
        search_filter.append(['excluderule', excluderule])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsaction64{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsaction64')

    return response


def get_dnsaddrec(hostname=None, ipaddress=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnsaddrec config key.

    hostname(str): Filters results that only match the hostname field.

    ipaddress(str): Filters results that only match the ipaddress field.

    ttl(int): Filters results that only match the ttl field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsaddrec

    '''

    search_filter = []

    if hostname:
        search_filter.append(['hostname', hostname])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if ttl:
        search_filter.append(['ttl', ttl])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsaddrec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsaddrec')

    return response


def get_dnscnamerec(aliasname=None, canonicalname=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnscnamerec config key.

    aliasname(str): Filters results that only match the aliasname field.

    canonicalname(str): Filters results that only match the canonicalname field.

    ttl(int): Filters results that only match the ttl field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnscnamerec

    '''

    search_filter = []

    if aliasname:
        search_filter.append(['aliasname', aliasname])

    if canonicalname:
        search_filter.append(['canonicalname', canonicalname])

    if ttl:
        search_filter.append(['ttl', ttl])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnscnamerec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnscnamerec')

    return response


def get_dnsglobal_binding():
    '''
    Show the running configuration for the dnsglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsglobal_binding'), 'dnsglobal_binding')

    return response


def get_dnsglobal_dnspolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                    gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the dnsglobal_dnspolicy_binding config key.

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

    salt '*' domain_name_service.get_dnsglobal_dnspolicy_binding

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
            __proxy__['citrixns.get']('config/dnsglobal_dnspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsglobal_dnspolicy_binding')

    return response


def get_dnskey(keyname=None, publickey=None, privatekey=None, expires=None, units1=None, notificationperiod=None,
               units2=None, ttl=None, password=None, zonename=None, keytype=None, algorithm=None, keysize=None,
               filenameprefix=None, src=None):
    '''
    Show the running configuration for the dnskey config key.

    keyname(str): Filters results that only match the keyname field.

    publickey(str): Filters results that only match the publickey field.

    privatekey(str): Filters results that only match the privatekey field.

    expires(int): Filters results that only match the expires field.

    units1(str): Filters results that only match the units1 field.

    notificationperiod(int): Filters results that only match the notificationperiod field.

    units2(str): Filters results that only match the units2 field.

    ttl(int): Filters results that only match the ttl field.

    password(str): Filters results that only match the password field.

    zonename(str): Filters results that only match the zonename field.

    keytype(str): Filters results that only match the keytype field.

    algorithm(str): Filters results that only match the algorithm field.

    keysize(int): Filters results that only match the keysize field.

    filenameprefix(str): Filters results that only match the filenameprefix field.

    src(str): Filters results that only match the src field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnskey

    '''

    search_filter = []

    if keyname:
        search_filter.append(['keyname', keyname])

    if publickey:
        search_filter.append(['publickey', publickey])

    if privatekey:
        search_filter.append(['privatekey', privatekey])

    if expires:
        search_filter.append(['expires', expires])

    if units1:
        search_filter.append(['units1', units1])

    if notificationperiod:
        search_filter.append(['notificationperiod', notificationperiod])

    if units2:
        search_filter.append(['units2', units2])

    if ttl:
        search_filter.append(['ttl', ttl])

    if password:
        search_filter.append(['password', password])

    if zonename:
        search_filter.append(['zonename', zonename])

    if keytype:
        search_filter.append(['keytype', keytype])

    if algorithm:
        search_filter.append(['algorithm', algorithm])

    if keysize:
        search_filter.append(['keysize', keysize])

    if filenameprefix:
        search_filter.append(['filenameprefix', filenameprefix])

    if src:
        search_filter.append(['src', src])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnskey{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnskey')

    return response


def get_dnsmxrec(domain=None, mx=None, pref=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnsmxrec config key.

    domain(str): Filters results that only match the domain field.

    mx(str): Filters results that only match the mx field.

    pref(int): Filters results that only match the pref field.

    ttl(int): Filters results that only match the ttl field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsmxrec

    '''

    search_filter = []

    if domain:
        search_filter.append(['domain', domain])

    if mx:
        search_filter.append(['mx', mx])

    if pref:
        search_filter.append(['pref', pref])

    if ttl:
        search_filter.append(['ttl', ttl])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsmxrec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsmxrec')

    return response


def get_dnsnameserver(ip=None, dnsvservername=None, local=None, state=None, ns_type=None, dnsprofilename=None):
    '''
    Show the running configuration for the dnsnameserver config key.

    ip(str): Filters results that only match the ip field.

    dnsvservername(str): Filters results that only match the dnsvservername field.

    local(bool): Filters results that only match the local field.

    state(str): Filters results that only match the state field.

    ns_type(str): Filters results that only match the type field.

    dnsprofilename(str): Filters results that only match the dnsprofilename field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsnameserver

    '''

    search_filter = []

    if ip:
        search_filter.append(['ip', ip])

    if dnsvservername:
        search_filter.append(['dnsvservername', dnsvservername])

    if local:
        search_filter.append(['local', local])

    if state:
        search_filter.append(['state', state])

    if ns_type:
        search_filter.append(['type', ns_type])

    if dnsprofilename:
        search_filter.append(['dnsprofilename', dnsprofilename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsnameserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsnameserver')

    return response


def get_dnsnaptrrec(domain=None, order=None, preference=None, flags=None, services=None, regexp=None, replacement=None,
                    ttl=None, recordid=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnsnaptrrec config key.

    domain(str): Filters results that only match the domain field.

    order(int): Filters results that only match the order field.

    preference(int): Filters results that only match the preference field.

    flags(str): Filters results that only match the flags field.

    services(str): Filters results that only match the services field.

    regexp(str): Filters results that only match the regexp field.

    replacement(str): Filters results that only match the replacement field.

    ttl(int): Filters results that only match the ttl field.

    recordid(int): Filters results that only match the recordid field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsnaptrrec

    '''

    search_filter = []

    if domain:
        search_filter.append(['domain', domain])

    if order:
        search_filter.append(['order', order])

    if preference:
        search_filter.append(['preference', preference])

    if flags:
        search_filter.append(['flags', flags])

    if services:
        search_filter.append(['services', services])

    if regexp:
        search_filter.append(['regexp', regexp])

    if replacement:
        search_filter.append(['replacement', replacement])

    if ttl:
        search_filter.append(['ttl', ttl])

    if recordid:
        search_filter.append(['recordid', recordid])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsnaptrrec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsnaptrrec')

    return response


def get_dnsnsecrec(hostname=None, ns_type=None):
    '''
    Show the running configuration for the dnsnsecrec config key.

    hostname(str): Filters results that only match the hostname field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsnsecrec

    '''

    search_filter = []

    if hostname:
        search_filter.append(['hostname', hostname])

    if ns_type:
        search_filter.append(['type', ns_type])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsnsecrec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsnsecrec')

    return response


def get_dnsnsrec(domain=None, nameserver=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnsnsrec config key.

    domain(str): Filters results that only match the domain field.

    nameserver(str): Filters results that only match the nameserver field.

    ttl(int): Filters results that only match the ttl field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsnsrec

    '''

    search_filter = []

    if domain:
        search_filter.append(['domain', domain])

    if nameserver:
        search_filter.append(['nameserver', nameserver])

    if ttl:
        search_filter.append(['ttl', ttl])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsnsrec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsnsrec')

    return response


def get_dnsparameter():
    '''
    Show the running configuration for the dnsparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsparameter'), 'dnsparameter')

    return response


def get_dnspolicy(name=None, rule=None, viewname=None, preferredlocation=None, preferredloclist=None, drop=None,
                  cachebypass=None, actionname=None, logaction=None):
    '''
    Show the running configuration for the dnspolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    viewname(str): Filters results that only match the viewname field.

    preferredlocation(str): Filters results that only match the preferredlocation field.

    preferredloclist(list(str)): Filters results that only match the preferredloclist field.

    drop(str): Filters results that only match the drop field.

    cachebypass(str): Filters results that only match the cachebypass field.

    actionname(str): Filters results that only match the actionname field.

    logaction(str): Filters results that only match the logaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if viewname:
        search_filter.append(['viewname', viewname])

    if preferredlocation:
        search_filter.append(['preferredlocation', preferredlocation])

    if preferredloclist:
        search_filter.append(['preferredloclist', preferredloclist])

    if drop:
        search_filter.append(['drop', drop])

    if cachebypass:
        search_filter.append(['cachebypass', cachebypass])

    if actionname:
        search_filter.append(['actionname', actionname])

    if logaction:
        search_filter.append(['logaction', logaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnspolicy')

    return response


def get_dnspolicy64(name=None, rule=None, action=None):
    '''
    Show the running configuration for the dnspolicy64 config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicy64

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicy64{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnspolicy64')

    return response


def get_dnspolicy64_binding():
    '''
    Show the running configuration for the dnspolicy64_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicy64_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicy64_binding'), 'dnspolicy64_binding')

    return response


def get_dnspolicy64_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the dnspolicy64_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicy64_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicy64_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnspolicy64_lbvserver_binding')

    return response


def get_dnspolicy_binding():
    '''
    Show the running configuration for the dnspolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicy_binding'), 'dnspolicy_binding')

    return response


def get_dnspolicy_dnsglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the dnspolicy_dnsglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicy_dnsglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicy_dnsglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnspolicy_dnsglobal_binding')

    return response


def get_dnspolicy_dnspolicylabel_binding(boundto=None, name=None):
    '''
    Show the running configuration for the dnspolicy_dnspolicylabel_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicy_dnspolicylabel_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicy_dnspolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnspolicy_dnspolicylabel_binding')

    return response


def get_dnspolicylabel(labelname=None, transform=None, newname=None):
    '''
    Show the running configuration for the dnspolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    transform(str): Filters results that only match the transform field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if transform:
        search_filter.append(['transform', transform])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnspolicylabel')

    return response


def get_dnspolicylabel_binding():
    '''
    Show the running configuration for the dnspolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicylabel_binding'), 'dnspolicylabel_binding')

    return response


def get_dnspolicylabel_dnspolicy_binding(priority=None, gotopriorityexpression=None, policyname=None, labeltype=None,
                                         labelname=None, invoke_labelname=None, invoke=None):
    '''
    Show the running configuration for the dnspolicylabel_dnspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policyname(str): Filters results that only match the policyname field.

    labeltype(str): Filters results that only match the labeltype field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    invoke(bool): Filters results that only match the invoke field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicylabel_dnspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    if labelname:
        search_filter.append(['labelname', labelname])

    if invoke_labelname:
        search_filter.append(['invoke_labelname', invoke_labelname])

    if invoke:
        search_filter.append(['invoke', invoke])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicylabel_dnspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnspolicylabel_dnspolicy_binding')

    return response


def get_dnspolicylabel_policybinding_binding(priority=None, gotopriorityexpression=None, policyname=None, labeltype=None,
                                             labelname=None, invoke_labelname=None, invoke=None):
    '''
    Show the running configuration for the dnspolicylabel_policybinding_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policyname(str): Filters results that only match the policyname field.

    labeltype(str): Filters results that only match the labeltype field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    invoke(bool): Filters results that only match the invoke field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnspolicylabel_policybinding_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    if labelname:
        search_filter.append(['labelname', labelname])

    if invoke_labelname:
        search_filter.append(['invoke_labelname', invoke_labelname])

    if invoke:
        search_filter.append(['invoke', invoke])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnspolicylabel_policybinding_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnspolicylabel_policybinding_binding')

    return response


def get_dnsprofile(dnsprofilename=None, dnsquerylogging=None, dnsanswerseclogging=None, dnsextendedlogging=None,
                   dnserrorlogging=None, cacherecords=None, cachenegativeresponses=None, dropmultiqueryrequest=None,
                   cacheecsresponses=None):
    '''
    Show the running configuration for the dnsprofile config key.

    dnsprofilename(str): Filters results that only match the dnsprofilename field.

    dnsquerylogging(str): Filters results that only match the dnsquerylogging field.

    dnsanswerseclogging(str): Filters results that only match the dnsanswerseclogging field.

    dnsextendedlogging(str): Filters results that only match the dnsextendedlogging field.

    dnserrorlogging(str): Filters results that only match the dnserrorlogging field.

    cacherecords(str): Filters results that only match the cacherecords field.

    cachenegativeresponses(str): Filters results that only match the cachenegativeresponses field.

    dropmultiqueryrequest(str): Filters results that only match the dropmultiqueryrequest field.

    cacheecsresponses(str): Filters results that only match the cacheecsresponses field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsprofile

    '''

    search_filter = []

    if dnsprofilename:
        search_filter.append(['dnsprofilename', dnsprofilename])

    if dnsquerylogging:
        search_filter.append(['dnsquerylogging', dnsquerylogging])

    if dnsanswerseclogging:
        search_filter.append(['dnsanswerseclogging', dnsanswerseclogging])

    if dnsextendedlogging:
        search_filter.append(['dnsextendedlogging', dnsextendedlogging])

    if dnserrorlogging:
        search_filter.append(['dnserrorlogging', dnserrorlogging])

    if cacherecords:
        search_filter.append(['cacherecords', cacherecords])

    if cachenegativeresponses:
        search_filter.append(['cachenegativeresponses', cachenegativeresponses])

    if dropmultiqueryrequest:
        search_filter.append(['dropmultiqueryrequest', dropmultiqueryrequest])

    if cacheecsresponses:
        search_filter.append(['cacheecsresponses', cacheecsresponses])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsprofile')

    return response


def get_dnsptrrec(reversedomain=None, domain=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnsptrrec config key.

    reversedomain(str): Filters results that only match the reversedomain field.

    domain(str): Filters results that only match the domain field.

    ttl(int): Filters results that only match the ttl field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsptrrec

    '''

    search_filter = []

    if reversedomain:
        search_filter.append(['reversedomain', reversedomain])

    if domain:
        search_filter.append(['domain', domain])

    if ttl:
        search_filter.append(['ttl', ttl])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsptrrec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsptrrec')

    return response


def get_dnssoarec(domain=None, originserver=None, contact=None, serial=None, refresh=None, retry=None, expire=None,
                  minimum=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnssoarec config key.

    domain(str): Filters results that only match the domain field.

    originserver(str): Filters results that only match the originserver field.

    contact(str): Filters results that only match the contact field.

    serial(int): Filters results that only match the serial field.

    refresh(int): Filters results that only match the refresh field.

    retry(int): Filters results that only match the retry field.

    expire(int): Filters results that only match the expire field.

    minimum(int): Filters results that only match the minimum field.

    ttl(int): Filters results that only match the ttl field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnssoarec

    '''

    search_filter = []

    if domain:
        search_filter.append(['domain', domain])

    if originserver:
        search_filter.append(['originserver', originserver])

    if contact:
        search_filter.append(['contact', contact])

    if serial:
        search_filter.append(['serial', serial])

    if refresh:
        search_filter.append(['refresh', refresh])

    if retry:
        search_filter.append(['retry', retry])

    if expire:
        search_filter.append(['expire', expire])

    if minimum:
        search_filter.append(['minimum', minimum])

    if ttl:
        search_filter.append(['ttl', ttl])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnssoarec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnssoarec')

    return response


def get_dnssrvrec(domain=None, target=None, priority=None, weight=None, port=None, ttl=None, ecssubnet=None,
                  ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnssrvrec config key.

    domain(str): Filters results that only match the domain field.

    target(str): Filters results that only match the target field.

    priority(int): Filters results that only match the priority field.

    weight(int): Filters results that only match the weight field.

    port(int): Filters results that only match the port field.

    ttl(int): Filters results that only match the ttl field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnssrvrec

    '''

    search_filter = []

    if domain:
        search_filter.append(['domain', domain])

    if target:
        search_filter.append(['target', target])

    if priority:
        search_filter.append(['priority', priority])

    if weight:
        search_filter.append(['weight', weight])

    if port:
        search_filter.append(['port', port])

    if ttl:
        search_filter.append(['ttl', ttl])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnssrvrec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnssrvrec')

    return response


def get_dnssubnetcache(ecssubnet=None, nodeid=None):
    '''
    Show the running configuration for the dnssubnetcache config key.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnssubnetcache

    '''

    search_filter = []

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnssubnetcache{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnssubnetcache')

    return response


def get_dnssuffix(dnssuffix=None):
    '''
    Show the running configuration for the dnssuffix config key.

    dnssuffix(str): Filters results that only match the Dnssuffix field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnssuffix

    '''

    search_filter = []

    if dnssuffix:
        search_filter.append(['Dnssuffix', dnssuffix])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnssuffix{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnssuffix')

    return response


def get_dnstxtrec(domain=None, string=None, ttl=None, recordid=None, ecssubnet=None, ns_type=None, nodeid=None):
    '''
    Show the running configuration for the dnstxtrec config key.

    domain(str): Filters results that only match the domain field.

    string(list(str)): Filters results that only match the String field.

    ttl(int): Filters results that only match the ttl field.

    recordid(int): Filters results that only match the recordid field.

    ecssubnet(str): Filters results that only match the ecssubnet field.

    ns_type(str): Filters results that only match the type field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnstxtrec

    '''

    search_filter = []

    if domain:
        search_filter.append(['domain', domain])

    if string:
        search_filter.append(['String', string])

    if ttl:
        search_filter.append(['ttl', ttl])

    if recordid:
        search_filter.append(['recordid', recordid])

    if ecssubnet:
        search_filter.append(['ecssubnet', ecssubnet])

    if ns_type:
        search_filter.append(['type', ns_type])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnstxtrec{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnstxtrec')

    return response


def get_dnsview(viewname=None):
    '''
    Show the running configuration for the dnsview config key.

    viewname(str): Filters results that only match the viewname field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsview

    '''

    search_filter = []

    if viewname:
        search_filter.append(['viewname', viewname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsview{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsview')

    return response


def get_dnsview_binding():
    '''
    Show the running configuration for the dnsview_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsview_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsview_binding'), 'dnsview_binding')

    return response


def get_dnsview_dnspolicy_binding(viewname=None, dnspolicyname=None):
    '''
    Show the running configuration for the dnsview_dnspolicy_binding config key.

    viewname(str): Filters results that only match the viewname field.

    dnspolicyname(str): Filters results that only match the dnspolicyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsview_dnspolicy_binding

    '''

    search_filter = []

    if viewname:
        search_filter.append(['viewname', viewname])

    if dnspolicyname:
        search_filter.append(['dnspolicyname', dnspolicyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsview_dnspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsview_dnspolicy_binding')

    return response


def get_dnsview_gslbservice_binding(viewname=None, gslbservicename=None):
    '''
    Show the running configuration for the dnsview_gslbservice_binding config key.

    viewname(str): Filters results that only match the viewname field.

    gslbservicename(str): Filters results that only match the gslbservicename field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnsview_gslbservice_binding

    '''

    search_filter = []

    if viewname:
        search_filter.append(['viewname', viewname])

    if gslbservicename:
        search_filter.append(['gslbservicename', gslbservicename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnsview_gslbservice_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnsview_gslbservice_binding')

    return response


def get_dnszone(zonename=None, proxymode=None, dnssecoffload=None, nsec=None, keyname=None, ns_type=None):
    '''
    Show the running configuration for the dnszone config key.

    zonename(str): Filters results that only match the zonename field.

    proxymode(str): Filters results that only match the proxymode field.

    dnssecoffload(str): Filters results that only match the dnssecoffload field.

    nsec(str): Filters results that only match the nsec field.

    keyname(list(str)): Filters results that only match the keyname field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnszone

    '''

    search_filter = []

    if zonename:
        search_filter.append(['zonename', zonename])

    if proxymode:
        search_filter.append(['proxymode', proxymode])

    if dnssecoffload:
        search_filter.append(['dnssecoffload', dnssecoffload])

    if nsec:
        search_filter.append(['nsec', nsec])

    if keyname:
        search_filter.append(['keyname', keyname])

    if ns_type:
        search_filter.append(['type', ns_type])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnszone{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnszone')

    return response


def get_dnszone_binding():
    '''
    Show the running configuration for the dnszone_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnszone_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnszone_binding'), 'dnszone_binding')

    return response


def get_dnszone_dnskey_binding(zonename=None, keyname=None):
    '''
    Show the running configuration for the dnszone_dnskey_binding config key.

    zonename(str): Filters results that only match the zonename field.

    keyname(list(str)): Filters results that only match the keyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnszone_dnskey_binding

    '''

    search_filter = []

    if zonename:
        search_filter.append(['zonename', zonename])

    if keyname:
        search_filter.append(['keyname', keyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnszone_dnskey_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnszone_dnskey_binding')

    return response


def get_dnszone_domain_binding(zonename=None, domain=None):
    '''
    Show the running configuration for the dnszone_domain_binding config key.

    zonename(str): Filters results that only match the zonename field.

    domain(str): Filters results that only match the domain field.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.get_dnszone_domain_binding

    '''

    search_filter = []

    if zonename:
        search_filter.append(['zonename', zonename])

    if domain:
        search_filter.append(['domain', domain])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dnszone_domain_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dnszone_domain_binding')

    return response


def unset_dnsaction(actionname=None, actiontype=None, ipaddress=None, ttl=None, viewname=None, preferredloclist=None,
                    dnsprofilename=None, save=False):
    '''
    Unsets values from the dnsaction configuration key.

    actionname(bool): Unsets the actionname value.

    actiontype(bool): Unsets the actiontype value.

    ipaddress(bool): Unsets the ipaddress value.

    ttl(bool): Unsets the ttl value.

    viewname(bool): Unsets the viewname value.

    preferredloclist(bool): Unsets the preferredloclist value.

    dnsprofilename(bool): Unsets the dnsprofilename value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnsaction <args>

    '''

    result = {}

    payload = {'dnsaction': {}}

    if actionname:
        payload['dnsaction']['actionname'] = True

    if actiontype:
        payload['dnsaction']['actiontype'] = True

    if ipaddress:
        payload['dnsaction']['ipaddress'] = True

    if ttl:
        payload['dnsaction']['ttl'] = True

    if viewname:
        payload['dnsaction']['viewname'] = True

    if preferredloclist:
        payload['dnsaction']['preferredloclist'] = True

    if dnsprofilename:
        payload['dnsaction']['dnsprofilename'] = True

    execution = __proxy__['citrixns.post']('config/dnsaction?action=unset', payload)

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


def unset_dnsaction64(actionname=None, prefix=None, mappedrule=None, excluderule=None, save=False):
    '''
    Unsets values from the dnsaction64 configuration key.

    actionname(bool): Unsets the actionname value.

    prefix(bool): Unsets the prefix value.

    mappedrule(bool): Unsets the mappedrule value.

    excluderule(bool): Unsets the excluderule value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnsaction64 <args>

    '''

    result = {}

    payload = {'dnsaction64': {}}

    if actionname:
        payload['dnsaction64']['actionname'] = True

    if prefix:
        payload['dnsaction64']['prefix'] = True

    if mappedrule:
        payload['dnsaction64']['mappedrule'] = True

    if excluderule:
        payload['dnsaction64']['excluderule'] = True

    execution = __proxy__['citrixns.post']('config/dnsaction64?action=unset', payload)

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


def unset_dnskey(keyname=None, publickey=None, privatekey=None, expires=None, units1=None, notificationperiod=None,
                 units2=None, ttl=None, password=None, zonename=None, keytype=None, algorithm=None, keysize=None,
                 filenameprefix=None, src=None, save=False):
    '''
    Unsets values from the dnskey configuration key.

    keyname(bool): Unsets the keyname value.

    publickey(bool): Unsets the publickey value.

    privatekey(bool): Unsets the privatekey value.

    expires(bool): Unsets the expires value.

    units1(bool): Unsets the units1 value.

    notificationperiod(bool): Unsets the notificationperiod value.

    units2(bool): Unsets the units2 value.

    ttl(bool): Unsets the ttl value.

    password(bool): Unsets the password value.

    zonename(bool): Unsets the zonename value.

    keytype(bool): Unsets the keytype value.

    algorithm(bool): Unsets the algorithm value.

    keysize(bool): Unsets the keysize value.

    filenameprefix(bool): Unsets the filenameprefix value.

    src(bool): Unsets the src value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnskey <args>

    '''

    result = {}

    payload = {'dnskey': {}}

    if keyname:
        payload['dnskey']['keyname'] = True

    if publickey:
        payload['dnskey']['publickey'] = True

    if privatekey:
        payload['dnskey']['privatekey'] = True

    if expires:
        payload['dnskey']['expires'] = True

    if units1:
        payload['dnskey']['units1'] = True

    if notificationperiod:
        payload['dnskey']['notificationperiod'] = True

    if units2:
        payload['dnskey']['units2'] = True

    if ttl:
        payload['dnskey']['ttl'] = True

    if password:
        payload['dnskey']['password'] = True

    if zonename:
        payload['dnskey']['zonename'] = True

    if keytype:
        payload['dnskey']['keytype'] = True

    if algorithm:
        payload['dnskey']['algorithm'] = True

    if keysize:
        payload['dnskey']['keysize'] = True

    if filenameprefix:
        payload['dnskey']['filenameprefix'] = True

    if src:
        payload['dnskey']['src'] = True

    execution = __proxy__['citrixns.post']('config/dnskey?action=unset', payload)

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


def unset_dnsmxrec(domain=None, mx=None, pref=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Unsets values from the dnsmxrec configuration key.

    domain(bool): Unsets the domain value.

    mx(bool): Unsets the mx value.

    pref(bool): Unsets the pref value.

    ttl(bool): Unsets the ttl value.

    ecssubnet(bool): Unsets the ecssubnet value.

    ns_type(bool): Unsets the ns_type value.

    nodeid(bool): Unsets the nodeid value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnsmxrec <args>

    '''

    result = {}

    payload = {'dnsmxrec': {}}

    if domain:
        payload['dnsmxrec']['domain'] = True

    if mx:
        payload['dnsmxrec']['mx'] = True

    if pref:
        payload['dnsmxrec']['pref'] = True

    if ttl:
        payload['dnsmxrec']['ttl'] = True

    if ecssubnet:
        payload['dnsmxrec']['ecssubnet'] = True

    if ns_type:
        payload['dnsmxrec']['type'] = True

    if nodeid:
        payload['dnsmxrec']['nodeid'] = True

    execution = __proxy__['citrixns.post']('config/dnsmxrec?action=unset', payload)

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


def unset_dnsnameserver(ip=None, dnsvservername=None, local=None, state=None, ns_type=None, dnsprofilename=None,
                        save=False):
    '''
    Unsets values from the dnsnameserver configuration key.

    ip(bool): Unsets the ip value.

    dnsvservername(bool): Unsets the dnsvservername value.

    local(bool): Unsets the local value.

    state(bool): Unsets the state value.

    ns_type(bool): Unsets the ns_type value.

    dnsprofilename(bool): Unsets the dnsprofilename value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnsnameserver <args>

    '''

    result = {}

    payload = {'dnsnameserver': {}}

    if ip:
        payload['dnsnameserver']['ip'] = True

    if dnsvservername:
        payload['dnsnameserver']['dnsvservername'] = True

    if local:
        payload['dnsnameserver']['local'] = True

    if state:
        payload['dnsnameserver']['state'] = True

    if ns_type:
        payload['dnsnameserver']['type'] = True

    if dnsprofilename:
        payload['dnsnameserver']['dnsprofilename'] = True

    execution = __proxy__['citrixns.post']('config/dnsnameserver?action=unset', payload)

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


def unset_dnsparameter(retries=None, minttl=None, maxttl=None, cacherecords=None, namelookuppriority=None,
                       recursion=None, resolutionorder=None, dnssec=None, maxpipeline=None, dnsrootreferral=None,
                       dns64timeout=None, ecsmaxsubnets=None, maxnegcachettl=None, cachehitbypass=None,
                       maxcachesize=None, maxnegativecachesize=None, cachenoexpire=None, splitpktqueryprocessing=None,
                       cacheecszeroprefix=None, save=False):
    '''
    Unsets values from the dnsparameter configuration key.

    retries(bool): Unsets the retries value.

    minttl(bool): Unsets the minttl value.

    maxttl(bool): Unsets the maxttl value.

    cacherecords(bool): Unsets the cacherecords value.

    namelookuppriority(bool): Unsets the namelookuppriority value.

    recursion(bool): Unsets the recursion value.

    resolutionorder(bool): Unsets the resolutionorder value.

    dnssec(bool): Unsets the dnssec value.

    maxpipeline(bool): Unsets the maxpipeline value.

    dnsrootreferral(bool): Unsets the dnsrootreferral value.

    dns64timeout(bool): Unsets the dns64timeout value.

    ecsmaxsubnets(bool): Unsets the ecsmaxsubnets value.

    maxnegcachettl(bool): Unsets the maxnegcachettl value.

    cachehitbypass(bool): Unsets the cachehitbypass value.

    maxcachesize(bool): Unsets the maxcachesize value.

    maxnegativecachesize(bool): Unsets the maxnegativecachesize value.

    cachenoexpire(bool): Unsets the cachenoexpire value.

    splitpktqueryprocessing(bool): Unsets the splitpktqueryprocessing value.

    cacheecszeroprefix(bool): Unsets the cacheecszeroprefix value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnsparameter <args>

    '''

    result = {}

    payload = {'dnsparameter': {}}

    if retries:
        payload['dnsparameter']['retries'] = True

    if minttl:
        payload['dnsparameter']['minttl'] = True

    if maxttl:
        payload['dnsparameter']['maxttl'] = True

    if cacherecords:
        payload['dnsparameter']['cacherecords'] = True

    if namelookuppriority:
        payload['dnsparameter']['namelookuppriority'] = True

    if recursion:
        payload['dnsparameter']['recursion'] = True

    if resolutionorder:
        payload['dnsparameter']['resolutionorder'] = True

    if dnssec:
        payload['dnsparameter']['dnssec'] = True

    if maxpipeline:
        payload['dnsparameter']['maxpipeline'] = True

    if dnsrootreferral:
        payload['dnsparameter']['dnsrootreferral'] = True

    if dns64timeout:
        payload['dnsparameter']['dns64timeout'] = True

    if ecsmaxsubnets:
        payload['dnsparameter']['ecsmaxsubnets'] = True

    if maxnegcachettl:
        payload['dnsparameter']['maxnegcachettl'] = True

    if cachehitbypass:
        payload['dnsparameter']['cachehitbypass'] = True

    if maxcachesize:
        payload['dnsparameter']['maxcachesize'] = True

    if maxnegativecachesize:
        payload['dnsparameter']['maxnegativecachesize'] = True

    if cachenoexpire:
        payload['dnsparameter']['cachenoexpire'] = True

    if splitpktqueryprocessing:
        payload['dnsparameter']['splitpktqueryprocessing'] = True

    if cacheecszeroprefix:
        payload['dnsparameter']['cacheecszeroprefix'] = True

    execution = __proxy__['citrixns.post']('config/dnsparameter?action=unset', payload)

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


def unset_dnspolicy(name=None, rule=None, viewname=None, preferredlocation=None, preferredloclist=None, drop=None,
                    cachebypass=None, actionname=None, logaction=None, save=False):
    '''
    Unsets values from the dnspolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    viewname(bool): Unsets the viewname value.

    preferredlocation(bool): Unsets the preferredlocation value.

    preferredloclist(bool): Unsets the preferredloclist value.

    drop(bool): Unsets the drop value.

    cachebypass(bool): Unsets the cachebypass value.

    actionname(bool): Unsets the actionname value.

    logaction(bool): Unsets the logaction value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnspolicy <args>

    '''

    result = {}

    payload = {'dnspolicy': {}}

    if name:
        payload['dnspolicy']['name'] = True

    if rule:
        payload['dnspolicy']['rule'] = True

    if viewname:
        payload['dnspolicy']['viewname'] = True

    if preferredlocation:
        payload['dnspolicy']['preferredlocation'] = True

    if preferredloclist:
        payload['dnspolicy']['preferredloclist'] = True

    if drop:
        payload['dnspolicy']['drop'] = True

    if cachebypass:
        payload['dnspolicy']['cachebypass'] = True

    if actionname:
        payload['dnspolicy']['actionname'] = True

    if logaction:
        payload['dnspolicy']['logaction'] = True

    execution = __proxy__['citrixns.post']('config/dnspolicy?action=unset', payload)

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


def unset_dnsprofile(dnsprofilename=None, dnsquerylogging=None, dnsanswerseclogging=None, dnsextendedlogging=None,
                     dnserrorlogging=None, cacherecords=None, cachenegativeresponses=None, dropmultiqueryrequest=None,
                     cacheecsresponses=None, save=False):
    '''
    Unsets values from the dnsprofile configuration key.

    dnsprofilename(bool): Unsets the dnsprofilename value.

    dnsquerylogging(bool): Unsets the dnsquerylogging value.

    dnsanswerseclogging(bool): Unsets the dnsanswerseclogging value.

    dnsextendedlogging(bool): Unsets the dnsextendedlogging value.

    dnserrorlogging(bool): Unsets the dnserrorlogging value.

    cacherecords(bool): Unsets the cacherecords value.

    cachenegativeresponses(bool): Unsets the cachenegativeresponses value.

    dropmultiqueryrequest(bool): Unsets the dropmultiqueryrequest value.

    cacheecsresponses(bool): Unsets the cacheecsresponses value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnsprofile <args>

    '''

    result = {}

    payload = {'dnsprofile': {}}

    if dnsprofilename:
        payload['dnsprofile']['dnsprofilename'] = True

    if dnsquerylogging:
        payload['dnsprofile']['dnsquerylogging'] = True

    if dnsanswerseclogging:
        payload['dnsprofile']['dnsanswerseclogging'] = True

    if dnsextendedlogging:
        payload['dnsprofile']['dnsextendedlogging'] = True

    if dnserrorlogging:
        payload['dnsprofile']['dnserrorlogging'] = True

    if cacherecords:
        payload['dnsprofile']['cacherecords'] = True

    if cachenegativeresponses:
        payload['dnsprofile']['cachenegativeresponses'] = True

    if dropmultiqueryrequest:
        payload['dnsprofile']['dropmultiqueryrequest'] = True

    if cacheecsresponses:
        payload['dnsprofile']['cacheecsresponses'] = True

    execution = __proxy__['citrixns.post']('config/dnsprofile?action=unset', payload)

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


def unset_dnssoarec(domain=None, originserver=None, contact=None, serial=None, refresh=None, retry=None, expire=None,
                    minimum=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Unsets values from the dnssoarec configuration key.

    domain(bool): Unsets the domain value.

    originserver(bool): Unsets the originserver value.

    contact(bool): Unsets the contact value.

    serial(bool): Unsets the serial value.

    refresh(bool): Unsets the refresh value.

    retry(bool): Unsets the retry value.

    expire(bool): Unsets the expire value.

    minimum(bool): Unsets the minimum value.

    ttl(bool): Unsets the ttl value.

    ecssubnet(bool): Unsets the ecssubnet value.

    ns_type(bool): Unsets the ns_type value.

    nodeid(bool): Unsets the nodeid value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnssoarec <args>

    '''

    result = {}

    payload = {'dnssoarec': {}}

    if domain:
        payload['dnssoarec']['domain'] = True

    if originserver:
        payload['dnssoarec']['originserver'] = True

    if contact:
        payload['dnssoarec']['contact'] = True

    if serial:
        payload['dnssoarec']['serial'] = True

    if refresh:
        payload['dnssoarec']['refresh'] = True

    if retry:
        payload['dnssoarec']['retry'] = True

    if expire:
        payload['dnssoarec']['expire'] = True

    if minimum:
        payload['dnssoarec']['minimum'] = True

    if ttl:
        payload['dnssoarec']['ttl'] = True

    if ecssubnet:
        payload['dnssoarec']['ecssubnet'] = True

    if ns_type:
        payload['dnssoarec']['type'] = True

    if nodeid:
        payload['dnssoarec']['nodeid'] = True

    execution = __proxy__['citrixns.post']('config/dnssoarec?action=unset', payload)

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


def unset_dnssrvrec(domain=None, target=None, priority=None, weight=None, port=None, ttl=None, ecssubnet=None,
                    ns_type=None, nodeid=None, save=False):
    '''
    Unsets values from the dnssrvrec configuration key.

    domain(bool): Unsets the domain value.

    target(bool): Unsets the target value.

    priority(bool): Unsets the priority value.

    weight(bool): Unsets the weight value.

    port(bool): Unsets the port value.

    ttl(bool): Unsets the ttl value.

    ecssubnet(bool): Unsets the ecssubnet value.

    ns_type(bool): Unsets the ns_type value.

    nodeid(bool): Unsets the nodeid value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnssrvrec <args>

    '''

    result = {}

    payload = {'dnssrvrec': {}}

    if domain:
        payload['dnssrvrec']['domain'] = True

    if target:
        payload['dnssrvrec']['target'] = True

    if priority:
        payload['dnssrvrec']['priority'] = True

    if weight:
        payload['dnssrvrec']['weight'] = True

    if port:
        payload['dnssrvrec']['port'] = True

    if ttl:
        payload['dnssrvrec']['ttl'] = True

    if ecssubnet:
        payload['dnssrvrec']['ecssubnet'] = True

    if ns_type:
        payload['dnssrvrec']['type'] = True

    if nodeid:
        payload['dnssrvrec']['nodeid'] = True

    execution = __proxy__['citrixns.post']('config/dnssrvrec?action=unset', payload)

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


def unset_dnszone(zonename=None, proxymode=None, dnssecoffload=None, nsec=None, keyname=None, ns_type=None, save=False):
    '''
    Unsets values from the dnszone configuration key.

    zonename(bool): Unsets the zonename value.

    proxymode(bool): Unsets the proxymode value.

    dnssecoffload(bool): Unsets the dnssecoffload value.

    nsec(bool): Unsets the nsec value.

    keyname(bool): Unsets the keyname value.

    ns_type(bool): Unsets the ns_type value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.unset_dnszone <args>

    '''

    result = {}

    payload = {'dnszone': {}}

    if zonename:
        payload['dnszone']['zonename'] = True

    if proxymode:
        payload['dnszone']['proxymode'] = True

    if dnssecoffload:
        payload['dnszone']['dnssecoffload'] = True

    if nsec:
        payload['dnszone']['nsec'] = True

    if keyname:
        payload['dnszone']['keyname'] = True

    if ns_type:
        payload['dnszone']['type'] = True

    execution = __proxy__['citrixns.post']('config/dnszone?action=unset', payload)

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


def update_dnsaction(actionname=None, actiontype=None, ipaddress=None, ttl=None, viewname=None, preferredloclist=None,
                     dnsprofilename=None, save=False):
    '''
    Update the running configuration for the dnsaction config key.

    actionname(str): Name of the dns action.

    actiontype(str): The type of DNS action that is being configured. Possible values = ViewName, GslbPrefLoc, noop, Drop,
        Cache_Bypass, Rewrite_Response

    ipaddress(list(str)): List of IP address to be returned in case of rewrite_response actiontype. They can be of IPV4 or
        IPV6 type.  In case of set command We will remove all the IP address previously present in the action and will
        add new once given in set dns action command.

    ttl(int): Time to live, in seconds. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    viewname(str): The view name that must be used for the given action.

    preferredloclist(list(str)): The location list in priority order used for the given action. Minimum length = 1

    dnsprofilename(str): Name of the DNS profile to be associated with the transaction for which the action is chosen.
        Minimum length = 1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnsaction <args>

    '''

    result = {}

    payload = {'dnsaction': {}}

    if actionname:
        payload['dnsaction']['actionname'] = actionname

    if actiontype:
        payload['dnsaction']['actiontype'] = actiontype

    if ipaddress:
        payload['dnsaction']['ipaddress'] = ipaddress

    if ttl:
        payload['dnsaction']['ttl'] = ttl

    if viewname:
        payload['dnsaction']['viewname'] = viewname

    if preferredloclist:
        payload['dnsaction']['preferredloclist'] = preferredloclist

    if dnsprofilename:
        payload['dnsaction']['dnsprofilename'] = dnsprofilename

    execution = __proxy__['citrixns.put']('config/dnsaction', payload)

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


def update_dnsaction64(actionname=None, prefix=None, mappedrule=None, excluderule=None, save=False):
    '''
    Update the running configuration for the dnsaction64 config key.

    actionname(str): Name of the dns64 action.

    prefix(str): The dns64 prefix to be used if the after evaluating the rules.

    mappedrule(str): The expression to select the criteria for ipv4 addresses to be used for synthesis.  Only if the
        mappedrule is evaluated to true the corresponding ipv4 address is used for synthesis using respective prefix,
        otherwise the A RR is discarded.

    excluderule(str): The expression to select the criteria for eliminating the corresponding ipv6 addresses from the
        response.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnsaction64 <args>

    '''

    result = {}

    payload = {'dnsaction64': {}}

    if actionname:
        payload['dnsaction64']['actionname'] = actionname

    if prefix:
        payload['dnsaction64']['prefix'] = prefix

    if mappedrule:
        payload['dnsaction64']['mappedrule'] = mappedrule

    if excluderule:
        payload['dnsaction64']['excluderule'] = excluderule

    execution = __proxy__['citrixns.put']('config/dnsaction64', payload)

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


def update_dnskey(keyname=None, publickey=None, privatekey=None, expires=None, units1=None, notificationperiod=None,
                  units2=None, ttl=None, password=None, zonename=None, keytype=None, algorithm=None, keysize=None,
                  filenameprefix=None, src=None, save=False):
    '''
    Update the running configuration for the dnskey config key.

    keyname(str): Name of the public-private key pair to publish in the zone. Minimum length = 1

    publickey(str): File name of the public key.

    privatekey(str): File name of the private key.

    expires(int): Time period for which to consider the key valid, after the key is used to sign a zone. Default value: 120
        Minimum value = 1 Maximum value = 32767

    units1(str): Units for the expiry period. Default value: DAYS Possible values = MINUTES, HOURS, DAYS

    notificationperiod(int): Time at which to generate notification of key expiration, specified as number of days, hours, or
        minutes before expiry. Must be less than the expiry period. The notification is an SNMP trap sent to an SNMP
        manager. To enable the appliance to send the trap, enable the DNSKEY-EXPIRY SNMP alarm. Default value: 7 Minimum
        value = 1 Maximum value = 32767

    units2(str): Units for the notification period. Default value: DAYS Possible values = MINUTES, HOURS, DAYS

    ttl(int): Time to Live (TTL), in seconds, for the DNSKEY resource record created in the zone. TTL is the time for which
        the record must be cached by the DNS proxies. If the TTL is not specified, either the DNS zones minimum TTL or
        the default value of 3600 is used. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    password(str): Passphrase for reading the encrypted public/private DNS keys. Minimum length = 1

    zonename(str): Name of the zone for which to create a key. Minimum length = 1

    keytype(str): Type of key to create. Default value: NS_DNSKEY_ZSK Possible values = KSK, KeySigningKey, ZSK,
        ZoneSigningKey

    algorithm(str): Algorithm to generate for zone signing. Default value: NS_DNSKEYALGO_RSASHA1 Possible values = RSASHA1

    keysize(int): Size of the key, in bits. Default value: 512

    filenameprefix(str): Common prefix for the names of the generated public and private key files and the Delegation Signer
        (DS) resource record. During key generation, the .key, .private, and .ds suffixes are appended automatically to
        the file name prefix to produce the names of the public key, the private key, and the DS record, respectively.

    src(str): URL (protocol, host, path, and file name) from where the DNS key file will be imported. NOTE: The import fails
        if the object to be imported is on an HTTPS server that requires client certificate authentication for access.
        This is a mandatory argument. Minimum length = 1 Maximum length = 2047

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnskey <args>

    '''

    result = {}

    payload = {'dnskey': {}}

    if keyname:
        payload['dnskey']['keyname'] = keyname

    if publickey:
        payload['dnskey']['publickey'] = publickey

    if privatekey:
        payload['dnskey']['privatekey'] = privatekey

    if expires:
        payload['dnskey']['expires'] = expires

    if units1:
        payload['dnskey']['units1'] = units1

    if notificationperiod:
        payload['dnskey']['notificationperiod'] = notificationperiod

    if units2:
        payload['dnskey']['units2'] = units2

    if ttl:
        payload['dnskey']['ttl'] = ttl

    if password:
        payload['dnskey']['password'] = password

    if zonename:
        payload['dnskey']['zonename'] = zonename

    if keytype:
        payload['dnskey']['keytype'] = keytype

    if algorithm:
        payload['dnskey']['algorithm'] = algorithm

    if keysize:
        payload['dnskey']['keysize'] = keysize

    if filenameprefix:
        payload['dnskey']['filenameprefix'] = filenameprefix

    if src:
        payload['dnskey']['src'] = src

    execution = __proxy__['citrixns.put']('config/dnskey', payload)

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


def update_dnsmxrec(domain=None, mx=None, pref=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Update the running configuration for the dnsmxrec config key.

    domain(str): Domain name for which to add the MX record. Minimum length = 1

    mx(str): Host name of the mail exchange server. Minimum length = 1

    pref(int): Priority number to assign to the mail exchange server. A domain name can have multiple mail servers, with a
        priority number assigned to each server. The lower the priority number, the higher the mail servers priority.
        When other mail servers have to deliver mail to the specified domain, they begin with the mail server with the
        lowest priority number, and use other configured mail servers, in priority order, as backups. Minimum value = 0
        Maximum value = 65535

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached MX record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Default value:
        ADNS Possible values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnsmxrec <args>

    '''

    result = {}

    payload = {'dnsmxrec': {}}

    if domain:
        payload['dnsmxrec']['domain'] = domain

    if mx:
        payload['dnsmxrec']['mx'] = mx

    if pref:
        payload['dnsmxrec']['pref'] = pref

    if ttl:
        payload['dnsmxrec']['ttl'] = ttl

    if ecssubnet:
        payload['dnsmxrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnsmxrec']['type'] = ns_type

    if nodeid:
        payload['dnsmxrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.put']('config/dnsmxrec', payload)

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


def update_dnsnameserver(ip=None, dnsvservername=None, local=None, state=None, ns_type=None, dnsprofilename=None,
                         save=False):
    '''
    Update the running configuration for the dnsnameserver config key.

    ip(str): IP address of an external name server or, if the Local parameter is set, IP address of a local DNS server
        (LDNS). Minimum length = 1

    dnsvservername(str): Name of a DNS virtual server. Overrides any IP address-based name servers configured on the
        NetScaler appliance. Minimum length = 1

    local(bool): Mark the IP address as one that belongs to a local recursive DNS server on the NetScaler appliance. The
        appliance recursively resolves queries received on an IP address that is marked as being local. For recursive
        resolution to work, the global DNS parameter, Recursion, must also be set.   If no name server is marked as being
        local, the appliance functions as a stub resolver and load balances the name servers.

    state(str): Administrative state of the name server. Default value: ENABLED Possible values = ENABLED, DISABLED

    ns_type(str): Protocol used by the name server. UDP_TCP is not valid if the name server is a DNS virtual server
        configured on the appliance. Default value: UDP Possible values = UDP, TCP, UDP_TCP

    dnsprofilename(str): Name of the DNS profile to be associated with the name server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnsnameserver <args>

    '''

    result = {}

    payload = {'dnsnameserver': {}}

    if ip:
        payload['dnsnameserver']['ip'] = ip

    if dnsvservername:
        payload['dnsnameserver']['dnsvservername'] = dnsvservername

    if local:
        payload['dnsnameserver']['local'] = local

    if state:
        payload['dnsnameserver']['state'] = state

    if ns_type:
        payload['dnsnameserver']['type'] = ns_type

    if dnsprofilename:
        payload['dnsnameserver']['dnsprofilename'] = dnsprofilename

    execution = __proxy__['citrixns.put']('config/dnsnameserver', payload)

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


def update_dnsparameter(retries=None, minttl=None, maxttl=None, cacherecords=None, namelookuppriority=None,
                        recursion=None, resolutionorder=None, dnssec=None, maxpipeline=None, dnsrootreferral=None,
                        dns64timeout=None, ecsmaxsubnets=None, maxnegcachettl=None, cachehitbypass=None,
                        maxcachesize=None, maxnegativecachesize=None, cachenoexpire=None, splitpktqueryprocessing=None,
                        cacheecszeroprefix=None, save=False):
    '''
    Update the running configuration for the dnsparameter config key.

    retries(int): Maximum number of retry attempts when no response is received for a query sent to a name server. Applies to
        end resolver and forwarder configurations. Default value: 5 Minimum value = 1 Maximum value = 5

    minttl(int): Minimum permissible time to live (TTL) for all records cached in the DNS cache by DNS proxy, end resolver,
        and forwarder configurations. If the TTL of a record that is to be cached is lower than the value configured for
        minTTL, the TTL of the record is set to the value of minTTL before caching. When you modify this setting, the new
        value is applied only to those records that are cached after the modification. The TTL values of existing records
        are not changed. Minimum value = 0 Maximum value = 604800

    maxttl(int): Maximum time to live (TTL) for all records cached in the DNS cache by DNS proxy, end resolver, and forwarder
        configurations. If the TTL of a record that is to be cached is higher than the value configured for maxTTL, the
        TTL of the record is set to the value of maxTTL before caching. When you modify this setting, the new value is
        applied only to those records that are cached after the modification. The TTL values of existing records are not
        changed. Default value: 604800 Minimum value = 1 Maximum value = 604800

    cacherecords(str): Cache resource records in the DNS cache. Applies to resource records obtained through proxy
        configurations only. End resolver and forwarder configurations always cache records in the DNS cache, and you
        cannot disable this behavior. When you disable record caching, the appliance stops caching server responses.
        However, cached records are not flushed. The appliance does not serve requests from the cache until record
        caching is enabled again. Default value: YES Possible values = YES, NO

    namelookuppriority(str): Type of lookup (DNS or WINS) to attempt first. If the first-priority lookup fails, the
        second-priority lookup is attempted. Used only by the SSL VPN feature. Default value: WINS Possible values =
        WINS, DNS

    recursion(str): Function as an end resolver and recursively resolve queries for domains that are not hosted on the
        NetScaler appliance. Also resolve queries recursively when the external name servers configured on the appliance
        (for a forwarder configuration) are unavailable. When external name servers are unavailable, the appliance
        queries a root server and resolves the request recursively, as it does for an end resolver configuration. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    resolutionorder(str): Type of DNS queries (A, AAAA, or both) to generate during the routine functioning of certain
        NetScaler features, such as SSL VPN, cache redirection, and the integrated cache. The queries are sent to the
        external name servers that are configured for the forwarder function. If you specify both query types, you can
        also specify the order. Available settings function as follows: * OnlyAQuery. Send queries for IPv4 address
        records (A records) only.  * OnlyAAAAQuery. Send queries for IPv6 address records (AAAA records) instead of
        queries for IPv4 address records (A records). * AThenAAAAQuery. Send a query for an A record, and then send a
        query for an AAAA record if the query for the A record results in a NODATA response from the name server. *
        AAAAThenAQuery. Send a query for an AAAA record, and then send a query for an A record if the query for the AAAA
        record results in a NODATA response from the name server. Default value: OnlyAQuery Possible values = OnlyAQuery,
        OnlyAAAAQuery, AThenAAAAQuery, AAAAThenAQuery

    dnssec(str): Enable or disable the Domain Name System Security Extensions (DNSSEC) feature on the appliance. Note: Even
        when the DNSSEC feature is enabled, forwarder configurations (used by internal NetScaler features such as SSL VPN
        and Cache Redirection for name resolution) do not support the DNSSEC OK (DO) bit in the EDNS0 OPT header. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    maxpipeline(int): Maximum number of concurrent DNS requests to allow on a single client connection, which is identified
        by the ;lt;clientip:port;gt;-;lt;vserver ip:port;gt; tuple. A value of 0 (zero) applies no limit to the number of
        concurrent DNS requests allowed on a single client connection.

    dnsrootreferral(str): Send a root referral if a client queries a domain name that is unrelated to the domains
        configured/cached on the NetScaler appliance. If the setting is disabled, the appliance sends a blank response
        instead of a root referral. Applicable to domains for which the appliance is authoritative. Disable the parameter
        when the appliance is under attack from a client that is sending a flood of queries for unrelated domains.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    dns64timeout(int): While doing DNS64 resolution, this parameter specifies the time to wait before sending an A query if
        no response is received from backend DNS server for AAAA query. Minimum value = 0 Maximum value = 10000

    ecsmaxsubnets(int): Maximum number of subnets that can be cached corresponding to a single domain. Subnet caching will
        occur for responses with EDNS Client Subnet (ECS) option. Caching of such responses can be disabled using DNS
        profile settings. A value of zero indicates that the number of subnets cached is limited only by existing memory
        constraints. The default value is zero. Default value: 0 Minimum value = 0 Maximum value = 1280

    maxnegcachettl(int): Maximum time to live (TTL) for all negative records ( NXDONAIN and NODATA ) cached in the DNS cache
        by DNS proxy, end resolver, and forwarder configurations. If the TTL of a record that is to be cached is higher
        than the value configured for maxnegcacheTTL, the TTL of the record is set to the value of maxnegcacheTTL before
        caching. When you modify this setting, the new value is applied only to those records that are cached after the
        modification. The TTL values of existing records are not changed. Default value: 604800 Minimum value = 1 Maximum
        value = 604800

    cachehitbypass(str): This parameter is applicable only in proxy mode and if this parameter is enabled we will forward all
        the client requests to the backend DNS server and the response served will be cached on netscaler. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    maxcachesize(int): Maximum memory, in megabytes, that can be used for dns caching per Packet Engine.

    maxnegativecachesize(int): Maximum memory, in megabytes, that can be used for caching of negative DNS responses per
        packet engine.

    cachenoexpire(str): If this flag is set to YES, the existing entries in cache do not age out. On reaching the max limit
        the cache records are frozen. Default value: DISABLED Possible values = ENABLED, DISABLED

    splitpktqueryprocessing(str): Processing requests split across multiple packets. Default value: ALLOW Possible values =
        ALLOW, DROP

    cacheecszeroprefix(str): Cache ECS responses with a Scope Prefix length of zero. Such a cached response will be used for
        all queries with this domain name and any subnet. When disabled, ECS responses with Scope Prefix length of zero
        will be cached, but not tied to any subnet. This option has no effect if caching of ECS responses is disabled in
        the corresponding DNS profile. Default value: ENABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnsparameter <args>

    '''

    result = {}

    payload = {'dnsparameter': {}}

    if retries:
        payload['dnsparameter']['retries'] = retries

    if minttl:
        payload['dnsparameter']['minttl'] = minttl

    if maxttl:
        payload['dnsparameter']['maxttl'] = maxttl

    if cacherecords:
        payload['dnsparameter']['cacherecords'] = cacherecords

    if namelookuppriority:
        payload['dnsparameter']['namelookuppriority'] = namelookuppriority

    if recursion:
        payload['dnsparameter']['recursion'] = recursion

    if resolutionorder:
        payload['dnsparameter']['resolutionorder'] = resolutionorder

    if dnssec:
        payload['dnsparameter']['dnssec'] = dnssec

    if maxpipeline:
        payload['dnsparameter']['maxpipeline'] = maxpipeline

    if dnsrootreferral:
        payload['dnsparameter']['dnsrootreferral'] = dnsrootreferral

    if dns64timeout:
        payload['dnsparameter']['dns64timeout'] = dns64timeout

    if ecsmaxsubnets:
        payload['dnsparameter']['ecsmaxsubnets'] = ecsmaxsubnets

    if maxnegcachettl:
        payload['dnsparameter']['maxnegcachettl'] = maxnegcachettl

    if cachehitbypass:
        payload['dnsparameter']['cachehitbypass'] = cachehitbypass

    if maxcachesize:
        payload['dnsparameter']['maxcachesize'] = maxcachesize

    if maxnegativecachesize:
        payload['dnsparameter']['maxnegativecachesize'] = maxnegativecachesize

    if cachenoexpire:
        payload['dnsparameter']['cachenoexpire'] = cachenoexpire

    if splitpktqueryprocessing:
        payload['dnsparameter']['splitpktqueryprocessing'] = splitpktqueryprocessing

    if cacheecszeroprefix:
        payload['dnsparameter']['cacheecszeroprefix'] = cacheecszeroprefix

    execution = __proxy__['citrixns.put']('config/dnsparameter', payload)

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


def update_dnspolicy(name=None, rule=None, viewname=None, preferredlocation=None, preferredloclist=None, drop=None,
                     cachebypass=None, actionname=None, logaction=None, save=False):
    '''
    Update the running configuration for the dnspolicy config key.

    name(str): Name for the DNS policy.

    rule(str): Expression against which DNS traffic is evaluated. Written in the default syntax. Note: * On the command line
        interface, if the expression includes blank spaces, the entire expression must be enclosed in double quotation
        marks. * If the expression itself includes double quotation marks, you must escape the quotations by using the
        character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks.  Maximum length of a string literal in the expression is 255
        characters. A longer string can be split into smaller strings of up to 255 characters each, and the smaller
        strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" Example:
        CLIENT.UDP.DNS.DOMAIN.EQ("domainname").

    viewname(str): The view name that must be used for the given policy.

    preferredlocation(str): The location used for the given policy. This is deprecated attribute. Please use -prefLocList.

    preferredloclist(list(str)): The location list in priority order used for the given policy. Minimum length = 1

    drop(str): The dns packet must be dropped. Possible values = YES, NO

    cachebypass(str): By pass dns cache for this. Possible values = YES, NO

    actionname(str): Name of the DNS action to perform when the rule evaluates to TRUE. The built in actions function as
        follows: * dns_default_act_Drop. Drop the DNS request. * dns_default_act_Cachebypass. Bypass the DNS cache and
        forward the request to the name server. You can create custom actions by using the add dns action command in the
        CLI or the DNS ;gt; Actions ;gt; Create DNS Action dialog box in the NetScaler configuration utility.

    logaction(str): Name of the messagelog action to use for requests that match this policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnspolicy <args>

    '''

    result = {}

    payload = {'dnspolicy': {}}

    if name:
        payload['dnspolicy']['name'] = name

    if rule:
        payload['dnspolicy']['rule'] = rule

    if viewname:
        payload['dnspolicy']['viewname'] = viewname

    if preferredlocation:
        payload['dnspolicy']['preferredlocation'] = preferredlocation

    if preferredloclist:
        payload['dnspolicy']['preferredloclist'] = preferredloclist

    if drop:
        payload['dnspolicy']['drop'] = drop

    if cachebypass:
        payload['dnspolicy']['cachebypass'] = cachebypass

    if actionname:
        payload['dnspolicy']['actionname'] = actionname

    if logaction:
        payload['dnspolicy']['logaction'] = logaction

    execution = __proxy__['citrixns.put']('config/dnspolicy', payload)

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


def update_dnspolicy64(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the dnspolicy64 config key.

    name(str): Name for the DNS64 policy.

    rule(str): Expression against which DNS traffic is evaluated. Written in the default syntax. Note: * On the command line
        interface, if the expression includes blank spaces, the entire expression must be enclosed in double quotation
        marks. * If the expression itself includes double quotation marks, you must escape the quotations by using the
        character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case you do not
        have to escape the double quotation marks.  Maximum length of a string literal in the expression is 255
        characters. A longer string can be split into smaller strings of up to 255 characters each, and the smaller
        strings concatenated with the + operator. For example, you can create a 500-character string as follows:
        ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" Example:
        CLIENT.IP.SRC.IN_SUBENT(23.34.0.0/16).

    action(str): Name of the DNS64 action to perform when the rule evaluates to TRUE. The built in actions function as
        follows: * A default dns64 action with prefix ;lt;default prefix;gt; and mapped and exclude are any  You can
        create custom actions by using the add dns action command in the CLI or the DNS64 ;gt; Actions ;gt; Create DNS64
        Action dialog box in the NetScaler configuration utility.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnspolicy64 <args>

    '''

    result = {}

    payload = {'dnspolicy64': {}}

    if name:
        payload['dnspolicy64']['name'] = name

    if rule:
        payload['dnspolicy64']['rule'] = rule

    if action:
        payload['dnspolicy64']['action'] = action

    execution = __proxy__['citrixns.put']('config/dnspolicy64', payload)

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


def update_dnsprofile(dnsprofilename=None, dnsquerylogging=None, dnsanswerseclogging=None, dnsextendedlogging=None,
                      dnserrorlogging=None, cacherecords=None, cachenegativeresponses=None, dropmultiqueryrequest=None,
                      cacheecsresponses=None, save=False):
    '''
    Update the running configuration for the dnsprofile config key.

    dnsprofilename(str): Name of the DNS profile. Minimum length = 1 Maximum length = 127

    dnsquerylogging(str): DNS query logging; if enabled, DNS query information such as DNS query id, DNS query flags , DNS
        domain name and DNS query type will be logged. Default value: DISABLED Possible values = ENABLED, DISABLED

    dnsanswerseclogging(str): DNS answer section; if enabled, answer section in the response will be logged. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    dnsextendedlogging(str): DNS extended logging; if enabled, authority and additional section in the response will be
        logged. Default value: DISABLED Possible values = ENABLED, DISABLED

    dnserrorlogging(str): DNS error logging; if enabled, whenever error is encountered in DNS module reason for the error
        will be logged. Default value: DISABLED Possible values = ENABLED, DISABLED

    cacherecords(str): Cache resource records in the DNS cache. Applies to resource records obtained through proxy
        configurations only. End resolver and forwarder configurations always cache records in the DNS cache, and you
        cannot disable this behavior. When you disable record caching, the appliance stops caching server responses.
        However, cached records are not flushed. The appliance does not serve requests from the cache until record
        caching is enabled again. Default value: ENABLED Possible values = ENABLED, DISABLED

    cachenegativeresponses(str): Cache negative responses in the DNS cache. When disabled, the appliance stops caching
        negative responses except referral records. This applies to all configurations - proxy, end resolver, and
        forwarder. However, cached responses are not flushed. The appliance does not serve negative responses from the
        cache until this parameter is enabled again. Default value: ENABLED Possible values = ENABLED, DISABLED

    dropmultiqueryrequest(str): Drop the DNS requests containing multiple queries. When enabled, DNS requests containing
        multiple queries will be dropped. In case of proxy configuration by default the DNS request containing multiple
        queries is forwarded to the backend and in case of ADNS and Resolver configuration NOCODE error response will be
        sent to the client. Default value: DISABLED Possible values = ENABLED, DISABLED

    cacheecsresponses(str): Cache DNS responses with EDNS Client Subnet(ECS) option in the DNS cache. When disabled, the
        appliance stops caching responses with ECS option. This is relevant to proxy configuration. Enabling/disabling
        support of ECS option when NetScaler is authoritative for a GSLB domain is supported using a knob in GSLB
        vserver. In all other modes, ECS option is ignored. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnsprofile <args>

    '''

    result = {}

    payload = {'dnsprofile': {}}

    if dnsprofilename:
        payload['dnsprofile']['dnsprofilename'] = dnsprofilename

    if dnsquerylogging:
        payload['dnsprofile']['dnsquerylogging'] = dnsquerylogging

    if dnsanswerseclogging:
        payload['dnsprofile']['dnsanswerseclogging'] = dnsanswerseclogging

    if dnsextendedlogging:
        payload['dnsprofile']['dnsextendedlogging'] = dnsextendedlogging

    if dnserrorlogging:
        payload['dnsprofile']['dnserrorlogging'] = dnserrorlogging

    if cacherecords:
        payload['dnsprofile']['cacherecords'] = cacherecords

    if cachenegativeresponses:
        payload['dnsprofile']['cachenegativeresponses'] = cachenegativeresponses

    if dropmultiqueryrequest:
        payload['dnsprofile']['dropmultiqueryrequest'] = dropmultiqueryrequest

    if cacheecsresponses:
        payload['dnsprofile']['cacheecsresponses'] = cacheecsresponses

    execution = __proxy__['citrixns.put']('config/dnsprofile', payload)

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


def update_dnssoarec(domain=None, originserver=None, contact=None, serial=None, refresh=None, retry=None, expire=None,
                     minimum=None, ttl=None, ecssubnet=None, ns_type=None, nodeid=None, save=False):
    '''
    Update the running configuration for the dnssoarec config key.

    domain(str): Domain name for which to add the SOA record. Minimum length = 1

    originserver(str): Domain name of the name server that responds authoritatively for the domain. Minimum length = 1

    contact(str): Email address of the contact to whom domain issues can be addressed. In the email address, replace the @
        sign with a period (.). For example, enter domainadmin.example.com instead of domainadmin@example.com. Minimum
        length = 1

    serial(int): The secondary server uses this parameter to determine whether it requires a zone transfer from the primary
        server. Default value: 100 Minimum value = 0 Maximum value = 4294967294

    refresh(int): Time, in seconds, for which a secondary server must wait between successive checks on the value of the
        serial number. Default value: 3600 Minimum value = 0 Maximum value = 4294967294

    retry(int): Time, in seconds, between retries if a secondary servers attempt to contact the primary server for a zone
        refresh fails. Default value: 3 Minimum value = 0 Maximum value = 4294967294

    expire(int): Time, in seconds, after which the zone data on a secondary name server can no longer be considered
        authoritative because all refresh and retry attempts made during the period have failed. After the expiry period,
        the secondary server stops serving the zone. Typically one week. Not used by the primary server. Default value:
        3600 Minimum value = 0 Maximum value = 4294967294

    minimum(int): Default time to live (TTL) for all records in the zone. Can be overridden for individual records. Default
        value: 5 Minimum value = 0 Maximum value = 2147483647

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached SOA record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Possible
        values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnssoarec <args>

    '''

    result = {}

    payload = {'dnssoarec': {}}

    if domain:
        payload['dnssoarec']['domain'] = domain

    if originserver:
        payload['dnssoarec']['originserver'] = originserver

    if contact:
        payload['dnssoarec']['contact'] = contact

    if serial:
        payload['dnssoarec']['serial'] = serial

    if refresh:
        payload['dnssoarec']['refresh'] = refresh

    if retry:
        payload['dnssoarec']['retry'] = retry

    if expire:
        payload['dnssoarec']['expire'] = expire

    if minimum:
        payload['dnssoarec']['minimum'] = minimum

    if ttl:
        payload['dnssoarec']['ttl'] = ttl

    if ecssubnet:
        payload['dnssoarec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnssoarec']['type'] = ns_type

    if nodeid:
        payload['dnssoarec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.put']('config/dnssoarec', payload)

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


def update_dnssrvrec(domain=None, target=None, priority=None, weight=None, port=None, ttl=None, ecssubnet=None,
                     ns_type=None, nodeid=None, save=False):
    '''
    Update the running configuration for the dnssrvrec config key.

    domain(str): Domain name, which, by convention, is prefixed by the symbolic name of the desired service and the symbolic
        name of the desired protocol, each with an underscore (_) prepended. For example, if an SRV-aware client wants to
        discover a SIP service that is provided over UDP, in the domain example.com, the client performs a lookup for
        _sip._udp.example.com. Minimum length = 1

    target(str): Target host for the specified service.

    priority(int): Integer specifying the priority of the target host. The lower the number, the higher the priority. If
        multiple target hosts have the same priority, selection is based on the Weight parameter. Minimum value = 0
        Maximum value = 65535

    weight(int): Weight for the target host. Aids host selection when two or more hosts have the same priority. A larger
        number indicates greater weight. Minimum value = 0 Maximum value = 65535

    port(int): Port on which the target host listens for client requests. Minimum value = 0 Maximum value = 65535

    ttl(int): Time to Live (TTL), in seconds, for the record. TTL is the time for which the record must be cached by DNS
        proxies. The specified TTL is applied to all the resource records that are of the same record type and belong to
        the specified domain name. For example, if you add an address record, with a TTL of 36000, to the domain name
        example.com, the TTLs of all the address records of example.com are changed to 36000. If the TTL is not
        specified, the NetScaler appliance uses either the DNS zones minimum TTL or, if the SOA record is not available
        on the appliance, the default value of 3600. Default value: 3600 Minimum value = 0 Maximum value = 2147483647

    ecssubnet(str): Subnet for which the cached SRV record need to be removed.

    ns_type(str): Type of records to display. Available settings function as follows: * ADNS - Display all authoritative
        address records. * PROXY - Display all proxy address records. * ALL - Display all address records. Possible
        values = ALL, ADNS, PROXY

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnssrvrec <args>

    '''

    result = {}

    payload = {'dnssrvrec': {}}

    if domain:
        payload['dnssrvrec']['domain'] = domain

    if target:
        payload['dnssrvrec']['target'] = target

    if priority:
        payload['dnssrvrec']['priority'] = priority

    if weight:
        payload['dnssrvrec']['weight'] = weight

    if port:
        payload['dnssrvrec']['port'] = port

    if ttl:
        payload['dnssrvrec']['ttl'] = ttl

    if ecssubnet:
        payload['dnssrvrec']['ecssubnet'] = ecssubnet

    if ns_type:
        payload['dnssrvrec']['type'] = ns_type

    if nodeid:
        payload['dnssrvrec']['nodeid'] = nodeid

    execution = __proxy__['citrixns.put']('config/dnssrvrec', payload)

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


def update_dnszone(zonename=None, proxymode=None, dnssecoffload=None, nsec=None, keyname=None, ns_type=None,
                   save=False):
    '''
    Update the running configuration for the dnszone config key.

    zonename(str): Name of the zone to create. Minimum length = 1

    proxymode(str): Deploy the zone in proxy mode. Enable in the following scenarios: * The load balanced DNS servers are
        authoritative for the zone and all resource records that are part of the zone.  * The load balanced DNS servers
        are authoritative for the zone, but the NetScaler appliance owns a subset of the resource records that belong to
        the zone (partial zone ownership configuration). Typically seen in global server load balancing (GSLB)
        configurations, in which the appliance responds authoritatively to queries for GSLB domain names but forwards
        queries for other domain names in the zone to the load balanced servers. In either scenario, do not create the
        zones Start of Authority (SOA) and name server (NS) resource records on the appliance.  Disable if the appliance
        is authoritative for the zone, but make sure that you have created the SOA and NS records on the appliance before
        you create the zone. Default value: ENABLED Possible values = YES, NO

    dnssecoffload(str): Enable dnssec offload for this zone. Default value: DISABLED Possible values = ENABLED, DISABLED

    nsec(str): Enable nsec generation for dnssec offload. Default value: DISABLED Possible values = ENABLED, DISABLED

    keyname(list(str)): Name of the public/private DNS key pair with which to sign the zone. You can sign a zone with up to
        four keys. Minimum length = 1

    ns_type(str): Type of zone to display. Mutually exclusive with the DNS Zone (zoneName) parameter. Available settings
        function as follows: * ADNS - Display all the zones for which the NetScaler appliance is authoritative. * PROXY -
        Display all the zones for which the NetScaler appliance is functioning as a proxy server. * ALL - Display all the
        zones configured on the appliance. Possible values = ALL, ADNS, PROXY

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' domain_name_service.update_dnszone <args>

    '''

    result = {}

    payload = {'dnszone': {}}

    if zonename:
        payload['dnszone']['zonename'] = zonename

    if proxymode:
        payload['dnszone']['proxymode'] = proxymode

    if dnssecoffload:
        payload['dnszone']['dnssecoffload'] = dnssecoffload

    if nsec:
        payload['dnszone']['nsec'] = nsec

    if keyname:
        payload['dnszone']['keyname'] = keyname

    if ns_type:
        payload['dnszone']['type'] = ns_type

    execution = __proxy__['citrixns.put']('config/dnszone', payload)

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
