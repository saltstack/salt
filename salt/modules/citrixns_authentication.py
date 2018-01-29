# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the authentication key.

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

__virtualname__ = 'authentication'


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

    return False, 'The authentication execution module can only be loaded for citrixns proxy minions.'


def add_authenticationauthnprofile(name=None, authnvsname=None, authenticationhost=None, authenticationdomain=None,
                                   authenticationlevel=None, save=False):
    '''
    Add a new authenticationauthnprofile to the running configuration.

    name(str): Name for the authentication profile.  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the RADIUS action is added. Minimum length = 1

    authnvsname(str): Name of the authentication vserver at which authentication should be done. Minimum length = 1 Maximum
        length = 128

    authenticationhost(str): Hostname of the authentication vserver to which user must be redirected for authentication.
        Minimum length = 1 Maximum length = 256

    authenticationdomain(str): Domain for which TM cookie must to be set. If unspecified, cookie will be set for FQDN.
        Minimum length = 1 Maximum length = 256

    authenticationlevel(int): Authentication weight or level of the vserver to which this will bound. This is used to order
        TM vservers based on the protection required. A session that is created by authenticating against TM vserver at
        given level cannot be used to access TM vserver at a higher level. Minimum value = 0 Maximum value = 255

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationauthnprofile <args>

    '''

    result = {}

    payload = {'authenticationauthnprofile': {}}

    if name:
        payload['authenticationauthnprofile']['name'] = name

    if authnvsname:
        payload['authenticationauthnprofile']['authnvsname'] = authnvsname

    if authenticationhost:
        payload['authenticationauthnprofile']['authenticationhost'] = authenticationhost

    if authenticationdomain:
        payload['authenticationauthnprofile']['authenticationdomain'] = authenticationdomain

    if authenticationlevel:
        payload['authenticationauthnprofile']['authenticationlevel'] = authenticationlevel

    execution = __proxy__['citrixns.post']('config/authenticationauthnprofile', payload)

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


def add_authenticationcertaction(name=None, twofactor=None, usernamefield=None, groupnamefield=None,
                                 defaultauthenticationgroup=None, save=False):
    '''
    Add a new authenticationcertaction to the running configuration.

    name(str): Name for the client cert authentication server profile (action).  Must begin with a letter, number, or the
        underscore character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space
        ( ), at (@), equals (=), colon (:), and underscore characters. Cannot be changed after certifcate action is
        created.  The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my authentication action" or my
        authentication action). Minimum length = 1

    twofactor(str): Enables or disables two-factor authentication.  Two factor authentication is client cert authentication
        followed by password authentication. Default value: OFF Possible values = ON, OFF

    usernamefield(str): Client-cert field from which the username is extracted. Must be set to either ""Subject"" and
        ""Issuer"" (include both sets of double quotation marks). Format: ;lt;field;gt;:;lt;subfield;gt;. Minimum length
        = 1

    groupnamefield(str): Client-cert field from which the group is extracted. Must be set to either ""Subject"" and
        ""Issuer"" (include both sets of double quotation marks). Format: ;lt;field;gt;:;lt;subfield;gt;. Minimum length
        = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationcertaction <args>

    '''

    result = {}

    payload = {'authenticationcertaction': {}}

    if name:
        payload['authenticationcertaction']['name'] = name

    if twofactor:
        payload['authenticationcertaction']['twofactor'] = twofactor

    if usernamefield:
        payload['authenticationcertaction']['usernamefield'] = usernamefield

    if groupnamefield:
        payload['authenticationcertaction']['groupnamefield'] = groupnamefield

    if defaultauthenticationgroup:
        payload['authenticationcertaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.post']('config/authenticationcertaction', payload)

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


def add_authenticationcertpolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Add a new authenticationcertpolicy to the running configuration.

    name(str): Name for the client certificate authentication policy.  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters. Cannot be changed after cert authentication policy is
        created.  The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my authentication policy" or my
        authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the authentication server. Minimum length = 1

    reqaction(str): Name of the client cert authentication action to be performed if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationcertpolicy <args>

    '''

    result = {}

    payload = {'authenticationcertpolicy': {}}

    if name:
        payload['authenticationcertpolicy']['name'] = name

    if rule:
        payload['authenticationcertpolicy']['rule'] = rule

    if reqaction:
        payload['authenticationcertpolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.post']('config/authenticationcertpolicy', payload)

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


def add_authenticationdfaaction(name=None, clientid=None, serverurl=None, passphrase=None,
                                defaultauthenticationgroup=None, save=False):
    '''
    Add a new authenticationdfaaction to the running configuration.

    name(str): Name for the DFA action.  Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the DFA action is added. Minimum length = 1

    clientid(str): If configured, this string is sent to the DFA server as the X-Citrix-Exchange header value.

    serverurl(str): DFA Server URL.

    passphrase(str): Key shared between the DFA server and the NetScaler appliance.  Required to allow the NetScaler
        appliance to communicate with the DFA server. Minimum length = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationdfaaction <args>

    '''

    result = {}

    payload = {'authenticationdfaaction': {}}

    if name:
        payload['authenticationdfaaction']['name'] = name

    if clientid:
        payload['authenticationdfaaction']['clientid'] = clientid

    if serverurl:
        payload['authenticationdfaaction']['serverurl'] = serverurl

    if passphrase:
        payload['authenticationdfaaction']['passphrase'] = passphrase

    if defaultauthenticationgroup:
        payload['authenticationdfaaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.post']('config/authenticationdfaaction', payload)

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


def add_authenticationdfapolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new authenticationdfapolicy to the running configuration.

    name(str): Name for the DFA policy.  Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after DFA policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the Web server. Minimum length = 1

    action(str): Name of the DFA action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationdfapolicy <args>

    '''

    result = {}

    payload = {'authenticationdfapolicy': {}}

    if name:
        payload['authenticationdfapolicy']['name'] = name

    if rule:
        payload['authenticationdfapolicy']['rule'] = rule

    if action:
        payload['authenticationdfapolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/authenticationdfapolicy', payload)

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


def add_authenticationepaaction(name=None, csecexpr=None, killprocess=None, deletefiles=None, defaultepagroup=None,
                                quarantinegroup=None, save=False):
    '''
    Add a new authenticationepaaction to the running configuration.

    name(str): Name for the epa action. Must begin with a  letter, number, or the underscore character (_), and must consist
        only of letters, numbers, and the hyphen (-), period (.) pound  (#), space ( ), at (@), equals (=), colon (:),
        and underscore  characters. Cannot be changed after epa action is created.The following requirement applies only
        to the NetScaler CLI:If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my aaa action" or my aaa action). Minimum length = 1

    csecexpr(str): it holds the ClientSecurityExpression to be sent to the client.

    killprocess(str): String specifying the name of a process to be terminated by the endpoint analysis (EPA) tool. Multiple
        processes to be delimited by comma.

    deletefiles(str): String specifying the path(s) and name(s) of the files to be deleted by the endpoint analysis (EPA)
        tool. Multiple files to be delimited by comma.

    defaultepagroup(str): This is the default group that is chosen when the EPA check succeeds. Maximum length = 64

    quarantinegroup(str): This is the quarantine group that is chosen when the EPA check fails if configured. Maximum length
        = 64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationepaaction <args>

    '''

    result = {}

    payload = {'authenticationepaaction': {}}

    if name:
        payload['authenticationepaaction']['name'] = name

    if csecexpr:
        payload['authenticationepaaction']['csecexpr'] = csecexpr

    if killprocess:
        payload['authenticationepaaction']['killprocess'] = killprocess

    if deletefiles:
        payload['authenticationepaaction']['deletefiles'] = deletefiles

    if defaultepagroup:
        payload['authenticationepaaction']['defaultepagroup'] = defaultepagroup

    if quarantinegroup:
        payload['authenticationepaaction']['quarantinegroup'] = quarantinegroup

    execution = __proxy__['citrixns.post']('config/authenticationepaaction', payload)

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


def add_authenticationldapaction(name=None, serverip=None, servername=None, serverport=None, authtimeout=None,
                                 ldapbase=None, ldapbinddn=None, ldapbinddnpassword=None, ldaploginname=None,
                                 searchfilter=None, groupattrname=None, subattributename=None, sectype=None,
                                 svrtype=None, ssonameattribute=None, authentication=None, requireuser=None,
                                 passwdchange=None, nestedgroupextraction=None, maxnestinglevel=None,
                                 followreferrals=None, maxldapreferrals=None, referraldnslookup=None,
                                 mssrvrecordlocation=None, validateservercert=None, ldaphostname=None,
                                 groupnameidentifier=None, groupsearchattribute=None, groupsearchsubattribute=None,
                                 groupsearchfilter=None, defaultauthenticationgroup=None, attribute1=None,
                                 attribute2=None, attribute3=None, attribute4=None, attribute5=None, attribute6=None,
                                 attribute7=None, attribute8=None, attribute9=None, attribute10=None, attribute11=None,
                                 attribute12=None, attribute13=None, attribute14=None, attribute15=None,
                                 attribute16=None, save=False):
    '''
    Add a new authenticationldapaction to the running configuration.

    name(str): Name for the new LDAP action.  Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the LDAP action is added.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication action" or my authentication action). Minimum length = 1

    serverip(str): IP address assigned to the LDAP server. Minimum length = 1

    servername(str): LDAP server name as a FQDN. Mutually exclusive with LDAP IP address. Minimum length = 1

    serverport(int): Port on which the LDAP server accepts connections. Default value: 389 Minimum value = 1

    authtimeout(int): Number of seconds the NetScaler appliance waits for a response from the RADIUS server. Default value: 3
        Minimum value = 1

    ldapbase(str): Base (node) from which to start LDAP searches.  If the LDAP server is running locally, the default value
        of base is dc=netscaler, dc=com.

    ldapbinddn(str): Full distinguished name (DN) that is used to bind to the LDAP server.  Default:
        cn=Manager,dc=netscaler,dc=com.

    ldapbinddnpassword(str): Password used to bind to the LDAP server. Minimum length = 1

    ldaploginname(str): LDAP login name attribute.  The NetScaler appliance uses the LDAP login name to query external LDAP
        servers or Active Directories.

    searchfilter(str): String to be combined with the default LDAP user search string to form the search value. For example,
        if the search filter "vpnallowed=true" is combined with the LDAP login name "samaccount" and the user-supplied
        username is "bob", the result is the LDAP search string ""(;amp;(vpnallowed=true)(samaccount=bob)"" (Be sure to
        enclose the search string in two sets of double quotation marks; both sets are needed.). Minimum length = 1

    groupattrname(str): LDAP group attribute name. Used for group extraction on the LDAP server.

    subattributename(str): LDAP group sub-attribute name.  Used for group extraction from the LDAP server.

    sectype(str): Type of security used for communications between the NetScaler appliance and the LDAP server. For the
        PLAINTEXT setting, no encryption is required. Default value: PLAINTEXT Possible values = PLAINTEXT, TLS, SSL

    svrtype(str): The type of LDAP server. Default value: AAA_LDAP_SERVER_TYPE_DEFAULT Possible values = AD, NDS

    ssonameattribute(str): LDAP single signon (SSO) attribute.  The NetScaler appliance uses the SSO name attribute to query
        external LDAP servers or Active Directories for an alternate username.

    authentication(str): Perform LDAP authentication. If authentication is disabled, any LDAP authentication attempt returns
        authentication success if the user is found.  CAUTION! Authentication should be disabled only for authorization
        group extraction or where other (non-LDAP) authentication methods are in use and either bound to a primary list
        or flagged as secondary. Default value: ENABLED Possible values = ENABLED, DISABLED

    requireuser(str): Require a successful user search for authentication. Default value: YES Possible values = YES, NO

    passwdchange(str): Allow password change requests. Default value: DISABLED Possible values = ENABLED, DISABLED

    nestedgroupextraction(str): Allow nested group extraction, in which the NetScaler appliance queries external LDAP servers
        to determine whether a group is part of another group. Default value: OFF Possible values = ON, OFF

    maxnestinglevel(int): If nested group extraction is ON, specifies the number of levels up to which group extraction is
        performed. Default value: 2 Minimum value = 2

    followreferrals(str): Setting this option to ON enables following LDAP referrals received from the LDAP server. Default
        value: OFF Possible values = ON, OFF

    maxldapreferrals(int): Specifies the maximum number of nested referrals to follow. Default value: 1 Minimum value = 1

    referraldnslookup(str): Specifies the DNS Record lookup Type for the referrals. Default value: A-REC Possible values =
        A-REC, SRV-REC, MSSRV-REC

    mssrvrecordlocation(str): MSSRV Specific parameter. Used to locate the DNS node to which the SRV record pertains in the
        domainname. The domainname is appended to it to form the srv record. Example : For "dc._msdcs", the srv record
        formed is _ldap._tcp.dc._msdcs.;lt;domainname;gt;.

    validateservercert(str): When to validate LDAP server certs. Default value: NO Possible values = YES, NO

    ldaphostname(str): Hostname for the LDAP server. If -validateServerCert is ON then this must be the host name on the
        certificate from the LDAP server. A hostname mismatch will cause a connection failure.

    groupnameidentifier(str): Name that uniquely identifies a group in LDAP or Active Directory.

    groupsearchattribute(str): LDAP group search attribute.  Used to determine to which groups a group belongs.

    groupsearchsubattribute(str): LDAP group search subattribute.  Used to determine to which groups a group belongs.

    groupsearchfilter(str): String to be combined with the default LDAP group search string to form the search value. For
        example, the group search filter ""vpnallowed=true"" when combined with the group identifier ""samaccount"" and
        the group name ""g1"" yields the LDAP search string ""(;amp;(vpnallowed=true)(samaccount=g1)"". (Be sure to
        enclose the search string in two sets of double quotation marks; both sets are needed.).

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Expression that would be evaluated to extract attribute1 from the ldap response.

    attribute2(str): Expression that would be evaluated to extract attribute2 from the ldap response.

    attribute3(str): Expression that would be evaluated to extract attribute3 from the ldap response.

    attribute4(str): Expression that would be evaluated to extract attribute4 from the ldap response.

    attribute5(str): Expression that would be evaluated to extract attribute5 from the ldap response.

    attribute6(str): Expression that would be evaluated to extract attribute6 from the ldap response.

    attribute7(str): Expression that would be evaluated to extract attribute7 from the ldap response.

    attribute8(str): Expression that would be evaluated to extract attribute8 from the ldap response.

    attribute9(str): Expression that would be evaluated to extract attribute9 from the ldap response.

    attribute10(str): Expression that would be evaluated to extract attribute10 from the ldap response.

    attribute11(str): Expression that would be evaluated to extract attribute11 from the ldap response.

    attribute12(str): Expression that would be evaluated to extract attribute12 from the ldap response.

    attribute13(str): Expression that would be evaluated to extract attribute13 from the ldap response.

    attribute14(str): Expression that would be evaluated to extract attribute14 from the ldap response.

    attribute15(str): Expression that would be evaluated to extract attribute15 from the ldap response.

    attribute16(str): Expression that would be evaluated to extract attribute16 from the ldap response.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationldapaction <args>

    '''

    result = {}

    payload = {'authenticationldapaction': {}}

    if name:
        payload['authenticationldapaction']['name'] = name

    if serverip:
        payload['authenticationldapaction']['serverip'] = serverip

    if servername:
        payload['authenticationldapaction']['servername'] = servername

    if serverport:
        payload['authenticationldapaction']['serverport'] = serverport

    if authtimeout:
        payload['authenticationldapaction']['authtimeout'] = authtimeout

    if ldapbase:
        payload['authenticationldapaction']['ldapbase'] = ldapbase

    if ldapbinddn:
        payload['authenticationldapaction']['ldapbinddn'] = ldapbinddn

    if ldapbinddnpassword:
        payload['authenticationldapaction']['ldapbinddnpassword'] = ldapbinddnpassword

    if ldaploginname:
        payload['authenticationldapaction']['ldaploginname'] = ldaploginname

    if searchfilter:
        payload['authenticationldapaction']['searchfilter'] = searchfilter

    if groupattrname:
        payload['authenticationldapaction']['groupattrname'] = groupattrname

    if subattributename:
        payload['authenticationldapaction']['subattributename'] = subattributename

    if sectype:
        payload['authenticationldapaction']['sectype'] = sectype

    if svrtype:
        payload['authenticationldapaction']['svrtype'] = svrtype

    if ssonameattribute:
        payload['authenticationldapaction']['ssonameattribute'] = ssonameattribute

    if authentication:
        payload['authenticationldapaction']['authentication'] = authentication

    if requireuser:
        payload['authenticationldapaction']['requireuser'] = requireuser

    if passwdchange:
        payload['authenticationldapaction']['passwdchange'] = passwdchange

    if nestedgroupextraction:
        payload['authenticationldapaction']['nestedgroupextraction'] = nestedgroupextraction

    if maxnestinglevel:
        payload['authenticationldapaction']['maxnestinglevel'] = maxnestinglevel

    if followreferrals:
        payload['authenticationldapaction']['followreferrals'] = followreferrals

    if maxldapreferrals:
        payload['authenticationldapaction']['maxldapreferrals'] = maxldapreferrals

    if referraldnslookup:
        payload['authenticationldapaction']['referraldnslookup'] = referraldnslookup

    if mssrvrecordlocation:
        payload['authenticationldapaction']['mssrvrecordlocation'] = mssrvrecordlocation

    if validateservercert:
        payload['authenticationldapaction']['validateservercert'] = validateservercert

    if ldaphostname:
        payload['authenticationldapaction']['ldaphostname'] = ldaphostname

    if groupnameidentifier:
        payload['authenticationldapaction']['groupnameidentifier'] = groupnameidentifier

    if groupsearchattribute:
        payload['authenticationldapaction']['groupsearchattribute'] = groupsearchattribute

    if groupsearchsubattribute:
        payload['authenticationldapaction']['groupsearchsubattribute'] = groupsearchsubattribute

    if groupsearchfilter:
        payload['authenticationldapaction']['groupsearchfilter'] = groupsearchfilter

    if defaultauthenticationgroup:
        payload['authenticationldapaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationldapaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationldapaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationldapaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationldapaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationldapaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationldapaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationldapaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationldapaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationldapaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationldapaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationldapaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationldapaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationldapaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationldapaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationldapaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationldapaction']['attribute16'] = attribute16

    execution = __proxy__['citrixns.post']('config/authenticationldapaction', payload)

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


def add_authenticationldappolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Add a new authenticationldappolicy to the running configuration.

    name(str): Name for the LDAP policy.  Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after LDAP policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the LDAP server. Minimum length = 1

    reqaction(str): Name of the LDAP action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationldappolicy <args>

    '''

    result = {}

    payload = {'authenticationldappolicy': {}}

    if name:
        payload['authenticationldappolicy']['name'] = name

    if rule:
        payload['authenticationldappolicy']['rule'] = rule

    if reqaction:
        payload['authenticationldappolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.post']('config/authenticationldappolicy', payload)

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


def add_authenticationlocalpolicy(name=None, rule=None, save=False):
    '''
    Add a new authenticationlocalpolicy to the running configuration.

    name(str): Name for the local authentication policy.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after local policy is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication policy" or my authentication policy).

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to perform the
        authentication.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationlocalpolicy <args>

    '''

    result = {}

    payload = {'authenticationlocalpolicy': {}}

    if name:
        payload['authenticationlocalpolicy']['name'] = name

    if rule:
        payload['authenticationlocalpolicy']['rule'] = rule

    execution = __proxy__['citrixns.post']('config/authenticationlocalpolicy', payload)

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


def add_authenticationloginschema(name=None, authenticationschema=None, userexpression=None, passwdexpression=None,
                                  usercredentialindex=None, passwordcredentialindex=None, authenticationstrength=None,
                                  ssocredentials=None, save=False):
    '''
    Add a new authenticationloginschema to the running configuration.

    name(str): Name for the new login schema. Login schema defines the way login form is rendered. It provides a way to
        customize the fields that are shown to the user. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an action is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my action" or my action). Minimum length = 1

    authenticationschema(str): Name of the file for reading authentication schema to be sent for Login Page UI. This file
        should contain xml definition of elements as per Citrix Forms Authentication Protocol to be able to render login
        form. If administrator does not want to prompt users for additional credentials but continue with previously
        obtained credentials, then "noschema" can be given as argument. Please note that this applies only to
        loginSchemas that are used with user-defined factors, and not the vserver factor. Minimum length = 1

    userexpression(str): Expression for username extraction during login. This can be any relevant advanced policy
        expression. Minimum length = 1

    passwdexpression(str): Expression for password extraction during login. This can be any relevant advanced policy
        expression. Minimum length = 1

    usercredentialindex(int): The index at which user entered username should be stored in session. Minimum value = 1 Maximum
        value = 16

    passwordcredentialindex(int): The index at which user entered password should be stored in session. Minimum value = 1
        Maximum value = 16

    authenticationstrength(int): Weight of the current authentication. Minimum value = 0 Maximum value = 65535

    ssocredentials(str): This option indicates whether current factor credentials are the default SSO (SingleSignOn)
        credentials. Default value: NO Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationloginschema <args>

    '''

    result = {}

    payload = {'authenticationloginschema': {}}

    if name:
        payload['authenticationloginschema']['name'] = name

    if authenticationschema:
        payload['authenticationloginschema']['authenticationschema'] = authenticationschema

    if userexpression:
        payload['authenticationloginschema']['userexpression'] = userexpression

    if passwdexpression:
        payload['authenticationloginschema']['passwdexpression'] = passwdexpression

    if usercredentialindex:
        payload['authenticationloginschema']['usercredentialindex'] = usercredentialindex

    if passwordcredentialindex:
        payload['authenticationloginschema']['passwordcredentialindex'] = passwordcredentialindex

    if authenticationstrength:
        payload['authenticationloginschema']['authenticationstrength'] = authenticationstrength

    if ssocredentials:
        payload['authenticationloginschema']['ssocredentials'] = ssocredentials

    execution = __proxy__['citrixns.post']('config/authenticationloginschema', payload)

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


def add_authenticationloginschemapolicy(name=None, rule=None, action=None, undefaction=None, comment=None,
                                        logaction=None, newname=None, save=False):
    '''
    Add a new authenticationloginschemapolicy to the running configuration.

    name(str): Name for the LoginSchema policy. This is used for selecting parameters for user logon. Must begin with an
        ASCII alphanumeric or underscore (_) character, and must contain only ASCII alphanumeric, underscore, hash (#),
        period (.), space, colon (:), at (@), equals (=), and hyphen (-) characters. Cannot be changed after the policy
        is created.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my policy" or my policy). Minimum
        length = 1

    rule(str): Expression which is evaluated to choose a profile for authentication. Maximum length of a string literal in
        the expression is 255 characters. A longer string can be split into smaller strings of up to 255 characters each,
        and the smaller strings concatenated with the + operator. For example, you can create a 500-character string as
        follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements
        apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression
        in double quotation marks. * If the expression itself includes double quotation marks, escape the quotations by
        using the \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case
        you do not have to escape the double quotation marks. Minimum length = 1

    action(str): Name of the profile to apply to requests or connections that match this policy. * NOOP - Do not take any
        specific action when this policy evaluates to true. This is useful to implicitly go to a different policy set. *
        RESET - Reset the client connection by closing it. The client program, such as a browser, will handle this and
        may inform the user. The client may then resend the request if desired. * DROP - Drop the request without sending
        a response to the user. Minimum length = 1

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any comments to preserve information about this policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the LoginSchema policy.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        loginschemapolicy policy" or my loginschemapolicy policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationloginschemapolicy <args>

    '''

    result = {}

    payload = {'authenticationloginschemapolicy': {}}

    if name:
        payload['authenticationloginschemapolicy']['name'] = name

    if rule:
        payload['authenticationloginschemapolicy']['rule'] = rule

    if action:
        payload['authenticationloginschemapolicy']['action'] = action

    if undefaction:
        payload['authenticationloginschemapolicy']['undefaction'] = undefaction

    if comment:
        payload['authenticationloginschemapolicy']['comment'] = comment

    if logaction:
        payload['authenticationloginschemapolicy']['logaction'] = logaction

    if newname:
        payload['authenticationloginschemapolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/authenticationloginschemapolicy', payload)

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


def add_authenticationnegotiateaction(name=None, domain=None, domainuser=None, domainuserpasswd=None, ou=None,
                                      defaultauthenticationgroup=None, keytab=None, ntlmpath=None, save=False):
    '''
    Add a new authenticationnegotiateaction to the running configuration.

    name(str): Name for the AD KDC server profile (negotiate action).  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters. Cannot be changed after AD KDC server profile is created.
        The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my authentication action" or my authentication action).
        Minimum length = 1

    domain(str): Domain name of the service principal that represnts Netscaler. Minimum length = 1

    domainuser(str): User name of the account that is mapped with Netscaler principal. This can be given along with domain
        and password when keytab file is not available. If username is given along with keytab file, then that keytab
        file will be searched for this users credentials. Minimum length = 1

    domainuserpasswd(str): Password of the account that is mapped to the NetScaler principal. Minimum length = 1

    ou(str): Active Directory organizational units (OU) attribute. Minimum length = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    keytab(str): The path to the keytab file that is used to decrypt kerberos tickets presented to Netscaler. If keytab is
        not available, domain/username/password can be specified in the negotiate action configuration. Minimum length =
        1

    ntlmpath(str): The path to the site that is enabled for NTLM authentication, including FQDN of the server. This is used
        when clients fallback to NTLM. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationnegotiateaction <args>

    '''

    result = {}

    payload = {'authenticationnegotiateaction': {}}

    if name:
        payload['authenticationnegotiateaction']['name'] = name

    if domain:
        payload['authenticationnegotiateaction']['domain'] = domain

    if domainuser:
        payload['authenticationnegotiateaction']['domainuser'] = domainuser

    if domainuserpasswd:
        payload['authenticationnegotiateaction']['domainuserpasswd'] = domainuserpasswd

    if ou:
        payload['authenticationnegotiateaction']['ou'] = ou

    if defaultauthenticationgroup:
        payload['authenticationnegotiateaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if keytab:
        payload['authenticationnegotiateaction']['keytab'] = keytab

    if ntlmpath:
        payload['authenticationnegotiateaction']['ntlmpath'] = ntlmpath

    execution = __proxy__['citrixns.post']('config/authenticationnegotiateaction', payload)

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


def add_authenticationnegotiatepolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Add a new authenticationnegotiatepolicy to the running configuration.

    name(str): Name for the negotiate authentication policy.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Cannot be changed after AD KCD (negotiate) policy is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my authentication policy" or my authentication policy).
        Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the AD KCD server. Minimum length = 1

    reqaction(str): Name of the negotiate action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationnegotiatepolicy <args>

    '''

    result = {}

    payload = {'authenticationnegotiatepolicy': {}}

    if name:
        payload['authenticationnegotiatepolicy']['name'] = name

    if rule:
        payload['authenticationnegotiatepolicy']['rule'] = rule

    if reqaction:
        payload['authenticationnegotiatepolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.post']('config/authenticationnegotiatepolicy', payload)

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


def add_authenticationoauthaction(name=None, oauthtype=None, authorizationendpoint=None, tokenendpoint=None,
                                  idtokendecryptendpoint=None, clientid=None, clientsecret=None,
                                  defaultauthenticationgroup=None, attribute1=None, attribute2=None, attribute3=None,
                                  attribute4=None, attribute5=None, attribute6=None, attribute7=None, attribute8=None,
                                  attribute9=None, attribute10=None, attribute11=None, attribute12=None,
                                  attribute13=None, attribute14=None, attribute15=None, attribute16=None, tenantid=None,
                                  graphendpoint=None, refreshinterval=None, certendpoint=None, audience=None,
                                  usernamefield=None, skewtime=None, issuer=None, save=False):
    '''
    Add a new authenticationoauthaction to the running configuration.

    name(str): Name for the OAuth Authentication action.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the profile is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication action" or my authentication action). Minimum length = 1

    oauthtype(str): Type of the OAuth implementation. Default value is generic implementation that is applicable for most
        deployments. Default value: GENERIC Possible values = GENERIC, INTUNE

    authorizationendpoint(str): Authorization endpoint/url to which unauthenticated user will be redirected. Netscaler
        appliance redirects user to this endpoint by adding query parameters including clientid. If this parameter not
        specified then as default value we take Token Endpoint/URL value. Please note that Authorization Endpoint or
        Token Endpoint is mandatory for oauthAction.

    tokenendpoint(str): URL to which OAuth token will be posted to verify its authenticity. User obtains this token from
        Authorization server upon successful authentication. Netscaler appliance will validate presented token by posting
        it to the URL configured.

    idtokendecryptendpoint(str): URL to which obtained idtoken will be posted to get a decrypted user identity. Encrypted
        idtoken will be obtained by posting OAuth token to token endpoint. In order to decrypt idtoken, Netscaler
        appliance posts request to the URL configured.

    clientid(str): Unique identity of the client/user who is getting authenticated. Authorization server infers client
        configuration using this ID. Minimum length = 1

    clientsecret(str): Secret string established by user and authorization server. Minimum length = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Expression that would be evaluated to extract attribute1 from the oauth response.

    attribute2(str): Expression that would be evaluated to extract attribute2 from the oauth response.

    attribute3(str): Expression that would be evaluated to extract attribute3 from the oauth response.

    attribute4(str): Expression that would be evaluated to extract attribute4 from the oauth response.

    attribute5(str): Expression that would be evaluated to extract attribute5 from the oauth response.

    attribute6(str): Expression that would be evaluated to extract attribute6 from the oauth response.

    attribute7(str): Expression that would be evaluated to extract attribute7 from the oauth response.

    attribute8(str): Expression that would be evaluated to extract attribute8 from the oauth response.

    attribute9(str): Expression that would be evaluated to extract attribute9 from the oauth response.

    attribute10(str): Expression that would be evaluated to extract attribute10 from the oauth response.

    attribute11(str): Expression that would be evaluated to extract attribute11 from the oauth response.

    attribute12(str): Expression that would be evaluated to extract attribute12 from the oauth response.

    attribute13(str): Expression that would be evaluated to extract attribute13 from the oauth response.

    attribute14(str): Expression that would be evaluated to extract attribute14 from the oauth response.

    attribute15(str): Expression that would be evaluated to extract attribute15 from the oauth response.

    attribute16(str): Expression that would be evaluated to extract attribute16 from the oauth response.

    tenantid(str): TenantID of the application. This is usually specific to providers such as Microsoft and usually refers to
        the deployment identifier.

    graphendpoint(str): URL of the Graph API service to learn Enterprise Mobility Services (EMS) endpoints.

    refreshinterval(int): Interval at which services are monitored for necessary configuration. Default value: 1440

    certendpoint(str): URL of the endpoint that contains JWKs (Json Web Key) for JWT (Json Web Token) verification.

    audience(str): Audience for which token sent by Authorization server is applicable. This is typically entity name or url
        that represents the recipient.

    usernamefield(str): Attribute in the token from which username should be extracted. Minimum length = 1

    skewtime(int): This option specifies the allowed clock skew in number of minutes that Netscaler allows on an incoming
        token. For example, if skewTime is 10, then token would be valid from (current time - 10) min to (current time +
        10) min, ie 20min in all. Default value: 5

    issuer(str): Identity of the server whose tokens are to be accepted.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationoauthaction <args>

    '''

    result = {}

    payload = {'authenticationoauthaction': {}}

    if name:
        payload['authenticationoauthaction']['name'] = name

    if oauthtype:
        payload['authenticationoauthaction']['oauthtype'] = oauthtype

    if authorizationendpoint:
        payload['authenticationoauthaction']['authorizationendpoint'] = authorizationendpoint

    if tokenendpoint:
        payload['authenticationoauthaction']['tokenendpoint'] = tokenendpoint

    if idtokendecryptendpoint:
        payload['authenticationoauthaction']['idtokendecryptendpoint'] = idtokendecryptendpoint

    if clientid:
        payload['authenticationoauthaction']['clientid'] = clientid

    if clientsecret:
        payload['authenticationoauthaction']['clientsecret'] = clientsecret

    if defaultauthenticationgroup:
        payload['authenticationoauthaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationoauthaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationoauthaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationoauthaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationoauthaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationoauthaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationoauthaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationoauthaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationoauthaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationoauthaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationoauthaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationoauthaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationoauthaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationoauthaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationoauthaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationoauthaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationoauthaction']['attribute16'] = attribute16

    if tenantid:
        payload['authenticationoauthaction']['tenantid'] = tenantid

    if graphendpoint:
        payload['authenticationoauthaction']['graphendpoint'] = graphendpoint

    if refreshinterval:
        payload['authenticationoauthaction']['refreshinterval'] = refreshinterval

    if certendpoint:
        payload['authenticationoauthaction']['certendpoint'] = certendpoint

    if audience:
        payload['authenticationoauthaction']['audience'] = audience

    if usernamefield:
        payload['authenticationoauthaction']['usernamefield'] = usernamefield

    if skewtime:
        payload['authenticationoauthaction']['skewtime'] = skewtime

    if issuer:
        payload['authenticationoauthaction']['issuer'] = issuer

    execution = __proxy__['citrixns.post']('config/authenticationoauthaction', payload)

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


def add_authenticationpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                             newname=None, save=False):
    '''
    Add a new authenticationpolicy to the running configuration.

    name(str): Name for the advance AUTHENTICATION policy.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Cannot be changed after AUTHENTICATION policy is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my authentication policy" or my authentication policy).
        Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the AUTHENTICATION server.

    action(str): Name of the authentication action to be performed if the policy matches.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any comments to preserve information about this policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the authentication policy. Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters.   The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        authentication policy" or my authentication policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationpolicy <args>

    '''

    result = {}

    payload = {'authenticationpolicy': {}}

    if name:
        payload['authenticationpolicy']['name'] = name

    if rule:
        payload['authenticationpolicy']['rule'] = rule

    if action:
        payload['authenticationpolicy']['action'] = action

    if undefaction:
        payload['authenticationpolicy']['undefaction'] = undefaction

    if comment:
        payload['authenticationpolicy']['comment'] = comment

    if logaction:
        payload['authenticationpolicy']['logaction'] = logaction

    if newname:
        payload['authenticationpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/authenticationpolicy', payload)

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


def add_authenticationpolicylabel(labelname=None, ns_type=None, comment=None, loginschema=None, newname=None,
                                  save=False):
    '''
    Add a new authenticationpolicylabel to the running configuration.

    labelname(str): Name for the new authentication policy label. Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters.  The following requirement applies only to the NetScaler
        CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for example,
        "my authentication policy label" or authentication policy label).

    ns_type(str): Type of feature (aaatm or rba) against which to match the policies bound to this policy label. Default
        value: AAATM_REQ Possible values = AAATM_REQ, RBA_REQ

    comment(str): Any comments to preserve information about this authentication policy label.

    loginschema(str): Login schema associated with authentication policy label. Login schema defines the UI rendering by
        providing customization option of the fields. If user intervention is not needed for a given factor such as group
        extraction, a loginSchema whose authentication schema is "noschema" should be used.

    newname(str): The new name of the auth policy label. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationpolicylabel <args>

    '''

    result = {}

    payload = {'authenticationpolicylabel': {}}

    if labelname:
        payload['authenticationpolicylabel']['labelname'] = labelname

    if ns_type:
        payload['authenticationpolicylabel']['type'] = ns_type

    if comment:
        payload['authenticationpolicylabel']['comment'] = comment

    if loginschema:
        payload['authenticationpolicylabel']['loginschema'] = loginschema

    if newname:
        payload['authenticationpolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/authenticationpolicylabel', payload)

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


def add_authenticationpolicylabel_authenticationpolicy_binding(priority=None, nextfactor=None,
                                                               gotopriorityexpression=None, policyname=None,
                                                               labelname=None, save=False):
    '''
    Add a new authenticationpolicylabel_authenticationpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    nextfactor(str): On success invoke label.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policyname(str): Name of the authentication policy to bind to the policy label.

    labelname(str): Name of the authentication policy label to which to bind the policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationpolicylabel_authenticationpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationpolicylabel_authenticationpolicy_binding': {}}

    if priority:
        payload['authenticationpolicylabel_authenticationpolicy_binding']['priority'] = priority

    if nextfactor:
        payload['authenticationpolicylabel_authenticationpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationpolicylabel_authenticationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policyname:
        payload['authenticationpolicylabel_authenticationpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['authenticationpolicylabel_authenticationpolicy_binding']['labelname'] = labelname

    execution = __proxy__['citrixns.post']('config/authenticationpolicylabel_authenticationpolicy_binding', payload)

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


def add_authenticationradiusaction(name=None, serverip=None, servername=None, serverport=None, authtimeout=None,
                                   radkey=None, radnasip=None, radnasid=None, radvendorid=None, radattributetype=None,
                                   radgroupsprefix=None, radgroupseparator=None, passencoding=None, ipvendorid=None,
                                   ipattributetype=None, accounting=None, pwdvendorid=None, pwdattributetype=None,
                                   defaultauthenticationgroup=None, callingstationid=None, authservretry=None,
                                   authentication=None, save=False):
    '''
    Add a new authenticationradiusaction to the running configuration.

    name(str): Name for the RADIUS action.  Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the RADIUS action is added. Minimum length = 1

    serverip(str): IP address assigned to the RADIUS server. Minimum length = 1

    servername(str): RADIUS server name as a FQDN. Mutually exclusive with RADIUS IP address. Minimum length = 1

    serverport(int): Port number on which the RADIUS server listens for connections. Minimum value = 1

    authtimeout(int): Number of seconds the NetScaler appliance waits for a response from the RADIUS server. Default value: 3
        Minimum value = 1

    radkey(str): Key shared between the RADIUS server and the NetScaler appliance.  Required to allow the NetScaler appliance
        to communicate with the RADIUS server. Minimum length = 1

    radnasip(str): If enabled, the NetScaler appliance IP address (NSIP) is sent to the RADIUS server as the Network Access
        Server IP (NASIP) address.  The RADIUS protocol defines the meaning and use of the NASIP address. Possible values
        = ENABLED, DISABLED

    radnasid(str): If configured, this string is sent to the RADIUS server as the Network Access Server ID (NASID).

    radvendorid(int): RADIUS vendor ID attribute, used for RADIUS group extraction. Minimum value = 1

    radattributetype(int): RADIUS attribute type, used for RADIUS group extraction. Minimum value = 1

    radgroupsprefix(str): RADIUS groups prefix string.  This groups prefix precedes the group names within a RADIUS attribute
        for RADIUS group extraction.

    radgroupseparator(str): RADIUS group separator string The group separator delimits group names within a RADIUS attribute
        for RADIUS group extraction.

    passencoding(str): Encoding type for passwords in RADIUS packets that the NetScaler appliance sends to the RADIUS server.
        Default value: pap Possible values = pap, chap, mschapv1, mschapv2

    ipvendorid(int): Vendor ID of the intranet IP attribute in the RADIUS response. NOTE: A value of 0 indicates that the
        attribute is not vendor encoded.

    ipattributetype(int): Remote IP address attribute type in a RADIUS response. Minimum value = 1

    accounting(str): Whether the RADIUS server is currently accepting accounting messages. Possible values = ON, OFF

    pwdvendorid(int): Vendor ID of the attribute, in the RADIUS response, used to extract the user password. Minimum value =
        1

    pwdattributetype(int): Vendor-specific password attribute type in a RADIUS response. Minimum value = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    callingstationid(str): Send Calling-Station-ID of the client to the RADIUS server. IP Address of the client is sent as
        its Calling-Station-ID. Default value: DISABLED Possible values = ENABLED, DISABLED

    authservretry(int): Number of retry by the NetScaler appliance before getting response from the RADIUS server. Default
        value: 3 Minimum value = 1 Maximum value = 10

    authentication(str): Configure the RADIUS server state to accept or refuse authentication messages. Default value: ON
        Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationradiusaction <args>

    '''

    result = {}

    payload = {'authenticationradiusaction': {}}

    if name:
        payload['authenticationradiusaction']['name'] = name

    if serverip:
        payload['authenticationradiusaction']['serverip'] = serverip

    if servername:
        payload['authenticationradiusaction']['servername'] = servername

    if serverport:
        payload['authenticationradiusaction']['serverport'] = serverport

    if authtimeout:
        payload['authenticationradiusaction']['authtimeout'] = authtimeout

    if radkey:
        payload['authenticationradiusaction']['radkey'] = radkey

    if radnasip:
        payload['authenticationradiusaction']['radnasip'] = radnasip

    if radnasid:
        payload['authenticationradiusaction']['radnasid'] = radnasid

    if radvendorid:
        payload['authenticationradiusaction']['radvendorid'] = radvendorid

    if radattributetype:
        payload['authenticationradiusaction']['radattributetype'] = radattributetype

    if radgroupsprefix:
        payload['authenticationradiusaction']['radgroupsprefix'] = radgroupsprefix

    if radgroupseparator:
        payload['authenticationradiusaction']['radgroupseparator'] = radgroupseparator

    if passencoding:
        payload['authenticationradiusaction']['passencoding'] = passencoding

    if ipvendorid:
        payload['authenticationradiusaction']['ipvendorid'] = ipvendorid

    if ipattributetype:
        payload['authenticationradiusaction']['ipattributetype'] = ipattributetype

    if accounting:
        payload['authenticationradiusaction']['accounting'] = accounting

    if pwdvendorid:
        payload['authenticationradiusaction']['pwdvendorid'] = pwdvendorid

    if pwdattributetype:
        payload['authenticationradiusaction']['pwdattributetype'] = pwdattributetype

    if defaultauthenticationgroup:
        payload['authenticationradiusaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if callingstationid:
        payload['authenticationradiusaction']['callingstationid'] = callingstationid

    if authservretry:
        payload['authenticationradiusaction']['authservretry'] = authservretry

    if authentication:
        payload['authenticationradiusaction']['authentication'] = authentication

    execution = __proxy__['citrixns.post']('config/authenticationradiusaction', payload)

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


def add_authenticationradiuspolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Add a new authenticationradiuspolicy to the running configuration.

    name(str): Name for the RADIUS authentication policy.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after RADIUS policy is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my authentication policy" or my authentication policy). Minimum
        length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the RADIUS server.

    reqaction(str): Name of the RADIUS action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationradiuspolicy <args>

    '''

    result = {}

    payload = {'authenticationradiuspolicy': {}}

    if name:
        payload['authenticationradiuspolicy']['name'] = name

    if rule:
        payload['authenticationradiuspolicy']['rule'] = rule

    if reqaction:
        payload['authenticationradiuspolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.post']('config/authenticationradiuspolicy', payload)

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


def add_authenticationsamlaction(name=None, samlidpcertname=None, samlsigningcertname=None, samlredirecturl=None,
                                 samlacsindex=None, samluserfield=None, samlrejectunsignedassertion=None,
                                 samlissuername=None, samltwofactor=None, defaultauthenticationgroup=None,
                                 attribute1=None, attribute2=None, attribute3=None, attribute4=None, attribute5=None,
                                 attribute6=None, attribute7=None, attribute8=None, attribute9=None, attribute10=None,
                                 attribute11=None, attribute12=None, attribute13=None, attribute14=None,
                                 attribute15=None, attribute16=None, signaturealg=None, digestmethod=None,
                                 requestedauthncontext=None, authnctxclassref=None, samlbinding=None,
                                 attributeconsumingserviceindex=None, sendthumbprint=None, enforceusername=None,
                                 logouturl=None, artifactresolutionserviceurl=None, skewtime=None, logoutbinding=None,
                                 forceauthn=None, save=False):
    '''
    Add a new authenticationsamlaction to the running configuration.

    name(str): Name for the SAML server profile (action).  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after SAML profile is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication action" or my authentication action). Minimum length = 1

    samlidpcertname(str): Name of the SAML server as given in that servers SSL certificate. Minimum length = 1

    samlsigningcertname(str): Name of the signing authority as given in the SAML servers SSL certificate. Minimum length = 1

    samlredirecturl(str): URL to which users are redirected for authentication. Minimum length = 1

    samlacsindex(int): Index/ID of the metadata entry corresponding to this configuration. Default value: 255 Minimum value =
        0 Maximum value = 255

    samluserfield(str): SAML user ID, as given in the SAML assertion. Minimum length = 1

    samlrejectunsignedassertion(str): Reject unsigned SAML assertions. ON option results in rejection of Assertion that is
        received without signature. STRICT option ensures that both Response and Assertion are signed. OFF allows
        unsigned Assertions. Default value: ON Possible values = ON, OFF, STRICT

    samlissuername(str): The name to be used in requests sent from Netscaler to IdP to uniquely identify Netscaler. Minimum
        length = 1

    samltwofactor(str): Option to enable second factor after SAML. Default value: OFF Possible values = ON, OFF

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute1.
        Maximum length of the extracted attribute is 239 bytes.

    attribute2(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute2.
        Maximum length of the extracted attribute is 239 bytes.

    attribute3(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute3.
        Maximum length of the extracted attribute is 239 bytes.

    attribute4(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute4.
        Maximum length of the extracted attribute is 239 bytes.

    attribute5(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute5.
        Maximum length of the extracted attribute is 239 bytes.

    attribute6(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute6.
        Maximum length of the extracted attribute is 239 bytes.

    attribute7(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute7.
        Maximum length of the extracted attribute is 239 bytes.

    attribute8(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute8.
        Maximum length of the extracted attribute is 239 bytes.

    attribute9(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute9.
        Maximum length of the extracted attribute is 239 bytes.

    attribute10(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute10.
        Maximum length of the extracted attribute is 239 bytes.

    attribute11(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute11.
        Maximum length of the extracted attribute is 239 bytes.

    attribute12(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute12.
        Maximum length of the extracted attribute is 239 bytes.

    attribute13(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute13.
        Maximum length of the extracted attribute is 239 bytes.

    attribute14(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute14.
        Maximum length of the extracted attribute is 239 bytes.

    attribute15(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute15.
        Maximum length of the extracted attribute is 239 bytes.

    attribute16(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute16.
        Maximum length of the extracted attribute is 239 bytes.

    signaturealg(str): Algorithm to be used to sign/verify SAML transactions. Default value: RSA-SHA1 Possible values =
        RSA-SHA1, RSA-SHA256

    digestmethod(str): Algorithm to be used to compute/verify digest for SAML transactions. Default value: SHA1 Possible
        values = SHA1, SHA256

    requestedauthncontext(str): This element specifies the authentication context requirements of authentication statements
        returned in the response. Default value: exact Possible values = exact, minimum, maximum, better

    authnctxclassref(list(str)): This element specifies the authentication class types that are requested from IdP
        (IdentityProvider). InternetProtocol: This is applicable when a principal is authenticated through the use of a
        provided IP address. InternetProtocolPassword: This is applicable when a principal is authenticated through the
        use of a provided IP address, in addition to a username/password. Kerberos: This is applicable when the principal
        has authenticated using a password to a local authentication authority, in order to acquire a Kerberos ticket.
        MobileOneFactorUnregistered: This indicates authentication of the mobile device without requiring explicit
        end-user interaction. MobileTwoFactorUnregistered: This indicates two-factor based authentication during mobile
        customer registration process, such as secure device and user PIN. MobileOneFactorContract: Reflects mobile
        contract customer registration procedures and a single factor authentication. MobileTwoFactorContract: Reflects
        mobile contract customer registration procedures and a two-factor based authentication. Password: This class is
        applicable when a principal authenticates using password over unprotected http session.
        PasswordProtectedTransport: This class is applicable when a principal authenticates to an authentication
        authority through the presentation of a password over a protected session. PreviousSession: This class is
        applicable when a principal had authenticated to an authentication authority at some point in the past using any
        authentication context. X509: This indicates that the principal authenticated by means of a digital signature
        where the key was validated as part of an X.509 Public Key Infrastructure. PGP: This indicates that the principal
        authenticated by means of a digital signature where the key was validated as part of a PGP Public Key
        Infrastructure. SPKI: This indicates that the principal authenticated by means of a digital signature where the
        key was validated via an SPKI Infrastructure. XMLDSig: This indicates that the principal authenticated by means
        of a digital signature according to the processing rules specified in the XML Digital Signature specification.
        Smartcard: This indicates that the principal has authenticated using smartcard. SmartcardPKI: This class is
        applicable when a principal authenticates to an authentication authority through a two-factor authentication
        mechanism using a smartcard with enclosed private key and a PIN. SoftwarePKI: This class is applicable when a
        principal uses an X.509 certificate stored in software to authenticate to the authentication authority.
        Telephony: This class is used to indicate that the principal authenticated via the provision of a fixed-line
        telephone number, transported via a telephony protocol such as ADSL. NomadTelephony: Indicates that the principal
        is "roaming" and authenticates via the means of the line number, a user suffix, and a password element.
        PersonalTelephony: This class is used to indicate that the principal authenticated via the provision of a
        fixed-line telephone. AuthenticatedTelephony: Indicates that the principal authenticated via the means of the
        line number, a user suffix, and a password element. SecureRemotePassword: This class is applicable when the
        authentication was performed by means of Secure Remote Password. TLSClient: This class indicates that the
        principal authenticated by means of a client certificate, secured with the SSL/TLS transport. TimeSyncToken: This
        is applicable when a principal authenticates through a time synchronization token. Unspecified: This indicates
        that the authentication was performed by unspecified means. Windows: This indicates that Windows integrated
        authentication is utilized for authentication. Possible values = InternetProtocol, InternetProtocolPassword,
        Kerberos, MobileOneFactorUnregistered, MobileTwoFactorUnregistered, MobileOneFactorContract,
        MobileTwoFactorContract, Password, PasswordProtectedTransport, PreviousSession, X509, PGP, SPKI, XMLDSig,
        Smartcard, SmartcardPKI, SoftwarePKI, Telephony, NomadTelephony, PersonalTelephony, AuthenticatedTelephony,
        SecureRemotePassword, TLSClient, TimeSyncToken, Unspecified, Windows

    samlbinding(str): This element specifies the transport mechanism of saml messages. Default value: POST Possible values =
        REDIRECT, POST, ARTIFACT

    attributeconsumingserviceindex(int): Index/ID of the attribute specification at Identity Provider (IdP). IdP will locate
        attributes requested by SP using this index and send those attributes in Assertion. Default value: 255 Minimum
        value = 0 Maximum value = 255

    sendthumbprint(str): Option to send thumbprint instead of x509 certificate in SAML request. Default value: OFF Possible
        values = ON, OFF

    enforceusername(str): Option to choose whether the username that is extracted from SAML assertion can be edited in login
        page while doing second factor. Default value: ON Possible values = ON, OFF

    logouturl(str): SingleLogout URL on IdP to which logoutRequest will be sent on Netscaler session cleanup.

    artifactresolutionserviceurl(str): URL of the Artifact Resolution Service on IdP to which Netscaler will post artifact to
        get actual SAML token.

    skewtime(int): This option specifies the allowed clock skew in number of minutes that Netscaler ServiceProvider allows on
        an incoming assertion. For example, if skewTime is 10, then assertion would be valid from (current time - 10) min
        to (current time + 10) min, ie 20min in all. Default value: 5

    logoutbinding(str): This element specifies the transport mechanism of saml logout messages. Default value: POST Possible
        values = REDIRECT, POST

    forceauthn(str): Option that forces authentication at the Identity Provider (IdP) that receives Netscalers request.
        Default value: OFF Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationsamlaction <args>

    '''

    result = {}

    payload = {'authenticationsamlaction': {}}

    if name:
        payload['authenticationsamlaction']['name'] = name

    if samlidpcertname:
        payload['authenticationsamlaction']['samlidpcertname'] = samlidpcertname

    if samlsigningcertname:
        payload['authenticationsamlaction']['samlsigningcertname'] = samlsigningcertname

    if samlredirecturl:
        payload['authenticationsamlaction']['samlredirecturl'] = samlredirecturl

    if samlacsindex:
        payload['authenticationsamlaction']['samlacsindex'] = samlacsindex

    if samluserfield:
        payload['authenticationsamlaction']['samluserfield'] = samluserfield

    if samlrejectunsignedassertion:
        payload['authenticationsamlaction']['samlrejectunsignedassertion'] = samlrejectunsignedassertion

    if samlissuername:
        payload['authenticationsamlaction']['samlissuername'] = samlissuername

    if samltwofactor:
        payload['authenticationsamlaction']['samltwofactor'] = samltwofactor

    if defaultauthenticationgroup:
        payload['authenticationsamlaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationsamlaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationsamlaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationsamlaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationsamlaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationsamlaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationsamlaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationsamlaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationsamlaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationsamlaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationsamlaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationsamlaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationsamlaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationsamlaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationsamlaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationsamlaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationsamlaction']['attribute16'] = attribute16

    if signaturealg:
        payload['authenticationsamlaction']['signaturealg'] = signaturealg

    if digestmethod:
        payload['authenticationsamlaction']['digestmethod'] = digestmethod

    if requestedauthncontext:
        payload['authenticationsamlaction']['requestedauthncontext'] = requestedauthncontext

    if authnctxclassref:
        payload['authenticationsamlaction']['authnctxclassref'] = authnctxclassref

    if samlbinding:
        payload['authenticationsamlaction']['samlbinding'] = samlbinding

    if attributeconsumingserviceindex:
        payload['authenticationsamlaction']['attributeconsumingserviceindex'] = attributeconsumingserviceindex

    if sendthumbprint:
        payload['authenticationsamlaction']['sendthumbprint'] = sendthumbprint

    if enforceusername:
        payload['authenticationsamlaction']['enforceusername'] = enforceusername

    if logouturl:
        payload['authenticationsamlaction']['logouturl'] = logouturl

    if artifactresolutionserviceurl:
        payload['authenticationsamlaction']['artifactresolutionserviceurl'] = artifactresolutionserviceurl

    if skewtime:
        payload['authenticationsamlaction']['skewtime'] = skewtime

    if logoutbinding:
        payload['authenticationsamlaction']['logoutbinding'] = logoutbinding

    if forceauthn:
        payload['authenticationsamlaction']['forceauthn'] = forceauthn

    execution = __proxy__['citrixns.post']('config/authenticationsamlaction', payload)

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


def add_authenticationsamlidppolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                    newname=None, save=False):
    '''
    Add a new authenticationsamlidppolicy to the running configuration.

    name(str): Name for the SAML Identity Provider (IdP) authentication policy. This is used for configuring Netscaler as
        SAML Identity Provider. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the policy is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression which is evaluated to choose a profile for authentication. Maximum length of a string literal in
        the expression is 255 characters. A longer string can be split into smaller strings of up to 255 characters each,
        and the smaller strings concatenated with the + operator. For example, you can create a 500-character string as
        follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements
        apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression
        in double quotation marks. * If the expression itself includes double quotation marks, escape the quotations by
        using the \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case
        you do not have to escape the double quotation marks. Minimum length = 1

    action(str): Name of the profile to apply to requests or connections that match this policy. Minimum length = 1

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any comments to preserve information about this policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the SAML IdentityProvider policy.  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters.  The following requirement applies only to the NetScaler
        CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for example,
        "my samlidppolicy policy" or my samlidppolicy policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationsamlidppolicy <args>

    '''

    result = {}

    payload = {'authenticationsamlidppolicy': {}}

    if name:
        payload['authenticationsamlidppolicy']['name'] = name

    if rule:
        payload['authenticationsamlidppolicy']['rule'] = rule

    if action:
        payload['authenticationsamlidppolicy']['action'] = action

    if undefaction:
        payload['authenticationsamlidppolicy']['undefaction'] = undefaction

    if comment:
        payload['authenticationsamlidppolicy']['comment'] = comment

    if logaction:
        payload['authenticationsamlidppolicy']['logaction'] = logaction

    if newname:
        payload['authenticationsamlidppolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/authenticationsamlidppolicy', payload)

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


def add_authenticationsamlidpprofile(name=None, samlspcertname=None, samlidpcertname=None,
                                     assertionconsumerserviceurl=None, sendpassword=None, samlissuername=None,
                                     rejectunsignedrequests=None, signaturealg=None, digestmethod=None, audience=None,
                                     nameidformat=None, nameidexpr=None, attribute1=None, attribute1expr=None,
                                     attribute1friendlyname=None, attribute1format=None, attribute2=None,
                                     attribute2expr=None, attribute2friendlyname=None, attribute2format=None,
                                     attribute3=None, attribute3expr=None, attribute3friendlyname=None,
                                     attribute3format=None, attribute4=None, attribute4expr=None,
                                     attribute4friendlyname=None, attribute4format=None, attribute5=None,
                                     attribute5expr=None, attribute5friendlyname=None, attribute5format=None,
                                     attribute6=None, attribute6expr=None, attribute6friendlyname=None,
                                     attribute6format=None, attribute7=None, attribute7expr=None,
                                     attribute7friendlyname=None, attribute7format=None, attribute8=None,
                                     attribute8expr=None, attribute8friendlyname=None, attribute8format=None,
                                     attribute9=None, attribute9expr=None, attribute9friendlyname=None,
                                     attribute9format=None, attribute10=None, attribute10expr=None,
                                     attribute10friendlyname=None, attribute10format=None, attribute11=None,
                                     attribute11expr=None, attribute11friendlyname=None, attribute11format=None,
                                     attribute12=None, attribute12expr=None, attribute12friendlyname=None,
                                     attribute12format=None, attribute13=None, attribute13expr=None,
                                     attribute13friendlyname=None, attribute13format=None, attribute14=None,
                                     attribute14expr=None, attribute14friendlyname=None, attribute14format=None,
                                     attribute15=None, attribute15expr=None, attribute15friendlyname=None,
                                     attribute15format=None, attribute16=None, attribute16expr=None,
                                     attribute16friendlyname=None, attribute16format=None, encryptassertion=None,
                                     encryptionalgorithm=None, samlbinding=None, skewtime=None, serviceproviderid=None,
                                     signassertion=None, keytransportalg=None, splogouturl=None, logoutbinding=None,
                                     save=False):
    '''
    Add a new authenticationsamlidpprofile to the running configuration.

    name(str): Name for the new saml single sign-on profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an action is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my action" or my action). Minimum length = 1

    samlspcertname(str): Name of the SSL certificate of SAML Relying Party. This certificate is used to verify signature of
        the incoming AuthnRequest from a Relying Party or Service Provider. Minimum length = 1

    samlidpcertname(str): Name of the signing authority as given in the SAML servers SSL certificate. This certificate is
        used to sign the SAMLResposne that is sent to Relying Party or Service Provider after successful authentication.
        Minimum length = 1

    assertionconsumerserviceurl(str): URL to which the assertion is to be sent. Minimum length = 1

    sendpassword(str): Option to send password in assertion. Default value: OFF Possible values = ON, OFF

    samlissuername(str): The name to be used in requests sent from Netscaler to IdP to uniquely identify Netscaler. Minimum
        length = 1

    rejectunsignedrequests(str): Option to Reject unsigned SAML Requests. ON option denies any authentication requests that
        arrive without signature. Default value: ON Possible values = ON, OFF

    signaturealg(str): Algorithm to be used to sign/verify SAML transactions. Default value: RSA-SHA1 Possible values =
        RSA-SHA1, RSA-SHA256

    digestmethod(str): Algorithm to be used to compute/verify digest for SAML transactions. Default value: SHA1 Possible
        values = SHA1, SHA256

    audience(str): Audience for which assertion sent by IdP is applicable. This is typically entity name or url that
        represents ServiceProvider.

    nameidformat(str): Format of Name Identifier sent in Assertion. Default value: transient Possible values = Unspecified,
        emailAddress, X509SubjectName, WindowsDomainQualifiedName, kerberos, entity, persistent, transient

    nameidexpr(str): Expression that will be evaluated to obtain NameIdentifier to be sent in assertion. Maximum length =
        128

    attribute1(str): Name of attribute1 that needs to be sent in SAML Assertion.

    attribute1expr(str): Expression that will be evaluated to obtain attribute1s value to be sent in Assertion. Maximum
        length = 128

    attribute1friendlyname(str): User-Friendly Name of attribute1 that needs to be sent in SAML Assertion.

    attribute1format(str): Format of Attribute1 to be sent in Assertion. Possible values = URI, Basic

    attribute2(str): Name of attribute2 that needs to be sent in SAML Assertion.

    attribute2expr(str): Expression that will be evaluated to obtain attribute2s value to be sent in Assertion. Maximum
        length = 128

    attribute2friendlyname(str): User-Friendly Name of attribute2 that needs to be sent in SAML Assertion.

    attribute2format(str): Format of Attribute2 to be sent in Assertion. Possible values = URI, Basic

    attribute3(str): Name of attribute3 that needs to be sent in SAML Assertion.

    attribute3expr(str): Expression that will be evaluated to obtain attribute3s value to be sent in Assertion. Maximum
        length = 128

    attribute3friendlyname(str): User-Friendly Name of attribute3 that needs to be sent in SAML Assertion.

    attribute3format(str): Format of Attribute3 to be sent in Assertion. Possible values = URI, Basic

    attribute4(str): Name of attribute4 that needs to be sent in SAML Assertion.

    attribute4expr(str): Expression that will be evaluated to obtain attribute4s value to be sent in Assertion. Maximum
        length = 128

    attribute4friendlyname(str): User-Friendly Name of attribute4 that needs to be sent in SAML Assertion.

    attribute4format(str): Format of Attribute4 to be sent in Assertion. Possible values = URI, Basic

    attribute5(str): Name of attribute5 that needs to be sent in SAML Assertion.

    attribute5expr(str): Expression that will be evaluated to obtain attribute5s value to be sent in Assertion. Maximum
        length = 128

    attribute5friendlyname(str): User-Friendly Name of attribute5 that needs to be sent in SAML Assertion.

    attribute5format(str): Format of Attribute5 to be sent in Assertion. Possible values = URI, Basic

    attribute6(str): Name of attribute6 that needs to be sent in SAML Assertion.

    attribute6expr(str): Expression that will be evaluated to obtain attribute6s value to be sent in Assertion. Maximum
        length = 128

    attribute6friendlyname(str): User-Friendly Name of attribute6 that needs to be sent in SAML Assertion.

    attribute6format(str): Format of Attribute6 to be sent in Assertion. Possible values = URI, Basic

    attribute7(str): Name of attribute7 that needs to be sent in SAML Assertion.

    attribute7expr(str): Expression that will be evaluated to obtain attribute7s value to be sent in Assertion. Maximum
        length = 128

    attribute7friendlyname(str): User-Friendly Name of attribute7 that needs to be sent in SAML Assertion.

    attribute7format(str): Format of Attribute7 to be sent in Assertion. Possible values = URI, Basic

    attribute8(str): Name of attribute8 that needs to be sent in SAML Assertion.

    attribute8expr(str): Expression that will be evaluated to obtain attribute8s value to be sent in Assertion. Maximum
        length = 128

    attribute8friendlyname(str): User-Friendly Name of attribute8 that needs to be sent in SAML Assertion.

    attribute8format(str): Format of Attribute8 to be sent in Assertion. Possible values = URI, Basic

    attribute9(str): Name of attribute9 that needs to be sent in SAML Assertion.

    attribute9expr(str): Expression that will be evaluated to obtain attribute9s value to be sent in Assertion. Maximum
        length = 128

    attribute9friendlyname(str): User-Friendly Name of attribute9 that needs to be sent in SAML Assertion.

    attribute9format(str): Format of Attribute9 to be sent in Assertion. Possible values = URI, Basic

    attribute10(str): Name of attribute10 that needs to be sent in SAML Assertion.

    attribute10expr(str): Expression that will be evaluated to obtain attribute10s value to be sent in Assertion. Maximum
        length = 128

    attribute10friendlyname(str): User-Friendly Name of attribute10 that needs to be sent in SAML Assertion.

    attribute10format(str): Format of Attribute10 to be sent in Assertion. Possible values = URI, Basic

    attribute11(str): Name of attribute11 that needs to be sent in SAML Assertion.

    attribute11expr(str): Expression that will be evaluated to obtain attribute11s value to be sent in Assertion. Maximum
        length = 128

    attribute11friendlyname(str): User-Friendly Name of attribute11 that needs to be sent in SAML Assertion.

    attribute11format(str): Format of Attribute11 to be sent in Assertion. Possible values = URI, Basic

    attribute12(str): Name of attribute12 that needs to be sent in SAML Assertion.

    attribute12expr(str): Expression that will be evaluated to obtain attribute12s value to be sent in Assertion. Maximum
        length = 128

    attribute12friendlyname(str): User-Friendly Name of attribute12 that needs to be sent in SAML Assertion.

    attribute12format(str): Format of Attribute12 to be sent in Assertion. Possible values = URI, Basic

    attribute13(str): Name of attribute13 that needs to be sent in SAML Assertion.

    attribute13expr(str): Expression that will be evaluated to obtain attribute13s value to be sent in Assertion. Maximum
        length = 128

    attribute13friendlyname(str): User-Friendly Name of attribute13 that needs to be sent in SAML Assertion.

    attribute13format(str): Format of Attribute13 to be sent in Assertion. Possible values = URI, Basic

    attribute14(str): Name of attribute14 that needs to be sent in SAML Assertion.

    attribute14expr(str): Expression that will be evaluated to obtain attribute14s value to be sent in Assertion. Maximum
        length = 128

    attribute14friendlyname(str): User-Friendly Name of attribute14 that needs to be sent in SAML Assertion.

    attribute14format(str): Format of Attribute14 to be sent in Assertion. Possible values = URI, Basic

    attribute15(str): Name of attribute15 that needs to be sent in SAML Assertion.

    attribute15expr(str): Expression that will be evaluated to obtain attribute15s value to be sent in Assertion. Maximum
        length = 128

    attribute15friendlyname(str): User-Friendly Name of attribute15 that needs to be sent in SAML Assertion.

    attribute15format(str): Format of Attribute15 to be sent in Assertion. Possible values = URI, Basic

    attribute16(str): Name of attribute16 that needs to be sent in SAML Assertion.

    attribute16expr(str): Expression that will be evaluated to obtain attribute16s value to be sent in Assertion. Maximum
        length = 128

    attribute16friendlyname(str): User-Friendly Name of attribute16 that needs to be sent in SAML Assertion.

    attribute16format(str): Format of Attribute16 to be sent in Assertion. Possible values = URI, Basic

    encryptassertion(str): Option to encrypt assertion when Netscaler IDP sends one. Default value: OFF Possible values = ON,
        OFF

    encryptionalgorithm(str): Algorithm to be used to encrypt SAML assertion. Default value: AES256 Possible values = DES3,
        AES128, AES192, AES256

    samlbinding(str): This element specifies the transport mechanism of saml messages. Default value: POST Possible values =
        REDIRECT, POST, ARTIFACT

    skewtime(int): This option specifies the number of minutes on either side of current time that the assertion would be
        valid. For example, if skewTime is 10, then assertion would be valid from (current time - 10) min to (current
        time + 10) min, ie 20min in all. Default value: 5

    serviceproviderid(str): Unique identifier of the Service Provider that sends SAML Request. Netscaler will ensure that the
        Issuer of the SAML Request matches this URI. Minimum length = 1

    signassertion(str): Option to sign portions of assertion when Netscaler IDP sends one. Based on the user selection,
        either Assertion or Response or Both or none can be signed. Default value: ASSERTION Possible values = NONE,
        ASSERTION, RESPONSE, BOTH

    keytransportalg(str): Key transport algorithm to be used in encryption of SAML assertion. Default value: RSA_OAEP
        Possible values = RSA-V1_5, RSA_OAEP

    splogouturl(str): Endpoint on the ServiceProvider (SP) to which logout messages are to be sent. Minimum length = 1

    logoutbinding(str): This element specifies the transport mechanism of saml logout messages. Default value: POST Possible
        values = REDIRECT, POST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationsamlidpprofile <args>

    '''

    result = {}

    payload = {'authenticationsamlidpprofile': {}}

    if name:
        payload['authenticationsamlidpprofile']['name'] = name

    if samlspcertname:
        payload['authenticationsamlidpprofile']['samlspcertname'] = samlspcertname

    if samlidpcertname:
        payload['authenticationsamlidpprofile']['samlidpcertname'] = samlidpcertname

    if assertionconsumerserviceurl:
        payload['authenticationsamlidpprofile']['assertionconsumerserviceurl'] = assertionconsumerserviceurl

    if sendpassword:
        payload['authenticationsamlidpprofile']['sendpassword'] = sendpassword

    if samlissuername:
        payload['authenticationsamlidpprofile']['samlissuername'] = samlissuername

    if rejectunsignedrequests:
        payload['authenticationsamlidpprofile']['rejectunsignedrequests'] = rejectunsignedrequests

    if signaturealg:
        payload['authenticationsamlidpprofile']['signaturealg'] = signaturealg

    if digestmethod:
        payload['authenticationsamlidpprofile']['digestmethod'] = digestmethod

    if audience:
        payload['authenticationsamlidpprofile']['audience'] = audience

    if nameidformat:
        payload['authenticationsamlidpprofile']['nameidformat'] = nameidformat

    if nameidexpr:
        payload['authenticationsamlidpprofile']['nameidexpr'] = nameidexpr

    if attribute1:
        payload['authenticationsamlidpprofile']['attribute1'] = attribute1

    if attribute1expr:
        payload['authenticationsamlidpprofile']['attribute1expr'] = attribute1expr

    if attribute1friendlyname:
        payload['authenticationsamlidpprofile']['attribute1friendlyname'] = attribute1friendlyname

    if attribute1format:
        payload['authenticationsamlidpprofile']['attribute1format'] = attribute1format

    if attribute2:
        payload['authenticationsamlidpprofile']['attribute2'] = attribute2

    if attribute2expr:
        payload['authenticationsamlidpprofile']['attribute2expr'] = attribute2expr

    if attribute2friendlyname:
        payload['authenticationsamlidpprofile']['attribute2friendlyname'] = attribute2friendlyname

    if attribute2format:
        payload['authenticationsamlidpprofile']['attribute2format'] = attribute2format

    if attribute3:
        payload['authenticationsamlidpprofile']['attribute3'] = attribute3

    if attribute3expr:
        payload['authenticationsamlidpprofile']['attribute3expr'] = attribute3expr

    if attribute3friendlyname:
        payload['authenticationsamlidpprofile']['attribute3friendlyname'] = attribute3friendlyname

    if attribute3format:
        payload['authenticationsamlidpprofile']['attribute3format'] = attribute3format

    if attribute4:
        payload['authenticationsamlidpprofile']['attribute4'] = attribute4

    if attribute4expr:
        payload['authenticationsamlidpprofile']['attribute4expr'] = attribute4expr

    if attribute4friendlyname:
        payload['authenticationsamlidpprofile']['attribute4friendlyname'] = attribute4friendlyname

    if attribute4format:
        payload['authenticationsamlidpprofile']['attribute4format'] = attribute4format

    if attribute5:
        payload['authenticationsamlidpprofile']['attribute5'] = attribute5

    if attribute5expr:
        payload['authenticationsamlidpprofile']['attribute5expr'] = attribute5expr

    if attribute5friendlyname:
        payload['authenticationsamlidpprofile']['attribute5friendlyname'] = attribute5friendlyname

    if attribute5format:
        payload['authenticationsamlidpprofile']['attribute5format'] = attribute5format

    if attribute6:
        payload['authenticationsamlidpprofile']['attribute6'] = attribute6

    if attribute6expr:
        payload['authenticationsamlidpprofile']['attribute6expr'] = attribute6expr

    if attribute6friendlyname:
        payload['authenticationsamlidpprofile']['attribute6friendlyname'] = attribute6friendlyname

    if attribute6format:
        payload['authenticationsamlidpprofile']['attribute6format'] = attribute6format

    if attribute7:
        payload['authenticationsamlidpprofile']['attribute7'] = attribute7

    if attribute7expr:
        payload['authenticationsamlidpprofile']['attribute7expr'] = attribute7expr

    if attribute7friendlyname:
        payload['authenticationsamlidpprofile']['attribute7friendlyname'] = attribute7friendlyname

    if attribute7format:
        payload['authenticationsamlidpprofile']['attribute7format'] = attribute7format

    if attribute8:
        payload['authenticationsamlidpprofile']['attribute8'] = attribute8

    if attribute8expr:
        payload['authenticationsamlidpprofile']['attribute8expr'] = attribute8expr

    if attribute8friendlyname:
        payload['authenticationsamlidpprofile']['attribute8friendlyname'] = attribute8friendlyname

    if attribute8format:
        payload['authenticationsamlidpprofile']['attribute8format'] = attribute8format

    if attribute9:
        payload['authenticationsamlidpprofile']['attribute9'] = attribute9

    if attribute9expr:
        payload['authenticationsamlidpprofile']['attribute9expr'] = attribute9expr

    if attribute9friendlyname:
        payload['authenticationsamlidpprofile']['attribute9friendlyname'] = attribute9friendlyname

    if attribute9format:
        payload['authenticationsamlidpprofile']['attribute9format'] = attribute9format

    if attribute10:
        payload['authenticationsamlidpprofile']['attribute10'] = attribute10

    if attribute10expr:
        payload['authenticationsamlidpprofile']['attribute10expr'] = attribute10expr

    if attribute10friendlyname:
        payload['authenticationsamlidpprofile']['attribute10friendlyname'] = attribute10friendlyname

    if attribute10format:
        payload['authenticationsamlidpprofile']['attribute10format'] = attribute10format

    if attribute11:
        payload['authenticationsamlidpprofile']['attribute11'] = attribute11

    if attribute11expr:
        payload['authenticationsamlidpprofile']['attribute11expr'] = attribute11expr

    if attribute11friendlyname:
        payload['authenticationsamlidpprofile']['attribute11friendlyname'] = attribute11friendlyname

    if attribute11format:
        payload['authenticationsamlidpprofile']['attribute11format'] = attribute11format

    if attribute12:
        payload['authenticationsamlidpprofile']['attribute12'] = attribute12

    if attribute12expr:
        payload['authenticationsamlidpprofile']['attribute12expr'] = attribute12expr

    if attribute12friendlyname:
        payload['authenticationsamlidpprofile']['attribute12friendlyname'] = attribute12friendlyname

    if attribute12format:
        payload['authenticationsamlidpprofile']['attribute12format'] = attribute12format

    if attribute13:
        payload['authenticationsamlidpprofile']['attribute13'] = attribute13

    if attribute13expr:
        payload['authenticationsamlidpprofile']['attribute13expr'] = attribute13expr

    if attribute13friendlyname:
        payload['authenticationsamlidpprofile']['attribute13friendlyname'] = attribute13friendlyname

    if attribute13format:
        payload['authenticationsamlidpprofile']['attribute13format'] = attribute13format

    if attribute14:
        payload['authenticationsamlidpprofile']['attribute14'] = attribute14

    if attribute14expr:
        payload['authenticationsamlidpprofile']['attribute14expr'] = attribute14expr

    if attribute14friendlyname:
        payload['authenticationsamlidpprofile']['attribute14friendlyname'] = attribute14friendlyname

    if attribute14format:
        payload['authenticationsamlidpprofile']['attribute14format'] = attribute14format

    if attribute15:
        payload['authenticationsamlidpprofile']['attribute15'] = attribute15

    if attribute15expr:
        payload['authenticationsamlidpprofile']['attribute15expr'] = attribute15expr

    if attribute15friendlyname:
        payload['authenticationsamlidpprofile']['attribute15friendlyname'] = attribute15friendlyname

    if attribute15format:
        payload['authenticationsamlidpprofile']['attribute15format'] = attribute15format

    if attribute16:
        payload['authenticationsamlidpprofile']['attribute16'] = attribute16

    if attribute16expr:
        payload['authenticationsamlidpprofile']['attribute16expr'] = attribute16expr

    if attribute16friendlyname:
        payload['authenticationsamlidpprofile']['attribute16friendlyname'] = attribute16friendlyname

    if attribute16format:
        payload['authenticationsamlidpprofile']['attribute16format'] = attribute16format

    if encryptassertion:
        payload['authenticationsamlidpprofile']['encryptassertion'] = encryptassertion

    if encryptionalgorithm:
        payload['authenticationsamlidpprofile']['encryptionalgorithm'] = encryptionalgorithm

    if samlbinding:
        payload['authenticationsamlidpprofile']['samlbinding'] = samlbinding

    if skewtime:
        payload['authenticationsamlidpprofile']['skewtime'] = skewtime

    if serviceproviderid:
        payload['authenticationsamlidpprofile']['serviceproviderid'] = serviceproviderid

    if signassertion:
        payload['authenticationsamlidpprofile']['signassertion'] = signassertion

    if keytransportalg:
        payload['authenticationsamlidpprofile']['keytransportalg'] = keytransportalg

    if splogouturl:
        payload['authenticationsamlidpprofile']['splogouturl'] = splogouturl

    if logoutbinding:
        payload['authenticationsamlidpprofile']['logoutbinding'] = logoutbinding

    execution = __proxy__['citrixns.post']('config/authenticationsamlidpprofile', payload)

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


def add_authenticationsamlpolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Add a new authenticationsamlpolicy to the running configuration.

    name(str): Name for the SAML policy.  Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after SAML policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the SAML server. Minimum length = 1

    reqaction(str): Name of the SAML authentication action to be performed if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationsamlpolicy <args>

    '''

    result = {}

    payload = {'authenticationsamlpolicy': {}}

    if name:
        payload['authenticationsamlpolicy']['name'] = name

    if rule:
        payload['authenticationsamlpolicy']['rule'] = rule

    if reqaction:
        payload['authenticationsamlpolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.post']('config/authenticationsamlpolicy', payload)

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


def add_authenticationstorefrontauthaction(name=None, serverurl=None, domain=None, defaultauthenticationgroup=None,
                                           save=False):
    '''
    Add a new authenticationstorefrontauthaction to the running configuration.

    name(str): Name for the Storefront Authentication action.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Cannot be changed after the profile is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my authentication action" or my authentication action). Minimum
        length = 1

    serverurl(str): URL of the Storefront server. This is the FQDN of the Storefront server. example:
        https://storefront.com/. Authentication endpoints are learned dynamically by Gateway.

    domain(str): Domain of the server that is used for authentication. If users enter name without domain, this parameter is
        added to username in the authentication request to server.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationstorefrontauthaction <args>

    '''

    result = {}

    payload = {'authenticationstorefrontauthaction': {}}

    if name:
        payload['authenticationstorefrontauthaction']['name'] = name

    if serverurl:
        payload['authenticationstorefrontauthaction']['serverurl'] = serverurl

    if domain:
        payload['authenticationstorefrontauthaction']['domain'] = domain

    if defaultauthenticationgroup:
        payload['authenticationstorefrontauthaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.post']('config/authenticationstorefrontauthaction', payload)

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


def add_authenticationtacacsaction(name=None, serverip=None, serverport=None, authtimeout=None, tacacssecret=None,
                                   authorization=None, accounting=None, auditfailedcmds=None, groupattrname=None,
                                   defaultauthenticationgroup=None, attribute1=None, attribute2=None, attribute3=None,
                                   attribute4=None, attribute5=None, attribute6=None, attribute7=None, attribute8=None,
                                   attribute9=None, attribute10=None, attribute11=None, attribute12=None,
                                   attribute13=None, attribute14=None, attribute15=None, attribute16=None, save=False):
    '''
    Add a new authenticationtacacsaction to the running configuration.

    name(str): Name for the TACACS+ profile (action).  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after TACACS profile is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my authentication action" or y authentication action). Minimum
        length = 1

    serverip(str): IP address assigned to the TACACS+ server. Minimum length = 1

    serverport(int): Port number on which the TACACS+ server listens for connections. Default value: 49 Minimum value = 1

    authtimeout(int): Number of seconds the NetScaler appliance waits for a response from the TACACS+ server. Default value:
        3 Minimum value = 1

    tacacssecret(str): Key shared between the TACACS+ server and the NetScaler appliance.  Required for allowing the
        NetScaler appliance to communicate with the TACACS+ server. Minimum length = 1

    authorization(str): Use streaming authorization on the TACACS+ server. Possible values = ON, OFF

    accounting(str): Whether the TACACS+ server is currently accepting accounting messages. Possible values = ON, OFF

    auditfailedcmds(str): The state of the TACACS+ server that will receive accounting messages. Possible values = ON, OFF

    groupattrname(str): TACACS+ group attribute name. Used for group extraction on the TACACS+ server.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Name of the custom attribute to be extracted from server and stored at index 1 (where 1 changes for each
        attribute).

    attribute2(str): Name of the custom attribute to be extracted from server and stored at index 2 (where 2 changes for each
        attribute).

    attribute3(str): Name of the custom attribute to be extracted from server and stored at index 3 (where 3 changes for each
        attribute).

    attribute4(str): Name of the custom attribute to be extracted from server and stored at index 4 (where 4 changes for each
        attribute).

    attribute5(str): Name of the custom attribute to be extracted from server and stored at index 5 (where 5 changes for each
        attribute).

    attribute6(str): Name of the custom attribute to be extracted from server and stored at index 6 (where 6 changes for each
        attribute).

    attribute7(str): Name of the custom attribute to be extracted from server and stored at index 7 (where 7 changes for each
        attribute).

    attribute8(str): Name of the custom attribute to be extracted from server and stored at index 8 (where 8 changes for each
        attribute).

    attribute9(str): Name of the custom attribute to be extracted from server and stored at index 9 (where 9 changes for each
        attribute).

    attribute10(str): Name of the custom attribute to be extracted from server and stored at index 10 (where 10 changes for
        each attribute).

    attribute11(str): Name of the custom attribute to be extracted from server and stored at index 11 (where 11 changes for
        each attribute).

    attribute12(str): Name of the custom attribute to be extracted from server and stored at index 12 (where 12 changes for
        each attribute).

    attribute13(str): Name of the custom attribute to be extracted from server and stored at index 13 (where 13 changes for
        each attribute).

    attribute14(str): Name of the custom attribute to be extracted from server and stored at index 14 (where 14 changes for
        each attribute).

    attribute15(str): Name of the custom attribute to be extracted from server and stored at index 15 (where 15 changes for
        each attribute).

    attribute16(str): Name of the custom attribute to be extracted from server and stored at index 16 (where 16 changes for
        each attribute).

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationtacacsaction <args>

    '''

    result = {}

    payload = {'authenticationtacacsaction': {}}

    if name:
        payload['authenticationtacacsaction']['name'] = name

    if serverip:
        payload['authenticationtacacsaction']['serverip'] = serverip

    if serverport:
        payload['authenticationtacacsaction']['serverport'] = serverport

    if authtimeout:
        payload['authenticationtacacsaction']['authtimeout'] = authtimeout

    if tacacssecret:
        payload['authenticationtacacsaction']['tacacssecret'] = tacacssecret

    if authorization:
        payload['authenticationtacacsaction']['authorization'] = authorization

    if accounting:
        payload['authenticationtacacsaction']['accounting'] = accounting

    if auditfailedcmds:
        payload['authenticationtacacsaction']['auditfailedcmds'] = auditfailedcmds

    if groupattrname:
        payload['authenticationtacacsaction']['groupattrname'] = groupattrname

    if defaultauthenticationgroup:
        payload['authenticationtacacsaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationtacacsaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationtacacsaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationtacacsaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationtacacsaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationtacacsaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationtacacsaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationtacacsaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationtacacsaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationtacacsaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationtacacsaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationtacacsaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationtacacsaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationtacacsaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationtacacsaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationtacacsaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationtacacsaction']['attribute16'] = attribute16

    execution = __proxy__['citrixns.post']('config/authenticationtacacsaction', payload)

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


def add_authenticationtacacspolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Add a new authenticationtacacspolicy to the running configuration.

    name(str): Name for the TACACS+ policy.  Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after TACACS+ policy is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the TACACS+ server. Minimum length = 1

    reqaction(str): Name of the TACACS+ action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationtacacspolicy <args>

    '''

    result = {}

    payload = {'authenticationtacacspolicy': {}}

    if name:
        payload['authenticationtacacspolicy']['name'] = name

    if rule:
        payload['authenticationtacacspolicy']['rule'] = rule

    if reqaction:
        payload['authenticationtacacspolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.post']('config/authenticationtacacspolicy', payload)

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


def add_authenticationvserver(name=None, servicetype=None, ipv46=None, range=None, port=None, state=None,
                              authentication=None, authenticationdomain=None, comment=None, td=None, appflowlog=None,
                              maxloginattempts=None, failedlogintimeout=None, newname=None, save=False):
    '''
    Add a new authenticationvserver to the running configuration.

    name(str): Name for the new authentication virtual server.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Can be changed after the authentication virtual server is added by
        using the rename authentication vserver command.  The following requirement applies only to the NetScaler CLI: If
        the name includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        authentication policy" or my authentication policy). Minimum length = 1

    servicetype(str): Protocol type of the authentication virtual server. Always SSL. Default value: SSL Possible values =
        SSL

    ipv46(str): IP address of the authentication virtual server, if a single IP address is assigned to the virtual server.
        Minimum length = 1

    range(int): If you are creating a series of virtual servers with a range of IP addresses assigned to them, the length of
        the range.  The new range of authentication virtual servers will have IP addresses consecutively numbered,
        starting with the primary address specified with the IP Address parameter. Default value: 1 Minimum value = 1

    port(int): TCP port on which the virtual server accepts connections. Range 1 - 65535 * in CLI is represented as 65535 in
        NITRO API

    state(str): Initial state of the new virtual server. Default value: ENABLED Possible values = ENABLED, DISABLED

    authentication(str): Require users to be authenticated before sending traffic through this virtual server. Default value:
        ON Possible values = ON, OFF

    authenticationdomain(str): The domain of the authentication cookie set by Authentication vserver. Minimum length = 3
        Maximum length = 252

    comment(str): Any comments associated with this virtual server.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    appflowlog(str): Log AppFlow flow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    maxloginattempts(int): Maximum Number of login Attempts. Minimum value = 1 Maximum value = 255

    failedlogintimeout(int): Number of minutes an account will be locked if user exceeds maximum permissible attempts.
        Minimum value = 1

    newname(str): New name of the authentication virtual server.  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters.  The following requirement applies only to the NetScaler
        CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for example,
        my authentication policy or "my authentication policy"). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver <args>

    '''

    result = {}

    payload = {'authenticationvserver': {}}

    if name:
        payload['authenticationvserver']['name'] = name

    if servicetype:
        payload['authenticationvserver']['servicetype'] = servicetype

    if ipv46:
        payload['authenticationvserver']['ipv46'] = ipv46

    if range:
        payload['authenticationvserver']['range'] = range

    if port:
        payload['authenticationvserver']['port'] = port

    if state:
        payload['authenticationvserver']['state'] = state

    if authentication:
        payload['authenticationvserver']['authentication'] = authentication

    if authenticationdomain:
        payload['authenticationvserver']['authenticationdomain'] = authenticationdomain

    if comment:
        payload['authenticationvserver']['comment'] = comment

    if td:
        payload['authenticationvserver']['td'] = td

    if appflowlog:
        payload['authenticationvserver']['appflowlog'] = appflowlog

    if maxloginattempts:
        payload['authenticationvserver']['maxloginattempts'] = maxloginattempts

    if failedlogintimeout:
        payload['authenticationvserver']['failedlogintimeout'] = failedlogintimeout

    if newname:
        payload['authenticationvserver']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/authenticationvserver', payload)

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


def add_authenticationvserver_auditnslogpolicy_binding(priority=None, name=None, nextfactor=None,
                                                       gotopriorityexpression=None, secondary=None, policy=None,
                                                       groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_auditnslogpolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_auditnslogpolicy_binding': {}}

    if priority:
        payload['authenticationvserver_auditnslogpolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_auditnslogpolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_auditnslogpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_auditnslogpolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_auditnslogpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_auditnslogpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_auditnslogpolicy_binding', payload)

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


def add_authenticationvserver_auditsyslogpolicy_binding(priority=None, name=None, nextfactor=None,
                                                        gotopriorityexpression=None, secondary=None, policy=None,
                                                        groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_auditsyslogpolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_auditsyslogpolicy_binding': {}}

    if priority:
        payload['authenticationvserver_auditsyslogpolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_auditsyslogpolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_auditsyslogpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_auditsyslogpolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_auditsyslogpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_auditsyslogpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_auditsyslogpolicy_binding', payload)

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


def add_authenticationvserver_authenticationcertpolicy_binding(priority=None, name=None, nextfactor=None,
                                                               gotopriorityexpression=None, secondary=None, policy=None,
                                                               groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationcertpolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Bind the authentication policy to the secondary chain. Provides for multifactor authentication in which
        a user must authenticate via both a primary authentication method and, afterward, via a secondary authentication
        method. Because user groups are aggregated across authentication systems, usernames must be the same on all
        authentication servers. Passwords can be different.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationcertpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationcertpolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationcertpolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationcertpolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationcertpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationcertpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationcertpolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationcertpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationcertpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationcertpolicy_binding', payload)

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


def add_authenticationvserver_authenticationldappolicy_binding(priority=None, name=None, nextfactor=None,
                                                               gotopriorityexpression=None, secondary=None, policy=None,
                                                               groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationldappolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Bind the authentication policy to the secondary chain. Provides for multifactor authentication in which
        a user must authenticate via both a primary authentication method and, afterward, via a secondary authentication
        method. Because user groups are aggregated across authentication systems, usernames must be the same on all
        authentication servers. Passwords can be different.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Bind the Authentication policy to a tertiary chain which will be used only for group extraction.
        The user will not authenticate against this server, and this will only be called if primary and/or secondary
        authentication has succeeded.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationldappolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationldappolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationldappolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationldappolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationldappolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationldappolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationldappolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationldappolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationldappolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationldappolicy_binding', payload)

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


def add_authenticationvserver_authenticationlocalpolicy_binding(priority=None, name=None, nextfactor=None,
                                                                gotopriorityexpression=None, secondary=None, policy=None,
                                                                groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationlocalpolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Bind the authentication policy to the secondary chain. Provides for multifactor authentication in which
        a user must authenticate via both a primary authentication method and, afterward, via a secondary authentication
        method. Because user groups are aggregated across authentication systems, usernames must be the same on all
        authentication servers. Passwords can be different.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationlocalpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationlocalpolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationlocalpolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationlocalpolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationlocalpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationlocalpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationlocalpolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationlocalpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationlocalpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationlocalpolicy_binding', payload)

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


def add_authenticationvserver_authenticationloginschemapolicy_binding(priority=None, name=None, nextfactor=None,
                                                                      gotopriorityexpression=None, secondary=None,
                                                                      policy=None, groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationloginschemapolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationloginschemapolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationloginschemapolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationloginschemapolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationloginschemapolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationloginschemapolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationloginschemapolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationloginschemapolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationloginschemapolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationloginschemapolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationloginschemapolicy_binding', payload)

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


def add_authenticationvserver_authenticationnegotiatepolicy_binding(priority=None, name=None, nextfactor=None,
                                                                    gotopriorityexpression=None, secondary=None,
                                                                    policy=None, groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationnegotiatepolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Bind the authentication policy to the secondary chain. Provides for multifactor authentication in which
        a user must authenticate via both a primary authentication method and, afterward, via a secondary authentication
        method. Because user groups are aggregated across authentication systems, usernames must be the same on all
        authentication servers. Passwords can be different.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationnegotiatepolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationnegotiatepolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationnegotiatepolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationnegotiatepolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationnegotiatepolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationnegotiatepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationnegotiatepolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationnegotiatepolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationnegotiatepolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationnegotiatepolicy_binding', payload)

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


def add_authenticationvserver_authenticationpolicy_binding(priority=None, name=None, nextfactor=None,
                                                           gotopriorityexpression=None, secondary=None, policy=None,
                                                           groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationpolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): On success invoke label.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    secondary(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationpolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationpolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationpolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationpolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationpolicy_binding', payload)

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


def add_authenticationvserver_authenticationradiuspolicy_binding(priority=None, name=None, nextfactor=None,
                                                                 gotopriorityexpression=None, secondary=None,
                                                                 policy=None, groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationradiuspolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Bind the authentication policy to the secondary chain. Provides for multifactor authentication in which
        a user must authenticate via both a primary authentication method and, afterward, via a secondary authentication
        method. Because user groups are aggregated across authentication systems, usernames must be the same on all
        authentication servers. Passwords can be different.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationradiuspolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationradiuspolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationradiuspolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationradiuspolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationradiuspolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationradiuspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationradiuspolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationradiuspolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationradiuspolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationradiuspolicy_binding', payload)

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


def add_authenticationvserver_authenticationsamlidppolicy_binding(priority=None, name=None, nextfactor=None,
                                                                  gotopriorityexpression=None, secondary=None,
                                                                  policy=None, groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationsamlidppolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationsamlidppolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationsamlidppolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationsamlidppolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationsamlidppolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationsamlidppolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationsamlidppolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationsamlidppolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationsamlidppolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationsamlidppolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationsamlidppolicy_binding', payload)

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


def add_authenticationvserver_authenticationsamlpolicy_binding(priority=None, name=None, nextfactor=None,
                                                               gotopriorityexpression=None, secondary=None, policy=None,
                                                               groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationsamlpolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Bind the authentication policy to the secondary chain. Provides for multifactor authentication in which
        a user must authenticate via both a primary authentication method and, afterward, via a secondary authentication
        method. Because user groups are aggregated across authentication systems, usernames must be the same on all
        authentication servers. Passwords can be different.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationsamlpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationsamlpolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationsamlpolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationsamlpolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationsamlpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationsamlpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationsamlpolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationsamlpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationsamlpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationsamlpolicy_binding', payload)

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


def add_authenticationvserver_authenticationtacacspolicy_binding(priority=None, name=None, nextfactor=None,
                                                                 gotopriorityexpression=None, secondary=None,
                                                                 policy=None, groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationtacacspolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Bind the authentication policy to the secondary chain. Provides for multifactor authentication in which
        a user must authenticate via both a primary authentication method and, afterward, via a secondary authentication
        method. Because user groups are aggregated across authentication systems, usernames must be the same on all
        authentication servers. Passwords can be different.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationtacacspolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationtacacspolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationtacacspolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationtacacspolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationtacacspolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationtacacspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationtacacspolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationtacacspolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationtacacspolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationtacacspolicy_binding', payload)

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


def add_authenticationvserver_authenticationwebauthpolicy_binding(priority=None, name=None, nextfactor=None,
                                                                  gotopriorityexpression=None, secondary=None,
                                                                  policy=None, groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_authenticationwebauthpolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Applicable only to advance authentication policy. Expression or other value specifying the
        next policy to be evaluated if the current policy evaluates to TRUE. Specify one of the following values: * NEXT
        - Evaluate the policy with the next higher priority number. * END - End policy evaluation. *
        USE_INVOCATION_RESULT - Applicable if this policy invokes another policy label. If the final goto in the invoked
        policy label has a value of END, the evaluation stops. If the final goto is anything other than END, the current
        policy label performs a NEXT. * A default syntax expression that evaluates to a number. If you specify an
        expression, the number to which it evaluates determines the next policy to evaluate, as follows: * If the
        expression evaluates to a higher numbered priority, the policy with that priority is evaluated next. * If the
        expression evaluates to the priority of the current policy, the policy with the next higher numbered priority is
        evaluated next. * If the expression evaluates to a priority number that is numerically higher than the highest
        numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The expression is invalid. * The
        expression evaluates to a priority number that is numerically lower than the current policys priority. * The
        expression evaluates to a priority number that is between the current policys priority number (say, 30) and the
        highest priority number (say, 100), but does not match any configured priority number (for example, the
        expression evaluates to the number 85). This example assumes that the priority number increments by 10 for every
        successive policy, and therefore a priority number of 85 does not exist in the policy label.

    secondary(bool): Bind the authentication policy to the secondary chain. Provides for multifactor authentication in which
        a user must authenticate via both a primary authentication method and, afterward, via a secondary authentication
        method. Because user groups are aggregated across authentication systems, usernames must be the same on all
        authentication servers. Passwords can be different.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_authenticationwebauthpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_authenticationwebauthpolicy_binding': {}}

    if priority:
        payload['authenticationvserver_authenticationwebauthpolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_authenticationwebauthpolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_authenticationwebauthpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_authenticationwebauthpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_authenticationwebauthpolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_authenticationwebauthpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_authenticationwebauthpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_authenticationwebauthpolicy_binding', payload)

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


def add_authenticationvserver_cspolicy_binding(priority=None, name=None, nextfactor=None, gotopriorityexpression=None,
                                               secondary=None, policy=None, groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_cspolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    secondary(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_cspolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_cspolicy_binding': {}}

    if priority:
        payload['authenticationvserver_cspolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_cspolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_cspolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_cspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_cspolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_cspolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_cspolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_cspolicy_binding', payload)

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


def add_authenticationvserver_tmsessionpolicy_binding(priority=None, name=None, nextfactor=None,
                                                      gotopriorityexpression=None, secondary=None, policy=None,
                                                      groupextraction=None, save=False):
    '''
    Add a new authenticationvserver_tmsessionpolicy_binding to the running configuration.

    priority(int): The priority, if any, of the vpn vserver policy.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    nextfactor(str): Applicable only while binding advance authentication policy as classic authentication policy does not
        support nFactor.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    secondary(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    policy(str): The name of the policy, if any, bound to the authentication vserver.

    groupextraction(bool): Applicable only while bindind classic authentication policy as advance authentication policy use
        nFactor.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_tmsessionpolicy_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_tmsessionpolicy_binding': {}}

    if priority:
        payload['authenticationvserver_tmsessionpolicy_binding']['priority'] = priority

    if name:
        payload['authenticationvserver_tmsessionpolicy_binding']['name'] = name

    if nextfactor:
        payload['authenticationvserver_tmsessionpolicy_binding']['nextfactor'] = nextfactor

    if gotopriorityexpression:
        payload['authenticationvserver_tmsessionpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if secondary:
        payload['authenticationvserver_tmsessionpolicy_binding']['secondary'] = secondary

    if policy:
        payload['authenticationvserver_tmsessionpolicy_binding']['policy'] = policy

    if groupextraction:
        payload['authenticationvserver_tmsessionpolicy_binding']['groupextraction'] = groupextraction

    execution = __proxy__['citrixns.post']('config/authenticationvserver_tmsessionpolicy_binding', payload)

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


def add_authenticationvserver_vpnportaltheme_binding(name=None, portaltheme=None, save=False):
    '''
    Add a new authenticationvserver_vpnportaltheme_binding to the running configuration.

    name(str): Name of the authentication virtual server to which to bind the policy. Minimum length = 1

    portaltheme(str): Theme for Authentication virtual server Login portal.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationvserver_vpnportaltheme_binding <args>

    '''

    result = {}

    payload = {'authenticationvserver_vpnportaltheme_binding': {}}

    if name:
        payload['authenticationvserver_vpnportaltheme_binding']['name'] = name

    if portaltheme:
        payload['authenticationvserver_vpnportaltheme_binding']['portaltheme'] = portaltheme

    execution = __proxy__['citrixns.post']('config/authenticationvserver_vpnportaltheme_binding', payload)

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


def add_authenticationwebauthaction(name=None, serverip=None, serverport=None, fullreqexpr=None, scheme=None,
                                    successrule=None, defaultauthenticationgroup=None, attribute1=None, attribute2=None,
                                    attribute3=None, attribute4=None, attribute5=None, attribute6=None, attribute7=None,
                                    attribute8=None, attribute9=None, attribute10=None, attribute11=None,
                                    attribute12=None, attribute13=None, attribute14=None, attribute15=None,
                                    attribute16=None, save=False):
    '''
    Add a new authenticationwebauthaction to the running configuration.

    name(str): Name for the Web Authentication action.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the profile is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication action" or my authentication action). Minimum length = 1

    serverip(str): IP address of the web server to be used for authentication. Minimum length = 1

    serverport(int): Port on which the web server accepts connections. Minimum value = 1 Range 1 - 65535 * in CLI is
        represented as 65535 in NITRO API

    fullreqexpr(str): Exact HTTP request, in the form of a default syntax expression, which the NetScaler appliance sends to
        the authentication server. The NetScaler appliance does not check the validity of this request. One must manually
        validate the request.

    scheme(str): Type of scheme for the web server. Possible values = http, https

    successrule(str): Expression, that checks to see if authentication is successful.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Expression that would be evaluated to extract attribute1 from the webauth response. Maximum length =
        128

    attribute2(str): Expression that would be evaluated to extract attribute2 from the webauth response. Maximum length =
        128

    attribute3(str): Expression that would be evaluated to extract attribute3 from the webauth response. Maximum length =
        128

    attribute4(str): Expression that would be evaluated to extract attribute4 from the webauth response. Maximum length =
        128

    attribute5(str): Expression that would be evaluated to extract attribute5 from the webauth response. Maximum length =
        128

    attribute6(str): Expression that would be evaluated to extract attribute6 from the webauth response. Maximum length =
        128

    attribute7(str): Expression that would be evaluated to extract attribute7 from the webauth response. Maximum length =
        128

    attribute8(str): Expression that would be evaluated to extract attribute8 from the webauth response. Maximum length =
        128

    attribute9(str): Expression that would be evaluated to extract attribute9 from the webauth response. Maximum length =
        128

    attribute10(str): Expression that would be evaluated to extract attribute10 from the webauth response. Maximum length =
        128

    attribute11(str): Expression that would be evaluated to extract attribute11 from the webauth response. Maximum length =
        128

    attribute12(str): Expression that would be evaluated to extract attribute12 from the webauth response. Maximum length =
        128

    attribute13(str): Expression that would be evaluated to extract attribute13 from the webauth response. Maximum length =
        128

    attribute14(str): Expression that would be evaluated to extract attribute14 from the webauth response. Maximum length =
        128

    attribute15(str): Expression that would be evaluated to extract attribute15 from the webauth response. Maximum length =
        128

    attribute16(str): Expression that would be evaluated to extract attribute16 from the webauth response. Maximum length =
        128

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationwebauthaction <args>

    '''

    result = {}

    payload = {'authenticationwebauthaction': {}}

    if name:
        payload['authenticationwebauthaction']['name'] = name

    if serverip:
        payload['authenticationwebauthaction']['serverip'] = serverip

    if serverport:
        payload['authenticationwebauthaction']['serverport'] = serverport

    if fullreqexpr:
        payload['authenticationwebauthaction']['fullreqexpr'] = fullreqexpr

    if scheme:
        payload['authenticationwebauthaction']['scheme'] = scheme

    if successrule:
        payload['authenticationwebauthaction']['successrule'] = successrule

    if defaultauthenticationgroup:
        payload['authenticationwebauthaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationwebauthaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationwebauthaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationwebauthaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationwebauthaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationwebauthaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationwebauthaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationwebauthaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationwebauthaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationwebauthaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationwebauthaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationwebauthaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationwebauthaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationwebauthaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationwebauthaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationwebauthaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationwebauthaction']['attribute16'] = attribute16

    execution = __proxy__['citrixns.post']('config/authenticationwebauthaction', payload)

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


def add_authenticationwebauthpolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new authenticationwebauthpolicy to the running configuration.

    name(str): Name for the WebAuth policy.  Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after LDAP policy is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the Web server. Minimum length = 1

    action(str): Name of the WebAuth action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.add_authenticationwebauthpolicy <args>

    '''

    result = {}

    payload = {'authenticationwebauthpolicy': {}}

    if name:
        payload['authenticationwebauthpolicy']['name'] = name

    if rule:
        payload['authenticationwebauthpolicy']['rule'] = rule

    if action:
        payload['authenticationwebauthpolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/authenticationwebauthpolicy', payload)

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


def disable_authenticationvserver(name=None, save=False):
    '''
    Disables a authenticationvserver matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.disable_authenticationvserver name=foo

    '''

    result = {}

    payload = {'authenticationvserver': {}}

    if name:
        payload['authenticationvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/authenticationvserver?action=disable', payload)

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


def enable_authenticationvserver(name=None, save=False):
    '''
    Enables a authenticationvserver matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.enable_authenticationvserver name=foo

    '''

    result = {}

    payload = {'authenticationvserver': {}}

    if name:
        payload['authenticationvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/authenticationvserver?action=enable', payload)

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


def get_authenticationauthnprofile(name=None, authnvsname=None, authenticationhost=None, authenticationdomain=None,
                                   authenticationlevel=None):
    '''
    Show the running configuration for the authenticationauthnprofile config key.

    name(str): Filters results that only match the name field.

    authnvsname(str): Filters results that only match the authnvsname field.

    authenticationhost(str): Filters results that only match the authenticationhost field.

    authenticationdomain(str): Filters results that only match the authenticationdomain field.

    authenticationlevel(int): Filters results that only match the authenticationlevel field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationauthnprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if authnvsname:
        search_filter.append(['authnvsname', authnvsname])

    if authenticationhost:
        search_filter.append(['authenticationhost', authenticationhost])

    if authenticationdomain:
        search_filter.append(['authenticationdomain', authenticationdomain])

    if authenticationlevel:
        search_filter.append(['authenticationlevel', authenticationlevel])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationauthnprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationauthnprofile')

    return response


def get_authenticationcertaction(name=None, twofactor=None, usernamefield=None, groupnamefield=None,
                                 defaultauthenticationgroup=None):
    '''
    Show the running configuration for the authenticationcertaction config key.

    name(str): Filters results that only match the name field.

    twofactor(str): Filters results that only match the twofactor field.

    usernamefield(str): Filters results that only match the usernamefield field.

    groupnamefield(str): Filters results that only match the groupnamefield field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationcertaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if twofactor:
        search_filter.append(['twofactor', twofactor])

    if usernamefield:
        search_filter.append(['usernamefield', usernamefield])

    if groupnamefield:
        search_filter.append(['groupnamefield', groupnamefield])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationcertaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationcertaction')

    return response


def get_authenticationcertpolicy(name=None, rule=None, reqaction=None):
    '''
    Show the running configuration for the authenticationcertpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationcertpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationcertpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationcertpolicy')

    return response


def get_authenticationcertpolicy_authenticationvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the authenticationcertpolicy_authenticationvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationcertpolicy_authenticationvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationcertpolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationcertpolicy_authenticationvserver_binding')

    return response


def get_authenticationcertpolicy_binding():
    '''
    Show the running configuration for the authenticationcertpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationcertpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationcertpolicy_binding'), 'authenticationcertpolicy_binding')

    return response


def get_authenticationcertpolicy_vpnglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the authenticationcertpolicy_vpnglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationcertpolicy_vpnglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationcertpolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationcertpolicy_vpnglobal_binding')

    return response


def get_authenticationcertpolicy_vpnvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the authenticationcertpolicy_vpnvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationcertpolicy_vpnvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationcertpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationcertpolicy_vpnvserver_binding')

    return response


def get_authenticationdfaaction(name=None, clientid=None, serverurl=None, passphrase=None,
                                defaultauthenticationgroup=None):
    '''
    Show the running configuration for the authenticationdfaaction config key.

    name(str): Filters results that only match the name field.

    clientid(str): Filters results that only match the clientid field.

    serverurl(str): Filters results that only match the serverurl field.

    passphrase(str): Filters results that only match the passphrase field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationdfaaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if clientid:
        search_filter.append(['clientid', clientid])

    if serverurl:
        search_filter.append(['serverurl', serverurl])

    if passphrase:
        search_filter.append(['passphrase', passphrase])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationdfaaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationdfaaction')

    return response


def get_authenticationdfapolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the authenticationdfapolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationdfapolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationdfapolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationdfapolicy')

    return response


def get_authenticationdfapolicy_binding():
    '''
    Show the running configuration for the authenticationdfapolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationdfapolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationdfapolicy_binding'), 'authenticationdfapolicy_binding')

    return response


def get_authenticationdfapolicy_vpnvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the authenticationdfapolicy_vpnvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationdfapolicy_vpnvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationdfapolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationdfapolicy_vpnvserver_binding')

    return response


def get_authenticationepaaction(name=None, csecexpr=None, killprocess=None, deletefiles=None, defaultepagroup=None,
                                quarantinegroup=None):
    '''
    Show the running configuration for the authenticationepaaction config key.

    name(str): Filters results that only match the name field.

    csecexpr(str): Filters results that only match the csecexpr field.

    killprocess(str): Filters results that only match the killprocess field.

    deletefiles(str): Filters results that only match the deletefiles field.

    defaultepagroup(str): Filters results that only match the defaultepagroup field.

    quarantinegroup(str): Filters results that only match the quarantinegroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationepaaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if csecexpr:
        search_filter.append(['csecexpr', csecexpr])

    if killprocess:
        search_filter.append(['killprocess', killprocess])

    if deletefiles:
        search_filter.append(['deletefiles', deletefiles])

    if defaultepagroup:
        search_filter.append(['defaultepagroup', defaultepagroup])

    if quarantinegroup:
        search_filter.append(['quarantinegroup', quarantinegroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationepaaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationepaaction')

    return response


def get_authenticationldapaction(name=None, serverip=None, servername=None, serverport=None, authtimeout=None,
                                 ldapbase=None, ldapbinddn=None, ldapbinddnpassword=None, ldaploginname=None,
                                 searchfilter=None, groupattrname=None, subattributename=None, sectype=None,
                                 svrtype=None, ssonameattribute=None, authentication=None, requireuser=None,
                                 passwdchange=None, nestedgroupextraction=None, maxnestinglevel=None,
                                 followreferrals=None, maxldapreferrals=None, referraldnslookup=None,
                                 mssrvrecordlocation=None, validateservercert=None, ldaphostname=None,
                                 groupnameidentifier=None, groupsearchattribute=None, groupsearchsubattribute=None,
                                 groupsearchfilter=None, defaultauthenticationgroup=None, attribute1=None,
                                 attribute2=None, attribute3=None, attribute4=None, attribute5=None, attribute6=None,
                                 attribute7=None, attribute8=None, attribute9=None, attribute10=None, attribute11=None,
                                 attribute12=None, attribute13=None, attribute14=None, attribute15=None,
                                 attribute16=None):
    '''
    Show the running configuration for the authenticationldapaction config key.

    name(str): Filters results that only match the name field.

    serverip(str): Filters results that only match the serverip field.

    servername(str): Filters results that only match the servername field.

    serverport(int): Filters results that only match the serverport field.

    authtimeout(int): Filters results that only match the authtimeout field.

    ldapbase(str): Filters results that only match the ldapbase field.

    ldapbinddn(str): Filters results that only match the ldapbinddn field.

    ldapbinddnpassword(str): Filters results that only match the ldapbinddnpassword field.

    ldaploginname(str): Filters results that only match the ldaploginname field.

    searchfilter(str): Filters results that only match the searchfilter field.

    groupattrname(str): Filters results that only match the groupattrname field.

    subattributename(str): Filters results that only match the subattributename field.

    sectype(str): Filters results that only match the sectype field.

    svrtype(str): Filters results that only match the svrtype field.

    ssonameattribute(str): Filters results that only match the ssonameattribute field.

    authentication(str): Filters results that only match the authentication field.

    requireuser(str): Filters results that only match the requireuser field.

    passwdchange(str): Filters results that only match the passwdchange field.

    nestedgroupextraction(str): Filters results that only match the nestedgroupextraction field.

    maxnestinglevel(int): Filters results that only match the maxnestinglevel field.

    followreferrals(str): Filters results that only match the followreferrals field.

    maxldapreferrals(int): Filters results that only match the maxldapreferrals field.

    referraldnslookup(str): Filters results that only match the referraldnslookup field.

    mssrvrecordlocation(str): Filters results that only match the mssrvrecordlocation field.

    validateservercert(str): Filters results that only match the validateservercert field.

    ldaphostname(str): Filters results that only match the ldaphostname field.

    groupnameidentifier(str): Filters results that only match the groupnameidentifier field.

    groupsearchattribute(str): Filters results that only match the groupsearchattribute field.

    groupsearchsubattribute(str): Filters results that only match the groupsearchsubattribute field.

    groupsearchfilter(str): Filters results that only match the groupsearchfilter field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    attribute1(str): Filters results that only match the attribute1 field.

    attribute2(str): Filters results that only match the attribute2 field.

    attribute3(str): Filters results that only match the attribute3 field.

    attribute4(str): Filters results that only match the attribute4 field.

    attribute5(str): Filters results that only match the attribute5 field.

    attribute6(str): Filters results that only match the attribute6 field.

    attribute7(str): Filters results that only match the attribute7 field.

    attribute8(str): Filters results that only match the attribute8 field.

    attribute9(str): Filters results that only match the attribute9 field.

    attribute10(str): Filters results that only match the attribute10 field.

    attribute11(str): Filters results that only match the attribute11 field.

    attribute12(str): Filters results that only match the attribute12 field.

    attribute13(str): Filters results that only match the attribute13 field.

    attribute14(str): Filters results that only match the attribute14 field.

    attribute15(str): Filters results that only match the attribute15 field.

    attribute16(str): Filters results that only match the attribute16 field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationldapaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if serverip:
        search_filter.append(['serverip', serverip])

    if servername:
        search_filter.append(['servername', servername])

    if serverport:
        search_filter.append(['serverport', serverport])

    if authtimeout:
        search_filter.append(['authtimeout', authtimeout])

    if ldapbase:
        search_filter.append(['ldapbase', ldapbase])

    if ldapbinddn:
        search_filter.append(['ldapbinddn', ldapbinddn])

    if ldapbinddnpassword:
        search_filter.append(['ldapbinddnpassword', ldapbinddnpassword])

    if ldaploginname:
        search_filter.append(['ldaploginname', ldaploginname])

    if searchfilter:
        search_filter.append(['searchfilter', searchfilter])

    if groupattrname:
        search_filter.append(['groupattrname', groupattrname])

    if subattributename:
        search_filter.append(['subattributename', subattributename])

    if sectype:
        search_filter.append(['sectype', sectype])

    if svrtype:
        search_filter.append(['svrtype', svrtype])

    if ssonameattribute:
        search_filter.append(['ssonameattribute', ssonameattribute])

    if authentication:
        search_filter.append(['authentication', authentication])

    if requireuser:
        search_filter.append(['requireuser', requireuser])

    if passwdchange:
        search_filter.append(['passwdchange', passwdchange])

    if nestedgroupextraction:
        search_filter.append(['nestedgroupextraction', nestedgroupextraction])

    if maxnestinglevel:
        search_filter.append(['maxnestinglevel', maxnestinglevel])

    if followreferrals:
        search_filter.append(['followreferrals', followreferrals])

    if maxldapreferrals:
        search_filter.append(['maxldapreferrals', maxldapreferrals])

    if referraldnslookup:
        search_filter.append(['referraldnslookup', referraldnslookup])

    if mssrvrecordlocation:
        search_filter.append(['mssrvrecordlocation', mssrvrecordlocation])

    if validateservercert:
        search_filter.append(['validateservercert', validateservercert])

    if ldaphostname:
        search_filter.append(['ldaphostname', ldaphostname])

    if groupnameidentifier:
        search_filter.append(['groupnameidentifier', groupnameidentifier])

    if groupsearchattribute:
        search_filter.append(['groupsearchattribute', groupsearchattribute])

    if groupsearchsubattribute:
        search_filter.append(['groupsearchsubattribute', groupsearchsubattribute])

    if groupsearchfilter:
        search_filter.append(['groupsearchfilter', groupsearchfilter])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    if attribute1:
        search_filter.append(['attribute1', attribute1])

    if attribute2:
        search_filter.append(['attribute2', attribute2])

    if attribute3:
        search_filter.append(['attribute3', attribute3])

    if attribute4:
        search_filter.append(['attribute4', attribute4])

    if attribute5:
        search_filter.append(['attribute5', attribute5])

    if attribute6:
        search_filter.append(['attribute6', attribute6])

    if attribute7:
        search_filter.append(['attribute7', attribute7])

    if attribute8:
        search_filter.append(['attribute8', attribute8])

    if attribute9:
        search_filter.append(['attribute9', attribute9])

    if attribute10:
        search_filter.append(['attribute10', attribute10])

    if attribute11:
        search_filter.append(['attribute11', attribute11])

    if attribute12:
        search_filter.append(['attribute12', attribute12])

    if attribute13:
        search_filter.append(['attribute13', attribute13])

    if attribute14:
        search_filter.append(['attribute14', attribute14])

    if attribute15:
        search_filter.append(['attribute15', attribute15])

    if attribute16:
        search_filter.append(['attribute16', attribute16])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationldapaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationldapaction')

    return response


def get_authenticationldappolicy(name=None, rule=None, reqaction=None):
    '''
    Show the running configuration for the authenticationldappolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationldappolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationldappolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationldappolicy')

    return response


def get_authenticationldappolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationldappolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationldappolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationldappolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationldappolicy_authenticationvserver_binding')

    return response


def get_authenticationldappolicy_binding():
    '''
    Show the running configuration for the authenticationldappolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationldappolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationldappolicy_binding'), 'authenticationldappolicy_binding')

    return response


def get_authenticationldappolicy_systemglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationldappolicy_systemglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationldappolicy_systemglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationldappolicy_systemglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationldappolicy_systemglobal_binding')

    return response


def get_authenticationldappolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationldappolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationldappolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationldappolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationldappolicy_vpnglobal_binding')

    return response


def get_authenticationldappolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationldappolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationldappolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationldappolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationldappolicy_vpnvserver_binding')

    return response


def get_authenticationlocalpolicy(name=None, rule=None):
    '''
    Show the running configuration for the authenticationlocalpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationlocalpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationlocalpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationlocalpolicy')

    return response


def get_authenticationlocalpolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationlocalpolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationlocalpolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationlocalpolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationlocalpolicy_authenticationvserver_binding')

    return response


def get_authenticationlocalpolicy_binding():
    '''
    Show the running configuration for the authenticationlocalpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationlocalpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationlocalpolicy_binding'), 'authenticationlocalpolicy_binding')

    return response


def get_authenticationlocalpolicy_systemglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationlocalpolicy_systemglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationlocalpolicy_systemglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationlocalpolicy_systemglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationlocalpolicy_systemglobal_binding')

    return response


def get_authenticationlocalpolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationlocalpolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationlocalpolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationlocalpolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationlocalpolicy_vpnglobal_binding')

    return response


def get_authenticationlocalpolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationlocalpolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationlocalpolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationlocalpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationlocalpolicy_vpnvserver_binding')

    return response


def get_authenticationloginschema(name=None, authenticationschema=None, userexpression=None, passwdexpression=None,
                                  usercredentialindex=None, passwordcredentialindex=None, authenticationstrength=None,
                                  ssocredentials=None):
    '''
    Show the running configuration for the authenticationloginschema config key.

    name(str): Filters results that only match the name field.

    authenticationschema(str): Filters results that only match the authenticationschema field.

    userexpression(str): Filters results that only match the userexpression field.

    passwdexpression(str): Filters results that only match the passwdexpression field.

    usercredentialindex(int): Filters results that only match the usercredentialindex field.

    passwordcredentialindex(int): Filters results that only match the passwordcredentialindex field.

    authenticationstrength(int): Filters results that only match the authenticationstrength field.

    ssocredentials(str): Filters results that only match the ssocredentials field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationloginschema

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if authenticationschema:
        search_filter.append(['authenticationschema', authenticationschema])

    if userexpression:
        search_filter.append(['userexpression', userexpression])

    if passwdexpression:
        search_filter.append(['passwdexpression', passwdexpression])

    if usercredentialindex:
        search_filter.append(['usercredentialindex', usercredentialindex])

    if passwordcredentialindex:
        search_filter.append(['passwordcredentialindex', passwordcredentialindex])

    if authenticationstrength:
        search_filter.append(['authenticationstrength', authenticationstrength])

    if ssocredentials:
        search_filter.append(['ssocredentials', ssocredentials])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationloginschema{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationloginschema')

    return response


def get_authenticationloginschemapolicy(name=None, rule=None, action=None, undefaction=None, comment=None,
                                        logaction=None, newname=None):
    '''
    Show the running configuration for the authenticationloginschemapolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationloginschemapolicy

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
            __proxy__['citrixns.get']('config/authenticationloginschemapolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationloginschemapolicy')

    return response


def get_authenticationloginschemapolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationloginschemapolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationloginschemapolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationloginschemapolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationloginschemapolicy_authenticationvserver_binding')

    return response


def get_authenticationloginschemapolicy_binding():
    '''
    Show the running configuration for the authenticationloginschemapolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationloginschemapolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationloginschemapolicy_binding'), 'authenticationloginschemapolicy_binding')

    return response


def get_authenticationloginschemapolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationloginschemapolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationloginschemapolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationloginschemapolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationloginschemapolicy_vpnvserver_binding')

    return response


def get_authenticationnegotiateaction(name=None, domain=None, domainuser=None, domainuserpasswd=None, ou=None,
                                      defaultauthenticationgroup=None, keytab=None, ntlmpath=None):
    '''
    Show the running configuration for the authenticationnegotiateaction config key.

    name(str): Filters results that only match the name field.

    domain(str): Filters results that only match the domain field.

    domainuser(str): Filters results that only match the domainuser field.

    domainuserpasswd(str): Filters results that only match the domainuserpasswd field.

    ou(str): Filters results that only match the ou field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    keytab(str): Filters results that only match the keytab field.

    ntlmpath(str): Filters results that only match the ntlmpath field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationnegotiateaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if domain:
        search_filter.append(['domain', domain])

    if domainuser:
        search_filter.append(['domainuser', domainuser])

    if domainuserpasswd:
        search_filter.append(['domainuserpasswd', domainuserpasswd])

    if ou:
        search_filter.append(['ou', ou])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    if keytab:
        search_filter.append(['keytab', keytab])

    if ntlmpath:
        search_filter.append(['ntlmpath', ntlmpath])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationnegotiateaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationnegotiateaction')

    return response


def get_authenticationnegotiatepolicy(name=None, rule=None, reqaction=None):
    '''
    Show the running configuration for the authenticationnegotiatepolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationnegotiatepolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationnegotiatepolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationnegotiatepolicy')

    return response


def get_authenticationnegotiatepolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationnegotiatepolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationnegotiatepolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationnegotiatepolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationnegotiatepolicy_authenticationvserver_binding')

    return response


def get_authenticationnegotiatepolicy_binding():
    '''
    Show the running configuration for the authenticationnegotiatepolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationnegotiatepolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationnegotiatepolicy_binding'), 'authenticationnegotiatepolicy_binding')

    return response


def get_authenticationnegotiatepolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationnegotiatepolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationnegotiatepolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationnegotiatepolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationnegotiatepolicy_vpnglobal_binding')

    return response


def get_authenticationnegotiatepolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationnegotiatepolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationnegotiatepolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationnegotiatepolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationnegotiatepolicy_vpnvserver_binding')

    return response


def get_authenticationoauthaction(name=None, oauthtype=None, authorizationendpoint=None, tokenendpoint=None,
                                  idtokendecryptendpoint=None, clientid=None, clientsecret=None,
                                  defaultauthenticationgroup=None, attribute1=None, attribute2=None, attribute3=None,
                                  attribute4=None, attribute5=None, attribute6=None, attribute7=None, attribute8=None,
                                  attribute9=None, attribute10=None, attribute11=None, attribute12=None,
                                  attribute13=None, attribute14=None, attribute15=None, attribute16=None, tenantid=None,
                                  graphendpoint=None, refreshinterval=None, certendpoint=None, audience=None,
                                  usernamefield=None, skewtime=None, issuer=None):
    '''
    Show the running configuration for the authenticationoauthaction config key.

    name(str): Filters results that only match the name field.

    oauthtype(str): Filters results that only match the oauthtype field.

    authorizationendpoint(str): Filters results that only match the authorizationendpoint field.

    tokenendpoint(str): Filters results that only match the tokenendpoint field.

    idtokendecryptendpoint(str): Filters results that only match the idtokendecryptendpoint field.

    clientid(str): Filters results that only match the clientid field.

    clientsecret(str): Filters results that only match the clientsecret field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    attribute1(str): Filters results that only match the attribute1 field.

    attribute2(str): Filters results that only match the attribute2 field.

    attribute3(str): Filters results that only match the attribute3 field.

    attribute4(str): Filters results that only match the attribute4 field.

    attribute5(str): Filters results that only match the attribute5 field.

    attribute6(str): Filters results that only match the attribute6 field.

    attribute7(str): Filters results that only match the attribute7 field.

    attribute8(str): Filters results that only match the attribute8 field.

    attribute9(str): Filters results that only match the attribute9 field.

    attribute10(str): Filters results that only match the attribute10 field.

    attribute11(str): Filters results that only match the attribute11 field.

    attribute12(str): Filters results that only match the attribute12 field.

    attribute13(str): Filters results that only match the attribute13 field.

    attribute14(str): Filters results that only match the attribute14 field.

    attribute15(str): Filters results that only match the attribute15 field.

    attribute16(str): Filters results that only match the attribute16 field.

    tenantid(str): Filters results that only match the tenantid field.

    graphendpoint(str): Filters results that only match the graphendpoint field.

    refreshinterval(int): Filters results that only match the refreshinterval field.

    certendpoint(str): Filters results that only match the certendpoint field.

    audience(str): Filters results that only match the audience field.

    usernamefield(str): Filters results that only match the usernamefield field.

    skewtime(int): Filters results that only match the skewtime field.

    issuer(str): Filters results that only match the issuer field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationoauthaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if oauthtype:
        search_filter.append(['oauthtype', oauthtype])

    if authorizationendpoint:
        search_filter.append(['authorizationendpoint', authorizationendpoint])

    if tokenendpoint:
        search_filter.append(['tokenendpoint', tokenendpoint])

    if idtokendecryptendpoint:
        search_filter.append(['idtokendecryptendpoint', idtokendecryptendpoint])

    if clientid:
        search_filter.append(['clientid', clientid])

    if clientsecret:
        search_filter.append(['clientsecret', clientsecret])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    if attribute1:
        search_filter.append(['attribute1', attribute1])

    if attribute2:
        search_filter.append(['attribute2', attribute2])

    if attribute3:
        search_filter.append(['attribute3', attribute3])

    if attribute4:
        search_filter.append(['attribute4', attribute4])

    if attribute5:
        search_filter.append(['attribute5', attribute5])

    if attribute6:
        search_filter.append(['attribute6', attribute6])

    if attribute7:
        search_filter.append(['attribute7', attribute7])

    if attribute8:
        search_filter.append(['attribute8', attribute8])

    if attribute9:
        search_filter.append(['attribute9', attribute9])

    if attribute10:
        search_filter.append(['attribute10', attribute10])

    if attribute11:
        search_filter.append(['attribute11', attribute11])

    if attribute12:
        search_filter.append(['attribute12', attribute12])

    if attribute13:
        search_filter.append(['attribute13', attribute13])

    if attribute14:
        search_filter.append(['attribute14', attribute14])

    if attribute15:
        search_filter.append(['attribute15', attribute15])

    if attribute16:
        search_filter.append(['attribute16', attribute16])

    if tenantid:
        search_filter.append(['tenantid', tenantid])

    if graphendpoint:
        search_filter.append(['graphendpoint', graphendpoint])

    if refreshinterval:
        search_filter.append(['refreshinterval', refreshinterval])

    if certendpoint:
        search_filter.append(['certendpoint', certendpoint])

    if audience:
        search_filter.append(['audience', audience])

    if usernamefield:
        search_filter.append(['usernamefield', usernamefield])

    if skewtime:
        search_filter.append(['skewtime', skewtime])

    if issuer:
        search_filter.append(['issuer', issuer])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationoauthaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationoauthaction')

    return response


def get_authenticationpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                             newname=None):
    '''
    Show the running configuration for the authenticationpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationpolicy

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
            __proxy__['citrixns.get']('config/authenticationpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationpolicy')

    return response


def get_authenticationpolicy_authenticationpolicylabel_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationpolicy_authenticationpolicylabel_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationpolicy_authenticationpolicylabel_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationpolicy_authenticationpolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationpolicy_authenticationpolicylabel_binding')

    return response


def get_authenticationpolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationpolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationpolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationpolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationpolicy_authenticationvserver_binding')

    return response


def get_authenticationpolicy_binding():
    '''
    Show the running configuration for the authenticationpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationpolicy_binding'), 'authenticationpolicy_binding')

    return response


def get_authenticationpolicylabel(labelname=None, ns_type=None, comment=None, loginschema=None, newname=None):
    '''
    Show the running configuration for the authenticationpolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    ns_type(str): Filters results that only match the type field.

    comment(str): Filters results that only match the comment field.

    loginschema(str): Filters results that only match the loginschema field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationpolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if ns_type:
        search_filter.append(['type', ns_type])

    if comment:
        search_filter.append(['comment', comment])

    if loginschema:
        search_filter.append(['loginschema', loginschema])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationpolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationpolicylabel')

    return response


def get_authenticationpolicylabel_authenticationpolicy_binding(priority=None, nextfactor=None,
                                                               gotopriorityexpression=None, policyname=None,
                                                               labelname=None):
    '''
    Show the running configuration for the authenticationpolicylabel_authenticationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationpolicylabel_authenticationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationpolicylabel_authenticationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationpolicylabel_authenticationpolicy_binding')

    return response


def get_authenticationpolicylabel_binding():
    '''
    Show the running configuration for the authenticationpolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationpolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationpolicylabel_binding'), 'authenticationpolicylabel_binding')

    return response


def get_authenticationradiusaction(name=None, serverip=None, servername=None, serverport=None, authtimeout=None,
                                   radkey=None, radnasip=None, radnasid=None, radvendorid=None, radattributetype=None,
                                   radgroupsprefix=None, radgroupseparator=None, passencoding=None, ipvendorid=None,
                                   ipattributetype=None, accounting=None, pwdvendorid=None, pwdattributetype=None,
                                   defaultauthenticationgroup=None, callingstationid=None, authservretry=None,
                                   authentication=None):
    '''
    Show the running configuration for the authenticationradiusaction config key.

    name(str): Filters results that only match the name field.

    serverip(str): Filters results that only match the serverip field.

    servername(str): Filters results that only match the servername field.

    serverport(int): Filters results that only match the serverport field.

    authtimeout(int): Filters results that only match the authtimeout field.

    radkey(str): Filters results that only match the radkey field.

    radnasip(str): Filters results that only match the radnasip field.

    radnasid(str): Filters results that only match the radnasid field.

    radvendorid(int): Filters results that only match the radvendorid field.

    radattributetype(int): Filters results that only match the radattributetype field.

    radgroupsprefix(str): Filters results that only match the radgroupsprefix field.

    radgroupseparator(str): Filters results that only match the radgroupseparator field.

    passencoding(str): Filters results that only match the passencoding field.

    ipvendorid(int): Filters results that only match the ipvendorid field.

    ipattributetype(int): Filters results that only match the ipattributetype field.

    accounting(str): Filters results that only match the accounting field.

    pwdvendorid(int): Filters results that only match the pwdvendorid field.

    pwdattributetype(int): Filters results that only match the pwdattributetype field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    callingstationid(str): Filters results that only match the callingstationid field.

    authservretry(int): Filters results that only match the authservretry field.

    authentication(str): Filters results that only match the authentication field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationradiusaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if serverip:
        search_filter.append(['serverip', serverip])

    if servername:
        search_filter.append(['servername', servername])

    if serverport:
        search_filter.append(['serverport', serverport])

    if authtimeout:
        search_filter.append(['authtimeout', authtimeout])

    if radkey:
        search_filter.append(['radkey', radkey])

    if radnasip:
        search_filter.append(['radnasip', radnasip])

    if radnasid:
        search_filter.append(['radnasid', radnasid])

    if radvendorid:
        search_filter.append(['radvendorid', radvendorid])

    if radattributetype:
        search_filter.append(['radattributetype', radattributetype])

    if radgroupsprefix:
        search_filter.append(['radgroupsprefix', radgroupsprefix])

    if radgroupseparator:
        search_filter.append(['radgroupseparator', radgroupseparator])

    if passencoding:
        search_filter.append(['passencoding', passencoding])

    if ipvendorid:
        search_filter.append(['ipvendorid', ipvendorid])

    if ipattributetype:
        search_filter.append(['ipattributetype', ipattributetype])

    if accounting:
        search_filter.append(['accounting', accounting])

    if pwdvendorid:
        search_filter.append(['pwdvendorid', pwdvendorid])

    if pwdattributetype:
        search_filter.append(['pwdattributetype', pwdattributetype])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    if callingstationid:
        search_filter.append(['callingstationid', callingstationid])

    if authservretry:
        search_filter.append(['authservretry', authservretry])

    if authentication:
        search_filter.append(['authentication', authentication])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationradiusaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationradiusaction')

    return response


def get_authenticationradiuspolicy(name=None, rule=None, reqaction=None):
    '''
    Show the running configuration for the authenticationradiuspolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationradiuspolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationradiuspolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationradiuspolicy')

    return response


def get_authenticationradiuspolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationradiuspolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationradiuspolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationradiuspolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationradiuspolicy_authenticationvserver_binding')

    return response


def get_authenticationradiuspolicy_binding():
    '''
    Show the running configuration for the authenticationradiuspolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationradiuspolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationradiuspolicy_binding'), 'authenticationradiuspolicy_binding')

    return response


def get_authenticationradiuspolicy_systemglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationradiuspolicy_systemglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationradiuspolicy_systemglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationradiuspolicy_systemglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationradiuspolicy_systemglobal_binding')

    return response


def get_authenticationradiuspolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationradiuspolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationradiuspolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationradiuspolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationradiuspolicy_vpnglobal_binding')

    return response


def get_authenticationradiuspolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationradiuspolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationradiuspolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationradiuspolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationradiuspolicy_vpnvserver_binding')

    return response


def get_authenticationsamlaction(name=None, samlidpcertname=None, samlsigningcertname=None, samlredirecturl=None,
                                 samlacsindex=None, samluserfield=None, samlrejectunsignedassertion=None,
                                 samlissuername=None, samltwofactor=None, defaultauthenticationgroup=None,
                                 attribute1=None, attribute2=None, attribute3=None, attribute4=None, attribute5=None,
                                 attribute6=None, attribute7=None, attribute8=None, attribute9=None, attribute10=None,
                                 attribute11=None, attribute12=None, attribute13=None, attribute14=None,
                                 attribute15=None, attribute16=None, signaturealg=None, digestmethod=None,
                                 requestedauthncontext=None, authnctxclassref=None, samlbinding=None,
                                 attributeconsumingserviceindex=None, sendthumbprint=None, enforceusername=None,
                                 logouturl=None, artifactresolutionserviceurl=None, skewtime=None, logoutbinding=None,
                                 forceauthn=None):
    '''
    Show the running configuration for the authenticationsamlaction config key.

    name(str): Filters results that only match the name field.

    samlidpcertname(str): Filters results that only match the samlidpcertname field.

    samlsigningcertname(str): Filters results that only match the samlsigningcertname field.

    samlredirecturl(str): Filters results that only match the samlredirecturl field.

    samlacsindex(int): Filters results that only match the samlacsindex field.

    samluserfield(str): Filters results that only match the samluserfield field.

    samlrejectunsignedassertion(str): Filters results that only match the samlrejectunsignedassertion field.

    samlissuername(str): Filters results that only match the samlissuername field.

    samltwofactor(str): Filters results that only match the samltwofactor field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    attribute1(str): Filters results that only match the attribute1 field.

    attribute2(str): Filters results that only match the attribute2 field.

    attribute3(str): Filters results that only match the attribute3 field.

    attribute4(str): Filters results that only match the attribute4 field.

    attribute5(str): Filters results that only match the attribute5 field.

    attribute6(str): Filters results that only match the attribute6 field.

    attribute7(str): Filters results that only match the attribute7 field.

    attribute8(str): Filters results that only match the attribute8 field.

    attribute9(str): Filters results that only match the attribute9 field.

    attribute10(str): Filters results that only match the attribute10 field.

    attribute11(str): Filters results that only match the attribute11 field.

    attribute12(str): Filters results that only match the attribute12 field.

    attribute13(str): Filters results that only match the attribute13 field.

    attribute14(str): Filters results that only match the attribute14 field.

    attribute15(str): Filters results that only match the attribute15 field.

    attribute16(str): Filters results that only match the attribute16 field.

    signaturealg(str): Filters results that only match the signaturealg field.

    digestmethod(str): Filters results that only match the digestmethod field.

    requestedauthncontext(str): Filters results that only match the requestedauthncontext field.

    authnctxclassref(list(str)): Filters results that only match the authnctxclassref field.

    samlbinding(str): Filters results that only match the samlbinding field.

    attributeconsumingserviceindex(int): Filters results that only match the attributeconsumingserviceindex field.

    sendthumbprint(str): Filters results that only match the sendthumbprint field.

    enforceusername(str): Filters results that only match the enforceusername field.

    logouturl(str): Filters results that only match the logouturl field.

    artifactresolutionserviceurl(str): Filters results that only match the artifactresolutionserviceurl field.

    skewtime(int): Filters results that only match the skewtime field.

    logoutbinding(str): Filters results that only match the logoutbinding field.

    forceauthn(str): Filters results that only match the forceauthn field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if samlidpcertname:
        search_filter.append(['samlidpcertname', samlidpcertname])

    if samlsigningcertname:
        search_filter.append(['samlsigningcertname', samlsigningcertname])

    if samlredirecturl:
        search_filter.append(['samlredirecturl', samlredirecturl])

    if samlacsindex:
        search_filter.append(['samlacsindex', samlacsindex])

    if samluserfield:
        search_filter.append(['samluserfield', samluserfield])

    if samlrejectunsignedassertion:
        search_filter.append(['samlrejectunsignedassertion', samlrejectunsignedassertion])

    if samlissuername:
        search_filter.append(['samlissuername', samlissuername])

    if samltwofactor:
        search_filter.append(['samltwofactor', samltwofactor])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    if attribute1:
        search_filter.append(['attribute1', attribute1])

    if attribute2:
        search_filter.append(['attribute2', attribute2])

    if attribute3:
        search_filter.append(['attribute3', attribute3])

    if attribute4:
        search_filter.append(['attribute4', attribute4])

    if attribute5:
        search_filter.append(['attribute5', attribute5])

    if attribute6:
        search_filter.append(['attribute6', attribute6])

    if attribute7:
        search_filter.append(['attribute7', attribute7])

    if attribute8:
        search_filter.append(['attribute8', attribute8])

    if attribute9:
        search_filter.append(['attribute9', attribute9])

    if attribute10:
        search_filter.append(['attribute10', attribute10])

    if attribute11:
        search_filter.append(['attribute11', attribute11])

    if attribute12:
        search_filter.append(['attribute12', attribute12])

    if attribute13:
        search_filter.append(['attribute13', attribute13])

    if attribute14:
        search_filter.append(['attribute14', attribute14])

    if attribute15:
        search_filter.append(['attribute15', attribute15])

    if attribute16:
        search_filter.append(['attribute16', attribute16])

    if signaturealg:
        search_filter.append(['signaturealg', signaturealg])

    if digestmethod:
        search_filter.append(['digestmethod', digestmethod])

    if requestedauthncontext:
        search_filter.append(['requestedauthncontext', requestedauthncontext])

    if authnctxclassref:
        search_filter.append(['authnctxclassref', authnctxclassref])

    if samlbinding:
        search_filter.append(['samlbinding', samlbinding])

    if attributeconsumingserviceindex:
        search_filter.append(['attributeconsumingserviceindex', attributeconsumingserviceindex])

    if sendthumbprint:
        search_filter.append(['sendthumbprint', sendthumbprint])

    if enforceusername:
        search_filter.append(['enforceusername', enforceusername])

    if logouturl:
        search_filter.append(['logouturl', logouturl])

    if artifactresolutionserviceurl:
        search_filter.append(['artifactresolutionserviceurl', artifactresolutionserviceurl])

    if skewtime:
        search_filter.append(['skewtime', skewtime])

    if logoutbinding:
        search_filter.append(['logoutbinding', logoutbinding])

    if forceauthn:
        search_filter.append(['forceauthn', forceauthn])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlaction')

    return response


def get_authenticationsamlidppolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                    newname=None):
    '''
    Show the running configuration for the authenticationsamlidppolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlidppolicy

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
            __proxy__['citrixns.get']('config/authenticationsamlidppolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlidppolicy')

    return response


def get_authenticationsamlidppolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationsamlidppolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlidppolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlidppolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlidppolicy_authenticationvserver_binding')

    return response


def get_authenticationsamlidppolicy_binding():
    '''
    Show the running configuration for the authenticationsamlidppolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlidppolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlidppolicy_binding'), 'authenticationsamlidppolicy_binding')

    return response


def get_authenticationsamlidppolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationsamlidppolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlidppolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlidppolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlidppolicy_vpnvserver_binding')

    return response


def get_authenticationsamlidpprofile(name=None, samlspcertname=None, samlidpcertname=None,
                                     assertionconsumerserviceurl=None, sendpassword=None, samlissuername=None,
                                     rejectunsignedrequests=None, signaturealg=None, digestmethod=None, audience=None,
                                     nameidformat=None, nameidexpr=None, attribute1=None, attribute1expr=None,
                                     attribute1friendlyname=None, attribute1format=None, attribute2=None,
                                     attribute2expr=None, attribute2friendlyname=None, attribute2format=None,
                                     attribute3=None, attribute3expr=None, attribute3friendlyname=None,
                                     attribute3format=None, attribute4=None, attribute4expr=None,
                                     attribute4friendlyname=None, attribute4format=None, attribute5=None,
                                     attribute5expr=None, attribute5friendlyname=None, attribute5format=None,
                                     attribute6=None, attribute6expr=None, attribute6friendlyname=None,
                                     attribute6format=None, attribute7=None, attribute7expr=None,
                                     attribute7friendlyname=None, attribute7format=None, attribute8=None,
                                     attribute8expr=None, attribute8friendlyname=None, attribute8format=None,
                                     attribute9=None, attribute9expr=None, attribute9friendlyname=None,
                                     attribute9format=None, attribute10=None, attribute10expr=None,
                                     attribute10friendlyname=None, attribute10format=None, attribute11=None,
                                     attribute11expr=None, attribute11friendlyname=None, attribute11format=None,
                                     attribute12=None, attribute12expr=None, attribute12friendlyname=None,
                                     attribute12format=None, attribute13=None, attribute13expr=None,
                                     attribute13friendlyname=None, attribute13format=None, attribute14=None,
                                     attribute14expr=None, attribute14friendlyname=None, attribute14format=None,
                                     attribute15=None, attribute15expr=None, attribute15friendlyname=None,
                                     attribute15format=None, attribute16=None, attribute16expr=None,
                                     attribute16friendlyname=None, attribute16format=None, encryptassertion=None,
                                     encryptionalgorithm=None, samlbinding=None, skewtime=None, serviceproviderid=None,
                                     signassertion=None, keytransportalg=None, splogouturl=None, logoutbinding=None):
    '''
    Show the running configuration for the authenticationsamlidpprofile config key.

    name(str): Filters results that only match the name field.

    samlspcertname(str): Filters results that only match the samlspcertname field.

    samlidpcertname(str): Filters results that only match the samlidpcertname field.

    assertionconsumerserviceurl(str): Filters results that only match the assertionconsumerserviceurl field.

    sendpassword(str): Filters results that only match the sendpassword field.

    samlissuername(str): Filters results that only match the samlissuername field.

    rejectunsignedrequests(str): Filters results that only match the rejectunsignedrequests field.

    signaturealg(str): Filters results that only match the signaturealg field.

    digestmethod(str): Filters results that only match the digestmethod field.

    audience(str): Filters results that only match the audience field.

    nameidformat(str): Filters results that only match the nameidformat field.

    nameidexpr(str): Filters results that only match the nameidexpr field.

    attribute1(str): Filters results that only match the attribute1 field.

    attribute1expr(str): Filters results that only match the attribute1expr field.

    attribute1friendlyname(str): Filters results that only match the attribute1friendlyname field.

    attribute1format(str): Filters results that only match the attribute1format field.

    attribute2(str): Filters results that only match the attribute2 field.

    attribute2expr(str): Filters results that only match the attribute2expr field.

    attribute2friendlyname(str): Filters results that only match the attribute2friendlyname field.

    attribute2format(str): Filters results that only match the attribute2format field.

    attribute3(str): Filters results that only match the attribute3 field.

    attribute3expr(str): Filters results that only match the attribute3expr field.

    attribute3friendlyname(str): Filters results that only match the attribute3friendlyname field.

    attribute3format(str): Filters results that only match the attribute3format field.

    attribute4(str): Filters results that only match the attribute4 field.

    attribute4expr(str): Filters results that only match the attribute4expr field.

    attribute4friendlyname(str): Filters results that only match the attribute4friendlyname field.

    attribute4format(str): Filters results that only match the attribute4format field.

    attribute5(str): Filters results that only match the attribute5 field.

    attribute5expr(str): Filters results that only match the attribute5expr field.

    attribute5friendlyname(str): Filters results that only match the attribute5friendlyname field.

    attribute5format(str): Filters results that only match the attribute5format field.

    attribute6(str): Filters results that only match the attribute6 field.

    attribute6expr(str): Filters results that only match the attribute6expr field.

    attribute6friendlyname(str): Filters results that only match the attribute6friendlyname field.

    attribute6format(str): Filters results that only match the attribute6format field.

    attribute7(str): Filters results that only match the attribute7 field.

    attribute7expr(str): Filters results that only match the attribute7expr field.

    attribute7friendlyname(str): Filters results that only match the attribute7friendlyname field.

    attribute7format(str): Filters results that only match the attribute7format field.

    attribute8(str): Filters results that only match the attribute8 field.

    attribute8expr(str): Filters results that only match the attribute8expr field.

    attribute8friendlyname(str): Filters results that only match the attribute8friendlyname field.

    attribute8format(str): Filters results that only match the attribute8format field.

    attribute9(str): Filters results that only match the attribute9 field.

    attribute9expr(str): Filters results that only match the attribute9expr field.

    attribute9friendlyname(str): Filters results that only match the attribute9friendlyname field.

    attribute9format(str): Filters results that only match the attribute9format field.

    attribute10(str): Filters results that only match the attribute10 field.

    attribute10expr(str): Filters results that only match the attribute10expr field.

    attribute10friendlyname(str): Filters results that only match the attribute10friendlyname field.

    attribute10format(str): Filters results that only match the attribute10format field.

    attribute11(str): Filters results that only match the attribute11 field.

    attribute11expr(str): Filters results that only match the attribute11expr field.

    attribute11friendlyname(str): Filters results that only match the attribute11friendlyname field.

    attribute11format(str): Filters results that only match the attribute11format field.

    attribute12(str): Filters results that only match the attribute12 field.

    attribute12expr(str): Filters results that only match the attribute12expr field.

    attribute12friendlyname(str): Filters results that only match the attribute12friendlyname field.

    attribute12format(str): Filters results that only match the attribute12format field.

    attribute13(str): Filters results that only match the attribute13 field.

    attribute13expr(str): Filters results that only match the attribute13expr field.

    attribute13friendlyname(str): Filters results that only match the attribute13friendlyname field.

    attribute13format(str): Filters results that only match the attribute13format field.

    attribute14(str): Filters results that only match the attribute14 field.

    attribute14expr(str): Filters results that only match the attribute14expr field.

    attribute14friendlyname(str): Filters results that only match the attribute14friendlyname field.

    attribute14format(str): Filters results that only match the attribute14format field.

    attribute15(str): Filters results that only match the attribute15 field.

    attribute15expr(str): Filters results that only match the attribute15expr field.

    attribute15friendlyname(str): Filters results that only match the attribute15friendlyname field.

    attribute15format(str): Filters results that only match the attribute15format field.

    attribute16(str): Filters results that only match the attribute16 field.

    attribute16expr(str): Filters results that only match the attribute16expr field.

    attribute16friendlyname(str): Filters results that only match the attribute16friendlyname field.

    attribute16format(str): Filters results that only match the attribute16format field.

    encryptassertion(str): Filters results that only match the encryptassertion field.

    encryptionalgorithm(str): Filters results that only match the encryptionalgorithm field.

    samlbinding(str): Filters results that only match the samlbinding field.

    skewtime(int): Filters results that only match the skewtime field.

    serviceproviderid(str): Filters results that only match the serviceproviderid field.

    signassertion(str): Filters results that only match the signassertion field.

    keytransportalg(str): Filters results that only match the keytransportalg field.

    splogouturl(str): Filters results that only match the splogouturl field.

    logoutbinding(str): Filters results that only match the logoutbinding field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlidpprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if samlspcertname:
        search_filter.append(['samlspcertname', samlspcertname])

    if samlidpcertname:
        search_filter.append(['samlidpcertname', samlidpcertname])

    if assertionconsumerserviceurl:
        search_filter.append(['assertionconsumerserviceurl', assertionconsumerserviceurl])

    if sendpassword:
        search_filter.append(['sendpassword', sendpassword])

    if samlissuername:
        search_filter.append(['samlissuername', samlissuername])

    if rejectunsignedrequests:
        search_filter.append(['rejectunsignedrequests', rejectunsignedrequests])

    if signaturealg:
        search_filter.append(['signaturealg', signaturealg])

    if digestmethod:
        search_filter.append(['digestmethod', digestmethod])

    if audience:
        search_filter.append(['audience', audience])

    if nameidformat:
        search_filter.append(['nameidformat', nameidformat])

    if nameidexpr:
        search_filter.append(['nameidexpr', nameidexpr])

    if attribute1:
        search_filter.append(['attribute1', attribute1])

    if attribute1expr:
        search_filter.append(['attribute1expr', attribute1expr])

    if attribute1friendlyname:
        search_filter.append(['attribute1friendlyname', attribute1friendlyname])

    if attribute1format:
        search_filter.append(['attribute1format', attribute1format])

    if attribute2:
        search_filter.append(['attribute2', attribute2])

    if attribute2expr:
        search_filter.append(['attribute2expr', attribute2expr])

    if attribute2friendlyname:
        search_filter.append(['attribute2friendlyname', attribute2friendlyname])

    if attribute2format:
        search_filter.append(['attribute2format', attribute2format])

    if attribute3:
        search_filter.append(['attribute3', attribute3])

    if attribute3expr:
        search_filter.append(['attribute3expr', attribute3expr])

    if attribute3friendlyname:
        search_filter.append(['attribute3friendlyname', attribute3friendlyname])

    if attribute3format:
        search_filter.append(['attribute3format', attribute3format])

    if attribute4:
        search_filter.append(['attribute4', attribute4])

    if attribute4expr:
        search_filter.append(['attribute4expr', attribute4expr])

    if attribute4friendlyname:
        search_filter.append(['attribute4friendlyname', attribute4friendlyname])

    if attribute4format:
        search_filter.append(['attribute4format', attribute4format])

    if attribute5:
        search_filter.append(['attribute5', attribute5])

    if attribute5expr:
        search_filter.append(['attribute5expr', attribute5expr])

    if attribute5friendlyname:
        search_filter.append(['attribute5friendlyname', attribute5friendlyname])

    if attribute5format:
        search_filter.append(['attribute5format', attribute5format])

    if attribute6:
        search_filter.append(['attribute6', attribute6])

    if attribute6expr:
        search_filter.append(['attribute6expr', attribute6expr])

    if attribute6friendlyname:
        search_filter.append(['attribute6friendlyname', attribute6friendlyname])

    if attribute6format:
        search_filter.append(['attribute6format', attribute6format])

    if attribute7:
        search_filter.append(['attribute7', attribute7])

    if attribute7expr:
        search_filter.append(['attribute7expr', attribute7expr])

    if attribute7friendlyname:
        search_filter.append(['attribute7friendlyname', attribute7friendlyname])

    if attribute7format:
        search_filter.append(['attribute7format', attribute7format])

    if attribute8:
        search_filter.append(['attribute8', attribute8])

    if attribute8expr:
        search_filter.append(['attribute8expr', attribute8expr])

    if attribute8friendlyname:
        search_filter.append(['attribute8friendlyname', attribute8friendlyname])

    if attribute8format:
        search_filter.append(['attribute8format', attribute8format])

    if attribute9:
        search_filter.append(['attribute9', attribute9])

    if attribute9expr:
        search_filter.append(['attribute9expr', attribute9expr])

    if attribute9friendlyname:
        search_filter.append(['attribute9friendlyname', attribute9friendlyname])

    if attribute9format:
        search_filter.append(['attribute9format', attribute9format])

    if attribute10:
        search_filter.append(['attribute10', attribute10])

    if attribute10expr:
        search_filter.append(['attribute10expr', attribute10expr])

    if attribute10friendlyname:
        search_filter.append(['attribute10friendlyname', attribute10friendlyname])

    if attribute10format:
        search_filter.append(['attribute10format', attribute10format])

    if attribute11:
        search_filter.append(['attribute11', attribute11])

    if attribute11expr:
        search_filter.append(['attribute11expr', attribute11expr])

    if attribute11friendlyname:
        search_filter.append(['attribute11friendlyname', attribute11friendlyname])

    if attribute11format:
        search_filter.append(['attribute11format', attribute11format])

    if attribute12:
        search_filter.append(['attribute12', attribute12])

    if attribute12expr:
        search_filter.append(['attribute12expr', attribute12expr])

    if attribute12friendlyname:
        search_filter.append(['attribute12friendlyname', attribute12friendlyname])

    if attribute12format:
        search_filter.append(['attribute12format', attribute12format])

    if attribute13:
        search_filter.append(['attribute13', attribute13])

    if attribute13expr:
        search_filter.append(['attribute13expr', attribute13expr])

    if attribute13friendlyname:
        search_filter.append(['attribute13friendlyname', attribute13friendlyname])

    if attribute13format:
        search_filter.append(['attribute13format', attribute13format])

    if attribute14:
        search_filter.append(['attribute14', attribute14])

    if attribute14expr:
        search_filter.append(['attribute14expr', attribute14expr])

    if attribute14friendlyname:
        search_filter.append(['attribute14friendlyname', attribute14friendlyname])

    if attribute14format:
        search_filter.append(['attribute14format', attribute14format])

    if attribute15:
        search_filter.append(['attribute15', attribute15])

    if attribute15expr:
        search_filter.append(['attribute15expr', attribute15expr])

    if attribute15friendlyname:
        search_filter.append(['attribute15friendlyname', attribute15friendlyname])

    if attribute15format:
        search_filter.append(['attribute15format', attribute15format])

    if attribute16:
        search_filter.append(['attribute16', attribute16])

    if attribute16expr:
        search_filter.append(['attribute16expr', attribute16expr])

    if attribute16friendlyname:
        search_filter.append(['attribute16friendlyname', attribute16friendlyname])

    if attribute16format:
        search_filter.append(['attribute16format', attribute16format])

    if encryptassertion:
        search_filter.append(['encryptassertion', encryptassertion])

    if encryptionalgorithm:
        search_filter.append(['encryptionalgorithm', encryptionalgorithm])

    if samlbinding:
        search_filter.append(['samlbinding', samlbinding])

    if skewtime:
        search_filter.append(['skewtime', skewtime])

    if serviceproviderid:
        search_filter.append(['serviceproviderid', serviceproviderid])

    if signassertion:
        search_filter.append(['signassertion', signassertion])

    if keytransportalg:
        search_filter.append(['keytransportalg', keytransportalg])

    if splogouturl:
        search_filter.append(['splogouturl', splogouturl])

    if logoutbinding:
        search_filter.append(['logoutbinding', logoutbinding])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlidpprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlidpprofile')

    return response


def get_authenticationsamlpolicy(name=None, rule=None, reqaction=None):
    '''
    Show the running configuration for the authenticationsamlpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlpolicy')

    return response


def get_authenticationsamlpolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationsamlpolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlpolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlpolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlpolicy_authenticationvserver_binding')

    return response


def get_authenticationsamlpolicy_binding():
    '''
    Show the running configuration for the authenticationsamlpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlpolicy_binding'), 'authenticationsamlpolicy_binding')

    return response


def get_authenticationsamlpolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationsamlpolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlpolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlpolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlpolicy_vpnglobal_binding')

    return response


def get_authenticationsamlpolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationsamlpolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationsamlpolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationsamlpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationsamlpolicy_vpnvserver_binding')

    return response


def get_authenticationstorefrontauthaction(name=None, serverurl=None, domain=None, defaultauthenticationgroup=None):
    '''
    Show the running configuration for the authenticationstorefrontauthaction config key.

    name(str): Filters results that only match the name field.

    serverurl(str): Filters results that only match the serverurl field.

    domain(str): Filters results that only match the domain field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationstorefrontauthaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if serverurl:
        search_filter.append(['serverurl', serverurl])

    if domain:
        search_filter.append(['domain', domain])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationstorefrontauthaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationstorefrontauthaction')

    return response


def get_authenticationtacacsaction(name=None, serverip=None, serverport=None, authtimeout=None, tacacssecret=None,
                                   authorization=None, accounting=None, auditfailedcmds=None, groupattrname=None,
                                   defaultauthenticationgroup=None, attribute1=None, attribute2=None, attribute3=None,
                                   attribute4=None, attribute5=None, attribute6=None, attribute7=None, attribute8=None,
                                   attribute9=None, attribute10=None, attribute11=None, attribute12=None,
                                   attribute13=None, attribute14=None, attribute15=None, attribute16=None):
    '''
    Show the running configuration for the authenticationtacacsaction config key.

    name(str): Filters results that only match the name field.

    serverip(str): Filters results that only match the serverip field.

    serverport(int): Filters results that only match the serverport field.

    authtimeout(int): Filters results that only match the authtimeout field.

    tacacssecret(str): Filters results that only match the tacacssecret field.

    authorization(str): Filters results that only match the authorization field.

    accounting(str): Filters results that only match the accounting field.

    auditfailedcmds(str): Filters results that only match the auditfailedcmds field.

    groupattrname(str): Filters results that only match the groupattrname field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    attribute1(str): Filters results that only match the attribute1 field.

    attribute2(str): Filters results that only match the attribute2 field.

    attribute3(str): Filters results that only match the attribute3 field.

    attribute4(str): Filters results that only match the attribute4 field.

    attribute5(str): Filters results that only match the attribute5 field.

    attribute6(str): Filters results that only match the attribute6 field.

    attribute7(str): Filters results that only match the attribute7 field.

    attribute8(str): Filters results that only match the attribute8 field.

    attribute9(str): Filters results that only match the attribute9 field.

    attribute10(str): Filters results that only match the attribute10 field.

    attribute11(str): Filters results that only match the attribute11 field.

    attribute12(str): Filters results that only match the attribute12 field.

    attribute13(str): Filters results that only match the attribute13 field.

    attribute14(str): Filters results that only match the attribute14 field.

    attribute15(str): Filters results that only match the attribute15 field.

    attribute16(str): Filters results that only match the attribute16 field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationtacacsaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if serverip:
        search_filter.append(['serverip', serverip])

    if serverport:
        search_filter.append(['serverport', serverport])

    if authtimeout:
        search_filter.append(['authtimeout', authtimeout])

    if tacacssecret:
        search_filter.append(['tacacssecret', tacacssecret])

    if authorization:
        search_filter.append(['authorization', authorization])

    if accounting:
        search_filter.append(['accounting', accounting])

    if auditfailedcmds:
        search_filter.append(['auditfailedcmds', auditfailedcmds])

    if groupattrname:
        search_filter.append(['groupattrname', groupattrname])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    if attribute1:
        search_filter.append(['attribute1', attribute1])

    if attribute2:
        search_filter.append(['attribute2', attribute2])

    if attribute3:
        search_filter.append(['attribute3', attribute3])

    if attribute4:
        search_filter.append(['attribute4', attribute4])

    if attribute5:
        search_filter.append(['attribute5', attribute5])

    if attribute6:
        search_filter.append(['attribute6', attribute6])

    if attribute7:
        search_filter.append(['attribute7', attribute7])

    if attribute8:
        search_filter.append(['attribute8', attribute8])

    if attribute9:
        search_filter.append(['attribute9', attribute9])

    if attribute10:
        search_filter.append(['attribute10', attribute10])

    if attribute11:
        search_filter.append(['attribute11', attribute11])

    if attribute12:
        search_filter.append(['attribute12', attribute12])

    if attribute13:
        search_filter.append(['attribute13', attribute13])

    if attribute14:
        search_filter.append(['attribute14', attribute14])

    if attribute15:
        search_filter.append(['attribute15', attribute15])

    if attribute16:
        search_filter.append(['attribute16', attribute16])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationtacacsaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationtacacsaction')

    return response


def get_authenticationtacacspolicy(name=None, rule=None, reqaction=None):
    '''
    Show the running configuration for the authenticationtacacspolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationtacacspolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationtacacspolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationtacacspolicy')

    return response


def get_authenticationtacacspolicy_authenticationvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the authenticationtacacspolicy_authenticationvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationtacacspolicy_authenticationvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationtacacspolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationtacacspolicy_authenticationvserver_binding')

    return response


def get_authenticationtacacspolicy_binding():
    '''
    Show the running configuration for the authenticationtacacspolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationtacacspolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationtacacspolicy_binding'), 'authenticationtacacspolicy_binding')

    return response


def get_authenticationtacacspolicy_systemglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the authenticationtacacspolicy_systemglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationtacacspolicy_systemglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationtacacspolicy_systemglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationtacacspolicy_systemglobal_binding')

    return response


def get_authenticationtacacspolicy_vpnglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the authenticationtacacspolicy_vpnglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationtacacspolicy_vpnglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationtacacspolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationtacacspolicy_vpnglobal_binding')

    return response


def get_authenticationtacacspolicy_vpnvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the authenticationtacacspolicy_vpnvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationtacacspolicy_vpnvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationtacacspolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationtacacspolicy_vpnvserver_binding')

    return response


def get_authenticationvserver(name=None, servicetype=None, ipv46=None, range=None, port=None, state=None,
                              authentication=None, authenticationdomain=None, comment=None, td=None, appflowlog=None,
                              maxloginattempts=None, failedlogintimeout=None, newname=None):
    '''
    Show the running configuration for the authenticationvserver config key.

    name(str): Filters results that only match the name field.

    servicetype(str): Filters results that only match the servicetype field.

    ipv46(str): Filters results that only match the ipv46 field.

    range(int): Filters results that only match the range field.

    port(int): Filters results that only match the port field.

    state(str): Filters results that only match the state field.

    authentication(str): Filters results that only match the authentication field.

    authenticationdomain(str): Filters results that only match the authenticationdomain field.

    comment(str): Filters results that only match the comment field.

    td(int): Filters results that only match the td field.

    appflowlog(str): Filters results that only match the appflowlog field.

    maxloginattempts(int): Filters results that only match the maxloginattempts field.

    failedlogintimeout(int): Filters results that only match the failedlogintimeout field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if servicetype:
        search_filter.append(['servicetype', servicetype])

    if ipv46:
        search_filter.append(['ipv46', ipv46])

    if range:
        search_filter.append(['range', range])

    if port:
        search_filter.append(['port', port])

    if state:
        search_filter.append(['state', state])

    if authentication:
        search_filter.append(['authentication', authentication])

    if authenticationdomain:
        search_filter.append(['authenticationdomain', authenticationdomain])

    if comment:
        search_filter.append(['comment', comment])

    if td:
        search_filter.append(['td', td])

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if maxloginattempts:
        search_filter.append(['maxloginattempts', maxloginattempts])

    if failedlogintimeout:
        search_filter.append(['failedlogintimeout', failedlogintimeout])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver')

    return response


def get_authenticationvserver_auditnslogpolicy_binding(priority=None, name=None, nextfactor=None,
                                                       gotopriorityexpression=None, secondary=None, policy=None,
                                                       groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_auditnslogpolicy_binding')

    return response


def get_authenticationvserver_auditsyslogpolicy_binding(priority=None, name=None, nextfactor=None,
                                                        gotopriorityexpression=None, secondary=None, policy=None,
                                                        groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_auditsyslogpolicy_binding')

    return response


def get_authenticationvserver_authenticationcertpolicy_binding(priority=None, name=None, nextfactor=None,
                                                               gotopriorityexpression=None, secondary=None, policy=None,
                                                               groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationcertpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationcertpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationcertpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationcertpolicy_binding')

    return response


def get_authenticationvserver_authenticationldappolicy_binding(priority=None, name=None, nextfactor=None,
                                                               gotopriorityexpression=None, secondary=None, policy=None,
                                                               groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationldappolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationldappolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationldappolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationldappolicy_binding')

    return response


def get_authenticationvserver_authenticationlocalpolicy_binding(priority=None, name=None, nextfactor=None,
                                                                gotopriorityexpression=None, secondary=None, policy=None,
                                                                groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationlocalpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationlocalpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationlocalpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationlocalpolicy_binding')

    return response


def get_authenticationvserver_authenticationloginschemapolicy_binding(priority=None, name=None, nextfactor=None,
                                                                      gotopriorityexpression=None, secondary=None,
                                                                      policy=None, groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationloginschemapolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationloginschemapolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationloginschemapolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationloginschemapolicy_binding')

    return response


def get_authenticationvserver_authenticationnegotiatepolicy_binding(priority=None, name=None, nextfactor=None,
                                                                    gotopriorityexpression=None, secondary=None,
                                                                    policy=None, groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationnegotiatepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationnegotiatepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationnegotiatepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationnegotiatepolicy_binding')

    return response


def get_authenticationvserver_authenticationpolicy_binding(priority=None, name=None, nextfactor=None,
                                                           gotopriorityexpression=None, secondary=None, policy=None,
                                                           groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationpolicy_binding')

    return response


def get_authenticationvserver_authenticationradiuspolicy_binding(priority=None, name=None, nextfactor=None,
                                                                 gotopriorityexpression=None, secondary=None,
                                                                 policy=None, groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationradiuspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationradiuspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationradiuspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationradiuspolicy_binding')

    return response


def get_authenticationvserver_authenticationsamlidppolicy_binding(priority=None, name=None, nextfactor=None,
                                                                  gotopriorityexpression=None, secondary=None,
                                                                  policy=None, groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationsamlidppolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationsamlidppolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationsamlidppolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationsamlidppolicy_binding')

    return response


def get_authenticationvserver_authenticationsamlpolicy_binding(priority=None, name=None, nextfactor=None,
                                                               gotopriorityexpression=None, secondary=None, policy=None,
                                                               groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationsamlpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationsamlpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationsamlpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationsamlpolicy_binding')

    return response


def get_authenticationvserver_authenticationtacacspolicy_binding(priority=None, name=None, nextfactor=None,
                                                                 gotopriorityexpression=None, secondary=None,
                                                                 policy=None, groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationtacacspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationtacacspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationtacacspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationtacacspolicy_binding')

    return response


def get_authenticationvserver_authenticationwebauthpolicy_binding(priority=None, name=None, nextfactor=None,
                                                                  gotopriorityexpression=None, secondary=None,
                                                                  policy=None, groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_authenticationwebauthpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_authenticationwebauthpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_authenticationwebauthpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_authenticationwebauthpolicy_binding')

    return response


def get_authenticationvserver_binding():
    '''
    Show the running configuration for the authenticationvserver_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_binding'), 'authenticationvserver_binding')

    return response


def get_authenticationvserver_cspolicy_binding(priority=None, name=None, nextfactor=None, gotopriorityexpression=None,
                                               secondary=None, policy=None, groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_cspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_cspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_cspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_cspolicy_binding')

    return response


def get_authenticationvserver_tmsessionpolicy_binding(priority=None, name=None, nextfactor=None,
                                                      gotopriorityexpression=None, secondary=None, policy=None,
                                                      groupextraction=None):
    '''
    Show the running configuration for the authenticationvserver_tmsessionpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    name(str): Filters results that only match the name field.

    nextfactor(str): Filters results that only match the nextfactor field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    secondary(bool): Filters results that only match the secondary field.

    policy(str): Filters results that only match the policy field.

    groupextraction(bool): Filters results that only match the groupextraction field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_tmsessionpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if name:
        search_filter.append(['name', name])

    if nextfactor:
        search_filter.append(['nextfactor', nextfactor])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if secondary:
        search_filter.append(['secondary', secondary])

    if policy:
        search_filter.append(['policy', policy])

    if groupextraction:
        search_filter.append(['groupextraction', groupextraction])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_tmsessionpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_tmsessionpolicy_binding')

    return response


def get_authenticationvserver_vpnportaltheme_binding(name=None, portaltheme=None):
    '''
    Show the running configuration for the authenticationvserver_vpnportaltheme_binding config key.

    name(str): Filters results that only match the name field.

    portaltheme(str): Filters results that only match the portaltheme field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationvserver_vpnportaltheme_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if portaltheme:
        search_filter.append(['portaltheme', portaltheme])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationvserver_vpnportaltheme_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationvserver_vpnportaltheme_binding')

    return response


def get_authenticationwebauthaction(name=None, serverip=None, serverport=None, fullreqexpr=None, scheme=None,
                                    successrule=None, defaultauthenticationgroup=None, attribute1=None, attribute2=None,
                                    attribute3=None, attribute4=None, attribute5=None, attribute6=None, attribute7=None,
                                    attribute8=None, attribute9=None, attribute10=None, attribute11=None,
                                    attribute12=None, attribute13=None, attribute14=None, attribute15=None,
                                    attribute16=None):
    '''
    Show the running configuration for the authenticationwebauthaction config key.

    name(str): Filters results that only match the name field.

    serverip(str): Filters results that only match the serverip field.

    serverport(int): Filters results that only match the serverport field.

    fullreqexpr(str): Filters results that only match the fullreqexpr field.

    scheme(str): Filters results that only match the scheme field.

    successrule(str): Filters results that only match the successrule field.

    defaultauthenticationgroup(str): Filters results that only match the defaultauthenticationgroup field.

    attribute1(str): Filters results that only match the attribute1 field.

    attribute2(str): Filters results that only match the attribute2 field.

    attribute3(str): Filters results that only match the attribute3 field.

    attribute4(str): Filters results that only match the attribute4 field.

    attribute5(str): Filters results that only match the attribute5 field.

    attribute6(str): Filters results that only match the attribute6 field.

    attribute7(str): Filters results that only match the attribute7 field.

    attribute8(str): Filters results that only match the attribute8 field.

    attribute9(str): Filters results that only match the attribute9 field.

    attribute10(str): Filters results that only match the attribute10 field.

    attribute11(str): Filters results that only match the attribute11 field.

    attribute12(str): Filters results that only match the attribute12 field.

    attribute13(str): Filters results that only match the attribute13 field.

    attribute14(str): Filters results that only match the attribute14 field.

    attribute15(str): Filters results that only match the attribute15 field.

    attribute16(str): Filters results that only match the attribute16 field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationwebauthaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if serverip:
        search_filter.append(['serverip', serverip])

    if serverport:
        search_filter.append(['serverport', serverport])

    if fullreqexpr:
        search_filter.append(['fullreqexpr', fullreqexpr])

    if scheme:
        search_filter.append(['scheme', scheme])

    if successrule:
        search_filter.append(['successrule', successrule])

    if defaultauthenticationgroup:
        search_filter.append(['defaultauthenticationgroup', defaultauthenticationgroup])

    if attribute1:
        search_filter.append(['attribute1', attribute1])

    if attribute2:
        search_filter.append(['attribute2', attribute2])

    if attribute3:
        search_filter.append(['attribute3', attribute3])

    if attribute4:
        search_filter.append(['attribute4', attribute4])

    if attribute5:
        search_filter.append(['attribute5', attribute5])

    if attribute6:
        search_filter.append(['attribute6', attribute6])

    if attribute7:
        search_filter.append(['attribute7', attribute7])

    if attribute8:
        search_filter.append(['attribute8', attribute8])

    if attribute9:
        search_filter.append(['attribute9', attribute9])

    if attribute10:
        search_filter.append(['attribute10', attribute10])

    if attribute11:
        search_filter.append(['attribute11', attribute11])

    if attribute12:
        search_filter.append(['attribute12', attribute12])

    if attribute13:
        search_filter.append(['attribute13', attribute13])

    if attribute14:
        search_filter.append(['attribute14', attribute14])

    if attribute15:
        search_filter.append(['attribute15', attribute15])

    if attribute16:
        search_filter.append(['attribute16', attribute16])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationwebauthaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationwebauthaction')

    return response


def get_authenticationwebauthpolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the authenticationwebauthpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationwebauthpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationwebauthpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationwebauthpolicy')

    return response


def get_authenticationwebauthpolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationwebauthpolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationwebauthpolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationwebauthpolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationwebauthpolicy_authenticationvserver_binding')

    return response


def get_authenticationwebauthpolicy_binding():
    '''
    Show the running configuration for the authenticationwebauthpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationwebauthpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationwebauthpolicy_binding'), 'authenticationwebauthpolicy_binding')

    return response


def get_authenticationwebauthpolicy_systemglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationwebauthpolicy_systemglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationwebauthpolicy_systemglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationwebauthpolicy_systemglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationwebauthpolicy_systemglobal_binding')

    return response


def get_authenticationwebauthpolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationwebauthpolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationwebauthpolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationwebauthpolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationwebauthpolicy_vpnglobal_binding')

    return response


def get_authenticationwebauthpolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authenticationwebauthpolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.get_authenticationwebauthpolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authenticationwebauthpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authenticationwebauthpolicy_vpnvserver_binding')

    return response


def unset_authenticationauthnprofile(name=None, authnvsname=None, authenticationhost=None, authenticationdomain=None,
                                     authenticationlevel=None, save=False):
    '''
    Unsets values from the authenticationauthnprofile configuration key.

    name(bool): Unsets the name value.

    authnvsname(bool): Unsets the authnvsname value.

    authenticationhost(bool): Unsets the authenticationhost value.

    authenticationdomain(bool): Unsets the authenticationdomain value.

    authenticationlevel(bool): Unsets the authenticationlevel value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationauthnprofile <args>

    '''

    result = {}

    payload = {'authenticationauthnprofile': {}}

    if name:
        payload['authenticationauthnprofile']['name'] = True

    if authnvsname:
        payload['authenticationauthnprofile']['authnvsname'] = True

    if authenticationhost:
        payload['authenticationauthnprofile']['authenticationhost'] = True

    if authenticationdomain:
        payload['authenticationauthnprofile']['authenticationdomain'] = True

    if authenticationlevel:
        payload['authenticationauthnprofile']['authenticationlevel'] = True

    execution = __proxy__['citrixns.post']('config/authenticationauthnprofile?action=unset', payload)

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


def unset_authenticationcertaction(name=None, twofactor=None, usernamefield=None, groupnamefield=None,
                                   defaultauthenticationgroup=None, save=False):
    '''
    Unsets values from the authenticationcertaction configuration key.

    name(bool): Unsets the name value.

    twofactor(bool): Unsets the twofactor value.

    usernamefield(bool): Unsets the usernamefield value.

    groupnamefield(bool): Unsets the groupnamefield value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationcertaction <args>

    '''

    result = {}

    payload = {'authenticationcertaction': {}}

    if name:
        payload['authenticationcertaction']['name'] = True

    if twofactor:
        payload['authenticationcertaction']['twofactor'] = True

    if usernamefield:
        payload['authenticationcertaction']['usernamefield'] = True

    if groupnamefield:
        payload['authenticationcertaction']['groupnamefield'] = True

    if defaultauthenticationgroup:
        payload['authenticationcertaction']['defaultauthenticationgroup'] = True

    execution = __proxy__['citrixns.post']('config/authenticationcertaction?action=unset', payload)

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


def unset_authenticationcertpolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Unsets values from the authenticationcertpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    reqaction(bool): Unsets the reqaction value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationcertpolicy <args>

    '''

    result = {}

    payload = {'authenticationcertpolicy': {}}

    if name:
        payload['authenticationcertpolicy']['name'] = True

    if rule:
        payload['authenticationcertpolicy']['rule'] = True

    if reqaction:
        payload['authenticationcertpolicy']['reqaction'] = True

    execution = __proxy__['citrixns.post']('config/authenticationcertpolicy?action=unset', payload)

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


def unset_authenticationdfaaction(name=None, clientid=None, serverurl=None, passphrase=None,
                                  defaultauthenticationgroup=None, save=False):
    '''
    Unsets values from the authenticationdfaaction configuration key.

    name(bool): Unsets the name value.

    clientid(bool): Unsets the clientid value.

    serverurl(bool): Unsets the serverurl value.

    passphrase(bool): Unsets the passphrase value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationdfaaction <args>

    '''

    result = {}

    payload = {'authenticationdfaaction': {}}

    if name:
        payload['authenticationdfaaction']['name'] = True

    if clientid:
        payload['authenticationdfaaction']['clientid'] = True

    if serverurl:
        payload['authenticationdfaaction']['serverurl'] = True

    if passphrase:
        payload['authenticationdfaaction']['passphrase'] = True

    if defaultauthenticationgroup:
        payload['authenticationdfaaction']['defaultauthenticationgroup'] = True

    execution = __proxy__['citrixns.post']('config/authenticationdfaaction?action=unset', payload)

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


def unset_authenticationepaaction(name=None, csecexpr=None, killprocess=None, deletefiles=None, defaultepagroup=None,
                                  quarantinegroup=None, save=False):
    '''
    Unsets values from the authenticationepaaction configuration key.

    name(bool): Unsets the name value.

    csecexpr(bool): Unsets the csecexpr value.

    killprocess(bool): Unsets the killprocess value.

    deletefiles(bool): Unsets the deletefiles value.

    defaultepagroup(bool): Unsets the defaultepagroup value.

    quarantinegroup(bool): Unsets the quarantinegroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationepaaction <args>

    '''

    result = {}

    payload = {'authenticationepaaction': {}}

    if name:
        payload['authenticationepaaction']['name'] = True

    if csecexpr:
        payload['authenticationepaaction']['csecexpr'] = True

    if killprocess:
        payload['authenticationepaaction']['killprocess'] = True

    if deletefiles:
        payload['authenticationepaaction']['deletefiles'] = True

    if defaultepagroup:
        payload['authenticationepaaction']['defaultepagroup'] = True

    if quarantinegroup:
        payload['authenticationepaaction']['quarantinegroup'] = True

    execution = __proxy__['citrixns.post']('config/authenticationepaaction?action=unset', payload)

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


def unset_authenticationldapaction(name=None, serverip=None, servername=None, serverport=None, authtimeout=None,
                                   ldapbase=None, ldapbinddn=None, ldapbinddnpassword=None, ldaploginname=None,
                                   searchfilter=None, groupattrname=None, subattributename=None, sectype=None,
                                   svrtype=None, ssonameattribute=None, authentication=None, requireuser=None,
                                   passwdchange=None, nestedgroupextraction=None, maxnestinglevel=None,
                                   followreferrals=None, maxldapreferrals=None, referraldnslookup=None,
                                   mssrvrecordlocation=None, validateservercert=None, ldaphostname=None,
                                   groupnameidentifier=None, groupsearchattribute=None, groupsearchsubattribute=None,
                                   groupsearchfilter=None, defaultauthenticationgroup=None, attribute1=None,
                                   attribute2=None, attribute3=None, attribute4=None, attribute5=None, attribute6=None,
                                   attribute7=None, attribute8=None, attribute9=None, attribute10=None, attribute11=None,
                                   attribute12=None, attribute13=None, attribute14=None, attribute15=None,
                                   attribute16=None, save=False):
    '''
    Unsets values from the authenticationldapaction configuration key.

    name(bool): Unsets the name value.

    serverip(bool): Unsets the serverip value.

    servername(bool): Unsets the servername value.

    serverport(bool): Unsets the serverport value.

    authtimeout(bool): Unsets the authtimeout value.

    ldapbase(bool): Unsets the ldapbase value.

    ldapbinddn(bool): Unsets the ldapbinddn value.

    ldapbinddnpassword(bool): Unsets the ldapbinddnpassword value.

    ldaploginname(bool): Unsets the ldaploginname value.

    searchfilter(bool): Unsets the searchfilter value.

    groupattrname(bool): Unsets the groupattrname value.

    subattributename(bool): Unsets the subattributename value.

    sectype(bool): Unsets the sectype value.

    svrtype(bool): Unsets the svrtype value.

    ssonameattribute(bool): Unsets the ssonameattribute value.

    authentication(bool): Unsets the authentication value.

    requireuser(bool): Unsets the requireuser value.

    passwdchange(bool): Unsets the passwdchange value.

    nestedgroupextraction(bool): Unsets the nestedgroupextraction value.

    maxnestinglevel(bool): Unsets the maxnestinglevel value.

    followreferrals(bool): Unsets the followreferrals value.

    maxldapreferrals(bool): Unsets the maxldapreferrals value.

    referraldnslookup(bool): Unsets the referraldnslookup value.

    mssrvrecordlocation(bool): Unsets the mssrvrecordlocation value.

    validateservercert(bool): Unsets the validateservercert value.

    ldaphostname(bool): Unsets the ldaphostname value.

    groupnameidentifier(bool): Unsets the groupnameidentifier value.

    groupsearchattribute(bool): Unsets the groupsearchattribute value.

    groupsearchsubattribute(bool): Unsets the groupsearchsubattribute value.

    groupsearchfilter(bool): Unsets the groupsearchfilter value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    attribute1(bool): Unsets the attribute1 value.

    attribute2(bool): Unsets the attribute2 value.

    attribute3(bool): Unsets the attribute3 value.

    attribute4(bool): Unsets the attribute4 value.

    attribute5(bool): Unsets the attribute5 value.

    attribute6(bool): Unsets the attribute6 value.

    attribute7(bool): Unsets the attribute7 value.

    attribute8(bool): Unsets the attribute8 value.

    attribute9(bool): Unsets the attribute9 value.

    attribute10(bool): Unsets the attribute10 value.

    attribute11(bool): Unsets the attribute11 value.

    attribute12(bool): Unsets the attribute12 value.

    attribute13(bool): Unsets the attribute13 value.

    attribute14(bool): Unsets the attribute14 value.

    attribute15(bool): Unsets the attribute15 value.

    attribute16(bool): Unsets the attribute16 value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationldapaction <args>

    '''

    result = {}

    payload = {'authenticationldapaction': {}}

    if name:
        payload['authenticationldapaction']['name'] = True

    if serverip:
        payload['authenticationldapaction']['serverip'] = True

    if servername:
        payload['authenticationldapaction']['servername'] = True

    if serverport:
        payload['authenticationldapaction']['serverport'] = True

    if authtimeout:
        payload['authenticationldapaction']['authtimeout'] = True

    if ldapbase:
        payload['authenticationldapaction']['ldapbase'] = True

    if ldapbinddn:
        payload['authenticationldapaction']['ldapbinddn'] = True

    if ldapbinddnpassword:
        payload['authenticationldapaction']['ldapbinddnpassword'] = True

    if ldaploginname:
        payload['authenticationldapaction']['ldaploginname'] = True

    if searchfilter:
        payload['authenticationldapaction']['searchfilter'] = True

    if groupattrname:
        payload['authenticationldapaction']['groupattrname'] = True

    if subattributename:
        payload['authenticationldapaction']['subattributename'] = True

    if sectype:
        payload['authenticationldapaction']['sectype'] = True

    if svrtype:
        payload['authenticationldapaction']['svrtype'] = True

    if ssonameattribute:
        payload['authenticationldapaction']['ssonameattribute'] = True

    if authentication:
        payload['authenticationldapaction']['authentication'] = True

    if requireuser:
        payload['authenticationldapaction']['requireuser'] = True

    if passwdchange:
        payload['authenticationldapaction']['passwdchange'] = True

    if nestedgroupextraction:
        payload['authenticationldapaction']['nestedgroupextraction'] = True

    if maxnestinglevel:
        payload['authenticationldapaction']['maxnestinglevel'] = True

    if followreferrals:
        payload['authenticationldapaction']['followreferrals'] = True

    if maxldapreferrals:
        payload['authenticationldapaction']['maxldapreferrals'] = True

    if referraldnslookup:
        payload['authenticationldapaction']['referraldnslookup'] = True

    if mssrvrecordlocation:
        payload['authenticationldapaction']['mssrvrecordlocation'] = True

    if validateservercert:
        payload['authenticationldapaction']['validateservercert'] = True

    if ldaphostname:
        payload['authenticationldapaction']['ldaphostname'] = True

    if groupnameidentifier:
        payload['authenticationldapaction']['groupnameidentifier'] = True

    if groupsearchattribute:
        payload['authenticationldapaction']['groupsearchattribute'] = True

    if groupsearchsubattribute:
        payload['authenticationldapaction']['groupsearchsubattribute'] = True

    if groupsearchfilter:
        payload['authenticationldapaction']['groupsearchfilter'] = True

    if defaultauthenticationgroup:
        payload['authenticationldapaction']['defaultauthenticationgroup'] = True

    if attribute1:
        payload['authenticationldapaction']['attribute1'] = True

    if attribute2:
        payload['authenticationldapaction']['attribute2'] = True

    if attribute3:
        payload['authenticationldapaction']['attribute3'] = True

    if attribute4:
        payload['authenticationldapaction']['attribute4'] = True

    if attribute5:
        payload['authenticationldapaction']['attribute5'] = True

    if attribute6:
        payload['authenticationldapaction']['attribute6'] = True

    if attribute7:
        payload['authenticationldapaction']['attribute7'] = True

    if attribute8:
        payload['authenticationldapaction']['attribute8'] = True

    if attribute9:
        payload['authenticationldapaction']['attribute9'] = True

    if attribute10:
        payload['authenticationldapaction']['attribute10'] = True

    if attribute11:
        payload['authenticationldapaction']['attribute11'] = True

    if attribute12:
        payload['authenticationldapaction']['attribute12'] = True

    if attribute13:
        payload['authenticationldapaction']['attribute13'] = True

    if attribute14:
        payload['authenticationldapaction']['attribute14'] = True

    if attribute15:
        payload['authenticationldapaction']['attribute15'] = True

    if attribute16:
        payload['authenticationldapaction']['attribute16'] = True

    execution = __proxy__['citrixns.post']('config/authenticationldapaction?action=unset', payload)

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


def unset_authenticationldappolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Unsets values from the authenticationldappolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    reqaction(bool): Unsets the reqaction value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationldappolicy <args>

    '''

    result = {}

    payload = {'authenticationldappolicy': {}}

    if name:
        payload['authenticationldappolicy']['name'] = True

    if rule:
        payload['authenticationldappolicy']['rule'] = True

    if reqaction:
        payload['authenticationldappolicy']['reqaction'] = True

    execution = __proxy__['citrixns.post']('config/authenticationldappolicy?action=unset', payload)

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


def unset_authenticationloginschema(name=None, authenticationschema=None, userexpression=None, passwdexpression=None,
                                    usercredentialindex=None, passwordcredentialindex=None, authenticationstrength=None,
                                    ssocredentials=None, save=False):
    '''
    Unsets values from the authenticationloginschema configuration key.

    name(bool): Unsets the name value.

    authenticationschema(bool): Unsets the authenticationschema value.

    userexpression(bool): Unsets the userexpression value.

    passwdexpression(bool): Unsets the passwdexpression value.

    usercredentialindex(bool): Unsets the usercredentialindex value.

    passwordcredentialindex(bool): Unsets the passwordcredentialindex value.

    authenticationstrength(bool): Unsets the authenticationstrength value.

    ssocredentials(bool): Unsets the ssocredentials value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationloginschema <args>

    '''

    result = {}

    payload = {'authenticationloginschema': {}}

    if name:
        payload['authenticationloginschema']['name'] = True

    if authenticationschema:
        payload['authenticationloginschema']['authenticationschema'] = True

    if userexpression:
        payload['authenticationloginschema']['userexpression'] = True

    if passwdexpression:
        payload['authenticationloginschema']['passwdexpression'] = True

    if usercredentialindex:
        payload['authenticationloginschema']['usercredentialindex'] = True

    if passwordcredentialindex:
        payload['authenticationloginschema']['passwordcredentialindex'] = True

    if authenticationstrength:
        payload['authenticationloginschema']['authenticationstrength'] = True

    if ssocredentials:
        payload['authenticationloginschema']['ssocredentials'] = True

    execution = __proxy__['citrixns.post']('config/authenticationloginschema?action=unset', payload)

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


def unset_authenticationloginschemapolicy(name=None, rule=None, action=None, undefaction=None, comment=None,
                                          logaction=None, newname=None, save=False):
    '''
    Unsets values from the authenticationloginschemapolicy configuration key.

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

    salt '*' authentication.unset_authenticationloginschemapolicy <args>

    '''

    result = {}

    payload = {'authenticationloginschemapolicy': {}}

    if name:
        payload['authenticationloginschemapolicy']['name'] = True

    if rule:
        payload['authenticationloginschemapolicy']['rule'] = True

    if action:
        payload['authenticationloginschemapolicy']['action'] = True

    if undefaction:
        payload['authenticationloginschemapolicy']['undefaction'] = True

    if comment:
        payload['authenticationloginschemapolicy']['comment'] = True

    if logaction:
        payload['authenticationloginschemapolicy']['logaction'] = True

    if newname:
        payload['authenticationloginschemapolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/authenticationloginschemapolicy?action=unset', payload)

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


def unset_authenticationnegotiateaction(name=None, domain=None, domainuser=None, domainuserpasswd=None, ou=None,
                                        defaultauthenticationgroup=None, keytab=None, ntlmpath=None, save=False):
    '''
    Unsets values from the authenticationnegotiateaction configuration key.

    name(bool): Unsets the name value.

    domain(bool): Unsets the domain value.

    domainuser(bool): Unsets the domainuser value.

    domainuserpasswd(bool): Unsets the domainuserpasswd value.

    ou(bool): Unsets the ou value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    keytab(bool): Unsets the keytab value.

    ntlmpath(bool): Unsets the ntlmpath value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationnegotiateaction <args>

    '''

    result = {}

    payload = {'authenticationnegotiateaction': {}}

    if name:
        payload['authenticationnegotiateaction']['name'] = True

    if domain:
        payload['authenticationnegotiateaction']['domain'] = True

    if domainuser:
        payload['authenticationnegotiateaction']['domainuser'] = True

    if domainuserpasswd:
        payload['authenticationnegotiateaction']['domainuserpasswd'] = True

    if ou:
        payload['authenticationnegotiateaction']['ou'] = True

    if defaultauthenticationgroup:
        payload['authenticationnegotiateaction']['defaultauthenticationgroup'] = True

    if keytab:
        payload['authenticationnegotiateaction']['keytab'] = True

    if ntlmpath:
        payload['authenticationnegotiateaction']['ntlmpath'] = True

    execution = __proxy__['citrixns.post']('config/authenticationnegotiateaction?action=unset', payload)

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


def unset_authenticationoauthaction(name=None, oauthtype=None, authorizationendpoint=None, tokenendpoint=None,
                                    idtokendecryptendpoint=None, clientid=None, clientsecret=None,
                                    defaultauthenticationgroup=None, attribute1=None, attribute2=None, attribute3=None,
                                    attribute4=None, attribute5=None, attribute6=None, attribute7=None, attribute8=None,
                                    attribute9=None, attribute10=None, attribute11=None, attribute12=None,
                                    attribute13=None, attribute14=None, attribute15=None, attribute16=None,
                                    tenantid=None, graphendpoint=None, refreshinterval=None, certendpoint=None,
                                    audience=None, usernamefield=None, skewtime=None, issuer=None, save=False):
    '''
    Unsets values from the authenticationoauthaction configuration key.

    name(bool): Unsets the name value.

    oauthtype(bool): Unsets the oauthtype value.

    authorizationendpoint(bool): Unsets the authorizationendpoint value.

    tokenendpoint(bool): Unsets the tokenendpoint value.

    idtokendecryptendpoint(bool): Unsets the idtokendecryptendpoint value.

    clientid(bool): Unsets the clientid value.

    clientsecret(bool): Unsets the clientsecret value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    attribute1(bool): Unsets the attribute1 value.

    attribute2(bool): Unsets the attribute2 value.

    attribute3(bool): Unsets the attribute3 value.

    attribute4(bool): Unsets the attribute4 value.

    attribute5(bool): Unsets the attribute5 value.

    attribute6(bool): Unsets the attribute6 value.

    attribute7(bool): Unsets the attribute7 value.

    attribute8(bool): Unsets the attribute8 value.

    attribute9(bool): Unsets the attribute9 value.

    attribute10(bool): Unsets the attribute10 value.

    attribute11(bool): Unsets the attribute11 value.

    attribute12(bool): Unsets the attribute12 value.

    attribute13(bool): Unsets the attribute13 value.

    attribute14(bool): Unsets the attribute14 value.

    attribute15(bool): Unsets the attribute15 value.

    attribute16(bool): Unsets the attribute16 value.

    tenantid(bool): Unsets the tenantid value.

    graphendpoint(bool): Unsets the graphendpoint value.

    refreshinterval(bool): Unsets the refreshinterval value.

    certendpoint(bool): Unsets the certendpoint value.

    audience(bool): Unsets the audience value.

    usernamefield(bool): Unsets the usernamefield value.

    skewtime(bool): Unsets the skewtime value.

    issuer(bool): Unsets the issuer value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationoauthaction <args>

    '''

    result = {}

    payload = {'authenticationoauthaction': {}}

    if name:
        payload['authenticationoauthaction']['name'] = True

    if oauthtype:
        payload['authenticationoauthaction']['oauthtype'] = True

    if authorizationendpoint:
        payload['authenticationoauthaction']['authorizationendpoint'] = True

    if tokenendpoint:
        payload['authenticationoauthaction']['tokenendpoint'] = True

    if idtokendecryptendpoint:
        payload['authenticationoauthaction']['idtokendecryptendpoint'] = True

    if clientid:
        payload['authenticationoauthaction']['clientid'] = True

    if clientsecret:
        payload['authenticationoauthaction']['clientsecret'] = True

    if defaultauthenticationgroup:
        payload['authenticationoauthaction']['defaultauthenticationgroup'] = True

    if attribute1:
        payload['authenticationoauthaction']['attribute1'] = True

    if attribute2:
        payload['authenticationoauthaction']['attribute2'] = True

    if attribute3:
        payload['authenticationoauthaction']['attribute3'] = True

    if attribute4:
        payload['authenticationoauthaction']['attribute4'] = True

    if attribute5:
        payload['authenticationoauthaction']['attribute5'] = True

    if attribute6:
        payload['authenticationoauthaction']['attribute6'] = True

    if attribute7:
        payload['authenticationoauthaction']['attribute7'] = True

    if attribute8:
        payload['authenticationoauthaction']['attribute8'] = True

    if attribute9:
        payload['authenticationoauthaction']['attribute9'] = True

    if attribute10:
        payload['authenticationoauthaction']['attribute10'] = True

    if attribute11:
        payload['authenticationoauthaction']['attribute11'] = True

    if attribute12:
        payload['authenticationoauthaction']['attribute12'] = True

    if attribute13:
        payload['authenticationoauthaction']['attribute13'] = True

    if attribute14:
        payload['authenticationoauthaction']['attribute14'] = True

    if attribute15:
        payload['authenticationoauthaction']['attribute15'] = True

    if attribute16:
        payload['authenticationoauthaction']['attribute16'] = True

    if tenantid:
        payload['authenticationoauthaction']['tenantid'] = True

    if graphendpoint:
        payload['authenticationoauthaction']['graphendpoint'] = True

    if refreshinterval:
        payload['authenticationoauthaction']['refreshinterval'] = True

    if certendpoint:
        payload['authenticationoauthaction']['certendpoint'] = True

    if audience:
        payload['authenticationoauthaction']['audience'] = True

    if usernamefield:
        payload['authenticationoauthaction']['usernamefield'] = True

    if skewtime:
        payload['authenticationoauthaction']['skewtime'] = True

    if issuer:
        payload['authenticationoauthaction']['issuer'] = True

    execution = __proxy__['citrixns.post']('config/authenticationoauthaction?action=unset', payload)

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


def unset_authenticationpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                               newname=None, save=False):
    '''
    Unsets values from the authenticationpolicy configuration key.

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

    salt '*' authentication.unset_authenticationpolicy <args>

    '''

    result = {}

    payload = {'authenticationpolicy': {}}

    if name:
        payload['authenticationpolicy']['name'] = True

    if rule:
        payload['authenticationpolicy']['rule'] = True

    if action:
        payload['authenticationpolicy']['action'] = True

    if undefaction:
        payload['authenticationpolicy']['undefaction'] = True

    if comment:
        payload['authenticationpolicy']['comment'] = True

    if logaction:
        payload['authenticationpolicy']['logaction'] = True

    if newname:
        payload['authenticationpolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/authenticationpolicy?action=unset', payload)

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


def unset_authenticationradiusaction(name=None, serverip=None, servername=None, serverport=None, authtimeout=None,
                                     radkey=None, radnasip=None, radnasid=None, radvendorid=None, radattributetype=None,
                                     radgroupsprefix=None, radgroupseparator=None, passencoding=None, ipvendorid=None,
                                     ipattributetype=None, accounting=None, pwdvendorid=None, pwdattributetype=None,
                                     defaultauthenticationgroup=None, callingstationid=None, authservretry=None,
                                     authentication=None, save=False):
    '''
    Unsets values from the authenticationradiusaction configuration key.

    name(bool): Unsets the name value.

    serverip(bool): Unsets the serverip value.

    servername(bool): Unsets the servername value.

    serverport(bool): Unsets the serverport value.

    authtimeout(bool): Unsets the authtimeout value.

    radkey(bool): Unsets the radkey value.

    radnasip(bool): Unsets the radnasip value.

    radnasid(bool): Unsets the radnasid value.

    radvendorid(bool): Unsets the radvendorid value.

    radattributetype(bool): Unsets the radattributetype value.

    radgroupsprefix(bool): Unsets the radgroupsprefix value.

    radgroupseparator(bool): Unsets the radgroupseparator value.

    passencoding(bool): Unsets the passencoding value.

    ipvendorid(bool): Unsets the ipvendorid value.

    ipattributetype(bool): Unsets the ipattributetype value.

    accounting(bool): Unsets the accounting value.

    pwdvendorid(bool): Unsets the pwdvendorid value.

    pwdattributetype(bool): Unsets the pwdattributetype value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    callingstationid(bool): Unsets the callingstationid value.

    authservretry(bool): Unsets the authservretry value.

    authentication(bool): Unsets the authentication value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationradiusaction <args>

    '''

    result = {}

    payload = {'authenticationradiusaction': {}}

    if name:
        payload['authenticationradiusaction']['name'] = True

    if serverip:
        payload['authenticationradiusaction']['serverip'] = True

    if servername:
        payload['authenticationradiusaction']['servername'] = True

    if serverport:
        payload['authenticationradiusaction']['serverport'] = True

    if authtimeout:
        payload['authenticationradiusaction']['authtimeout'] = True

    if radkey:
        payload['authenticationradiusaction']['radkey'] = True

    if radnasip:
        payload['authenticationradiusaction']['radnasip'] = True

    if radnasid:
        payload['authenticationradiusaction']['radnasid'] = True

    if radvendorid:
        payload['authenticationradiusaction']['radvendorid'] = True

    if radattributetype:
        payload['authenticationradiusaction']['radattributetype'] = True

    if radgroupsprefix:
        payload['authenticationradiusaction']['radgroupsprefix'] = True

    if radgroupseparator:
        payload['authenticationradiusaction']['radgroupseparator'] = True

    if passencoding:
        payload['authenticationradiusaction']['passencoding'] = True

    if ipvendorid:
        payload['authenticationradiusaction']['ipvendorid'] = True

    if ipattributetype:
        payload['authenticationradiusaction']['ipattributetype'] = True

    if accounting:
        payload['authenticationradiusaction']['accounting'] = True

    if pwdvendorid:
        payload['authenticationradiusaction']['pwdvendorid'] = True

    if pwdattributetype:
        payload['authenticationradiusaction']['pwdattributetype'] = True

    if defaultauthenticationgroup:
        payload['authenticationradiusaction']['defaultauthenticationgroup'] = True

    if callingstationid:
        payload['authenticationradiusaction']['callingstationid'] = True

    if authservretry:
        payload['authenticationradiusaction']['authservretry'] = True

    if authentication:
        payload['authenticationradiusaction']['authentication'] = True

    execution = __proxy__['citrixns.post']('config/authenticationradiusaction?action=unset', payload)

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


def unset_authenticationradiuspolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Unsets values from the authenticationradiuspolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    reqaction(bool): Unsets the reqaction value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationradiuspolicy <args>

    '''

    result = {}

    payload = {'authenticationradiuspolicy': {}}

    if name:
        payload['authenticationradiuspolicy']['name'] = True

    if rule:
        payload['authenticationradiuspolicy']['rule'] = True

    if reqaction:
        payload['authenticationradiuspolicy']['reqaction'] = True

    execution = __proxy__['citrixns.post']('config/authenticationradiuspolicy?action=unset', payload)

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


def unset_authenticationsamlaction(name=None, samlidpcertname=None, samlsigningcertname=None, samlredirecturl=None,
                                   samlacsindex=None, samluserfield=None, samlrejectunsignedassertion=None,
                                   samlissuername=None, samltwofactor=None, defaultauthenticationgroup=None,
                                   attribute1=None, attribute2=None, attribute3=None, attribute4=None, attribute5=None,
                                   attribute6=None, attribute7=None, attribute8=None, attribute9=None, attribute10=None,
                                   attribute11=None, attribute12=None, attribute13=None, attribute14=None,
                                   attribute15=None, attribute16=None, signaturealg=None, digestmethod=None,
                                   requestedauthncontext=None, authnctxclassref=None, samlbinding=None,
                                   attributeconsumingserviceindex=None, sendthumbprint=None, enforceusername=None,
                                   logouturl=None, artifactresolutionserviceurl=None, skewtime=None, logoutbinding=None,
                                   forceauthn=None, save=False):
    '''
    Unsets values from the authenticationsamlaction configuration key.

    name(bool): Unsets the name value.

    samlidpcertname(bool): Unsets the samlidpcertname value.

    samlsigningcertname(bool): Unsets the samlsigningcertname value.

    samlredirecturl(bool): Unsets the samlredirecturl value.

    samlacsindex(bool): Unsets the samlacsindex value.

    samluserfield(bool): Unsets the samluserfield value.

    samlrejectunsignedassertion(bool): Unsets the samlrejectunsignedassertion value.

    samlissuername(bool): Unsets the samlissuername value.

    samltwofactor(bool): Unsets the samltwofactor value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    attribute1(bool): Unsets the attribute1 value.

    attribute2(bool): Unsets the attribute2 value.

    attribute3(bool): Unsets the attribute3 value.

    attribute4(bool): Unsets the attribute4 value.

    attribute5(bool): Unsets the attribute5 value.

    attribute6(bool): Unsets the attribute6 value.

    attribute7(bool): Unsets the attribute7 value.

    attribute8(bool): Unsets the attribute8 value.

    attribute9(bool): Unsets the attribute9 value.

    attribute10(bool): Unsets the attribute10 value.

    attribute11(bool): Unsets the attribute11 value.

    attribute12(bool): Unsets the attribute12 value.

    attribute13(bool): Unsets the attribute13 value.

    attribute14(bool): Unsets the attribute14 value.

    attribute15(bool): Unsets the attribute15 value.

    attribute16(bool): Unsets the attribute16 value.

    signaturealg(bool): Unsets the signaturealg value.

    digestmethod(bool): Unsets the digestmethod value.

    requestedauthncontext(bool): Unsets the requestedauthncontext value.

    authnctxclassref(bool): Unsets the authnctxclassref value.

    samlbinding(bool): Unsets the samlbinding value.

    attributeconsumingserviceindex(bool): Unsets the attributeconsumingserviceindex value.

    sendthumbprint(bool): Unsets the sendthumbprint value.

    enforceusername(bool): Unsets the enforceusername value.

    logouturl(bool): Unsets the logouturl value.

    artifactresolutionserviceurl(bool): Unsets the artifactresolutionserviceurl value.

    skewtime(bool): Unsets the skewtime value.

    logoutbinding(bool): Unsets the logoutbinding value.

    forceauthn(bool): Unsets the forceauthn value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationsamlaction <args>

    '''

    result = {}

    payload = {'authenticationsamlaction': {}}

    if name:
        payload['authenticationsamlaction']['name'] = True

    if samlidpcertname:
        payload['authenticationsamlaction']['samlidpcertname'] = True

    if samlsigningcertname:
        payload['authenticationsamlaction']['samlsigningcertname'] = True

    if samlredirecturl:
        payload['authenticationsamlaction']['samlredirecturl'] = True

    if samlacsindex:
        payload['authenticationsamlaction']['samlacsindex'] = True

    if samluserfield:
        payload['authenticationsamlaction']['samluserfield'] = True

    if samlrejectunsignedassertion:
        payload['authenticationsamlaction']['samlrejectunsignedassertion'] = True

    if samlissuername:
        payload['authenticationsamlaction']['samlissuername'] = True

    if samltwofactor:
        payload['authenticationsamlaction']['samltwofactor'] = True

    if defaultauthenticationgroup:
        payload['authenticationsamlaction']['defaultauthenticationgroup'] = True

    if attribute1:
        payload['authenticationsamlaction']['attribute1'] = True

    if attribute2:
        payload['authenticationsamlaction']['attribute2'] = True

    if attribute3:
        payload['authenticationsamlaction']['attribute3'] = True

    if attribute4:
        payload['authenticationsamlaction']['attribute4'] = True

    if attribute5:
        payload['authenticationsamlaction']['attribute5'] = True

    if attribute6:
        payload['authenticationsamlaction']['attribute6'] = True

    if attribute7:
        payload['authenticationsamlaction']['attribute7'] = True

    if attribute8:
        payload['authenticationsamlaction']['attribute8'] = True

    if attribute9:
        payload['authenticationsamlaction']['attribute9'] = True

    if attribute10:
        payload['authenticationsamlaction']['attribute10'] = True

    if attribute11:
        payload['authenticationsamlaction']['attribute11'] = True

    if attribute12:
        payload['authenticationsamlaction']['attribute12'] = True

    if attribute13:
        payload['authenticationsamlaction']['attribute13'] = True

    if attribute14:
        payload['authenticationsamlaction']['attribute14'] = True

    if attribute15:
        payload['authenticationsamlaction']['attribute15'] = True

    if attribute16:
        payload['authenticationsamlaction']['attribute16'] = True

    if signaturealg:
        payload['authenticationsamlaction']['signaturealg'] = True

    if digestmethod:
        payload['authenticationsamlaction']['digestmethod'] = True

    if requestedauthncontext:
        payload['authenticationsamlaction']['requestedauthncontext'] = True

    if authnctxclassref:
        payload['authenticationsamlaction']['authnctxclassref'] = True

    if samlbinding:
        payload['authenticationsamlaction']['samlbinding'] = True

    if attributeconsumingserviceindex:
        payload['authenticationsamlaction']['attributeconsumingserviceindex'] = True

    if sendthumbprint:
        payload['authenticationsamlaction']['sendthumbprint'] = True

    if enforceusername:
        payload['authenticationsamlaction']['enforceusername'] = True

    if logouturl:
        payload['authenticationsamlaction']['logouturl'] = True

    if artifactresolutionserviceurl:
        payload['authenticationsamlaction']['artifactresolutionserviceurl'] = True

    if skewtime:
        payload['authenticationsamlaction']['skewtime'] = True

    if logoutbinding:
        payload['authenticationsamlaction']['logoutbinding'] = True

    if forceauthn:
        payload['authenticationsamlaction']['forceauthn'] = True

    execution = __proxy__['citrixns.post']('config/authenticationsamlaction?action=unset', payload)

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


def unset_authenticationsamlidppolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                      newname=None, save=False):
    '''
    Unsets values from the authenticationsamlidppolicy configuration key.

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

    salt '*' authentication.unset_authenticationsamlidppolicy <args>

    '''

    result = {}

    payload = {'authenticationsamlidppolicy': {}}

    if name:
        payload['authenticationsamlidppolicy']['name'] = True

    if rule:
        payload['authenticationsamlidppolicy']['rule'] = True

    if action:
        payload['authenticationsamlidppolicy']['action'] = True

    if undefaction:
        payload['authenticationsamlidppolicy']['undefaction'] = True

    if comment:
        payload['authenticationsamlidppolicy']['comment'] = True

    if logaction:
        payload['authenticationsamlidppolicy']['logaction'] = True

    if newname:
        payload['authenticationsamlidppolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/authenticationsamlidppolicy?action=unset', payload)

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


def unset_authenticationsamlidpprofile(name=None, samlspcertname=None, samlidpcertname=None,
                                       assertionconsumerserviceurl=None, sendpassword=None, samlissuername=None,
                                       rejectunsignedrequests=None, signaturealg=None, digestmethod=None, audience=None,
                                       nameidformat=None, nameidexpr=None, attribute1=None, attribute1expr=None,
                                       attribute1friendlyname=None, attribute1format=None, attribute2=None,
                                       attribute2expr=None, attribute2friendlyname=None, attribute2format=None,
                                       attribute3=None, attribute3expr=None, attribute3friendlyname=None,
                                       attribute3format=None, attribute4=None, attribute4expr=None,
                                       attribute4friendlyname=None, attribute4format=None, attribute5=None,
                                       attribute5expr=None, attribute5friendlyname=None, attribute5format=None,
                                       attribute6=None, attribute6expr=None, attribute6friendlyname=None,
                                       attribute6format=None, attribute7=None, attribute7expr=None,
                                       attribute7friendlyname=None, attribute7format=None, attribute8=None,
                                       attribute8expr=None, attribute8friendlyname=None, attribute8format=None,
                                       attribute9=None, attribute9expr=None, attribute9friendlyname=None,
                                       attribute9format=None, attribute10=None, attribute10expr=None,
                                       attribute10friendlyname=None, attribute10format=None, attribute11=None,
                                       attribute11expr=None, attribute11friendlyname=None, attribute11format=None,
                                       attribute12=None, attribute12expr=None, attribute12friendlyname=None,
                                       attribute12format=None, attribute13=None, attribute13expr=None,
                                       attribute13friendlyname=None, attribute13format=None, attribute14=None,
                                       attribute14expr=None, attribute14friendlyname=None, attribute14format=None,
                                       attribute15=None, attribute15expr=None, attribute15friendlyname=None,
                                       attribute15format=None, attribute16=None, attribute16expr=None,
                                       attribute16friendlyname=None, attribute16format=None, encryptassertion=None,
                                       encryptionalgorithm=None, samlbinding=None, skewtime=None, serviceproviderid=None,
                                       signassertion=None, keytransportalg=None, splogouturl=None, logoutbinding=None,
                                       save=False):
    '''
    Unsets values from the authenticationsamlidpprofile configuration key.

    name(bool): Unsets the name value.

    samlspcertname(bool): Unsets the samlspcertname value.

    samlidpcertname(bool): Unsets the samlidpcertname value.

    assertionconsumerserviceurl(bool): Unsets the assertionconsumerserviceurl value.

    sendpassword(bool): Unsets the sendpassword value.

    samlissuername(bool): Unsets the samlissuername value.

    rejectunsignedrequests(bool): Unsets the rejectunsignedrequests value.

    signaturealg(bool): Unsets the signaturealg value.

    digestmethod(bool): Unsets the digestmethod value.

    audience(bool): Unsets the audience value.

    nameidformat(bool): Unsets the nameidformat value.

    nameidexpr(bool): Unsets the nameidexpr value.

    attribute1(bool): Unsets the attribute1 value.

    attribute1expr(bool): Unsets the attribute1expr value.

    attribute1friendlyname(bool): Unsets the attribute1friendlyname value.

    attribute1format(bool): Unsets the attribute1format value.

    attribute2(bool): Unsets the attribute2 value.

    attribute2expr(bool): Unsets the attribute2expr value.

    attribute2friendlyname(bool): Unsets the attribute2friendlyname value.

    attribute2format(bool): Unsets the attribute2format value.

    attribute3(bool): Unsets the attribute3 value.

    attribute3expr(bool): Unsets the attribute3expr value.

    attribute3friendlyname(bool): Unsets the attribute3friendlyname value.

    attribute3format(bool): Unsets the attribute3format value.

    attribute4(bool): Unsets the attribute4 value.

    attribute4expr(bool): Unsets the attribute4expr value.

    attribute4friendlyname(bool): Unsets the attribute4friendlyname value.

    attribute4format(bool): Unsets the attribute4format value.

    attribute5(bool): Unsets the attribute5 value.

    attribute5expr(bool): Unsets the attribute5expr value.

    attribute5friendlyname(bool): Unsets the attribute5friendlyname value.

    attribute5format(bool): Unsets the attribute5format value.

    attribute6(bool): Unsets the attribute6 value.

    attribute6expr(bool): Unsets the attribute6expr value.

    attribute6friendlyname(bool): Unsets the attribute6friendlyname value.

    attribute6format(bool): Unsets the attribute6format value.

    attribute7(bool): Unsets the attribute7 value.

    attribute7expr(bool): Unsets the attribute7expr value.

    attribute7friendlyname(bool): Unsets the attribute7friendlyname value.

    attribute7format(bool): Unsets the attribute7format value.

    attribute8(bool): Unsets the attribute8 value.

    attribute8expr(bool): Unsets the attribute8expr value.

    attribute8friendlyname(bool): Unsets the attribute8friendlyname value.

    attribute8format(bool): Unsets the attribute8format value.

    attribute9(bool): Unsets the attribute9 value.

    attribute9expr(bool): Unsets the attribute9expr value.

    attribute9friendlyname(bool): Unsets the attribute9friendlyname value.

    attribute9format(bool): Unsets the attribute9format value.

    attribute10(bool): Unsets the attribute10 value.

    attribute10expr(bool): Unsets the attribute10expr value.

    attribute10friendlyname(bool): Unsets the attribute10friendlyname value.

    attribute10format(bool): Unsets the attribute10format value.

    attribute11(bool): Unsets the attribute11 value.

    attribute11expr(bool): Unsets the attribute11expr value.

    attribute11friendlyname(bool): Unsets the attribute11friendlyname value.

    attribute11format(bool): Unsets the attribute11format value.

    attribute12(bool): Unsets the attribute12 value.

    attribute12expr(bool): Unsets the attribute12expr value.

    attribute12friendlyname(bool): Unsets the attribute12friendlyname value.

    attribute12format(bool): Unsets the attribute12format value.

    attribute13(bool): Unsets the attribute13 value.

    attribute13expr(bool): Unsets the attribute13expr value.

    attribute13friendlyname(bool): Unsets the attribute13friendlyname value.

    attribute13format(bool): Unsets the attribute13format value.

    attribute14(bool): Unsets the attribute14 value.

    attribute14expr(bool): Unsets the attribute14expr value.

    attribute14friendlyname(bool): Unsets the attribute14friendlyname value.

    attribute14format(bool): Unsets the attribute14format value.

    attribute15(bool): Unsets the attribute15 value.

    attribute15expr(bool): Unsets the attribute15expr value.

    attribute15friendlyname(bool): Unsets the attribute15friendlyname value.

    attribute15format(bool): Unsets the attribute15format value.

    attribute16(bool): Unsets the attribute16 value.

    attribute16expr(bool): Unsets the attribute16expr value.

    attribute16friendlyname(bool): Unsets the attribute16friendlyname value.

    attribute16format(bool): Unsets the attribute16format value.

    encryptassertion(bool): Unsets the encryptassertion value.

    encryptionalgorithm(bool): Unsets the encryptionalgorithm value.

    samlbinding(bool): Unsets the samlbinding value.

    skewtime(bool): Unsets the skewtime value.

    serviceproviderid(bool): Unsets the serviceproviderid value.

    signassertion(bool): Unsets the signassertion value.

    keytransportalg(bool): Unsets the keytransportalg value.

    splogouturl(bool): Unsets the splogouturl value.

    logoutbinding(bool): Unsets the logoutbinding value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationsamlidpprofile <args>

    '''

    result = {}

    payload = {'authenticationsamlidpprofile': {}}

    if name:
        payload['authenticationsamlidpprofile']['name'] = True

    if samlspcertname:
        payload['authenticationsamlidpprofile']['samlspcertname'] = True

    if samlidpcertname:
        payload['authenticationsamlidpprofile']['samlidpcertname'] = True

    if assertionconsumerserviceurl:
        payload['authenticationsamlidpprofile']['assertionconsumerserviceurl'] = True

    if sendpassword:
        payload['authenticationsamlidpprofile']['sendpassword'] = True

    if samlissuername:
        payload['authenticationsamlidpprofile']['samlissuername'] = True

    if rejectunsignedrequests:
        payload['authenticationsamlidpprofile']['rejectunsignedrequests'] = True

    if signaturealg:
        payload['authenticationsamlidpprofile']['signaturealg'] = True

    if digestmethod:
        payload['authenticationsamlidpprofile']['digestmethod'] = True

    if audience:
        payload['authenticationsamlidpprofile']['audience'] = True

    if nameidformat:
        payload['authenticationsamlidpprofile']['nameidformat'] = True

    if nameidexpr:
        payload['authenticationsamlidpprofile']['nameidexpr'] = True

    if attribute1:
        payload['authenticationsamlidpprofile']['attribute1'] = True

    if attribute1expr:
        payload['authenticationsamlidpprofile']['attribute1expr'] = True

    if attribute1friendlyname:
        payload['authenticationsamlidpprofile']['attribute1friendlyname'] = True

    if attribute1format:
        payload['authenticationsamlidpprofile']['attribute1format'] = True

    if attribute2:
        payload['authenticationsamlidpprofile']['attribute2'] = True

    if attribute2expr:
        payload['authenticationsamlidpprofile']['attribute2expr'] = True

    if attribute2friendlyname:
        payload['authenticationsamlidpprofile']['attribute2friendlyname'] = True

    if attribute2format:
        payload['authenticationsamlidpprofile']['attribute2format'] = True

    if attribute3:
        payload['authenticationsamlidpprofile']['attribute3'] = True

    if attribute3expr:
        payload['authenticationsamlidpprofile']['attribute3expr'] = True

    if attribute3friendlyname:
        payload['authenticationsamlidpprofile']['attribute3friendlyname'] = True

    if attribute3format:
        payload['authenticationsamlidpprofile']['attribute3format'] = True

    if attribute4:
        payload['authenticationsamlidpprofile']['attribute4'] = True

    if attribute4expr:
        payload['authenticationsamlidpprofile']['attribute4expr'] = True

    if attribute4friendlyname:
        payload['authenticationsamlidpprofile']['attribute4friendlyname'] = True

    if attribute4format:
        payload['authenticationsamlidpprofile']['attribute4format'] = True

    if attribute5:
        payload['authenticationsamlidpprofile']['attribute5'] = True

    if attribute5expr:
        payload['authenticationsamlidpprofile']['attribute5expr'] = True

    if attribute5friendlyname:
        payload['authenticationsamlidpprofile']['attribute5friendlyname'] = True

    if attribute5format:
        payload['authenticationsamlidpprofile']['attribute5format'] = True

    if attribute6:
        payload['authenticationsamlidpprofile']['attribute6'] = True

    if attribute6expr:
        payload['authenticationsamlidpprofile']['attribute6expr'] = True

    if attribute6friendlyname:
        payload['authenticationsamlidpprofile']['attribute6friendlyname'] = True

    if attribute6format:
        payload['authenticationsamlidpprofile']['attribute6format'] = True

    if attribute7:
        payload['authenticationsamlidpprofile']['attribute7'] = True

    if attribute7expr:
        payload['authenticationsamlidpprofile']['attribute7expr'] = True

    if attribute7friendlyname:
        payload['authenticationsamlidpprofile']['attribute7friendlyname'] = True

    if attribute7format:
        payload['authenticationsamlidpprofile']['attribute7format'] = True

    if attribute8:
        payload['authenticationsamlidpprofile']['attribute8'] = True

    if attribute8expr:
        payload['authenticationsamlidpprofile']['attribute8expr'] = True

    if attribute8friendlyname:
        payload['authenticationsamlidpprofile']['attribute8friendlyname'] = True

    if attribute8format:
        payload['authenticationsamlidpprofile']['attribute8format'] = True

    if attribute9:
        payload['authenticationsamlidpprofile']['attribute9'] = True

    if attribute9expr:
        payload['authenticationsamlidpprofile']['attribute9expr'] = True

    if attribute9friendlyname:
        payload['authenticationsamlidpprofile']['attribute9friendlyname'] = True

    if attribute9format:
        payload['authenticationsamlidpprofile']['attribute9format'] = True

    if attribute10:
        payload['authenticationsamlidpprofile']['attribute10'] = True

    if attribute10expr:
        payload['authenticationsamlidpprofile']['attribute10expr'] = True

    if attribute10friendlyname:
        payload['authenticationsamlidpprofile']['attribute10friendlyname'] = True

    if attribute10format:
        payload['authenticationsamlidpprofile']['attribute10format'] = True

    if attribute11:
        payload['authenticationsamlidpprofile']['attribute11'] = True

    if attribute11expr:
        payload['authenticationsamlidpprofile']['attribute11expr'] = True

    if attribute11friendlyname:
        payload['authenticationsamlidpprofile']['attribute11friendlyname'] = True

    if attribute11format:
        payload['authenticationsamlidpprofile']['attribute11format'] = True

    if attribute12:
        payload['authenticationsamlidpprofile']['attribute12'] = True

    if attribute12expr:
        payload['authenticationsamlidpprofile']['attribute12expr'] = True

    if attribute12friendlyname:
        payload['authenticationsamlidpprofile']['attribute12friendlyname'] = True

    if attribute12format:
        payload['authenticationsamlidpprofile']['attribute12format'] = True

    if attribute13:
        payload['authenticationsamlidpprofile']['attribute13'] = True

    if attribute13expr:
        payload['authenticationsamlidpprofile']['attribute13expr'] = True

    if attribute13friendlyname:
        payload['authenticationsamlidpprofile']['attribute13friendlyname'] = True

    if attribute13format:
        payload['authenticationsamlidpprofile']['attribute13format'] = True

    if attribute14:
        payload['authenticationsamlidpprofile']['attribute14'] = True

    if attribute14expr:
        payload['authenticationsamlidpprofile']['attribute14expr'] = True

    if attribute14friendlyname:
        payload['authenticationsamlidpprofile']['attribute14friendlyname'] = True

    if attribute14format:
        payload['authenticationsamlidpprofile']['attribute14format'] = True

    if attribute15:
        payload['authenticationsamlidpprofile']['attribute15'] = True

    if attribute15expr:
        payload['authenticationsamlidpprofile']['attribute15expr'] = True

    if attribute15friendlyname:
        payload['authenticationsamlidpprofile']['attribute15friendlyname'] = True

    if attribute15format:
        payload['authenticationsamlidpprofile']['attribute15format'] = True

    if attribute16:
        payload['authenticationsamlidpprofile']['attribute16'] = True

    if attribute16expr:
        payload['authenticationsamlidpprofile']['attribute16expr'] = True

    if attribute16friendlyname:
        payload['authenticationsamlidpprofile']['attribute16friendlyname'] = True

    if attribute16format:
        payload['authenticationsamlidpprofile']['attribute16format'] = True

    if encryptassertion:
        payload['authenticationsamlidpprofile']['encryptassertion'] = True

    if encryptionalgorithm:
        payload['authenticationsamlidpprofile']['encryptionalgorithm'] = True

    if samlbinding:
        payload['authenticationsamlidpprofile']['samlbinding'] = True

    if skewtime:
        payload['authenticationsamlidpprofile']['skewtime'] = True

    if serviceproviderid:
        payload['authenticationsamlidpprofile']['serviceproviderid'] = True

    if signassertion:
        payload['authenticationsamlidpprofile']['signassertion'] = True

    if keytransportalg:
        payload['authenticationsamlidpprofile']['keytransportalg'] = True

    if splogouturl:
        payload['authenticationsamlidpprofile']['splogouturl'] = True

    if logoutbinding:
        payload['authenticationsamlidpprofile']['logoutbinding'] = True

    execution = __proxy__['citrixns.post']('config/authenticationsamlidpprofile?action=unset', payload)

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


def unset_authenticationsamlpolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Unsets values from the authenticationsamlpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    reqaction(bool): Unsets the reqaction value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationsamlpolicy <args>

    '''

    result = {}

    payload = {'authenticationsamlpolicy': {}}

    if name:
        payload['authenticationsamlpolicy']['name'] = True

    if rule:
        payload['authenticationsamlpolicy']['rule'] = True

    if reqaction:
        payload['authenticationsamlpolicy']['reqaction'] = True

    execution = __proxy__['citrixns.post']('config/authenticationsamlpolicy?action=unset', payload)

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


def unset_authenticationstorefrontauthaction(name=None, serverurl=None, domain=None, defaultauthenticationgroup=None,
                                             save=False):
    '''
    Unsets values from the authenticationstorefrontauthaction configuration key.

    name(bool): Unsets the name value.

    serverurl(bool): Unsets the serverurl value.

    domain(bool): Unsets the domain value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationstorefrontauthaction <args>

    '''

    result = {}

    payload = {'authenticationstorefrontauthaction': {}}

    if name:
        payload['authenticationstorefrontauthaction']['name'] = True

    if serverurl:
        payload['authenticationstorefrontauthaction']['serverurl'] = True

    if domain:
        payload['authenticationstorefrontauthaction']['domain'] = True

    if defaultauthenticationgroup:
        payload['authenticationstorefrontauthaction']['defaultauthenticationgroup'] = True

    execution = __proxy__['citrixns.post']('config/authenticationstorefrontauthaction?action=unset', payload)

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


def unset_authenticationtacacsaction(name=None, serverip=None, serverport=None, authtimeout=None, tacacssecret=None,
                                     authorization=None, accounting=None, auditfailedcmds=None, groupattrname=None,
                                     defaultauthenticationgroup=None, attribute1=None, attribute2=None, attribute3=None,
                                     attribute4=None, attribute5=None, attribute6=None, attribute7=None, attribute8=None,
                                     attribute9=None, attribute10=None, attribute11=None, attribute12=None,
                                     attribute13=None, attribute14=None, attribute15=None, attribute16=None,
                                     save=False):
    '''
    Unsets values from the authenticationtacacsaction configuration key.

    name(bool): Unsets the name value.

    serverip(bool): Unsets the serverip value.

    serverport(bool): Unsets the serverport value.

    authtimeout(bool): Unsets the authtimeout value.

    tacacssecret(bool): Unsets the tacacssecret value.

    authorization(bool): Unsets the authorization value.

    accounting(bool): Unsets the accounting value.

    auditfailedcmds(bool): Unsets the auditfailedcmds value.

    groupattrname(bool): Unsets the groupattrname value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    attribute1(bool): Unsets the attribute1 value.

    attribute2(bool): Unsets the attribute2 value.

    attribute3(bool): Unsets the attribute3 value.

    attribute4(bool): Unsets the attribute4 value.

    attribute5(bool): Unsets the attribute5 value.

    attribute6(bool): Unsets the attribute6 value.

    attribute7(bool): Unsets the attribute7 value.

    attribute8(bool): Unsets the attribute8 value.

    attribute9(bool): Unsets the attribute9 value.

    attribute10(bool): Unsets the attribute10 value.

    attribute11(bool): Unsets the attribute11 value.

    attribute12(bool): Unsets the attribute12 value.

    attribute13(bool): Unsets the attribute13 value.

    attribute14(bool): Unsets the attribute14 value.

    attribute15(bool): Unsets the attribute15 value.

    attribute16(bool): Unsets the attribute16 value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationtacacsaction <args>

    '''

    result = {}

    payload = {'authenticationtacacsaction': {}}

    if name:
        payload['authenticationtacacsaction']['name'] = True

    if serverip:
        payload['authenticationtacacsaction']['serverip'] = True

    if serverport:
        payload['authenticationtacacsaction']['serverport'] = True

    if authtimeout:
        payload['authenticationtacacsaction']['authtimeout'] = True

    if tacacssecret:
        payload['authenticationtacacsaction']['tacacssecret'] = True

    if authorization:
        payload['authenticationtacacsaction']['authorization'] = True

    if accounting:
        payload['authenticationtacacsaction']['accounting'] = True

    if auditfailedcmds:
        payload['authenticationtacacsaction']['auditfailedcmds'] = True

    if groupattrname:
        payload['authenticationtacacsaction']['groupattrname'] = True

    if defaultauthenticationgroup:
        payload['authenticationtacacsaction']['defaultauthenticationgroup'] = True

    if attribute1:
        payload['authenticationtacacsaction']['attribute1'] = True

    if attribute2:
        payload['authenticationtacacsaction']['attribute2'] = True

    if attribute3:
        payload['authenticationtacacsaction']['attribute3'] = True

    if attribute4:
        payload['authenticationtacacsaction']['attribute4'] = True

    if attribute5:
        payload['authenticationtacacsaction']['attribute5'] = True

    if attribute6:
        payload['authenticationtacacsaction']['attribute6'] = True

    if attribute7:
        payload['authenticationtacacsaction']['attribute7'] = True

    if attribute8:
        payload['authenticationtacacsaction']['attribute8'] = True

    if attribute9:
        payload['authenticationtacacsaction']['attribute9'] = True

    if attribute10:
        payload['authenticationtacacsaction']['attribute10'] = True

    if attribute11:
        payload['authenticationtacacsaction']['attribute11'] = True

    if attribute12:
        payload['authenticationtacacsaction']['attribute12'] = True

    if attribute13:
        payload['authenticationtacacsaction']['attribute13'] = True

    if attribute14:
        payload['authenticationtacacsaction']['attribute14'] = True

    if attribute15:
        payload['authenticationtacacsaction']['attribute15'] = True

    if attribute16:
        payload['authenticationtacacsaction']['attribute16'] = True

    execution = __proxy__['citrixns.post']('config/authenticationtacacsaction?action=unset', payload)

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


def unset_authenticationtacacspolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Unsets values from the authenticationtacacspolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    reqaction(bool): Unsets the reqaction value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationtacacspolicy <args>

    '''

    result = {}

    payload = {'authenticationtacacspolicy': {}}

    if name:
        payload['authenticationtacacspolicy']['name'] = True

    if rule:
        payload['authenticationtacacspolicy']['rule'] = True

    if reqaction:
        payload['authenticationtacacspolicy']['reqaction'] = True

    execution = __proxy__['citrixns.post']('config/authenticationtacacspolicy?action=unset', payload)

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


def unset_authenticationvserver(name=None, servicetype=None, ipv46=None, range=None, port=None, state=None,
                                authentication=None, authenticationdomain=None, comment=None, td=None, appflowlog=None,
                                maxloginattempts=None, failedlogintimeout=None, newname=None, save=False):
    '''
    Unsets values from the authenticationvserver configuration key.

    name(bool): Unsets the name value.

    servicetype(bool): Unsets the servicetype value.

    ipv46(bool): Unsets the ipv46 value.

    range(bool): Unsets the range value.

    port(bool): Unsets the port value.

    state(bool): Unsets the state value.

    authentication(bool): Unsets the authentication value.

    authenticationdomain(bool): Unsets the authenticationdomain value.

    comment(bool): Unsets the comment value.

    td(bool): Unsets the td value.

    appflowlog(bool): Unsets the appflowlog value.

    maxloginattempts(bool): Unsets the maxloginattempts value.

    failedlogintimeout(bool): Unsets the failedlogintimeout value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationvserver <args>

    '''

    result = {}

    payload = {'authenticationvserver': {}}

    if name:
        payload['authenticationvserver']['name'] = True

    if servicetype:
        payload['authenticationvserver']['servicetype'] = True

    if ipv46:
        payload['authenticationvserver']['ipv46'] = True

    if range:
        payload['authenticationvserver']['range'] = True

    if port:
        payload['authenticationvserver']['port'] = True

    if state:
        payload['authenticationvserver']['state'] = True

    if authentication:
        payload['authenticationvserver']['authentication'] = True

    if authenticationdomain:
        payload['authenticationvserver']['authenticationdomain'] = True

    if comment:
        payload['authenticationvserver']['comment'] = True

    if td:
        payload['authenticationvserver']['td'] = True

    if appflowlog:
        payload['authenticationvserver']['appflowlog'] = True

    if maxloginattempts:
        payload['authenticationvserver']['maxloginattempts'] = True

    if failedlogintimeout:
        payload['authenticationvserver']['failedlogintimeout'] = True

    if newname:
        payload['authenticationvserver']['newname'] = True

    execution = __proxy__['citrixns.post']('config/authenticationvserver?action=unset', payload)

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


def unset_authenticationwebauthaction(name=None, serverip=None, serverport=None, fullreqexpr=None, scheme=None,
                                      successrule=None, defaultauthenticationgroup=None, attribute1=None,
                                      attribute2=None, attribute3=None, attribute4=None, attribute5=None,
                                      attribute6=None, attribute7=None, attribute8=None, attribute9=None,
                                      attribute10=None, attribute11=None, attribute12=None, attribute13=None,
                                      attribute14=None, attribute15=None, attribute16=None, save=False):
    '''
    Unsets values from the authenticationwebauthaction configuration key.

    name(bool): Unsets the name value.

    serverip(bool): Unsets the serverip value.

    serverport(bool): Unsets the serverport value.

    fullreqexpr(bool): Unsets the fullreqexpr value.

    scheme(bool): Unsets the scheme value.

    successrule(bool): Unsets the successrule value.

    defaultauthenticationgroup(bool): Unsets the defaultauthenticationgroup value.

    attribute1(bool): Unsets the attribute1 value.

    attribute2(bool): Unsets the attribute2 value.

    attribute3(bool): Unsets the attribute3 value.

    attribute4(bool): Unsets the attribute4 value.

    attribute5(bool): Unsets the attribute5 value.

    attribute6(bool): Unsets the attribute6 value.

    attribute7(bool): Unsets the attribute7 value.

    attribute8(bool): Unsets the attribute8 value.

    attribute9(bool): Unsets the attribute9 value.

    attribute10(bool): Unsets the attribute10 value.

    attribute11(bool): Unsets the attribute11 value.

    attribute12(bool): Unsets the attribute12 value.

    attribute13(bool): Unsets the attribute13 value.

    attribute14(bool): Unsets the attribute14 value.

    attribute15(bool): Unsets the attribute15 value.

    attribute16(bool): Unsets the attribute16 value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.unset_authenticationwebauthaction <args>

    '''

    result = {}

    payload = {'authenticationwebauthaction': {}}

    if name:
        payload['authenticationwebauthaction']['name'] = True

    if serverip:
        payload['authenticationwebauthaction']['serverip'] = True

    if serverport:
        payload['authenticationwebauthaction']['serverport'] = True

    if fullreqexpr:
        payload['authenticationwebauthaction']['fullreqexpr'] = True

    if scheme:
        payload['authenticationwebauthaction']['scheme'] = True

    if successrule:
        payload['authenticationwebauthaction']['successrule'] = True

    if defaultauthenticationgroup:
        payload['authenticationwebauthaction']['defaultauthenticationgroup'] = True

    if attribute1:
        payload['authenticationwebauthaction']['attribute1'] = True

    if attribute2:
        payload['authenticationwebauthaction']['attribute2'] = True

    if attribute3:
        payload['authenticationwebauthaction']['attribute3'] = True

    if attribute4:
        payload['authenticationwebauthaction']['attribute4'] = True

    if attribute5:
        payload['authenticationwebauthaction']['attribute5'] = True

    if attribute6:
        payload['authenticationwebauthaction']['attribute6'] = True

    if attribute7:
        payload['authenticationwebauthaction']['attribute7'] = True

    if attribute8:
        payload['authenticationwebauthaction']['attribute8'] = True

    if attribute9:
        payload['authenticationwebauthaction']['attribute9'] = True

    if attribute10:
        payload['authenticationwebauthaction']['attribute10'] = True

    if attribute11:
        payload['authenticationwebauthaction']['attribute11'] = True

    if attribute12:
        payload['authenticationwebauthaction']['attribute12'] = True

    if attribute13:
        payload['authenticationwebauthaction']['attribute13'] = True

    if attribute14:
        payload['authenticationwebauthaction']['attribute14'] = True

    if attribute15:
        payload['authenticationwebauthaction']['attribute15'] = True

    if attribute16:
        payload['authenticationwebauthaction']['attribute16'] = True

    execution = __proxy__['citrixns.post']('config/authenticationwebauthaction?action=unset', payload)

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


def update_authenticationauthnprofile(name=None, authnvsname=None, authenticationhost=None, authenticationdomain=None,
                                      authenticationlevel=None, save=False):
    '''
    Update the running configuration for the authenticationauthnprofile config key.

    name(str): Name for the authentication profile.  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the RADIUS action is added. Minimum length = 1

    authnvsname(str): Name of the authentication vserver at which authentication should be done. Minimum length = 1 Maximum
        length = 128

    authenticationhost(str): Hostname of the authentication vserver to which user must be redirected for authentication.
        Minimum length = 1 Maximum length = 256

    authenticationdomain(str): Domain for which TM cookie must to be set. If unspecified, cookie will be set for FQDN.
        Minimum length = 1 Maximum length = 256

    authenticationlevel(int): Authentication weight or level of the vserver to which this will bound. This is used to order
        TM vservers based on the protection required. A session that is created by authenticating against TM vserver at
        given level cannot be used to access TM vserver at a higher level. Minimum value = 0 Maximum value = 255

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationauthnprofile <args>

    '''

    result = {}

    payload = {'authenticationauthnprofile': {}}

    if name:
        payload['authenticationauthnprofile']['name'] = name

    if authnvsname:
        payload['authenticationauthnprofile']['authnvsname'] = authnvsname

    if authenticationhost:
        payload['authenticationauthnprofile']['authenticationhost'] = authenticationhost

    if authenticationdomain:
        payload['authenticationauthnprofile']['authenticationdomain'] = authenticationdomain

    if authenticationlevel:
        payload['authenticationauthnprofile']['authenticationlevel'] = authenticationlevel

    execution = __proxy__['citrixns.put']('config/authenticationauthnprofile', payload)

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


def update_authenticationcertaction(name=None, twofactor=None, usernamefield=None, groupnamefield=None,
                                    defaultauthenticationgroup=None, save=False):
    '''
    Update the running configuration for the authenticationcertaction config key.

    name(str): Name for the client cert authentication server profile (action).  Must begin with a letter, number, or the
        underscore character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space
        ( ), at (@), equals (=), colon (:), and underscore characters. Cannot be changed after certifcate action is
        created.  The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my authentication action" or my
        authentication action). Minimum length = 1

    twofactor(str): Enables or disables two-factor authentication.  Two factor authentication is client cert authentication
        followed by password authentication. Default value: OFF Possible values = ON, OFF

    usernamefield(str): Client-cert field from which the username is extracted. Must be set to either ""Subject"" and
        ""Issuer"" (include both sets of double quotation marks). Format: ;lt;field;gt;:;lt;subfield;gt;. Minimum length
        = 1

    groupnamefield(str): Client-cert field from which the group is extracted. Must be set to either ""Subject"" and
        ""Issuer"" (include both sets of double quotation marks). Format: ;lt;field;gt;:;lt;subfield;gt;. Minimum length
        = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationcertaction <args>

    '''

    result = {}

    payload = {'authenticationcertaction': {}}

    if name:
        payload['authenticationcertaction']['name'] = name

    if twofactor:
        payload['authenticationcertaction']['twofactor'] = twofactor

    if usernamefield:
        payload['authenticationcertaction']['usernamefield'] = usernamefield

    if groupnamefield:
        payload['authenticationcertaction']['groupnamefield'] = groupnamefield

    if defaultauthenticationgroup:
        payload['authenticationcertaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.put']('config/authenticationcertaction', payload)

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


def update_authenticationcertpolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Update the running configuration for the authenticationcertpolicy config key.

    name(str): Name for the client certificate authentication policy.  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters. Cannot be changed after cert authentication policy is
        created.  The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my authentication policy" or my
        authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the authentication server. Minimum length = 1

    reqaction(str): Name of the client cert authentication action to be performed if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationcertpolicy <args>

    '''

    result = {}

    payload = {'authenticationcertpolicy': {}}

    if name:
        payload['authenticationcertpolicy']['name'] = name

    if rule:
        payload['authenticationcertpolicy']['rule'] = rule

    if reqaction:
        payload['authenticationcertpolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.put']('config/authenticationcertpolicy', payload)

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


def update_authenticationdfaaction(name=None, clientid=None, serverurl=None, passphrase=None,
                                   defaultauthenticationgroup=None, save=False):
    '''
    Update the running configuration for the authenticationdfaaction config key.

    name(str): Name for the DFA action.  Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the DFA action is added. Minimum length = 1

    clientid(str): If configured, this string is sent to the DFA server as the X-Citrix-Exchange header value.

    serverurl(str): DFA Server URL.

    passphrase(str): Key shared between the DFA server and the NetScaler appliance.  Required to allow the NetScaler
        appliance to communicate with the DFA server. Minimum length = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationdfaaction <args>

    '''

    result = {}

    payload = {'authenticationdfaaction': {}}

    if name:
        payload['authenticationdfaaction']['name'] = name

    if clientid:
        payload['authenticationdfaaction']['clientid'] = clientid

    if serverurl:
        payload['authenticationdfaaction']['serverurl'] = serverurl

    if passphrase:
        payload['authenticationdfaaction']['passphrase'] = passphrase

    if defaultauthenticationgroup:
        payload['authenticationdfaaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.put']('config/authenticationdfaaction', payload)

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


def update_authenticationdfapolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the authenticationdfapolicy config key.

    name(str): Name for the DFA policy.  Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after DFA policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the Web server. Minimum length = 1

    action(str): Name of the DFA action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationdfapolicy <args>

    '''

    result = {}

    payload = {'authenticationdfapolicy': {}}

    if name:
        payload['authenticationdfapolicy']['name'] = name

    if rule:
        payload['authenticationdfapolicy']['rule'] = rule

    if action:
        payload['authenticationdfapolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/authenticationdfapolicy', payload)

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


def update_authenticationepaaction(name=None, csecexpr=None, killprocess=None, deletefiles=None, defaultepagroup=None,
                                   quarantinegroup=None, save=False):
    '''
    Update the running configuration for the authenticationepaaction config key.

    name(str): Name for the epa action. Must begin with a  letter, number, or the underscore character (_), and must consist
        only of letters, numbers, and the hyphen (-), period (.) pound  (#), space ( ), at (@), equals (=), colon (:),
        and underscore  characters. Cannot be changed after epa action is created.The following requirement applies only
        to the NetScaler CLI:If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my aaa action" or my aaa action). Minimum length = 1

    csecexpr(str): it holds the ClientSecurityExpression to be sent to the client.

    killprocess(str): String specifying the name of a process to be terminated by the endpoint analysis (EPA) tool. Multiple
        processes to be delimited by comma.

    deletefiles(str): String specifying the path(s) and name(s) of the files to be deleted by the endpoint analysis (EPA)
        tool. Multiple files to be delimited by comma.

    defaultepagroup(str): This is the default group that is chosen when the EPA check succeeds. Maximum length = 64

    quarantinegroup(str): This is the quarantine group that is chosen when the EPA check fails if configured. Maximum length
        = 64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationepaaction <args>

    '''

    result = {}

    payload = {'authenticationepaaction': {}}

    if name:
        payload['authenticationepaaction']['name'] = name

    if csecexpr:
        payload['authenticationepaaction']['csecexpr'] = csecexpr

    if killprocess:
        payload['authenticationepaaction']['killprocess'] = killprocess

    if deletefiles:
        payload['authenticationepaaction']['deletefiles'] = deletefiles

    if defaultepagroup:
        payload['authenticationepaaction']['defaultepagroup'] = defaultepagroup

    if quarantinegroup:
        payload['authenticationepaaction']['quarantinegroup'] = quarantinegroup

    execution = __proxy__['citrixns.put']('config/authenticationepaaction', payload)

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


def update_authenticationldapaction(name=None, serverip=None, servername=None, serverport=None, authtimeout=None,
                                    ldapbase=None, ldapbinddn=None, ldapbinddnpassword=None, ldaploginname=None,
                                    searchfilter=None, groupattrname=None, subattributename=None, sectype=None,
                                    svrtype=None, ssonameattribute=None, authentication=None, requireuser=None,
                                    passwdchange=None, nestedgroupextraction=None, maxnestinglevel=None,
                                    followreferrals=None, maxldapreferrals=None, referraldnslookup=None,
                                    mssrvrecordlocation=None, validateservercert=None, ldaphostname=None,
                                    groupnameidentifier=None, groupsearchattribute=None, groupsearchsubattribute=None,
                                    groupsearchfilter=None, defaultauthenticationgroup=None, attribute1=None,
                                    attribute2=None, attribute3=None, attribute4=None, attribute5=None, attribute6=None,
                                    attribute7=None, attribute8=None, attribute9=None, attribute10=None,
                                    attribute11=None, attribute12=None, attribute13=None, attribute14=None,
                                    attribute15=None, attribute16=None, save=False):
    '''
    Update the running configuration for the authenticationldapaction config key.

    name(str): Name for the new LDAP action.  Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the LDAP action is added.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication action" or my authentication action). Minimum length = 1

    serverip(str): IP address assigned to the LDAP server. Minimum length = 1

    servername(str): LDAP server name as a FQDN. Mutually exclusive with LDAP IP address. Minimum length = 1

    serverport(int): Port on which the LDAP server accepts connections. Default value: 389 Minimum value = 1

    authtimeout(int): Number of seconds the NetScaler appliance waits for a response from the RADIUS server. Default value: 3
        Minimum value = 1

    ldapbase(str): Base (node) from which to start LDAP searches.  If the LDAP server is running locally, the default value
        of base is dc=netscaler, dc=com.

    ldapbinddn(str): Full distinguished name (DN) that is used to bind to the LDAP server.  Default:
        cn=Manager,dc=netscaler,dc=com.

    ldapbinddnpassword(str): Password used to bind to the LDAP server. Minimum length = 1

    ldaploginname(str): LDAP login name attribute.  The NetScaler appliance uses the LDAP login name to query external LDAP
        servers or Active Directories.

    searchfilter(str): String to be combined with the default LDAP user search string to form the search value. For example,
        if the search filter "vpnallowed=true" is combined with the LDAP login name "samaccount" and the user-supplied
        username is "bob", the result is the LDAP search string ""(;amp;(vpnallowed=true)(samaccount=bob)"" (Be sure to
        enclose the search string in two sets of double quotation marks; both sets are needed.). Minimum length = 1

    groupattrname(str): LDAP group attribute name. Used for group extraction on the LDAP server.

    subattributename(str): LDAP group sub-attribute name.  Used for group extraction from the LDAP server.

    sectype(str): Type of security used for communications between the NetScaler appliance and the LDAP server. For the
        PLAINTEXT setting, no encryption is required. Default value: PLAINTEXT Possible values = PLAINTEXT, TLS, SSL

    svrtype(str): The type of LDAP server. Default value: AAA_LDAP_SERVER_TYPE_DEFAULT Possible values = AD, NDS

    ssonameattribute(str): LDAP single signon (SSO) attribute.  The NetScaler appliance uses the SSO name attribute to query
        external LDAP servers or Active Directories for an alternate username.

    authentication(str): Perform LDAP authentication. If authentication is disabled, any LDAP authentication attempt returns
        authentication success if the user is found.  CAUTION! Authentication should be disabled only for authorization
        group extraction or where other (non-LDAP) authentication methods are in use and either bound to a primary list
        or flagged as secondary. Default value: ENABLED Possible values = ENABLED, DISABLED

    requireuser(str): Require a successful user search for authentication. Default value: YES Possible values = YES, NO

    passwdchange(str): Allow password change requests. Default value: DISABLED Possible values = ENABLED, DISABLED

    nestedgroupextraction(str): Allow nested group extraction, in which the NetScaler appliance queries external LDAP servers
        to determine whether a group is part of another group. Default value: OFF Possible values = ON, OFF

    maxnestinglevel(int): If nested group extraction is ON, specifies the number of levels up to which group extraction is
        performed. Default value: 2 Minimum value = 2

    followreferrals(str): Setting this option to ON enables following LDAP referrals received from the LDAP server. Default
        value: OFF Possible values = ON, OFF

    maxldapreferrals(int): Specifies the maximum number of nested referrals to follow. Default value: 1 Minimum value = 1

    referraldnslookup(str): Specifies the DNS Record lookup Type for the referrals. Default value: A-REC Possible values =
        A-REC, SRV-REC, MSSRV-REC

    mssrvrecordlocation(str): MSSRV Specific parameter. Used to locate the DNS node to which the SRV record pertains in the
        domainname. The domainname is appended to it to form the srv record. Example : For "dc._msdcs", the srv record
        formed is _ldap._tcp.dc._msdcs.;lt;domainname;gt;.

    validateservercert(str): When to validate LDAP server certs. Default value: NO Possible values = YES, NO

    ldaphostname(str): Hostname for the LDAP server. If -validateServerCert is ON then this must be the host name on the
        certificate from the LDAP server. A hostname mismatch will cause a connection failure.

    groupnameidentifier(str): Name that uniquely identifies a group in LDAP or Active Directory.

    groupsearchattribute(str): LDAP group search attribute.  Used to determine to which groups a group belongs.

    groupsearchsubattribute(str): LDAP group search subattribute.  Used to determine to which groups a group belongs.

    groupsearchfilter(str): String to be combined with the default LDAP group search string to form the search value. For
        example, the group search filter ""vpnallowed=true"" when combined with the group identifier ""samaccount"" and
        the group name ""g1"" yields the LDAP search string ""(;amp;(vpnallowed=true)(samaccount=g1)"". (Be sure to
        enclose the search string in two sets of double quotation marks; both sets are needed.).

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Expression that would be evaluated to extract attribute1 from the ldap response.

    attribute2(str): Expression that would be evaluated to extract attribute2 from the ldap response.

    attribute3(str): Expression that would be evaluated to extract attribute3 from the ldap response.

    attribute4(str): Expression that would be evaluated to extract attribute4 from the ldap response.

    attribute5(str): Expression that would be evaluated to extract attribute5 from the ldap response.

    attribute6(str): Expression that would be evaluated to extract attribute6 from the ldap response.

    attribute7(str): Expression that would be evaluated to extract attribute7 from the ldap response.

    attribute8(str): Expression that would be evaluated to extract attribute8 from the ldap response.

    attribute9(str): Expression that would be evaluated to extract attribute9 from the ldap response.

    attribute10(str): Expression that would be evaluated to extract attribute10 from the ldap response.

    attribute11(str): Expression that would be evaluated to extract attribute11 from the ldap response.

    attribute12(str): Expression that would be evaluated to extract attribute12 from the ldap response.

    attribute13(str): Expression that would be evaluated to extract attribute13 from the ldap response.

    attribute14(str): Expression that would be evaluated to extract attribute14 from the ldap response.

    attribute15(str): Expression that would be evaluated to extract attribute15 from the ldap response.

    attribute16(str): Expression that would be evaluated to extract attribute16 from the ldap response.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationldapaction <args>

    '''

    result = {}

    payload = {'authenticationldapaction': {}}

    if name:
        payload['authenticationldapaction']['name'] = name

    if serverip:
        payload['authenticationldapaction']['serverip'] = serverip

    if servername:
        payload['authenticationldapaction']['servername'] = servername

    if serverport:
        payload['authenticationldapaction']['serverport'] = serverport

    if authtimeout:
        payload['authenticationldapaction']['authtimeout'] = authtimeout

    if ldapbase:
        payload['authenticationldapaction']['ldapbase'] = ldapbase

    if ldapbinddn:
        payload['authenticationldapaction']['ldapbinddn'] = ldapbinddn

    if ldapbinddnpassword:
        payload['authenticationldapaction']['ldapbinddnpassword'] = ldapbinddnpassword

    if ldaploginname:
        payload['authenticationldapaction']['ldaploginname'] = ldaploginname

    if searchfilter:
        payload['authenticationldapaction']['searchfilter'] = searchfilter

    if groupattrname:
        payload['authenticationldapaction']['groupattrname'] = groupattrname

    if subattributename:
        payload['authenticationldapaction']['subattributename'] = subattributename

    if sectype:
        payload['authenticationldapaction']['sectype'] = sectype

    if svrtype:
        payload['authenticationldapaction']['svrtype'] = svrtype

    if ssonameattribute:
        payload['authenticationldapaction']['ssonameattribute'] = ssonameattribute

    if authentication:
        payload['authenticationldapaction']['authentication'] = authentication

    if requireuser:
        payload['authenticationldapaction']['requireuser'] = requireuser

    if passwdchange:
        payload['authenticationldapaction']['passwdchange'] = passwdchange

    if nestedgroupextraction:
        payload['authenticationldapaction']['nestedgroupextraction'] = nestedgroupextraction

    if maxnestinglevel:
        payload['authenticationldapaction']['maxnestinglevel'] = maxnestinglevel

    if followreferrals:
        payload['authenticationldapaction']['followreferrals'] = followreferrals

    if maxldapreferrals:
        payload['authenticationldapaction']['maxldapreferrals'] = maxldapreferrals

    if referraldnslookup:
        payload['authenticationldapaction']['referraldnslookup'] = referraldnslookup

    if mssrvrecordlocation:
        payload['authenticationldapaction']['mssrvrecordlocation'] = mssrvrecordlocation

    if validateservercert:
        payload['authenticationldapaction']['validateservercert'] = validateservercert

    if ldaphostname:
        payload['authenticationldapaction']['ldaphostname'] = ldaphostname

    if groupnameidentifier:
        payload['authenticationldapaction']['groupnameidentifier'] = groupnameidentifier

    if groupsearchattribute:
        payload['authenticationldapaction']['groupsearchattribute'] = groupsearchattribute

    if groupsearchsubattribute:
        payload['authenticationldapaction']['groupsearchsubattribute'] = groupsearchsubattribute

    if groupsearchfilter:
        payload['authenticationldapaction']['groupsearchfilter'] = groupsearchfilter

    if defaultauthenticationgroup:
        payload['authenticationldapaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationldapaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationldapaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationldapaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationldapaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationldapaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationldapaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationldapaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationldapaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationldapaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationldapaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationldapaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationldapaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationldapaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationldapaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationldapaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationldapaction']['attribute16'] = attribute16

    execution = __proxy__['citrixns.put']('config/authenticationldapaction', payload)

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


def update_authenticationldappolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Update the running configuration for the authenticationldappolicy config key.

    name(str): Name for the LDAP policy.  Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after LDAP policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the LDAP server. Minimum length = 1

    reqaction(str): Name of the LDAP action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationldappolicy <args>

    '''

    result = {}

    payload = {'authenticationldappolicy': {}}

    if name:
        payload['authenticationldappolicy']['name'] = name

    if rule:
        payload['authenticationldappolicy']['rule'] = rule

    if reqaction:
        payload['authenticationldappolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.put']('config/authenticationldappolicy', payload)

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


def update_authenticationlocalpolicy(name=None, rule=None, save=False):
    '''
    Update the running configuration for the authenticationlocalpolicy config key.

    name(str): Name for the local authentication policy.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after local policy is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication policy" or my authentication policy).

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to perform the
        authentication.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationlocalpolicy <args>

    '''

    result = {}

    payload = {'authenticationlocalpolicy': {}}

    if name:
        payload['authenticationlocalpolicy']['name'] = name

    if rule:
        payload['authenticationlocalpolicy']['rule'] = rule

    execution = __proxy__['citrixns.put']('config/authenticationlocalpolicy', payload)

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


def update_authenticationloginschema(name=None, authenticationschema=None, userexpression=None, passwdexpression=None,
                                     usercredentialindex=None, passwordcredentialindex=None, authenticationstrength=None,
                                     ssocredentials=None, save=False):
    '''
    Update the running configuration for the authenticationloginschema config key.

    name(str): Name for the new login schema. Login schema defines the way login form is rendered. It provides a way to
        customize the fields that are shown to the user. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an action is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my action" or my action). Minimum length = 1

    authenticationschema(str): Name of the file for reading authentication schema to be sent for Login Page UI. This file
        should contain xml definition of elements as per Citrix Forms Authentication Protocol to be able to render login
        form. If administrator does not want to prompt users for additional credentials but continue with previously
        obtained credentials, then "noschema" can be given as argument. Please note that this applies only to
        loginSchemas that are used with user-defined factors, and not the vserver factor. Minimum length = 1

    userexpression(str): Expression for username extraction during login. This can be any relevant advanced policy
        expression. Minimum length = 1

    passwdexpression(str): Expression for password extraction during login. This can be any relevant advanced policy
        expression. Minimum length = 1

    usercredentialindex(int): The index at which user entered username should be stored in session. Minimum value = 1 Maximum
        value = 16

    passwordcredentialindex(int): The index at which user entered password should be stored in session. Minimum value = 1
        Maximum value = 16

    authenticationstrength(int): Weight of the current authentication. Minimum value = 0 Maximum value = 65535

    ssocredentials(str): This option indicates whether current factor credentials are the default SSO (SingleSignOn)
        credentials. Default value: NO Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationloginschema <args>

    '''

    result = {}

    payload = {'authenticationloginschema': {}}

    if name:
        payload['authenticationloginschema']['name'] = name

    if authenticationschema:
        payload['authenticationloginschema']['authenticationschema'] = authenticationschema

    if userexpression:
        payload['authenticationloginschema']['userexpression'] = userexpression

    if passwdexpression:
        payload['authenticationloginschema']['passwdexpression'] = passwdexpression

    if usercredentialindex:
        payload['authenticationloginschema']['usercredentialindex'] = usercredentialindex

    if passwordcredentialindex:
        payload['authenticationloginschema']['passwordcredentialindex'] = passwordcredentialindex

    if authenticationstrength:
        payload['authenticationloginschema']['authenticationstrength'] = authenticationstrength

    if ssocredentials:
        payload['authenticationloginschema']['ssocredentials'] = ssocredentials

    execution = __proxy__['citrixns.put']('config/authenticationloginschema', payload)

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


def update_authenticationloginschemapolicy(name=None, rule=None, action=None, undefaction=None, comment=None,
                                           logaction=None, newname=None, save=False):
    '''
    Update the running configuration for the authenticationloginschemapolicy config key.

    name(str): Name for the LoginSchema policy. This is used for selecting parameters for user logon. Must begin with an
        ASCII alphanumeric or underscore (_) character, and must contain only ASCII alphanumeric, underscore, hash (#),
        period (.), space, colon (:), at (@), equals (=), and hyphen (-) characters. Cannot be changed after the policy
        is created.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my policy" or my policy). Minimum
        length = 1

    rule(str): Expression which is evaluated to choose a profile for authentication. Maximum length of a string literal in
        the expression is 255 characters. A longer string can be split into smaller strings of up to 255 characters each,
        and the smaller strings concatenated with the + operator. For example, you can create a 500-character string as
        follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements
        apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression
        in double quotation marks. * If the expression itself includes double quotation marks, escape the quotations by
        using the \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case
        you do not have to escape the double quotation marks. Minimum length = 1

    action(str): Name of the profile to apply to requests or connections that match this policy. * NOOP - Do not take any
        specific action when this policy evaluates to true. This is useful to implicitly go to a different policy set. *
        RESET - Reset the client connection by closing it. The client program, such as a browser, will handle this and
        may inform the user. The client may then resend the request if desired. * DROP - Drop the request without sending
        a response to the user. Minimum length = 1

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any comments to preserve information about this policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the LoginSchema policy.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        loginschemapolicy policy" or my loginschemapolicy policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationloginschemapolicy <args>

    '''

    result = {}

    payload = {'authenticationloginschemapolicy': {}}

    if name:
        payload['authenticationloginschemapolicy']['name'] = name

    if rule:
        payload['authenticationloginschemapolicy']['rule'] = rule

    if action:
        payload['authenticationloginschemapolicy']['action'] = action

    if undefaction:
        payload['authenticationloginschemapolicy']['undefaction'] = undefaction

    if comment:
        payload['authenticationloginschemapolicy']['comment'] = comment

    if logaction:
        payload['authenticationloginschemapolicy']['logaction'] = logaction

    if newname:
        payload['authenticationloginschemapolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/authenticationloginschemapolicy', payload)

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


def update_authenticationnegotiateaction(name=None, domain=None, domainuser=None, domainuserpasswd=None, ou=None,
                                         defaultauthenticationgroup=None, keytab=None, ntlmpath=None, save=False):
    '''
    Update the running configuration for the authenticationnegotiateaction config key.

    name(str): Name for the AD KDC server profile (negotiate action).  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters. Cannot be changed after AD KDC server profile is created.
        The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my authentication action" or my authentication action).
        Minimum length = 1

    domain(str): Domain name of the service principal that represnts Netscaler. Minimum length = 1

    domainuser(str): User name of the account that is mapped with Netscaler principal. This can be given along with domain
        and password when keytab file is not available. If username is given along with keytab file, then that keytab
        file will be searched for this users credentials. Minimum length = 1

    domainuserpasswd(str): Password of the account that is mapped to the NetScaler principal. Minimum length = 1

    ou(str): Active Directory organizational units (OU) attribute. Minimum length = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    keytab(str): The path to the keytab file that is used to decrypt kerberos tickets presented to Netscaler. If keytab is
        not available, domain/username/password can be specified in the negotiate action configuration. Minimum length =
        1

    ntlmpath(str): The path to the site that is enabled for NTLM authentication, including FQDN of the server. This is used
        when clients fallback to NTLM. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationnegotiateaction <args>

    '''

    result = {}

    payload = {'authenticationnegotiateaction': {}}

    if name:
        payload['authenticationnegotiateaction']['name'] = name

    if domain:
        payload['authenticationnegotiateaction']['domain'] = domain

    if domainuser:
        payload['authenticationnegotiateaction']['domainuser'] = domainuser

    if domainuserpasswd:
        payload['authenticationnegotiateaction']['domainuserpasswd'] = domainuserpasswd

    if ou:
        payload['authenticationnegotiateaction']['ou'] = ou

    if defaultauthenticationgroup:
        payload['authenticationnegotiateaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if keytab:
        payload['authenticationnegotiateaction']['keytab'] = keytab

    if ntlmpath:
        payload['authenticationnegotiateaction']['ntlmpath'] = ntlmpath

    execution = __proxy__['citrixns.put']('config/authenticationnegotiateaction', payload)

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


def update_authenticationnegotiatepolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Update the running configuration for the authenticationnegotiatepolicy config key.

    name(str): Name for the negotiate authentication policy.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Cannot be changed after AD KCD (negotiate) policy is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my authentication policy" or my authentication policy).
        Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the AD KCD server. Minimum length = 1

    reqaction(str): Name of the negotiate action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationnegotiatepolicy <args>

    '''

    result = {}

    payload = {'authenticationnegotiatepolicy': {}}

    if name:
        payload['authenticationnegotiatepolicy']['name'] = name

    if rule:
        payload['authenticationnegotiatepolicy']['rule'] = rule

    if reqaction:
        payload['authenticationnegotiatepolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.put']('config/authenticationnegotiatepolicy', payload)

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


def update_authenticationoauthaction(name=None, oauthtype=None, authorizationendpoint=None, tokenendpoint=None,
                                     idtokendecryptendpoint=None, clientid=None, clientsecret=None,
                                     defaultauthenticationgroup=None, attribute1=None, attribute2=None, attribute3=None,
                                     attribute4=None, attribute5=None, attribute6=None, attribute7=None, attribute8=None,
                                     attribute9=None, attribute10=None, attribute11=None, attribute12=None,
                                     attribute13=None, attribute14=None, attribute15=None, attribute16=None,
                                     tenantid=None, graphendpoint=None, refreshinterval=None, certendpoint=None,
                                     audience=None, usernamefield=None, skewtime=None, issuer=None, save=False):
    '''
    Update the running configuration for the authenticationoauthaction config key.

    name(str): Name for the OAuth Authentication action.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the profile is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication action" or my authentication action). Minimum length = 1

    oauthtype(str): Type of the OAuth implementation. Default value is generic implementation that is applicable for most
        deployments. Default value: GENERIC Possible values = GENERIC, INTUNE

    authorizationendpoint(str): Authorization endpoint/url to which unauthenticated user will be redirected. Netscaler
        appliance redirects user to this endpoint by adding query parameters including clientid. If this parameter not
        specified then as default value we take Token Endpoint/URL value. Please note that Authorization Endpoint or
        Token Endpoint is mandatory for oauthAction.

    tokenendpoint(str): URL to which OAuth token will be posted to verify its authenticity. User obtains this token from
        Authorization server upon successful authentication. Netscaler appliance will validate presented token by posting
        it to the URL configured.

    idtokendecryptendpoint(str): URL to which obtained idtoken will be posted to get a decrypted user identity. Encrypted
        idtoken will be obtained by posting OAuth token to token endpoint. In order to decrypt idtoken, Netscaler
        appliance posts request to the URL configured.

    clientid(str): Unique identity of the client/user who is getting authenticated. Authorization server infers client
        configuration using this ID. Minimum length = 1

    clientsecret(str): Secret string established by user and authorization server. Minimum length = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Expression that would be evaluated to extract attribute1 from the oauth response.

    attribute2(str): Expression that would be evaluated to extract attribute2 from the oauth response.

    attribute3(str): Expression that would be evaluated to extract attribute3 from the oauth response.

    attribute4(str): Expression that would be evaluated to extract attribute4 from the oauth response.

    attribute5(str): Expression that would be evaluated to extract attribute5 from the oauth response.

    attribute6(str): Expression that would be evaluated to extract attribute6 from the oauth response.

    attribute7(str): Expression that would be evaluated to extract attribute7 from the oauth response.

    attribute8(str): Expression that would be evaluated to extract attribute8 from the oauth response.

    attribute9(str): Expression that would be evaluated to extract attribute9 from the oauth response.

    attribute10(str): Expression that would be evaluated to extract attribute10 from the oauth response.

    attribute11(str): Expression that would be evaluated to extract attribute11 from the oauth response.

    attribute12(str): Expression that would be evaluated to extract attribute12 from the oauth response.

    attribute13(str): Expression that would be evaluated to extract attribute13 from the oauth response.

    attribute14(str): Expression that would be evaluated to extract attribute14 from the oauth response.

    attribute15(str): Expression that would be evaluated to extract attribute15 from the oauth response.

    attribute16(str): Expression that would be evaluated to extract attribute16 from the oauth response.

    tenantid(str): TenantID of the application. This is usually specific to providers such as Microsoft and usually refers to
        the deployment identifier.

    graphendpoint(str): URL of the Graph API service to learn Enterprise Mobility Services (EMS) endpoints.

    refreshinterval(int): Interval at which services are monitored for necessary configuration. Default value: 1440

    certendpoint(str): URL of the endpoint that contains JWKs (Json Web Key) for JWT (Json Web Token) verification.

    audience(str): Audience for which token sent by Authorization server is applicable. This is typically entity name or url
        that represents the recipient.

    usernamefield(str): Attribute in the token from which username should be extracted. Minimum length = 1

    skewtime(int): This option specifies the allowed clock skew in number of minutes that Netscaler allows on an incoming
        token. For example, if skewTime is 10, then token would be valid from (current time - 10) min to (current time +
        10) min, ie 20min in all. Default value: 5

    issuer(str): Identity of the server whose tokens are to be accepted.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationoauthaction <args>

    '''

    result = {}

    payload = {'authenticationoauthaction': {}}

    if name:
        payload['authenticationoauthaction']['name'] = name

    if oauthtype:
        payload['authenticationoauthaction']['oauthtype'] = oauthtype

    if authorizationendpoint:
        payload['authenticationoauthaction']['authorizationendpoint'] = authorizationendpoint

    if tokenendpoint:
        payload['authenticationoauthaction']['tokenendpoint'] = tokenendpoint

    if idtokendecryptendpoint:
        payload['authenticationoauthaction']['idtokendecryptendpoint'] = idtokendecryptendpoint

    if clientid:
        payload['authenticationoauthaction']['clientid'] = clientid

    if clientsecret:
        payload['authenticationoauthaction']['clientsecret'] = clientsecret

    if defaultauthenticationgroup:
        payload['authenticationoauthaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationoauthaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationoauthaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationoauthaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationoauthaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationoauthaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationoauthaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationoauthaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationoauthaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationoauthaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationoauthaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationoauthaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationoauthaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationoauthaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationoauthaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationoauthaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationoauthaction']['attribute16'] = attribute16

    if tenantid:
        payload['authenticationoauthaction']['tenantid'] = tenantid

    if graphendpoint:
        payload['authenticationoauthaction']['graphendpoint'] = graphendpoint

    if refreshinterval:
        payload['authenticationoauthaction']['refreshinterval'] = refreshinterval

    if certendpoint:
        payload['authenticationoauthaction']['certendpoint'] = certendpoint

    if audience:
        payload['authenticationoauthaction']['audience'] = audience

    if usernamefield:
        payload['authenticationoauthaction']['usernamefield'] = usernamefield

    if skewtime:
        payload['authenticationoauthaction']['skewtime'] = skewtime

    if issuer:
        payload['authenticationoauthaction']['issuer'] = issuer

    execution = __proxy__['citrixns.put']('config/authenticationoauthaction', payload)

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


def update_authenticationpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                newname=None, save=False):
    '''
    Update the running configuration for the authenticationpolicy config key.

    name(str): Name for the advance AUTHENTICATION policy.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Cannot be changed after AUTHENTICATION policy is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my authentication policy" or my authentication policy).
        Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the AUTHENTICATION server.

    action(str): Name of the authentication action to be performed if the policy matches.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any comments to preserve information about this policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the authentication policy. Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters.   The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        authentication policy" or my authentication policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationpolicy <args>

    '''

    result = {}

    payload = {'authenticationpolicy': {}}

    if name:
        payload['authenticationpolicy']['name'] = name

    if rule:
        payload['authenticationpolicy']['rule'] = rule

    if action:
        payload['authenticationpolicy']['action'] = action

    if undefaction:
        payload['authenticationpolicy']['undefaction'] = undefaction

    if comment:
        payload['authenticationpolicy']['comment'] = comment

    if logaction:
        payload['authenticationpolicy']['logaction'] = logaction

    if newname:
        payload['authenticationpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/authenticationpolicy', payload)

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


def update_authenticationradiusaction(name=None, serverip=None, servername=None, serverport=None, authtimeout=None,
                                      radkey=None, radnasip=None, radnasid=None, radvendorid=None, radattributetype=None,
                                      radgroupsprefix=None, radgroupseparator=None, passencoding=None, ipvendorid=None,
                                      ipattributetype=None, accounting=None, pwdvendorid=None, pwdattributetype=None,
                                      defaultauthenticationgroup=None, callingstationid=None, authservretry=None,
                                      authentication=None, save=False):
    '''
    Update the running configuration for the authenticationradiusaction config key.

    name(str): Name for the RADIUS action.  Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the RADIUS action is added. Minimum length = 1

    serverip(str): IP address assigned to the RADIUS server. Minimum length = 1

    servername(str): RADIUS server name as a FQDN. Mutually exclusive with RADIUS IP address. Minimum length = 1

    serverport(int): Port number on which the RADIUS server listens for connections. Minimum value = 1

    authtimeout(int): Number of seconds the NetScaler appliance waits for a response from the RADIUS server. Default value: 3
        Minimum value = 1

    radkey(str): Key shared between the RADIUS server and the NetScaler appliance.  Required to allow the NetScaler appliance
        to communicate with the RADIUS server. Minimum length = 1

    radnasip(str): If enabled, the NetScaler appliance IP address (NSIP) is sent to the RADIUS server as the Network Access
        Server IP (NASIP) address.  The RADIUS protocol defines the meaning and use of the NASIP address. Possible values
        = ENABLED, DISABLED

    radnasid(str): If configured, this string is sent to the RADIUS server as the Network Access Server ID (NASID).

    radvendorid(int): RADIUS vendor ID attribute, used for RADIUS group extraction. Minimum value = 1

    radattributetype(int): RADIUS attribute type, used for RADIUS group extraction. Minimum value = 1

    radgroupsprefix(str): RADIUS groups prefix string.  This groups prefix precedes the group names within a RADIUS attribute
        for RADIUS group extraction.

    radgroupseparator(str): RADIUS group separator string The group separator delimits group names within a RADIUS attribute
        for RADIUS group extraction.

    passencoding(str): Encoding type for passwords in RADIUS packets that the NetScaler appliance sends to the RADIUS server.
        Default value: pap Possible values = pap, chap, mschapv1, mschapv2

    ipvendorid(int): Vendor ID of the intranet IP attribute in the RADIUS response. NOTE: A value of 0 indicates that the
        attribute is not vendor encoded.

    ipattributetype(int): Remote IP address attribute type in a RADIUS response. Minimum value = 1

    accounting(str): Whether the RADIUS server is currently accepting accounting messages. Possible values = ON, OFF

    pwdvendorid(int): Vendor ID of the attribute, in the RADIUS response, used to extract the user password. Minimum value =
        1

    pwdattributetype(int): Vendor-specific password attribute type in a RADIUS response. Minimum value = 1

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    callingstationid(str): Send Calling-Station-ID of the client to the RADIUS server. IP Address of the client is sent as
        its Calling-Station-ID. Default value: DISABLED Possible values = ENABLED, DISABLED

    authservretry(int): Number of retry by the NetScaler appliance before getting response from the RADIUS server. Default
        value: 3 Minimum value = 1 Maximum value = 10

    authentication(str): Configure the RADIUS server state to accept or refuse authentication messages. Default value: ON
        Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationradiusaction <args>

    '''

    result = {}

    payload = {'authenticationradiusaction': {}}

    if name:
        payload['authenticationradiusaction']['name'] = name

    if serverip:
        payload['authenticationradiusaction']['serverip'] = serverip

    if servername:
        payload['authenticationradiusaction']['servername'] = servername

    if serverport:
        payload['authenticationradiusaction']['serverport'] = serverport

    if authtimeout:
        payload['authenticationradiusaction']['authtimeout'] = authtimeout

    if radkey:
        payload['authenticationradiusaction']['radkey'] = radkey

    if radnasip:
        payload['authenticationradiusaction']['radnasip'] = radnasip

    if radnasid:
        payload['authenticationradiusaction']['radnasid'] = radnasid

    if radvendorid:
        payload['authenticationradiusaction']['radvendorid'] = radvendorid

    if radattributetype:
        payload['authenticationradiusaction']['radattributetype'] = radattributetype

    if radgroupsprefix:
        payload['authenticationradiusaction']['radgroupsprefix'] = radgroupsprefix

    if radgroupseparator:
        payload['authenticationradiusaction']['radgroupseparator'] = radgroupseparator

    if passencoding:
        payload['authenticationradiusaction']['passencoding'] = passencoding

    if ipvendorid:
        payload['authenticationradiusaction']['ipvendorid'] = ipvendorid

    if ipattributetype:
        payload['authenticationradiusaction']['ipattributetype'] = ipattributetype

    if accounting:
        payload['authenticationradiusaction']['accounting'] = accounting

    if pwdvendorid:
        payload['authenticationradiusaction']['pwdvendorid'] = pwdvendorid

    if pwdattributetype:
        payload['authenticationradiusaction']['pwdattributetype'] = pwdattributetype

    if defaultauthenticationgroup:
        payload['authenticationradiusaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if callingstationid:
        payload['authenticationradiusaction']['callingstationid'] = callingstationid

    if authservretry:
        payload['authenticationradiusaction']['authservretry'] = authservretry

    if authentication:
        payload['authenticationradiusaction']['authentication'] = authentication

    execution = __proxy__['citrixns.put']('config/authenticationradiusaction', payload)

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


def update_authenticationradiuspolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Update the running configuration for the authenticationradiuspolicy config key.

    name(str): Name for the RADIUS authentication policy.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after RADIUS policy is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my authentication policy" or my authentication policy). Minimum
        length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the RADIUS server.

    reqaction(str): Name of the RADIUS action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationradiuspolicy <args>

    '''

    result = {}

    payload = {'authenticationradiuspolicy': {}}

    if name:
        payload['authenticationradiuspolicy']['name'] = name

    if rule:
        payload['authenticationradiuspolicy']['rule'] = rule

    if reqaction:
        payload['authenticationradiuspolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.put']('config/authenticationradiuspolicy', payload)

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


def update_authenticationsamlaction(name=None, samlidpcertname=None, samlsigningcertname=None, samlredirecturl=None,
                                    samlacsindex=None, samluserfield=None, samlrejectunsignedassertion=None,
                                    samlissuername=None, samltwofactor=None, defaultauthenticationgroup=None,
                                    attribute1=None, attribute2=None, attribute3=None, attribute4=None, attribute5=None,
                                    attribute6=None, attribute7=None, attribute8=None, attribute9=None, attribute10=None,
                                    attribute11=None, attribute12=None, attribute13=None, attribute14=None,
                                    attribute15=None, attribute16=None, signaturealg=None, digestmethod=None,
                                    requestedauthncontext=None, authnctxclassref=None, samlbinding=None,
                                    attributeconsumingserviceindex=None, sendthumbprint=None, enforceusername=None,
                                    logouturl=None, artifactresolutionserviceurl=None, skewtime=None, logoutbinding=None,
                                    forceauthn=None, save=False):
    '''
    Update the running configuration for the authenticationsamlaction config key.

    name(str): Name for the SAML server profile (action).  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after SAML profile is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication action" or my authentication action). Minimum length = 1

    samlidpcertname(str): Name of the SAML server as given in that servers SSL certificate. Minimum length = 1

    samlsigningcertname(str): Name of the signing authority as given in the SAML servers SSL certificate. Minimum length = 1

    samlredirecturl(str): URL to which users are redirected for authentication. Minimum length = 1

    samlacsindex(int): Index/ID of the metadata entry corresponding to this configuration. Default value: 255 Minimum value =
        0 Maximum value = 255

    samluserfield(str): SAML user ID, as given in the SAML assertion. Minimum length = 1

    samlrejectunsignedassertion(str): Reject unsigned SAML assertions. ON option results in rejection of Assertion that is
        received without signature. STRICT option ensures that both Response and Assertion are signed. OFF allows
        unsigned Assertions. Default value: ON Possible values = ON, OFF, STRICT

    samlissuername(str): The name to be used in requests sent from Netscaler to IdP to uniquely identify Netscaler. Minimum
        length = 1

    samltwofactor(str): Option to enable second factor after SAML. Default value: OFF Possible values = ON, OFF

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute1.
        Maximum length of the extracted attribute is 239 bytes.

    attribute2(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute2.
        Maximum length of the extracted attribute is 239 bytes.

    attribute3(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute3.
        Maximum length of the extracted attribute is 239 bytes.

    attribute4(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute4.
        Maximum length of the extracted attribute is 239 bytes.

    attribute5(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute5.
        Maximum length of the extracted attribute is 239 bytes.

    attribute6(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute6.
        Maximum length of the extracted attribute is 239 bytes.

    attribute7(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute7.
        Maximum length of the extracted attribute is 239 bytes.

    attribute8(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute8.
        Maximum length of the extracted attribute is 239 bytes.

    attribute9(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute9.
        Maximum length of the extracted attribute is 239 bytes.

    attribute10(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute10.
        Maximum length of the extracted attribute is 239 bytes.

    attribute11(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute11.
        Maximum length of the extracted attribute is 239 bytes.

    attribute12(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute12.
        Maximum length of the extracted attribute is 239 bytes.

    attribute13(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute13.
        Maximum length of the extracted attribute is 239 bytes.

    attribute14(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute14.
        Maximum length of the extracted attribute is 239 bytes.

    attribute15(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute15.
        Maximum length of the extracted attribute is 239 bytes.

    attribute16(str): Name of the attribute in SAML Assertion whose value needs to be extracted and stored as attribute16.
        Maximum length of the extracted attribute is 239 bytes.

    signaturealg(str): Algorithm to be used to sign/verify SAML transactions. Default value: RSA-SHA1 Possible values =
        RSA-SHA1, RSA-SHA256

    digestmethod(str): Algorithm to be used to compute/verify digest for SAML transactions. Default value: SHA1 Possible
        values = SHA1, SHA256

    requestedauthncontext(str): This element specifies the authentication context requirements of authentication statements
        returned in the response. Default value: exact Possible values = exact, minimum, maximum, better

    authnctxclassref(list(str)): This element specifies the authentication class types that are requested from IdP
        (IdentityProvider). InternetProtocol: This is applicable when a principal is authenticated through the use of a
        provided IP address. InternetProtocolPassword: This is applicable when a principal is authenticated through the
        use of a provided IP address, in addition to a username/password. Kerberos: This is applicable when the principal
        has authenticated using a password to a local authentication authority, in order to acquire a Kerberos ticket.
        MobileOneFactorUnregistered: This indicates authentication of the mobile device without requiring explicit
        end-user interaction. MobileTwoFactorUnregistered: This indicates two-factor based authentication during mobile
        customer registration process, such as secure device and user PIN. MobileOneFactorContract: Reflects mobile
        contract customer registration procedures and a single factor authentication. MobileTwoFactorContract: Reflects
        mobile contract customer registration procedures and a two-factor based authentication. Password: This class is
        applicable when a principal authenticates using password over unprotected http session.
        PasswordProtectedTransport: This class is applicable when a principal authenticates to an authentication
        authority through the presentation of a password over a protected session. PreviousSession: This class is
        applicable when a principal had authenticated to an authentication authority at some point in the past using any
        authentication context. X509: This indicates that the principal authenticated by means of a digital signature
        where the key was validated as part of an X.509 Public Key Infrastructure. PGP: This indicates that the principal
        authenticated by means of a digital signature where the key was validated as part of a PGP Public Key
        Infrastructure. SPKI: This indicates that the principal authenticated by means of a digital signature where the
        key was validated via an SPKI Infrastructure. XMLDSig: This indicates that the principal authenticated by means
        of a digital signature according to the processing rules specified in the XML Digital Signature specification.
        Smartcard: This indicates that the principal has authenticated using smartcard. SmartcardPKI: This class is
        applicable when a principal authenticates to an authentication authority through a two-factor authentication
        mechanism using a smartcard with enclosed private key and a PIN. SoftwarePKI: This class is applicable when a
        principal uses an X.509 certificate stored in software to authenticate to the authentication authority.
        Telephony: This class is used to indicate that the principal authenticated via the provision of a fixed-line
        telephone number, transported via a telephony protocol such as ADSL. NomadTelephony: Indicates that the principal
        is "roaming" and authenticates via the means of the line number, a user suffix, and a password element.
        PersonalTelephony: This class is used to indicate that the principal authenticated via the provision of a
        fixed-line telephone. AuthenticatedTelephony: Indicates that the principal authenticated via the means of the
        line number, a user suffix, and a password element. SecureRemotePassword: This class is applicable when the
        authentication was performed by means of Secure Remote Password. TLSClient: This class indicates that the
        principal authenticated by means of a client certificate, secured with the SSL/TLS transport. TimeSyncToken: This
        is applicable when a principal authenticates through a time synchronization token. Unspecified: This indicates
        that the authentication was performed by unspecified means. Windows: This indicates that Windows integrated
        authentication is utilized for authentication. Possible values = InternetProtocol, InternetProtocolPassword,
        Kerberos, MobileOneFactorUnregistered, MobileTwoFactorUnregistered, MobileOneFactorContract,
        MobileTwoFactorContract, Password, PasswordProtectedTransport, PreviousSession, X509, PGP, SPKI, XMLDSig,
        Smartcard, SmartcardPKI, SoftwarePKI, Telephony, NomadTelephony, PersonalTelephony, AuthenticatedTelephony,
        SecureRemotePassword, TLSClient, TimeSyncToken, Unspecified, Windows

    samlbinding(str): This element specifies the transport mechanism of saml messages. Default value: POST Possible values =
        REDIRECT, POST, ARTIFACT

    attributeconsumingserviceindex(int): Index/ID of the attribute specification at Identity Provider (IdP). IdP will locate
        attributes requested by SP using this index and send those attributes in Assertion. Default value: 255 Minimum
        value = 0 Maximum value = 255

    sendthumbprint(str): Option to send thumbprint instead of x509 certificate in SAML request. Default value: OFF Possible
        values = ON, OFF

    enforceusername(str): Option to choose whether the username that is extracted from SAML assertion can be edited in login
        page while doing second factor. Default value: ON Possible values = ON, OFF

    logouturl(str): SingleLogout URL on IdP to which logoutRequest will be sent on Netscaler session cleanup.

    artifactresolutionserviceurl(str): URL of the Artifact Resolution Service on IdP to which Netscaler will post artifact to
        get actual SAML token.

    skewtime(int): This option specifies the allowed clock skew in number of minutes that Netscaler ServiceProvider allows on
        an incoming assertion. For example, if skewTime is 10, then assertion would be valid from (current time - 10) min
        to (current time + 10) min, ie 20min in all. Default value: 5

    logoutbinding(str): This element specifies the transport mechanism of saml logout messages. Default value: POST Possible
        values = REDIRECT, POST

    forceauthn(str): Option that forces authentication at the Identity Provider (IdP) that receives Netscalers request.
        Default value: OFF Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationsamlaction <args>

    '''

    result = {}

    payload = {'authenticationsamlaction': {}}

    if name:
        payload['authenticationsamlaction']['name'] = name

    if samlidpcertname:
        payload['authenticationsamlaction']['samlidpcertname'] = samlidpcertname

    if samlsigningcertname:
        payload['authenticationsamlaction']['samlsigningcertname'] = samlsigningcertname

    if samlredirecturl:
        payload['authenticationsamlaction']['samlredirecturl'] = samlredirecturl

    if samlacsindex:
        payload['authenticationsamlaction']['samlacsindex'] = samlacsindex

    if samluserfield:
        payload['authenticationsamlaction']['samluserfield'] = samluserfield

    if samlrejectunsignedassertion:
        payload['authenticationsamlaction']['samlrejectunsignedassertion'] = samlrejectunsignedassertion

    if samlissuername:
        payload['authenticationsamlaction']['samlissuername'] = samlissuername

    if samltwofactor:
        payload['authenticationsamlaction']['samltwofactor'] = samltwofactor

    if defaultauthenticationgroup:
        payload['authenticationsamlaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationsamlaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationsamlaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationsamlaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationsamlaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationsamlaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationsamlaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationsamlaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationsamlaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationsamlaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationsamlaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationsamlaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationsamlaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationsamlaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationsamlaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationsamlaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationsamlaction']['attribute16'] = attribute16

    if signaturealg:
        payload['authenticationsamlaction']['signaturealg'] = signaturealg

    if digestmethod:
        payload['authenticationsamlaction']['digestmethod'] = digestmethod

    if requestedauthncontext:
        payload['authenticationsamlaction']['requestedauthncontext'] = requestedauthncontext

    if authnctxclassref:
        payload['authenticationsamlaction']['authnctxclassref'] = authnctxclassref

    if samlbinding:
        payload['authenticationsamlaction']['samlbinding'] = samlbinding

    if attributeconsumingserviceindex:
        payload['authenticationsamlaction']['attributeconsumingserviceindex'] = attributeconsumingserviceindex

    if sendthumbprint:
        payload['authenticationsamlaction']['sendthumbprint'] = sendthumbprint

    if enforceusername:
        payload['authenticationsamlaction']['enforceusername'] = enforceusername

    if logouturl:
        payload['authenticationsamlaction']['logouturl'] = logouturl

    if artifactresolutionserviceurl:
        payload['authenticationsamlaction']['artifactresolutionserviceurl'] = artifactresolutionserviceurl

    if skewtime:
        payload['authenticationsamlaction']['skewtime'] = skewtime

    if logoutbinding:
        payload['authenticationsamlaction']['logoutbinding'] = logoutbinding

    if forceauthn:
        payload['authenticationsamlaction']['forceauthn'] = forceauthn

    execution = __proxy__['citrixns.put']('config/authenticationsamlaction', payload)

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


def update_authenticationsamlidppolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                                       newname=None, save=False):
    '''
    Update the running configuration for the authenticationsamlidppolicy config key.

    name(str): Name for the SAML Identity Provider (IdP) authentication policy. This is used for configuring Netscaler as
        SAML Identity Provider. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the policy is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression which is evaluated to choose a profile for authentication. Maximum length of a string literal in
        the expression is 255 characters. A longer string can be split into smaller strings of up to 255 characters each,
        and the smaller strings concatenated with the + operator. For example, you can create a 500-character string as
        follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;"  The following requirements
        apply only to the NetScaler CLI: * If the expression includes one or more spaces, enclose the entire expression
        in double quotation marks. * If the expression itself includes double quotation marks, escape the quotations by
        using the \\ character.  * Alternatively, you can use single quotation marks to enclose the rule, in which case
        you do not have to escape the double quotation marks. Minimum length = 1

    action(str): Name of the profile to apply to requests or connections that match this policy. Minimum length = 1

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any comments to preserve information about this policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the SAML IdentityProvider policy.  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters.  The following requirement applies only to the NetScaler
        CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for example,
        "my samlidppolicy policy" or my samlidppolicy policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationsamlidppolicy <args>

    '''

    result = {}

    payload = {'authenticationsamlidppolicy': {}}

    if name:
        payload['authenticationsamlidppolicy']['name'] = name

    if rule:
        payload['authenticationsamlidppolicy']['rule'] = rule

    if action:
        payload['authenticationsamlidppolicy']['action'] = action

    if undefaction:
        payload['authenticationsamlidppolicy']['undefaction'] = undefaction

    if comment:
        payload['authenticationsamlidppolicy']['comment'] = comment

    if logaction:
        payload['authenticationsamlidppolicy']['logaction'] = logaction

    if newname:
        payload['authenticationsamlidppolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/authenticationsamlidppolicy', payload)

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


def update_authenticationsamlidpprofile(name=None, samlspcertname=None, samlidpcertname=None,
                                        assertionconsumerserviceurl=None, sendpassword=None, samlissuername=None,
                                        rejectunsignedrequests=None, signaturealg=None, digestmethod=None, audience=None,
                                        nameidformat=None, nameidexpr=None, attribute1=None, attribute1expr=None,
                                        attribute1friendlyname=None, attribute1format=None, attribute2=None,
                                        attribute2expr=None, attribute2friendlyname=None, attribute2format=None,
                                        attribute3=None, attribute3expr=None, attribute3friendlyname=None,
                                        attribute3format=None, attribute4=None, attribute4expr=None,
                                        attribute4friendlyname=None, attribute4format=None, attribute5=None,
                                        attribute5expr=None, attribute5friendlyname=None, attribute5format=None,
                                        attribute6=None, attribute6expr=None, attribute6friendlyname=None,
                                        attribute6format=None, attribute7=None, attribute7expr=None,
                                        attribute7friendlyname=None, attribute7format=None, attribute8=None,
                                        attribute8expr=None, attribute8friendlyname=None, attribute8format=None,
                                        attribute9=None, attribute9expr=None, attribute9friendlyname=None,
                                        attribute9format=None, attribute10=None, attribute10expr=None,
                                        attribute10friendlyname=None, attribute10format=None, attribute11=None,
                                        attribute11expr=None, attribute11friendlyname=None, attribute11format=None,
                                        attribute12=None, attribute12expr=None, attribute12friendlyname=None,
                                        attribute12format=None, attribute13=None, attribute13expr=None,
                                        attribute13friendlyname=None, attribute13format=None, attribute14=None,
                                        attribute14expr=None, attribute14friendlyname=None, attribute14format=None,
                                        attribute15=None, attribute15expr=None, attribute15friendlyname=None,
                                        attribute15format=None, attribute16=None, attribute16expr=None,
                                        attribute16friendlyname=None, attribute16format=None, encryptassertion=None,
                                        encryptionalgorithm=None, samlbinding=None, skewtime=None,
                                        serviceproviderid=None, signassertion=None, keytransportalg=None,
                                        splogouturl=None, logoutbinding=None, save=False):
    '''
    Update the running configuration for the authenticationsamlidpprofile config key.

    name(str): Name for the new saml single sign-on profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after an action is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my action" or my action). Minimum length = 1

    samlspcertname(str): Name of the SSL certificate of SAML Relying Party. This certificate is used to verify signature of
        the incoming AuthnRequest from a Relying Party or Service Provider. Minimum length = 1

    samlidpcertname(str): Name of the signing authority as given in the SAML servers SSL certificate. This certificate is
        used to sign the SAMLResposne that is sent to Relying Party or Service Provider after successful authentication.
        Minimum length = 1

    assertionconsumerserviceurl(str): URL to which the assertion is to be sent. Minimum length = 1

    sendpassword(str): Option to send password in assertion. Default value: OFF Possible values = ON, OFF

    samlissuername(str): The name to be used in requests sent from Netscaler to IdP to uniquely identify Netscaler. Minimum
        length = 1

    rejectunsignedrequests(str): Option to Reject unsigned SAML Requests. ON option denies any authentication requests that
        arrive without signature. Default value: ON Possible values = ON, OFF

    signaturealg(str): Algorithm to be used to sign/verify SAML transactions. Default value: RSA-SHA1 Possible values =
        RSA-SHA1, RSA-SHA256

    digestmethod(str): Algorithm to be used to compute/verify digest for SAML transactions. Default value: SHA1 Possible
        values = SHA1, SHA256

    audience(str): Audience for which assertion sent by IdP is applicable. This is typically entity name or url that
        represents ServiceProvider.

    nameidformat(str): Format of Name Identifier sent in Assertion. Default value: transient Possible values = Unspecified,
        emailAddress, X509SubjectName, WindowsDomainQualifiedName, kerberos, entity, persistent, transient

    nameidexpr(str): Expression that will be evaluated to obtain NameIdentifier to be sent in assertion. Maximum length =
        128

    attribute1(str): Name of attribute1 that needs to be sent in SAML Assertion.

    attribute1expr(str): Expression that will be evaluated to obtain attribute1s value to be sent in Assertion. Maximum
        length = 128

    attribute1friendlyname(str): User-Friendly Name of attribute1 that needs to be sent in SAML Assertion.

    attribute1format(str): Format of Attribute1 to be sent in Assertion. Possible values = URI, Basic

    attribute2(str): Name of attribute2 that needs to be sent in SAML Assertion.

    attribute2expr(str): Expression that will be evaluated to obtain attribute2s value to be sent in Assertion. Maximum
        length = 128

    attribute2friendlyname(str): User-Friendly Name of attribute2 that needs to be sent in SAML Assertion.

    attribute2format(str): Format of Attribute2 to be sent in Assertion. Possible values = URI, Basic

    attribute3(str): Name of attribute3 that needs to be sent in SAML Assertion.

    attribute3expr(str): Expression that will be evaluated to obtain attribute3s value to be sent in Assertion. Maximum
        length = 128

    attribute3friendlyname(str): User-Friendly Name of attribute3 that needs to be sent in SAML Assertion.

    attribute3format(str): Format of Attribute3 to be sent in Assertion. Possible values = URI, Basic

    attribute4(str): Name of attribute4 that needs to be sent in SAML Assertion.

    attribute4expr(str): Expression that will be evaluated to obtain attribute4s value to be sent in Assertion. Maximum
        length = 128

    attribute4friendlyname(str): User-Friendly Name of attribute4 that needs to be sent in SAML Assertion.

    attribute4format(str): Format of Attribute4 to be sent in Assertion. Possible values = URI, Basic

    attribute5(str): Name of attribute5 that needs to be sent in SAML Assertion.

    attribute5expr(str): Expression that will be evaluated to obtain attribute5s value to be sent in Assertion. Maximum
        length = 128

    attribute5friendlyname(str): User-Friendly Name of attribute5 that needs to be sent in SAML Assertion.

    attribute5format(str): Format of Attribute5 to be sent in Assertion. Possible values = URI, Basic

    attribute6(str): Name of attribute6 that needs to be sent in SAML Assertion.

    attribute6expr(str): Expression that will be evaluated to obtain attribute6s value to be sent in Assertion. Maximum
        length = 128

    attribute6friendlyname(str): User-Friendly Name of attribute6 that needs to be sent in SAML Assertion.

    attribute6format(str): Format of Attribute6 to be sent in Assertion. Possible values = URI, Basic

    attribute7(str): Name of attribute7 that needs to be sent in SAML Assertion.

    attribute7expr(str): Expression that will be evaluated to obtain attribute7s value to be sent in Assertion. Maximum
        length = 128

    attribute7friendlyname(str): User-Friendly Name of attribute7 that needs to be sent in SAML Assertion.

    attribute7format(str): Format of Attribute7 to be sent in Assertion. Possible values = URI, Basic

    attribute8(str): Name of attribute8 that needs to be sent in SAML Assertion.

    attribute8expr(str): Expression that will be evaluated to obtain attribute8s value to be sent in Assertion. Maximum
        length = 128

    attribute8friendlyname(str): User-Friendly Name of attribute8 that needs to be sent in SAML Assertion.

    attribute8format(str): Format of Attribute8 to be sent in Assertion. Possible values = URI, Basic

    attribute9(str): Name of attribute9 that needs to be sent in SAML Assertion.

    attribute9expr(str): Expression that will be evaluated to obtain attribute9s value to be sent in Assertion. Maximum
        length = 128

    attribute9friendlyname(str): User-Friendly Name of attribute9 that needs to be sent in SAML Assertion.

    attribute9format(str): Format of Attribute9 to be sent in Assertion. Possible values = URI, Basic

    attribute10(str): Name of attribute10 that needs to be sent in SAML Assertion.

    attribute10expr(str): Expression that will be evaluated to obtain attribute10s value to be sent in Assertion. Maximum
        length = 128

    attribute10friendlyname(str): User-Friendly Name of attribute10 that needs to be sent in SAML Assertion.

    attribute10format(str): Format of Attribute10 to be sent in Assertion. Possible values = URI, Basic

    attribute11(str): Name of attribute11 that needs to be sent in SAML Assertion.

    attribute11expr(str): Expression that will be evaluated to obtain attribute11s value to be sent in Assertion. Maximum
        length = 128

    attribute11friendlyname(str): User-Friendly Name of attribute11 that needs to be sent in SAML Assertion.

    attribute11format(str): Format of Attribute11 to be sent in Assertion. Possible values = URI, Basic

    attribute12(str): Name of attribute12 that needs to be sent in SAML Assertion.

    attribute12expr(str): Expression that will be evaluated to obtain attribute12s value to be sent in Assertion. Maximum
        length = 128

    attribute12friendlyname(str): User-Friendly Name of attribute12 that needs to be sent in SAML Assertion.

    attribute12format(str): Format of Attribute12 to be sent in Assertion. Possible values = URI, Basic

    attribute13(str): Name of attribute13 that needs to be sent in SAML Assertion.

    attribute13expr(str): Expression that will be evaluated to obtain attribute13s value to be sent in Assertion. Maximum
        length = 128

    attribute13friendlyname(str): User-Friendly Name of attribute13 that needs to be sent in SAML Assertion.

    attribute13format(str): Format of Attribute13 to be sent in Assertion. Possible values = URI, Basic

    attribute14(str): Name of attribute14 that needs to be sent in SAML Assertion.

    attribute14expr(str): Expression that will be evaluated to obtain attribute14s value to be sent in Assertion. Maximum
        length = 128

    attribute14friendlyname(str): User-Friendly Name of attribute14 that needs to be sent in SAML Assertion.

    attribute14format(str): Format of Attribute14 to be sent in Assertion. Possible values = URI, Basic

    attribute15(str): Name of attribute15 that needs to be sent in SAML Assertion.

    attribute15expr(str): Expression that will be evaluated to obtain attribute15s value to be sent in Assertion. Maximum
        length = 128

    attribute15friendlyname(str): User-Friendly Name of attribute15 that needs to be sent in SAML Assertion.

    attribute15format(str): Format of Attribute15 to be sent in Assertion. Possible values = URI, Basic

    attribute16(str): Name of attribute16 that needs to be sent in SAML Assertion.

    attribute16expr(str): Expression that will be evaluated to obtain attribute16s value to be sent in Assertion. Maximum
        length = 128

    attribute16friendlyname(str): User-Friendly Name of attribute16 that needs to be sent in SAML Assertion.

    attribute16format(str): Format of Attribute16 to be sent in Assertion. Possible values = URI, Basic

    encryptassertion(str): Option to encrypt assertion when Netscaler IDP sends one. Default value: OFF Possible values = ON,
        OFF

    encryptionalgorithm(str): Algorithm to be used to encrypt SAML assertion. Default value: AES256 Possible values = DES3,
        AES128, AES192, AES256

    samlbinding(str): This element specifies the transport mechanism of saml messages. Default value: POST Possible values =
        REDIRECT, POST, ARTIFACT

    skewtime(int): This option specifies the number of minutes on either side of current time that the assertion would be
        valid. For example, if skewTime is 10, then assertion would be valid from (current time - 10) min to (current
        time + 10) min, ie 20min in all. Default value: 5

    serviceproviderid(str): Unique identifier of the Service Provider that sends SAML Request. Netscaler will ensure that the
        Issuer of the SAML Request matches this URI. Minimum length = 1

    signassertion(str): Option to sign portions of assertion when Netscaler IDP sends one. Based on the user selection,
        either Assertion or Response or Both or none can be signed. Default value: ASSERTION Possible values = NONE,
        ASSERTION, RESPONSE, BOTH

    keytransportalg(str): Key transport algorithm to be used in encryption of SAML assertion. Default value: RSA_OAEP
        Possible values = RSA-V1_5, RSA_OAEP

    splogouturl(str): Endpoint on the ServiceProvider (SP) to which logout messages are to be sent. Minimum length = 1

    logoutbinding(str): This element specifies the transport mechanism of saml logout messages. Default value: POST Possible
        values = REDIRECT, POST

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationsamlidpprofile <args>

    '''

    result = {}

    payload = {'authenticationsamlidpprofile': {}}

    if name:
        payload['authenticationsamlidpprofile']['name'] = name

    if samlspcertname:
        payload['authenticationsamlidpprofile']['samlspcertname'] = samlspcertname

    if samlidpcertname:
        payload['authenticationsamlidpprofile']['samlidpcertname'] = samlidpcertname

    if assertionconsumerserviceurl:
        payload['authenticationsamlidpprofile']['assertionconsumerserviceurl'] = assertionconsumerserviceurl

    if sendpassword:
        payload['authenticationsamlidpprofile']['sendpassword'] = sendpassword

    if samlissuername:
        payload['authenticationsamlidpprofile']['samlissuername'] = samlissuername

    if rejectunsignedrequests:
        payload['authenticationsamlidpprofile']['rejectunsignedrequests'] = rejectunsignedrequests

    if signaturealg:
        payload['authenticationsamlidpprofile']['signaturealg'] = signaturealg

    if digestmethod:
        payload['authenticationsamlidpprofile']['digestmethod'] = digestmethod

    if audience:
        payload['authenticationsamlidpprofile']['audience'] = audience

    if nameidformat:
        payload['authenticationsamlidpprofile']['nameidformat'] = nameidformat

    if nameidexpr:
        payload['authenticationsamlidpprofile']['nameidexpr'] = nameidexpr

    if attribute1:
        payload['authenticationsamlidpprofile']['attribute1'] = attribute1

    if attribute1expr:
        payload['authenticationsamlidpprofile']['attribute1expr'] = attribute1expr

    if attribute1friendlyname:
        payload['authenticationsamlidpprofile']['attribute1friendlyname'] = attribute1friendlyname

    if attribute1format:
        payload['authenticationsamlidpprofile']['attribute1format'] = attribute1format

    if attribute2:
        payload['authenticationsamlidpprofile']['attribute2'] = attribute2

    if attribute2expr:
        payload['authenticationsamlidpprofile']['attribute2expr'] = attribute2expr

    if attribute2friendlyname:
        payload['authenticationsamlidpprofile']['attribute2friendlyname'] = attribute2friendlyname

    if attribute2format:
        payload['authenticationsamlidpprofile']['attribute2format'] = attribute2format

    if attribute3:
        payload['authenticationsamlidpprofile']['attribute3'] = attribute3

    if attribute3expr:
        payload['authenticationsamlidpprofile']['attribute3expr'] = attribute3expr

    if attribute3friendlyname:
        payload['authenticationsamlidpprofile']['attribute3friendlyname'] = attribute3friendlyname

    if attribute3format:
        payload['authenticationsamlidpprofile']['attribute3format'] = attribute3format

    if attribute4:
        payload['authenticationsamlidpprofile']['attribute4'] = attribute4

    if attribute4expr:
        payload['authenticationsamlidpprofile']['attribute4expr'] = attribute4expr

    if attribute4friendlyname:
        payload['authenticationsamlidpprofile']['attribute4friendlyname'] = attribute4friendlyname

    if attribute4format:
        payload['authenticationsamlidpprofile']['attribute4format'] = attribute4format

    if attribute5:
        payload['authenticationsamlidpprofile']['attribute5'] = attribute5

    if attribute5expr:
        payload['authenticationsamlidpprofile']['attribute5expr'] = attribute5expr

    if attribute5friendlyname:
        payload['authenticationsamlidpprofile']['attribute5friendlyname'] = attribute5friendlyname

    if attribute5format:
        payload['authenticationsamlidpprofile']['attribute5format'] = attribute5format

    if attribute6:
        payload['authenticationsamlidpprofile']['attribute6'] = attribute6

    if attribute6expr:
        payload['authenticationsamlidpprofile']['attribute6expr'] = attribute6expr

    if attribute6friendlyname:
        payload['authenticationsamlidpprofile']['attribute6friendlyname'] = attribute6friendlyname

    if attribute6format:
        payload['authenticationsamlidpprofile']['attribute6format'] = attribute6format

    if attribute7:
        payload['authenticationsamlidpprofile']['attribute7'] = attribute7

    if attribute7expr:
        payload['authenticationsamlidpprofile']['attribute7expr'] = attribute7expr

    if attribute7friendlyname:
        payload['authenticationsamlidpprofile']['attribute7friendlyname'] = attribute7friendlyname

    if attribute7format:
        payload['authenticationsamlidpprofile']['attribute7format'] = attribute7format

    if attribute8:
        payload['authenticationsamlidpprofile']['attribute8'] = attribute8

    if attribute8expr:
        payload['authenticationsamlidpprofile']['attribute8expr'] = attribute8expr

    if attribute8friendlyname:
        payload['authenticationsamlidpprofile']['attribute8friendlyname'] = attribute8friendlyname

    if attribute8format:
        payload['authenticationsamlidpprofile']['attribute8format'] = attribute8format

    if attribute9:
        payload['authenticationsamlidpprofile']['attribute9'] = attribute9

    if attribute9expr:
        payload['authenticationsamlidpprofile']['attribute9expr'] = attribute9expr

    if attribute9friendlyname:
        payload['authenticationsamlidpprofile']['attribute9friendlyname'] = attribute9friendlyname

    if attribute9format:
        payload['authenticationsamlidpprofile']['attribute9format'] = attribute9format

    if attribute10:
        payload['authenticationsamlidpprofile']['attribute10'] = attribute10

    if attribute10expr:
        payload['authenticationsamlidpprofile']['attribute10expr'] = attribute10expr

    if attribute10friendlyname:
        payload['authenticationsamlidpprofile']['attribute10friendlyname'] = attribute10friendlyname

    if attribute10format:
        payload['authenticationsamlidpprofile']['attribute10format'] = attribute10format

    if attribute11:
        payload['authenticationsamlidpprofile']['attribute11'] = attribute11

    if attribute11expr:
        payload['authenticationsamlidpprofile']['attribute11expr'] = attribute11expr

    if attribute11friendlyname:
        payload['authenticationsamlidpprofile']['attribute11friendlyname'] = attribute11friendlyname

    if attribute11format:
        payload['authenticationsamlidpprofile']['attribute11format'] = attribute11format

    if attribute12:
        payload['authenticationsamlidpprofile']['attribute12'] = attribute12

    if attribute12expr:
        payload['authenticationsamlidpprofile']['attribute12expr'] = attribute12expr

    if attribute12friendlyname:
        payload['authenticationsamlidpprofile']['attribute12friendlyname'] = attribute12friendlyname

    if attribute12format:
        payload['authenticationsamlidpprofile']['attribute12format'] = attribute12format

    if attribute13:
        payload['authenticationsamlidpprofile']['attribute13'] = attribute13

    if attribute13expr:
        payload['authenticationsamlidpprofile']['attribute13expr'] = attribute13expr

    if attribute13friendlyname:
        payload['authenticationsamlidpprofile']['attribute13friendlyname'] = attribute13friendlyname

    if attribute13format:
        payload['authenticationsamlidpprofile']['attribute13format'] = attribute13format

    if attribute14:
        payload['authenticationsamlidpprofile']['attribute14'] = attribute14

    if attribute14expr:
        payload['authenticationsamlidpprofile']['attribute14expr'] = attribute14expr

    if attribute14friendlyname:
        payload['authenticationsamlidpprofile']['attribute14friendlyname'] = attribute14friendlyname

    if attribute14format:
        payload['authenticationsamlidpprofile']['attribute14format'] = attribute14format

    if attribute15:
        payload['authenticationsamlidpprofile']['attribute15'] = attribute15

    if attribute15expr:
        payload['authenticationsamlidpprofile']['attribute15expr'] = attribute15expr

    if attribute15friendlyname:
        payload['authenticationsamlidpprofile']['attribute15friendlyname'] = attribute15friendlyname

    if attribute15format:
        payload['authenticationsamlidpprofile']['attribute15format'] = attribute15format

    if attribute16:
        payload['authenticationsamlidpprofile']['attribute16'] = attribute16

    if attribute16expr:
        payload['authenticationsamlidpprofile']['attribute16expr'] = attribute16expr

    if attribute16friendlyname:
        payload['authenticationsamlidpprofile']['attribute16friendlyname'] = attribute16friendlyname

    if attribute16format:
        payload['authenticationsamlidpprofile']['attribute16format'] = attribute16format

    if encryptassertion:
        payload['authenticationsamlidpprofile']['encryptassertion'] = encryptassertion

    if encryptionalgorithm:
        payload['authenticationsamlidpprofile']['encryptionalgorithm'] = encryptionalgorithm

    if samlbinding:
        payload['authenticationsamlidpprofile']['samlbinding'] = samlbinding

    if skewtime:
        payload['authenticationsamlidpprofile']['skewtime'] = skewtime

    if serviceproviderid:
        payload['authenticationsamlidpprofile']['serviceproviderid'] = serviceproviderid

    if signassertion:
        payload['authenticationsamlidpprofile']['signassertion'] = signassertion

    if keytransportalg:
        payload['authenticationsamlidpprofile']['keytransportalg'] = keytransportalg

    if splogouturl:
        payload['authenticationsamlidpprofile']['splogouturl'] = splogouturl

    if logoutbinding:
        payload['authenticationsamlidpprofile']['logoutbinding'] = logoutbinding

    execution = __proxy__['citrixns.put']('config/authenticationsamlidpprofile', payload)

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


def update_authenticationsamlpolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Update the running configuration for the authenticationsamlpolicy config key.

    name(str): Name for the SAML policy.  Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after SAML policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the SAML server. Minimum length = 1

    reqaction(str): Name of the SAML authentication action to be performed if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationsamlpolicy <args>

    '''

    result = {}

    payload = {'authenticationsamlpolicy': {}}

    if name:
        payload['authenticationsamlpolicy']['name'] = name

    if rule:
        payload['authenticationsamlpolicy']['rule'] = rule

    if reqaction:
        payload['authenticationsamlpolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.put']('config/authenticationsamlpolicy', payload)

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


def update_authenticationstorefrontauthaction(name=None, serverurl=None, domain=None, defaultauthenticationgroup=None,
                                              save=False):
    '''
    Update the running configuration for the authenticationstorefrontauthaction config key.

    name(str): Name for the Storefront Authentication action.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Cannot be changed after the profile is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my authentication action" or my authentication action). Minimum
        length = 1

    serverurl(str): URL of the Storefront server. This is the FQDN of the Storefront server. example:
        https://storefront.com/. Authentication endpoints are learned dynamically by Gateway.

    domain(str): Domain of the server that is used for authentication. If users enter name without domain, this parameter is
        added to username in the authentication request to server.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationstorefrontauthaction <args>

    '''

    result = {}

    payload = {'authenticationstorefrontauthaction': {}}

    if name:
        payload['authenticationstorefrontauthaction']['name'] = name

    if serverurl:
        payload['authenticationstorefrontauthaction']['serverurl'] = serverurl

    if domain:
        payload['authenticationstorefrontauthaction']['domain'] = domain

    if defaultauthenticationgroup:
        payload['authenticationstorefrontauthaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    execution = __proxy__['citrixns.put']('config/authenticationstorefrontauthaction', payload)

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


def update_authenticationtacacsaction(name=None, serverip=None, serverport=None, authtimeout=None, tacacssecret=None,
                                      authorization=None, accounting=None, auditfailedcmds=None, groupattrname=None,
                                      defaultauthenticationgroup=None, attribute1=None, attribute2=None, attribute3=None,
                                      attribute4=None, attribute5=None, attribute6=None, attribute7=None,
                                      attribute8=None, attribute9=None, attribute10=None, attribute11=None,
                                      attribute12=None, attribute13=None, attribute14=None, attribute15=None,
                                      attribute16=None, save=False):
    '''
    Update the running configuration for the authenticationtacacsaction config key.

    name(str): Name for the TACACS+ profile (action).  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after TACACS profile is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my authentication action" or y authentication action). Minimum
        length = 1

    serverip(str): IP address assigned to the TACACS+ server. Minimum length = 1

    serverport(int): Port number on which the TACACS+ server listens for connections. Default value: 49 Minimum value = 1

    authtimeout(int): Number of seconds the NetScaler appliance waits for a response from the TACACS+ server. Default value:
        3 Minimum value = 1

    tacacssecret(str): Key shared between the TACACS+ server and the NetScaler appliance.  Required for allowing the
        NetScaler appliance to communicate with the TACACS+ server. Minimum length = 1

    authorization(str): Use streaming authorization on the TACACS+ server. Possible values = ON, OFF

    accounting(str): Whether the TACACS+ server is currently accepting accounting messages. Possible values = ON, OFF

    auditfailedcmds(str): The state of the TACACS+ server that will receive accounting messages. Possible values = ON, OFF

    groupattrname(str): TACACS+ group attribute name. Used for group extraction on the TACACS+ server.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Name of the custom attribute to be extracted from server and stored at index 1 (where 1 changes for each
        attribute).

    attribute2(str): Name of the custom attribute to be extracted from server and stored at index 2 (where 2 changes for each
        attribute).

    attribute3(str): Name of the custom attribute to be extracted from server and stored at index 3 (where 3 changes for each
        attribute).

    attribute4(str): Name of the custom attribute to be extracted from server and stored at index 4 (where 4 changes for each
        attribute).

    attribute5(str): Name of the custom attribute to be extracted from server and stored at index 5 (where 5 changes for each
        attribute).

    attribute6(str): Name of the custom attribute to be extracted from server and stored at index 6 (where 6 changes for each
        attribute).

    attribute7(str): Name of the custom attribute to be extracted from server and stored at index 7 (where 7 changes for each
        attribute).

    attribute8(str): Name of the custom attribute to be extracted from server and stored at index 8 (where 8 changes for each
        attribute).

    attribute9(str): Name of the custom attribute to be extracted from server and stored at index 9 (where 9 changes for each
        attribute).

    attribute10(str): Name of the custom attribute to be extracted from server and stored at index 10 (where 10 changes for
        each attribute).

    attribute11(str): Name of the custom attribute to be extracted from server and stored at index 11 (where 11 changes for
        each attribute).

    attribute12(str): Name of the custom attribute to be extracted from server and stored at index 12 (where 12 changes for
        each attribute).

    attribute13(str): Name of the custom attribute to be extracted from server and stored at index 13 (where 13 changes for
        each attribute).

    attribute14(str): Name of the custom attribute to be extracted from server and stored at index 14 (where 14 changes for
        each attribute).

    attribute15(str): Name of the custom attribute to be extracted from server and stored at index 15 (where 15 changes for
        each attribute).

    attribute16(str): Name of the custom attribute to be extracted from server and stored at index 16 (where 16 changes for
        each attribute).

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationtacacsaction <args>

    '''

    result = {}

    payload = {'authenticationtacacsaction': {}}

    if name:
        payload['authenticationtacacsaction']['name'] = name

    if serverip:
        payload['authenticationtacacsaction']['serverip'] = serverip

    if serverport:
        payload['authenticationtacacsaction']['serverport'] = serverport

    if authtimeout:
        payload['authenticationtacacsaction']['authtimeout'] = authtimeout

    if tacacssecret:
        payload['authenticationtacacsaction']['tacacssecret'] = tacacssecret

    if authorization:
        payload['authenticationtacacsaction']['authorization'] = authorization

    if accounting:
        payload['authenticationtacacsaction']['accounting'] = accounting

    if auditfailedcmds:
        payload['authenticationtacacsaction']['auditfailedcmds'] = auditfailedcmds

    if groupattrname:
        payload['authenticationtacacsaction']['groupattrname'] = groupattrname

    if defaultauthenticationgroup:
        payload['authenticationtacacsaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationtacacsaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationtacacsaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationtacacsaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationtacacsaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationtacacsaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationtacacsaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationtacacsaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationtacacsaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationtacacsaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationtacacsaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationtacacsaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationtacacsaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationtacacsaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationtacacsaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationtacacsaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationtacacsaction']['attribute16'] = attribute16

    execution = __proxy__['citrixns.put']('config/authenticationtacacsaction', payload)

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


def update_authenticationtacacspolicy(name=None, rule=None, reqaction=None, save=False):
    '''
    Update the running configuration for the authenticationtacacspolicy config key.

    name(str): Name for the TACACS+ policy.  Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after TACACS+ policy is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the TACACS+ server. Minimum length = 1

    reqaction(str): Name of the TACACS+ action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationtacacspolicy <args>

    '''

    result = {}

    payload = {'authenticationtacacspolicy': {}}

    if name:
        payload['authenticationtacacspolicy']['name'] = name

    if rule:
        payload['authenticationtacacspolicy']['rule'] = rule

    if reqaction:
        payload['authenticationtacacspolicy']['reqaction'] = reqaction

    execution = __proxy__['citrixns.put']('config/authenticationtacacspolicy', payload)

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


def update_authenticationvserver(name=None, servicetype=None, ipv46=None, range=None, port=None, state=None,
                                 authentication=None, authenticationdomain=None, comment=None, td=None, appflowlog=None,
                                 maxloginattempts=None, failedlogintimeout=None, newname=None, save=False):
    '''
    Update the running configuration for the authenticationvserver config key.

    name(str): Name for the new authentication virtual server.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Can be changed after the authentication virtual server is added by
        using the rename authentication vserver command.  The following requirement applies only to the NetScaler CLI: If
        the name includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        authentication policy" or my authentication policy). Minimum length = 1

    servicetype(str): Protocol type of the authentication virtual server. Always SSL. Default value: SSL Possible values =
        SSL

    ipv46(str): IP address of the authentication virtual server, if a single IP address is assigned to the virtual server.
        Minimum length = 1

    range(int): If you are creating a series of virtual servers with a range of IP addresses assigned to them, the length of
        the range.  The new range of authentication virtual servers will have IP addresses consecutively numbered,
        starting with the primary address specified with the IP Address parameter. Default value: 1 Minimum value = 1

    port(int): TCP port on which the virtual server accepts connections. Range 1 - 65535 * in CLI is represented as 65535 in
        NITRO API

    state(str): Initial state of the new virtual server. Default value: ENABLED Possible values = ENABLED, DISABLED

    authentication(str): Require users to be authenticated before sending traffic through this virtual server. Default value:
        ON Possible values = ON, OFF

    authenticationdomain(str): The domain of the authentication cookie set by Authentication vserver. Minimum length = 3
        Maximum length = 252

    comment(str): Any comments associated with this virtual server.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    appflowlog(str): Log AppFlow flow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    maxloginattempts(int): Maximum Number of login Attempts. Minimum value = 1 Maximum value = 255

    failedlogintimeout(int): Number of minutes an account will be locked if user exceeds maximum permissible attempts.
        Minimum value = 1

    newname(str): New name of the authentication virtual server.  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters.  The following requirement applies only to the NetScaler
        CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for example,
        my authentication policy or "my authentication policy"). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationvserver <args>

    '''

    result = {}

    payload = {'authenticationvserver': {}}

    if name:
        payload['authenticationvserver']['name'] = name

    if servicetype:
        payload['authenticationvserver']['servicetype'] = servicetype

    if ipv46:
        payload['authenticationvserver']['ipv46'] = ipv46

    if range:
        payload['authenticationvserver']['range'] = range

    if port:
        payload['authenticationvserver']['port'] = port

    if state:
        payload['authenticationvserver']['state'] = state

    if authentication:
        payload['authenticationvserver']['authentication'] = authentication

    if authenticationdomain:
        payload['authenticationvserver']['authenticationdomain'] = authenticationdomain

    if comment:
        payload['authenticationvserver']['comment'] = comment

    if td:
        payload['authenticationvserver']['td'] = td

    if appflowlog:
        payload['authenticationvserver']['appflowlog'] = appflowlog

    if maxloginattempts:
        payload['authenticationvserver']['maxloginattempts'] = maxloginattempts

    if failedlogintimeout:
        payload['authenticationvserver']['failedlogintimeout'] = failedlogintimeout

    if newname:
        payload['authenticationvserver']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/authenticationvserver', payload)

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


def update_authenticationwebauthaction(name=None, serverip=None, serverport=None, fullreqexpr=None, scheme=None,
                                       successrule=None, defaultauthenticationgroup=None, attribute1=None,
                                       attribute2=None, attribute3=None, attribute4=None, attribute5=None,
                                       attribute6=None, attribute7=None, attribute8=None, attribute9=None,
                                       attribute10=None, attribute11=None, attribute12=None, attribute13=None,
                                       attribute14=None, attribute15=None, attribute16=None, save=False):
    '''
    Update the running configuration for the authenticationwebauthaction config key.

    name(str): Name for the Web Authentication action.  Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the profile is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication action" or my authentication action). Minimum length = 1

    serverip(str): IP address of the web server to be used for authentication. Minimum length = 1

    serverport(int): Port on which the web server accepts connections. Minimum value = 1 Range 1 - 65535 * in CLI is
        represented as 65535 in NITRO API

    fullreqexpr(str): Exact HTTP request, in the form of a default syntax expression, which the NetScaler appliance sends to
        the authentication server. The NetScaler appliance does not check the validity of this request. One must manually
        validate the request.

    scheme(str): Type of scheme for the web server. Possible values = http, https

    successrule(str): Expression, that checks to see if authentication is successful.

    defaultauthenticationgroup(str): This is the default group that is chosen when the authentication succeeds in addition to
        extracted groups.

    attribute1(str): Expression that would be evaluated to extract attribute1 from the webauth response. Maximum length =
        128

    attribute2(str): Expression that would be evaluated to extract attribute2 from the webauth response. Maximum length =
        128

    attribute3(str): Expression that would be evaluated to extract attribute3 from the webauth response. Maximum length =
        128

    attribute4(str): Expression that would be evaluated to extract attribute4 from the webauth response. Maximum length =
        128

    attribute5(str): Expression that would be evaluated to extract attribute5 from the webauth response. Maximum length =
        128

    attribute6(str): Expression that would be evaluated to extract attribute6 from the webauth response. Maximum length =
        128

    attribute7(str): Expression that would be evaluated to extract attribute7 from the webauth response. Maximum length =
        128

    attribute8(str): Expression that would be evaluated to extract attribute8 from the webauth response. Maximum length =
        128

    attribute9(str): Expression that would be evaluated to extract attribute9 from the webauth response. Maximum length =
        128

    attribute10(str): Expression that would be evaluated to extract attribute10 from the webauth response. Maximum length =
        128

    attribute11(str): Expression that would be evaluated to extract attribute11 from the webauth response. Maximum length =
        128

    attribute12(str): Expression that would be evaluated to extract attribute12 from the webauth response. Maximum length =
        128

    attribute13(str): Expression that would be evaluated to extract attribute13 from the webauth response. Maximum length =
        128

    attribute14(str): Expression that would be evaluated to extract attribute14 from the webauth response. Maximum length =
        128

    attribute15(str): Expression that would be evaluated to extract attribute15 from the webauth response. Maximum length =
        128

    attribute16(str): Expression that would be evaluated to extract attribute16 from the webauth response. Maximum length =
        128

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationwebauthaction <args>

    '''

    result = {}

    payload = {'authenticationwebauthaction': {}}

    if name:
        payload['authenticationwebauthaction']['name'] = name

    if serverip:
        payload['authenticationwebauthaction']['serverip'] = serverip

    if serverport:
        payload['authenticationwebauthaction']['serverport'] = serverport

    if fullreqexpr:
        payload['authenticationwebauthaction']['fullreqexpr'] = fullreqexpr

    if scheme:
        payload['authenticationwebauthaction']['scheme'] = scheme

    if successrule:
        payload['authenticationwebauthaction']['successrule'] = successrule

    if defaultauthenticationgroup:
        payload['authenticationwebauthaction']['defaultauthenticationgroup'] = defaultauthenticationgroup

    if attribute1:
        payload['authenticationwebauthaction']['attribute1'] = attribute1

    if attribute2:
        payload['authenticationwebauthaction']['attribute2'] = attribute2

    if attribute3:
        payload['authenticationwebauthaction']['attribute3'] = attribute3

    if attribute4:
        payload['authenticationwebauthaction']['attribute4'] = attribute4

    if attribute5:
        payload['authenticationwebauthaction']['attribute5'] = attribute5

    if attribute6:
        payload['authenticationwebauthaction']['attribute6'] = attribute6

    if attribute7:
        payload['authenticationwebauthaction']['attribute7'] = attribute7

    if attribute8:
        payload['authenticationwebauthaction']['attribute8'] = attribute8

    if attribute9:
        payload['authenticationwebauthaction']['attribute9'] = attribute9

    if attribute10:
        payload['authenticationwebauthaction']['attribute10'] = attribute10

    if attribute11:
        payload['authenticationwebauthaction']['attribute11'] = attribute11

    if attribute12:
        payload['authenticationwebauthaction']['attribute12'] = attribute12

    if attribute13:
        payload['authenticationwebauthaction']['attribute13'] = attribute13

    if attribute14:
        payload['authenticationwebauthaction']['attribute14'] = attribute14

    if attribute15:
        payload['authenticationwebauthaction']['attribute15'] = attribute15

    if attribute16:
        payload['authenticationwebauthaction']['attribute16'] = attribute16

    execution = __proxy__['citrixns.put']('config/authenticationwebauthaction', payload)

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


def update_authenticationwebauthpolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the authenticationwebauthpolicy config key.

    name(str): Name for the WebAuth policy.  Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after LDAP policy is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my authentication policy" or my authentication policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to determine whether to
        attempt to authenticate the user with the Web server. Minimum length = 1

    action(str): Name of the WebAuth action to perform if the policy matches. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authentication.update_authenticationwebauthpolicy <args>

    '''

    result = {}

    payload = {'authenticationwebauthpolicy': {}}

    if name:
        payload['authenticationwebauthpolicy']['name'] = name

    if rule:
        payload['authenticationwebauthpolicy']['rule'] = rule

    if action:
        payload['authenticationwebauthpolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/authenticationwebauthpolicy', payload)

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
